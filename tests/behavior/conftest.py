from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from coding_agent.agent.actions import FinishAction, ModelUsage, ToolAction
from coding_agent.agent.runner import AgentRunner
from coding_agent.agent.state import RunLimits, RunState
from coding_agent.context.budget import ContextBudget
from coding_agent.context.builder import ContextBuilder
from coding_agent.context.manager import ContextManager
from coding_agent.context.selector import ContextSelector
from coding_agent.events.artifacts import Finalizer
from coding_agent.events.recorder import RunEventRecorder
from coding_agent.events.writer import EventWriter
from coding_agent.execution.local import LocalExecutionBackend
from coding_agent.execution.policy import CommandPolicy
from coding_agent.memory.episodic import EpisodicMemory
from coding_agent.memory.processors import HistoryProcessorPipeline
from coding_agent.memory.working import WorkingMemory
from coding_agent.models.base import ModelResponse
from coding_agent.models.scripted import ScriptedModelClient
from coding_agent.tools.git import current_head, git_diff
from coding_agent.tools.registry import ToolContext, ToolRegistry


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def tool(name: str, **arguments: object) -> ModelResponse:
    return ModelResponse(action=ToolAction(tool=name, arguments=arguments), usage=ModelUsage())


def finish(summary: str) -> ModelResponse:
    return ModelResponse(action=FinishAction(summary=summary), usage=ModelUsage())


@dataclass
class Harness:
    repo: Path
    run_dir: Path
    state: RunState
    model: ScriptedModelClient
    runner: AgentRunner
    context_manager: ContextManager


@pytest.fixture
def agent_harness(
    tmp_path: Path,
) -> Callable[[list[ModelResponse | BaseException], RunLimits | None], Harness]:
    def create(
        responses: list[ModelResponse | BaseException], limits: RunLimits | None = None
    ) -> Harness:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "calc.py").write_text("def add(a, b):\n    return a-b\n", encoding="utf-8")
        (repo / "test_calc.py").write_text(
            "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        git(repo, "init", "-b", "main")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "initial")
        base = current_head(repo)
        run_dir = tmp_path / "run"
        writer = EventWriter(run_dir / "events.jsonl", "run-1")
        episodic = EpisodicMemory()
        recorder = RunEventRecorder(writer, episodic)
        backend = LocalExecutionBackend(repo, CommandPolicy(((sys.executable, ("-m", "pytest")),)))
        registry = ToolRegistry.create(ToolContext(repo, base, backend, recorder))
        state = RunState.start(repo, "fix add", base, limits or RunLimits(max_steps=10))
        model = ScriptedModelClient(responses)
        finalizer = Finalizer(recorder, lambda: git_diff(repo, base))
        manager = ContextManager(
            ContextBudget(24_000),
            WorkingMemory(),
            episodic,
            ContextSelector(),
            ContextBuilder(),
            HistoryProcessorPipeline(()),
        )
        runner = AgentRunner(model, manager, registry, recorder, finalizer)
        return Harness(repo, run_dir, state, model, runner, manager)

    return create
