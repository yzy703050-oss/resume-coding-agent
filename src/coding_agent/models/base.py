"""Synchronous model protocol."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.agent.actions import FinishAction, JsonValue, ModelUsage, ToolAction
from coding_agent.context.builder import Message

type FormatErrorReason = Literal[
    "invalid_action",
    "sdk_parse_error",
    "non_ai_message",
    "invalid_tool_call",
    "missing_tool_call",
    "multiple_tool_calls",
    "invalid_action_arguments",
]

_FORMAT_ERROR_REASONS = frozenset(
    {
        "invalid_action",
        "sdk_parse_error",
        "non_ai_message",
        "invalid_tool_call",
        "missing_tool_call",
        "multiple_tool_calls",
        "invalid_action_arguments",
    }
)


class ModelFormatError(ValueError):
    def __init__(self, message: str, *, reason_code: FormatErrorReason = "invalid_action") -> None:
        super().__init__(message)
        self.reason_code: FormatErrorReason = (
            reason_code if reason_code in _FORMAT_ERROR_REASONS else "invalid_action"
        )


type AgentAction = Annotated[ToolAction | FinishAction, Field(discriminator="kind")]


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AgentAction
    usage: ModelUsage = Field(default_factory=ModelUsage)
    raw_response_id: str | None = None


class ModelClient(Protocol):
    def complete(
        self, messages: list[Message], tool_schemas: list[dict[str, JsonValue]]
    ) -> ModelResponse: ...
