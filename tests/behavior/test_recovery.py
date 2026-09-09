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
    assert any(not item.ok and item.tool == "run_command" for item in result.recent_observations)
    assert result.latest_test_result is not None and result.latest_test_result.ok


def test_tool_policy_failure_does_not_crash(agent_harness) -> None:
    harness = agent_harness(
        [tool("run_command", executable="cmd", args=["/c", "del", "*"]), finish("blocked")]
    )
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    assert any(item.error_code == "policy_error" for item in result.recent_observations)


def test_model_format_failure_can_be_corrected(agent_harness) -> None:
    harness = agent_harness([ModelFormatError("bad action"), finish("corrected")])
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    assert any(item.error_code == "format_error" for item in result.recent_observations)
