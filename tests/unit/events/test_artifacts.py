import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from coding_agent.agent.state import RunLimits, RunState, RunStatus
from coding_agent.events.artifacts import Finalizer
from coding_agent.events.writer import EventWriter


@dataclass(frozen=True)
class PatchEvidence:
    patch: str
    changed_files: tuple[str, ...]


def terminal_state(tmp_path: Path, status: RunStatus) -> RunState:
    state = RunState.start(tmp_path, "fix", "abc123", RunLimits(max_steps=3))
    state.finish(status, f"ended as {status.value}")
    return state


@pytest.mark.parametrize(
    ("status", "event_type"),
    [
        (RunStatus.COMPLETED, "AgentFinished"),
        (RunStatus.STEP_LIMIT, "AgentFailed"),
        (RunStatus.BUDGET_LIMIT, "AgentFailed"),
        (RunStatus.CANCELLED, "AgentFailed"),
        (RunStatus.FAILED, "AgentFailed"),
    ],
)
def test_finalizer_owns_terminal_event_and_all_artifacts(
    tmp_path: Path, status: RunStatus, event_type: str
) -> None:
    run_dir = tmp_path / status.value
    state = terminal_state(tmp_path, status)
    writer = EventWriter(run_dir / "events.jsonl", state.run_id)
    writer.append("TaskStarted", {"task": state.task})
    finalizer = Finalizer(
        writer,
        patch_provider=lambda: PatchEvidence("diff --git a/a.py b/a.py\n", ("a.py",)),
    )

    artifacts = finalizer.finalize(state)

    events = [json.loads(line) for line in artifacts.events_path.read_text().splitlines()]
    terminal_events = [event for event in events if event["type"].startswith("Agent")]
    assert [(event["type"], event["payload"]["status"]) for event in terminal_events] == [
        (event_type, status.value)
    ]
    assert artifacts.patch_path.read_text(encoding="utf-8").startswith("diff --git")
    summary = json.loads(artifacts.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == status.value
    assert summary["artifacts"]["events"] == "events.jsonl"
    assert summary["artifacts"]["patch"] == "patch.diff"


def test_finalizer_rejects_second_call_before_any_rewrite(tmp_path: Path) -> None:
    state = terminal_state(tmp_path, RunStatus.COMPLETED)
    writer = EventWriter(tmp_path / "events.jsonl", state.run_id)
    finalizer = Finalizer(writer, patch_provider=lambda: PatchEvidence("first patch\n", ()))
    artifacts = finalizer.finalize(state)
    before = (
        artifacts.events_path.read_bytes(),
        artifacts.patch_path.read_bytes(),
        artifacts.summary_path.read_bytes(),
    )

    with pytest.raises(ValueError, match="already finalized"):
        finalizer.finalize(state)

    after = (
        artifacts.events_path.read_bytes(),
        artifacts.patch_path.read_bytes(),
        artifacts.summary_path.read_bytes(),
    )
    assert after == before


def test_finalizer_requires_terminal_state(tmp_path: Path) -> None:
    state = RunState.start(tmp_path, "fix", "abc123", RunLimits())
    finalizer = Finalizer(
        EventWriter(tmp_path / "events.jsonl", state.run_id), lambda: PatchEvidence("", ())
    )
    with pytest.raises(ValueError, match="terminal"):
        finalizer.finalize(state)


def test_summary_uses_changed_files_from_final_patch_evidence(tmp_path: Path) -> None:
    state = terminal_state(tmp_path, RunStatus.COMPLETED)
    writer = EventWriter(tmp_path / "events.jsonl", state.run_id)
    evidence = PatchEvidence("diff --git a/generated.py b/generated.py\n", ("generated.py",))

    artifacts = Finalizer(writer, lambda: evidence).finalize(state)

    summary = json.loads(artifacts.summary_path.read_text(encoding="utf-8"))
    assert summary["changed_files"] == ["generated.py"]
