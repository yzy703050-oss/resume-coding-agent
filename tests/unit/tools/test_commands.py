import json
from pathlib import Path

from coding_agent.events.writer import EventWriter
from coding_agent.execution.local import LocalExecutionBackend
from coding_agent.execution.policy import CommandPolicy
from coding_agent.tools.registry import ToolContext, ToolRegistry


def test_failing_pytest_is_result_and_emits_test_event(tmp_path: Path) -> None:
    event_path = tmp_path / "run" / "events.jsonl"
    writer = EventWriter(event_path, "run-1")
    registry = ToolRegistry.create(
        ToolContext(
            repo_root=tmp_path,
            base_commit="HEAD",
            execution_backend=LocalExecutionBackend(tmp_path, CommandPolicy.default()),
            event_writer=writer,
        )
    )
    result = registry.execute(
        "run_command",
        {"executable": "python", "args": ["-m", "pytest", "missing.py", "-q"]},
    )
    writer.close()
    assert not result.ok
    assert result.error_code == "command_failed"
    assert result.data["exit_code"] != 0
    events = [json.loads(line) for line in event_path.read_text().splitlines()]
    assert [event["type"] for event in events] == [
        "ToolCalled",
        "CommandExecuted",
        "TestResult",
        "ToolResult",
    ]


def test_blocked_command_is_policy_result_not_exception(tmp_path: Path) -> None:
    writer = EventWriter(tmp_path / "events.jsonl", "run-1")
    registry = ToolRegistry.create(
        ToolContext(
            repo_root=tmp_path,
            base_commit="HEAD",
            execution_backend=LocalExecutionBackend(tmp_path, CommandPolicy.default()),
            event_writer=writer,
        )
    )
    result = registry.execute("run_command", {"executable": "cmd", "args": ["/c", "del"]})
    writer.close()
    assert (result.ok, result.error_code) == (False, "policy_error")
