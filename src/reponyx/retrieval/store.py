"""Repository-scoped vector and lexical index backed by SQLAlchemy."""

import json
import math
import re
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from reponyx.repositories.database import Base, RepositoryStore
from reponyx.retrieval.models import ChunkRecord, IndexStatus, RetrievalFilters, RetrievalResult


class VectorRecord(Base):
    __tablename__ = "code_vectors"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(32), index=True)
    file_path: Mapped[str] = mapped_column(String(1_000), index=True)
    symbol_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    symbol_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(32), index=True)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    parent_symbol: Mapped[str | None] = mapped_column(String(500), nullable=True)
    relevant_imports: Mapped[str] = mapped_column(Text, default="[]")
    embedding: Mapped[str] = mapped_column(Text)


class IndexStatusRecord(Base):
    __tablename__ = "retrieval_index_status"

    repository_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    chunks_processed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_indexed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_failed: Mapped[int] = mapped_column(Integer, default=0)
    embedding_provider: Mapped[str] = mapped_column(String(100), default="")
    embedding_model: Mapped[str] = mapped_column(String(200), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failures: Mapped[str] = mapped_column(Text, default="[]")


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value)}


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True))))


class VectorStore:
    def __init__(self, repository_store: RepositoryStore) -> None:
        self.repository_store = repository_store
        self.engine = repository_store.engine
        Base.metadata.create_all(self.engine)
        self.sessions = repository_store.sessions

    def replace_repository(
        self, repository_id: str, records: list[tuple[ChunkRecord, list[float]]]
    ) -> None:
        with self.sessions.begin() as session:
            session.execute(delete(VectorRecord).where(VectorRecord.repository_id == repository_id))
            for chunk, embedding in records:
                session.add(
                    VectorRecord(
                        chunk_id=chunk.chunk_id,
                        repository_id=chunk.repository_id,
                        file_path=chunk.file_path,
                        symbol_name=chunk.symbol_name,
                        symbol_type=chunk.symbol_type,
                        language=chunk.language,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        content=chunk.content,
                        parent_symbol=chunk.parent_symbol,
                        relevant_imports=json.dumps(chunk.relevant_imports),
                        embedding=json.dumps(embedding),
                    )
                )

    def count(self, repository_id: str) -> int:
        with self.sessions() as session:
            return len(
                session.scalars(
                    select(VectorRecord.chunk_id).where(VectorRecord.repository_id == repository_id)
                ).all()
            )

    def delete_repository(self, repository_id: str) -> None:
        with self.sessions.begin() as session:
            session.execute(delete(VectorRecord).where(VectorRecord.repository_id == repository_id))

    def search_semantic(
        self,
        repository_id: str,
        query_embedding: list[float],
        top_k: int,
        filters: RetrievalFilters,
    ) -> list[RetrievalResult]:
        rows = self._filtered(repository_id, filters)
        scored = [(row, cosine(query_embedding, json.loads(row.embedding))) for row in rows]
        scores = _normalize([score for _, score in scored])
        results = [
            self._result(row, score, 0.0, score, "semantic")
            for (row, _), score in zip(scored, scores, strict=True)
        ]
        return sorted(results, key=lambda result: result.semantic_score, reverse=True)[:top_k]

    def search_lexical(
        self, repository_id: str, query: str, top_k: int, filters: RetrievalFilters
    ) -> list[RetrievalResult]:
        query_tokens = _tokens(query)
        rows = self._filtered(repository_id, filters)
        scored: list[tuple[VectorRecord, float]] = []
        for row in rows:
            searchable = f"{row.file_path} {row.symbol_name or ''} {row.content}"
            overlap = len(query_tokens & _tokens(searchable)) / max(len(query_tokens), 1)
            exact_symbol = (
                1.0 if row.symbol_name and row.symbol_name.lower() in query.lower() else 0.0
            )
            score = min(1.0, overlap * 0.7 + exact_symbol * 0.3)
            if score > 0:
                scored.append((row, score))
        results = [self._result(row, 0.0, score, score, "lexical") for row, score in scored]
        return sorted(results, key=lambda result: result.lexical_score, reverse=True)[:top_k]

    def _filtered(self, repository_id: str, filters: RetrievalFilters) -> list[VectorRecord]:
        with self.sessions() as session:
            statement = select(VectorRecord).where(VectorRecord.repository_id == repository_id)
            if filters.language:
                statement = statement.where(VectorRecord.language == filters.language)
            if filters.file_path:
                statement = statement.where(VectorRecord.file_path.startswith(filters.file_path))
            if filters.symbol_type:
                statement = statement.where(VectorRecord.symbol_type == filters.symbol_type)
            return list(session.scalars(statement))

    @staticmethod
    def _result(
        row: VectorRecord, semantic: float, lexical: float, hybrid: float, method: str
    ) -> RetrievalResult:
        return RetrievalResult(
            row.chunk_id,
            row.repository_id,
            row.file_path,
            row.symbol_name,
            row.symbol_type,
            row.language,
            row.start_line,
            row.end_line,
            row.content,
            semantic,
            lexical,
            hybrid,
            method,
        )


def _normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    low, high = min(scores), max(scores)
    if math.isclose(low, high):
        return [1.0 if high > 0 else 0.0 for _ in scores]
    return [(score - low) / (high - low) for score in scores]


def status_from_record(record: IndexStatusRecord) -> IndexStatus:
    return IndexStatus(
        repository_id=record.repository_id,
        status=record.status,
        chunks_processed=record.chunks_processed,
        chunks_indexed=record.chunks_indexed,
        chunks_failed=record.chunks_failed,
        embedding_provider=record.embedding_provider,
        embedding_model=record.embedding_model,
        started_at=record.started_at,
        completed_at=record.completed_at,
        failures=json.loads(record.failures),
    )
