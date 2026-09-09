"""Deterministic queued-response model for tests and offline demos."""

from __future__ import annotations

from collections import deque

from coding_agent.agent.actions import JsonValue
from coding_agent.context.builder import Message
from coding_agent.models.base import ModelResponse


class ScriptedModelClient:
    def __init__(self, responses: list[ModelResponse | BaseException]) -> None:
        self._responses = deque(responses)
        self.received_messages: list[list[Message]] = []
        self.received_tool_schemas: list[list[dict[str, JsonValue]]] = []

    def complete(
        self, messages: list[Message], tool_schemas: list[dict[str, JsonValue]]
    ) -> ModelResponse:
        self.received_messages.append(list(messages))
        self.received_tool_schemas.append(list(tool_schemas))
        if not self._responses:
            raise RuntimeError("scripted model response queue exhausted")
        response = self._responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response
