"""Bounded persistence for repair state and reports."""

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from reponyx.repositories.database import Base, RepositoryStore


class RepairRecord(Base):
    __tablename__ = "repairs"

    repair_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(32), index=True)
    issue: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    state_json: Mapped[str] = mapped_column(Text)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RepairStore:
    def __init__(self, repositories: RepositoryStore) -> None:
        self.sessions = repositories.sessions
        Base.metadata.create_all(repositories.engine)

    def save(self, state: dict[str, object]) -> None:
        now = datetime.now(UTC)
        report = state.get("final_report")
        payload = _jsonable(state)
        with self.sessions.begin() as session:
            record = session.get(RepairRecord, str(state["repair_id"]))
            if record is None:
                record = RepairRecord(
                    repair_id=str(state["repair_id"]),
                    repository_id=str(state["repository_id"]),
                    issue=str(state["issue"]),
                    status=str(state["repair_status"]),
                    state_json=json.dumps(payload),
                    report_json=json.dumps(_jsonable(report)) if report else None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
            else:
                record.status = str(state["repair_status"])
                record.state_json = json.dumps(payload)
                record.report_json = json.dumps(_jsonable(report)) if report else None
                record.updated_at = now

    def get(self, repair_id: str) -> dict[str, object] | None:
        with self.sessions.begin() as session:
            record = session.get(RepairRecord, repair_id)
            if record is None:
                return None
            try:
                result: dict[str, object] = json.loads(record.state_json)
                return result
            except (json.JSONDecodeError, TypeError):
                return None

    def list(self, limit: int = 100) -> list[dict[str, object]]:
        from sqlalchemy import select

        with self.sessions() as session:
            records = session.scalars(
                select(RepairRecord).order_by(RepairRecord.created_at.desc()).limit(limit)
            )
            results = []
            for record in records:
                try:
                    state = json.loads(record.state_json)
                    results.append(state)
                except (json.JSONDecodeError, TypeError):
                    continue
            return results


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(cast(Any, value))) if is_dataclass(value) else str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
