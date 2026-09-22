import pytest

from reponyx.repositories.discovery import DiscoveryError, discover_files
from reponyx.repositories.policy import (
    RepositoryPolicyError,
    safe_relative_path,
    validate_repository_url,
)


def test_github_url_is_canonicalized() -> None:
    assert (
        validate_repository_url("https://github.com/acme/project")
        == "https://github.com/acme/project.git"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/project",
        "https://evil.example/acme/project",
        "https://github.com/acme/project?token=x",
    ],
)
def test_unsafe_url_is_rejected(url: str) -> None:
    with pytest.raises(RepositoryPolicyError):
        validate_repository_url(url)


@pytest.mark.parametrize("path", ["../secret.py", "/tmp/file.py", "..\\secret.py"])
def test_path_traversal_is_rejected(path: str) -> None:
    with pytest.raises(RepositoryPolicyError):
        safe_relative_path(path)


def test_file_discovery_filters_binary_and_generated_files(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("value = 1")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "bad.js").write_text("bad")
    (tmp_path / "image.png").write_bytes(b"\x00\x01")

    assert discover_files(tmp_path, 100, 10, 1000) == ["src/ok.py"]


def test_file_count_limit_is_enforced(tmp_path) -> None:
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    with pytest.raises(DiscoveryError):
        discover_files(tmp_path, 100, 1, 1000)
