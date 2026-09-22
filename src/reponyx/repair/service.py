"""Application service for isolated autonomous repair."""

from dataclasses import asdict, is_dataclass
from typing import Any, cast

from reponyx.config import Settings
from reponyx.execution.service import ExecutionService
from reponyx.repair.context import RepairContextBuilder
from reponyx.repair.database import RepairStore
from reponyx.repair.graph import RepairGraph, initial_repair_state
from reponyx.repair.llm import build_llm_repair_model
from reponyx.repair.model import (
    RepairModel,
    build_default_deterministic_model,
)
from reponyx.repair.patching import PatchService
from reponyx.repair.workspace import RepairWorkspaceService
from reponyx.repositories.service import RepositoryService


class RepairService:
    def __init__(
        self,
        settings: Settings,
        repositories: RepositoryService,
        execution: ExecutionService,
        model: RepairModel | None = None,
        store: RepairStore | None = None,
    ) -> None:
        self.repositories = repositories
        self.workspaces = RepairWorkspaceService(repositories, settings.repair_workspace_root)
        self.store = store or RepairStore(repositories.store)
        self.max_iterations = settings.repair_max_iterations
        self.graph_model = model or (
            build_default_deterministic_model()
            if settings.llm_provider == "mock"
            else build_llm_repair_model(
                settings, RepairContextBuilder(settings.llm_max_context_characters)
            )
        )
        self.execution = execution
        self.active: dict[str, dict[str, object]] = {}

    def create(
        self, repository_id: str, issue: str, investigation_id: str | None = None
    ) -> dict[str, str]:
        workspace = self.workspaces.create(repository_id, investigation_id)
        state = initial_repair_state(
            workspace.repair_id, repository_id, issue, workspace.workspace_path, investigation_id
        )
        self.active[workspace.repair_id] = cast(dict[str, object], state)
        result = RepairGraph(
            self.workspaces, PatchService(), self.execution, self.graph_model, self.max_iterations
        ).run(state)
        self.active[workspace.repair_id] = cast(dict[str, object], result)
        self.store.save(cast(dict[str, object], result))
        self.workspaces.cleanup(workspace.repair_id)
        return {
            "repair_id": workspace.repair_id,
            "status": str(result.get("repair_status", "failed")),
        }

    def get(self, repair_id: str) -> dict[str, object] | None:
        state = self.active.get(repair_id)
        if state is None:
            state = self.store.get(repair_id)
        if state is None:
            return None
        return {
            "repair_id": repair_id,
            "repository_id": state.get("repository_id", ""),
            "status": state.get("repair_status", "unknown"),
            "iteration_count": state.get("iteration_count", 0),
            "changed_files": state.get("changed_files", []),
        }

    def _serialize_report(self, raw: dict[str, object]) -> dict[str, object]:
        status = raw.get("final_status", raw.get("status", "failed"))
        if hasattr(status, "value"):
            status = status.value
        files_changed = raw.get("files_changed", raw.get("changed_files", []))
        if not isinstance(files_changed, list):
            if files_changed and isinstance(files_changed, (list, tuple)):
                files_changed = list(files_changed)
            else:
                files_changed = []
        tests_run = raw.get("tests_run", [])
        tests_passed = raw.get("tests_passed", [])
        tests_failed = raw.get("tests_failed", [])
        passed_count = len(tests_passed) if isinstance(tests_passed, (list, tuple)) else 0
        failed_count = len(tests_failed) if isinstance(tests_failed, (list, tuple)) else 0
        test_results: list[dict[str, object]] = []
        if tests_run:
            test_results.append(
                {
                    "framework": "default",
                    "passed": passed_count,
                    "failed": failed_count,
                    "skipped": 0,
                    "duration": 0,
                    "output": "",
                }
            )
        failure_analyses = raw.get("failure_analyses", [])
        failure_analysis = None
        if isinstance(failure_analyses, list) and failure_analyses:
            fa = failure_analyses[0]
            if isinstance(fa, dict):
                failure_analysis = fa
        final_diff = raw.get("final_diff", "")
        summary = raw.get("summary", "")
        return {
            "repair_id": raw.get("repair_id", ""),
            "repository_id": raw.get("repository_id", ""),
            "status": status,
            "issue": raw.get("issue", ""),
            "iterations": raw.get("iterations", 0),
            "root_cause": raw.get("root_cause", raw.get("root_cause_analysis")),
            "repair_plan": raw.get("repair_plan"),
            "changed_files": files_changed,
            "test_results": test_results,
            "failure_analysis": failure_analysis,
            "repair_decision": raw.get("repair_decision"),
            "final_report": str(summary) if summary else "",
            "symbols_changed": raw.get("symbols_changed", []),
            "patch_description": raw.get("patch_description"),
            "verification_level": raw.get("verification_level", "unverified"),
            "final_diff": final_diff,
        }

    def report(self, repair_id: str) -> dict[str, object] | None:
        state = self.active.get(repair_id)
        if state is None:
            state = self.store.get(repair_id)
        if state is None:
            return None
        report = state.get("final_report")
        if report is not None:
            if isinstance(report, dict):
                return self._serialize_report(report)
            if is_dataclass(report):
                return self._serialize_report(asdict(cast(Any, report)))
        raw_errors = state.get("errors", [])
        errors = [str(e) for e in raw_errors] if isinstance(raw_errors, list) else []
        return self._serialize_report(
            {
                "repair_id": repair_id,
                "repository_id": state.get("repository_id", ""),
                "issue": state.get("issue", ""),
                "summary": (
                    f"Repair failed. {'; '.join(errors) if errors else 'No details available.'}"
                ),
                "root_cause": None,
                "files_changed": state.get("changed_files", []),
                "symbols_changed": (),
                "patch_description": None,
                "iterations": state.get("iteration_count", 0),
                "tests_run": (),
                "tests_passed": (),
                "tests_failed": (),
                "final_status": state.get("repair_status", "failed"),
                "verification_level": "unverified",
                "root_cause_analysis": None,
                "repair_plan": None,
                "failure_analyses": (),
                "repair_decision": None,
                "retrieved_sources": (),
                "llm_calls": 0,
                "model_provider": "mock",
                "model_name": "deterministic",
                "confidence": "low",
                "limitations": (
                    "Canonical repository was never modified.",
                    "No commits, pushes, or pull requests were created.",
                ),
                "final_diff": "",
            }
        )

    def diff(self, repair_id: str) -> str | None:
        state = self.active.get(repair_id)
        if state is None:
            state = self.store.get(repair_id)
        if state is None:
            return None
        patch = state.get("current_patch")
        if patch is not None:
            if hasattr(patch, "diff"):
                return patch.diff
            if isinstance(patch, dict) and patch.get("diff"):
                return str(patch["diff"])
        report = state.get("final_report")
        if report is not None:
            if hasattr(report, "final_diff"):
                return report.final_diff
            if isinstance(report, dict):
                return str(report.get("final_diff", ""))
        return None

    def cancel(self, repair_id: str) -> dict[str, str]:
        state = self.active.get(repair_id)
        if state is None:
            raise KeyError(repair_id)
        state["cancelled"] = True
        state["repair_status"] = "cancelled"
        self.workspaces.cleanup(repair_id)
        self.store.save(state)
        return {"repair_id": repair_id, "status": "cancelled"}
