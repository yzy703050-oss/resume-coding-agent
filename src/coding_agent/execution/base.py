"""Execution protocol and value types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True)
class CommandRequest:
    executable: str
    args: tuple[str, ...]
    cwd: str
    timeout_seconds: float
    output_limit_bytes: int

    def __post_init__(self) -> None:
        if not self.executable:
            raise ValueError("executable must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.output_limit_bytes < 1:
            raise ValueError("output_limit_bytes must be positive")


class CommandStatus(StrEnum):
    EXITED = "exited"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"
    SPAWN_FAILED = "spawn_failed"


@dataclass(frozen=True)
class CommandResult:
    status: CommandStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class ExecutionBackend(Protocol):
    def run(self, request: CommandRequest) -> CommandResult: ...
