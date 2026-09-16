"""LangChain provider integration behind the existing single-action model protocol."""

from __future__ import annotations

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langsmith import tracing_context
from openai import APIError
from pydantic import ValidationError

from coding_agent.agent.actions import FinishAction, JsonValue, ModelUsage, ToolAction
from coding_agent.config import RunConfig
from coding_agent.context.builder import Message
from coding_agent.models.base import ModelFormatError, ModelResponse
from coding_agent.models.openai_compatible import ModelTransportError
from coding_agent.models.tool_binding import function_tools


class LangChainModelClient:
    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    def complete(
        self,
        messages: list[Message],
        tool_schemas: list[dict[str, JsonValue]],
    ) -> ModelResponse:
        converted: list[BaseMessage] = []
        for message in messages:
            if message.role == "system":
                converted.append(SystemMessage(content=message.content))
            elif message.role == "assistant":
                converted.append(AIMessage(content=message.content))
            else:
                converted.append(HumanMessage(content=message.content))
        try:
            bound = self.chat_model.bind_tools(function_tools(tool_schemas), tool_choice="required")
            with tracing_context(enabled=False):
                result = bound.invoke(converted, config={"callbacks": []})
        except APIError as error:
            raise ModelTransportError("LangChain model request failed") from error
        except (ValueError, TypeError) as error:
            raise ModelFormatError("invalid model action response") from error
        if (
            not isinstance(result, AIMessage)
            or result.invalid_tool_calls
            or len(result.tool_calls) != 1
        ):
            raise ModelFormatError("model must return exactly one valid action")
        call = result.tool_calls[0]
        try:
            name, arguments = call["name"], call["args"]
            action = (
                FinishAction.model_validate(arguments)
                if name == "finish"
                else ToolAction(tool=name, arguments=arguments)
            )
            usage = result.usage_metadata
            if usage is None:
                raw_usage = result.response_metadata.get("token_usage", {})
                input_tokens = int(raw_usage.get("prompt_tokens", 0))
                output_tokens = int(raw_usage.get("completion_tokens", 0))
            else:
                input_tokens, output_tokens = usage["input_tokens"], usage["output_tokens"]
            raw_id = result.response_metadata.get("id")
            return ModelResponse(
                action=action,
                usage=ModelUsage(input_tokens=input_tokens, output_tokens=output_tokens),
                raw_response_id=raw_id if isinstance(raw_id, str) else None,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise ModelFormatError("invalid model action response") from error


def create_langchain_model(
    config: RunConfig,
    *,
    http_client: httpx.Client | None = None,
) -> LangChainModelClient:
    if config.api_key is None:
        raise ValueError("API key is required for live LangChain model")
    if config.provider == "deepseek" and config.thinking_enabled is True:
        raise ValueError("DeepSeek thinking mode is incompatible with required tool choice")
    thinking = False if config.provider == "deepseek" else config.thinking_enabled
    extra_body = (
        {"thinking": {"type": "enabled" if thinking else "disabled"}}
        if thinking is not None
        else None
    )
    chat_model = init_chat_model(
        config.model,
        model_provider="deepseek" if config.provider == "deepseek" else "openai",
        api_key=config.api_key,
        base_url=config.base_url,
        max_tokens=config.max_output_tokens,
        timeout=60,
        max_retries=1,
        extra_body=extra_body,
        use_responses_api=False,
        http_client=http_client,
        callbacks=[],
        cache=False,
    )
    return LangChainModelClient(chat_model)
