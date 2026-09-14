"""Budgeted gateway for model calls that support, but do not drive, a run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from coding_agent.agent.actions import JsonValue, ModelUsage
from coding_agent.context.budget import AuxiliaryBudget


class AuxiliaryModelClient(Protocol):
    def complete_json(self, prompt: str) -> tuple[dict[str, JsonValue], ModelUsage]: ...


class AuxiliaryBudgetExceeded(RuntimeError):
    pass


@dataclass
class RunUsageLedger:
    main: ModelUsage = field(default_factory=ModelUsage)
    auxiliary: ModelUsage = field(default_factory=ModelUsage)

    @property
    def total_tokens(self) -> int:
        return self.main.total_tokens + self.auxiliary.total_tokens

    @property
    def total_cost_usd(self) -> float | None:
        usages = (self.main, self.auxiliary)
        if any(item.total_tokens > 0 and item.cost_usd is None for item in usages):
            return None
        return sum(item.cost_usd or 0.0 for item in usages)


@dataclass
class AuxiliaryModelGateway:
    client: AuxiliaryModelClient
    budget: AuxiliaryBudget
    ledger: RunUsageLedger
    global_max_tokens: int | None = None
    global_max_cost_usd: float | None = None

    def complete_json(
        self,
        component: str,
        prompt: str,
        *,
        estimated_tokens: int,
        estimated_cost_usd: float | None = None,
    ) -> dict[str, JsonValue]:
        if not self.budget.can_start(component, estimated_tokens, estimated_cost_usd):
            raise AuxiliaryBudgetExceeded("auxiliary budget exhausted")
        if (
            self.global_max_tokens is not None
            and self.ledger.total_tokens + estimated_tokens > self.global_max_tokens
        ):
            raise AuxiliaryBudgetExceeded("global token budget exhausted")
        total_cost = self.ledger.total_cost_usd
        if self.global_max_cost_usd is not None:
            if total_cost is None or estimated_cost_usd is None:
                raise AuxiliaryBudgetExceeded("global cost cannot be bounded")
            if total_cost + estimated_cost_usd > self.global_max_cost_usd:
                raise AuxiliaryBudgetExceeded("global cost budget exhausted")

        payload, usage = self.client.complete_json(prompt)
        self.budget.record(component, usage.total_tokens, usage.cost_usd)
        self.ledger.auxiliary.add(usage)
        return payload
