"""Safe repository file discovery."""

from pathlib import Path

from reponyx.repositories.policy import is_ignored_path, safe_relative_path


class DiscoveryError(ValueError):
    """Raised when repository limits are violated."""


def discover_files(
    root: Path, max_file_bytes: int, max_files: int, max_repository_bytes: int
) -> list[str]:
    files: list[str] = []
    total = 0
    for candidate in sorted(root.rglob("*")):
        relative = safe_relative_path(candidate.relative_to(root).as_posix())
        if candidate.is_symlink() or not candidate.is_file() or is_ignored_path(relative):
            continue
        size = candidate.stat().st_size
        if size > max_file_bytes:
            continue
        total += size
        if total > max_repository_bytes:
            raise DiscoveryError("repository exceeds configured source size limit")
        files.append(relative)
        if len(files) > max_files:
            raise DiscoveryError("repository exceeds configured file count limit")
    return files
