"""Run the deterministic read-only investigation benchmark."""

import json
import shutil
from pathlib import Path

from reponyx.config import Settings
from reponyx.investigation.graph import InvestigationGraph, initial_state
from reponyx.investigation.model import DeterministicInvestigationModel
from reponyx.investigation.tools import InvestigationTools
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.service import RepositoryService
from reponyx.retrieval.embeddings import DeterministicEmbeddingProvider
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore


def main() -> None:
    root = Path(__file__).parents[1]
    shutil.rmtree(root / "evaluation" / "investigation-workspaces", ignore_errors=True)
    (root / "evaluation" / "investigation.db").unlink(missing_ok=True)
    settings = Settings(
        _env_file=None,
        workspace_root=str(root / "evaluation" / "investigation-workspaces"),
        database_url=f"sqlite:///{root / 'evaluation' / 'investigation.db'}",
        embedding_dimensions=16,
    )
    repositories = RepositoryService(settings, RepositoryStore(settings.database_url))
    repository_id = "investigation-benchmark"
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
    graph = InvestigationGraph(
        InvestigationTools(repositories, retrieval, settings.investigation_max_source_bytes),
        DeterministicInvestigationModel(),
        settings.investigation_max_iterations,
    )
    cases = [
        "Users cannot reset their password",
        "Which function handles password reset?",
        "An unrelated issue with unavailable evidence",
    ]
    reports = [graph.run(initial_state(repository_id, issue))["final_report"] for issue in cases]
    result = [
        {
            "issue": report.issue,
            "status": report.confidence.value,
            "evidence_count": len(report.evidence),
            "attribution_accuracy": sum(bool(item.source_reference) for item in report.evidence)
            / max(len(report.evidence), 1),
        }
        for report in reports
        if report
    ]
    output = root / "evaluation" / "investigation-results.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
