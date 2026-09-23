"""Application service composing indexing and retrieval dependencies."""

from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import EmbeddingProvider
from reponyx.retrieval.indexer import IndexingService
from reponyx.retrieval.models import (
    ContextDocument,
    IndexStatus,
    RetrievalFilters,
    RetrievalResult,
)
from reponyx.retrieval.pipeline import Reranker, RetrievalPipeline
from reponyx.retrieval.store import VectorStore


class RetrievalService:
    def __init__(
        self,
        repositories: RepositoryService,
        vectors: VectorStore,
        embeddings: EmbeddingProvider,
        batch_size: int,
        semantic_weight: float,
        lexical_weight: float,
        character_budget: int,
    ) -> None:
        self.indexer = IndexingService(repositories, vectors, embeddings, batch_size)
        self.pipeline = RetrievalPipeline(
            vectors,
            embeddings,
            semantic_weight=semantic_weight,
            lexical_weight=lexical_weight,
            character_budget=character_budget,
            reranker=Reranker(),
        )

    def index(self, repository_id: str) -> IndexStatus:
        return self.indexer.index(repository_id)

    def status(self, repository_id: str) -> IndexStatus:
        if self.indexer.repositories.get(repository_id) is None:
            raise KeyError(repository_id)
        return self.indexer.status(repository_id)

    def is_indexed(self, repository_id: str) -> bool:
        if self.indexer.repositories.get(repository_id) is None:
            return False
        return self.indexer.vectors.is_indexed(repository_id)

    def search(
        self,
        repository_id: str,
        query: str,
        top_k: int,
        filters: RetrievalFilters,
        rerank: bool,
        semantic_weight: float | None = None,
        lexical_weight: float | None = None,
    ) -> list[RetrievalResult]:
        if self.indexer.repositories.get(repository_id) is None:
            raise KeyError(repository_id)
        return self.pipeline.search(
            repository_id,
            query,
            top_k,
            filters,
            rerank,
            semantic_weight,
            lexical_weight,
        )

    def context(
        self,
        repository_id: str,
        query: str,
        top_k: int,
        filters: RetrievalFilters,
        rerank: bool,
        semantic_weight: float | None = None,
        lexical_weight: float | None = None,
    ) -> ContextDocument:
        if self.indexer.repositories.get(repository_id) is None:
            raise KeyError(repository_id)
        return self.pipeline.context(
            self.search(
                repository_id,
                query,
                top_k,
                filters,
                rerank,
                semantic_weight,
                lexical_weight,
            )
        )
