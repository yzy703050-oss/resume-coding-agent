from pathlib import Path

import pytest

from coding_agent.evaluation.fixtures import apply_gold, prepare_fixture
from coding_agent.evaluation.suite import RESUME_V1_TASK_IDS, LiveTask, load_live_suite
from coding_agent.evaluation.trusted_oracle import judge_patch
from coding_agent.tools.git import current_head, git_diff

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


@pytest.mark.parametrize("task_id", RESUME_V1_TASK_IDS)
def test_every_initial_fails_and_gold_passes_trusted_oracle(tmp_path: Path, task_id: str) -> None:
    suite = load_live_suite(
        ROOT / "live_tasks" / "resume-v1",
        ROOT / "hidden_oracles" / "resume-v1",
    )
    task: LiveTask = next(item for item in suite.tasks if item.manifest.id == task_id)

    initial = judge_patch(task, "", tmp_path / "initial-evaluation")
    assert initial.patch_applied
    assert not initial.trusted_oracle_passed

    agent_repo = prepare_fixture(task.manifest, tmp_path / "agent")
    base = current_head(agent_repo)
    apply_gold(agent_repo, task.manifest.gold_files)
    patch = git_diff(agent_repo, base).patch
    gold = judge_patch(task, patch, tmp_path / "gold-evaluation")
    assert gold.patch_applied
    assert gold.trusted_oracle_passed
