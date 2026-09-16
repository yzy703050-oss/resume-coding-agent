"""Explicitly gated live DeepSeek evaluation over the frozen resume suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, SecretStr

from coding_agent.agent.state import RunStatus
from coding_agent.cli import build_runner
from coding_agent.config import RunConfig
from coding_agent.evaluation.environment import load_deepseek_key
from coding_agent.evaluation.fixtures import prepare_fixture
from coding_agent.evaluation.suite import LiveSuite, LiveTask, load_live_suite
from coding_agent.evaluation.trusted_oracle import judge_patch
from coding_agent.models.base import ModelClient
from coding_agent.models.langchain_client import create_langchain_model
from coding_agent.models.openai_compatible import ModelTransportError

LIVE_LIMITS: dict[str, str | int | bool] = {
    "max_steps": 8,
    "max_output_tokens": 512,
    "max_tokens": 8000,
    "memory_preset": "baseline",
    "auxiliary_max_calls": 0,
    "auxiliary_max_tokens": 0,
    "repeats": 1,
    "thinking_enabled": False,
}

ModelFactory = Callable[[RunConfig], ModelClient]


class LiveTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    protocol_completed: bool
    patch_applied: bool
    trusted_oracle_passed: bool
    task_success: bool
    agent_status: str
    termination_reason: str | None
    failure_category: str | None
    visible_test_result: bool | None
    steps: int
    tool_counts: dict[str, int]
    elapsed_ms: int
    input_tokens: int
    output_tokens: int
    auxiliary_tokens: int
    cost_usd: None = None
    patch_sha256: str
    artifact_directory: str


class LiveEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    evaluation_kind: Literal["live_model_microtask_suite"]
    evaluator_version: Literal["resume-v1.0"]
    suite_name: str
    sample_size: int
    manifest_sha256: str
    provider: Literal["deepseek"]
    model: Literal["deepseek-flash"]
    limits: dict[str, str | int | bool]
    started_at: datetime
    finished_at: datetime
    attempted_tasks: int
    successes: int
    stopped_early: bool
    stop_reason: str | None
    input_tokens: int
    output_tokens: int
    auxiliary_tokens: int
    cost_usd: None = None
    results: tuple[LiveTaskResult, ...]


class TaskExecutor(Protocol):
    def __call__(
        self,
        task: LiveTask,
        workspace: Path,
        key: SecretStr,
        model_factory: ModelFactory,
    ) -> LiveTaskResult: ...


def run_live_suite(
    project_root: Path,
    suite: LiveSuite,
    workspace: Path,
    key: SecretStr,
    model_factory: ModelFactory = create_langchain_model,
    task_executor: TaskExecutor | None = None,
) -> LiveEvaluationReport:
    """Run each frozen task once, stopping only on infrastructure failure."""
    project_root.resolve(strict=True)
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    execute = task_executor or _execute_task
    started_at = datetime.now(UTC)
    results: list[LiveTaskResult] = []
    attempted_tasks = 0
    stop_reason: str | None = None

    for index, task in enumerate(suite.tasks):
        attempted_tasks += 1
        try:
            result = execute(task, workspace / task.manifest.id, key, model_factory)
        except Exception:
            stop_reason = (
                "canary_infrastructure_failure" if index == 0 else "infrastructure_failure"
            )
            break
        results.append(result)

    finished_at = datetime.now(UTC)
    return LiveEvaluationReport(
        schema_version="1",
        evaluation_kind="live_model_microtask_suite",
        evaluator_version="resume-v1.0",
        suite_name=suite.name,
        sample_size=len(suite.tasks),
        manifest_sha256=_manifest_hash(suite),
        provider="deepseek",
        model="deepseek-flash",
        limits=dict(LIVE_LIMITS),
        started_at=started_at,
        finished_at=finished_at,
        attempted_tasks=attempted_tasks,
        successes=sum(item.task_success for item in results),
        stopped_early=stop_reason is not None,
        stop_reason=stop_reason,
        input_tokens=sum(item.input_tokens for item in results),
        output_tokens=sum(item.output_tokens for item in results),
        auxiliary_tokens=sum(item.auxiliary_tokens for item in results),
        cost_usd=None,
        results=tuple(results),
    )


def _execute_task(
    task: LiveTask,
    workspace: Path,
    key: SecretStr,
    model_factory: ModelFactory,
) -> LiveTaskResult:
    repository = prepare_fixture(task.manifest, workspace / "agent")
    config = RunConfig(
        repository=repository,
        task=task.manifest.task,
        provider="deepseek",
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        api_key=key,
        max_output_tokens=512,
        thinking_enabled=False,
        max_steps=8,
        max_tokens=8000,
        memory_preset="baseline",
        auxiliary_max_calls=0,
        auxiliary_max_tokens=0,
        artifacts_dir=workspace / "artifacts",
    )
    built = build_runner(config, model_client=model_factory(config))
    state = built.runner.run(built.state)
    if state.termination_reason == "unexpected ModelTransportError":
        raise ModelTransportError("live model transport failed")
    artifacts = built.runner.artifacts
    if artifacts is None:
        raise RuntimeError("agent completed without artifacts")

    patch = artifacts.patch_path.read_text(encoding="utf-8")
    oracle = judge_patch(task, patch, workspace / "evaluation")
    protocol_completed = state.status is RunStatus.COMPLETED
    success = protocol_completed and oracle.patch_applied and oracle.trusted_oracle_passed
    finished_at = state.finished_at or state.started_at
    elapsed_ms = max(0, int((finished_at - state.started_at).total_seconds() * 1_000))
    failure_category = oracle.failure_category
    if not protocol_completed and failure_category is None:
        failure_category = "agent_protocol_failed"

    return LiveTaskResult(
        task_id=task.manifest.id,
        protocol_completed=protocol_completed,
        patch_applied=oracle.patch_applied,
        trusted_oracle_passed=oracle.trusted_oracle_passed,
        task_success=success,
        agent_status=state.status.value,
        termination_reason=state.termination_reason,
        failure_category=failure_category,
        visible_test_result=(
            state.latest_test_result.ok if state.latest_test_result is not None else None
        ),
        steps=state.step_count,
        tool_counts=dict(state.tool_counts),
        elapsed_ms=elapsed_ms,
        input_tokens=state.usage.input_tokens,
        output_tokens=state.usage.output_tokens,
        auxiliary_tokens=state.auxiliary_usage.total_tokens,
        cost_usd=None,
        patch_sha256=hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        artifact_directory=str(artifacts.patch_path.parent),
    )


def _manifest_hash(suite: LiveSuite) -> str:
    payload = [
        {
            "manifest": task.manifest.model_dump(mode="json"),
            "oracle": task.oracle.model_dump(mode="json"),
        }
        for task in suite.tasks
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--suite", default="resume-v1")
    parser.add_argument("--workspace", type=Path, default=Path("runs/live-deepseek-resume-v1"))
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/deepseek-live-resume-v1.json")
    )
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.confirm_paid_run:
        print("Error: --confirm-paid-run is required", file=sys.stderr)
        return 2
    if args.suite != "resume-v1":
        print("Error: only the frozen resume-v1 suite is supported", file=sys.stderr)
        return 2

    try:
        project_root = args.project_root.resolve(strict=True)
        key = load_deepseek_key(project_root)
        suite = load_live_suite(
            project_root / "tests" / "fixtures" / "live_tasks" / "resume-v1",
            project_root / "tests" / "fixtures" / "hidden_oracles" / "resume-v1",
        )
        workspace = _under_project(project_root, args.workspace)
        output = _under_project(project_root, args.output)
        report = run_live_suite(project_root, suite, workspace, key)
        _write_report(output, report)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {type(error).__name__}", file=sys.stderr)
        return 2

    for result in report.results:
        print(
            f"{result.task_id}: {'passed' if result.task_success else 'failed'} "
            f"tokens={result.input_tokens + result.output_tokens + result.auxiliary_tokens} "
            f"artifacts={result.artifact_directory}"
        )
    print(
        f"summary: attempted={report.attempted_tasks} successes={report.successes} "
        f"tokens={report.input_tokens + report.output_tokens + report.auxiliary_tokens}"
    )
    print(f"report={output}")
    return 0 if not report.stopped_early else 1


def _under_project(project_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _write_report(output: Path, report: LiveEvaluationReport) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)


if __name__ == "__main__":
    raise SystemExit(main())
