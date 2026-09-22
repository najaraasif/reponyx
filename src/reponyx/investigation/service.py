"""Application service for read-only investigations."""

from dataclasses import asdict

from reponyx.config import Settings
from reponyx.execution.service import ExecutionService
from reponyx.investigation.database import InvestigationStore
from reponyx.investigation.graph import InvestigationGraph, initial_state
from reponyx.investigation.model import build_investigation_model
from reponyx.investigation.tools import InvestigationTools
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.service import RetrievalService


class InvestigationService:
    def __init__(
        self,
        settings: Settings,
        repositories: RepositoryService,
        retrieval: RetrievalService,
        execution: ExecutionService | None = None,
        store: InvestigationStore | None = None,
        graph: InvestigationGraph | None = None,
    ) -> None:
        self.repositories = repositories
        self.retrieval = retrieval
        self.store = store or InvestigationStore(repositories.store)
        self.graph = graph or InvestigationGraph(
            InvestigationTools(
                repositories, retrieval, settings.investigation_max_source_bytes, execution
            ),
            build_investigation_model(settings),
            settings.investigation_max_iterations,
        )

    def create(self, repository_id: str, issue: str) -> dict[str, str]:
        if self.repositories.get(repository_id) is None:
            raise KeyError(repository_id)
        if self.retrieval.indexer.vectors.count(repository_id) == 0:
            self.retrieval.index(repository_id)
        state = initial_state(repository_id, issue)
        self.store.create(state["investigation_id"], repository_id, issue, state)
        result = self.graph.run(state)
        self.store.save(result)
        return {
            "investigation_id": result["investigation_id"],
            "repository_id": repository_id,
            "status": result["status"].value,
        }

    def get(self, investigation_id: str) -> dict[str, object] | None:
        state = self.store.get(investigation_id)
        if state is None:
            return None
        return {
            "investigation_id": state["investigation_id"],
            "repository_id": state["repository_id"],
            "issue": state["issue"],
            "status": state["status"].value,
            "current_step": state.get("current_step"),
            "iteration_count": state.get("iteration_count", 0),
            "errors": state.get("errors", []),
        }

    def list(self, limit: int = 100) -> list[dict[str, object]]:
        return self.store.list(limit)

    def report(self, investigation_id: str) -> dict[str, object] | None:
        state = self.store.get(investigation_id)
        if state is None or state.get("final_report") is None:
            return None
        report = state["final_report"]
        if report is None:
            return None
        return asdict(report)
