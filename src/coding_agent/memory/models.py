"""Shared memory value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from coding_agent.agent.actions import JsonValue, ModelUsage


class HistoryEventKind(StrEnum):
    TASK = "task"
    MODEL = "model"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_EDIT = "file_edit"
    COMMAND = "command"
    TEST = "test"
    ERROR = "error"
    DECISION = "decision"


@dataclass(frozen=True)
class HistoryEvent:
    run_id: str
    source_sequence: int
    timestamp: datetime
    kind: HistoryEventKind
    content: str
    correlation_id: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class CondensedSummary:
    summary_id: str
    run_id: str
    revision: int
    covered_from_sequence: int
    covered_through_sequence: int
    content: str
    source_event_count: int
    created_at: datetime
    condenser: str
    usage: ModelUsage | None = None
    fallback_reason: str | None = None
