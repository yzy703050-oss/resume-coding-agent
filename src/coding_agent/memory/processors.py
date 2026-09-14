"""Copy-on-write projections over canonical episodic history."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from coding_agent.memory.models import HistoryEvent


@dataclass(frozen=True)
class HistoryView:
    events: tuple[HistoryEvent, ...]


class HistoryProcessor(Protocol):
    def process(self, view: HistoryView) -> HistoryView: ...


@dataclass(frozen=True)
class HistoryProcessorPipeline:
    processors: tuple[HistoryProcessor, ...]

    def process(self, view: HistoryView) -> HistoryView:
        result = view
        for processor in self.processors:
            result = processor.process(result)
        return result


@dataclass(frozen=True)
class LargeOutputProcessor:
    max_chars: int

    def __post_init__(self) -> None:
        if self.max_chars < 0:
            raise ValueError("max_chars cannot be negative")

    def process(self, view: HistoryView) -> HistoryView:
        events = tuple(
            replace(event, content=event.content[: self.max_chars] + "...[truncated]")
            if len(event.content) > self.max_chars
            else event
            for event in view.events
        )
        return HistoryView(events)


class DeduplicateProcessor:
    """Keep the latest event having the same semantic payload."""

    def process(self, view: HistoryView) -> HistoryView:
        seen: set[tuple[object, ...]] = set()
        retained: list[HistoryEvent] = []
        for event in reversed(view.events):
            key = (event.kind, event.content, repr(sorted(event.metadata.items())))
            if key not in seen:
                seen.add(key)
                retained.append(event)
        retained.reverse()
        return HistoryView(tuple(retained))


@dataclass(frozen=True)
class RecentObservationProcessor:
    max_events: int

    def __post_init__(self) -> None:
        if self.max_events < 0:
            raise ValueError("max_events cannot be negative")

    def process(self, view: HistoryView) -> HistoryView:
        if self.max_events == 0 or not view.events:
            return HistoryView(())
        start = max(0, len(view.events) - self.max_events)
        boundary = view.events[start].correlation_id
        if boundary is not None:
            while start > 0 and view.events[start - 1].correlation_id == boundary:
                start -= 1
        return HistoryView(view.events[start:])
