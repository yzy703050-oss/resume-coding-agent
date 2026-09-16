"""Convert authoritative registry schemas to LangChain function bindings."""

from __future__ import annotations

from typing import Any

from coding_agent.agent.actions import FinishAction, JsonValue


def function_tools(schemas: list[dict[str, JsonValue]]) -> list[dict[str, Any]]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["input_schema"],
            },
        }
        for schema in schemas
    ]
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Finish the run with a concise summary",
                "parameters": FinishAction.model_json_schema(),
            },
        }
    )
    return tools
