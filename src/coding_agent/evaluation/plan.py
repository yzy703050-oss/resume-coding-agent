"""Read-only evaluation protocol: no clients, agent runs, subprocesses or API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from coding_agent.evaluation.fixtures import load_manifest


def build_evaluation_plan(tasks_root: Path) -> dict[str, object]:
    manifests = [load_manifest(path) for path in sorted(tasks_root.glob("*/task.json"))]
    if not manifests:
        raise ValueError("no task manifests found")
    ids = [manifest.id for manifest in manifests]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    return {
        "schema_version": 1,
        "status": "not_run",
        "evaluation_kind": "protocol_only",
        "model": "deepseek-flash",
        "base_url": "https://api.deepseek.com",
        "thinking_enabled": False,
        "task_count": len(manifests),
        "tasks": [{"id": manifest.id, "task": manifest.task} for manifest in manifests],
        "presets": ["baseline", "full"],
        "future_limits": {
            "max_steps_per_run": 8,
            "max_output_tokens_per_call": 1024,
            "reported_token_stop_threshold_per_run": 12000,
            "auxiliary_model_calls": 0,
            "repeats": 1,
        },
        "api_calls_made": 0,
        "metrics": {
            "autonomous_success_rate": None,
            "total_tokens": None,
            "cost_usd": None,
            "median_elapsed_seconds": None,
        },
        "required_before_live_evaluation": [
            "Create evaluator-owned hidden tests outside agent-visible workspace",
            "Apply patch to fresh fixture and restore trusted tests before oracle",
            "Record task/commit/model/preset/prompt versions and raw usage",
            "Isolate project-memory DB per ablation; share only for sequential memory tests",
            "Obtain explicit approval for paid calls and account spending limit",
        ],
        "warnings": [
            "Existing scripted fixtures contain predetermined edits, not autonomous results",
            "Existing oracle tests are visible and mutable; not a trusted hidden-test benchmark",
            "Token threshold is post-response accounting, not a guaranteed billing hard cap",
            "Small samples and single repeats cannot establish general coding capability",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=Path("tests/fixtures/tasks"))
    args = parser.parse_args()
    try:
        plan = build_evaluation_plan(args.tasks)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(plan, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
