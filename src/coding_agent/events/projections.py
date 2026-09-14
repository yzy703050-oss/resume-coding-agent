"""Independent projections from canonical runtime facts."""

from __future__ import annotations

import json
from typing import cast

from coding_agent.agent.actions import JsonValue
from coding_agent.events.models import CanonicalRunEvent, RunEvent
from coding_agent.memory.models import HistoryEvent, HistoryEventKind


def _sanitize(value: JsonValue, secrets: frozenset[str], max_chars: int | None) -> JsonValue:
    if isinstance(value, str):
        result = value
        for secret in secrets:
            result = result.replace(secret, "[REDACTED]")
        if max_chars is not None and len(result) > max_chars:
            return result[:max_chars] + "...[truncated]"
        return result
    if isinstance(value, list):
        return [_sanitize(item, secrets, max_chars) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item, secrets, max_chars) for key, item in value.items()}
    return value


class AuditProjector:
    def __init__(self, secrets: set[str] | None = None, max_string_chars: int = 8_000) -> None:
        self._secrets = frozenset(item for item in (secrets or set()) if item)
        self._max_chars = max_string_chars

    def project(self, event: CanonicalRunEvent) -> RunEvent:
        return RunEvent(
            **event.model_dump(exclude={"payload"}),
            payload=cast(
                dict[str, JsonValue],
                _sanitize(event.payload, self._secrets, self._max_chars),
            ),
        )


_HISTORY_KINDS: dict[str, HistoryEventKind] = {
    "TaskStarted": HistoryEventKind.TASK,
    "ModelStep": HistoryEventKind.MODEL,
    "ToolCalled": HistoryEventKind.TOOL_CALL,
    "ToolResult": HistoryEventKind.TOOL_RESULT,
    "FileEdited": HistoryEventKind.FILE_EDIT,
    "CommandExecuted": HistoryEventKind.COMMAND,
    "TestResult": HistoryEventKind.TEST,
}


class HistoryProjector:
    def __init__(self, secrets: set[str] | None = None) -> None:
        self._secrets = frozenset(item for item in (secrets or set()) if item)

    def project(self, event: CanonicalRunEvent) -> HistoryEvent | None:
        kind = _HISTORY_KINDS.get(event.type)
        if kind is None:
            return None
        payload = _sanitize(event.payload, self._secrets, None)
        return HistoryEvent(
            run_id=event.run_id,
            source_sequence=event.sequence,
            timestamp=event.timestamp,
            kind=kind,
            content=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            correlation_id=event.correlation_id,
        )
