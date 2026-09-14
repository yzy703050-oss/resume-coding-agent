"""Deterministic policy for selecting typed context candidates."""

from __future__ import annotations

from collections import defaultdict

from coding_agent.context.budget import ContextBudget
from coding_agent.context.items import ContextItem, ContextPriority, ContextSection, PreparedContext

_PRIORITY = {
    ContextPriority.MANDATORY: 3,
    ContextPriority.HIGH: 2,
    ContextPriority.NORMAL: 1,
    ContextPriority.LOW: 0,
}


class ContextSelector:
    def select(self, candidates: tuple[ContextItem, ...], budget: ContextBudget) -> PreparedContext:
        mandatory = tuple(
            item
            for item in candidates
            if item.priority is ContextPriority.MANDATORY
            or item.section is ContextSection.MANDATORY
        )
        mandatory_size = sum(item.estimated_size for item in mandatory)
        budget.require_mandatory_fits(mandatory_size)
        selected_ids = {id(item) for item in mandatory}
        used = mandatory_size
        section_used: dict[ContextSection, int] = defaultdict(int)
        for item in mandatory:
            section_used[item.section] += item.estimated_size

        groups: dict[str, list[ContextItem]] = {}
        for index, item in enumerate(candidates):
            if id(item) in selected_ids:
                continue
            key = item.atomic_group or f"__item_{index}"
            groups.setdefault(key, []).append(item)

        def rank(group: list[ContextItem]) -> tuple[float, float, float, float, str]:
            best = max(
                group,
                key=lambda item: (
                    _PRIORITY[item.priority],
                    item.relevance,
                    item.importance,
                    item.recency,
                ),
            )
            return (
                -_PRIORITY[best.priority],
                -best.relevance,
                -best.importance,
                -best.recency,
                best.item_id,
            )

        for group in sorted(groups.values(), key=rank):
            group_size = sum(item.estimated_size for item in group)
            per_section: dict[ContextSection, int] = defaultdict(int)
            for item in group:
                per_section[item.section] += item.estimated_size
            if used + group_size > budget.input_capacity:
                continue
            if any(
                section_used[section] + size > budget.cap_for(section)
                for section, size in per_section.items()
            ):
                continue
            selected_ids.update(id(item) for item in group)
            used += group_size
            for section, size in per_section.items():
                section_used[section] += size

        selected = tuple(item for item in candidates if id(item) in selected_ids)
        omitted: dict[ContextSection, int] = defaultdict(int)
        for item in candidates:
            if id(item) not in selected_ids:
                omitted[item.section] += 1
        return PreparedContext(selected, used, dict(omitted))
