"""Batch code-chunk indexing lifecycle."""

import hashlib
import logging
from datetime import UTC, datetime

from reponyx.repositories.models import CodeChunk
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import EmbeddingError, EmbeddingProvider
from reponyx.retrieval.models import ChunkRecord, IndexStatus
from reponyx.retrieval.store import IndexStatusRecord, VectorStore, status_from_record

logger = logging.getLogger(__name__)


def chunk_id(repository_id: str, chunk: CodeChunk) -> str:
    identity = (
        f"{repository_id}:{chunk.file_path}:{chunk.start_line}:{chunk.end_line}:"
        f"{chunk.symbol}:{chunk.content}"
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def normalize_for_embedding(chunk: CodeChunk | ChunkRecord) -> str:
    symbol = chunk.symbol if isinstance(chunk, CodeChunk) else chunk.symbol_name
    header = f"file: {chunk.file_path}\nlanguage: {chunk.language}\nsymbol: {symbol or ''}"
    imports = "\n".join(chunk.relevant_imports)
    return f"{header}\nimports:\n{imports}\ncode:\n{chunk.content}".strip()


class IndexingService:
    def __init__(
        self,
        repositories: RepositoryService,
        vectors: VectorStore,
        embeddings: EmbeddingProvider,
        batch_size: int,
    ) -> None:
        self.repositories = repositories
        self.vectors = vectors
        self.embeddings = embeddings
        self.batch_size = batch_size

    def status(self, repository_id: str) -> IndexStatus:
        with self.vectors.sessions() as session:
            record = session.get(IndexStatusRecord, repository_id)
        if record is None:
            return IndexStatus(
                repository_id=repository_id,
                embedding_provider=self.embeddings.name,
                embedding_model=self.embeddings.model,
            )
        return status_from_record(record)

    def index(self, repository_id: str) -> IndexStatus:
        analysis = self.repositories.store.analysis(repository_id)
        if analysis is None:
            raise KeyError(repository_id)
        symbol_types = {
            (item.get("file_path"), item.get("name")): item.get("symbol_type")
            for item in analysis.get("symbols", [])
            if isinstance(item, dict)
        }
        chunks = [
            self._chunk_from_dict(repository_id, item, symbol_types)
            for item in analysis.get("chunks", [])
        ]
        status = IndexStatus(
            repository_id,
            "indexing",
            embedding_provider=self.embeddings.name,
            embedding_model=self.embeddings.model,
            started_at=datetime.now(UTC),
        )
        self._save_status(status)
        records: list[tuple[ChunkRecord, list[float]]] = []
        for offset in range(0, len(chunks), self.batch_size):
            batch = chunks[offset : offset + self.batch_size]
            status.chunks_processed += len(batch)
            try:
                vectors = self.embeddings.embed([normalize_for_embedding(chunk) for chunk in batch])
                if len(vectors) != len(batch):
                    raise EmbeddingError("embedding provider returned a partial batch")
                records.extend(zip(batch, vectors, strict=True))
                status.chunks_indexed += len(batch)
                logger.info(
                    "embedding_batch_completed",
                    extra={"repository_id": repository_id, "batch_size": len(batch)},
                )
            except EmbeddingError as exc:
                status.chunks_failed += len(batch)
                status.failures.append(str(exc))
                logger.warning(
                    "embedding_batch_failed",
                    extra={"repository_id": repository_id, "error": str(exc)},
                )
        if status.chunks_failed:
            status.status = "failed"
            self.vectors.delete_repository(repository_id)
        else:
            self.vectors.replace_repository(repository_id, records)
            status.status = "completed"
        status.completed_at = datetime.now(UTC)
        self._save_status(status)
        logger.info(
            "index_completed",
            extra={"repository_id": repository_id, "chunks_indexed": status.chunks_indexed},
        )
        return status

    def _save_status(self, status: IndexStatus) -> None:
        with self.vectors.sessions.begin() as session:
            record = session.get(IndexStatusRecord, status.repository_id)
            if record is None:
                record = IndexStatusRecord(repository_id=status.repository_id)
                session.add(record)
            record.status = status.status
            record.chunks_processed = status.chunks_processed
            record.chunks_indexed = status.chunks_indexed
            record.chunks_failed = status.chunks_failed
            record.embedding_provider = status.embedding_provider
            record.embedding_model = status.embedding_model
            record.started_at = status.started_at
            record.completed_at = status.completed_at
            record.failures = __import__("json").dumps(status.failures)

    @staticmethod
    def _chunk_from_dict(
        repository_id: str,
        item: object,
        symbol_types: dict[tuple[object, object], object],
    ) -> ChunkRecord:
        data = item if isinstance(item, dict) else {}
        chunk = CodeChunk(
            file_path=str(data.get("file_path", "")),
            symbol=data.get("symbol") if isinstance(data.get("symbol"), str) else None,
            language=str(data.get("language", "")),
            start_line=int(data.get("start_line", 0)),
            end_line=int(data.get("end_line", 0)),
            content=str(data.get("content", "")),
            parent_symbol=data.get("parent_symbol")
            if isinstance(data.get("parent_symbol"), str)
            else None,
            relevant_imports=tuple(data.get("relevant_imports", [])),
        )
        return ChunkRecord(
            chunk_id=chunk_id(repository_id, chunk),
            repository_id=repository_id,
            file_path=chunk.file_path,
            symbol_name=chunk.symbol,
            symbol_type=(
                str(symbol_types.get((chunk.file_path, chunk.symbol)))
                if (chunk.file_path, chunk.symbol) in symbol_types
                else None
            ),
            language=chunk.language,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            content=chunk.content,
            parent_symbol=chunk.parent_symbol,
            relevant_imports=chunk.relevant_imports,
        )
