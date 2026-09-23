from pathlib import Path

from reponyx.config import Settings
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingError,
    EmbeddingProvider,
)
from reponyx.retrieval.evaluation import EvaluationCase, evaluate, write_report
from reponyx.retrieval.models import RetrievalFilters
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mixed_repo"


def make_service(tmp_path: Path) -> RetrievalService:
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        embedding_dimensions=16,
        embedding_batch_size=2,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repositories.register_for_testing("retrieval-repo", FIXTURE)
    repositories.analyze("retrieval-repo")
    return RetrievalService(
        repositories,
        VectorStore(repositories.store),
        DeterministicEmbeddingProvider(16),
        2,
        settings.semantic_weight,
        settings.lexical_weight,
        settings.retrieval_character_budget,
    )


def test_indexing_batches_and_replaces_stale_vectors(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    first = service.index("retrieval-repo")
    count = service.indexer.vectors.count("retrieval-repo")
    second = service.index("retrieval-repo")

    assert first.status == "completed"
    assert first.chunks_indexed == count
    assert second.status == "completed"
    assert service.indexer.vectors.count("retrieval-repo") == count


def test_search_has_source_attribution_and_filters(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.index("retrieval-repo")

    results = service.search(
        "retrieval-repo",
        "password reset",
        5,
        RetrievalFilters(language="python"),
        False,
    )

    assert results
    assert all(result.repository_id == "retrieval-repo" for result in results)
    assert all(result.language == "python" for result in results)
    assert all(result.chunk_id and result.file_path and result.start_line > 0 for result in results)
    assert any(result.symbol_name == "reset_password" for result in results)


def test_context_deduplicates_and_respects_budget(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.index("retrieval-repo")
    service.pipeline.character_budget = 350

    context = service.context(
        "retrieval-repo", "AuthService password reset", 10, RetrievalFilters(), False
    )

    assert len(context.text) <= 350
    assert context.sources
    assert all(source.source_id for source in context.sources)
    assert context.text.count("SOURCE:") == len(context.sources)


def test_query_rewrite_has_deterministic_fallback(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.index("retrieval-repo")

    results = service.search(
        "retrieval-repo", "Where does login happen?", 5, RetrievalFilters(), False
    )

    assert results


def test_evaluation_writes_machine_and_human_reports(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.index("retrieval-repo")
    metrics = evaluate(
        service.pipeline,
        [EvaluationCase("retrieval-repo", "password reset", ("app/auth.py",), ("reset_password",))],
        k=5,
    )
    json_path = tmp_path / "evaluation.json"
    markdown_path = tmp_path / "evaluation.md"
    write_report(metrics, json_path, markdown_path)

    assert {metric.method for metric in metrics} == {"lexical", "semantic", "hybrid"}
    assert json_path.exists()
    assert "Recall@5" in markdown_path.read_text()


class FailingProvider(EmbeddingProvider):
    name = "failing"
    model = "failing"
    dimensions = 2

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("provider unavailable")


def test_failed_embedding_batch_does_not_leave_vectors(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.indexer.embeddings = FailingProvider()

    status = service.index("retrieval-repo")

    assert status.status == "failed"
    assert status.chunks_failed > 0
    assert service.indexer.vectors.count("retrieval-repo") == 0


def test_persist_index_survives_restart(tmp_path: Path) -> None:
    # Phase 1: Index the repository
    settings = Settings(
        _env_file=None,
        workspace_root=str(tmp_path / "workspaces"),
        database_url=f"sqlite:///{tmp_path / 'reponyx.db'}",
        embedding_dimensions=16,
        embedding_batch_size=2,
    )
    store = RepositoryStore(settings.database_url)
    repositories = RepositoryService(settings, store)
    repositories.register_for_testing("persist-repo", FIXTURE)
    repositories.analyze("persist-repo")
    embedding_provider = DeterministicEmbeddingProvider(16)
    vectors = VectorStore(store)
    service = RetrievalService(
        repositories, vectors, embedding_provider, 2,
        settings.semantic_weight, settings.lexical_weight,
        settings.retrieval_character_budget,
    )

    index_status = service.index("persist-repo")
    indexed_count = service.indexer.vectors.count("persist-repo")
    assert index_status.status == "completed"
    assert indexed_count > 0

    # Phase 2: Simulate server restart — create new service instances from same DB
    new_store = RepositoryStore(settings.database_url)
    new_repositories = RepositoryService(settings, new_store)
    new_vectors = VectorStore(new_store)
    new_service = RetrievalService(
        new_repositories, new_vectors, embedding_provider, 2,
        settings.semantic_weight, settings.lexical_weight,
        settings.retrieval_character_budget,
    )

    # Phase 3: Investigate without re-indexing
    assert new_vectors.is_indexed("persist-repo")
    assert new_vectors.count("persist-repo") == indexed_count
    results = new_service.search(
        "persist-repo", "password reset", 5, RetrievalFilters(), False
    )
    assert results
    assert all(result.repository_id == "persist-repo" for result in results)
    assert all(result.chunk_id and result.file_path for result in results)


def test_is_indexed_before_and_after(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    assert not service.is_indexed("retrieval-repo")
    assert service.indexer.vectors.count("retrieval-repo") == 0

    service.index("retrieval-repo")

    assert service.is_indexed("retrieval-repo")
    assert service.indexer.vectors.count("retrieval-repo") > 0


def test_is_indexed_unknown_repo() -> None:
    settings = Settings(
        _env_file=None,
        workspace_root="/tmp/reponyx-nonexistent",
        database_url="sqlite:///:memory:",
        embedding_dimensions=16,
    )
    store = RepositoryStore(settings.database_url)
    repositories = RepositoryService(settings, store)
    vectors = VectorStore(store)
    embeddings = DeterministicEmbeddingProvider(16)
    service = RetrievalService(
        repositories, vectors, embeddings, 2,
        settings.semantic_weight, settings.lexical_weight,
        settings.retrieval_character_budget,
    )
    assert not service.is_indexed("nonexistent-repo")
