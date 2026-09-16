from pathlib import Path

from coding_agent.evaluation.suite import RESUME_V1_TASK_IDS, load_live_suite

ROOT = Path(__file__).parents[2] / "fixtures"


def test_resume_v1_has_exact_frozen_order() -> None:
    suite = load_live_suite(
        ROOT / "live_tasks" / "resume-v1",
        ROOT / "hidden_oracles" / "resume-v1",
    )
    assert (
        suite.task_ids
        == RESUME_V1_TASK_IDS
        == (
            "off-by-one",
            "change-contract",
            "add-regression-test",
            "empty-mean",
            "parse-port",
            "normalize-tags",
            "category-totals",
            "optional-display-name",
            "json-omit-none",
            "stable-priority",
            "package-export",
            "recover-failing-test",
        )
    )
    assert len(set(suite.task_ids)) == 12


def test_every_task_has_gold_and_evaluator_owned_oracle() -> None:
    suite = load_live_suite(
        ROOT / "live_tasks" / "resume-v1",
        ROOT / "hidden_oracles" / "resume-v1",
    )
    for task in suite.tasks:
        assert task.manifest.gold_files
        assert task.oracle.task_id == task.manifest.id
        assert task.oracle.kind in {"pytest", "mutation"}
        if task.oracle.kind == "pytest":
            assert task.oracle.hidden_files
        else:
            assert task.oracle.mutation_files
