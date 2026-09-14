import pytest

from coding_agent.context.budget import AuxiliaryBudget, ContextBudget
from coding_agent.context.items import ContextSection


def test_context_budget_reserves_response_and_fixed_overhead() -> None:
    budget = ContextBudget(
        total_size=1_000,
        response_reserve=200,
        fixed_overhead=100,
        section_caps={ContextSection.RECENT_HISTORY: 300},
    )

    assert budget.input_capacity == 700
    assert budget.cap_for(ContextSection.RECENT_HISTORY) == 300

    with pytest.raises(ValueError, match="mandatory context"):
        budget.require_mandatory_fits(701)


def test_context_budget_uses_remaining_capacity_for_uncapped_sections() -> None:
    budget = ContextBudget(total_size=500, response_reserve=100, fixed_overhead=50)

    assert budget.cap_for(ContextSection.WORKING_MEMORY) == 350
    assert budget.remaining_after(125) == 225


def test_auxiliary_budget_enforces_total_and_component_call_limits() -> None:
    budget = AuxiliaryBudget(
        max_calls=2,
        max_tokens=50,
        max_cost_usd=1.0,
        component_call_limits={"condenser": 1},
    )

    assert budget.can_start("condenser", estimated_tokens=20, estimated_cost_usd=0.25)
    budget.record("condenser", tokens=20, cost_usd=0.25)
    assert not budget.can_start("condenser", estimated_tokens=1, estimated_cost_usd=0.01)
    assert budget.can_start("candidate_extractor", estimated_tokens=30, estimated_cost_usd=0.75)
    budget.record("candidate_extractor", tokens=30, cost_usd=0.75)
    assert not budget.can_start("candidate_extractor", estimated_tokens=1, estimated_cost_usd=0.01)
