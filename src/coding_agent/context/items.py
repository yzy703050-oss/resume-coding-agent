"""Typed inputs and outputs for context selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from coding_agent.agent.actions import JsonValue


class ContextSection(StrEnum):
    MANDATORY = "mandatory"
    WORKING_MEMORY = "working_memory"
    PINNED_CODE = "pinned_code"
    REPO_MAP = "repo_map"
    RECENT_HISTORY = "recent_history"
    COMPRESSED_HISTORY = "compressed_history"
    PERSISTENT_MEMORY = "persistent_memory"


class ContextPriority(StrEnum):
    MANDATORY = "mandatory"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    section: ContextSection
    content: str
    priority: ContextPriority = ContextPriority.NORMAL
    estimated_size: int = 0
    source: str = ""
    relevance: float = 0.0
    importance: float = 0.0
    recency: float = 0.0
    atomic_group: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedContext:
    items: tuple[ContextItem, ...]
    estimated_size: int
    omitted_by_section: dict[ContextSection, int] = field(default_factory=dict)
