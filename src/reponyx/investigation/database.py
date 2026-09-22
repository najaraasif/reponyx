"""Persistence for bounded investigation state and reports."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from reponyx.investigation.models import (
    Confidence,
    Evidence,
    Hypothesis,
    InvestigationReport,
    InvestigationState,
    InvestigationStatus,
    SourceInspection,
    VerificationStatus,
)
from reponyx.repositories.database import Base, RepositoryStore


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    investigation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(32), index=True)
    issue: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    state_json: Mapped[str] = mapped_column(Text)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InvestigationStore:
    def __init__(self, repositories: RepositoryStore) -> None:
        self.sessions = repositories.sessions
        Base.metadata.create_all(repositories.engine)

    def create(
        self, investigation_id: str, repository_id: str, issue: str, state: InvestigationState
    ) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            session.add(
                InvestigationRecord(
                    investigation_id=investigation_id,
                    repository_id=repository_id,
                    issue=issue,
                    status="pending",
                    state_json=json.dumps(state_to_dict(state)),
                    report_json=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    def save(self, state: InvestigationState) -> None:
        with self.sessions.begin() as session:
            record = session.get(InvestigationRecord, state["investigation_id"])
            if record is None:
                raise KeyError(state["investigation_id"])
            record.status = state["status"].value
            record.state_json = json.dumps(state_to_dict(state))
            report = state.get("final_report")
            record.report_json = json.dumps(asdict(report)) if report is not None else None
            record.updated_at = datetime.now(UTC)

    def get(self, investigation_id: str) -> InvestigationState | None:
        with self.sessions() as session:
            record = session.get(InvestigationRecord, investigation_id)
        if record is None:
            return None
        return state_from_dict(json.loads(record.state_json))

    def list(self, limit: int = 100) -> list[dict[str, object]]:
        with self.sessions() as session:
            records = (
                session.query(InvestigationRecord)
                .order_by(InvestigationRecord.created_at.desc())
                .limit(limit)
                .all()
            )
        return [
            {
                "investigation_id": r.investigation_id,
                "repository_id": r.repository_id,
                "issue": r.issue,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in records
        ]


def state_to_dict(state: InvestigationState) -> dict[str, Any]:
    result = dict(state)
    result["status"] = state["status"].value
    result["retrieval_results"] = [asdict(item) for item in state.get("retrieval_results", [])]
    result["inspected_sources"] = [asdict(item) for item in state.get("inspected_sources", [])]
    result["evidence"] = [asdict(item) for item in state.get("evidence", [])]
    result["hypotheses"] = [asdict(item) for item in state.get("hypotheses", [])]
    result["verified_hypotheses"] = [asdict(item) for item in state.get("verified_hypotheses", [])]
    if state.get("final_report"):
        report = state["final_report"]
        result["final_report"] = asdict(report) if report is not None else None
    return result


def state_from_dict(value: dict[str, Any]) -> InvestigationState:
    value = dict(value)
    value["status"] = InvestigationStatus(value["status"])
    value["inspected_sources"] = [
        SourceInspection(**item) for item in value.get("inspected_sources", [])
    ]
    value["evidence"] = [Evidence(**item) for item in value.get("evidence", [])]
    value["hypotheses"] = [_hypothesis(item) for item in value.get("hypotheses", [])]
    value["verified_hypotheses"] = [
        _hypothesis(item) for item in value.get("verified_hypotheses", [])
    ]
    if isinstance(value.get("final_report"), dict):
        report = dict(value["final_report"])
        report["confidence"] = Confidence(report["confidence"])
        report["evidence"] = tuple(Evidence(**item) for item in report["evidence"])
        report["hypotheses"] = tuple(_hypothesis(item) for item in report["hypotheses"])
        value["final_report"] = InvestigationReport(**report)
    return cast(InvestigationState, value)


def _hypothesis(value: dict[str, Any]) -> Hypothesis:
    item = dict(value)
    item["verification_status"] = VerificationStatus(item["verification_status"])
    item["confidence"] = Confidence(item["confidence"])
    return Hypothesis(**item)
