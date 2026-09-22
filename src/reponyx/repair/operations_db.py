"""SQLAlchemy persistence for Phase 8 operational records."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from reponyx.repair.operations import JobStatus, RepairJob
from reponyx.repositories.database import Base, RepositoryStore


class LLMCallRecord(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repair_id: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer)


class RepairMetricRecord(Base):
    __tablename__ = "repair_metrics"

    repair_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_llm_calls: Mapped[int] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_duration_ms: Mapped[int] = mapped_column(Integer)
    iterations: Mapped[int] = mapped_column(Integer)
    tests_run: Mapped[int] = mapped_column(Integer)
    tests_passed: Mapped[int] = mapped_column(Integer)
    tests_failed: Mapped[int] = mapped_column(Integer)
    final_status: Mapped[str] = mapped_column(String(32))
    verification_level: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RepairJobRecord(Base):
    __tablename__ = "repair_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repair_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class OperationsStore:
    def __init__(self, repositories: RepositoryStore) -> None:
        self.sessions = repositories.sessions
        Base.metadata.create_all(repositories.engine)

    def save_job(self, job: RepairJob) -> None:
        with self.sessions.begin() as session:
            session.add(
                RepairJobRecord(
                    job_id=job.job_id,
                    repair_id=job.repair_id,
                    status=job.status.value,
                    created_at=job.created_at,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    error=job.error,
                )
            )

    def update_job(self, job: RepairJob) -> None:
        with self.sessions.begin() as session:
            record = session.get(RepairJobRecord, job.job_id)
            if record is None:
                raise KeyError(job.job_id)
            record.status = job.status.value
            record.started_at = job.started_at
            record.completed_at = job.completed_at
            record.error = job.error

    def list_jobs(self, repair_id: str | None = None) -> list[RepairJob]:
        with self.sessions() as session:
            statement = select(RepairJobRecord).order_by(RepairJobRecord.created_at)
            if repair_id:
                statement = statement.where(RepairJobRecord.repair_id == repair_id)
            return [
                RepairJob(
                    record.job_id,
                    record.repair_id,
                    JobStatus(record.status),
                    record.created_at,
                    record.started_at,
                    record.completed_at,
                    record.error,
                )
                for record in session.scalars(statement)
            ]
