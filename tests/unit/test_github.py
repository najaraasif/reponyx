"""Tests for GitHub PR creation service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from reponyx.config import Settings
from reponyx.github.service import GitHubService, GitHubServiceError, parse_owner_repo


def test_parse_owner_repo_with_suffix() -> None:
    owner, repo = parse_owner_repo("https://github.com/najaraasif/reponyx.git")
    assert owner == "najaraasif"
    assert repo == "reponyx"


def test_parse_owner_repo_without_suffix() -> None:
    owner, repo = parse_owner_repo("https://github.com/acme/project")
    assert owner == "acme"
    assert repo == "project"


def test_parse_owner_repo_invalid() -> None:
    with pytest.raises(GitHubServiceError):
        parse_owner_repo("https://example.com/not-github")


def test_github_service_requires_token() -> None:
    settings = Settings(_env_file=None, github_token=None)
    service = GitHubService(settings)
    assert service.token is None


def test_github_service_with_token() -> None:
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    assert service.token == "ghp_test123"


def test_build_pr_body_contains_repair_info() -> None:
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    body = service._build_pr_body(
        issue_body="Fix the variance bug",
        root_cause="Population variance divides by N instead of N-1",
        confidence="high",
        diff="- old\n+ new",
        changed_files=["src/statistics.py"],
        repair_id="abc123",
    )
    assert "Reponyx" in body
    assert "abc123" in body
    assert "high" in body
    assert "variance" in body.lower()
    assert "src/statistics.py" in body


def test_build_pr_body_truncates_long_issue() -> None:
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    long_issue = "x" * 5000
    body = service._build_pr_body(
        issue_body=long_issue,
        root_cause=None,
        confidence="low",
        diff="",
        changed_files=[],
        repair_id="test123",
    )
    assert len(body) < 5000


def test_build_pr_body_handles_empty_diff() -> None:
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    body = service._build_pr_body(
        issue_body="test issue",
        root_cause=None,
        confidence="low",
        diff="",
        changed_files=[],
        repair_id="test123",
    )
    assert "test issue" in body
    assert "Reponyx" in body


@patch("reponyx.github.service.subprocess.run")
def test_create_branch_calls_git_checkout(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    service._create_branch(Path("/tmp/test"), "fix/test-branch")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "git" in args
    assert "checkout" in args
    assert "fix/test-branch" in args


@patch("reponyx.github.service.subprocess.run")
def test_commit_changes_calls_git_add_and_commit(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    service._commit_changes(
        Path("/tmp/test"),
        ["src/main.py", "tests/test_main.py"],
        "Fix the bug",
        "repair123",
    )
    assert mock_run.call_count == 3


@patch("reponyx.github.service.subprocess.run")
def test_push_branch_calls_git_push(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    service._push_branch(Path("/tmp/test"), "fix/test-branch")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "push" in args
    assert "fix/test-branch" in args


@patch("reponyx.github.service.subprocess.run")
def test_create_branch_failure_raises_error(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=1, stderr="branch already exists")
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    with pytest.raises(GitHubServiceError, match="Failed to create branch"):
        service._create_branch(Path("/tmp/test"), "fix/test-branch")


def test_headers_include_auth_token() -> None:
    settings = Settings(_env_file=None, github_token="ghp_test123")
    service = GitHubService(settings)
    headers = service._headers()
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer ghp_test123"


def test_headers_without_token() -> None:
    settings = Settings(_env_file=None, github_token=None)
    service = GitHubService(settings)
    headers = service._headers()
    assert "Authorization" not in headers
