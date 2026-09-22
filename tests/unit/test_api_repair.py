from pathlib import Path

from fastapi.testclient import TestClient
from tests.unit.test_repair import PassingRunner

from reponyx.config import Settings
from reponyx.execution.service import ExecutionService
from reponyx.main import create_app
from reponyx.repair.model import DeterministicRepairModel
from reponyx.repair.models import ChangeType, ProposedChange
from reponyx.repair.service import RepairService
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService


def test_repair_api_returns_report_and_diff(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
        repair_workspace_root=str(tmp_path / "repairs"),
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_text("value = 1\n")
    repositories.register_for_testing("api-repair", source)
    execution = ExecutionService(settings, repositories, PassingRunner())
    model = DeterministicRepairModel(
        {"change value": [ProposedChange("module.py", ChangeType.MODIFIED, "value = 2\n")]}
    )
    repairs = RepairService(settings, repositories, execution, model)
    client = TestClient(
        create_app(settings, repositories, execution_service=execution, repair_service=repairs)
    )

    created = client.post("/repositories/api-repair/repairs", json={"issue": "change value"})
    repair_id = created.json()["repair_id"]
    report = client.get(f"/repairs/{repair_id}/report")
    diff = client.get(f"/repairs/{repair_id}/diff")

    assert created.status_code == 200
    assert report.status_code == 200
    assert diff.status_code == 200
    assert "module.py" in diff.json()["diff"]
