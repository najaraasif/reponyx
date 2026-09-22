"""Operational models for LLM calls, repair metrics, jobs, and review."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class LLMCallMetric:
    repair_id: str
    iteration: int
    operation: str
    provider: str
    model: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    request_id: str | None
    status: str
    error_type: str | None


@dataclass(frozen=True, slots=True)
class RepairMetric:
    repair_id: str
    total_llm_calls: int
    total_tokens: int | None
    total_duration_ms: int
    iterations: int
    tests_run: int
    tests_passed: int
    tests_failed: int
    final_status: str
    verification_level: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class RepairJob:
    job_id: str
    repair_id: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
