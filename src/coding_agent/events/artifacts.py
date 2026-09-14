"""One-shot terminal event and run artifact finalization."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from coding_agent.agent.actions import JsonValue
from coding_agent.agent.state import RunState, RunStatus
from coding_agent.events.recorder import RunEventRecorder


@dataclass(frozen=True)
class RunArtifacts:
    events_path: Path
    summary_path: Path
    patch_path: Path


class PatchEvidence(Protocol):
    @property
    def patch(self) -> str: ...

    @property
    def changed_files(self) -> tuple[str, ...]: ...


class Finalizer:
    """Sole terminal-event owner for one run."""

    def __init__(
        self, event_writer: RunEventRecorder, patch_provider: Callable[[], PatchEvidence]
    ) -> None:
        self._event_writer = event_writer
        self._patch_provider = patch_provider
        self._finalized = False

    def finalize(self, state: RunState) -> RunArtifacts:
        if self._finalized:
            raise ValueError("run already finalized")
        if not state.status.terminal:
            raise ValueError("run must be terminal before finalization")
        self._finalized = True

        patch_evidence = self._patch_provider()
        event_type = "AgentFinished" if state.status is RunStatus.COMPLETED else "AgentFailed"
        self._event_writer._append_terminal(
            event_type,
            {
                "status": state.status.value,
                "reason": state.termination_reason,
                "step_count": state.step_count,
            },
        )
        self._event_writer.close()

        run_dir = self._event_writer.path.parent
        patch_path = run_dir / "patch.diff"
        summary_path = run_dir / "summary.json"
        patch_path.write_text(patch_evidence.patch, encoding="utf-8", newline="\n")
        summary = self._summary(state, patch_evidence.changed_files)
        temporary = summary_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(summary_path)
        return RunArtifacts(self._event_writer.path, summary_path, patch_path)

    def _summary(self, state: RunState, changed_files: tuple[str, ...]) -> dict[str, JsonValue]:
        finished_at = state.finished_at or state.started_at
        elapsed_ms = max(0, int((finished_at - state.started_at).total_seconds() * 1_000))
        latest_test = (
            state.latest_test_result.model_dump(mode="json") if state.latest_test_result else None
        )
        main_usage: dict[str, JsonValue] = cast(
            dict[str, JsonValue],
            state.usage.model_dump(mode="json") | {"total_tokens": state.usage.total_tokens},
        )
        auxiliary_usage: dict[str, JsonValue] = cast(
            dict[str, JsonValue],
            state.auxiliary_usage.model_dump(mode="json")
            | {"total_tokens": state.auxiliary_usage.total_tokens},
        )
        usage: dict[str, JsonValue] = {
            **main_usage,
            "main": main_usage,
            "auxiliary": auxiliary_usage,
            "combined_total_tokens": state.total_tokens,
            "combined_cost_usd": state.total_cost_usd,
        }
        return {
            "schema_version": "1",
            "run_id": state.run_id,
            "status": state.status.value,
            "reason": state.termination_reason,
            "task": state.task,
            "repository": {"root": str(state.repo_root), "base_commit": state.base_commit},
            "limits": state.limits.model_dump(mode="json"),
            "configuration": state.effective_config,
            "usage": usage,
            "elapsed_ms": elapsed_ms,
            "step_count": state.step_count,
            "tool_counts": cast(dict[str, JsonValue], state.tool_counts),
            "changed_files": cast(list[JsonValue], list(changed_files)),
            "latest_test_result": latest_test,
            "finish_summary": state.finish_summary,
            "context_metrics": state.context_metrics,
            "memory_metrics": state.memory_metrics,
            "artifacts": {
                "events": self._event_writer.path.name,
                "patch": "patch.diff",
                "summary": "summary.json",
            },
        }
