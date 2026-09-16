"""Fresh-copy patch judging with evaluator-owned tests and sanitized subprocesses."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from coding_agent.evaluation.fixtures import prepare_fixture
from coding_agent.evaluation.suite import LiveTask
from coding_agent.tools.paths import resolve_confined

_SECRET_ENVIRONMENT_KEYS = frozenset({"DEEPSEEK_API_KEY", "OPENAI_API_KEY"})


@dataclass(frozen=True)
class TrustedOracleResult:
    patch_applied: bool
    trusted_oracle_passed: bool
    failure_category: str | None
    oracle_exit_code: int | None
    oracle_stdout: str
    oracle_stderr: str
    judge_repository: Path


def oracle_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a subprocess environment with model-provider credentials removed."""
    source = os.environ if environ is None else environ
    return {
        key: value for key, value in source.items() if key.upper() not in _SECRET_ENVIRONMENT_KEYS
    }


def judge_patch(task: LiveTask, patch: str, workspace: Path) -> TrustedOracleResult:
    """Apply a candidate patch to a fresh fixture and run its trusted oracle."""
    judge_repository = prepare_fixture(task.manifest, workspace / "judge")
    patch_path = workspace / "candidate.patch"
    patch_path.write_text(patch, encoding="utf-8", newline="\n")

    if patch.strip():
        checked = _run_git_apply(judge_repository, patch_path, check_only=True)
        if checked.returncode != 0:
            return _failure(
                judge_repository,
                "patch_apply_failed",
                stdout=checked.stdout,
                stderr=checked.stderr,
            )
        applied = _run_git_apply(judge_repository, patch_path, check_only=False)
        if applied.returncode != 0:
            return _failure(
                judge_repository,
                "patch_apply_failed",
                stdout=applied.stdout,
                stderr=applied.stderr,
            )

    _install_hidden_files(task, judge_repository)
    submitted = _run_pytest(judge_repository)
    if submitted is None:
        return _failure(judge_repository, "oracle_timeout")

    if task.oracle.kind == "pytest":
        if submitted.returncode != 0:
            return _failure(
                judge_repository,
                "hidden_oracle_failed",
                exit_code=submitted.returncode,
                stdout=submitted.stdout,
                stderr=submitted.stderr,
            )
        return _success(judge_repository, submitted)

    if submitted.returncode != 0:
        return _failure(
            judge_repository,
            "submitted_tests_failed",
            exit_code=submitted.returncode,
            stdout=submitted.stdout,
            stderr=submitted.stderr,
        )

    _install_mutations(task, judge_repository)
    mutated = _run_pytest(judge_repository)
    if mutated is None:
        return _failure(judge_repository, "oracle_timeout")
    if mutated.returncode == 0:
        return _failure(
            judge_repository,
            "mutation_survived",
            exit_code=mutated.returncode,
            stdout=mutated.stdout,
            stderr=mutated.stderr,
        )
    return _success(judge_repository, mutated)


def _run_git_apply(
    repository: Path, patch_path: Path, *, check_only: bool
) -> subprocess.CompletedProcess[str]:
    command = ["git", "apply"]
    if check_only:
        command.append("--check")
    command.extend(["--", str(patch_path)])
    return subprocess.run(
        command,
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def _install_hidden_files(task: LiveTask, repository: Path) -> None:
    for relative in task.oracle.hidden_files:
        source = resolve_confined(task.oracle_root, relative)
        destination = resolve_confined(repository, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _install_mutations(task: LiveTask, repository: Path) -> None:
    for relative, content in task.oracle.mutation_files.items():
        destination = resolve_confined(repository, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")


def _run_pytest(repository: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=repository,
            env=oracle_environment(),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return None


def _success(repository: Path, completed: subprocess.CompletedProcess[str]) -> TrustedOracleResult:
    return TrustedOracleResult(
        patch_applied=True,
        trusted_oracle_passed=True,
        failure_category=None,
        oracle_exit_code=completed.returncode,
        oracle_stdout=completed.stdout,
        oracle_stderr=completed.stderr,
        judge_repository=repository,
    )


def _failure(
    repository: Path,
    category: str,
    *,
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
) -> TrustedOracleResult:
    return TrustedOracleResult(
        patch_applied=category != "patch_apply_failed",
        trusted_oracle_passed=False,
        failure_category=category,
        oracle_exit_code=exit_code,
        oracle_stdout=stdout,
        oracle_stderr=stderr,
        judge_repository=repository,
    )
