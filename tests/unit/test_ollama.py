import httpx
import pytest

from reponyx.repair.ollama import OllamaStructuredProvider


def test_ollama_health_and_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OllamaStructuredProvider("http://ollama", "qwen2.5-coder", 5, 100)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder"}]})
        return httpx.Response(200, json={"response": '{"changes": []}'})

    provider.client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ollama")
    assert provider.health()["model_available"] is True
    assert provider.generate_structured_output("patch", "data", "PatchProposal") == {"changes": []}


def test_ollama_connection_failure_is_diagnostic() -> None:
    provider = OllamaStructuredProvider("http://127.0.0.1:1", "missing", 0.01, 10)

    result = provider.health()

    assert result["available"] is False
    assert result["status"] == "connection_failed"
