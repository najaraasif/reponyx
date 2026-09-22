from pathlib import Path

from fastapi.testclient import TestClient

from reponyx.config import Settings
from reponyx.main import create_app
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore


def test_retrieval_endpoints_return_attributed_results(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "mixed_repo"
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        embedding_dimensions=16,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("api-repo", fixture)
    repositories.analyze("api-repo")
    retrieval = RetrievalService(
        repositories,
        VectorStore(repositories.store),
        DeterministicEmbeddingProvider(16),
        8,
        settings.semantic_weight,
        settings.lexical_weight,
        settings.retrieval_character_budget,
    )
    client = TestClient(create_app(settings, repositories, retrieval))

    assert client.post("/repositories/api-repo/index").status_code == 200
    status = client.get("/repositories/api-repo/index/status")
    search = client.post(
        "/repositories/api-repo/search", json={"query": "password reset", "top_k": 5}
    )
    context = client.post(
        "/repositories/api-repo/context", json={"query": "AuthService", "top_k": 3}
    )

    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert search.status_code == 200
    assert all(result["chunk_id"] and result["file_path"] for result in search.json())
    assert context.status_code == 200
    assert context.json()["sources"]


def test_retrieval_requires_an_existing_repository(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
    )
    client = TestClient(create_app(settings))

    response = client.post("/repositories/missing/search", json={"query": "AuthService"})

    assert response.status_code == 404
