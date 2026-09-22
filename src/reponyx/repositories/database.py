"""SQLAlchemy persistence for repository metadata and analysis summaries."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from reponyx.repositories.models import RepositoryAnalysis


class Base(DeclarativeBase):
    pass


class RepositoryRecord(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    workspace_path: Mapped[str] = mapped_column(String(1_000))
    status: Mapped[str] = mapped_column(String(32), default="cloned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class RepositoryStore:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def create(self, repository_id: str, url: str, workspace_path: str) -> RepositoryRecord:
        record = RepositoryRecord(
            id=repository_id,
            url=url,
            workspace_path=workspace_path,
            status="cloned",
            created_at=datetime.now(UTC),
        )
        with self.sessions.begin() as session:
            session.add(record)
        return record

    def get(self, repository_id: str) -> RepositoryRecord | None:
        with self.sessions() as session:
            return session.get(RepositoryRecord, repository_id)

    def list(self) -> list[RepositoryRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(select(RepositoryRecord).order_by(RepositoryRecord.created_at))
            )

    def save_analysis(self, repository_id: str, analysis: RepositoryAnalysis) -> None:
        with self.sessions.begin() as session:
            record = session.get(RepositoryRecord, repository_id)
            if record is None:
                raise KeyError(repository_id)
            record.status = "analyzed"
            record.analyzed_at = analysis.analyzed_at
            record.analysis_json = json.dumps(analysis_to_dict(analysis))

    def analysis(self, repository_id: str) -> dict[str, Any] | None:
        record = self.get(repository_id)
        return json.loads(record.analysis_json) if record and record.analysis_json else None


def analysis_to_dict(analysis: RepositoryAnalysis) -> dict[str, Any]:
    return {
        "repository_id": analysis.repository_id,
        "files": analysis.files,
        "languages": analysis.languages,
        "symbols": [asdict(symbol) for symbol in analysis.symbols],
        "imports": [asdict(reference) for reference in analysis.imports],
        "dependencies": [asdict(dependency) for dependency in analysis.dependencies],
        "chunks": [asdict(chunk) for chunk in analysis.chunks],
        "directories": analysis.directories,
        "frameworks": analysis.frameworks,
        "package_managers": analysis.package_managers,
        "entry_points": analysis.entry_points,
        "test_locations": analysis.test_locations,
        "configuration_files": analysis.configuration_files,
        "parse_failures": analysis.parse_failures,
        "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
    }
