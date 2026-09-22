"""Isolated repository workspace and clone operations."""

import hashlib
import logging
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from reponyx.repositories.policy import validate_repository_url

logger = logging.getLogger(__name__)


class WorkspaceError(RuntimeError):
    """Raised when a workspace cannot be created or safely used."""


class WorkspaceManager:
    def __init__(self, root: str, max_repository_bytes: int) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_repository_bytes = max_repository_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, repository_url: str) -> tuple[str, Path]:
        canonical_url = validate_repository_url(repository_url)
        repository_id = hashlib.sha256(f"{canonical_url}:{uuid4()}".encode()).hexdigest()[:24]
        workspace = (self.root / repository_id).resolve()
        if self.root not in workspace.parents:
            raise WorkspaceError("workspace escaped configured root")
        workspace.mkdir()
        try:
            subprocess.run(
                ["git", "clone", "--no-tags", "--depth", "1", canonical_url, str(workspace)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            size = sum(item.stat().st_size for item in workspace.rglob("*") if item.is_file())
            if size > self.max_repository_bytes:
                raise WorkspaceError("repository exceeds configured size limit")
            logger.info("repository_cloned", extra={"repository_id": repository_id})
            return repository_id, workspace
        except (subprocess.SubprocessError, OSError) as exc:
            shutil.rmtree(workspace, ignore_errors=True)
            raise WorkspaceError("repository clone failed") from exc

    def register_existing(self, repository_id: str, source: Path) -> Path:
        """Copy a test or already-cloned tree without following symlinks outside it."""

        destination = (self.root / repository_id).resolve()
        if self.root not in destination.parents:
            raise WorkspaceError("workspace escaped configured root")
        if destination.exists():
            raise WorkspaceError("workspace already exists")
        source = source.resolve()
        shutil.copytree(source, destination, symlinks=True)
        return destination
