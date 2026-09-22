"""Execution gateway and read-only test execution service."""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from reponyx.config import Settings
from reponyx.execution.database import ExecutionStore
from reponyx.execution.docker import DockerExecutionError, DockerRunner
from reponyx.execution.models import (
    EnvironmentPolicy,
    ExecutionEvidence,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ResourcePolicy,
)
from reponyx.execution.policy import bounded_resources
from reponyx.execution.tests import approved_test_command, parse_test_output
from reponyx.repositories.service import RepositoryService


class ExecutionService:
    def __init__(
        self,
        settings: Settings,
        repositories: RepositoryService,
        runner: DockerRunner | None = None,
        store: ExecutionStore | None = None,
    ) -> None:
        self.settings = settings
        self.repositories = repositories
        self.runner = runner or DockerRunner(
            settings.execution_root, settings.execution_image, settings.execution_network_disabled
        )
        self.store = store or ExecutionStore(repositories.store)
        self.results: dict[str, ExecutionResult] = {}
        self.evidence: dict[str, ExecutionEvidence] = {}

    def run_tests(
        self, repository_id: str, framework: str, timeout_seconds: float | None = None
    ) -> ExecutionResult:
        record = self.repositories.store.get(repository_id)
        if record is None:
            raise KeyError(repository_id)
        return self._run_tests_at_path(
            repository_id, Path(record.workspace_path), framework, timeout_seconds
        )

    def run_tests_at_path(
        self,
        repository_id: str,
        workspace: Path,
        framework: str,
        timeout_seconds: float | None = None,
    ) -> ExecutionResult:
        record = self.repositories.store.get(repository_id)
        if record is None:
            raise KeyError(repository_id)
        canonical = Path(record.workspace_path).resolve()
        candidate = workspace.resolve()
        if not candidate.is_dir() or canonical == candidate:
            raise ValueError("test workspace must be a distinct directory")
        return self._run_tests_at_path(repository_id, candidate, framework, timeout_seconds)

    def _run_tests_at_path(
        self,
        repository_id: str,
        workspace: Path,
        framework: str,
        timeout_seconds: float | None = None,
    ) -> ExecutionResult:
        approved = approved_test_command(framework)
        maximum = ResourcePolicy(
            self.settings.execution_max_timeout_seconds,
            self.settings.execution_memory_limit,
            self.settings.execution_cpu_limit,
            self.settings.execution_pids_limit,
            self.settings.execution_output_limit,
        )
        resource = bounded_resources(
            ResourcePolicy(
                timeout_seconds or self.settings.execution_default_timeout_seconds,
                self.settings.execution_memory_limit,
                self.settings.execution_cpu_limit,
                self.settings.execution_pids_limit,
                self.settings.execution_output_limit,
            ),
            maximum,
        )
        execution_id = uuid4().hex
        request = ExecutionRequest(
            execution_id,
            repository_id,
            approved.argv,
            "",
            resource.timeout_seconds,
            EnvironmentPolicy(()),
            resource,
        )
        try:
            result = self.runner.run(request, workspace)
        except (DockerExecutionError, OSError) as exc:
            now = datetime.now(UTC)
            result = ExecutionResult(
                execution_id,
                repository_id,
                approved.argv,
                ExecutionStatus.FAILED,
                None,
                "",
                "",
                0,
                False,
                False,
                False,
                None,
                now,
                now,
                error=str(exc),
            )
        summary = parse_test_output(
            approved.framework, result.stdout, result.stderr, result.duration_ms
        )
        result = ExecutionResult(**{**asdict(result), "test_summary": summary})
        self.results[execution_id] = result
        self.store.save(result)
        self.evidence[execution_id] = ExecutionEvidence(
            execution_id,
            repository_id,
            result.command,
            result.status,
            result.exit_code,
            summary,
            (result.stdout + "\n" + result.stderr)[-10_000:],
        )
        return result

    def get(self, execution_id: str) -> ExecutionResult | None:
        return self.results.get(execution_id) or self.store.get(execution_id)

    def get_evidence(self, execution_id: str) -> ExecutionEvidence | None:
        return self.evidence.get(execution_id)
