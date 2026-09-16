import json
import sys

from conftest import finish, tool

from coding_agent.agent.actions import ModelUsage, ToolAction
from coding_agent.agent.state import RunLimits, RunStatus
from coding_agent.models.base import ModelFormatError, ModelResponse


def test_failed_test_becomes_observation_and_can_be_repaired(agent_harness) -> None:
    harness = agent_harness(
        [
            tool("run_command", executable=sys.executable, args=["-m", "pytest", "-q"]),
            tool(
                "edit_file",
                path="calc.py",
                operation="replace",
                expected_text="return a-b",
                new_text="return a+b",
            ),
            tool("run_command", executable=sys.executable, args=["-m", "pytest", "-q"]),
            finish("verified"),
        ]
    )
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    assert any(
        not item.ok and item.tool == "run_command"
        for item in harness.context_manager.working.recent_errors
    )
    assert result.latest_test_result is not None and result.latest_test_result.ok


def test_tool_policy_failure_does_not_crash(agent_harness) -> None:
    harness = agent_harness(
        [tool("run_command", executable="cmd", args=["/c", "del", "*"]), finish("blocked")]
    )
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    assert any(
        item.error_code == "policy_error" for item in harness.context_manager.working.recent_errors
    )


def test_model_format_failure_can_be_corrected(agent_harness) -> None:
    harness = agent_harness([ModelFormatError("bad action"), finish("corrected")])
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    assert any(
        item.error_code == "format_error" for item in harness.context_manager.working.recent_errors
    )


def test_model_format_failure_gives_safe_next_step_feedback(agent_harness) -> None:
    harness = agent_harness(
        [ModelFormatError("provider-secret-payload", reason_code="missing_tool_call"), finish("ok")]
    )
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    second_messages = "\n".join(message.content for message in harness.model.received_messages[1])
    assert "missing_tool_call" in second_messages
    assert "exactly one" in second_messages
    assert "provider-secret-payload" not in second_messages
    assert harness.context_manager.working.recent_errors[-1].data == {
        "reason_code": "missing_tool_call"
    }
    events = [
        json.loads(line) for line in (harness.run_dir / "events.jsonl").read_text().splitlines()
    ]
    rejected = next(
        event for event in events if event["type"] == "ModelStep" and not event["payload"]["ok"]
    )
    assert rejected["payload"]["reason_code"] == "missing_tool_call"
    assert "provider-secret-payload" not in json.dumps(events)


def test_bound_tool_schema_is_not_copied_into_system_prompt(agent_harness) -> None:
    harness = agent_harness([finish("done")])
    harness.runner.run(harness.state)
    system_messages = [
        message.content
        for message in harness.model.received_messages[0]
        if message.role == "system"
    ]
    assert len(system_messages) == 1
    assert "exactly one" in system_messages[0]
    assert '"input_schema"' not in system_messages[0]
    assert '"properties"' not in system_messages[0]
    assert "TOOLS:" not in system_messages[0]


def test_format_error_usage_is_counted_before_next_model_call(agent_harness) -> None:
    error = ModelFormatError(
        "bad response", reason_code="multiple_tool_calls", usage=ModelUsage(input_tokens=6)
    )
    harness = agent_harness([error, finish("should not run")], RunLimits(max_steps=3, max_tokens=5))
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.BUDGET_LIMIT
    assert result.total_tokens == 6
    assert len(harness.model.received_messages) == 1
    events = [
        json.loads(line) for line in (harness.run_dir / "events.jsonl").read_text().splitlines()
    ]
    rejected = next(event for event in events if event["type"] == "ModelStep")
    assert rejected["payload"]["usage"]["input_tokens"] == 6


def test_missing_format_error_usage_is_explicitly_marked(agent_harness) -> None:
    harness = agent_harness([ModelFormatError("bad response"), finish("recovered")])
    assert harness.runner.run(harness.state).status is RunStatus.COMPLETED
    events = [
        json.loads(line) for line in (harness.run_dir / "events.jsonl").read_text().splitlines()
    ]
    rejected = next(event for event in events if event["type"] == "ModelStep")
    assert rejected["payload"]["usage_unavailable"] is True


def test_selected_first_tool_records_ignored_calls_and_guides_next_step(agent_harness) -> None:
    response = ModelResponse(
        action=ToolAction(tool="read_file", arguments={"path": "calc.py"}),
        ignored_tool_calls=1,
        usage=ModelUsage(input_tokens=3),
    )
    harness = agent_harness([response, finish("done")])
    assert harness.runner.run(harness.state).status is RunStatus.COMPLETED
    events = [
        json.loads(line) for line in (harness.run_dir / "events.jsonl").read_text().splitlines()
    ]
    steps = [event for event in events if event["type"] == "ModelStep"]
    calls = [event for event in events if event["type"] == "ToolCalled"]
    assert steps[0]["payload"]["ignored_tool_calls"] == 1
    assert [event["payload"]["tool"] for event in calls] == ["read_file"]
    next_messages = "\n".join(message.content for message in harness.model.received_messages[1])
    assert "Only the first tool call was selected" in next_messages
