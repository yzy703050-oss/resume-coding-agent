"""Run lifecycle around a compiled LangGraph ReAct workflow."""

from __future__ import annotations

from typing import cast

from langsmith import tracing_context

from coding_agent.agent.actions import JsonValue
from coding_agent.agent.graph import ReActGraph, build_react_graph
from coding_agent.agent.state import RunState, RunStatus
from coding_agent.context.manager import ContextManager
from coding_agent.events.artifacts import Finalizer, RunArtifacts
from coding_agent.events.recorder import RunEventRecorder
from coding_agent.models.base import ModelClient
from coding_agent.tools.registry import ToolRegistry


class AgentRunner:
    def __init__(
        self,
        model: ModelClient,
        context_manager: ContextManager,
        tools: ToolRegistry,
        event_writer: RunEventRecorder,
        finalizer: Finalizer,
    ) -> None:
        self._context_manager = context_manager
        self._event_writer = event_writer
        self._finalizer = finalizer
        self.graph: ReActGraph = build_react_graph(context_manager, model, tools, event_writer)
        self.artifacts: RunArtifacts | None = None

    def run(self, state: RunState) -> RunState:
        if state.status is not RunStatus.STARTING:
            raise ValueError("runner requires a starting state")
        self._event_writer.append(
            "TaskStarted",
            {
                "task": state.task,
                "repository": str(state.repo_root),
                "base_commit": state.base_commit,
                "limits": cast(JsonValue, state.limits.model_dump(mode="json")),
                "configuration": cast(JsonValue, state.effective_config),
            },
        )
        try:
            self._context_manager.start_run()
            with tracing_context(enabled=False):
                self.graph.invoke(
                    {"run": state},
                    config={"recursion_limit": state.limits.max_steps * 5 + 10, "callbacks": []},
                )
        except KeyboardInterrupt:
            if not state.status.terminal:
                state.finish(RunStatus.CANCELLED, "interrupted by user")
        except Exception as error:
            if not state.status.terminal:
                state.finish(RunStatus.FAILED, f"unexpected {type(error).__name__}")
        if not state.status.terminal:
            state.finish(RunStatus.FAILED, "graph exited without terminal status")
        try:
            self._context_manager.finish_run(state)
        except Exception as error:
            state.memory_metrics["finish_error"] = type(error).__name__
        self.artifacts = self._finalizer.finalize(state)
        return state
