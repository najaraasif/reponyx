"""Run the deterministic fixture retrieval benchmark."""

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from reponyx.config import Settings
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider
from reponyx.retrieval.evaluation import EvaluationCase, evaluate, write_report
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore


def main() -> None:
    root = Path(__file__).parents[1]
    output = root / "evaluation"
    output.mkdir(exist_ok=True)
    shutil.rmtree(output / "workspaces", ignore_errors=True)
    (output / "benchmark.db").unlink(missing_ok=True)
    settings = Settings(
        _env_file=None,
        workspace_root=str(output / "workspaces"),
        database_url=f"sqlite:///{output / 'benchmark.db'}",
        embedding_dimensions=16,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repository_id = "benchmark-repo"
    repositories.register_for_testing(repository_id, root / "tests" / "fixtures" / "mixed_repo")
    repositories.analyze(repository_id)
    retrieval = RetrievalService(
        repositories,
        VectorStore(repositories.store),
        DeterministicEmbeddingProvider(16),
        8,
        settings.semantic_weight,
        settings.lexical_weight,
        settings.retrieval_character_budget,
    )
    retrieval.index(repository_id)
    metrics = evaluate(
        retrieval.pipeline,
        [
            EvaluationCase(
                repository_id,
                "Where is authentication implemented?",
                ("app/auth.py",),
                ("AuthService",),
            ),
            EvaluationCase(
                repository_id,
                "Which function handles password reset?",
                ("app/auth.py",),
                ("reset_password",),
            ),
            EvaluationCase(
                repository_id, "What files depend on AuthService?", ("app/routes.ts",), ()
            ),
        ],
    )
    write_report(metrics, output / "retrieval-results.json", output / "retrieval-report.md")
    print(json.dumps([asdict(metric) for metric in metrics], indent=2))


if __name__ == "__main__":
    main()
