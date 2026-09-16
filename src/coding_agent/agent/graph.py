"""Explicit single-action ReAct graph using existing run-local domain boundaries."""

from __future__ import annotations

from typing import NotRequired, TypedDict, cast

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from coding_agent.agent.actions import FinishAction, JsonValue, Observation
from coding_agent.agent.state import RunState, RunStatus
from coding_agent.context.builder import Message
from coding_agent.context.manager import ContextManager
from coding_agent.events.recorder import RunEventRecorder
from coding_agent.models.base import ModelClient, ModelFormatError, ModelResponse
from coding_agent.tools.registry import ToolRegistry, ToolResult


class ReActGraphState(TypedDict):
    run: RunState
    messages: NotRequired[list[Message]]
    response: NotRequired[ModelResponse | None]
    result: NotRequired[ToolResult | None]


type ReActGraph = CompiledStateGraph[ReActGraphState, None, ReActGraphState, ReActGraphState]


def budget_exhausted(state: RunState) -> bool:
    if state.limits.max_tokens is not None and state.total_tokens >= state.limits.max_tokens:
        return True
    if state.limits.max_cost_usd is None:
        return False
    cost = state.total_cost_usd
    return (state.total_tokens > 0 and cost is None) or (
        cost is not None and cost >= state.limits.max_cost_usd
    )


def build_react_graph(
    context: ContextManager,
    model: ModelClient,
    tools: ToolRegistry,
    recorder: RunEventRecorder,
) -> ReActGraph:
    def guard(data: ReActGraphState) -> dict[str, object]:
        state = data["run"]
        if not state.status.terminal:
            if state.step_count >= state.limits.max_steps:
                state.finish(RunStatus.STEP_LIMIT, "step limit reached")
            elif budget_exhausted(state):
                state.finish(RunStatus.BUDGET_LIMIT, "model budget reached")
        return {"run": state, "messages": [], "response": None, "result": None}

    def after_guard(data: ReActGraphState) -> str:
        return END if data["run"].status.terminal else "prepare"

    def prepare(data: ReActGraphState) -> dict[str, object]:
        state = data["run"]
        state.begin_step()
        return {"run": state, "messages": context.prepare(state, tools.schemas())}

    def decide(data: ReActGraphState) -> dict[str, object]:
        state = data["run"]
        try:
            response = model.complete(data["messages"], tools.schemas())
        except ModelFormatError as error:
            recorder.append(
                "ModelStep",
                {
                    "step": state.step_count,
                    "ok": False,
                    "error": "format_error",
                    "reason_code": error.reason_code,
                },
            )
            observation = Observation(
                tool="model",
                ok=False,
                summary="Model response did not contain one valid action.",
                data={"reason_code": error.reason_code},
                error_code="format_error",
            )
            state.add_observation(observation)
            context.record_observation(observation)
            return {"run": state, "response": None}
        state.usage.add(response.usage)
        recorder.append(
            "ModelStep",
            {
                "step": state.step_count,
                "ok": True,
                "action": response.action.kind,
                "response_id": response.raw_response_id,
                "usage": cast(JsonValue, response.usage.model_dump(mode="json")),
            },
        )
        if isinstance(response.action, FinishAction):
            state.finish_summary = response.action.summary
            state.finish(RunStatus.COMPLETED, "model finished")
        elif budget_exhausted(state):
            state.finish(RunStatus.BUDGET_LIMIT, "model budget reached")
        return {"run": state, "response": response}

    def after_decide(data: ReActGraphState) -> str:
        if data["run"].status.terminal:
            return END
        return "guard" if data.get("response") is None else "execute"

    def execute(data: ReActGraphState) -> dict[str, object]:
        response = data["response"]
        assert response is not None and response.action.kind == "tool"
        with recorder.correlate(f"step-{data['run'].step_count}"):
            result = tools.execute(response.action.tool, response.action.arguments)
        return {"result": result}

    def observe(data: ReActGraphState) -> dict[str, object]:
        state, response, result = data["run"], data["response"], data["result"]
        assert response is not None and response.action.kind == "tool" and result is not None
        observation = result.to_observation(response.action.tool)
        state.add_observation(observation)
        context.record_observation(observation)
        if result.ok and response.action.tool == "read_file":
            path, content = result.data.get("path"), result.data.get("content")
            if isinstance(path, str) and isinstance(content, str):
                context.pin_file(path, content)
        if result.ok and response.action.tool == "edit_file":
            path = result.data.get("path")
            if isinstance(path, str):
                context.mark_changed(path)
        return {"run": state}

    builder = StateGraph(ReActGraphState)
    builder.add_node("guard", RunnableLambda(guard))
    builder.add_node("prepare", RunnableLambda(prepare))
    builder.add_node("decide", RunnableLambda(decide))
    builder.add_node("execute", RunnableLambda(execute))
    builder.add_node("observe", RunnableLambda(observe))
    builder.add_edge(START, "guard")
    builder.add_conditional_edges("guard", after_guard, {END: END, "prepare": "prepare"})
    builder.add_edge("prepare", "decide")
    builder.add_conditional_edges(
        "decide", after_decide, {END: END, "guard": "guard", "execute": "execute"}
    )
    builder.add_edge("execute", "observe")
    builder.add_edge("observe", "guard")
    return builder.compile()
