import subprocess
from pathlib import Path

from coding_agent.memory.identity import ProjectIdentityResolver, canonicalize_remote


def git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True)


def test_equivalent_remote_forms_have_stable_credential_free_identity(tmp_path: Path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"
    for path in (one, two):
        path.mkdir()
        git(path, "init")
    git(one, "remote", "add", "origin", "git@Example.COM:Org/Repo.git")
    git(two, "remote", "add", "origin", "ssh://token@EXAMPLE.com/Org/Repo/")

    first = ProjectIdentityResolver(one).resolve()
    assert first == ProjectIdentityResolver(one).resolve()
    assert first == ProjectIdentityResolver(two).resolve()
    assert first.startswith("sha256:")
    assert "token" not in first and "example" not in first
    assert canonicalize_remote("https://user:pass@EXAMPLE.com/A/B.git?x=1#f") == (
        "https://example.com/A/B"
    )


def test_no_remote_uses_stable_common_dir_and_isolates_projects(tmp_path: Path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"
    for path in (one, two):
        path.mkdir()
        git(path, "init")
    assert ProjectIdentityResolver(one).resolve() == ProjectIdentityResolver(one).resolve()
    assert ProjectIdentityResolver(one).resolve() != ProjectIdentityResolver(two).resolve()


def test_linked_worktree_without_remote_shares_common_directory_identity(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    linked = tmp_path / "linked"
    repo.mkdir()
    git(repo, "init")
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(
        repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial"
    )
    git(repo, "worktree", "add", str(linked), "-b", "linked")

    assert ProjectIdentityResolver(repo).resolve() == ProjectIdentityResolver(linked).resolve()
