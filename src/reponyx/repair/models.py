"""Typed repair workspace, patch, execution, and report models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TypedDict

from reponyx.execution.models import ExecutionResult


class RepairStatus(StrEnum):
    CREATED = "created"
    INVESTIGATING = "investigating"
    PATCHING = "patching"
    TESTING = "testing"
    FAILED = "failed"
    COMPLETED = "completed"
    DISCARDED = "discarded"
    CANCELLED = "cancelled"


class ChangeType(StrEnum):
    MODIFIED = "modified"
    CREATED = "created"
    DELETED = "deleted"


class VerificationLevel(StrEnum):
    UNVERIFIED = "unverified"
    TARGETED_TESTS_PASSED = "targeted_tests_passed"
    BROADER_TESTS_PASSED = "broader_tests_passed"
    FULL_TESTS_PASSED = "full_tests_passed"
    INCOMPLETE = "verification_incomplete"


@dataclass(frozen=True, slots=True)
class RepairWorkspace:
    repair_id: str
    repository_id: str
    workspace_path: str
    created_at: datetime
    status: RepairStatus
    iteration_count: int
    created_by_investigation: str | None


@dataclass(frozen=True, slots=True)
class FileChange:
    file_path: str
    change_type: ChangeType
    old_content_hash: str | None
    new_content_hash: str | None
    diff: str


@dataclass(frozen=True, slots=True)
class ProposedChange:
    file_path: str
    operation: ChangeType
    content: str | None


@dataclass(frozen=True, slots=True)
class Patch:
    patch_id: str
    repair_id: str
    files_changed: tuple[FileChange, ...]
    diff: str
    description: str
    reason: str
    evidence: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PatchAttempt:
    iteration: int
    patch: Patch | None
    validation_error: str | None
    execution_id: str | None
    test_result: ExecutionResult | None
    failure_analysis: str | None


@dataclass(frozen=True, slots=True)
class RepairReport:
    repair_id: str
    repository_id: str
    issue: str
    summary: str
    root_cause: str | None
    files_changed: tuple[str, ...]
    symbols_changed: tuple[str, ...]
    patch_description: str | None
    iterations: int
    tests_run: tuple[str, ...]
    tests_passed: tuple[str, ...]
    tests_failed: tuple[str, ...]
    final_status: RepairStatus
    verification_level: VerificationLevel
    root_cause_analysis: object | None = None
    repair_plan: object | None = None
    failure_analyses: list[object] = field(default_factory=list)
    repair_decision: str | None = None
    retrieved_sources: list[object] = field(default_factory=list)
    llm_calls: int = 0
    model_provider: str = "mock"
    model_name: str = "deterministic"
    confidence: str = "low"
    limitations: tuple[str, ...] = ()
    final_diff: str = ""
    confidence_score: float = 0.0
    confidence_reasons: tuple[str, ...] = ()
    patch_attempts: tuple[object, ...] = ()


class RepairState(TypedDict, total=False):
    repair_id: str
    repository_id: str
    issue: str
    investigation_id: str | None
    workspace_path: str
    current_patch: Patch | None
    patch_history: list[PatchAttempt]
    test_executions: list[ExecutionResult]
    test_results: list[str]
    iteration_count: int
    changed_files: list[str]
    changed_lines: int
    repair_status: RepairStatus
    final_diff: str
    root_cause: str | None
    evidence: list[str]
    targeted_framework: str
    broad_framework: str | None
    final_report: RepairReport | None
    errors: list[str]
    cancelled: bool
    current_step: str
    proposed_changes: list[ProposedChange]
    patch_validation_error: str | None
    patch_description: str
    patch_reason: str
    verification_level: VerificationLevel
    primary_file: str
    repair_plan: dict[str, object]
    root_cause_analysis: object
    failure_analyses: list[object]
    repair_decision: str
    retrieved_sources: list[object]
    llm_calls: int
    model_provider: str
    model_name: str
