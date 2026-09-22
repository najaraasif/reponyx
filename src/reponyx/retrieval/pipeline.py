"""Code-aware lexical, semantic, and hybrid retrieval pipeline."""

import logging
import re
from collections.abc import Callable
from dataclasses import replace

from reponyx.retrieval.embeddings import EmbeddingProvider
from reponyx.retrieval.models import (
    ContextDocument,
    ContextSource,
    RetrievalFilters,
    RetrievalResult,
)
from reponyx.retrieval.store import VectorStore

logger = logging.getLogger(__name__)


class QueryRewriter:
    """Controlled deterministic rewrite with an optional external adapter."""

    _terms = {
        "login": ("authentication entry point", "credential validation", "session creation"),
        "password reset": (
            "password reset token",
            "reset password endpoint",
            "credential recovery",
        ),
        "authentication": ("auth service", "login endpoint", "credential validation"),
    }

    def __init__(self, external: Callable[[str], list[str]] | None = None) -> None:
        self.external = external

    def rewrite(self, query: str) -> list[str]:
        try:
            if self.external:
                rewritten = self.external(query)
                if rewritten:
                    return [query, *rewritten[:3]]
        except Exception:  # provider failures must not break retrieval
            logger.warning("query_rewrite_failed")
        additions = next(
            (terms for phrase, terms in self._terms.items() if phrase in query.lower()), ()
        )
        return [query, *additions]


class Reranker:
    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        query_tokens = {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query)}
        rescored = []
        for result in results:
            identifier_hits = len(
                query_tokens
                & {
                    token.lower()
                    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", result.symbol_name or "")
                }
            )
            score = min(1.0, result.hybrid_score + identifier_hits * 0.05)
            rescored.append(replace(result, hybrid_score=score, retrieval_method="reranked"))
        return sorted(rescored, key=lambda item: item.hybrid_score, reverse=True)


class RetrievalPipeline:
    def __init__(
        self,
        vectors: VectorStore,
        embeddings: EmbeddingProvider,
        rewriter: QueryRewriter | None = None,
        reranker: Reranker | None = None,
        semantic_weight: float = 0.65,
        lexical_weight: float = 0.35,
        character_budget: int = 20_000,
    ) -> None:
        if not 0 <= semantic_weight <= 1 or not 0 <= lexical_weight <= 1:
            raise ValueError("retrieval weights must be between zero and one")
        self.vectors = vectors
        self.embeddings = embeddings
        self.rewriter = rewriter or QueryRewriter()
        self.reranker = reranker
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.character_budget = character_budget

    def search(
        self,
        repository_id: str,
        query: str,
        top_k: int = 8,
        filters: RetrievalFilters | None = None,
        rerank: bool = False,
        semantic_weight: float | None = None,
        lexical_weight: float | None = None,
    ) -> list[RetrievalResult]:
        filters = filters or RetrievalFilters()
        queries = self.rewriter.rewrite(query)
        semantic_query = self.embeddings.embed([query])[0]
        semantic = self.vectors.search_semantic(repository_id, semantic_query, top_k * 3, filters)
        lexical: dict[str, RetrievalResult] = {}
        for rewritten in queries:
            for result in self.vectors.search_lexical(repository_id, rewritten, top_k * 3, filters):
                prior = lexical.get(result.chunk_id)
                if prior is None or result.lexical_score > prior.lexical_score:
                    lexical[result.chunk_id] = result
        semantic_by_id = {result.chunk_id: result for result in semantic}
        semantic_weight = self.semantic_weight if semantic_weight is None else semantic_weight
        lexical_weight = self.lexical_weight if lexical_weight is None else lexical_weight
        if not 0 <= semantic_weight <= 1 or not 0 <= lexical_weight <= 1:
            raise ValueError("retrieval weights must be between zero and one")
        candidates: list[RetrievalResult] = []
        for chunk_id in set(semantic_by_id) | set(lexical):
            sem = semantic_by_id.get(chunk_id)
            lex = lexical.get(chunk_id)
            base = sem or lex
            assert base is not None
            semantic_score = sem.semantic_score if sem else 0.0
            lexical_score = lex.lexical_score if lex else 0.0
            hybrid = semantic_weight * semantic_score + lexical_weight * lexical_score
            method = "hybrid" if sem and lex else ("semantic" if sem else "lexical")
            candidates.append(
                replace(
                    base,
                    semantic_score=semantic_score,
                    lexical_score=lexical_score,
                    hybrid_score=hybrid,
                    retrieval_method=method,
                )
            )
        results = sorted(candidates, key=lambda result: result.hybrid_score, reverse=True)
        if rerank and self.reranker:
            results = self.reranker.rerank(query, results)
        logger.info(
            "search_completed",
            extra={
                "repository_id": repository_id,
                "retrieval_method": "hybrid",
                "result_count": len(results),
            },
        )
        return _deduplicate(results)[:top_k]

    def search_lexical(
        self, repository_id: str, query: str, top_k: int, filters: RetrievalFilters
    ) -> list[RetrievalResult]:
        return self.vectors.search_lexical(repository_id, query, top_k, filters)

    def search_semantic(
        self, repository_id: str, query: str, top_k: int, filters: RetrievalFilters
    ) -> list[RetrievalResult]:
        return self.vectors.search_semantic(
            repository_id, self.embeddings.embed([query])[0], top_k, filters
        )

    def context(self, results: list[RetrievalResult]) -> ContextDocument:
        selected: list[RetrievalResult] = []
        seen_locations: set[tuple[str, int, int]] = set()
        size = 0
        for result in results:
            location = (result.file_path, result.start_line, result.end_line)
            if location in seen_locations:
                continue
            block = _format_result(result)
            if size + len(block) > self.character_budget:
                continue
            selected.append(result)
            seen_locations.add(location)
            size += len(block)
        sources = tuple(
            ContextSource(
                source_id=result.chunk_id,
                repository_id=result.repository_id,
                file_path=result.file_path,
                symbol_name=result.symbol_name,
                language=result.language,
                start_line=result.start_line,
                end_line=result.end_line,
                score=result.hybrid_score,
                retrieval_method=result.retrieval_method,
            )
            for result in selected
        )
        return ContextDocument("\n\n".join(_format_result(result) for result in selected), sources)


def _deduplicate(results: list[RetrievalResult]) -> list[RetrievalResult]:
    unique: dict[tuple[str, int, int], RetrievalResult] = {}
    for result in results:
        key = (result.file_path, result.start_line, result.end_line)
        if key not in unique or result.hybrid_score > unique[key].hybrid_score:
            unique[key] = result
    return list(unique.values())


def _format_result(result: RetrievalResult) -> str:
    return (
        f"SOURCE: {result.file_path}\nSYMBOL: {result.symbol_name or ''}\n"
        f"LINES: {result.start_line}-{result.end_line}\n"
        f"RETRIEVAL: {result.retrieval_method}\nSCORE: {result.hybrid_score:.4f}\n\n"
        f"{result.content}"
    )
