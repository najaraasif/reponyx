"""Explicit bounded LangGraph investigation workflow."""

import logging
import time
from typing import Any, cast
from uuid import uuid4

from langgraph.graph import END, StateGraph

from reponyx.investigation.model import InvestigationModel
from reponyx.investigation.models import (
    Confidence,
    Evidence,
    InvestigationReport,
    InvestigationState,
    InvestigationStatus,
    VerificationStatus,
)
from reponyx.investigation.prompts import PROMPT_VERSION
from reponyx.investigation.ranker import classify_evidence
from reponyx.investigation.tools import InvestigationToolError, InvestigationTools

logger = logging.getLogger(__name__)


class InvestigationGraph:
    def __init__(
        self, tools: InvestigationTools, model: InvestigationModel, max_iterations: int = 3
    ) -> None:
        self.tools = tools
        self.model = model
        self.max_iterations = max_iterations
        self.workflow = self._build()

    def _event(self, state: InvestigationState, node: str, status: str) -> None:
        logger.info(
            "investigation_event",
            extra={
                "investigation_id": state["investigation_id"],
                "repository_id": state["repository_id"],
                "node": node,
                "result_status": status,
                "prompt_version": PROMPT_VERSION,
            },
        )

    def _build(self) -> Any:
        graph = StateGraph(InvestigationState)
        graph.add_node("create_plan", self.create_plan)
        graph.add_node("retrieve_context", self.retrieve_context)
        graph.add_node("inspect_sources", self.inspect_sources)
        graph.add_node("inspect_dependencies", self.inspect_dependencies)
        graph.add_node("collect_evidence", self.collect_evidence)
        graph.add_node("generate_hypotheses", self.generate_hypotheses)
        graph.add_node("verify_hypotheses", self.verify_hypotheses)
        graph.add_node("build_report", self.build_report)
        graph.set_entry_point("create_plan")
        graph.add_edge("create_plan", "retrieve_context")
        graph.add_edge("retrieve_context", "inspect_sources")
        graph.add_edge("inspect_sources", "inspect_dependencies")
        graph.add_edge("inspect_dependencies", "collect_evidence")
        graph.add_edge("collect_evidence", "generate_hypotheses")
        graph.add_edge("generate_hypotheses", "verify_hypotheses")
        graph.add_edge("verify_hypotheses", "build_report")
        graph.add_edge("build_report", END)
        return graph.compile()

    def run(self, state: InvestigationState) -> InvestigationState:
        try:
            result = self.workflow.invoke(
                state, config={"recursion_limit": self.max_iterations * 4 + 4}
            )
            return cast(InvestigationState, result)
        except Exception as exc:
            state["status"] = InvestigationStatus.FAILED
            state.setdefault("errors", []).append(str(exc))
            self._event(state, "workflow", "failed")
            return state

    def create_plan(self, state: InvestigationState) -> dict[str, object]:
        started = time.perf_counter()
        metadata = self.tools.get_repository_metadata(state["repository_id"])
        analysis = self.tools.repositories.store.analysis(state["repository_id"]) or {}
        plan, queries = self.model.plan(
            state["issue"],
            {
                "metadata": metadata,
                "analysis": {
                    key: analysis.get(key, [])
                    for key in ("languages", "files", "symbols", "dependencies", "test_locations")
                },
            },
        )
        self._event(state, "create_plan", "completed")
        logger.debug("plan_duration_ms=%s", round((time.perf_counter() - started) * 1000, 2))
        return {
            "investigation_plan": plan,
            "search_queries": queries,
            "current_step": "retrieve_context",
            "status": InvestigationStatus.RUNNING,
        }

    def retrieve_context(self, state: InvestigationState) -> dict[str, object]:
        results = []
        for query in state.get("search_queries", [])[:8]:
            results.extend(
                self.tools.search_code(state["repository_id"], query, top_k=5, rerank=True)
            )
        unique = {result.chunk_id: result for result in results}
        self._event(state, "retrieve_context", "completed")
        return {"retrieval_results": list(unique.values()), "current_step": "inspect_sources"}

    def inspect_sources(self, state: InvestigationState) -> dict[str, object]:
        inspected = []
        for result in state.get("retrieval_results", [])[:8]:
            try:
                inspected.append(
                    self.tools.inspect_source(
                        state["repository_id"], result.file_path, result.start_line, result.end_line
                    )
                )
            except InvestigationToolError as exc:
                state.setdefault("errors", []).append(str(exc))
        self._event(state, "inspect_sources", "completed")
        return {"inspected_sources": inspected, "current_step": "inspect_dependencies"}

    def inspect_dependencies(self, state: InvestigationState) -> dict[str, object]:
        dependencies: list[str] = []
        for result in state.get("retrieval_results", [])[:8]:
            for item in self.tools.inspect_dependencies(state["repository_id"], result.symbol_name):
                if isinstance(item, dict):
                    dependencies.append(f"{item.get('source_file')} -> {item.get('target')}")
        self._event(state, "inspect_dependencies", "completed")
        return {"dependencies": sorted(set(dependencies)), "current_step": "collect_evidence"}

    def collect_evidence(self, state: InvestigationState) -> dict[str, object]:
        evidence: list[Evidence] = []
        for result in state.get("retrieval_results", []):
            evidence.append(
                Evidence(
                    result.chunk_id,
                    "retrieval_result",
                    result.file_path,
                    result.symbol_name,
                    result.start_line,
                    result.end_line,
                    "Retrieved source chunk matched the investigation query.",
                    result.chunk_id,
                )
            )
        for source in state.get("inspected_sources", []):
            reference = f"{source.file_path}:{source.start_line}-{source.end_line}"
            evidence.append(
                Evidence(
                    f"source-{source.file_path}-{source.start_line}",
                    "source_code",
                    source.file_path,
                    None,
                    source.start_line,
                    source.end_line,
                    "Read-only source inspection returned this exact line range.",
                    reference,
                )
            )
        for dependency in state.get("dependencies", []):
            evidence.append(
                Evidence(
                    f"dependency-{len(evidence)}",
                    "dependency",
                    None,
                    None,
                    None,
                    None,
                    "Static dependency relationship from repository analysis.",
                    dependency,
                )
            )
        self._event(state, "collect_evidence", "completed")
        return {"evidence": evidence, "current_step": "generate_hypotheses"}

    def generate_hypotheses(self, state: InvestigationState) -> dict[str, object]:
        hypotheses = self.model.hypotheses(state["issue"], state.get("evidence", []))
        self._event(state, "generate_hypotheses", "completed")
        return {"hypotheses": hypotheses, "current_step": "verify_hypotheses"}

    def verify_hypotheses(self, state: InvestigationState) -> dict[str, object]:
        iteration = state.get("iteration_count", 0) + 1
        if iteration > self.max_iterations:
            return {
                "iteration_count": iteration,
                "status": InvestigationStatus.INCONCLUSIVE,
                "verified_hypotheses": [],
                "current_step": "build_report",
            }
        verified = self.model.verify(state.get("hypotheses", []), state.get("evidence", []))
        self._event(state, "verify_hypotheses", "completed")
        return {
            "verified_hypotheses": verified,
            "iteration_count": iteration,
            "current_step": "build_report",
        }

    def build_report(self, state: InvestigationState) -> dict[str, object]:
        verified = state.get("verified_hypotheses", [])
        supported = [
            hypothesis
            for hypothesis in verified
            if hypothesis.verification_status == VerificationStatus.SUPPORTED
        ]
        confidence = (
            Confidence.HIGH
            if len(supported) >= 2
            else Confidence.MEDIUM
            if supported
            else Confidence.LOW
        )
        root_cause = supported[0].description if supported else None
        files = tuple(
            sorted({item.file_path for item in state.get("evidence", []) if item.file_path})
        )
        symbols = tuple(sorted({item.symbol for item in state.get("evidence", []) if item.symbol}))
        classified = classify_evidence(state.get("evidence", []), state["issue"])
        report = InvestigationReport(
            issue=state["issue"],
            repository_id=state["repository_id"],
            summary=(
                "Read-only repository investigation completed; no runtime execution "
                "or modification was performed."
            ),
            relevant_components=tuple(state.get("investigation_plan", [])),
            evidence=tuple(state.get("evidence", [])),
            hypotheses=tuple(verified),
            root_cause=root_cause,
            supporting_evidence=tuple(
                item.evidence_id
                for hypothesis in supported
                for item in state.get("evidence", [])
                if item.evidence_id in hypothesis.supporting_evidence
            ),
            contradicting_evidence=tuple(
                item for hypothesis in verified for item in hypothesis.contradicting_evidence
            ),
            affected_files=files,
            relevant_symbols=symbols,
            dependencies=tuple(state.get("dependencies", [])),
            confidence=confidence,
            limitations=(
                "No repository commands, tests, or runtime execution were performed.",
                "Static dependency analysis may not reflect runtime call paths.",
            ),
            recommended_next_step="Perform a controlled verification in a later execution phase."
            if root_cause
            else "Gather additional repository evidence before drawing a root-cause conclusion.",
            classified_evidence=tuple(classified),
        )
        self._event(state, "build_report", "completed")
        return {
            "final_report": report,
            "confidence": confidence,
            "status": InvestigationStatus.COMPLETED
            if root_cause
            else InvestigationStatus.INCONCLUSIVE,
            "current_step": "complete",
        }


def initial_state(
    repository_id: str, issue: str, investigation_id: str | None = None
) -> InvestigationState:
    return InvestigationState(
        investigation_id=investigation_id or uuid4().hex,
        repository_id=repository_id,
        issue=issue,
        investigation_plan=[],
        current_step="create_plan",
        search_queries=[],
        retrieval_results=[],
        inspected_sources=[],
        dependencies=[],
        evidence=[],
        hypotheses=[],
        verified_hypotheses=[],
        confidence=Confidence.LOW,
        final_report=None,
        status=InvestigationStatus.PENDING,
        iteration_count=0,
        errors=[],
    )
