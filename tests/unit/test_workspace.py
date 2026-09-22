from pathlib import Path

import pytest

from reponyx.repositories.workspace import WorkspaceError, WorkspaceManager


def test_workspace_registration_keeps_repository_isolated(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('not executed')")
    manager = WorkspaceManager(str(tmp_path / "workspaces"), 1_000)

    workspace = manager.register_existing("repository-1", source)

    assert workspace.parent == (tmp_path / "workspaces").resolve()
    assert (workspace / "main.py").read_text() == "print('not executed')"


def test_workspace_rejects_duplicate_registration(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    manager = WorkspaceManager(str(tmp_path / "workspaces"), 1_000)
    manager.register_existing("repository-1", source)

    with pytest.raises(WorkspaceError):
        manager.register_existing("repository-1", source)
