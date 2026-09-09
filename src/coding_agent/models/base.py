"""Synchronous model protocol."""

from __future__ import annotations

from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.agent.actions import FinishAction, JsonValue, ModelUsage, ToolAction
from coding_agent.context.builder import Message

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
