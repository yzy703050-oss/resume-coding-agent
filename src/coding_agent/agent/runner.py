"""Single synchronous ReAct loop."""

from __future__ import annotations

from typing import cast

from coding_agent.agent.actions import FinishAction, JsonValue, Observation
from coding_agent.agent.state import RunState, RunStatus
from coding_agent.context.manager import ContextManager
from coding_agent.events.artifacts import Finalizer, RunArtifacts
from coding_agent.events.recorder import RunEventRecorder
from coding_agent.models.base import ModelClient, ModelFormatError
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
        self._model = model
        self._context_manager = context_manager
        self._tools = tools
        self._event_writer = event_writer
        self._finalizer = finalizer
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
        self._context_manager.start_run()
        try:
            self._loop(state)
        except KeyboardInterrupt:
            if not state.status.terminal:
                state.finish(RunStatus.CANCELLED, "interrupted by user")
        except Exception as error:
            if not state.status.terminal:
                state.finish(RunStatus.FAILED, f"unexpected {type(error).__name__}")
        if not state.status.terminal:
            state.finish(RunStatus.FAILED, "runner exited without terminal status")
        self._context_manager.finish_run(state)
        self.artifacts = self._finalizer.finalize(state)
        return state

    def _loop(self, state: RunState) -> None:
        while not state.status.terminal:
            if state.step_count >= state.limits.max_steps:
                state.finish(RunStatus.STEP_LIMIT, "step limit reached")
                return
            if self._budget_exhausted(state):
                state.finish(RunStatus.BUDGET_LIMIT, "model budget reached")
                return

            state.begin_step()
            messages = self._context_manager.prepare(state, self._tools.schemas())
            try:
                response = self._model.complete(messages, self._tools.schemas())
            except ModelFormatError as error:
                self._event_writer.append(
                    "ModelStep",
                    {"step": state.step_count, "ok": False, "error": "format_error"},
                )
                observation = Observation(
                    tool="model",
                    ok=False,
                    summary=str(error),
                    data={},
                    error_code="format_error",
                )
                state.add_observation(observation)
                self._context_manager.record_observation(observation)
                continue

            state.usage.add(response.usage)
            self._event_writer.append(
                "ModelStep",
                {
                    "step": state.step_count,
                    "ok": True,
                    "action": response.action.kind,
                    "response_id": response.raw_response_id,
                    "usage": cast(JsonValue, response.usage.model_dump(mode="json")),
                },
            )
            if self._budget_exhausted(state):
                state.finish(RunStatus.BUDGET_LIMIT, "model budget reached")
                return
            if isinstance(response.action, FinishAction):
                state.finish_summary = response.action.summary
                state.finish(RunStatus.COMPLETED, "model finished")
                return

            action = response.action
            with self._event_writer.correlate(f"step-{state.step_count}"):
                result = self._tools.execute(action.tool, action.arguments)
            observation = result.to_observation(action.tool)
            state.add_observation(observation)
            self._context_manager.record_observation(observation)
            if result.ok and action.tool == "read_file":
                path = result.data.get("path")
                content = result.data.get("content")
                if isinstance(path, str) and isinstance(content, str):
                    self._context_manager.pin_file(path, content)
            if result.ok and action.tool == "edit_file":
                path = result.data.get("path")
                if isinstance(path, str):
                    self._context_manager.mark_changed(path)

    @staticmethod
    def _budget_exhausted(state: RunState) -> bool:
        token_limit_reached = (
            state.limits.max_tokens is not None and state.total_tokens >= state.limits.max_tokens
        )
        if token_limit_reached:
            return True
        if state.limits.max_cost_usd is None:
            return False
        if state.total_tokens > 0 and state.total_cost_usd is None:
            return True
        return (
            state.total_cost_usd is not None and state.total_cost_usd >= state.limits.max_cost_usd
        )
