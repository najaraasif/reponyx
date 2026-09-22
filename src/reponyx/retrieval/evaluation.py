"""Reproducible retrieval benchmark and report generation."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from reponyx.retrieval.models import RetrievalFilters
from reponyx.retrieval.pipeline import RetrievalPipeline


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    repository_id: str
    query: str
    relevant_files: tuple[str, ...]
    relevant_symbols: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationMetric:
    method: str
    recall_at_k: float
    precision_at_k: float
    mrr: float


def evaluate(
    pipeline: RetrievalPipeline, cases: list[EvaluationCase], k: int = 5
) -> list[EvaluationMetric]:
    metrics: list[EvaluationMetric] = []
    for method in ("lexical", "semantic", "hybrid"):
        recalls: list[float] = []
        precisions: list[float] = []
        reciprocal_ranks: list[float] = []
        for case in cases:
            if method == "lexical":
                results = pipeline.search_lexical(
                    case.repository_id, case.query, k, RetrievalFilters()
                )
            elif method == "semantic":
                results = pipeline.search_semantic(
                    case.repository_id, case.query, k, RetrievalFilters()
                )
            else:
                results = pipeline.search(case.repository_id, case.query, k, rerank=False)
            hits = [
                result
                for result in results
                if result.file_path in case.relevant_files
                or result.symbol_name in case.relevant_symbols
            ]
            recalls.append(
                min(
                    1.0,
                    len({result.file_path for result in hits}) / max(len(case.relevant_files), 1),
                )
            )
            precisions.append(len(hits) / max(k, 1))
            reciprocal_ranks.append(
                1
                / (
                    next(
                        (index + 1 for index, result in enumerate(results) if result in hits), k + 1
                    )
                )
            )
        metrics.append(
            EvaluationMetric(
                method,
                sum(recalls) / len(recalls),
                sum(precisions) / len(precisions),
                sum(reciprocal_ranks) / len(reciprocal_ranks),
            )
        )
    return metrics


def write_report(metrics: list[EvaluationMetric], json_path: Path, markdown_path: Path) -> None:
    json_path.write_text(
        json.dumps([asdict(metric) for metric in metrics], indent=2), encoding="utf-8"
    )
    lines = ["| Method | Recall@5 | Precision@5 | MRR |", "| --- | ---: | ---: | ---: |"]
    lines.extend(
        f"| {metric.method} | {metric.recall_at_k:.3f} | "
        f"{metric.precision_at_k:.3f} | {metric.mrr:.3f} |"
        for metric in metrics
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
