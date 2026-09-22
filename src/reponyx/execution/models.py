"""Typed execution requests, results, and test evidence."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    RESOURCE_LIMITED = "resource_limited"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    timeout_seconds: float = 120.0
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    pids_limit: int = 128
    output_limit: int = 200_000


@dataclass(frozen=True, slots=True)
class EnvironmentPolicy:
    allowed: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_id: str
    repository_id: str
    command: tuple[str, ...]
    working_directory: str
    timeout_seconds: float
    environment_policy: EnvironmentPolicy
    resource_policy: ResourcePolicy


@dataclass(frozen=True, slots=True)
class TestSummary:
    framework: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    discovered: int = 0
    duration_ms: int | None = None
    parsing_complete: bool = True
    failure_summaries: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    execution_id: str
    repository_id: str
    command: tuple[str, ...]
    status: ExecutionStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    resource_limited: bool
    output_truncated: bool
    container_id: str | None
    started_at: datetime
    completed_at: datetime
    test_summary: TestSummary | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    execution_id: str
    repository_id: str
    command: tuple[str, ...]
    status: ExecutionStatus
    exit_code: int | None
    test_summary: TestSummary | None
    relevant_output: str
    source_reference: str = "execution"
