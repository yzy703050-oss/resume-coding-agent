"""Synchronous, flushed JSONL event writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO, cast

from pydantic import ValidationError

from coding_agent.agent.actions import JsonValue
from coding_agent.events.models import EventType, RunEvent


class EventWriter:
    def __init__(
        self,
        path: Path,
        run_id: str,
        secrets: set[str] | None = None,
        max_string_chars: int = 8_000,
    ) -> None:
        if max_string_chars < 1:
            raise ValueError("max_string_chars must be positive")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.run_id = run_id
        self._secrets = frozenset(secret for secret in (secrets or set()) if secret)
        self._max_string_chars = max_string_chars
        self._sequence = 0
        self._stream: TextIO = path.open("a", encoding="utf-8", newline="\n")
        self._closed = False

    def append(self, event_type: str, payload: dict[str, JsonValue]) -> RunEvent:
        if event_type in {"AgentFinished", "AgentFailed"}:
            raise ValueError("terminal events are owned by Finalizer")
        return self._append_validated(event_type, payload)

    def _append_terminal(self, event_type: str, payload: dict[str, JsonValue]) -> RunEvent:
        if event_type not in {"AgentFinished", "AgentFailed"}:
            raise ValueError("not a terminal event type")
        return self._append_validated(event_type, payload)

    def _append_validated(self, event_type: str, payload: dict[str, JsonValue]) -> RunEvent:
        if self._closed:
            raise ValueError("event writer is closed")
        try:
            event = RunEvent(
                run_id=self.run_id,
                sequence=self._sequence + 1,
                type=cast(EventType, event_type),
                payload=cast(dict[str, JsonValue], self._sanitize(payload)),
            )
        except ValidationError as error:
            raise ValueError("invalid event type or payload") from error
        self._stream.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
        self._stream.flush()
        self._sequence = event.sequence
        return event

    def write(self, event: RunEvent) -> RunEvent:
        """Write an already projected audit event without creating another fact."""
        if self._closed:
            raise ValueError("event writer is closed")
        if event.run_id != self.run_id:
            raise ValueError("event run_id does not match writer")
        if event.sequence != self._sequence + 1:
            raise ValueError("event sequence is not contiguous")
        self._stream.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
        self._stream.flush()
        self._sequence = event.sequence
        return event

    def _sanitize(self, value: JsonValue) -> JsonValue:
        if isinstance(value, str):
            sanitized = value
            for secret in self._secrets:
                sanitized = sanitized.replace(secret, "[REDACTED]")
            if len(sanitized) > self._max_string_chars:
                return sanitized[: self._max_string_chars] + "...[truncated]"
            return sanitized
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        return value

    def close(self) -> None:
        if not self._closed:
            self._stream.close()
            self._closed = True
