"""Values produced by the Python repository scanner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoSymbol:
    path: str
    kind: str
    name: str
    signature: str = ""
    parent: str | None = None
    line: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.parent}.{self.name}" if self.parent else self.name

    @property
    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.path, self.line, self.kind, self.qualified_name)

    def render(self) -> str:
        suffix = self.signature if self.signature else ""
        return f"{self.path}: {self.kind} {self.qualified_name}{suffix}"


@dataclass(frozen=True)
class RepoMapDiagnostic:
    path: str
    message: str
