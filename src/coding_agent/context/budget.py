"""Replaceable size estimation and explicit context/auxiliary budgets."""

from __future__ import annotations

from dataclasses import dataclass, field

from coding_agent.context.items import ContextSection


class CharacterEstimator:
    def estimate(self, value: str) -> int:
        return len(value)


@dataclass(frozen=True)
class ContextBudget:
    total_size: int
    response_reserve: int = 0
    fixed_overhead: int = 0
    section_caps: dict[ContextSection, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_size < 1:
            raise ValueError("total_size must be positive")
        if self.response_reserve < 0 or self.fixed_overhead < 0:
            raise ValueError("budget reserves cannot be negative")
        if self.response_reserve + self.fixed_overhead >= self.total_size:
            raise ValueError("budget reserves leave no input capacity")
        if any(value < 0 for value in self.section_caps.values()):
            raise ValueError("section caps cannot be negative")

    @property
    def input_capacity(self) -> int:
        return self.total_size - self.response_reserve - self.fixed_overhead

    def cap_for(self, section: ContextSection) -> int:
        return min(self.input_capacity, self.section_caps.get(section, self.input_capacity))

    def require_mandatory_fits(self, estimated_size: int) -> None:
        if estimated_size > self.input_capacity:
            raise ValueError("mandatory context exceeds input capacity")

    def remaining_after(self, used: int) -> int:
        return max(0, self.input_capacity - used)


@dataclass
class AuxiliaryBudget:
    max_calls: int
    max_tokens: int
    max_cost_usd: float | None = None
    component_call_limits: dict[str, int] = field(default_factory=dict)
    calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    component_calls: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_calls < 0 or self.max_tokens < 0:
            raise ValueError("auxiliary limits cannot be negative")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("auxiliary cost limit cannot be negative")

    def can_start(
        self, component: str, estimated_tokens: int, estimated_cost_usd: float | None
    ) -> bool:
        if self.calls >= self.max_calls or self.tokens + estimated_tokens > self.max_tokens:
            return False
        component_limit = self.component_call_limits.get(component, self.max_calls)
        if self.component_calls.get(component, 0) >= component_limit:
            return False
        if self.max_cost_usd is not None:
            if estimated_cost_usd is None:
                return False
            if self.cost_usd + estimated_cost_usd > self.max_cost_usd:
                return False
        return True

    def record(self, component: str, tokens: int, cost_usd: float | None) -> None:
        self.calls += 1
        self.tokens += tokens
        if cost_usd is not None:
            self.cost_usd += cost_usd
        self.component_calls[component] = self.component_calls.get(component, 0) + 1
