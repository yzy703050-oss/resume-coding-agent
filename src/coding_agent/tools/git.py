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
    names = _git(repo_root, "diff", "--name-only", "-z", "--no-ext-diff", base_commit, "--")
    tracked = {name for name in names.split("\0") if name}
    untracked_output = _git(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    untracked = {name for name in untracked_output.split("\0") if name}
    for relative_path in sorted(untracked):
        patch += _untracked_patch(repo_root, relative_path)
    changed = tuple(sorted(tracked | untracked))
    return GitDiff(patch=patch, changed_files=changed)


def _untracked_patch(repo_root: Path, relative_path: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative_path],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in {0, 1}:
        raise GitError(result.stderr.strip() or "could not diff untracked file")
    return result.stdout
