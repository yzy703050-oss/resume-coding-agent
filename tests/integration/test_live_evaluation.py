from pathlib import Path

from pydantic import SecretStr

from coding_agent.agent.actions import FinishAction, ModelUsage, ToolAction
from coding_agent.config import RunConfig
from coding_agent.evaluation.live import run_live_suite
from coding_agent.evaluation.suite import LiveSuite, load_live_suite
from coding_agent.models.base import ModelClient, ModelResponse
from coding_agent.models.scripted import ScriptedModelClient

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_one_task_flows_through_real_runner_patch_and_trusted_oracle(
    tmp_path: Path,
) -> None:
    complete_suite = load_live_suite(
        FIXTURES / "live_tasks" / "resume-v1",
        FIXTURES / "hidden_oracles" / "resume-v1",
    )
    suite = LiveSuite(complete_suite.name, (complete_suite.tasks[0],))
    seen: list[RunConfig] = []

    def model_factory(config: RunConfig) -> ModelClient:
        seen.append(config)
        usage = ModelUsage(input_tokens=11, output_tokens=4)
        return ScriptedModelClient(
            [
                ModelResponse(
                    action=ToolAction(
                        tool="edit_file",
                        arguments={
                            "path": "app.py",
                            "operation": "replace",
                            "expected_text": "return list(range(n + 1))",
                            "new_text": "return list(range(n))",
                        },
                    ),
                    usage=usage,
                ),
                ModelResponse(
                    action=ToolAction(
                        tool="run_command",
                        arguments={"executable": "python", "args": ["-m", "pytest", "-q"]},
                    ),
                    usage=usage,
                ),
                ModelResponse(action=FinishAction(summary="fixed"), usage=usage),
            ]
        )

    report = run_live_suite(
        tmp_path,
        suite,
        tmp_path / "runs",
        SecretStr("offline-key"),
        model_factory=model_factory,
    )

    assert report.attempted_tasks == report.successes == 1
    assert report.results[0].task_success
    assert report.results[0].trusted_oracle_passed
    assert report.results[0].visible_test_result is True
    assert report.evaluator_version == "resume-v1.0"
    assert report.sample_size == 1
    assert report.python_version
    assert report.package_versions["baseline-coding-agent"] == "0.1.0"
    assert report.provider_sdk_max_retries == 1
    assert report.results[0].input_tokens == 33
    assert report.results[0].output_tokens == 12
    assert len(seen) == 1
    config = seen[0]
    assert config.provider == "deepseek"
    assert config.model == "deepseek-flash"
    assert config.max_steps == 8
    assert config.max_output_tokens == 512
    assert config.max_tokens == 8000
    assert config.memory_preset == "baseline"
    assert config.auxiliary_max_calls == config.auxiliary_max_tokens == 0
    assert config.thinking_enabled is False
    artifact_root = Path(report.results[0].artifact_directory)
    serialized_artifacts = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in artifact_root.rglob("*")
        if path.is_file()
    )
    assert "offline-key" not in serialized_artifacts
