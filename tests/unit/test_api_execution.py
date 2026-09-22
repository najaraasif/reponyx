from pathlib import Path

from fastapi.testclient import TestClient
from tests.unit.test_execution_service import FakeRunner

from reponyx.config import Settings
from reponyx.execution.service import ExecutionService
from reponyx.main import create_app
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService


def test_test_api_does_not_accept_arbitrary_commands(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        execution_root=str(tmp_path / "executions"),
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    source = tmp_path / "source"
    source.mkdir()
    repositories.register_for_testing("api-execution", source)
    execution = ExecutionService(settings, repositories, FakeRunner())
    client = TestClient(create_app(settings, repositories, execution_service=execution))

    rejected = client.post(
        "/repositories/api-execution/tests",
        json={"framework": "sh -c echo unsafe"},
    )
    accepted = client.post("/repositories/api-execution/tests", json={"framework": "pytest"})

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert client.get(f"/executions/{accepted.json()['execution_id']}").status_code == 200
