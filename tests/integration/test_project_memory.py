import subprocess
from pathlib import Path

from coding_agent.agent.actions import FinishAction
from coding_agent.cli import build_runner
from coding_agent.config import RunConfig
from coding_agent.models.base import ModelResponse
from coding_agent.models.scripted import ScriptedModelClient


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_full_preset_recalls_project_memory_across_independent_runs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "init")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    artifacts = tmp_path / "artifacts"

    first_model = ScriptedModelClient(
        [ModelResponse(action=FinishAction(summary="Use pytest for verification"))]
    )
    first = build_runner(
        RunConfig(
            repository=repo,
            task="record testing convention",
            artifacts_dir=artifacts,
            memory_preset="full",
        ),
        first_model,
    )
    first.runner.run(first.state)

    second_model = ScriptedModelClient(
        [ModelResponse(action=FinishAction(summary="checked memory"))]
    )
    second = build_runner(
        RunConfig(
            repository=repo,
            task="what pytest convention is used?",
            artifacts_dir=artifacts,
            memory_preset="full",
        ),
        second_model,
    )
    second.runner.run(second.state)

    rendered = "\n".join(message.content for message in second_model.received_messages[0])
    assert "Use pytest for verification" in rendered
    assert (artifacts / "project-memory.sqlite3").is_file()
