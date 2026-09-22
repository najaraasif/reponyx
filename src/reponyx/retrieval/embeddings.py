"""Provider-neutral embedding adapters."""

import hashlib
import logging
import math
import struct
from collections.abc import Sequence

import httpx

from reponyx.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot return a valid batch."""


class EmbeddingProvider:
    name = "base"
    model = "base"
    dimensions = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    name = "deterministic"

    def __init__(self, dimensions: int = 64, model: str = "hash-embedding-v1") -> None:
        self.dimensions = dimensions
        self.model = model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        values: list[float] = []
        for index in range(self.dimensions):
            digest = hashlib.blake2b(f"{index}:{text}".encode(), digest_size=8).digest()
            integer = struct.unpack(">Q", digest)[0]
            values.append((integer / 2**63) - 1.0)
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, dimensions: int, timeout: float) -> None:
        self.model = model
        self.dimensions = dimensions
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            response = self._client.post(
                "/embeddings", json={"model": self.model, "input": list(texts)}
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list) or len(data) != len(texts):
                raise EmbeddingError("embedding provider returned an invalid batch")
            vectors = [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]
            if any(len(vector) != self.dimensions for vector in vectors):
                raise EmbeddingError("embedding dimension mismatch")
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("OpenAI embedding request failed") from exc


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, dimensions: int, timeout: float) -> None:
        self.model = model
        self.dimensions = dimensions
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        try:
            for text in texts:
                response = self._client.post(
                    "/api/embeddings", json={"model": self.model, "prompt": text}
                )
                response.raise_for_status()
                vector = response.json()["embedding"]
                if len(vector) != self.dimensions:
                    raise EmbeddingError("embedding dimension mismatch")
                vectors.append(vector)
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Ollama embedding request failed") from exc


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider
    if provider == "deterministic":
        return DeterministicEmbeddingProvider(
            settings.embedding_dimensions, settings.embedding_model
        )
    if provider == "openai":
        key = settings.openai_api_key
        if not key:
            raise EmbeddingError("REPONYX_OPENAI_API_KEY is required for OpenAI embeddings")
        return OpenAIEmbeddingProvider(
            key,
            settings.embedding_model,
            settings.embedding_dimensions,
            settings.embedding_timeout_seconds,
        )
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            settings.ollama_base_url,
            settings.embedding_model,
            settings.embedding_dimensions,
            settings.embedding_timeout_seconds,
        )
    raise EmbeddingError(f"unsupported embedding provider: {provider}")
