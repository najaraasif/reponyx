from fastapi.testclient import TestClient

from reponyx.config import Settings
from reponyx.main import create_app


def test_health_endpoint_reports_service_metadata() -> None:
    client = TestClient(create_app(Settings(app_name="Test reponyx", environment="test")))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Test reponyx",
        "version": "0.1.0",
        "environment": "test",
    }
