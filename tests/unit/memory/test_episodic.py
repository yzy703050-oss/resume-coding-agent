from datetime import UTC, datetime

from coding_agent.memory.episodic import EpisodicMemory
from coding_agent.memory.models import HistoryEvent, HistoryEventKind


def test_episodic_memory_retains_ordered_run_local_history() -> None:
    memory = EpisodicMemory()
    first = HistoryEvent("run-1", 1, datetime.now(UTC), HistoryEventKind.MODEL, "model")
    second = HistoryEvent("run-1", 2, datetime.now(UTC), HistoryEventKind.TOOL_RESULT, "result")

    memory.append(first)
    memory.append(second)

    assert memory.events == (first, second)
