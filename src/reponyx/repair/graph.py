"""Bounded LangGraph repair workflow operating only on ephemeral workspaces."""

import logging
from pathlib import Path
from typing import Any, cast

from langgraph.graph import END, StateGraph

from reponyx.execution.models import ExecutionStatus
from reponyx.execution.service import ExecutionService
from reponyx.repair.llm_models import (
    FailureAnalysis,
    FailureType,
    RepairDecision,
    RootCauseAnalysis,
)
from reponyx.repair.model import RepairModel
from reponyx.repair.models import (
    PatchAttempt,
    RepairReport,
    RepairState,
    RepairStatus,
    VerificationLevel,
)
from reponyx.repair.patching import PatchService, PatchValidationError
from reponyx.repair.planner import CrossFilePlanner
from reponyx.repair.workspace import RepairWorkspaceService

logger = logging.getLogger(__name__)


class RepairGraph:
    def __init__(
        self,
        workspaces: RepairWorkspaceService,
        patcher: PatchService,
        execution: ExecutionService,
        model: RepairModel,
        max_iterations: int = 5,
        planner: CrossFilePlanner | None = None,
    ) -> None:
        self.workspaces = workspaces
        self.patcher = patcher
        self.execution = execution
        self.model = model
        self.max_iterations = max_iterations
        self.planner = planner or CrossFilePlanner()
        self.workflow = self._build()

    def _build(self) -> Any:
        graph = StateGraph(RepairState)
        graph.add_node("create_repair_plan", self.create_repair_plan)
        graph.add_node("generate_patch", self.generate_patch)
        graph.add_node("validate_patch", self.validate_patch)
        graph.add_node("apply_patch", self.apply_patch)
        graph.add_node("select_tests", self.select_tests)
        graph.add_node("run_tests", self.run_tests)
        graph.add_node("analyze_test_results", self.analyze_test_results)
        graph.add_node("finalize_repair", self.finalize_repair)
        graph.set_entry_point("create_repair_plan")
        graph.add_edge("create_repair_plan", "generate_patch")
        graph.add_edge("generate_patch", "validate_patch")
        graph.add_conditional_edges(
            "validate_patch",
            self._after_validation,
            {"apply_patch": "apply_patch", "finalize_repair": "finalize_repair"},
        )
        graph.add_edge("apply_patch", "select_tests")
        graph.add_edge("select_tests", "run_tests")
        graph.add_edge("run_tests", "analyze_test_results")
        graph.add_conditional_edges(
            "analyze_test_results",
            self._after_tests,
            {"generate_patch": "generate_patch", "finalize_repair": "finalize_repair"},
        )
        graph.add_edge("finalize_repair", END)
        return graph.compile()

    def run(self, state: RepairState) -> RepairState:
        try:
            result = self.workflow.invoke(
                state, config={"recursion_limit": self.max_iterations * 5 + 8}
            )
            return cast(RepairState, result)
        except Exception as exc:
            state["repair_status"] = RepairStatus.FAILED
            state.setdefault("errors", []).append(str(exc))
            finalized = self.finalize_repair(state)
            state["final_report"] = cast(RepairReport | None, finalized.get("final_report"))
            return state

    def create_repair_plan(self, state: RepairState) -> dict[str, object]:
        workspace_path = Path(self.workspaces.path(state["repair_id"]))
        affected = self.planner.plan(
            workspace_path,
            primary_file=state.get("primary_file", ""),
            issue=state["issue"],
            evidence=state.get("evidence"),
        )
        affected_paths = [a.file_path for a in affected]
        affected_reasons = {a.file_path: a.reason for a in affected}
        root_cause = RootCauseAnalysis(
            observed_behavior=state["issue"],
            expected_behavior="The requested issue behavior should work without regressions.",
            likely_root_cause="Requires evidence-backed repair analysis.",
            affected_files=tuple(affected_paths),
            affected_symbols=(),
            dependencies=(),
            supporting_evidence=tuple(state.get("evidence", [])),
            alternative_hypotheses=(),
            selected_reason="The repair remains constrained to supplied evidence.",
        )
        return {
            "repair_status": RepairStatus.INVESTIGATING,
            "current_step": "generate_patch",
            "repair_plan": {
                "summary": "Generate and validate a minimal evidence-backed patch.",
                "test_strategy": [state.get("targeted_framework", "pytest")],
                "affected_files": affected_paths,
                "affected_reasons": affected_reasons,
            },
            "root_cause_analysis": root_cause,
        }

    def generate_patch(self, state: RepairState) -> dict[str, object]:
        if state.get("cancelled") or state.get("iteration_count", 0) >= self.max_iterations:
            return {
                "repair_status": RepairStatus.FAILED,
                "errors": ["repair iteration limit reached"],
            }
        changes, description, reason, evidence = self.model.propose(
            state["issue"], state.get("evidence", []), state
        )
        return {
            "proposed_changes": changes,
            "patch_description": description,
            "patch_reason": reason,
            "evidence": evidence,
            "repair_status": RepairStatus.PATCHING,
        }

    def validate_patch(self, state: RepairState) -> dict[str, object]:
        try:
            self.patcher.validate(
                self.workspaces.path(state["repair_id"]), state.get("proposed_changes", [])
            )
            return {"patch_validation_error": None}
        except PatchValidationError as exc:
            return {"patch_validation_error": str(exc), "repair_status": RepairStatus.FAILED}

    def _after_validation(self, state: RepairState) -> str:
        return "apply_patch" if not state.get("patch_validation_error") else "finalize_repair"

    def apply_patch(self, state: RepairState) -> dict[str, object]:
        try:
            patch = self.patcher.apply(
                state["repair_id"],
                self.workspaces.path(state["repair_id"]),
                state["proposed_changes"],
                state.get("patch_description", ""),
                state.get("patch_reason", ""),
                state.get("evidence", []),
            )
            new_files = [item.file_path for item in patch.files_changed]
            previous = state.get("changed_files", [])
            accumulated = list(dict.fromkeys(previous + new_files))
            return {
                "current_patch": patch,
                "repair_status": RepairStatus.TESTING,
                "changed_files": accumulated,
                "changed_lines": patch.diff.count("\n"),
            }
        except PatchValidationError as exc:
            return {"patch_validation_error": str(exc), "repair_status": RepairStatus.FAILED}

    def select_tests(self, state: RepairState) -> dict[str, object]:
        return {"targeted_framework": state.get("targeted_framework", "pytest")}

    def run_tests(self, state: RepairState) -> dict[str, object]:
        result = self.execution.run_tests_at_path(
            state["repository_id"],
            self.workspaces.path(state["repair_id"]),
            state.get("targeted_framework", "pytest"),
        )
        return {
            "test_executions": [*state.get("test_executions", []), result],
            "test_results": [*state.get("test_results", []), result.status.value],
        }

    def analyze_test_results(self, state: RepairState) -> dict[str, object]:
        result = state["test_executions"][-1]
        failure_data = self.analyze_failures(state)
        decision_data = self.decide_repair(state)
        iteration = state.get("iteration_count", 0) + 1
        attempt = PatchAttempt(
            iteration,
            state.get("current_patch"),
            state.get("patch_validation_error"),
            result.execution_id,
            result,
            result.error,
        )
        history = [*state.get("patch_history", []), attempt]
        if result.status == ExecutionStatus.COMPLETED and result.exit_code == 0:
            return {
                "patch_history": history,
                "iteration_count": iteration,
                "repair_status": RepairStatus.COMPLETED,
                "verification_level": VerificationLevel.TARGETED_TESTS_PASSED,
                **failure_data,
                **decision_data,
            }
        if iteration >= self.max_iterations or state.get("cancelled"):
            return {
                "patch_history": history,
                "iteration_count": iteration,
                "repair_status": RepairStatus.FAILED,
                **failure_data,
                **decision_data,
            }
        return {
            "patch_history": history,
            "iteration_count": iteration,
            "repair_status": RepairStatus.PATCHING,
            "errors": ["targeted tests did not pass"],
            **failure_data,
            **decision_data,
        }

    def analyze_failures(self, state: RepairState) -> dict[str, object]:
        result = state["test_executions"][-1]
        failure_type = FailureType.UNKNOWN
        if result.timed_out:
            failure_type = FailureType.TIMEOUT
        elif result.resource_limited:
            failure_type = FailureType.RESOURCE_LIMIT
        elif result.exit_code not in {0, None}:
            failure_type = FailureType.ASSERTION_FAILURE
        analysis = FailureAnalysis(
            failure_type,
            result.error or "Test execution returned a non-zero result.",
            tuple(state.get("changed_files", [])),
            (),
            result.exit_code not in {0, None},
            "revise patch" if result.exit_code not in {0, None} else "finalize",
            tuple(state.get("evidence", [])),
        )
        return {"failure_analyses": [analysis]}

    def decide_repair(self, state: RepairState) -> dict[str, object]:
        result = state["test_executions"][-1]
        decision = (
            RepairDecision.FINALIZE_SUCCESS
            if result.exit_code == 0
            else RepairDecision.CONTINUE_REPAIR
            if state.get("iteration_count", 0) < self.max_iterations
            else RepairDecision.FINALIZE_FAILURE
        )
        return {"repair_decision": decision.value}

    def _after_tests(self, state: RepairState) -> str:
        return (
            "finalize_repair"
            if state.get("repair_status")
            in {RepairStatus.COMPLETED, RepairStatus.FAILED, RepairStatus.CANCELLED}
            else "generate_patch"
        )

    def finalize_repair(self, state: RepairState) -> dict[str, object]:
        status = state.get("repair_status", RepairStatus.FAILED)
        patch = state.get("current_patch")
        report = RepairReport(
            repair_id=state["repair_id"],
            repository_id=state["repository_id"],
            issue=state["issue"],
            summary="Controlled repair completed in an ephemeral workspace.",
            root_cause=state.get("root_cause"),
            files_changed=tuple(state.get("changed_files", [])),
            symbols_changed=(),
            patch_description=patch.description if patch else None,
            iterations=state.get("iteration_count", 0),
            tests_run=tuple(result.command[0] for result in state.get("test_executions", [])),
            tests_passed=tuple(
                result.execution_id
                for result in state.get("test_executions", [])
                if result.exit_code == 0
            ),
            tests_failed=tuple(
                result.execution_id
                for result in state.get("test_executions", [])
                if result.exit_code not in {0, None}
            ),
            final_status=status,
            verification_level=state.get("verification_level", VerificationLevel.UNVERIFIED),
            root_cause_analysis=state.get("root_cause_analysis"),
            repair_plan=state.get("repair_plan"),
            failure_analyses=cast(list[object], state.get("failure_analyses", [])),
            repair_decision=cast(str | None, state.get("repair_decision")),
            retrieved_sources=cast(list[object], state.get("retrieved_sources", [])),
            llm_calls=cast(int, state.get("llm_calls", 0)),
            model_provider=cast(str, state.get("model_provider", "mock")),
            model_name=cast(str, state.get("model_name", "deterministic")),
            confidence="medium" if patch else "low",
            limitations=(
                "Canonical repository was never modified.",
                "No commits, pushes, or pull requests were created.",
            ),
            final_diff=patch.diff if patch else "",
        )
        return {"final_report": report, "repair_status": status}


def initial_repair_state(
    repair_id: str,
    repository_id: str,
    issue: str,
    workspace_path: str,
    investigation_id: str | None = None,
    primary_file: str = "",
) -> RepairState:
    return RepairState(
        repair_id=repair_id,
        repository_id=repository_id,
        issue=issue,
        investigation_id=investigation_id,
        workspace_path=workspace_path,
        current_patch=None,
        patch_history=[],
        test_executions=[],
        test_results=[],
        iteration_count=0,
        changed_files=[],
        changed_lines=0,
        repair_status=RepairStatus.CREATED,
        final_diff="",
        root_cause=None,
        evidence=[],
        targeted_framework="pytest",
        broad_framework=None,
        final_report=None,
        errors=[],
        cancelled=False,
        primary_file=primary_file,
        repair_plan={},
        root_cause_analysis=None,
        failure_analyses=[],
        repair_decision="",
        retrieved_sources=[],
        llm_calls=0,
        model_provider="mock",
        model_name="deterministic",
    )
