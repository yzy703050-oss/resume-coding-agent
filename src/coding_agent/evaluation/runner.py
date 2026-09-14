"""Independent local task evaluation and aggregate metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from coding_agent.cli import build_runner
from coding_agent.config import RunConfig
from coding_agent.evaluation.fixtures import TaskManifest, prepare_fixture, run_oracle
from coding_agent.models.base import ModelClient

type MemoryPreset = Literal[
    "baseline", "processor", "condenser", "repo-map", "project-memory", "full"
]


@dataclass(frozen=True)
class EvaluationResult:
    task_id: str
    task_success: bool
    agent_status: str
    oracle_exit_code: int
    oracle_stdout: str
    oracle_stderr: str
    steps: int
    tool_counts: dict[str, int]
    elapsed_ms: int
    tokens: int | None
    main_tokens: int
    auxiliary_tokens: int
    cost_usd: float | None
    patch_path: Path
    summary_path: Path
    memory_preset: MemoryPreset
    context_metrics: dict[str, object]
    memory_metrics: dict[str, object]


def evaluate_fixture(
    manifest: TaskManifest,
    workspace: Path,
    model_client: ModelClient,
    memory_preset: MemoryPreset = "baseline",
) -> EvaluationResult:
    task_root = workspace / manifest.id
    repo = prepare_fixture(manifest, task_root / "repo")
    built = build_runner(
        RunConfig(
            repository=repo,
            task=manifest.task,
            artifacts_dir=task_root / "artifacts",
            memory_preset=memory_preset,
        ),
        model_client=model_client,
    )
    state = built.runner.run(built.state)
    artifacts = built.runner.artifacts
    if artifacts is None:
        raise RuntimeError("agent completed without artifacts")
    oracle = run_oracle(repo, manifest.oracle_command)
    finished_at = state.finished_at or state.started_at
    elapsed_ms = max(0, int((finished_at - state.started_at).total_seconds() * 1_000))
    return EvaluationResult(
        task_id=manifest.id,
        task_success=state.status.value == "completed" and oracle.returncode == 0,
        agent_status=state.status.value,
        oracle_exit_code=oracle.returncode,
        oracle_stdout=oracle.stdout,
        oracle_stderr=oracle.stderr,
        steps=state.step_count,
        tool_counts=dict(state.tool_counts),
        elapsed_ms=elapsed_ms,
        tokens=state.total_tokens,
        main_tokens=state.usage.total_tokens,
        auxiliary_tokens=state.auxiliary_usage.total_tokens,
        cost_usd=state.total_cost_usd,
        patch_path=artifacts.patch_path,
        summary_path=artifacts.summary_path,
        memory_preset=memory_preset,
        context_metrics=dict(state.context_metrics),
        memory_metrics=dict(state.memory_metrics),
    )


def aggregate_results(results: list[EvaluationResult]) -> dict[str, object]:
    successes = sum(result.task_success for result in results)
    return {
        "tasks": len(results),
        "successes": successes,
        "success_rate": successes / len(results) if results else 0.0,
        "results": [
            {
                "task_id": result.task_id,
                "success": result.task_success,
                "steps": result.steps,
                "tool_counts": result.tool_counts,
                "elapsed_ms": result.elapsed_ms,
                "tokens": result.tokens,
                "main_tokens": result.main_tokens,
                "auxiliary_tokens": result.auxiliary_tokens,
                "cost_usd": result.cost_usd,
                "memory_preset": result.memory_preset,
                "context_metrics": result.context_metrics,
                "memory_metrics": result.memory_metrics,
            }
            for result in results
        ],
    }
