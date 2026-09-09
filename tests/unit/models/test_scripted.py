import pytest

from coding_agent.agent.actions import FinishAction, ModelUsage, ToolAction
from coding_agent.context.builder import Message
from coding_agent.models.base import ModelResponse
from coding_agent.models.scripted import ScriptedModelClient


def test_scripted_client_returns_queued_actions_and_records_messages() -> None:
    client = ScriptedModelClient(
        [
            ModelResponse(
                action=ToolAction(tool="read_file", arguments={"path": "a.py"}),
                usage=ModelUsage(input_tokens=2),
            ),
            ModelResponse(action=FinishAction(summary="done"), usage=ModelUsage()),
        ]
    )
    messages = [Message("user", "task")]
    assert client.complete(messages, []).action.kind == "tool"
    assert client.complete(messages, []).action.kind == "finish"
    assert client.received_messages == [messages, messages]
    with pytest.raises(RuntimeError, match="exhausted"):
        client.complete(messages, [])
