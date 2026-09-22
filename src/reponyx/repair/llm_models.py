"""Structured LLM outputs used by Phase 6 repair intelligence."""

from dataclasses import dataclass
from enum import StrEnum

from reponyx.repair.models import ProposedChange


class FailureType(StrEnum):
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    ASSERTION_FAILURE = "assertion_failure"
    REGRESSION = "regression"
    ENVIRONMENT_FAILURE = "environment_failure"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    TEST_INFRASTRUCTURE_FAILURE = "test_infrastructure_failure"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RepairPlan:
    summary: str
    root_cause: str
    affected_files: tuple[str, ...]
    affected_symbols: tuple[str, ...]
    reasoning_evidence: tuple[str, ...]
    test_strategy: tuple[str, ...]
    expected_behavior: str


@dataclass(frozen=True, slots=True)
class RootCauseAnalysis:
    observed_behavior: str
    expected_behavior: str
    likely_root_cause: str
    affected_files: tuple[str, ...]
    affected_symbols: tuple[str, ...]
    dependencies: tuple[str, ...]
    supporting_evidence: tuple[str, ...]
    alternative_hypotheses: tuple[str, ...]
    selected_reason: str


@dataclass(frozen=True, slots=True)
class PatchProposal:
    changes: tuple[ProposedChange, ...]
    summary: str
    reason: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FailureAnalysis:
    failure_type: FailureType
    likely_cause: str
    affected_files: tuple[str, ...]
    affected_symbols: tuple[str, ...]
    is_patch_related: bool
    recommended_action: str
    evidence: tuple[str, ...]


class RepairDecision(StrEnum):
    CONTINUE_REPAIR = "continue_repair"
    FINALIZE_SUCCESS = "finalize_success"
    FINALIZE_FAILURE = "finalize_failure"
    STOP_INCONCLUSIVE = "stop_inconclusive"
