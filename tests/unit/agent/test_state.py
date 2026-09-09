from pathlib import Path

import pytest
from pydantic import ValidationError

from coding_agent.agent.actions import FinishAction, ModelUsage, Observation, ToolAction
from coding_agent.agent.state import RunLimits, RunState, RunStatus


def test_running_state_counts_steps_and_becomes_terminal(tmp_path: Path) -> None:
    state = RunState.start(tmp_path, "fix the bug", "abc123", RunLimits(max_steps=2))
    state.begin_step()
    state.add_observation(Observation(tool="read_file", ok=True, summary="read", data={}))
    state.finish(RunStatus.COMPLETED, "model finished")
    assert state.step_count == 1
    assert state.status is RunStatus.COMPLETED
    with pytest.raises(ValueError, match="terminal"):
        state.begin_step()


def test_next_step_is_rejected_at_limit(tmp_path: Path) -> None:
    state = RunState.start(tmp_path, "fix", "abc123", RunLimits(max_steps=1))
    state.begin_step()
    with pytest.raises(ValueError, match="step limit"):
        state.begin_step()


def test_tool_action_requires_nonempty_tool_and_arguments() -> None:
    action = ToolAction(tool="read_file", arguments={"path": "app.py"})
    assert action.kind == "tool"
    with pytest.raises(ValidationError):
        ToolAction(tool="", arguments={})


def test_finish_and_limits_validate_user_controlled_values() -> None:
    assert FinishAction(summary="done").kind == "finish"
    with pytest.raises(ValidationError):
        FinishAction(summary="")
    with pytest.raises(ValidationError):
        RunLimits(max_steps=0)


def test_usage_accumulates_reported_tokens_and_cost() -> None:
    usage = ModelUsage(input_tokens=3, output_tokens=2, cost_usd=0.01)
    usage.add(ModelUsage(input_tokens=4, output_tokens=1, cost_usd=0.02))
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (7, 3, 10)
    assert usage.cost_usd == pytest.approx(0.03)


def test_usage_accepts_first_reported_cost_from_empty_accumulator() -> None:
    usage = ModelUsage()
    usage.add(ModelUsage(input_tokens=2, cost_usd=0.25))
    assert usage.cost_usd == pytest.approx(0.25)


def test_terminal_state_rejects_observation_mutation(tmp_path: Path) -> None:
    state = RunState.start(tmp_path, "fix", "abc123", RunLimits())
    state.finish(RunStatus.FAILED, "boom")
    with pytest.raises(ValueError, match="terminal"):
        state.add_observation(Observation(tool="model", ok=False, summary="late", data={}))


def test_start_requires_nonempty_task_and_absolute_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="task"):
        RunState.start(tmp_path, " ", "abc123", RunLimits())
    with pytest.raises(ValueError, match="absolute"):
        RunState.start(Path("relative"), "fix", "abc123", RunLimits())
