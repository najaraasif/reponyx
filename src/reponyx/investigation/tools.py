"""Read-only investigation tools with repository and workspace boundaries."""

from pathlib import Path

from reponyx.execution.models import ExecutionEvidence, ExecutionStatus
from reponyx.execution.service import ExecutionService
from reponyx.investigation.models import SourceInspection
from reponyx.repositories.database import RepositoryRecord
from reponyx.repositories.policy import RepositoryPolicyError, safe_relative_path
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.models import RetrievalFilters, RetrievalResult
from reponyx.retrieval.service import RetrievalService


class InvestigationToolError(ValueError):
    """Raised when a read-only investigation request is invalid."""


class InvestigationTools:
    def __init__(
        self,
        repositories: RepositoryService,
        retrieval: RetrievalService,
        max_source_bytes: int,
        execution: ExecutionService | None = None,
    ) -> None:
        self.repositories = repositories
        self.retrieval = retrieval
        self.max_source_bytes = max_source_bytes
        self.execution = execution

    def _record(self, repository_id: str) -> RepositoryRecord:
        record = self.repositories.store.get(repository_id)
        if record is None:
            raise InvestigationToolError("repository not found")
        return record

    def get_repository_metadata(self, repository_id: str) -> dict[str, object]:
        item = self.repositories.get(repository_id)
        if item is None:
            raise InvestigationToolError("repository not found")
        return item

    def get_repository_structure(self, repository_id: str) -> object:
        return self.repositories.analysis_section(repository_id, "directories")

    def search_code(
        self,
        repository_id: str,
        query: str,
        top_k: int = 8,
        language: str | None = None,
        file_path: str | None = None,
        symbol_type: str | None = None,
        rerank: bool = False,
    ) -> list[RetrievalResult]:
        filters = RetrievalFilters(language=language, file_path=file_path, symbol_type=symbol_type)
        return self.retrieval.search(repository_id, query, top_k, filters, rerank)

    def inspect_source(
        self, repository_id: str, file_path: str, start_line: int = 1, end_line: int | None = None
    ) -> SourceInspection:
        record = self._record(repository_id)
        try:
            relative = safe_relative_path(file_path)
        except RepositoryPolicyError as exc:
            raise InvestigationToolError(str(exc)) from exc
        if start_line < 1 or (end_line is not None and end_line < start_line):
            raise InvestigationToolError("invalid source line range")
        root = Path(record.workspace_path).resolve()
        target = (root / relative).resolve()
        if root not in target.parents or target.is_symlink() or not target.is_file():
            raise InvestigationToolError("source path is outside the repository workspace")
        if target.stat().st_size > self.max_source_bytes:
            raise InvestigationToolError("source file exceeds inspection limit")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        if start_line > len(lines):
            raise InvestigationToolError("source start line is outside the file")
        end = min(end_line or len(lines), len(lines))
        return SourceInspection(relative, start_line, end, "\n".join(lines[start_line - 1 : end]))

    def find_symbol(self, repository_id: str, symbol: str) -> list[dict[str, object]]:
        symbols = self.repositories.analysis_section(repository_id, "symbols")
        return [
            item
            for item in (symbols if isinstance(symbols, list) else [])
            if isinstance(item, dict) and item.get("name", "").lower() == symbol.lower()
        ]

    def find_references(self, repository_id: str, symbol: str) -> list[dict[str, object]]:
        analysis = self.repositories.store.analysis(repository_id)
        if analysis is None:
            raise InvestigationToolError("analysis not found")
        needle = symbol.lower()
        return [
            item
            for item in (
                analysis.get("imports", []) if isinstance(analysis.get("imports", []), list) else []
            )
            if isinstance(item, dict) and needle in str(item.get("target", "")).lower()
        ]

    def inspect_dependencies(
        self, repository_id: str, symbol: str | None = None
    ) -> list[dict[str, object]]:
        dependencies = self.repositories.analysis_section(repository_id, "dependencies")
        if symbol is None:
            return dependencies if isinstance(dependencies, list) else []
        needle = symbol.lower()
        return [
            item
            for item in (dependencies if isinstance(dependencies, list) else [])
            if isinstance(item, dict) and needle in str(item.get("target", "")).lower()
        ]

    def run_tests(
        self, repository_id: str, framework: str, timeout_seconds: float | None = None
    ) -> ExecutionEvidence:
        if self.execution is None:
            raise InvestigationToolError("execution is not configured")
        try:
            result = self.execution.run_tests(repository_id, framework, timeout_seconds)
        except KeyError as exc:
            raise InvestigationToolError("repository not found") from exc
        evidence = self.execution.get_evidence(result.execution_id)
        if evidence is None:
            raise InvestigationToolError("execution evidence unavailable")
        return ExecutionEvidence(
            execution_id=evidence.execution_id,
            repository_id=evidence.repository_id,
            command=evidence.command,
            status=ExecutionStatus(evidence.status.value),
            exit_code=evidence.exit_code,
            test_summary=evidence.test_summary,
            relevant_output=evidence.relevant_output,
        )
