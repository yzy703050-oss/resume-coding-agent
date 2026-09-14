"""Canonical event creation with independent history and audit projections."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from coding_agent.agent.actions import JsonValue
from coding_agent.events.models import CanonicalRunEvent, EventType
from coding_agent.events.projections import AuditProjector, HistoryProjector
from coding_agent.events.writer import EventWriter
from coding_agent.memory.episodic import EpisodicMemory


class RunEventRecorder:
    def __init__(
        self,
        writer: EventWriter,
        episodic_memory: EpisodicMemory | None = None,
        secrets: set[str] | None = None,
        audit_max_string_chars: int = 8_000,
    ) -> None:
        self._writer = writer
        self._history = episodic_memory
        self._audit_projector = AuditProjector(secrets, audit_max_string_chars)
        self._history_projector = HistoryProjector(secrets)
        self._sequence = 0
        self._correlation_id: str | None = None

    @property
    def path(self) -> Path:
        return self._writer.path

    @contextmanager
    def correlate(self, correlation_id: str) -> Iterator[None]:
        previous = self._correlation_id
        self._correlation_id = correlation_id
        try:
            yield
        finally:
            self._correlation_id = previous

    def append(self, event_type: str, payload: dict[str, JsonValue]) -> CanonicalRunEvent:
        if event_type in {"AgentFinished", "AgentFailed"}:
            raise ValueError("terminal events are owned by Finalizer")
        return self._record(event_type, payload)

    def _append_terminal(self, event_type: str, payload: dict[str, JsonValue]) -> CanonicalRunEvent:
        if event_type not in {"AgentFinished", "AgentFailed"}:
            raise ValueError("not a terminal event type")
        return self._record(event_type, payload)

    def _record(self, event_type: str, payload: dict[str, JsonValue]) -> CanonicalRunEvent:
        try:
            event = CanonicalRunEvent(
                run_id=self._writer.run_id,
                sequence=self._sequence + 1,
                type=cast(EventType, event_type),
                payload=payload,
                correlation_id=self._correlation_id,
            )
        except ValidationError as error:
            raise ValueError("invalid event type or payload") from error
        history = self._history_projector.project(event)
        if history is not None and self._history is not None:
            self._history.append(history)
        self._writer.write(self._audit_projector.project(event))
        self._sequence = event.sequence
        return event

    def close(self) -> None:
        self._writer.close()
