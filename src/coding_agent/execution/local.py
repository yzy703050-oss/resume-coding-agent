"""Windows-first subprocess backend with process-tree timeout cleanup."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType
from typing import Any

from coding_agent.execution.base import CommandRequest, CommandResult, CommandStatus
from coding_agent.execution.policy import CommandPolicy, CommandPolicyError
from coding_agent.tools.paths import PathPolicyError, resolve_confined


class LocalExecutionBackend:
    def __init__(self, repo_root: Path, policy: CommandPolicy) -> None:
        self._repo_root = repo_root.resolve()
        self._policy = policy

    def run(self, request: CommandRequest) -> CommandResult:
        started = time.perf_counter()
        try:
            self._policy.check(request)
            cwd = resolve_confined(self._repo_root, request.cwd)
            if not cwd.is_dir():
                raise PathPolicyError("working directory does not exist")
        except (CommandPolicyError, PathPolicyError) as error:
            return self._result(CommandStatus.BLOCKED, None, "", str(error), started, request)

        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        with _job_context() as job:
            process: subprocess.Popen[str] | None = None
            try:
                process = subprocess.Popen(
                    [_resolved_executable(request.executable), *request.args],
                    cwd=cwd,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags,
                    start_new_session=os.name != "nt",
                )
                job.assign(process)
            except OSError as error:
                if process is not None:
                    job.terminate(process)
                    process.communicate()
                return self._result(
                    CommandStatus.SPAWN_FAILED, None, "", str(error), started, request
                )

            try:
                stdout, stderr = process.communicate(timeout=request.timeout_seconds)
            except subprocess.TimeoutExpired:
                job.terminate(process)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                return self._result(CommandStatus.TIMED_OUT, None, stdout, stderr, started, request)
            return self._result(
                CommandStatus.EXITED, process.returncode, stdout, stderr, started, request
            )

    def _result(
        self,
        status: CommandStatus,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        started: float,
        request: CommandRequest,
    ) -> CommandResult:
        bounded_out, out_truncated = _truncate_utf8(stdout, request.output_limit_bytes)
        bounded_err, err_truncated = _truncate_utf8(stderr, request.output_limit_bytes)
        return CommandResult(
            status=status,
            exit_code=exit_code,
            stdout=bounded_out,
            stderr=bounded_err,
            duration_ms=max(0, int((time.perf_counter() - started) * 1_000)),
            stdout_truncated=out_truncated,
            stderr_truncated=err_truncated,
        )


def _truncate_utf8(value: str, limit: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def _resolved_executable(executable: str) -> str:
    if Path(executable).name.casefold() in {"python", "python.exe"}:
        return sys.executable
    return executable


class _ProcessTree(AbstractContextManager["_ProcessTree"]):
    def assign(self, process: subprocess.Popen[str]) -> None:
        del process

    def terminate(self, process: subprocess.Popen[str]) -> None:
        if os.name == "nt":
            process.kill()
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)  # type: ignore[attr-defined]
        except ProcessLookupError:
            pass

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class _WindowsJob(_ProcessTree):
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        configured = kernel32.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        if not configured:
            kernel32.CloseHandle(handle)
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        self._ctypes: Any = ctypes
        self._kernel32: Any = kernel32
        self._handle: Any = handle

    def assign(self, process: subprocess.Popen[str]) -> None:
        process_handle = self._ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
        if not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            raise OSError(self._ctypes.get_last_error(), "AssignProcessToJobObject failed")

    def terminate(self, process: subprocess.Popen[str]) -> None:
        del process
        self._kernel32.TerminateJobObject(self._handle, 1)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._kernel32.CloseHandle(self._handle)


def _job_context() -> _ProcessTree:
    if os.name == "nt":
        return _WindowsJob()
    return _ProcessTree()
