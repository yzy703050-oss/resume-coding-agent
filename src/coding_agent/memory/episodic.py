"""Append-only run-local episodic history and condensed summaries."""

from __future__ import annotations

from coding_agent.memory.models import CondensedSummary, HistoryEvent


class EpisodicMemory:
    def __init__(self) -> None:
        self._events: list[HistoryEvent] = []
        self._summaries: list[CondensedSummary] = []

    @property
    def events(self) -> tuple[HistoryEvent, ...]:
        return tuple(self._events)

    @property
    def summaries(self) -> tuple[CondensedSummary, ...]:
        return tuple(self._summaries)

    def append(self, event: HistoryEvent) -> None:
        if self._events and event.source_sequence <= self._events[-1].source_sequence:
            raise ValueError("history event sequence must increase")
        self._events.append(event)

    def add_summary(self, summary: CondensedSummary) -> None:
        self._summaries.append(summary)
