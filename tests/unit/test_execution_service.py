from datetime import UTC, datetime
from pathlib import Path

from reponyx.config import Settings
from reponyx.execution.models import ExecutionRequest, ExecutionResult, ExecutionStatus
from reponyx.execution.service import ExecutionService
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService


class FakeRunner:
    def run(self, request: ExecutionRequest, canonical_workspace: Path) -> ExecutionResult:
        now = datetime.now(UTC)
        return ExecutionResult(
            request.execution_id,
            request.repository_id,
            request.command,
            ExecutionStatus.COMPLETED,
            0,
            "3 passed in 0.01s",
            "",
            10,
            False,
            False,
            False,
            "fake-container",
            now,
            now,
        )


def test_test_service_uses_fake_runner_and_persists_bounded_result(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    source = tmp_path / "source"
    source.mkdir()
    (source / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    repositories.register_for_testing("execution-repo", source)
    service = ExecutionService(settings, repositories, FakeRunner())

    result = service.run_tests("execution-repo", "pytest")

    assert result.status == ExecutionStatus.COMPLETED
    assert result.test_summary is not None
    assert result.test_summary.passed == 3
    assert service.get(result.execution_id) is not None
    assert service.get_evidence(result.execution_id) is not None
