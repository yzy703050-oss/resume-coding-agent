from pathlib import Path

import pytest

from coding_agent.evaluation.fixtures import (
    apply_gold,
    load_manifest,
    prepare_fixture,
    run_oracle,
)

TASKS = Path(__file__).parents[1] / "fixtures" / "tasks"


@pytest.mark.parametrize("task_dir", sorted(TASKS.iterdir()))
def test_initial_fixture_fails_and_gold_passes(tmp_path: Path, task_dir: Path) -> None:
    manifest = load_manifest(task_dir / "task.json")
    repo = prepare_fixture(manifest, tmp_path / manifest.id)
    assert run_oracle(repo, manifest.oracle_command).returncode != 0
    apply_gold(repo, manifest.gold_files)
    assert run_oracle(repo, manifest.oracle_command).returncode == 0
