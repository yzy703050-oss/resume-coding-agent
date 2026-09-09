from pathlib import Path

from coding_agent.agent.actions import Observation
from coding_agent.agent.state import RunLimits, RunState
from coding_agent.context.builder import ContextBuilder


def state(tmp_path: Path) -> RunState:
    return RunState.start(tmp_path, "fix the calculator bug", "abc123", RunLimits(max_steps=5))


def rendered(builder: ContextBuilder, run_state: RunState) -> str:
    return "\n".join(message.content for message in builder.build(run_state, tool_schemas=[]))


def test_builder_preserves_mandatory_and_latest_test_under_budget(tmp_path: Path) -> None:
    run_state = state(tmp_path)
    run_state.add_observation(
        Observation(tool="read_file", ok=True, summary="old", data={"content": "x" * 500})
    )
    latest = Observation(
        tool="run_command",
        ok=False,
        summary="1 failed",
        data={"is_test": True, "stderr": "assertion failed"},
    )
    run_state.add_observation(latest)
    builder = ContextBuilder(max_chars=650, pinned_max_chars=100)
    text = rendered(builder, run_state)
    assert run_state.task in text
    assert "remaining_steps" in text
    assert "1 failed" in text
    assert "[older observation elided]" in text
    assert len(text) <= builder.max_chars


def test_pinned_reads_replace_by_path_and_move_to_mru(tmp_path: Path) -> None:
    run_state = state(tmp_path)
    run_state.pin_file("a.py", "old-a")
    run_state.pin_file("b.py", "only-b")
    run_state.pin_file("a.py", "new-a")
    text = rendered(ContextBuilder(max_chars=1_000, pinned_max_chars=100), run_state)
    assert "old-a" not in text
    assert text.index("only-b") < text.index("new-a")


def test_pinned_budget_evicts_least_recently_read_without_edit_priority(tmp_path: Path) -> None:
    run_state = state(tmp_path)
    run_state.pin_file("old.py", "OLD-CONTENT")
    run_state.pin_file("new.py", "NEW-CONTENT")
    run_state.mark_changed("old.py")
    text = rendered(ContextBuilder(max_chars=1_000, pinned_max_chars=11), run_state)
    assert "NEW-CONTENT" in text
    assert "OLD-CONTENT" not in text
    assert "[pinned file elided]" in text


def test_identical_state_produces_identical_messages(tmp_path: Path) -> None:
    run_state = state(tmp_path)
    run_state.pin_file("a.py", "x = 1")
    run_state.add_observation(Observation(tool="read_file", ok=True, summary="read", data={}))
    builder = ContextBuilder(max_chars=1_000, pinned_max_chars=100)
    assert builder.build(run_state, []) == builder.build(run_state, [])
