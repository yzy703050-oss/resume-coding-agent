import json
import sys

from conftest import finish, tool

from coding_agent.agent.state import RunStatus
from coding_agent.models.base import ModelFormatError


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
