import json
from pathlib import Path
from typing import cast

import httpx
import pytest
from pydantic import SecretStr

from coding_agent.config import RunConfig
from coding_agent.context.builder import Message
from coding_agent.models.base import FormatErrorReason, ModelFormatError


def test_format_error_reason_code_is_fixed_vocabulary() -> None:
    error = ModelFormatError(
        "raw-provider-content", reason_code=cast(FormatErrorReason, "untrusted-category")
    )
    assert error.reason_code == "invalid_action"


def body(calls: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "resp-framework",
        "object": "chat.completion",
        "created": 1,
        "model": "deepseek-flash",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": calls,
                },
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


def call(name: str = "finish", arguments: str = '{"summary":"done"}') -> dict[str, object]:
    return {
        "id": "call-1",
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }


@pytest.mark.parametrize("provider", ["deepseek", "openai-compatible"])
def test_framework_model_binds_real_schemas_and_maps_usage(provider: str) -> None:
    from coding_agent.models.langchain_client import create_langchain_model

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body([call()]))

    client = create_langchain_model(
        RunConfig(
            repository=Path.cwd(),
            task="fix",
            provider=provider,
            model="deepseek-flash",
            base_url="https://api.deepseek.com",
            api_key=SecretStr("offline-key"),
            max_output_tokens=512,
            thinking_enabled=False,
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.complete(
        [Message("system", "rules"), Message("user", "fix")],
        [
            {
                "name": "read_file",
                "description": "read",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ],
    )
    payload = json.loads(seen[0].content)
    assert seen[0].url == "https://api.deepseek.com/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer offline-key"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload.get("max_tokens", payload.get("max_completion_tokens")) == 512
    assert payload["tool_choice"] == "required"
    assert [t["function"]["name"] for t in payload["tools"]] == ["read_file", "finish"]
    assert payload["tools"][0]["function"]["parameters"]["properties"] == {
        "path": {"type": "string"},
    }
    assert result.action.kind == "finish"
    assert result.usage.total_tokens == 8
    assert result.usage.cost_usd is None
    assert result.raw_response_id == "resp-framework"


@pytest.mark.parametrize(
    ("calls", "reason_code"),
    [
        ([], "missing_tool_call"),
        ([call(), call()], "multiple_tool_calls"),
        ([call(arguments="{")], "invalid_tool_call"),
        ([call(arguments="[]")], "invalid_action_arguments"),
        ([call(arguments='{"extra":1}')], "invalid_action_arguments"),
    ],
)
def test_framework_model_rejects_missing_multiple_or_invalid_actions(calls, reason_code) -> None:
    from coding_agent.models.langchain_client import create_langchain_model

    client = create_langchain_model(
        RunConfig(
            repository=Path.cwd(),
            task="fix",
            provider="deepseek",
            api_key=SecretStr("offline-key"),
            model="deepseek-flash",
            base_url="https://api.deepseek.com",
            thinking_enabled=False,
        ),
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body(calls)))
        ),
    )
    with pytest.raises(ModelFormatError) as exc_info:
        client.complete([Message("user", "fix")], [])
    assert exc_info.value.reason_code == reason_code


def test_deepseek_factory_defaults_to_non_thinking_for_required_tools() -> None:
    from coding_agent.models.langchain_client import create_langchain_model

    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=body([call()]))

    client = create_langchain_model(
        RunConfig(
            repository=Path.cwd(),
            task="fix",
            provider="deepseek",
            api_key=SecretStr("offline-key"),
            model="deepseek-flash",
            base_url="https://api.deepseek.com",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.complete([Message("user", "fix")], [])
    assert payloads[0]["thinking"] == {"type": "disabled"}


def test_deepseek_thinking_mode_is_rejected_before_required_tool_request() -> None:
    from coding_agent.models.langchain_client import create_langchain_model

    with pytest.raises(ValueError, match="thinking"):
        create_langchain_model(
            RunConfig(
                repository=Path.cwd(),
                task="fix",
                provider="deepseek",
                thinking_enabled=True,
                api_key=SecretStr("offline-key"),
                model="deepseek-flash",
                base_url="https://api.deepseek.com",
            )
        )


def test_provider_malformed_function_fields_become_recoverable_format_error() -> None:
    from coding_agent.models.langchain_client import create_langchain_model

    malformed = {"id": "broken", "type": "function", "function": {"name": "finish"}}
    client = create_langchain_model(
        RunConfig(
            repository=Path.cwd(),
            task="fix",
            provider="deepseek",
            api_key=SecretStr("offline-key"),
            model="deepseek-flash",
            base_url="https://api.deepseek.com",
        ),
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=body([malformed]))
            )
        ),
    )
    with pytest.raises(ModelFormatError):
        client.complete([Message("user", "fix")], [])
