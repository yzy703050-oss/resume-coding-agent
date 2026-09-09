"""Read-only Git evidence and repository precondition helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitDiff:
    patch: str
    changed_files: tuple[str, ...]


def _git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise GitError(f"could not run Git: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise GitError(detail)
    return result.stdout


def current_head(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").strip()


def require_clean_worktree(repo_root: Path) -> None:
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
    if status.strip():
        raise GitError("a clean working tree is required")


def git_diff(repo_root: Path, base_commit: str) -> GitDiff:
    patch = _git(repo_root, "diff", "--binary", "--no-ext-diff", base_commit, "--")
    names = _git(repo_root, "diff", "--name-only", "--no-ext-diff", base_commit, "--")
    changed = tuple(sorted(line for line in names.splitlines() if line))
    return GitDiff(patch=patch, changed_files=changed)
