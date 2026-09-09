import sys

import pytest

from coding_agent.execution.base import CommandRequest
from coding_agent.execution.policy import CommandPolicy, CommandPolicyError


def test_default_policy_allows_pytest_but_blocks_shell_syntax() -> None:
    policy = CommandPolicy.default()
    policy.check(CommandRequest("python", ("-m", "pytest", "-q"), ".", 30, 10_000))
    with pytest.raises(CommandPolicyError):
        policy.check(CommandRequest("python", ("-m", "pytest", ";", "whoami"), ".", 30, 10_000))


@pytest.mark.parametrize(
    "argument", ["a|b", "a>b", "a<b", "a&&b", "$(whoami)", "`whoami`", "X=value", "a\nb"]
)
def test_policy_blocks_shell_and_environment_syntax(argument: str) -> None:
    policy = CommandPolicy(((sys.executable, ("-c",)),))
    with pytest.raises(CommandPolicyError):
        policy.check(CommandRequest(sys.executable, ("-c", argument), ".", 1, 100))


def test_policy_rejects_unapproved_executable_and_is_immutable() -> None:
    policy = CommandPolicy.default()
    with pytest.raises(CommandPolicyError, match="not allowed"):
        policy.check(CommandRequest("cmd", ("/c", "echo", "hello"), ".", 1, 100))
    with pytest.raises((AttributeError, TypeError)):
        policy.allowed_prefixes += (("cmd", ()),)


@pytest.mark.parametrize("disguised", ["./pytest", ".\\pytest.exe"])
def test_default_policy_rejects_dot_relative_allowed_name(disguised: str) -> None:
    with pytest.raises(CommandPolicyError, match="not allowed"):
        CommandPolicy.default().check(CommandRequest(disguised, (), ".", 1, 100))


def test_default_policy_rejects_allowed_name_from_arbitrary_path(tmp_path) -> None:
    disguised = tmp_path / "pytest.exe"
    with pytest.raises(CommandPolicyError, match="not allowed"):
        CommandPolicy.default().check(CommandRequest(str(disguised), (), ".", 1, 100))


def test_absolute_allow_entry_does_not_allow_same_bare_name(tmp_path) -> None:
    trusted = tmp_path / "pytest.exe"
    policy = CommandPolicy(((str(trusted), ()),))
    with pytest.raises(CommandPolicyError, match="not allowed"):
        policy.check(CommandRequest("pytest", (), ".", 1, 100))
