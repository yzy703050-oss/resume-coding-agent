"""Reproducible three-task scripted baseline command."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import cast

from coding_agent.agent.actions import FinishAction, JsonValue, ModelUsage, ToolAction
from coding_agent.evaluation.fixtures import TaskManifest, load_manifest
from coding_agent.evaluation.runner import MemoryPreset, aggregate_results, evaluate_fixture
from coding_agent.models.base import ModelResponse
from coding_agent.models.scripted import ScriptedModelClient


def _tool(name: str, **arguments: object) -> ModelResponse:
    return ModelResponse(
        action=ToolAction(tool=name, arguments=cast(dict[str, JsonValue], arguments))
    )


def _responses(manifest: TaskManifest) -> list[ModelResponse]:
    edits = {
        "off-by-one": _tool(
            "edit_file",
            path="app.py",
            operation="replace",
            expected_text="return list(range(n + 1))",
            new_text="return list(range(n))",
        ),
        "add-regression-test": _tool(
            "edit_file",
            path="test_mathutil.py",
            operation="create",
            new_text=(
                "from mathutil import multiply\n\n"
                "def test_multiply():\n    assert multiply(6, 7) == 42\n"
            ),
        ),
        "change-contract": _tool(
            "edit_file",
            path="app.py",
            operation="replace",
            expected_text="return f'Hello {name}'",
            new_text="return f'Hello {name.upper()}'",
        ),
    }
    return [
        edits[manifest.id],
        _tool("run_command", executable=sys.executable, args=["-m", "pytest", "-q"]),
        ModelResponse(
            action=FinishAction(summary="fixture repaired and independently verified"),
            usage=ModelUsage(input_tokens=1),
        ),
    ]


def run_scripted_baseline(tasks_root: Path, workspace: Path) -> dict[str, object]:
    manifests = [load_manifest(path) for path in sorted(tasks_root.glob("*/task.json"))]
    results = [
        evaluate_fixture(manifest, workspace, ScriptedModelClient(_responses(manifest)))
        for manifest in manifests
    ]
    return aggregate_results(results)


def run_scripted_presets(
    tasks_root: Path, workspace: Path, presets: tuple[MemoryPreset, ...]
) -> dict[str, object]:
    manifests = [load_manifest(path) for path in sorted(tasks_root.glob("*/task.json"))]
    return {
        preset: aggregate_results(
            [
                evaluate_fixture(
                    manifest,
                    workspace / preset,
                    ScriptedModelClient(_responses(manifest)),
                    memory_preset=preset,
                )
                for manifest in manifests
            ]
        )
        for preset in presets
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deterministic local coding-agent baseline"
    )
    parser.add_argument("--tasks", type=Path, default=Path("tests/fixtures/tasks"))
    parser.add_argument("--output", type=Path, default=Path("benchmarks/baseline-scripted.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="coding-agent-baseline-") as temporary:
        report = run_scripted_baseline(args.tasks, Path(temporary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
