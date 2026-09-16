"""History condensation with deterministic degradation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from coding_agent.memory.auxiliary import AuxiliaryBudgetExceeded, AuxiliaryModelGateway
from coding_agent.memory.models import CondensedSummary, HistoryEvent
from coding_agent.memory.processors import HistoryView


@dataclass(frozen=True)
class CondensationResult:
    view: HistoryView
    summary: CondensedSummary | None = None
    fallback_reason: str | None = None


class HistoryCondenser(Protocol):
    def condense(self, view: HistoryView, run_id: str) -> CondensationResult: ...


class NoOpCondenser:
    def condense(self, view: HistoryView, run_id: str) -> CondensationResult:
        del run_id
        return CondensationResult(view)


@dataclass(frozen=True)
class SlidingWindowCondenser:
    keep_recent: int
    max_summary_chars: int = 2000

    def __post_init__(self) -> None:
        if self.keep_recent < 0:
            raise ValueError("keep_recent cannot be negative")
        if self.max_summary_chars < 1:
            raise ValueError("max_summary_chars must be positive")

    def condense(self, view: HistoryView, run_id: str) -> CondensationResult:
        split = _safe_split(view.events, self.keep_recent)
        old, recent = view.events[:split], view.events[split:]
        if not old:
            return CondensationResult(HistoryView(recent))
        # This is bounded evidence, not an LLM-quality semantic summary.
        header = f"Events {old[0].source_sequence}-{old[-1].source_sequence} ({len(old)} total)\n"
        snippets = "\n".join(
            f"{event.source_sequence}:{event.kind}:{event.content[:160]}" for event in old[-8:]
        )
        content = (header + snippets)[: self.max_summary_chars]
        summary = _summary(run_id, old, content, "sliding-window")
        return CondensationResult(HistoryView(recent), summary)


@dataclass
class LLMSummarizingCondenser:
    gateway: AuxiliaryModelGateway
    trigger_events: int
    keep_recent: int
    fallback: SlidingWindowCondenser
    max_calls: int = 2
    minimum_new_events: int = 3
    calls: int = 0
    last_covered_sequence: int = 0

    def condense(self, view: HistoryView, run_id: str) -> CondensationResult:
        if len(view.events) <= self.trigger_events:
            return CondensationResult(view)
        split = _safe_split(view.events, self.keep_recent)
        old, recent = view.events[:split], view.events[split:]
        newly_eligible = sum(event.source_sequence > self.last_covered_sequence for event in old)
        if self.calls >= self.max_calls or newly_eligible < self.minimum_new_events:
            fallback = self.fallback.condense(view, run_id)
            return CondensationResult(fallback.view, fallback.summary, "cooldown")
        prompt = "Summarize these run events as JSON with a summary field:\n" + _render_events(old)
        try:
            payload = self.gateway.complete_json(
                "condenser", prompt, estimated_tokens=max(1, len(prompt) // 4)
            )
        except AuxiliaryBudgetExceeded:
            fallback = self.fallback.condense(view, run_id)
            return CondensationResult(fallback.view, fallback.summary, "auxiliary_budget")
        except Exception:
            fallback = self.fallback.condense(view, run_id)
            return CondensationResult(fallback.view, fallback.summary, "condenser_error")
        content = payload.get("summary")
        if not isinstance(content, str) or not content.strip():
            fallback = self.fallback.condense(view, run_id)
            return CondensationResult(fallback.view, fallback.summary, "invalid_summary")
        self.calls += 1
        self.last_covered_sequence = old[-1].source_sequence
        return CondensationResult(
            HistoryView(recent),
            _summary(run_id, old, content, "llm", revision=self.calls),
        )


def _render_events(events: tuple[HistoryEvent, ...]) -> str:
    return "\n".join(f"{event.source_sequence}:{event.kind}:{event.content}" for event in events)


def _safe_split(events: tuple[HistoryEvent, ...], keep_recent: int) -> int:
    split = max(0, len(events) - keep_recent)
    if split < len(events):
        boundary = events[split].correlation_id
        if boundary is not None:
            while split > 0 and events[split - 1].correlation_id == boundary:
                split -= 1
    return split


def _summary(
    run_id: str,
    events: tuple[HistoryEvent, ...],
    content: str,
    condenser: str,
    revision: int = 1,
) -> CondensedSummary:
    return CondensedSummary(
        summary_id=str(uuid4()),
        run_id=run_id,
        revision=revision,
        covered_from_sequence=events[0].source_sequence,
        covered_through_sequence=events[-1].source_sequence,
        content=content,
        source_event_count=len(events),
        created_at=datetime.now(UTC),
        condenser=condenser,
    )
