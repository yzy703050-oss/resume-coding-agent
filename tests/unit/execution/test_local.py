import sys
import time
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType

import pytest

import coding_agent.execution.local as local_module
from coding_agent.execution.base import CommandRequest
from coding_agent.execution.local import LocalExecutionBackend
from coding_agent.execution.policy import CommandPolicy


def backend(repo: Path) -> LocalExecutionBackend:
    return LocalExecutionBackend(repo, CommandPolicy(((sys.executable, ("-c",)),)))


def test_backend_captures_streams_and_nonzero_exit(tmp_path: Path) -> None:
    request = CommandRequest(
        sys.executable,
        (
            "-c",
            "(__import__('sys').stdout.write('out\\n'),"
            "__import__('sys').stderr.write('err\\n'),__import__('sys').exit(3))",
        ),
        ".",
        5,
        10_000,
    )
    result = backend(tmp_path).run(request)
    assert result.status == "exited"
    assert result.exit_code == 3
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"
    assert result.duration_ms >= 0


def test_backend_confines_cwd_and_truncates_by_bytes(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    request = CommandRequest(
        sys.executable,
        (
            "-c",
            "(print(__import__('os').path.basename(__import__('os').getcwd())),print('é' * 20))",
        ),
        "sub",
        5,
        12,
    )
    result = backend(tmp_path).run(request)
    assert result.status == "exited"
    assert result.stdout.startswith("sub")
    assert len(result.stdout.encode("utf-8")) <= 12
    assert result.stdout_truncated


def test_backend_normalizes_blocked_and_spawn_failed(tmp_path: Path) -> None:
    blocked = backend(tmp_path).run(CommandRequest("cmd", ("/c", "dir"), ".", 1, 100))
    assert blocked.status == "blocked"
    custom = LocalExecutionBackend(tmp_path, CommandPolicy((("missing-agent-exe", ()),)))
    missing = custom.run(CommandRequest("missing-agent-exe", (), ".", 1, 100))
    assert missing.status == "spawn_failed"


def test_timeout_kills_child_process_tree(tmp_path: Path) -> None:
    marker = tmp_path / "child-survived.txt"
    child_code = (
        f"(__import__('time').sleep(.8),"
        f"__import__('pathlib').Path({str(marker)!r}).write_text('bad'))"
    )
    parent_code = (
        f"(__import__('subprocess').Popen([__import__('sys').executable,'-c',{child_code!r}]),"
        "__import__('time').sleep(10))"
    )
    result = backend(tmp_path).run(
        CommandRequest(sys.executable, ("-c", parent_code), ".", 0.1, 10_000)
    )
    assert result.status == "timed_out"
    assert result.exit_code is None
    time.sleep(1)
    assert not marker.exists()


def test_backend_rejects_cwd_escape(tmp_path: Path) -> None:
    result = backend(tmp_path).run(
        CommandRequest(sys.executable, ("-c", "print('no')"), "..", 1, 100)
    )
    assert result.status == "blocked"


def test_assignment_failure_cleans_already_started_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "leaked.txt"

    class FailingJob(AbstractContextManager["FailingJob"]):
        def __enter__(self) -> "FailingJob":
            return self

        def assign(self, process) -> None:
            raise OSError("cannot assign")

        def terminate(self, process) -> None:
            process.kill()

        def __exit__(self, exc_type, exc_value, traceback: TracebackType | None) -> None:
            return None

    monkeypatch.setattr(local_module, "_job_context", FailingJob)
    code = (
        f"(__import__('time').sleep(.5),"
        f"__import__('pathlib').Path({str(marker)!r}).write_text('bad'))"
    )
    result = backend(tmp_path).run(CommandRequest(sys.executable, ("-c", code), ".", 2, 100))
    assert result.status == "spawn_failed"
    time.sleep(0.7)
    assert not marker.exists()
