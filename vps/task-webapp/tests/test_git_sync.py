"""Tests for git_sync.py — git operations (mocked).

Uses temporary git repo so we don't touch production.
"""
import os
import subprocess
import tempfile
import pytest
from unittest.mock import patch


# Set env for git_sync to import
os.environ.setdefault("GITHUB_PAT", "fake-pat")
os.environ.setdefault("GITHUB_USER", "test-user")
os.environ.setdefault("GIT_REPO_NAME", "test-repo")


@pytest.fixture
def tmp_git_repo(monkeypatch):
    """Create a temp git repo and patch VAULT_PATH."""
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True)

    import git_sync
    monkeypatch.setattr(git_sync, "VAULT_PATH", tmp)
    yield tmp

    import shutil
    shutil.rmtree(tmp)


def test_commit_and_push_no_changes(tmp_git_repo, monkeypatch):
    """If no changes, commit_and_push returns True without pushing."""
    import git_sync

    # Mock _run to track push calls, let git commands actually run for status
    real_run = git_sync._run
    pushed = []

    def fake_run(cmd, cwd=None):
        if "push" in cmd:
            pushed.append(cmd)
            return 0, ""
        if "remote" in cmd:
            return 0, "origin  fake-url (fetch)"
        return real_run(cmd, cwd or tmp_git_repo)

    monkeypatch.setattr(git_sync, "_run", fake_run)

    # Empty repo, nothing to commit
    result = git_sync.commit_and_push("test: no changes")
    # Should not call push (nothing to commit)
    assert len(pushed) == 0


def test_commit_and_push_with_changes(tmp_git_repo, monkeypatch):
    """With changes, commit_and_push runs add/commit/push."""
    import git_sync
    from pathlib import Path

    Path(tmp_git_repo, "test.md").write_text("hello", encoding="utf-8")

    push_called = []

    def fake_run(cmd, cwd=None):
        target = cwd or tmp_git_repo
        if "push" in cmd:
            push_called.append(cmd)
            return 0, "ok"
        if "remote" in cmd and "get-url" in cmd:
            return 0, "origin  fake-url (fetch)"
        # Run real command and return real stdout for status to work
        result = subprocess.run(cmd, cwd=target, capture_output=True, text=True)
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()

    monkeypatch.setattr(git_sync, "_run", fake_run)

    result = git_sync.commit_and_push("test: with change")
    assert len(push_called) == 1


def test_ensure_remote_adds_missing(tmp_git_repo, monkeypatch):
    """ensure_remote adds origin if missing."""
    import git_sync

    calls = []

    def fake_run(cmd, cwd=None):
        calls.append(cmd)
        if "remote" in cmd and "get-url" in cmd:
            return 1, ""  # no remote
        return 0, ""

    monkeypatch.setattr(git_sync, "_run", fake_run)
    git_sync.ensure_remote()

    add_cmds = [c for c in calls if "add" in c]
    assert len(add_cmds) >= 1
