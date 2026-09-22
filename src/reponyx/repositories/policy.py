"""Validation and filtering policies for untrusted repositories."""

import re
from pathlib import PurePosixPath
from urllib.parse import urlparse


class RepositoryPolicyError(ValueError):
    """Raised when an intake or workspace policy is violated."""


_SUPPORTED_SUFFIXES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
}
_IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "vendor",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "ignored",
}
_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".exe", ".dll"}


def validate_repository_url(value: str) -> str:
    """Accept only public HTTPS GitHub repository URLs, with no credentials/query."""

    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise RepositoryPolicyError("repository URL must be an HTTPS github.com URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RepositoryPolicyError("repository URL cannot contain credentials or query data")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise RepositoryPolicyError("repository URL must identify exactly owner and repository")
    return f"https://github.com/{parts[0]}/{parts[1].removesuffix('.git')}.git"


def language_for_path(path: str) -> str | None:
    """Return a supported language from a repository-relative path."""

    return _SUPPORTED_SUFFIXES.get(PurePosixPath(path).suffix.lower())


def is_ignored_path(path: str) -> bool:
    """Reject generated, VCS, hidden metadata, binary, and unsupported paths."""

    pure = PurePosixPath(path)
    if any(part in _IGNORED_DIRECTORIES for part in pure.parts):
        return True
    if any(part.startswith(".") and part not in {".github"} for part in pure.parts):
        return True
    return pure.suffix.lower() in _BINARY_SUFFIXES or language_for_path(path) is None


def safe_relative_path(path: str) -> str:
    """Normalize a relative POSIX path and reject traversal or absolute paths."""

    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or not normalized or normalized.startswith("/"):
        raise RepositoryPolicyError("path must remain relative to the repository workspace")
    return pure.as_posix()
