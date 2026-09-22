"""Application service for repository intake and analysis."""

from pathlib import Path

from reponyx.config import Settings
from reponyx.repositories.analyzer import analyze_repository
from reponyx.repositories.database import RepositoryStore
from reponyx.repositories.policy import validate_repository_url
from reponyx.repositories.workspace import WorkspaceManager


class RepositoryService:
    def __init__(self, settings: Settings, store: RepositoryStore | None = None) -> None:
        self.settings = settings
        self.store = store or RepositoryStore(settings.database_url)
        self.workspaces = WorkspaceManager(settings.workspace_root, settings.max_repository_bytes)

    def create(self, url: str) -> dict[str, str]:
        canonical_url = validate_repository_url(url)
        repository_id, workspace = self.workspaces.create(canonical_url)
        self.store.create(repository_id, canonical_url, str(workspace))
        return {"id": repository_id, "url": canonical_url, "status": "cloned"}

    def register_for_testing(
        self, repository_id: str, source: Path, url: str = "https://github.com/local/fixture.git"
    ) -> None:
        workspace = self.workspaces.register_existing(repository_id, source)
        self.store.create(repository_id, url, str(workspace))

    def analyze(self, repository_id: str) -> dict[str, object]:
        record = self.store.get(repository_id)
        if record is None:
            raise KeyError(repository_id)
        analysis = analyze_repository(
            repository_id,
            Path(record.workspace_path),
            self.settings.max_file_bytes,
            self.settings.max_files,
            self.settings.max_repository_bytes,
        )
        self.store.save_analysis(repository_id, analysis)
        return self.store.analysis(repository_id) or {}

    def get(self, repository_id: str) -> dict[str, object] | None:
        record = self.store.get(repository_id)
        if record is None:
            return None
        return {
            "id": record.id,
            "url": record.url,
            "status": record.status,
            "created_at": record.created_at.isoformat(),
            "analyzed_at": record.analyzed_at.isoformat() if record.analyzed_at else None,
        }

    def list(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for record in self.store.list():
            item = self.get(record.id)
            if item is not None:
                result.append(item)
        return result

    def analysis_section(self, repository_id: str, section: str) -> object:
        analysis = self.store.analysis(repository_id)
        if analysis is None:
            raise KeyError(repository_id)
        return analysis.get(section, [])
