"""Git sync for obsidian-tasks vault."""
from __future__ import annotations

import subprocess
import logging

logger = logging.getLogger(__name__)

VAULT_PATH = "/root/obsidian-tasks"
import os
_PAT = os.environ.get("GITHUB_PAT", "")
_USER = os.environ.get("GITHUB_USER", "Prygunov-Andrei")
_REPO = os.environ.get("GIT_REPO_NAME", "obsidian-tasks")
GIT_REMOTE = f"https://{_USER}:{_PAT}@github.com/{_USER}/{_REPO}.git"
GIT_BRANCH = "master"


def _run(cmd: list[str], cwd: str = VAULT_PATH) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip() + "\n" + result.stderr.strip()
        return result.returncode, output.strip()
    except Exception as e:
        return 1, str(e)


def ensure_remote():
    """Ensure git remote is set correctly."""
    code, out = _run(["git", "remote", "get-url", "origin"])
    if code != 0 or GIT_REMOTE not in out:
        _run(["git", "remote", "remove", "origin"])
        _run(["git", "remote", "add", "origin", GIT_REMOTE])


def pull():
    """Pull latest changes from remote."""
    ensure_remote()
    code, out = _run(["git", "pull", "origin", GIT_BRANCH, "--rebase"])
    logger.info(f"git pull: {code} {out}")
    return code == 0


def commit_and_push(message: str = "webapp: update tasks"):
    """Add, commit, push changes."""
    ensure_remote()
    _run(["git", "add", "-A"])

    # Check if there are changes to commit
    code, out = _run(["git", "status", "--porcelain"])
    if not out.strip():
        logger.info("git: nothing to commit")
        return True

    code, out = _run(["git", "commit", "-m", message])
    logger.info(f"git commit: {code} {out}")

    code, out = _run(["git", "push", "origin", GIT_BRANCH])
    logger.info(f"git push: {code} {out}")
    return code == 0


def init_repo():
    """Initialize repo if needed."""
    import os
    if not os.path.exists(os.path.join(VAULT_PATH, ".git")):
        _run(["git", "init"], cwd=VAULT_PATH)
        _run(["git", "branch", "-M", GIT_BRANCH], cwd=VAULT_PATH)
    ensure_remote()
    # Configure git user
    _run(["git", "config", "user.email", "andrei@prygunov.com"])
    _run(["git", "config", "user.name", "Task WebApp"])
