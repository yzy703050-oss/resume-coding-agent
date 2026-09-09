import os
from pathlib import Path

import pytest

from coding_agent.tools.paths import PathPolicyError, resolve_confined


@pytest.mark.parametrize("candidate", ["../outside.txt", "C:/Windows/System32", "//server/share"])
def test_resolve_confined_rejects_escape(tmp_path: Path, candidate: str) -> None:
    with pytest.raises(PathPolicyError):
        resolve_confined(tmp_path, candidate)


def test_resolve_confined_accepts_child(tmp_path: Path) -> None:
    assert resolve_confined(tmp_path, "src/app.py") == (tmp_path / "src/app.py").resolve()


def test_resolve_confined_rejects_link_to_outside(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(PathPolicyError):
        resolve_confined(root, "escape/file.py")
