from collections import deque
from datetime import UTC, datetime

from coding_agent.agent.actions import ModelUsage
from coding_agent.context.budget import AuxiliaryBudget
from coding_agent.memory.auxiliary import AuxiliaryModelGateway, RunUsageLedger
from coding_agent.memory.condenser import LLMSummarizingCondenser, SlidingWindowCondenser
from coding_agent.memory.models import HistoryEvent, HistoryEventKind
from coding_agent.memory.processors import HistoryView


class ScriptedAuxiliaryClient:
    def __init__(self, responses: list[tuple[dict[str, object], ModelUsage] | BaseException]):
        self.responses = deque(responses)
        self.calls = 0

    def complete_json(self, prompt: str) -> tuple[dict[str, object], ModelUsage]:
        del prompt
        self.calls += 1
        response = self.responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response


def view(count: int) -> HistoryView:
    return HistoryView(
        tuple(
            HistoryEvent(
                "run-1",
                number,
                datetime.now(UTC),
                HistoryEventKind.TOOL_RESULT,
                f"event-{number}",
                f"group-{number}",
            )
            for number in range(1, count + 1)
        )
    )


def test_auxiliary_gateway_charges_auxiliary_and_combined_usage() -> None:
    client = ScriptedAuxiliaryClient([({"summary": "old work"}, ModelUsage(input_tokens=7))])
    ledger = RunUsageLedger(main=ModelUsage(input_tokens=3))
    gateway = AuxiliaryModelGateway(
        client,
        AuxiliaryBudget(max_calls=1, max_tokens=10),
        ledger,
        global_max_tokens=12,
    )

    payload = gateway.complete_json("condenser", "summarize", estimated_tokens=5)

    assert payload == {"summary": "old work"}
    assert ledger.auxiliary.total_tokens == 7
    assert ledger.total_tokens == 10


def test_llm_condenser_uses_sliding_fallback_when_auxiliary_budget_denies_call() -> None:
    client = ScriptedAuxiliaryClient([])
    gateway = AuxiliaryModelGateway(
        client,
        AuxiliaryBudget(max_calls=0, max_tokens=0),
        RunUsageLedger(),
        global_max_tokens=100,
    )
    condenser = LLMSummarizingCondenser(
        gateway=gateway,
        trigger_events=3,
        keep_recent=2,
        fallback=SlidingWindowCondenser(keep_recent=2),
    )

    result = condenser.condense(view(5), "run-1")

    assert client.calls == 0
    assert result.fallback_reason == "auxiliary_budget"
    assert [item.source_sequence for item in result.view.events] == [4, 5]
    assert result.summary is not None
    assert result.summary.covered_through_sequence == 3


def test_llm_condenser_enforces_cooldown_for_unchanged_prefix() -> None:
    client = ScriptedAuxiliaryClient([({"summary": "old work"}, ModelUsage(input_tokens=1))])
    condenser = LLMSummarizingCondenser(
        AuxiliaryModelGateway(client, AuxiliaryBudget(2, 100), RunUsageLedger()),
        trigger_events=3,
        keep_recent=2,
        fallback=SlidingWindowCondenser(2),
    )
    first = condenser.condense(view(5), "run-1")
    second = condenser.condense(view(5), "run-1")

    assert first.summary is not None and first.summary.revision == 1
    assert second.fallback_reason == "cooldown"
    assert client.calls == 1


def test_sliding_summary_is_bounded_without_truncating_recent_events() -> None:
    result = SlidingWindowCondenser(keep_recent=2, max_summary_chars=80).condense(
        view(100), "run-1"
    )
    assert result.summary is not None
    assert len(result.summary.content) <= 80
    assert result.summary.source_event_count == 98
    assert [event.source_sequence for event in result.view.events] == [99, 100]
