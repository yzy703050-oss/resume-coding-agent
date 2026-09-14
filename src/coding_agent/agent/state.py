"""Explicit in-memory lifecycle state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.agent.actions import JsonValue, ModelUsage, Observation


class RunStatus(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    STEP_LIMIT = "step_limit"
    BUDGET_LIMIT = "budget_limit"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self not in {RunStatus.STARTING, RunStatus.RUNNING}


class RunLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int = Field(default=20, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, gt=0)
    recent_observations: int = Field(default=20, ge=1)


@dataclass
class RunState:
    run_id: str
    repo_root: Path
    task: str
    base_commit: str
    limits: RunLimits
    effective_config: dict[str, JsonValue] = field(default_factory=dict)
    status: RunStatus = RunStatus.STARTING
    step_count: int = 0
    usage: ModelUsage = field(default_factory=ModelUsage)
    auxiliary_usage: ModelUsage = field(default_factory=ModelUsage)
    latest_test_result: Observation | None = None
    tool_counts: dict[str, int] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    termination_reason: str | None = None
    finish_summary: str | None = None
    context_metrics: dict[str, JsonValue] = field(default_factory=dict)
    memory_metrics: dict[str, JsonValue] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.usage.total_tokens + self.auxiliary_usage.total_tokens

    @property
    def total_cost_usd(self) -> float | None:
        usages = (self.usage, self.auxiliary_usage)
        if any(item.total_tokens > 0 and item.cost_usd is None for item in usages):
            return None
        return sum(item.cost_usd or 0.0 for item in usages)

    @classmethod
    def start(
        cls,
        repo_root: Path,
        task: str,
        base_commit: str,
        limits: RunLimits,
        effective_config: dict[str, JsonValue] | None = None,
    ) -> RunState:
        if not repo_root.is_absolute():
            raise ValueError("repository root must be absolute")
        if not task.strip():
            raise ValueError("task must not be empty")
        state = cls(
            run_id=str(uuid4()),
            repo_root=repo_root.resolve(),
            task=task.strip(),
            base_commit=base_commit,
            limits=limits,
            effective_config=dict(effective_config or {}),
        )
        return state

    def _require_mutable(self) -> None:
        if self.status.terminal:
            raise ValueError("terminal run state cannot be mutated")

    def begin_step(self) -> None:
        self._require_mutable()
        if self.step_count >= self.limits.max_steps:
            raise ValueError("step limit reached")
        if self.status is RunStatus.STARTING:
            self.status = RunStatus.RUNNING
        self.step_count += 1

    def add_observation(self, observation: Observation) -> None:
        self._require_mutable()
        self.tool_counts[observation.tool] = self.tool_counts.get(observation.tool, 0) + 1
        if observation.tool == "run_command" and observation.data.get("is_test") is True:
            self.latest_test_result = observation

    def finish(self, status: RunStatus, reason: str) -> None:
        self._require_mutable()
        if not status.terminal:
            raise ValueError("finish requires a terminal status")
        self.status = status
        self.termination_reason = reason
        self.finished_at = datetime.now(UTC)
