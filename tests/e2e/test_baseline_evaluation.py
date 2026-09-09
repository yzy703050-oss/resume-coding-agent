import sys
from pathlib import Path

import pytest

from coding_agent.agent.actions import FinishAction, ModelUsage, ToolAction
from coding_agent.evaluation.baseline import run_scripted_baseline
from coding_agent.evaluation.fixtures import load_manifest
from coding_agent.evaluation.runner import evaluate_fixture
from coding_agent.models.base import ModelResponse
from coding_agent.models.scripted import ScriptedModelClient

TASKS = Path(__file__).parents[1] / "fixtures" / "tasks"


def finish(summary: str) -> ModelResponse:
    return ModelResponse(action=FinishAction(summary=summary), usage=ModelUsage(input_tokens=1))


def edit(**arguments: object) -> ModelResponse:
    return ModelResponse(action=ToolAction(tool="edit_file", arguments=arguments))


def test_finish_text_cannot_override_failed_oracle(tmp_path: Path) -> None:
    manifest = load_manifest(TASKS / "off-by-one" / "task.json")
    result = evaluate_fixture(manifest, tmp_path, ScriptedModelClient([finish("all tests pass")]))
    assert not result.task_success
    assert result.agent_status == "completed"
    assert result.oracle_exit_code != 0


@pytest.mark.parametrize(
    ("task_id", "action"),
    [
        (
            "off-by-one",
            edit(
                path="app.py",
                operation="replace",
                expected_text="return list(range(n + 1))",
                new_text="return list(range(n))",
            ),
        ),
        (
            "add-regression-test",
            edit(
                path="test_mathutil.py",
                operation="create",
                new_text=(
                    "from mathutil import multiply\n\n"
                    "def test_multiply():\n    assert multiply(6, 7) == 42\n"
                ),
            ),
        ),
        (
            "change-contract",
            edit(
                path="app.py",
                operation="replace",
                expected_text="return f'Hello {name}'",
                new_text="return f'Hello {name.upper()}'",
            ),
        ),
    ],
)
def test_scripted_trajectory_passes_independent_oracle(
    tmp_path: Path, task_id: str, action: ModelResponse
) -> None:
    manifest = load_manifest(TASKS / task_id / "task.json")
    run_tests = ModelResponse(
        action=ToolAction(
            tool="run_command",
            arguments={"executable": sys.executable, "args": ["-m", "pytest", "-q"]},
        )
    )
    result = evaluate_fixture(
        manifest,
        tmp_path,
        ScriptedModelClient([action, run_tests, finish("verified")]),
    )
    assert result.task_success
    assert result.agent_status == "completed"
    assert result.oracle_exit_code == 0
    assert result.steps == 3
    assert result.tool_counts == {"edit_file": 1, "run_command": 1}
    assert result.tokens == 1
    assert result.cost_usd is None
    assert result.patch_path.exists()


def test_scripted_baseline_aggregates_all_three_tasks(tmp_path: Path) -> None:
    report = run_scripted_baseline(TASKS, tmp_path)
    assert report["tasks"] == 3
    assert report["successes"] == 3
    assert report["success_rate"] == 1.0
    assert all(
        set(item)
        == {
            "task_id",
            "success",
            "steps",
            "tool_counts",
            "elapsed_ms",
            "tokens",
            "cost_usd",
        }
        for item in report["results"]
    )
