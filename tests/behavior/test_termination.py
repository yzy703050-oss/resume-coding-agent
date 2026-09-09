import json

import pytest
from conftest import finish, tool

from coding_agent.agent.actions import ModelUsage, ToolAction
from coding_agent.agent.state import RunLimits, RunStatus
from coding_agent.models.base import ModelResponse


def terminal_events(run_dir):
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    return [event for event in events if event["type"] in {"AgentFinished", "AgentFailed"}]


def test_step_limit_stops_without_extra_model_call(agent_harness) -> None:
    harness = agent_harness([tool("read_file", path="calc.py")], RunLimits(max_steps=1))
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.STEP_LIMIT
    assert len(harness.model.received_messages) == 1
    assert len(terminal_events(harness.run_dir)) == 1
    assert (harness.run_dir / "patch.diff").exists()
    assert (harness.run_dir / "summary.json").exists()


def test_budget_limit_uses_reported_usage(agent_harness) -> None:
    response = ModelResponse(
        action=ToolAction(tool="read_file", arguments={"path": "calc.py"}),
        usage=ModelUsage(input_tokens=6),
    )
    harness = agent_harness([response], RunLimits(max_steps=3, max_tokens=5))
    assert harness.runner.run(harness.state).status is RunStatus.BUDGET_LIMIT
    assert len(terminal_events(harness.run_dir)) == 1


@pytest.mark.parametrize(
    ("failure", "status"),
    [(KeyboardInterrupt(), RunStatus.CANCELLED), (RuntimeError("boom"), RunStatus.FAILED)],
)
def test_interrupt_and_fatal_failure_are_finalized(agent_harness, failure, status) -> None:
    harness = agent_harness([failure])
    assert harness.runner.run(harness.state).status is status
    assert len(terminal_events(harness.run_dir)) == 1
    assert (harness.run_dir / "patch.diff").exists()
    assert (harness.run_dir / "summary.json").exists()


def test_finish_has_exactly_one_finished_event(agent_harness) -> None:
    harness = agent_harness([finish("done")])
    assert harness.runner.run(harness.state).status is RunStatus.COMPLETED
    assert [event["type"] for event in terminal_events(harness.run_dir)] == ["AgentFinished"]
