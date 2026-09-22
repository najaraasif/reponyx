"""Typed models for indexing, search, and context assembly."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    repository_id: str
    file_path: str
    symbol_name: str | None
    symbol_type: str | None
    language: str
    start_line: int
    end_line: int
    content: str
    parent_symbol: str | None = None
    relevant_imports: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    language: str | None = None
    file_path: str | None = None
    symbol_type: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunk_id: str
    repository_id: str
    file_path: str
    symbol_name: str | None
    symbol_type: str | None
    language: str
    start_line: int
    end_line: int
    content: str
    semantic_score: float
    lexical_score: float
    hybrid_score: float
    retrieval_method: str


@dataclass(frozen=True, slots=True)
class ContextSource:
    source_id: str
    repository_id: str
    file_path: str
    symbol_name: str | None
    language: str
    start_line: int
    end_line: int
    score: float
    retrieval_method: str


@dataclass(frozen=True, slots=True)
class ContextDocument:
    text: str
    sources: tuple[ContextSource, ...]


@dataclass(slots=True)
class IndexStatus:
    repository_id: str
    status: str = "pending"
    chunks_processed: int = 0
    chunks_indexed: int = 0
    chunks_failed: int = 0
    embedding_provider: str = ""
    embedding_model: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failures: list[str] = field(default_factory=list)
