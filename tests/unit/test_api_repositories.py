from pathlib import Path

from fastapi.testclient import TestClient

from reponyx.config import Settings
from reponyx.main import create_app
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService


def test_repository_analysis_endpoints(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "mixed_repo"
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
    )
    service = RepositoryService(settings, RepositoryStore(settings.database_url))
    service.register_for_testing("fixture-repository", fixture)
    client = TestClient(create_app(settings, service))

    response = client.post("/repositories/fixture-repository/analyze")

    assert response.status_code == 200
    assert "symbols" in response.json()
    assert client.get("/repositories/fixture-repository/symbols").status_code == 200
    assert client.get("/repositories/fixture-repository/dependencies").status_code == 200
    assert client.get("/repositories/fixture-repository/structure").status_code == 200


def test_repository_endpoint_rejects_unsafe_url(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
    )
    service = RepositoryService(settings, RepositoryStore(settings.database_url))
    client = TestClient(create_app(settings, service))

    response = client.post("/repositories", json={"url": "http://evil.example/repo"})

    assert response.status_code == 422
