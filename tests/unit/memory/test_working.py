from coding_agent.agent.actions import Observation
from coding_agent.memory.working import WorkingMemory


def test_working_memory_replaces_pinned_path_and_bounds_total_content() -> None:
    memory = WorkingMemory(pinned_max_chars=10)
    memory.pin_file("a.py", "123456")
    memory.pin_file("b.py", "abcdef")

    assert [item.path for item in memory.pinned_files] == ["b.py"]

    memory.pin_file("b.py", "new")
    assert [(item.path, item.content) for item in memory.pinned_files] == [("b.py", "new")]


def test_working_memory_tracks_changed_files_latest_test_and_recent_errors() -> None:
    memory = WorkingMemory(pinned_max_chars=100, max_recent_errors=2)
    failed = Observation(
        tool="run_command",
        ok=False,
        summary="failed",
        data={"is_test": True},
        error_code="command_failed",
    )

    memory.mark_changed("src/a.py")
    memory.mark_changed("src/a.py")
    memory.record_observation(failed)
    memory.record_observation(Observation(tool="read_file", ok=False, summary="missing", data={}))
    memory.record_observation(Observation(tool="edit_file", ok=False, summary="conflict", data={}))

    assert memory.changed_files == ("src/a.py",)
    assert memory.latest_test_result is failed
    assert [item.summary for item in memory.recent_errors] == ["missing", "conflict"]
