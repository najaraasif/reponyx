from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponyx.config import Settings
from reponyx.execution.models import ExecutionRequest, ExecutionResult, ExecutionStatus
from reponyx.execution.service import ExecutionService
from reponyx.repair.model import DeterministicRepairModel
from reponyx.repair.models import ChangeType, ProposedChange, RepairStatus
from reponyx.repair.patching import PatchLimits, PatchService, PatchValidationError
from reponyx.repair.service import RepairService
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mixed_repo"
VARIANCE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "variance_repo"


class PassingRunner:
    def run(self, request: ExecutionRequest, canonical_workspace: Path) -> ExecutionResult:
        now = datetime.now(UTC)
        return ExecutionResult(
            request.execution_id,
            request.repository_id,
            request.command,
            ExecutionStatus.COMPLETED,
            0,
            "1 passed in 0.01s",
            "",
            10,
            False,
            False,
            False,
            "repair-fake",
            now,
            now,
        )


def make_service(
    tmp_path: Path, model: DeterministicRepairModel
) -> tuple[RepairService, RepositoryService]:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("repair-repo", FIXTURE)
    execution = ExecutionService(settings, repositories, PassingRunner())
    return RepairService(settings, repositories, execution, model), repositories


def test_successful_repair_is_ephemeral_and_preserves_canonical(tmp_path: Path) -> None:
    original = (FIXTURE / "app" / "auth.py").read_text()
    model = DeterministicRepairModel(
        {
            "fix reset": [
                ProposedChange(
                    "app/auth.py",
                    ChangeType.MODIFIED,
                    original.replace("return bool(email)", "return email.endswith('@example.com')"),
                )
            ]
        }
    )
    service, repositories = make_service(tmp_path, model)

    result = service.create("repair-repo", "fix reset")
    report = service.report(result["repair_id"])

    assert result["status"] == RepairStatus.COMPLETED.value
    assert report is not None
    assert report["verification_level"] == "targeted_tests_passed"
    assert "app/auth.py" in report["changed_files"]
    assert (FIXTURE / "app" / "auth.py").read_text() == original
    assert not list((tmp_path / "repairs").iterdir())
    assert repositories.store.get("repair-repo") is not None


@pytest.mark.parametrize(
    "path",
    ["../../secret.txt", "/etc/passwd", "C:\\Windows\\system.ini", "workspace/../../outside"],
)
def test_patch_paths_are_rejected(tmp_path: Path, path: str) -> None:
    workspace = tmp_path / "repair"
    workspace.mkdir()

    with pytest.raises(PatchValidationError):
        PatchService().validate(
            workspace,
            [ProposedChange(path, ChangeType.CREATED, "unsafe")],
        )


def test_patch_limits_reject_mass_change(tmp_path: Path) -> None:
    workspace = tmp_path / "repair"
    workspace.mkdir()
    patcher = PatchService(PatchLimits(max_files=1, max_lines=1, max_total_bytes=4))

    with pytest.raises(PatchValidationError):
        patcher.validate(
            workspace,
            [ProposedChange("new.py", ChangeType.CREATED, "one\ntwo\n")],
        )


def test_repair_service_retrieves_from_store_after_creation(tmp_path: Path) -> None:
    model = DeterministicRepairModel(
        {
            "fix reset": [
                ProposedChange(
                    "app/auth.py",
                    ChangeType.MODIFIED,
                    "fixed code",
                )
            ]
        }
    )
    service, _ = make_service(tmp_path, model)
    result = service.create("repair-repo", "fix reset")
    repair_id = result["repair_id"]

    repair = service.get(repair_id)
    assert repair is not None
    assert repair["repair_id"] == repair_id
    assert repair["repository_id"] == "repair-repo"


def test_repair_service_retrieves_report_from_store(tmp_path: Path) -> None:
    model = DeterministicRepairModel(
        {
            "fix reset": [
                ProposedChange(
                    "app/auth.py",
                    ChangeType.MODIFIED,
                    "fixed code",
                )
            ]
        }
    )
    service, _ = make_service(tmp_path, model)
    result = service.create("repair-repo", "fix reset")
    repair_id = result["repair_id"]

    report = service.report(repair_id)
    assert report is not None
    assert "issue" in report


def test_repair_creation_with_investigation_id(tmp_path: Path) -> None:
    model = DeterministicRepairModel(
        {
            "fix variance": [
                ProposedChange(
                    "src/statistics.py",
                    ChangeType.MODIFIED,
                    "fixed variance",
                )
            ]
        }
    )
    service, _ = make_service(tmp_path, model)
    result = service.create("repair-repo", "fix variance", investigation_id="inv-123")
    repair_id = result["repair_id"]

    repair = service.get(repair_id)
    assert repair is not None
    assert repair["repair_id"] == repair_id


def test_repair_store_persistence(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("repair-repo", FIXTURE)
    execution = ExecutionService(settings, repositories, PassingRunner())
    service = RepairService(settings, repositories, execution)

    model = DeterministicRepairModel(
        {
            "fix test": [
                ProposedChange(
                    "app/auth.py",
                    ChangeType.MODIFIED,
                    "fixed code",
                )
            ]
        }
    )
    service.graph_model = model
    result = service.create("repair-repo", "fix test")
    repair_id = result["repair_id"]

    new_service = RepairService(settings, repositories, execution)
    repair = new_service.get(repair_id)
    assert repair is not None
    assert repair["repair_id"] == repair_id


def test_failed_repair_exposes_error_instead_of_404(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("repair-repo", FIXTURE)
    execution = ExecutionService(settings, repositories, PassingRunner())
    service = RepairService(settings, repositories, execution)

    result = service.create("repair-repo", "nonexistent issue")
    repair_id = result["repair_id"]

    assert result["status"] == "failed"
    report = service.report(repair_id)
    assert report is not None
    assert report["status"] == "failed"


def test_successful_repair_persists_report(tmp_path: Path) -> None:
    original = (FIXTURE / "app" / "auth.py").read_text()
    model = DeterministicRepairModel(
        {
            "fix reset": [
                ProposedChange(
                    "app/auth.py",
                    ChangeType.MODIFIED,
                    original.replace("return bool(email)", "return email.endswith('@example.com')"),
                )
            ]
        }
    )
    service, _ = make_service(tmp_path, model)

    result = service.create("repair-repo", "fix reset")
    repair_id = result["repair_id"]

    assert result["status"] == RepairStatus.COMPLETED.value
    report = service.report(repair_id)
    assert report is not None
    assert report["status"] == "completed"
    assert report["verification_level"] == "targeted_tests_passed"


def test_repair_report_endpoint_returns_200(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from reponyx.main import create_app

    original = (FIXTURE / "app" / "auth.py").read_text()
    model = DeterministicRepairModel(
        {
            "fix reset": [
                ProposedChange(
                    "app/auth.py",
                    ChangeType.MODIFIED,
                    original.replace("return bool(email)", "return email.endswith('@example.com')"),
                )
            ]
        }
    )
    service, repositories = make_service(tmp_path, model)
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    app = create_app(
        settings=settings,
        repository_service=repositories,
        repair_service=service,
    )
    client = TestClient(app)

    result = service.create("repair-repo", "fix reset")
    repair_id = result["repair_id"]

    response = client.get(f"/repairs/{repair_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_failed_repair_report_endpoint_returns_200(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from reponyx.main import create_app

    service, repositories = make_service(tmp_path, DeterministicRepairModel())
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    app = create_app(
        settings=settings,
        repository_service=repositories,
        repair_service=service,
    )
    client = TestClient(app)

    result = service.create("repair-repo", "nonexistent issue")
    repair_id = result["repair_id"]

    response = client.get(f"/repairs/{repair_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"


def test_repair_without_final_report_returns_synthetic_failure(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path, DeterministicRepairModel())
    result = service.create("repair-repo", "nonexistent issue")
    repair_id = result["repair_id"]

    state = service.active.get(repair_id) or service.store.get(repair_id)
    assert state is not None
    state["final_report"] = None

    report = service.report(repair_id)
    assert report is not None
    assert report["status"] == "failed"
    assert report["repair_id"] == repair_id


def test_repair_without_final_report_endpoint_returns_200(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from reponyx.main import create_app

    service, repositories = make_service(tmp_path, DeterministicRepairModel())
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    app = create_app(
        settings=settings,
        repository_service=repositories,
        repair_service=service,
    )
    client = TestClient(app)

    result = service.create("repair-repo", "nonexistent issue")
    repair_id = result["repair_id"]

    response = client.get(f"/repairs/{repair_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "failed"


def _make_variance_service(
    tmp_path: Path, model: DeterministicRepairModel
) -> tuple[RepairService, RepositoryService]:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
        embedding_dimensions=16,
        repair_max_iterations=2,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("variance-repo", VARIANCE_FIXTURE)
    execution = ExecutionService(settings, repositories, PassingRunner())
    return RepairService(settings, repositories, execution, model), repositories


def _make_variance_model() -> DeterministicRepairModel:
    buggy = (VARIANCE_FIXTURE / "src" / "statistics.py").read_text()
    fixed = buggy.replace("return float(np.var(array, ddof=1))", "return float(np.var(array))")
    model = DeterministicRepairModel()
    model.add_keyword_rule(
        keywords=["variance", "population"],
        changes=[
            ProposedChange(
                "src/statistics.py",
                ChangeType.MODIFIED,
                fixed,
            )
        ],
    )
    return model


def test_variance_issue_produces_repair_proposal(tmp_path: Path) -> None:
    model = _make_variance_model()
    service, _ = _make_variance_service(tmp_path, model)
    issue = (
        "Population variance returns the wrong value. "
        "The variance function returns 2.5 for [1, 2, 3, 4, 5], "
        "but the expected population variance is 2.0."
    )
    result = service.create("variance-repo", issue)
    assert result["status"] == RepairStatus.COMPLETED.value


def test_variance_proposal_targets_statistics_py(tmp_path: Path) -> None:
    model = _make_variance_model()
    service, _ = _make_variance_service(tmp_path, model)
    issue = (
        "Population variance returns the wrong value. "
        "The variance function returns 2.5 for [1, 2, 3, 4, 5], "
        "but the expected population variance is 2.0."
    )
    result = service.create("variance-repo", issue)
    repair_id = result["repair_id"]
    report = service.report(repair_id)
    assert report is not None
    assert "src/statistics.py" in report["changed_files"]


def test_variance_proposal_is_minimal(tmp_path: Path) -> None:
    model = _make_variance_model()
    service, _ = _make_variance_service(tmp_path, model)
    issue = (
        "Population variance returns the wrong value. "
        "The variance function returns 2.5 for [1, 2, 3, 4, 5], "
        "but the expected population variance is 2.0."
    )
    result = service.create("variance-repo", issue)
    repair_id = result["repair_id"]
    report = service.report(repair_id)
    assert report is not None
    assert len(report["changed_files"]) == 1


def test_variance_successful_patch_application(tmp_path: Path) -> None:
    model = _make_variance_model()
    service, _ = _make_variance_service(tmp_path, model)
    issue = (
        "Population variance returns the wrong value. "
        "The variance function returns 2.5 for [1, 2, 3, 4, 5], "
        "but the expected population variance is 2.0."
    )
    result = service.create("variance-repo", issue)
    assert result["status"] == RepairStatus.COMPLETED.value
    repair_id = result["repair_id"]
    diff = service.diff(repair_id)
    assert diff is not None
    assert "ddof=1" in diff
    assert "ddof=0" not in diff or "np.var(array)" in diff


def test_variance_relevant_tests_pass(tmp_path: Path) -> None:
    model = _make_variance_model()
    service, _ = _make_variance_service(tmp_path, model)
    issue = (
        "Population variance returns the wrong value. "
        "The variance function returns 2.5 for [1, 2, 3, 4, 5], "
        "but the expected population variance is 2.0."
    )
    result = service.create("variance-repo", issue)
    assert result["status"] == RepairStatus.COMPLETED.value
    repair_id = result["repair_id"]
    report = service.report(repair_id)
    assert report is not None
    assert report["status"] == "completed"


def test_variance_repair_report_contains_repair_result(tmp_path: Path) -> None:
    model = _make_variance_model()
    service, _ = _make_variance_service(tmp_path, model)
    issue = (
        "Population variance returns the wrong value. "
        "The variance function returns 2.5 for [1, 2, 3, 4, 5], "
        "but the expected population variance is 2.0."
    )
    result = service.create("variance-repo", issue)
    assert result["status"] == RepairStatus.COMPLETED.value
    repair_id = result["repair_id"]
    report = service.report(repair_id)
    assert report is not None
    assert report["status"] == "completed"
    assert report["verification_level"] == "targeted_tests_passed"
    assert report["iterations"] >= 1
    assert len(report["changed_files"]) > 0
