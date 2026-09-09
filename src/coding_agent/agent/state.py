"""Explicit in-memory lifecycle state."""

from __future__ import annotations

from collections import OrderedDict, deque
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


@dataclass(frozen=True)
class ContextItem:
    path: str
    content: str


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
    recent_observations: deque[Observation] = field(default_factory=deque)
    pinned_context: OrderedDict[str, ContextItem] = field(default_factory=OrderedDict)
    latest_test_result: Observation | None = None
    changed_files: list[str] = field(default_factory=list)
    tool_counts: dict[str, int] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    termination_reason: str | None = None
    finish_summary: str | None = None

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
        state.recent_observations = deque(maxlen=limits.recent_observations)
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
        self.recent_observations.append(observation)
        self.tool_counts[observation.tool] = self.tool_counts.get(observation.tool, 0) + 1
        if observation.tool == "run_command" and observation.data.get("is_test") is True:
            self.latest_test_result = observation

    def pin_file(self, path: str, content: str) -> None:
        self._require_mutable()
        self.pinned_context.pop(path, None)
        self.pinned_context[path] = ContextItem(path=path, content=content)

    def mark_changed(self, path: str) -> None:
        self._require_mutable()
        if path not in self.changed_files:
            self.changed_files.append(path)

    def finish(self, status: RunStatus, reason: str) -> None:
        self._require_mutable()
        if not status.terminal:
            raise ValueError("finish requires a terminal status")
        self.status = status
        self.termination_reason = reason
        self.finished_at = datetime.now(UTC)
