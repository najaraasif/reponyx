import time
from pathlib import Path

from tests.unit.test_execution_service import FakeRunner

from reponyx.config import Settings
from reponyx.execution.service import ExecutionService
from reponyx.repair.model import DeterministicRepairModel
from reponyx.repair.models import ChangeType, ProposedChange
from reponyx.repair.operations_service import RepairOperationsService
from reponyx.repair.service import RepairService
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService


def test_repair_review_history_and_background_job(tmp_path: Path) -> None:
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
    repositories.register_for_testing("ops-repo", source)
    execution = ExecutionService(settings, repositories, FakeRunner())
    model = DeterministicRepairModel(
        {"change": [ProposedChange("module.py", ChangeType.MODIFIED, "value = 2\n")]}
    )
    repairs = RepairService(settings, repositories, execution, model)
    operations = RepairOperationsService(repairs)

    queued = operations.enqueue("ops-repo", "change")
    for _ in range(50):
        history = operations.history("ops-repo")
        if history:
            break
        time.sleep(0.02)

    assert queued["status"] == "queued"
    assert history
