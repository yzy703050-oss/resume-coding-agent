import json
from pathlib import Path

import pytest

from coding_agent.events.recorder import RunEventRecorder
from coding_agent.events.writer import EventWriter
from coding_agent.memory.episodic import EpisodicMemory


def test_recorder_projects_history_before_strict_audit_truncation(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    history = EpisodicMemory()
    writer = EventWriter(path, "run-1")
    recorder = RunEventRecorder(
        writer,
        history,
        secrets={"secret"},
        audit_max_string_chars=10,
    )

    with recorder.correlate("run-1:step:1"):
        canonical = recorder.append(
            "ToolResult", {"tool": "read_file", "text": "secret-" + "x" * 30}
        )
    recorder.close()

    audit = json.loads(path.read_text(encoding="utf-8"))
    assert canonical.sequence == audit["sequence"] == history.events[0].source_sequence
    assert audit["correlation_id"] == history.events[0].correlation_id == "run-1:step:1"
    assert len(history.events[0].content) > len(audit["payload"]["text"])
    assert "secret" not in path.read_text(encoding="utf-8")
    assert "secret" not in history.events[0].content


def test_recorder_keeps_terminal_events_restricted_to_finalizer_path(tmp_path: Path) -> None:
    recorder = RunEventRecorder(EventWriter(tmp_path / "events.jsonl", "run-1"))

    with pytest.raises(ValueError, match="terminal events"):
        recorder.append("AgentFinished", {"status": "completed"})

    terminal = recorder._append_terminal("AgentFinished", {"status": "completed"})
    assert terminal.type == "AgentFinished"
    recorder.close()
