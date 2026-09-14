import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from coding_agent.cli import app


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "test_app.py").write_text(
        "from app import x\n\ndef test_x():\n    assert x == 2\n", encoding="utf-8"
    )
    git(repo, "init", "-b", "main")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    return repo


def test_cli_rejects_non_git_and_dirty_repository(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = CliRunner().invoke(app, ["run", str(plain), "--task", "fix it"])
    assert result.exit_code == 2
    assert "git repository" in result.stdout.lower()

    repo = clean_repo(tmp_path)
    (repo / "app.py").write_text("dirty\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["run", str(repo), "--task", "fix it"])
    assert result.exit_code == 2
    assert "clean working tree" in result.stdout.lower()


def test_cli_runs_scripted_agent_and_prints_artifacts(tmp_path: Path) -> None:
    repo = clean_repo(tmp_path)
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps(
            [
                {
                    "action": {
                        "kind": "tool",
                        "tool": "edit_file",
                        "arguments": {
                            "path": "app.py",
                            "operation": "replace",
                            "expected_text": "x = 1",
                            "new_text": "x = 2",
                        },
                    }
                },
                {
                    "action": {
                        "kind": "tool",
                        "tool": "run_command",
                        "arguments": {"executable": "python", "args": ["-m", "pytest", "-q"]},
                    }
                },
                {"action": {"kind": "finish", "summary": "done"}},
            ]
        ),
        encoding="utf-8",
    )
    artifacts = tmp_path / "artifacts"
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(repo),
            "--task",
            "change x",
            "--script",
            str(script),
            "--artifacts-dir",
            str(artifacts),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "status: completed" in result.stdout.lower()
    summaries = list(artifacts.glob("*/summary.json"))
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["step_count"] == 3
    assert summary["latest_test_result"]["ok"] is True
    assert summary["configuration"] == {
        "model": "gpt-5",
        "base_url": "https://api.openai.com/v1",
        "command_timeout_seconds": 60.0,
        "context_max_chars": 24000,
        "pinned_max_chars": 12000,
        "model_mode": "scripted",
        "memory_preset": "baseline",
        "auxiliary_max_calls": 0,
        "auxiliary_max_tokens": 0,
        "auxiliary_max_cost_usd": None,
    }
    events = [
        json.loads(line)
        for line in (summaries[0].parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[0]["type"] == "TaskStarted"
    assert events[0]["payload"]["configuration"] == summary["configuration"]
    assert (summaries[0].parent / "patch.diff").read_text(encoding="utf-8")


def test_cli_help_documents_limits_and_trust_boundary() -> None:
    result = CliRunner().invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    for phrase in ["--task", "--model", "--base-url", "--max-steps", "--timeout", "trusted"]:
        assert phrase in result.stdout.lower()


def test_invalid_script_does_not_create_partial_run_directory(tmp_path: Path) -> None:
    repo = clean_repo(tmp_path)
    script = tmp_path / "bad.json"
    script.write_text("not json", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(repo),
            "--task",
            "fix",
            "--script",
            str(script),
            "--artifacts-dir",
            str(artifacts),
        ],
    )
    assert result.exit_code == 2
    assert not artifacts.exists()


def test_cli_rejects_artifact_directory_inside_target_repository(tmp_path: Path) -> None:
    repo = clean_repo(tmp_path)
    script = tmp_path / "finish.json"
    script.write_text('[{"action":{"kind":"finish","summary":"done"}}]', encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(repo),
            "--task",
            "fix",
            "--script",
            str(script),
            "--artifacts-dir",
            str(repo / "runs"),
        ],
    )
    assert result.exit_code == 2
    assert "outside" in result.stdout.lower()
    assert not (repo / "runs").exists()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:url-secret@example.test/v1",
        "https://example.test/v1?api_key=url-secret",
    ],
)
def test_cli_rejects_credential_bearing_base_url_without_leaking_it(
    tmp_path: Path, base_url: str
) -> None:
    repo = clean_repo(tmp_path)
    script = tmp_path / "finish.json"
    script.write_text('[{"action":{"kind":"finish","summary":"done"}}]', encoding="utf-8")
    artifacts = tmp_path / "artifacts"

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(repo),
            "--task",
            "fix",
            "--base-url",
            base_url,
            "--script",
            str(script),
            "--artifacts-dir",
            str(artifacts),
        ],
    )

    assert result.exit_code == 2
    assert "url-secret" not in result.stdout
    assert not artifacts.exists()
