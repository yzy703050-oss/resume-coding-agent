import json
from pathlib import Path

import pytest

from coding_agent.events.writer import EventWriter


def test_writer_appends_contiguous_redacted_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = EventWriter(path, run_id="run-1", secrets={"secret-key"}, max_string_chars=20)
    writer.append("TaskStarted", {"task": "fix", "nested": {"api_key": "secret-key"}})
    writer.append("ModelStep", {"step": 1, "raw": "x" * 30})
    writer.close()
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [event["sequence"] for event in events] == [1, 2]
    assert all(event["schema_version"] == "1" for event in events)
    assert "secret-key" not in path.read_text(encoding="utf-8")
    assert events[1]["payload"]["raw"] == "x" * 20 + "...[truncated]"


def test_writer_flushes_each_append_and_rejects_append_after_close(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = EventWriter(path, run_id="run-1")
    writer.append("TaskStarted", {"task": "fix"})
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    writer.close()
    with pytest.raises(ValueError, match="closed"):
        writer.append("ModelStep", {"step": 1})


def test_writer_rejects_unknown_event_type(tmp_path: Path) -> None:
    writer = EventWriter(tmp_path / "events.jsonl", run_id="run-1")
    with pytest.raises(ValueError, match="event type"):
        writer.append("SomethingElse", {})
    writer.close()
