"""Validated patch application and filesystem-derived unified diffs."""

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from reponyx.repair.models import ChangeType, FileChange, Patch, ProposedChange


class PatchValidationError(ValueError):
    """Raised for unsafe, stale, or oversized patch proposals."""


@dataclass(frozen=True, slots=True)
class PatchLimits:
    max_files: int = 8
    max_lines: int = 400
    max_file_bytes: int = 100_000
    max_total_bytes: int = 300_000
    max_created_files: int = 4
    max_deleted_files: int = 2


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class PatchService:
    def __init__(self, limits: PatchLimits | None = None) -> None:
        self.limits = limits or PatchLimits()

    def validate(self, workspace: Path, changes: list[ProposedChange]) -> None:
        if not changes or len(changes) > self.limits.max_files:
            raise PatchValidationError("patch file count exceeds limits")
        created = deleted = total_bytes = total_lines = 0
        for change in changes:
            relative = self._safe_path(change.file_path)
            target = (workspace / relative).resolve()
            if workspace.resolve() not in target.parents:
                raise PatchValidationError("patch path escapes repair workspace")
            if target.exists() and target.is_symlink():
                raise PatchValidationError("patch target cannot be a symlink")
            if change.operation == ChangeType.CREATED:
                created += 1
                if target.exists():
                    raise PatchValidationError("created file already exists")
            elif change.operation == ChangeType.DELETED:
                deleted += 1
                if not target.is_file():
                    raise PatchValidationError("deleted file does not exist")
            elif not target.is_file():
                raise PatchValidationError("modified file does not exist")
            if change.content is not None:
                size = len(change.content.encode())
                total_bytes += size
                total_lines += len(change.content.splitlines())
                if size > self.limits.max_file_bytes:
                    raise PatchValidationError("patch file exceeds size limit")
        if created > self.limits.max_created_files or deleted > self.limits.max_deleted_files:
            raise PatchValidationError("created/deleted file limits exceeded")
        if total_bytes > self.limits.max_total_bytes or total_lines > self.limits.max_lines:
            raise PatchValidationError("patch size limit exceeded")

    def apply(
        self,
        repair_id: str,
        workspace: Path,
        changes: list[ProposedChange],
        description: str,
        reason: str,
        evidence: list[str],
    ) -> Patch:
        self.validate(workspace, changes)
        file_changes: list[FileChange] = []
        diffs: list[str] = []
        for change in changes:
            relative = self._safe_path(change.file_path)
            target = (workspace / relative).resolve()
            old = target.read_text(encoding="utf-8") if target.exists() else ""
            old_hash = content_hash(old.encode()) if target.exists() else None
            if change.operation == ChangeType.DELETED:
                target.unlink()
                new = ""
                new_hash = None
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.content or "", encoding="utf-8", newline="")
                new = change.content or ""
                new_hash = content_hash(new.encode())
            diff = "".join(
                difflib.unified_diff(
                    old.splitlines(keepends=True),
                    new.splitlines(keepends=True),
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
            )
            file_changes.append(FileChange(relative, change.operation, old_hash, new_hash, diff))
            diffs.append(diff)
        return Patch(
            uuid4().hex,
            repair_id,
            tuple(file_changes),
            "".join(diffs),
            description,
            reason,
            tuple(evidence),
            __import__("datetime").datetime.now(__import__("datetime").UTC),
        )

    @staticmethod
    def _safe_path(value: str) -> str:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            raise PatchValidationError("patch path must be repository-relative")
        if path.parts[0].endswith(":"):
            raise PatchValidationError("drive-qualified patch path is forbidden")
        return path.as_posix()
