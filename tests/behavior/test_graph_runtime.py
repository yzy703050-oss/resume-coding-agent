import json

from conftest import finish, tool
from langsmith import tracing_context

from coding_agent.agent.state import RunLimits, RunStatus
from coding_agent.models.base import ModelFormatError


def terminal_events(run_dir):
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    return [event for event in events if event["type"] in {"AgentFinished", "AgentFailed"}]


def test_context_start_failure_still_finalizes(agent_harness, monkeypatch) -> None:
    harness = agent_harness([finish("done")])

    def fail():
        raise RuntimeError("private startup detail")

    monkeypatch.setattr(harness.context_manager, "start_run", fail)
    assert harness.runner.run(harness.state).status is RunStatus.FAILED
    assert len(harness.model.received_messages) == 0
    assert len(terminal_events(harness.run_dir)) == 1
    assert (harness.run_dir / "summary.json").exists()


def test_memory_finish_failure_does_not_lose_patch_and_terminal_event(
    agent_harness,
    monkeypatch,
) -> None:
    harness = agent_harness([finish("done")])

    def fail(state):
        raise RuntimeError("private memory detail")

    monkeypatch.setattr(harness.context_manager, "finish_run", fail)
    assert harness.runner.run(harness.state).status is RunStatus.COMPLETED
    assert len(terminal_events(harness.run_dir)) == 1
    summary = json.loads((harness.run_dir / "summary.json").read_text())
    assert summary["memory_metrics"]["finish_error"] == "RuntimeError"
    assert "private memory detail" not in json.dumps(summary)
    assert (harness.run_dir / "patch.diff").exists()


def test_graph_recursion_does_not_confuse_agent_steps_with_node_steps(agent_harness) -> None:
    harness = agent_harness(
        [tool("read_file", path="calc.py") for _ in range(12)] + [finish("done")],
        RunLimits(max_steps=13),
    )
    assert harness.runner.run(harness.state).status is RunStatus.COMPLETED
    assert harness.state.step_count == 13
    assert len(harness.model.received_messages) == 13
    assert len(terminal_events(harness.run_dir)) == 1


def test_format_error_does_not_reexecute_previous_tool_action(agent_harness) -> None:
    harness = agent_harness(
        [
            tool(
                "edit_file",
                path="calc.py",
                operation="replace",
                expected_text="return a-b",
                new_text="return a+b",
            ),
            ModelFormatError("invalid action"),
            finish("done"),
        ]
    )
    assert harness.runner.run(harness.state).status is RunStatus.COMPLETED
    assert harness.state.tool_counts["edit_file"] == 1
    assert harness.state.step_count == 3
    events = [
        json.loads(line) for line in (harness.run_dir / "events.jsonl").read_text().splitlines()
    ]
    calls = [event for event in events if event["type"] == "ToolCalled"]
    assert len(calls) == 1
    assert calls[0]["correlation_id"] == "step-1"


def test_public_compiled_graph_has_separate_decision_execution_and_observation(
    agent_harness,
) -> None:
    harness = agent_harness([tool("read_file", path="calc.py"), finish("done")])
    with tracing_context(enabled=False):
        updates = list(
            harness.runner.graph.stream(
                {"run": harness.state},
                config={"recursion_limit": 30},
                stream_mode="updates",
            )
        )
    assert [next(iter(update)) for update in updates] == [
        "guard",
        "prepare",
        "decide",
        "execute",
        "observe",
        "guard",
        "prepare",
        "decide",
    ]
    assert harness.state.status is RunStatus.COMPLETED
    assert harness.state.tool_counts["read_file"] == 1
