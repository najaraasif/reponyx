from pathlib import Path

from fastapi.testclient import TestClient

from reponyx.config import Settings
from reponyx.investigation.database import InvestigationStore
from reponyx.investigation.service import InvestigationService
from reponyx.main import create_app
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore


def test_investigation_api_returns_status_and_report(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "mixed_repo"
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        embedding_dimensions=16,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("api-investigation", fixture)
    repositories.analyze("api-investigation")
    retrieval = RetrievalService(
        repositories,
        VectorStore(repositories.store),
        DeterministicEmbeddingProvider(16),
        8,
        settings.semantic_weight,
        settings.lexical_weight,
        settings.retrieval_character_budget,
    )
    retrieval.index("api-investigation")
    investigation = InvestigationService(
        settings,
        repositories,
        retrieval,
        InvestigationStore(repositories.store),
    )
    client = TestClient(create_app(settings, repositories, retrieval, investigation))

    created = client.post(
        "/repositories/api-investigation/investigations",
        json={"issue": "Which function handles password reset?"},
    )
    investigation_id = created.json()["investigation_id"]
    detail = client.get(f"/investigations/{investigation_id}")
    report = client.get(f"/investigations/{investigation_id}/report")

    assert created.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["repository_id"] == "api-investigation"
    assert report.status_code == 200
    assert report.json()["evidence"]
    assert all(item["source_reference"] for item in report.json()["evidence"])
