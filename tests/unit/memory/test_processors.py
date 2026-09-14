from datetime import UTC, datetime

from coding_agent.memory.models import HistoryEvent, HistoryEventKind
from coding_agent.memory.processors import (
    DeduplicateProcessor,
    HistoryProcessorPipeline,
    HistoryView,
    LargeOutputProcessor,
    RecentObservationProcessor,
)


def event(sequence: int, content: str, correlation: str | None = None) -> HistoryEvent:
    return HistoryEvent(
        "run-1",
        sequence,
        datetime.now(UTC),
        HistoryEventKind.TOOL_RESULT,
        content,
        correlation,
    )


def test_processor_pipeline_is_copy_on_write_and_compacts_large_output() -> None:
    original = HistoryView((event(1, "x" * 50),))
    pipeline = HistoryProcessorPipeline((LargeOutputProcessor(max_chars=12),))

    processed = pipeline.process(original)

    assert original.events[0].content == "x" * 50
    assert processed.events[0].content == "x" * 12 + "...[truncated]"


def test_deduplicate_retains_latest_equivalent_event() -> None:
    view = HistoryView((event(1, "same"), event(2, "different"), event(3, "same")))

    processed = DeduplicateProcessor().process(view)

    assert [item.source_sequence for item in processed.events] == [2, 3]


def test_recent_processor_keeps_complete_correlation_groups() -> None:
    view = HistoryView(
        (
            event(1, "call-1", "group-1"),
            event(2, "result-1", "group-1"),
            event(3, "call-2", "group-2"),
            event(4, "result-2", "group-2"),
        )
    )

    processed = RecentObservationProcessor(max_events=1).process(view)

    assert [item.source_sequence for item in processed.events] == [3, 4]
