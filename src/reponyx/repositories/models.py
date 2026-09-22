"""Domain models for repository analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SymbolType(StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    EXPORT = "export"
    INTERFACE = "interface"
    TYPE = "type"
    DECORATOR = "decorator"
    CONSTANT = "constant"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class Symbol:
    repository_id: str
    file_path: str
    name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    language: str
    parent_symbol: str | None = None
    signature: str | None = None


@dataclass(frozen=True, slots=True)
class ImportReference:
    file_path: str
    target: str
    name: str | None
    start_line: int
    end_line: int
    language: str
    is_export: bool = False


@dataclass(frozen=True, slots=True)
class Dependency:
    source_file: str
    target: str
    kind: str


@dataclass(frozen=True, slots=True)
class CodeChunk:
    file_path: str
    symbol: str | None
    language: str
    start_line: int
    end_line: int
    content: str
    parent_symbol: str | None = None
    relevant_imports: tuple[str, ...] = ()


@dataclass(slots=True)
class RepositoryAnalysis:
    repository_id: str
    files: list[str] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportReference] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    chunks: list[CodeChunk] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    test_locations: list[str] = field(default_factory=list)
    configuration_files: list[str] = field(default_factory=list)
    parse_failures: list[str] = field(default_factory=list)
    analyzed_at: datetime | None = None
