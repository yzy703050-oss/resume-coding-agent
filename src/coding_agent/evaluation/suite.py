"""Frozen live-evaluation suite and evaluator-owned oracle metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.evaluation.fixtures import TaskManifest, load_manifest

RESUME_V1_TASK_IDS = (
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


class OracleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    kind: Literal["pytest", "mutation"]
    hidden_files: tuple[str, ...] = ()
    mutation_files: dict[str, str] = Field(default_factory=dict)


class _SuiteIndex(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    tasks: tuple[str, ...]


@dataclass(frozen=True)
class LiveTask:
    manifest: TaskManifest
    oracle: OracleSpec
    oracle_root: Path


@dataclass(frozen=True)
class LiveSuite:
    name: str
    tasks: tuple[LiveTask, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.manifest.id for task in self.tasks)


def load_live_suite(tasks_root: Path, oracle_root: Path) -> LiveSuite:
    index = _SuiteIndex.model_validate_json((tasks_root / "suite.json").read_text("utf-8"))
    if index.name != "resume-v1" or index.tasks != RESUME_V1_TASK_IDS:
        raise ValueError("resume-v1 suite order does not match the frozen task list")
    if len(set(index.tasks)) != len(index.tasks):
        raise ValueError("duplicate live evaluation task id")

    tasks: list[LiveTask] = []
    for task_id in index.tasks:
        manifest = load_manifest(tasks_root / task_id / "task.json")
        task_oracle_root = (oracle_root / task_id).resolve()
        oracle = OracleSpec.model_validate_json(
            (task_oracle_root / "oracle.json").read_text(encoding="utf-8")
        )
        if manifest.id != task_id or oracle.task_id != task_id:
            raise ValueError(f"task identity mismatch for {task_id}")
        for relative in oracle.hidden_files:
            path = (task_oracle_root / relative).resolve()
            if not path.is_relative_to(task_oracle_root) or not path.is_file():
                raise ValueError(f"invalid hidden oracle path for {task_id}: {relative}")
        tasks.append(LiveTask(manifest, oracle, task_oracle_root))

    declared_dirs = {
        path.name
        for path in tasks_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    if declared_dirs != set(index.tasks):
        raise ValueError("live task directories do not match suite index")
    return LiveSuite(index.name, tuple(tasks))
