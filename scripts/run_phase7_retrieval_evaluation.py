"""Run a reproducible 20-query retrieval evaluation over the fixture corpus."""

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from reponyx.config import Settings
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider
from reponyx.retrieval.evaluation import EvaluationCase, evaluate
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore


def main() -> None:
    root = Path(__file__).parents[1]
    work = root / "evaluation" / "phase7-retrieval"
    shutil.rmtree(work / "workspaces", ignore_errors=True)
    (work / "evaluation.db").unlink(missing_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        workspace_root=str(work / "workspaces"),
        database_url=f"sqlite:///{work / 'evaluation.db'}",
        embedding_dimensions=16,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repository_id = "phase7-retrieval"
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
    queries = [
        ("authentication service", ("app/auth.py",), ("AuthService",)),
        ("password reset", ("app/auth.py",), ("reset_password",)),
        ("password reset method", ("app/auth.py",), ("reset_password",)),
        ("requires auth decorator", ("app/auth.py",), ("requires_auth",)),
        ("wrapper function", ("app/auth.py",), ("wrapper",)),
        ("typescript controller", ("app/routes.ts",), ("PasswordController",)),
        ("reset request interface", ("app/routes.ts",), ("ResetRequest",)),
        ("controller reset method", ("app/routes.ts",), ("reset",)),
        ("auth import", ("app/routes.ts",), ()),
        ("email validation", ("app/auth.py",), ("reset_password",)),
        ("authentication entry point", ("app/auth.py",), ("AuthService",)),
        ("credential recovery", ("app/auth.py",), ("reset_password",)),
        ("decorator behavior", ("app/auth.py",), ("requires_auth",)),
        ("controller dependency", ("app/routes.ts",), ("PasswordController",)),
        ("interface type", ("app/routes.ts",), ("ResetRequest",)),
        ("service class", ("app/auth.py",), ("AuthService",)),
        ("reset endpoint", ("app/routes.ts",), ("reset",)),
        ("test fixture auth", ("tests/fixture_auth.py",), ()),
        ("python auth module", ("app/auth.py",), ()),
        ("typescript route module", ("app/routes.ts",), ()),
    ]
    metrics = evaluate(
        retrieval.pipeline,
        [EvaluationCase(repository_id, query, files, symbols) for query, files, symbols in queries],
        k=5,
    )
    output = root / "evaluation" / "phase7-retrieval-results.json"
    output.write_text(
        json.dumps([asdict(metric) for metric in metrics], indent=2), encoding="utf-8"
    )
    print(json.dumps([asdict(metric) for metric in metrics], indent=2))


if __name__ == "__main__":
    main()
