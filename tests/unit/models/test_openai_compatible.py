import json

import httpx
import pytest

from coding_agent.context.builder import Message
from coding_agent.models.openai_compatible import (
    ModelFormatError,
    ModelTransportError,
    OpenAICompatibleClient,
)


def response(action_name: str, arguments: dict[str, object], status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={
            "id": "resp-1",
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": action_name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        },
    )


def test_adapter_sends_tools_and_parses_action_and_usage() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response("read_file", {"path": "a.py"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = OpenAICompatibleClient("secret", "model-x", "https://example.test/v1", http)
    result = client.complete(
        [Message("user", "fix")],
        [{"name": "read_file", "description": "read", "input_schema": {"type": "object"}}],
    )
    payload = json.loads(seen[0].content)
    assert seen[0].url == "https://example.test/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer secret"
    assert payload["model"] == "model-x"
    assert [tool["function"]["name"] for tool in payload["tools"]] == ["read_file", "finish"]
    assert result.action.kind == "tool"
    assert result.usage.total_tokens == 8
    assert result.raw_response_id == "resp-1"


def test_adapter_parses_finish_and_rejects_malformed_arguments() -> None:
    finish_http = httpx.Client(
        transport=httpx.MockTransport(lambda request: response("finish", {"summary": "done"}))
    )
    client = OpenAICompatibleClient("secret", "m", "https://example.test/v1", finish_http)
    assert client.complete([], []).action.kind == "finish"

    malformed = httpx.Response(
        200,
        json={
            "id": "bad",
            "choices": [
                {"message": {"tool_calls": [{"function": {"name": "x", "arguments": "{"}}]}}
            ],
            "usage": {},
        },
    )
    bad_http = httpx.Client(transport=httpx.MockTransport(lambda request: malformed))
    with pytest.raises(ModelFormatError):
        OpenAICompatibleClient("secret", "m", "https://x/v1", bad_http).complete([], [])


def test_adapter_retries_transient_status_but_not_terminal_status() -> None:
    attempts = 0

    def transient(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429) if attempts == 1 else response("finish", {"summary": "done"})

    client = OpenAICompatibleClient(
        "secret", "m", "https://x/v1", httpx.Client(transport=httpx.MockTransport(transient))
    )
    assert client.complete([], []).action.kind == "finish"
    assert attempts == 2

    terminal = OpenAICompatibleClient(
        "secret",
        "m",
        "https://x/v1",
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(400))),
    )
    with pytest.raises(ModelTransportError) as captured:
        terminal.complete([], [])
    assert "secret" not in str(captured.value)


def test_deepseek_request_disables_thinking_and_caps_generated_tokens() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response("finish", {"summary": "done"})

    client = OpenAICompatibleClient(
        "secret",
        "deepseek-flash",
        "https://api.deepseek.com",
        httpx.Client(transport=httpx.MockTransport(handler)),
        max_output_tokens=512,
        thinking_enabled=False,
    )
    assert client.complete([Message("user", "fix")], []).action.kind == "finish"
    payload = json.loads(seen[0].content)
    assert seen[0].url == "https://api.deepseek.com/chat/completions"
    assert payload["max_tokens"] == 512
    assert payload["thinking"] == {"type": "disabled"}
