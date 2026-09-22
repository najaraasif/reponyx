"""Run the deterministic Phase 5 repair benchmark."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from reponyx.config import Settings
from reponyx.execution.models import ExecutionRequest, ExecutionResult, ExecutionStatus
from reponyx.execution.service import ExecutionService
from reponyx.repair.model import DeterministicRepairModel
from reponyx.repair.models import ChangeType, ProposedChange
from reponyx.repair.service import RepairService
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService


class PassingRunner:
    def run(self, request: ExecutionRequest, workspace: Path) -> ExecutionResult:
        now = datetime.now(UTC)
        return ExecutionResult(
            request.execution_id,
            request.repository_id,
            request.command,
            ExecutionStatus.COMPLETED,
            0,
            "1 passed",
            "",
            1,
            False,
            False,
            False,
            "benchmark",
            now,
            now,
        )


def main() -> None:
    root = Path(__file__).parents[1]
    work = root / "evaluation" / "repair-benchmark"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    settings = Settings(
        _env_file=None,
        workspace_root=str(work / "workspaces"),
        database_url=f"sqlite:///{work / 'benchmark.db'}",
        execution_root=str(work / "executions"),
        repair_workspace_root=str(work / "repairs"),
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    source = work / "source"
    source.mkdir()
    (source / "module.py").write_text("value = 1\n")
    repositories.register_for_testing("repair-benchmark", source)
    model = DeterministicRepairModel(
        {"change value": [ProposedChange("module.py", ChangeType.MODIFIED, "value = 2\n")]}
    )
    service = RepairService(
        settings, repositories, ExecutionService(settings, repositories, PassingRunner()), model
    )
    result = service.create("repair-benchmark", "change value")
    report = service.report(result["repair_id"])
    measured = {
        "cases": 1,
        "patch_application_success_rate": 1.0 if report and report["files_changed"] else 0.0,
        "repair_success_rate": 1.0 if result["status"] == "completed" else 0.0,
        "iterations": report["iterations"] if report else None,
    }
    output = root / "evaluation" / "repair-results.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(measured, indent=2), encoding="utf-8")
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
