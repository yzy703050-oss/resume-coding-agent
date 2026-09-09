"""Small OpenAI-compatible chat-completions adapter."""

from __future__ import annotations

import json
from typing import Any, cast

import httpx
from pydantic import ValidationError

from coding_agent.agent.actions import FinishAction, JsonValue, ModelUsage, ToolAction
from coding_agent.context.builder import Message
from coding_agent.models.base import ModelFormatError, ModelResponse


class ModelTransportError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        http_client: httpx.Client | None = None,
        max_retries: int = 2,
    ) -> None:
        if not api_key or not model:
            raise ValueError("api_key and model are required")
        self._api_key = api_key
        self._model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._http = http_client or httpx.Client(timeout=60)
        self._max_retries = max_retries

    def complete(
        self, messages: list[Message], tool_schemas: list[dict[str, JsonValue]]
    ) -> ModelResponse:
        response = self._post(self._payload(messages, tool_schemas))
        try:
            body = cast(dict[str, Any], response.json())
            choices = cast(list[dict[str, Any]], body["choices"])
            message = cast(dict[str, Any], choices[0]["message"])
            calls = cast(list[dict[str, Any]], message["tool_calls"])
            if len(calls) != 1:
                raise ModelFormatError("model must return exactly one action")
            function = cast(dict[str, Any], calls[0]["function"])
            name = cast(str, function["name"])
            arguments = json.loads(cast(str, function["arguments"]))
            if not isinstance(arguments, dict):
                raise ModelFormatError("tool arguments must be an object")
            action: FinishAction | ToolAction
            if name == "finish":
                action = FinishAction.model_validate(arguments)
            else:
                action = ToolAction(tool=name, arguments=cast(dict[str, JsonValue], arguments))
            usage = cast(dict[str, Any], body.get("usage", {}))
            model_usage = ModelUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            )
            return ModelResponse(
                action=action,
                usage=model_usage,
                raw_response_id=cast(str | None, body.get("id")),
            )
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            ValidationError,
            json.JSONDecodeError,
        ) as error:
            if isinstance(error, ModelFormatError):
                raise
            raise ModelFormatError("invalid model action response") from error

    def _payload(
        self, messages: list[Message], tool_schemas: list[dict[str, JsonValue]]
    ) -> dict[str, Any]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["input_schema"],
                },
            }
            for schema in tool_schemas
        ]
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "finish",
                    "description": "Finish the run with a concise summary",
                    "parameters": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                        "additionalProperties": False,
                    },
                },
            }
        )
        return {
            "model": self._model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "tools": tools,
            "tool_choice": "required",
        }

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            except (httpx.TimeoutException, httpx.TransportError) as error:
                if attempt < self._max_retries:
                    continue
                raise ModelTransportError("model request failed after retries") from error
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self._max_retries:
                    continue
            if response.is_error:
                raise ModelTransportError(f"model endpoint returned HTTP {response.status_code}")
            return response
        raise ModelTransportError("model request failed after retries")
