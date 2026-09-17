"""Single-process, local-only HTTP wrapper for trusted coding-agent runs.

Start with ``uvicorn coding_agent.api:app --host 127.0.0.1 --port 8000``.
Do not use multiple workers: reservations and job state live in this process.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal

import uvicorn
from dotenv import dotenv_values
from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from coding_agent.cli import BuiltRun, build_runner
from coding_agent.config import RunConfig

API_MAX_STEPS = 8
API_MAX_TOKENS = 16_000
API_MAX_OUTPUT_TOKENS = 1_024


class RunRequest(BaseModel):
    """Only task inputs; credentials and spending limits are server-owned."""

    model_config = ConfigDict(extra="forbid")

    repository: Path
    task: str = Field(min_length=1, max_length=20_000)


@dataclass
class _Job:
    built: BuiltRun
    repository: Path
    phase: Literal["queued", "running", "finished", "failed"] = "queued"


class _Jobs:
    """In-memory jobs and per-repository reservations for one API worker."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, _Job] = {}
        self._active_repositories: set[Path] = set()

    def submit(self, request: RunRequest) -> str:
        try:
            repository = request.repository.expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "repository does not exist") from None
        if not repository.is_dir():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "repository must be a directory")

        with self._lock:
            if repository in self._active_repositories:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "repository already has an active run"
                )
            self._active_repositories.add(repository)

        submitted = False
        try:
            key = os.getenv("DEEPSEEK_API_KEY") or dotenv_values(Path.cwd() / ".env").get(
                "DEEPSEEK_API_KEY"
            )
            if not isinstance(key, str) or not key.strip():
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "DEEPSEEK_API_KEY is not configured",
                )
            config = RunConfig(
                repository=repository,
                task=request.task,
                provider="deepseek",
                model="deepseek-flash",
                base_url="https://api.deepseek.com",
                api_key=SecretStr(key),
                thinking_enabled=False,
                max_steps=API_MAX_STEPS,
                max_tokens=API_MAX_TOKENS,
                max_output_tokens=API_MAX_OUTPUT_TOKENS,
                memory_preset="baseline",
            )
            built = build_runner(config)
            run_id = built.state.run_id
            with self._lock:
                self._jobs[run_id] = _Job(built=built, repository=repository)
            submitted = True
            return run_id
        except HTTPException:
            raise
        except Exception:
            # Git and model construction errors may contain local or provider details.
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "could not prepare run; check the repository and server configuration",
            ) from None
        finally:
            if not submitted:
                with self._lock:
                    self._active_repositories.discard(repository)

    def execute(self, run_id: str) -> None:
        with self._lock:
            job = self._jobs[run_id]
            job.phase = "running"
        try:
            job.built.runner.run(job.built.state)
            with self._lock:
                job.phase = "finished"
        except Exception:
            # Never return raw exception text: model clients may include credentials.
            with self._lock:
                job.phase = "failed"
        finally:
            with self._lock:
                self._active_repositories.discard(job.repository)

    def get(self, run_id: str) -> _Job:
        with self._lock:
            job = self._jobs.get(run_id)
            if job is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
            return job

    def snapshot(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(run_id)
            if job is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
            run = job.built.state
            return {
                "run_id": run_id,
                "phase": job.phase,
                "status": run.status.value if job.phase == "finished" else None,
                "step_count": run.step_count if job.phase == "finished" else None,
                "total_tokens": run.total_tokens if job.phase == "finished" else None,
                "result_url": f"/runs/{run_id}/result" if job.phase == "finished" else None,
            }


def create_app() -> FastAPI:
    """Create one process-local API instance; no durable queue or run resumption."""

    app = FastAPI(title="Local Coding Agent API")
    jobs = _Jobs()

    @app.post("/runs", status_code=status.HTTP_202_ACCEPTED)
    def submit_run(request: RunRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
        run_id = jobs.submit(request)
        background_tasks.add_task(jobs.execute, run_id)
        return {"run_id": run_id, "status_url": f"/runs/{run_id}"}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        return jobs.snapshot(run_id)

    @app.get("/runs/{run_id}/result")
    def get_result(run_id: str) -> dict[str, Any]:
        job = jobs.get(run_id)
        if job.phase != "finished":
            raise HTTPException(status.HTTP_409_CONFLICT, "run result is not available")
        artifacts = job.built.runner.artifacts
        if artifacts is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "run artifacts are missing")
        try:
            summary = json.loads(artifacts.summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "run summary is unavailable"
            ) from None
        return {"summary": summary, "patch_url": f"/runs/{run_id}/patch"}

    @app.get("/runs/{run_id}/patch")
    def get_patch(run_id: str) -> FileResponse:
        job = jobs.get(run_id)
        if job.phase != "finished":
            raise HTTPException(status.HTTP_409_CONFLICT, "run patch is not available")
        artifacts = job.built.runner.artifacts
        if artifacts is None or not artifacts.patch_path.is_file():
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "run patch is unavailable")
        return FileResponse(artifacts.patch_path, media_type="text/x-diff")

    return app


app = create_app()


def main() -> None:
    """Run the deliberately loopback-only, single-worker local server."""

    uvicorn.run("coding_agent.api:app", host="127.0.0.1", port=8000, workers=1)
