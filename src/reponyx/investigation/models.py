"""Strongly typed investigation state and report models."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypedDict

from reponyx.retrieval.models import RetrievalResult


class InvestigationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceCategory(StrEnum):
    PRIMARY_IMPLEMENTATION = "primary_implementation"
    PRIMARY_TESTS = "primary_tests"
    DIRECT_REFERENCES = "direct_references"
    SUPPORTING = "supporting"
    UNRELATED = "unrelated"


@dataclass(frozen=True, slots=True)
class SourceInspection:
    file_path: str
    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True, slots=True)
class ClassifiedEvidenceItem:
    evidence_id: str
    category: EvidenceCategory
    file_path: str
    symbol: str | None
    relevance_score: float
    reason: str


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    type: str
    file_path: str | None
    symbol: str | None
    start_line: int | None
    end_line: int | None
    description: str
    source_reference: str


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    execution_id: str
    repository_id: str
    command: tuple[str, ...]
    status: str
    exit_code: int | None
    test_summary: object | None
    relevant_output: str
    source_reference: str = "execution"


@dataclass(slots=True)
class Hypothesis:
    hypothesis_id: str
    description: str
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: Confidence = Confidence.LOW


@dataclass(frozen=True, slots=True)
class InvestigationReport:
    issue: str
    repository_id: str
    summary: str
    relevant_components: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    hypotheses: tuple[Hypothesis, ...]
    root_cause: str | None
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    affected_files: tuple[str, ...]
    relevant_symbols: tuple[str, ...]
    dependencies: tuple[str, ...]
    confidence: Confidence
    limitations: tuple[str, ...]
    recommended_next_step: str
    classified_evidence: tuple[ClassifiedEvidenceItem, ...] = ()


class InvestigationState(TypedDict, total=False):
    investigation_id: str
    repository_id: str
    issue: str
    investigation_plan: list[str]
    current_step: str
    search_queries: list[str]
    retrieval_results: list[RetrievalResult]
    inspected_sources: list[SourceInspection]
    dependencies: list[str]
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]
    verified_hypotheses: list[Hypothesis]
    confidence: Confidence
    final_report: InvestigationReport | None
    status: InvestigationStatus
    iteration_count: int
    errors: list[str]
