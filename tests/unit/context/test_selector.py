from coding_agent.context.budget import ContextBudget
from coding_agent.context.items import (
    ContextItem,
    ContextPriority,
    ContextSection,
)
from coding_agent.context.selector import ContextSelector


def item(
    name: str,
    section: ContextSection,
    size: int,
    priority: ContextPriority = ContextPriority.NORMAL,
    group: str | None = None,
) -> ContextItem:
    return ContextItem(name, section, name * size, priority, size, "test", atomic_group=group)


def test_selector_keeps_mandatory_and_respects_caps_and_atomic_groups() -> None:
    budget = ContextBudget(
        total_size=20,
        section_caps={ContextSection.RECENT_HISTORY: 7},
    )
    candidates = (
        item("task", ContextSection.MANDATORY, 5, ContextPriority.MANDATORY),
        item("a", ContextSection.RECENT_HISTORY, 4, group="pair"),
        item("b", ContextSection.RECENT_HISTORY, 4, group="pair"),
        item("pin", ContextSection.PINNED_CODE, 10, ContextPriority.HIGH),
    )

    prepared = ContextSelector().select(candidates, budget)

    assert [value.item_id for value in prepared.items] == ["task", "pin"]
    assert prepared.estimated_size == 15
    assert prepared.omitted_by_section[ContextSection.RECENT_HISTORY] == 2


def test_selector_rejects_mandatory_context_that_cannot_fit() -> None:
    candidate = item("task", ContextSection.MANDATORY, 11, ContextPriority.MANDATORY)
    try:
        ContextSelector().select((candidate,), ContextBudget(total_size=10))
    except ValueError as error:
        assert "mandatory" in str(error)
    else:
        raise AssertionError("mandatory overflow must fail")
