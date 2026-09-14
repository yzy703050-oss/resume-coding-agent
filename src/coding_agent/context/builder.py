"""Formatting-only conversion from selected context values to model messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from coding_agent.context.items import ContextSection, PreparedContext


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


class ContextBuilder:
    def build(self, prepared: PreparedContext) -> list[Message]:
        messages: list[Message] = []
        for item in prepared.items:
            raw_role = item.metadata.get("role", "user")
            role = cast(
                Literal["system", "user", "assistant"],
                raw_role if raw_role in {"system", "user", "assistant"} else "user",
            )
            content = item.content
            if item.section is not ContextSection.MANDATORY:
                content = f"{item.section.value.replace('_', ' ').upper()}:\n{content}"
            messages.append(Message(role, content))
        if prepared.omitted_by_section:
            values = ", ".join(
                f"{section.value}={count}"
                for section, count in sorted(
                    prepared.omitted_by_section.items(), key=lambda pair: pair[0].value
                )
            )
            messages.append(Message("user", f"[context omitted: {values}]"))
        return messages
