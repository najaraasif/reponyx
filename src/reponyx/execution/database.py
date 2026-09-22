"""Bounded execution metadata persistence."""

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from reponyx.execution.models import ExecutionResult, ExecutionStatus, TestSummary
from reponyx.repositories.database import Base, RepositoryStore


class ExecutionRecord(Base):
    __tablename__ = "executions"

    execution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(32), index=True)
    command_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text)
    stderr: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer)
    result_json: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExecutionStore:
    def __init__(self, repositories: RepositoryStore) -> None:
        self.sessions = repositories.sessions
        Base.metadata.create_all(repositories.engine)

    def save(self, result: ExecutionResult) -> None:
        payload = asdict(result)
        payload["status"] = result.status.value
        payload["command"] = list(result.command)
        payload["started_at"] = result.started_at.isoformat()
        payload["completed_at"] = result.completed_at.isoformat()
        with self.sessions.begin() as session:
            session.add(
                ExecutionRecord(
                    execution_id=result.execution_id,
                    repository_id=result.repository_id,
                    command_json=json.dumps(result.command),
                    status=result.status.value,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_ms=result.duration_ms,
                    result_json=json.dumps(payload),
                    started_at=result.started_at,
                    completed_at=result.completed_at,
                )
            )

    def get(self, execution_id: str) -> ExecutionResult | None:
        with self.sessions() as session:
            record = session.get(ExecutionRecord, execution_id)
        if record is None:
            return None
        value = json.loads(record.result_json)
        value["status"] = ExecutionStatus(value["status"])
        value["started_at"] = datetime.fromisoformat(value["started_at"])
        value["completed_at"] = datetime.fromisoformat(value["completed_at"])
        if value.get("test_summary"):
            value["test_summary"] = TestSummary(**value["test_summary"])
        value["command"] = tuple(value["command"])
        return ExecutionResult(**value)
