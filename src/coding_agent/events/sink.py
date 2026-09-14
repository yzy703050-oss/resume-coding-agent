"""Structural event interfaces used by runtime emitters."""

from __future__ import annotations

from typing import Protocol

from coding_agent.agent.actions import JsonValue


class EventSink(Protocol):
    def append(self, event_type: str, payload: dict[str, JsonValue]) -> object: ...
