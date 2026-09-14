"""Fixed six-tool registry with schema validation and event emission."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from coding_agent.agent.actions import JsonValue, Observation
from coding_agent.events.sink import EventSink
from coding_agent.execution.base import ExecutionBackend
from coding_agent.tools.commands import run_command
from coding_agent.tools.files import edit_file, list_files, read_file, search_code
from coding_agent.tools.git import GitError, git_diff


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    summary: str
    data: dict[str, JsonValue]
    error_code: str | None = None
    truncated: bool = False

    def to_observation(self, tool: str) -> Observation:
        return Observation(tool=tool, **self.model_dump())


@dataclass(frozen=True)
class ToolContext:
    repo_root: Path
    base_commit: str
    execution_backend: ExecutionBackend
    event_writer: EventSink
    command_timeout_seconds: float = 60


class ListFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = "."
    pattern: str | None = None
    max_results: int = Field(default=200, ge=1, le=2_000)


class SearchCodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)
    path: str = "."
    glob: str | None = None
    max_results: int = Field(default=100, ge=1, le=2_000)


class ReadFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    max_chars: int = Field(default=20_000, ge=1, le=200_000)


class EditFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    operation: Literal["replace", "create"]
    expected_text: str | None = None
    new_text: str


class RunCommandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executable: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    cwd: str = "."
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)
    output_limit_bytes: int = Field(default=100_000, ge=1, le=1_000_000)


class GitDiffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], ToolResult]


class ToolRegistry:
    def __init__(self, context: ToolContext, definitions: tuple[ToolDefinition, ...]) -> None:
        self._context = context
        self._definitions = MappingProxyType({item.name: item for item in definitions})
        self._order = tuple(item.name for item in definitions)

    @classmethod
    def create(cls, context: ToolContext) -> ToolRegistry:
        registry = cls(context, ())
        definitions = (
            ToolDefinition("list_files", "List repository files", ListFilesInput, registry._list),
            ToolDefinition(
                "search_code", "Search repository text", SearchCodeInput, registry._search
            ),
            ToolDefinition("read_file", "Read a UTF-8 file", ReadFileInput, registry._read),
            ToolDefinition(
                "edit_file", "Create or exactly replace text", EditFileInput, registry._edit
            ),
            ToolDefinition(
                "run_command", "Run an allowed command", RunCommandInput, registry._command
            ),
            ToolDefinition("git_diff", "Read the current Git diff", GitDiffInput, registry._diff),
        )
        registry._definitions = MappingProxyType({item.name: item for item in definitions})
        registry._order = tuple(item.name for item in definitions)
        return registry

    def schemas(self) -> list[dict[str, JsonValue]]:
        return [
            {
                "name": name,
                "description": self._definitions[name].description,
                "input_schema": cast(
                    dict[str, JsonValue], self._definitions[name].input_model.model_json_schema()
                ),
            }
            for name in self._order
        ]

    def execute(self, name: str, arguments: dict[str, JsonValue]) -> ToolResult:
        self._context.event_writer.append("ToolCalled", {"tool": name, "arguments": arguments})
        definition = self._definitions.get(name)
        if definition is None:
            result = ToolResult(
                ok=False, summary="unknown tool", data={}, error_code="unknown_tool"
            )
        else:
            try:
                validated = definition.input_model.model_validate(arguments)
            except ValidationError as error:
                result = ToolResult(
                    ok=False,
                    summary="invalid tool arguments",
                    data={"errors": cast(JsonValue, error.errors(include_url=False))},
                    error_code="invalid_arguments",
                )
            else:
                result = definition.handler(validated)
        self._context.event_writer.append(
            "ToolResult", {"tool": name, "result": cast(JsonValue, result.model_dump(mode="json"))}
        )
        return result

    def _list(self, value: BaseModel) -> ToolResult:
        args = cast(ListFilesInput, value)
        return _from_observation(
            list_files(self._context.repo_root, args.path, args.pattern, args.max_results)
        )

    def _search(self, value: BaseModel) -> ToolResult:
        args = cast(SearchCodeInput, value)
        return _from_observation(
            search_code(self._context.repo_root, args.query, args.path, args.glob, args.max_results)
        )

    def _read(self, value: BaseModel) -> ToolResult:
        args = cast(ReadFileInput, value)
        return _from_observation(
            read_file(
                self._context.repo_root,
                args.path,
                args.start_line,
                args.end_line,
                args.max_chars,
            )
        )

    def _edit(self, value: BaseModel) -> ToolResult:
        args = cast(EditFileInput, value)
        result = _from_observation(
            edit_file(
                self._context.repo_root,
                args.path,
                args.operation,
                args.new_text,
                args.expected_text,
            )
        )
        if result.ok:
            self._context.event_writer.append("FileEdited", {"path": result.data["path"]})
        return result

    def _command(self, value: BaseModel) -> ToolResult:
        args = cast(RunCommandInput, value)
        ok, summary, data, error_code, truncated = run_command(
            self._context.execution_backend,
            self._context.event_writer,
            args.executable,
            tuple(args.args),
            args.cwd,
            args.timeout_seconds or self._context.command_timeout_seconds,
            args.output_limit_bytes,
        )
        return ToolResult(
            ok=ok,
            summary=summary,
            data=data,
            error_code=error_code,
            truncated=truncated,
        )

    def _diff(self, value: BaseModel) -> ToolResult:
        del value
        try:
            result = git_diff(self._context.repo_root, self._context.base_commit)
        except GitError as error:
            return ToolResult(ok=False, summary=str(error), data={}, error_code="git_error")
        return ToolResult(
            ok=True,
            summary=f"diff contains {len(result.changed_files)} changed files",
            data={
                "patch": result.patch,
                "changed_files": cast(list[JsonValue], list(result.changed_files)),
            },
        )


def _from_observation(observation: Observation) -> ToolResult:
    return ToolResult(**observation.model_dump(exclude={"tool"}))
