"""Manifest loading, fixture preparation, and independent oracle execution."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.tools.paths import resolve_confined


class TaskManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    task: str = Field(min_length=1)
    setup_files: dict[str, str]
    oracle_command: tuple[str, ...] = Field(min_length=1)
    gold_files: dict[str, str]


def load_manifest(path: Path) -> TaskManifest:
    return TaskManifest.model_validate_json(path.read_text(encoding="utf-8"))


def prepare_fixture(manifest: TaskManifest, target: Path) -> Path:
    if target.exists():
        raise ValueError("fixture target already exists")
    target.mkdir(parents=True)
    _write_declared(target, manifest.setup_files)
    _run_git(target, "init", "-b", "main")
    _run_git(target, "add", ".")
    _run_git(target, "commit", "-m", "initial fixture")
    return target


def apply_gold(repo: Path, files: dict[str, str]) -> None:
    _write_declared(repo, files)


def run_oracle(repo: Path, command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    executable = sys.executable if command[0].casefold() in {"python", "python.exe"} else command[0]
    return subprocess.run(
        [executable, *command[1:]],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def _write_declared(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = resolve_confined(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def _run_git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Coding Agent Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            *args,
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git fixture command failed")
