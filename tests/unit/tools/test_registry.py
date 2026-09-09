import json
from pathlib import Path

from coding_agent.events.writer import EventWriter
from coding_agent.execution.local import LocalExecutionBackend
from coding_agent.execution.policy import CommandPolicy
from coding_agent.tools.registry import ToolContext, ToolRegistry


def make_registry(tmp_path: Path) -> tuple[ToolRegistry, EventWriter, Path]:
    event_path = tmp_path / "run" / "events.jsonl"
    writer = EventWriter(event_path, "run-1")
    context = ToolContext(
        repo_root=tmp_path,
        base_commit="HEAD",
        execution_backend=LocalExecutionBackend(tmp_path, CommandPolicy.default()),
        event_writer=writer,
    )
    return ToolRegistry.create(context), writer, event_path


def test_registry_exposes_exact_mvp_tools(tmp_path: Path) -> None:
    registry, writer, _ = make_registry(tmp_path)
    assert [schema["name"] for schema in registry.schemas()] == [
        "list_files",
        "search_code",
        "read_file",
        "edit_file",
        "run_command",
        "git_diff",
    ]
    writer.close()


def test_unknown_tool_and_invalid_arguments_are_normalized(tmp_path: Path) -> None:
    registry, writer, _ = make_registry(tmp_path)
    unknown = registry.execute("delete_repository", {})
    invalid = registry.execute("read_file", {"path": "a.py", "start_line": 0})
    assert (unknown.ok, unknown.error_code) == (False, "unknown_tool")
    assert (invalid.ok, invalid.error_code) == (False, "invalid_arguments")
    writer.close()


def test_edit_emits_call_result_and_file_event(tmp_path: Path) -> None:
    registry, writer, event_path = make_registry(tmp_path)
    result = registry.execute(
        "edit_file", {"path": "a.py", "operation": "create", "new_text": "x = 1\n"}
    )
    writer.close()
    assert result.ok
    events = [json.loads(line) for line in event_path.read_text().splitlines()]
    assert [event["type"] for event in events] == ["ToolCalled", "FileEdited", "ToolResult"]
