"""Immutable executable and argument-prefix allow policy."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from coding_agent.execution.base import CommandRequest


class CommandPolicyError(ValueError):
    pass


_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHELL_MARKERS = (";", "|", "&", ">", "<", "\r", "\n", "`", "$(")


@dataclass(frozen=True)
class CommandPolicy:
    allowed_prefixes: tuple[tuple[str, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        normalized = tuple(
            (str(executable), tuple(args)) for executable, args in self.allowed_prefixes
        )
        object.__setattr__(self, "allowed_prefixes", normalized)

    @classmethod
    def default(cls) -> CommandPolicy:
        return cls((("python", ("-m", "pytest")), ("pytest", ())))

    def check(self, request: CommandRequest) -> None:
        for argument in request.args:
            has_shell_marker = any(marker in argument for marker in _SHELL_MARKERS)
            if has_shell_marker or _ENV_ASSIGNMENT.match(argument):
                raise CommandPolicyError("shell or environment syntax is not allowed")
        for executable, prefix in self.allowed_prefixes:
            if not _matches_executable(request.executable, executable):
                continue
            if request.args[: len(prefix)] == prefix:
                return
        raise CommandPolicyError("command prefix is not allowed")


def _normalize_executable(executable: str) -> str:
    path = Path(executable)
    value = path.stem if path.parent != Path(".") else Path(executable).stem
    return value.casefold()


def _matches_executable(requested: str, allowed: str) -> bool:
    requested_path = Path(requested)
    allowed_path = Path(allowed)
    if requested == requested_path.name:
        return allowed == allowed_path.name and _normalize_executable(
            requested
        ) == _normalize_executable(allowed)
    if allowed_path.parent != Path("."):
        return requested_path.resolve() == allowed_path.resolve()
    return (
        _normalize_executable(allowed) == "python"
        and requested_path.resolve() == Path(sys.executable).resolve()
    )
