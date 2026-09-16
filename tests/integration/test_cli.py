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
        "provider": "openai-compatible",
        "orchestrator": "langgraph",
        "model_adapter": "scripted",
        "base_url": "https://api.openai.com/v1",
        "max_output_tokens": 1024,
        "thinking_enabled": None,
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


def test_deepseek_preset_is_recorded_without_exposing_environment_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = clean_repo(tmp_path)
    script = tmp_path / "finish.json"
    script.write_text('[{"action":{"kind":"finish","summary":"done"}}]', encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-secret")
    artifacts = tmp_path / "artifacts"
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(repo),
            "--task",
            "fix",
            "--provider",
            "deepseek",
            "--script",
            str(script),
            "--artifacts-dir",
            str(artifacts),
            "--max-output-tokens",
            "512",
        ],
    )
    assert result.exit_code == 0, result.stdout
    summary = next(artifacts.glob("*/summary.json")).read_text(encoding="utf-8")
    config = json.loads(summary)["configuration"]
    assert config["model"] == "deepseek-flash"
    assert config["base_url"] == "https://api.deepseek.com"
    assert config["max_output_tokens"] == 512
    assert config["thinking_enabled"] is False
    assert "deepseek-test-secret" not in summary


def test_live_cli_uses_langchain_inside_graph_with_mock_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    import coding_agent.cli as cli
    from coding_agent.models.langchain_client import create_langchain_model

    repo = clean_repo(tmp_path)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "cli-response",
                "object": "chat.completion",
                "created": 1,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "finish-1",
                                    "type": "function",
                                    "function": {
                                        "name": "finish",
                                        "arguments": '{"summary":"done"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        )

    monkeypatch.setattr(
        cli,
        "create_langchain_model",
        lambda config: create_langchain_model(
            config,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-live-key")
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-provider-key")
    artifacts = tmp_path / "artifacts"
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(repo),
            "--task",
            "inspect",
            "--provider",
            "deepseek",
            "--artifacts-dir",
            str(artifacts),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert len(seen) == 1
    assert seen[0].headers["authorization"] == "Bearer offline-live-key"
    summary_text = next(artifacts.glob("*/summary.json")).read_text(encoding="utf-8")
    summary = json.loads(summary_text)
    assert summary["configuration"]["orchestrator"] == "langgraph"
    assert summary["configuration"]["model_adapter"] == "langchain"
    assert summary["usage"]["combined_total_tokens"] == 8
    assert "offline-live-key" not in summary_text


def test_injected_scripted_model_is_not_reported_as_live_langchain(tmp_path: Path) -> None:
    from coding_agent.agent.actions import FinishAction
    from coding_agent.cli import build_runner
    from coding_agent.config import RunConfig
    from coding_agent.models.base import ModelResponse
    from coding_agent.models.scripted import ScriptedModelClient

    built = build_runner(
        RunConfig(repository=clean_repo(tmp_path), task="inspect", artifacts_dir=tmp_path / "runs"),
        ScriptedModelClient([ModelResponse(action=FinishAction(summary="done"))]),
    )
    built.runner.run(built.state)
    assert built.state.effective_config["model_adapter"] == "scripted"
    assert built.state.effective_config["model_mode"] == "scripted"


def test_programmatic_deepseek_config_records_effective_non_thinking(tmp_path: Path) -> None:
    from pydantic import SecretStr

    from coding_agent.cli import build_runner
    from coding_agent.config import RunConfig

    built = build_runner(
        RunConfig(
            repository=clean_repo(tmp_path),
            task="inspect",
            artifacts_dir=tmp_path / "runs",
            provider="deepseek",
            model="deepseek-flash",
            base_url="https://api.deepseek.com",
            api_key=SecretStr("offline-constructor-key"),
        )
    )
    assert built.state.effective_config["thinking_enabled"] is False


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
