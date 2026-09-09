import sys

from conftest import finish, tool

from coding_agent.agent.state import RunStatus


def test_runner_reads_edits_tests_and_finishes(agent_harness) -> None:
    harness = agent_harness(
        [
            tool("read_file", path="calc.py"),
            tool(
                "edit_file",
                path="calc.py",
                operation="replace",
                expected_text="return a-b",
                new_text="return a+b",
            ),
            tool("run_command", executable=sys.executable, args=["-m", "pytest", "-q"]),
            finish("fixed and verified"),
        ]
    )
    result = harness.runner.run(harness.state)
    assert result.status is RunStatus.COMPLETED
    assert result.step_count == 4
    assert "return a+b" in (harness.repo / "calc.py").read_text(encoding="utf-8")
    assert "passed" in "\n".join(message.content for message in harness.model.received_messages[3])
    assert (harness.run_dir / "patch.diff").read_text(encoding="utf-8")
    assert (harness.run_dir / "summary.json").exists()
