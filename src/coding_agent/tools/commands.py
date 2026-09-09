"""Adapter from command execution values to tool results."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from coding_agent.agent.actions import JsonValue
from coding_agent.events.writer import EventWriter
from coding_agent.execution.base import CommandRequest, CommandStatus, ExecutionBackend


def run_command(
    backend: ExecutionBackend,
    event_writer: EventWriter,
    executable: str,
    args: tuple[str, ...],
    cwd: str,
    timeout_seconds: float,
    output_limit_bytes: int,
) -> tuple[bool, str, dict[str, JsonValue], str | None, bool]:
    request = CommandRequest(executable, args, cwd, timeout_seconds, output_limit_bytes)
    result = backend.run(request)
    is_test = _is_test_command(executable, args)
    data: dict[str, JsonValue] = {
        "status": result.status.value,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        "is_test": is_test,
    }
    event_payload: dict[str, JsonValue] = {
        "executable": Path(executable).name,
        "args": cast(list[JsonValue], list(args)),
        "cwd": cwd,
        "result": data,
    }
    event_writer.append("CommandExecuted", event_payload)
    if is_test:
        event_writer.append("TestResult", data)
    if result.status is CommandStatus.BLOCKED:
        return False, "command blocked by policy", data, "policy_error", False
    if result.status is CommandStatus.TIMED_OUT:
        return False, "command timed out", data, "timeout", True
    if result.status is CommandStatus.SPAWN_FAILED:
        return False, "command could not start", data, "spawn_error", False
    if result.exit_code != 0:
        return False, f"command exited with {result.exit_code}", data, "command_failed", False
    return True, "command completed", data, None, False


def _is_test_command(executable: str, args: tuple[str, ...]) -> bool:
    name = Path(executable).stem.casefold()
    return name == "pytest" or (name in {"python", "python3"} and args[:2] == ("-m", "pytest"))
