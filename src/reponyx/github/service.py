"""GitHub integration for creating pull requests from verified repairs."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from reponyx.config import Settings

logger = logging.getLogger(__name__)


class GitHubServiceError(RuntimeError):
    """Raised when a GitHub operation fails."""


@dataclass(frozen=True, slots=True)
class PullRequestResult:
    pr_url: str
    pr_number: int
    branch_name: str
    commit_sha: str
    repository: str


def parse_owner_repo(github_url: str) -> tuple[str, str]:
    parsed = urlparse(github_url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise GitHubServiceError(f"Cannot parse owner/repo from URL: {github_url}")
    owner = parts[0]
    repo = parts[-1].removesuffix(".git")
    return owner, repo


class GitHubService:
    def __init__(self, settings: Settings) -> None:
        self.token = settings.github_token
        self.branch_prefix = settings.github_pr_branch_prefix
        self.api_base = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def create_pull_request(
        self,
        workspace_path: Path,
        repository_url: str,
        issue_title: str,
        issue_body: str,
        diff: str,
        changed_files: list[str],
        repair_id: str,
        root_cause: str | None = None,
        confidence: str = "low",
        branch_name: str | None = None,
    ) -> PullRequestResult:
        owner, repo = parse_owner_repo(repository_url)
        repo_slug = f"{owner}/{repo}"

        if branch_name is None:
            sanitized_title = re.sub(r"[^a-z0-9]+", "-", issue_title.lower())[:50].strip("-")
            branch_name = f"{self.branch_prefix}/{sanitized_title}"

        self._create_branch(workspace_path, branch_name)
        self._commit_changes(workspace_path, changed_files, issue_title, repair_id)
        self._push_branch(workspace_path, branch_name)

        pr_body = self._build_pr_body(
            issue_body=issue_body,
            root_cause=root_cause,
            confidence=confidence,
            diff=diff,
            changed_files=changed_files,
            repair_id=repair_id,
        )

        pr_result = self._create_github_pr(
            repo_slug=repo_slug,
            branch_name=branch_name,
            title=f"Fix: {issue_title}",
            body=pr_body,
        )

        return PullRequestResult(
            pr_url=pr_result["html_url"],
            pr_number=pr_result["number"],
            branch_name=branch_name,
            commit_sha=pr_result["head"]["sha"],
            repository=repo_slug,
        )

    def _create_branch(self, workspace_path: Path, branch_name: str) -> None:
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise GitHubServiceError(f"Failed to create branch: {result.stderr}")

    def _commit_changes(
        self, workspace_path: Path, changed_files: list[str], message: str, repair_id: str
    ) -> None:
        for file_path in changed_files:
            subprocess.run(
                ["git", "add", file_path],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

        commit_message = f"fix: {message}\n\nAutomated repair by Reponyx ({repair_id[:8]})"
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise GitHubServiceError(f"Failed to commit: {result.stderr}")

    def _push_branch(self, workspace_path: Path, branch_name: str) -> None:
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise GitHubServiceError(f"Failed to push: {result.stderr}")

    def _build_pr_body(
        self,
        issue_body: str,
        root_cause: str | None,
        confidence: str,
        diff: str,
        changed_files: list[str],
        repair_id: str,
    ) -> str:
        sections = [
            "## Automated Repair by Reponyx",
            "",
            f"**Repair ID:** `{repair_id}`",
            f"**Confidence:** {confidence}",
            "",
            "## Issue",
            issue_body[:2000] if issue_body else "No issue description provided.",
            "",
        ]

        if root_cause:
            sections.extend(["## Root Cause", root_cause, ""])

        sections.extend([
            "## Changed Files",
            *[f"- `{f}`" for f in changed_files],
            "",
        ])

        if diff:
            sections.extend([
                "## Diff",
                "<details>",
                "<summary>Show diff</summary>",
                "",
                "```diff",
                diff[:6000],
                "```",
                "</details>",
                "",
            ])

        sections.extend([
            "---",
            "*This pull request was automatically generated by [Reponyx](https://github.com/najaraasif/reponyx).*",
        ])

        return "\n".join(sections)

    def _create_github_pr(
        self, repo_slug: str, branch_name: str, title: str, body: str
    ) -> dict:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.api_base}/repos/{repo_slug}/pulls",
                headers=self._headers(),
                json={
                    "title": title,
                    "body": body,
                    "head": branch_name,
                    "base": "main",
                },
            )
            if response.status_code == 401:
                raise GitHubServiceError("GitHub authentication failed. Check GITHUB_TOKEN.")
            if response.status_code == 404:
                raise GitHubServiceError(f"Repository not found: {repo_slug}")
            if response.status_code == 422:
                error_msg = response.json().get("message", "Validation failed")
                if "already exists" in error_msg.lower():
                    raise GitHubServiceError(f"A pull request already exists for branch {branch_name}")
                raise GitHubServiceError(f"GitHub API error: {error_msg}")
            response.raise_for_status()
            return response.json()
