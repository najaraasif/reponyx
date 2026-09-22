from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider


def test_deterministic_embeddings_are_batched_and_repeatable() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=8)

    first = provider.embed(["AuthService", "password reset"])
    second = provider.embed(["AuthService", "password reset"])

    assert len(first) == 2
    assert all(len(vector) == 8 for vector in first)
    assert first == second
