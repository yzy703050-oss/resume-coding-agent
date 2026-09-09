"""Typer command-line entry point and dependency composition."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from pydantic import SecretStr, ValidationError

from coding_agent.agent.runner import AgentRunner
from coding_agent.agent.state import RunLimits, RunState, RunStatus
from coding_agent.config import RunConfig
from coding_agent.context.builder import ContextBuilder
from coding_agent.events.artifacts import Finalizer
from coding_agent.events.writer import EventWriter
from coding_agent.execution.local import LocalExecutionBackend
from coding_agent.execution.policy import CommandPolicy
from coding_agent.models.base import ModelClient, ModelResponse
from coding_agent.models.openai_compatible import OpenAICompatibleClient
from coding_agent.models.scripted import ScriptedModelClient
from coding_agent.tools.git import GitError, current_head, git_diff, require_clean_worktree
from coding_agent.tools.registry import ToolContext, ToolRegistry

app = typer.Typer(no_args_is_help=True, help="Inspectable local coding-agent baseline.")


@app.callback()
def main() -> None:
    """Run inspectable coding-agent tasks."""


@dataclass(frozen=True)
class BuiltRun:
    runner: AgentRunner
    state: RunState


def build_runner(config: RunConfig, model_client: ModelClient | None = None) -> BuiltRun:
    repository = config.repository.resolve(strict=True)
    require_clean_worktree(repository)
    base_commit = current_head(repository)
    state = RunState.start(
        repository,
        config.task,
        base_commit,
        RunLimits(
            max_steps=config.max_steps,
            max_tokens=config.max_tokens,
            max_cost_usd=config.max_cost_usd,
        ),
    )
    run_dir = config.artifacts_dir.resolve() / state.run_id
    secrets = (
        {config.api_key.get_secret_value()}
        if config.api_key is not None
        else set()
    )
    writer = EventWriter(run_dir / "events.jsonl", state.run_id, secrets=secrets)
    backend = LocalExecutionBackend(repository, CommandPolicy.default())
    tools = ToolRegistry.create(
        ToolContext(
            repository,
            base_commit,
            backend,
            writer,
            command_timeout_seconds=config.command_timeout_seconds,
        )
    )
    model = model_client or _model_from_config(config)
    finalizer = Finalizer(writer, lambda: git_diff(repository, base_commit).patch)
    runner = AgentRunner(
        model,
        ContextBuilder(config.context_max_chars, config.pinned_max_chars),
        tools,
        writer,
        finalizer,
    )
    return BuiltRun(runner, state)


def _model_from_config(config: RunConfig) -> ModelClient:
    if config.script is not None:
        try:
            payload = json.loads(config.script.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("script root must be a list")
            return ScriptedModelClient([ModelResponse.model_validate(item) for item in payload])
        except (OSError, ValueError, ValidationError) as error:
            raise ValueError(f"invalid scripted model file: {error}") from error
    if config.api_key is None:
        raise ValueError("API key is required unless --script is supplied")
    return OpenAICompatibleClient(
        config.api_key.get_secret_value(), config.model, config.base_url
    )


@app.command()
def run(
    repository: Annotated[Path, typer.Argument(help="Trusted local Git repository")],
    task: Annotated[str, typer.Option("--task", help="Coding task or issue")],
    model: Annotated[str, typer.Option("--model", help="Model identifier")] = "gpt-5",
    base_url: Annotated[
        str, typer.Option("--base-url", help="OpenAI-compatible API base URL")
    ] = "https://api.openai.com/v1",
    api_key: Annotated[
        str | None, typer.Option("--api-key", help="API key; prefer environment")
    ] = None,
    max_steps: Annotated[int, typer.Option("--max-steps", min=1)] = 20,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens", min=1)] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=0.1, max=600)] = 60,
    context_limit: Annotated[int, typer.Option("--context-limit", min=400)] = 24_000,
    artifacts_dir: Annotated[Path, typer.Option("--artifacts-dir")] = Path("runs"),
    script: Annotated[Path | None, typer.Option("--script", help="Offline response script")] = None,
) -> None:
    """Run on a trusted repository. Local command execution is not a sandbox."""
    try:
        raw_api_key = api_key or os.getenv("OPENAI_API_KEY")
        config = RunConfig(
            repository=repository,
            task=task,
            model=model,
            base_url=base_url,
            api_key=SecretStr(raw_api_key) if raw_api_key else None,
            max_steps=max_steps,
            max_tokens=max_tokens,
            command_timeout_seconds=timeout,
            context_max_chars=context_limit,
            artifacts_dir=artifacts_dir,
            script=script,
        )
        built = build_runner(config)
    except (OSError, GitError, ValueError, ValidationError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(2) from error

    state = built.runner.run(built.state)
    artifacts = built.runner.artifacts
    typer.echo(f"Status: {state.status.value}")
    if artifacts is not None:
        typer.echo(f"Patch: {artifacts.patch_path}")
        typer.echo(f"Summary: {artifacts.summary_path}")
        typer.echo(f"Events: {artifacts.events_path}")
    exit_code = 0 if state.status is RunStatus.COMPLETED else 1
    if exit_code:
        raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
