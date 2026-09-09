import json
import subprocess
from pathlib import Path

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
    assert summary["step_count"] == 2
    assert (summaries[0].parent / "patch.diff").read_text(encoding="utf-8")


def test_cli_help_documents_limits_and_trust_boundary() -> None:
    result = CliRunner().invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    for phrase in ["--task", "--model", "--base-url", "--max-steps", "--timeout", "trusted"]:
        assert phrase in result.stdout.lower()
