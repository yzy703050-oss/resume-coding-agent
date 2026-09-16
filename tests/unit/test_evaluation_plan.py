from pathlib import Path

import pytest

from coding_agent.evaluation.plan import build_evaluation_plan


def test_plan_lists_tasks_but_never_claims_model_results() -> None:
    plan = build_evaluation_plan(Path("tests/fixtures/tasks"))
    assert plan["status"] == "not_run"
    assert plan["evaluation_kind"] == "protocol_only"
    assert plan["task_count"] == 3
    assert plan["model"] == "deepseek-flash"
    assert plan["presets"] == ["baseline", "full"]
    assert plan["metrics"] == {
        "autonomous_success_rate": None,
        "total_tokens": None,
        "cost_usd": None,
        "median_elapsed_seconds": None,
    }
    assert plan["api_calls_made"] == 0


def test_plan_rejects_empty_suite_instead_of_implying_evaluation_ready(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no task manifests"):
        build_evaluation_plan(tmp_path)
