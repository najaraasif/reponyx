"""Ephemeral repair workspace lifecycle."""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from reponyx.repair.models import RepairStatus, RepairWorkspace
from reponyx.repositories.service import RepositoryService


class RepairWorkspaceError(RuntimeError):
    """Raised when a repair workspace cannot be created or safely managed."""


class RepairWorkspaceService:
    def __init__(self, repositories: RepositoryService, root: str) -> None:
        self.repositories = repositories
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.active: dict[str, RepairWorkspace] = {}

    def create(self, repository_id: str, investigation_id: str | None = None) -> RepairWorkspace:
        record = self.repositories.store.get(repository_id)
        if record is None:
            raise KeyError(repository_id)
        repair_id = uuid4().hex
        target = (self.root / repair_id).resolve()
        if self.root not in target.parents:
            raise RepairWorkspaceError("repair workspace escaped configured root")
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Copying workspace from {record.workspace_path} to {target}")
        shutil.copytree(record.workspace_path, target, symlinks=True)
        import os

        logger.info(f"Copied workspace, contents: {os.listdir(target)}")
        workspace = RepairWorkspace(
            repair_id,
            repository_id,
            str(target),
            datetime.now(UTC),
            RepairStatus.CREATED,
            0,
            investigation_id,
        )
        self.active[repair_id] = workspace
        return workspace

    def update(
        self, repair_id: str, status: RepairStatus, iteration_count: int | None = None
    ) -> RepairWorkspace:
        current = self.active.get(repair_id)
        if current is None:
            raise KeyError(repair_id)
        updated = RepairWorkspace(
            current.repair_id,
            current.repository_id,
            current.workspace_path,
            current.created_at,
            status,
            iteration_count if iteration_count is not None else current.iteration_count,
            current.created_by_investigation,
        )
        self.active[repair_id] = updated
        return updated

    def cleanup(self, repair_id: str) -> None:
        current = self.active.pop(repair_id, None)
        if current:
            shutil.rmtree(current.workspace_path, ignore_errors=True)

    def path(self, repair_id: str) -> Path:
        current = self.active.get(repair_id)
        if current is None:
            raise KeyError(repair_id)
        return Path(current.workspace_path).resolve()
