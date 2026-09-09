import subprocess
from pathlib import Path

import pytest

from coding_agent.tools.git import GitError, current_head, git_diff, require_clean_worktree


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    run_git(tmp_path, "init", "-b", "main")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    run_git(tmp_path, "add", "app.py")
    run_git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def test_current_head_and_clean_check(repo: Path) -> None:
    head = current_head(repo)
    assert len(head) == 40
    require_clean_worktree(repo)
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(GitError, match="clean working tree"):
        require_clean_worktree(repo)


def test_git_diff_reports_patch_and_sorted_paths_without_mutation(repo: Path) -> None:
    base = current_head(repo)
    (repo / "z.py").write_text("z = 1\n", encoding="utf-8")
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    before = run_git(repo, "status", "--porcelain")
    result = git_diff(repo, base)
    after = run_git(repo, "status", "--porcelain")
    assert "diff --git" in result.patch
    assert "z = 1" in result.patch
    assert result.changed_files == ("app.py", "z.py")
    assert after == before
