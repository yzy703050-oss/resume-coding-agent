from pathlib import Path

import pytest

from coding_agent.evaluation.fixtures import apply_gold, prepare_fixture
from coding_agent.evaluation.suite import LiveSuite, LiveTask, load_live_suite
from coding_agent.evaluation.trusted_oracle import judge_patch, oracle_environment
from coding_agent.tools.git import current_head, git_diff

FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.fixture(scope="module")
def live_suite() -> LiveSuite:
    return load_live_suite(
        FIXTURES / "live_tasks" / "resume-v1",
        FIXTURES / "hidden_oracles" / "resume-v1",
    )


@pytest.fixture
def off_by_one(live_suite: LiveSuite) -> LiveTask:
    return next(task for task in live_suite.tasks if task.manifest.id == "off-by-one")


@pytest.fixture
def add_regression_test(live_suite: LiveSuite) -> LiveTask:
    return next(task for task in live_suite.tasks if task.manifest.id == "add-regression-test")


def gold_patch(task: LiveTask, root: Path) -> tuple[Path, str]:
    repo = prepare_fixture(task.manifest, root)
    base = current_head(repo)
    apply_gold(repo, task.manifest.gold_files)
    return repo, git_diff(repo, base).patch


def test_hidden_files_never_exist_in_agent_fixture(tmp_path: Path, off_by_one: LiveTask) -> None:
    agent_repo = prepare_fixture(off_by_one.manifest, tmp_path / "agent")
    assert not any(path.name == "test_hidden.py" for path in agent_repo.rglob("*"))


def test_gold_patch_applies_to_fresh_copy_and_passes_hidden_oracle(
    tmp_path: Path, off_by_one: LiveTask
) -> None:
    agent_repo, patch = gold_patch(off_by_one, tmp_path / "agent")
    result = judge_patch(off_by_one, patch, tmp_path / "evaluation")
    assert result.patch_applied
    assert result.trusted_oracle_passed
    assert result.judge_repository != agent_repo


def test_visible_test_tampering_does_not_remove_hidden_oracle(
    tmp_path: Path, off_by_one: LiveTask
) -> None:
    agent_repo = prepare_fixture(off_by_one.manifest, tmp_path / "agent")
    base = current_head(agent_repo)
    (agent_repo / "test_app.py").write_text(
        "def test_vacuous():\n    assert True\n", encoding="utf-8"
    )
    patch = git_diff(agent_repo, base).patch
    result = judge_patch(off_by_one, patch, tmp_path / "evaluation")
    assert result.patch_applied
    assert not result.trusted_oracle_passed
    assert result.failure_category == "hidden_oracle_failed"


def test_regression_test_must_kill_mutation(tmp_path: Path, add_regression_test: LiveTask) -> None:
    agent_repo = prepare_fixture(add_regression_test.manifest, tmp_path / "agent")
    base = current_head(agent_repo)
    (agent_repo / "test_mathutil.py").write_text(
        "def test_vacuous():\n    assert True\n", encoding="utf-8"
    )
    patch = git_diff(agent_repo, base).patch
    result = judge_patch(add_regression_test, patch, tmp_path / "evaluation")
    assert not result.trusted_oracle_passed
    assert result.failure_category == "mutation_survived"


def test_patch_rejection_is_a_typed_failure(tmp_path: Path, off_by_one: LiveTask) -> None:
    result = judge_patch(
        off_by_one,
        "not a unified diff\n",
        tmp_path / "evaluation",
    )
    assert not result.patch_applied
    assert not result.trusted_oracle_passed
    assert result.failure_category == "patch_apply_failed"
    assert result.oracle_exit_code is None


@pytest.mark.parametrize("key", ["DEEPSEEK_API_KEY", "OPENAI_API_KEY"])
def test_key_is_removed_from_oracle_environment(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv(key, "never-forward-this")
    sanitized = oracle_environment()
    assert key not in sanitized


def test_oracle_environment_does_not_mutate_input() -> None:
    source = {
        "PATH": "safe-path",
        "DEEPSEEK_API_KEY": "secret",
        "OPENAI_API_KEY": "other-secret",
    }
    assert oracle_environment(source) == {"PATH": "safe-path"}
    assert source["DEEPSEEK_API_KEY"] == "secret"
