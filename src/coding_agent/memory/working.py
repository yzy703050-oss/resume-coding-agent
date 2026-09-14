"""High-priority, run-local working memory."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass

from coding_agent.agent.actions import Observation


@dataclass(frozen=True)
class PinnedFile:
    path: str
    content: str


class WorkingMemory:
    def __init__(self, pinned_max_chars: int = 12_000, max_recent_errors: int = 5) -> None:
        if pinned_max_chars < 0 or max_recent_errors < 0:
            raise ValueError("working-memory limits cannot be negative")
        self.pinned_max_chars = pinned_max_chars
        self._pinned: OrderedDict[str, PinnedFile] = OrderedDict()
        self._changed: dict[str, None] = {}
        self._recent_errors: deque[Observation] = deque(maxlen=max_recent_errors)
        self.latest_test_result: Observation | None = None
        self.current_plan: str | None = None
        self.current_progress: str | None = None
        self.diff_summary: str | None = None

    @property
    def pinned_files(self) -> tuple[PinnedFile, ...]:
        return tuple(self._pinned.values())

    @property
    def changed_files(self) -> tuple[str, ...]:
        return tuple(self._changed)

    @property
    def recent_errors(self) -> tuple[Observation, ...]:
        return tuple(self._recent_errors)

    def pin_file(self, path: str, content: str) -> None:
        bounded = content[: self.pinned_max_chars]
        self._pinned.pop(path, None)
        self._pinned[path] = PinnedFile(path, bounded)
        while (
            self._pinned
            and sum(len(item.content) for item in self._pinned.values()) > self.pinned_max_chars
        ):
            self._pinned.popitem(last=False)

    def mark_changed(self, path: str) -> None:
        self._changed.setdefault(path, None)

    def record_observation(self, observation: Observation) -> None:
        if observation.tool == "run_command" and observation.data.get("is_test") is True:
            self.latest_test_result = observation
        if not observation.ok:
            self._recent_errors.append(observation)
