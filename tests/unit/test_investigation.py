from pathlib import Path

import pytest

from reponyx.config import Settings
from reponyx.investigation.database import InvestigationStore
from reponyx.investigation.graph import InvestigationGraph, initial_state
from reponyx.investigation.model import DeterministicInvestigationModel
from reponyx.investigation.models import Confidence, InvestigationStatus
from reponyx.investigation.service import InvestigationService
from reponyx.investigation.tools import InvestigationToolError, InvestigationTools
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mixed_repo"


def make_components(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        embedding_dimensions=16,
        investigation_max_iterations=2,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("investigation-repo", FIXTURE)
    repositories.analyze("investigation-repo")
    retrieval = RetrievalService(
        repositories,
        VectorStore(repositories.store),
        DeterministicEmbeddingProvider(16),
        8,
        settings.semantic_weight,
        settings.lexical_weight,
        settings.retrieval_character_budget,
    )
    retrieval.index("investigation-repo")
    tools = InvestigationTools(repositories, retrieval, settings.investigation_max_source_bytes)
    return settings, repositories, retrieval, tools


def test_read_only_tools_inspect_source_and_dependencies(tmp_path: Path) -> None:
    _, repositories, retrieval, tools = make_components(tmp_path)

    source = tools.inspect_source("investigation-repo", "app/auth.py", 1, 20)
    dependencies = tools.inspect_dependencies("investigation-repo")
    results = tools.search_code("investigation-repo", "password reset", top_k=3)

    assert source.file_path == "app/auth.py"
    assert "AuthService" in source.content
    assert isinstance(dependencies, list)
    assert all(result.repository_id == "investigation-repo" for result in results)
    assert (
        repositories.store.get("investigation-repo").workspace_path
        if repositories.store.get("investigation-repo")
        else ""
    )


@pytest.mark.parametrize("path", ["../secret.py", "/etc/passwd", "app/../secret.py"])
def test_source_inspection_rejects_traversal(tmp_path: Path, path: str) -> None:
    _, _, _, tools = make_components(tmp_path)

    with pytest.raises(InvestigationToolError):
        tools.inspect_source("investigation-repo", path)


def test_graph_produces_attributed_report_without_execution(tmp_path: Path) -> None:
    settings, repositories, retrieval, tools = make_components(tmp_path)
    graph = InvestigationGraph(
        tools, DeterministicInvestigationModel(), settings.investigation_max_iterations
    )

    result = graph.run(initial_state("investigation-repo", "Users cannot reset their password"))

    assert result["status"] in {InvestigationStatus.COMPLETED, InvestigationStatus.INCONCLUSIVE}
    assert result["final_report"] is not None
    assert result["final_report"].confidence in set(Confidence)
    assert result["final_report"].evidence
    assert all(item.source_reference for item in result["final_report"].evidence)
    assert result["iteration_count"] <= settings.investigation_max_iterations


def test_graph_collects_evidence_for_non_auth_issue(tmp_path: Path) -> None:
    settings, repositories, retrieval, tools = make_components(tmp_path)
    graph = InvestigationGraph(
        tools, DeterministicInvestigationModel(), settings.investigation_max_iterations
    )

    result = graph.run(
        initial_state(
            "investigation-repo",
            "Population variance returns the wrong value. "
            "Expected 2.0 for [1,2,3,4,5], reported actual 2.5.",
        )
    )

    assert result["final_report"] is not None
    assert len(result["final_report"].evidence) > 0, (
        "Investigation must collect evidence for non-authentication issues"
    )


def test_insufficient_evidence_is_not_reported_as_high_confidence(tmp_path: Path) -> None:
    _, _, _, tools = make_components(tmp_path)

    class NoEvidenceModel(DeterministicInvestigationModel):
        def plan(
            self, issue: str, repository_map: dict[str, object]
        ) -> tuple[list[str], list[str]]:
            return [], []

    graph = InvestigationGraph(tools, NoEvidenceModel(), 2)
    state = initial_state("investigation-repo", "A completely unrelated unknown issue")
    state["search_queries"] = []

    result = graph.run(state)

    assert result["final_report"] is not None
    assert result["final_report"].confidence == Confidence.LOW
    assert result["final_report"].root_cause is None
    assert result["status"] == InvestigationStatus.INCONCLUSIVE


def test_investigation_service_persists_report_and_api_shape(tmp_path: Path) -> None:
    settings, repositories, retrieval, _ = make_components(tmp_path)
    service = InvestigationService(
        settings, repositories, retrieval, InvestigationStore(repositories.store)
    )

    created = service.create("investigation-repo", "Which function handles password reset?")
    detail = service.get(created["investigation_id"])
    report = service.report(created["investigation_id"])

    assert created["repository_id"] == "investigation-repo"
    assert detail is not None
    assert report is not None
    assert report["repository_id"] == "investigation-repo"


def test_missing_repository_isolation(tmp_path: Path) -> None:
    _, _, retrieval, tools = make_components(tmp_path)

    with pytest.raises(KeyError):
        retrieval.search(
            "other-repository",
            "AuthService",
            3,
            __import__(
                "reponyx.retrieval.models", fromlist=["RetrievalFilters"]
            ).RetrievalFilters(),
            False,
        )
    with pytest.raises(InvestigationToolError):
        tools.inspect_source("other-repository", "app/auth.py")
