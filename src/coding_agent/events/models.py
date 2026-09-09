"""Versioned event envelope."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.agent.actions import JsonValue

type EventType = Literal[
    "TaskStarted",
    "ModelStep",
    "ToolCalled",
    "ToolResult",
    "FileEdited",
    "CommandExecuted",
    "TestResult",
    "AgentFinished",
    "AgentFailed",
]


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    type: EventType
    payload: dict[str, JsonValue]
