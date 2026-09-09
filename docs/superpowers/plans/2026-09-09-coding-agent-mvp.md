# Coding Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-first CLI coding agent that iteratively inspects and edits a clean local Git repository, runs controlled commands, reacts to observations, and emits a patch plus inspectable run artifacts.

**Architecture:** A synchronous `AgentRunner` owns one ReAct loop and calls a bounded `ContextBuilder`, a six-function `ToolRegistry`, a small `ModelClient`, and a controlled `ExecutionBackend`. Current state is explicit and in memory; append-only JSONL events are observational artifacts, not the source of runtime state.

**Tech Stack:** Python 3.12+, Typer, Pydantic 2, httpx, pytest, Ruff, mypy, Git CLI

**Spec:** `openspec/changes/build-coding-agent-mvp/` — read `proposal.md`, all four `specs/*/spec.md` files, `design.md`, and `tasks.md` before implementation.

## Global Constraints

- OpenSpec is the sole source of truth; update it before changing specified behavior.
- MVP supports trusted local Python/pytest Git repositories on Windows and requires a clean tracked working tree.
- Each model step produces exactly one structured tool action or one finish action.
- Commands use an executable plus argument array with `shell=False`; no shell command strings, pipes, redirections, separators, or expansion.
- All file and working-directory paths remain inside the resolved repository root, including after symlink or junction resolution.
- Expected operational failures become observations; they do not escape the runner as uncaught exceptions.
- Events are append-only JSONL with schema version `1`; no event bus, database, replay-driven state, or resumability.
- Do not add FastAPI, web UI, SWE-bench runtime integration, Docker, worktrees, memory, RepoMap, RAG, MCP, skills, multiple strategies, multiple agents, or distributed execution.
- Every implementation cycle is Spec -> failing test -> Red -> minimal implementation -> Green -> refactor -> regression test.

---

### Task 1: Project foundation and lifecycle types

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/coding_agent/__init__.py`
- Create: `src/coding_agent/agent/actions.py`
- Create: `src/coding_agent/agent/state.py`
- Test: `tests/unit/agent/test_state.py`

**Interfaces:**
- Consumes: none.
- Produces: `ToolAction`, `FinishAction`, `Observation`, `ModelUsage`, `RunLimits`, `RunStatus`, and `RunState` used by every later task.

- [ ] **Step 1: Initialize version control and add package configuration**

If `.git` is absent, run `git init -b main`. Create `.gitignore` before installing anything, covering `.venv/`, Python caches, coverage output, local environment files, and generated run artifacts. Create `pyproject.toml` with Python `>=3.12`, runtime dependencies `typer`, `pydantic>=2,<3`, and `httpx`; add development dependencies `pytest`, `pytest-cov`, `ruff`, and `mypy`. Configure `src` packaging, Ruff line length 100, strict mypy for `coding_agent`, and pytest paths under `tests`.

Run: `python -m pip install -e ".[dev]"`

Expected: installation exits 0 and `python -c "import coding_agent"` succeeds.

- [ ] **Step 2: Write failing lifecycle tests**

```python
from pathlib import Path

import pytest

from coding_agent.agent.actions import Observation, ToolAction
from coding_agent.agent.state import RunLimits, RunState, RunStatus


def test_running_state_counts_steps_and_becomes_terminal(tmp_path: Path) -> None:
    state = RunState.start(tmp_path, "fix the bug", "abc123", RunLimits(max_steps=2))
    state.begin_step()
    state.add_observation(Observation(tool="read_file", ok=True, summary="read", data={}))
    state.finish(RunStatus.COMPLETED, "model finished")
    assert state.step_count == 1
    assert state.status is RunStatus.COMPLETED
    with pytest.raises(ValueError, match="terminal"):
        state.begin_step()


def test_next_step_is_rejected_at_limit(tmp_path: Path) -> None:
    state = RunState.start(tmp_path, "fix", "abc123", RunLimits(max_steps=1))
    state.begin_step()
    with pytest.raises(ValueError, match="step limit"):
        state.begin_step()


def test_tool_action_requires_arguments() -> None:
    action = ToolAction(tool="read_file", arguments={"path": "app.py"})
    assert action.kind == "tool"
```

- [ ] **Step 3: Run tests to verify Red**

Run: `python -m pytest tests/unit/agent/test_state.py -q`

Expected: collection fails because `coding_agent.agent.actions` and `coding_agent.agent.state` do not exist.

- [ ] **Step 4: Implement minimal typed lifecycle**

Implement Pydantic action/observation types and a dataclass state with these exact public signatures:

```python
class ToolAction(BaseModel):
    kind: Literal["tool"] = "tool"
    tool: str
    arguments: dict[str, JsonValue]


class FinishAction(BaseModel):
    kind: Literal["finish"] = "finish"
    summary: str


class Observation(BaseModel):
    tool: str
    ok: bool
    summary: str
    data: dict[str, JsonValue]
    error_code: str | None = None
    truncated: bool = False


class RunState:
    @classmethod
    def start(
        cls, repo_root: Path, task: str, base_commit: str, limits: RunLimits
    ) -> "RunState": ...
    def begin_step(self) -> None: ...
    def add_observation(self, observation: Observation) -> None: ...
    def finish(self, status: RunStatus, reason: str) -> None: ...
```

Use a bounded `deque` for recent observations and make every terminal `RunStatus` reject later mutations.

- [ ] **Step 5: Run focused and static checks**

Run: `python -m pytest tests/unit/agent/test_state.py -q`

Expected: all tests pass.

Run: `ruff check src/coding_agent/agent tests/unit/agent && mypy src/coding_agent/agent`

Expected: both commands exit 0.

- [ ] **Step 6: Commit the lifecycle slice**

```bash
git add .gitignore pyproject.toml src/coding_agent tests/unit/agent
git commit -m "feat: define coding agent lifecycle types"
```

### Task 2: Append-only events and artifact finalization

**Files:**
- Create: `src/coding_agent/events/models.py`
- Create: `src/coding_agent/events/writer.py`
- Create: `src/coding_agent/events/artifacts.py`
- Test: `tests/unit/events/test_writer.py`
- Test: `tests/unit/events/test_artifacts.py`

**Interfaces:**
- Consumes: `RunState`, `ModelUsage`, and JSON-compatible payloads from Task 1.
- Produces: `EventWriter.append(event_type, payload)`, `EventWriter.close()`, and single-owner `Finalizer.finalize(state) -> RunArtifacts`.

- [ ] **Step 1: Write failing ordered-event tests**

```python
import json
from pathlib import Path

from coding_agent.events.writer import EventWriter


def test_writer_appends_contiguous_redacted_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = EventWriter(path, run_id="run-1", secrets={"secret-key"})
    writer.append("TaskStarted", {"task": "fix", "api_key": "secret-key"})
    writer.append("ModelStep", {"step": 1})
    writer.close()
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [event["sequence"] for event in events] == [1, 2]
    assert all(event["schema_version"] == "1" for event in events)
    assert "secret-key" not in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the writer test to verify Red**

Run: `python -m pytest tests/unit/events/test_writer.py -q`

Expected: import failure for `coding_agent.events.writer`.

- [ ] **Step 3: Implement the event envelope and writer**

Define `EventType` as the nine specified literals and `RunEvent` with `schema_version`, `run_id`, `sequence`, UTC `timestamp`, `type`, and `payload`. Implement `EventWriter` as a single-owner UTF-8 JSONL writer that recursively replaces exact configured secret strings with `"[REDACTED]"`, bounds string payloads, flushes after each append, and rejects appends after close.

- [ ] **Step 4: Verify event Green**

Run: `python -m pytest tests/unit/events/test_writer.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing final-artifact test**

```python
import json

from coding_agent.agent.state import RunLimits, RunState, RunStatus
from coding_agent.events.artifacts import Finalizer
from coding_agent.events.writer import EventWriter


def test_finalize_writes_summary_and_patch(tmp_path) -> None:
    state = RunState.start(tmp_path, "fix", "abc123", RunLimits(max_steps=3))
    state.finish(RunStatus.COMPLETED, "done")
    writer = EventWriter(tmp_path / "events.jsonl", state.run_id, secrets=set())
    finalizer = Finalizer(writer, patch_provider=lambda: "diff --git a/a.py b/a.py\n")
    artifacts = finalizer.finalize(state)
    summary = json.loads(artifacts.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert artifacts.patch_path.read_text(encoding="utf-8").startswith("diff --git")
```

- [ ] **Step 6: Implement and verify finalization**

Implement immutable `RunArtifacts(events_path, summary_path, patch_path)` and stateful `Finalizer`. `Finalizer` is the only component permitted to append `AgentFinished` or `AgentFailed`. Its one-shot `finalize` method collects the diff, maps `completed` to `AgentFinished` and every other terminal status to `AgentFailed`, appends exactly one terminal event, closes the writer, writes `patch.diff`, then atomically replaces `summary.json` with all fields required by the run-artifacts spec. A repeated call is rejected before any write.

Run: `python -m pytest tests/unit/events -q`

Expected: all event and artifact tests pass.

- [ ] **Step 7: Commit the artifact slice**

```bash
git add src/coding_agent/events tests/unit/events
git commit -m "feat: record append-only run artifacts"
```

### Task 3: Path confinement and read-only repository tools

**Files:**
- Create: `src/coding_agent/tools/paths.py`
- Create: `src/coding_agent/tools/files.py`
- Test: `tests/unit/tools/test_paths.py`
- Test: `tests/unit/tools/test_file_reads.py`

**Interfaces:**
- Consumes: `Observation` from Task 1.
- Produces: `resolve_confined(root, relative_path) -> Path`, `list_files`, `search_code`, and `read_file` handlers.

- [ ] **Step 1: Write failing path escape tests**

```python
from pathlib import Path

import pytest

from coding_agent.tools.paths import PathPolicyError, resolve_confined


@pytest.mark.parametrize(
    "candidate", ["../outside.txt", "C:/Windows/System32", "\\\\server\\share"]
)
def test_resolve_confined_rejects_escape(tmp_path: Path, candidate: str) -> None:
    with pytest.raises(PathPolicyError):
        resolve_confined(tmp_path, candidate)


def test_resolve_confined_accepts_child(tmp_path: Path) -> None:
    assert resolve_confined(tmp_path, "src/app.py") == (tmp_path / "src/app.py").resolve()
```

Add Windows junction and available symlink tests that skip only when the OS refuses fixture creation.

- [ ] **Step 2: Verify path tests are Red, then implement one resolver**

Run: `python -m pytest tests/unit/tools/test_paths.py -q`

Expected: import failure.

Implement `resolve_confined` using resolved root/target paths and `Path.is_relative_to`; reject absolute inputs before resolution and re-check existing parents so links cannot escape.

Run: `python -m pytest tests/unit/tools/test_paths.py -q`

Expected: all applicable tests pass.

- [ ] **Step 3: Write failing deterministic inspection tests**

```python
from coding_agent.tools.files import list_files, read_file, search_code


def test_search_is_sorted_limited_and_reports_truncation(repo) -> None:
    (repo / "b.py").write_text("needle = 2\n", encoding="utf-8")
    (repo / "a.py").write_text("needle = 1\n", encoding="utf-8")
    result = search_code(repo, query="needle", max_results=1)
    assert result.ok
    assert result.data["matches"][0]["path"] == "a.py"
    assert result.truncated
```

Also assert line-number slicing, UTF-8 decoding errors, `.git` exclusion, file glob filtering, and explicit omitted counts.

- [ ] **Step 4: Implement inspection tools and verify Green**

Implement direct Python filesystem traversal and text search with deterministic path/line ordering. Do not invoke shell utilities. Return `Observation`-compatible results with bounded text.

Run: `python -m pytest tests/unit/tools/test_paths.py tests/unit/tools/test_file_reads.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit repository inspection**

```bash
git add src/coding_agent/tools/paths.py src/coding_agent/tools/files.py tests/unit/tools
git commit -m "feat: add confined repository inspection"
```

### Task 4: Checked edits and Git evidence

**Files:**
- Modify: `src/coding_agent/tools/files.py`
- Create: `src/coding_agent/tools/git.py`
- Test: `tests/unit/tools/test_edit_file.py`
- Test: `tests/unit/tools/test_git.py`

**Interfaces:**
- Consumes: `resolve_confined` from Task 3.
- Produces: `edit_file`, `require_clean_worktree`, `current_head`, and `git_diff`.

- [ ] **Step 1: Write failing atomic-edit tests**

```python
def test_replace_requires_one_exact_match(repo) -> None:
    path = repo / "app.py"
    path.write_text("x = 1\nx = 1\n", encoding="utf-8")
    result = edit_file(repo, "app.py", operation="replace", expected_text="x = 1", new_text="x = 2")
    assert not result.ok
    assert result.error_code == "edit_conflict"
    assert path.read_text(encoding="utf-8") == "x = 1\nx = 1\n"


def test_create_refuses_existing_file(repo) -> None:
    (repo / "new.py").write_text("old", encoding="utf-8")
    result = edit_file(repo, "new.py", operation="create", expected_text=None, new_text="new")
    assert not result.ok
```

- [ ] **Step 2: Verify Red, implement edits, verify Green**

Run: `python -m pytest tests/unit/tools/test_edit_file.py -q`

Expected: failing imports or assertions.

Implement UTF-8-only exact replacement and exclusive creation. Build replacement content completely before a same-directory temporary write and atomic replace.

Run: `python -m pytest tests/unit/tools/test_edit_file.py -q`

Expected: all tests pass.

- [ ] **Step 3: Write failing Git helper tests**

Create a fixture repository with one commit. Assert `require_clean_worktree` rejects tracked staged/unstaged changes before model work, `current_head` returns the commit hash, and `git_diff(base_commit)` returns a unified patch plus sorted changed paths without modifying index or working tree.

- [ ] **Step 4: Implement Git helpers and verify them**

Use `subprocess.run([...], shell=False, check=False, text=True)` with explicit Git argument arrays. Treat Git errors as typed operational results.

Run: `python -m pytest tests/unit/tools/test_git.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit edit and Git tools**

```bash
git add src/coding_agent/tools tests/unit/tools
git commit -m "feat: add checked edits and git evidence"
```

### Task 5: Command policy and Windows-local execution

**Files:**
- Create: `src/coding_agent/execution/base.py`
- Create: `src/coding_agent/execution/policy.py`
- Create: `src/coding_agent/execution/local.py`
- Test: `tests/unit/execution/test_policy.py`
- Test: `tests/unit/execution/test_local.py`

**Interfaces:**
- Consumes: `resolve_confined` from Task 3.
- Produces: `CommandRequest`, `CommandResult`, `ExecutionBackend.run`, `CommandPolicy.check`, and `LocalExecutionBackend.run`.

- [ ] **Step 1: Write failing policy tests**

```python
import pytest

from coding_agent.execution.base import CommandRequest
from coding_agent.execution.policy import CommandPolicy, CommandPolicyError


def test_default_policy_allows_pytest_but_blocks_shell_syntax() -> None:
    policy = CommandPolicy.default()
    policy.check(CommandRequest("python", ("-m", "pytest", "-q"), ".", 30, 10000))
    with pytest.raises(CommandPolicyError):
        policy.check(CommandRequest("python", ("-m", "pytest", ";", "whoami"), ".", 30, 10000))
```

Cover disallowed executables, argument newlines, separators, redirects, substitutions, environment assignment syntax, and mutation attempts after construction.

- [ ] **Step 2: Implement immutable prefix policy and verify Green**

Represent allowed commands as immutable executable/argument-prefix tuples. Default to `python -m pytest` and `pytest`; accept additional prefixes only from validated startup configuration.

Run: `python -m pytest tests/unit/execution/test_policy.py -q`

Expected: all tests pass.

- [ ] **Step 3: Write failing backend tests**

```python
def test_backend_captures_nonzero_result(repo, backend) -> None:
    request = CommandRequest("python", ("-m", "pytest", "missing.py"), ".", 10, 10000)
    result = backend.run(request)
    assert result.status == "exited"
    assert result.exit_code != 0
    assert result.duration_ms >= 0
```

Add tests for stdout/stderr, confined cwd, spawn failure, byte truncation, timeout, and a Windows child process that must not survive its parent timeout.

- [ ] **Step 4: Implement local execution and process-tree cleanup**

Use `subprocess.Popen` with `shell=False`, pipes, text decoding with replacement, and a new process group. On Windows timeout, use a scoped process-tree termination mechanism against the spawned PID, wait for cleanup, then return `status="timed_out"`. Never build a command string.

- [ ] **Step 5: Verify execution behavior**

Run: `python -m pytest tests/unit/execution -q`

Expected: all tests pass and the timeout test confirms both parent and child PIDs are gone.

- [ ] **Step 6: Commit the execution boundary**

```bash
git add src/coding_agent/execution tests/unit/execution
git commit -m "feat: add controlled local command execution"
```

### Task 6: Six-tool registry

**Files:**
- Create: `src/coding_agent/tools/registry.py`
- Create: `src/coding_agent/tools/commands.py`
- Test: `tests/unit/tools/test_registry.py`
- Test: `tests/unit/tools/test_commands.py`

**Interfaces:**
- Consumes: file/Git handlers from Tasks 3-4, execution types from Task 5, and `EventWriter` from Task 2.
- Produces: `ToolDefinition`, `ToolResult`, `ToolContext`, `ToolRegistry.schemas()`, and `ToolRegistry.execute(name, arguments)`.

- [ ] **Step 1: Write failing registry contract tests**

```python
def test_registry_exposes_exact_mvp_tools(registry) -> None:
    assert [schema["name"] for schema in registry.schemas()] == [
        "list_files",
        "search_code",
        "read_file",
        "edit_file",
        "run_command",
        "git_diff",
    ]


def test_unknown_tool_is_normalized(registry) -> None:
    result = registry.execute("delete_repository", {})
    assert not result.ok
    assert result.error_code == "unknown_tool"
```

Also assert invalid arguments, handler operational exceptions, `ToolCalled`/`ToolResult`, `FileEdited`, `CommandExecuted`, and pytest-classified `TestResult` events.

- [ ] **Step 2: Verify Red, implement registry and command adapter**

Use Pydantic input models to generate JSON schemas. Freeze the registration mapping after construction. Catch only documented policy, validation, filesystem, Git, and execution errors; unexpected programming exceptions remain fatal for the runner to finalize as failed.

- [ ] **Step 3: Verify the six-tool surface**

Run: `python -m pytest tests/unit/tools -q`

Expected: all tool tests pass and no seventh tool schema is exposed.

- [ ] **Step 4: Commit the tool surface**

```bash
git add src/coding_agent/tools tests/unit/tools
git commit -m "feat: expose deterministic coding tools"
```

### Task 7: Deterministic working-context builder

**Files:**
- Create: `src/coding_agent/context/builder.py`
- Test: `tests/unit/context/test_builder.py`

**Interfaces:**
- Consumes: `RunState`, observations, and tool schemas.
- Produces: `ContextBuilder.build(state, tool_schemas) -> list[Message]`.

- [ ] **Step 1: Write failing priority and budget tests**

```python
def test_builder_preserves_mandatory_and_latest_test_under_budget(state, builder) -> None:
    state.add_observation(long_old_observation())
    state.add_observation(test_observation("1 failed"))
    messages = builder.build(state, tool_schemas=[])
    text = "\n".join(message.content for message in messages)
    assert state.task in text
    assert "remaining_steps" in text
    assert "1 failed" in text
    assert "[older observation elided]" in text
    assert len(text) <= builder.max_chars
```

Also verify stable ordering, path-keyed replacement of stale reads, reread-to-MRU behavior, least-recently-read eviction under the pinned character budget, absence of edited-file special treatment, and identical output for identical state.

- [ ] **Step 2: Verify Red, implement deterministic selection, verify Green**

Implement immutable system/task messages, path-keyed pinned reads ordered by successful read recency, replacement-and-MRU on reread, least-recently-read pinned eviction, latest-test pinning, and newest-first observation selection rendered chronologically. Use character counts and explicit elision markers only; do not use another model, embeddings, semantic ranking, or implicit priority for edited files.

Run: `python -m pytest tests/unit/context/test_builder.py -q`

Expected: all tests pass.

- [ ] **Step 3: Commit context selection**

```bash
git add src/coding_agent/context tests/unit/context
git commit -m "feat: build bounded working context"
```

### Task 8: Model protocol, scripted client, and OpenAI-compatible adapter

**Files:**
- Create: `src/coding_agent/models/base.py`
- Create: `src/coding_agent/models/scripted.py`
- Create: `src/coding_agent/models/openai_compatible.py`
- Test: `tests/unit/models/test_scripted.py`
- Test: `tests/unit/models/test_openai_compatible.py`

**Interfaces:**
- Consumes: `ToolAction`, `FinishAction`, and `ModelUsage` from Task 1.
- Produces: `ModelClient.complete(messages, tool_schemas) -> ModelResponse`.

- [ ] **Step 1: Write failing scripted-client tests**

```python
def test_scripted_client_returns_queued_actions_and_usage() -> None:
    client = ScriptedModelClient(
        [
            ModelResponse(
                action=ToolAction(tool="read_file", arguments={"path": "a.py"}), usage=ModelUsage()
            ),
            ModelResponse(action=FinishAction(summary="done"), usage=ModelUsage()),
        ]
    )
    assert client.complete([], []).action.kind == "tool"
    assert client.complete([], []).action.kind == "finish"
```

- [ ] **Step 2: Implement the protocol and scripted client**

The protocol has one synchronous method. The scripted client stores received messages for later assertions and raises a clear test error when its response queue is exhausted.

Run: `python -m pytest tests/unit/models/test_scripted.py -q`

Expected: all tests pass.

- [ ] **Step 3: Write failing adapter contract tests with mock transport**

Use `httpx.MockTransport` to assert endpoint URL, bearer header, model name, messages, one tool choice, response ID, and token accounting. Add responses for tool action, finish action, malformed arguments, transient 429 then success, and terminal 400.

- [ ] **Step 4: Implement the production adapter and verify it offline**

Send OpenAI-compatible chat/tool payloads through an injected `httpx.Client`. Parse exactly one action, apply a small fixed retry count only to timeout/429/5xx responses, and never include the API key in exceptions or model-step metadata.

Run: `python -m pytest tests/unit/models -q`

Expected: all tests pass with no network access.

- [ ] **Step 5: Commit model clients**

```bash
git add src/coding_agent/models tests/unit/models
git commit -m "feat: add testable model boundary"
```

### Task 9: Minimal ReAct loop

**Files:**
- Create: `src/coding_agent/agent/runner.py`
- Test: `tests/behavior/test_react_loop.py`

**Interfaces:**
- Consumes: `RunState`, `ContextBuilder`, `ModelClient`, `ToolRegistry`, and `EventWriter`.
- Produces: `AgentRunner.run(state) -> RunState` with one visible tool-result feedback cycle per model step.

- [ ] **Step 1: Write the failing happy-path behavior test**

```python
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
            tool("run_command", executable="python", args=["-m", "pytest", "-q"]),
            finish("fixed and verified"),
        ]
    )
    result = harness.runner.run(harness.state)
    assert result.status.value == "completed"
    assert result.step_count == 4
    assert "return a+b" in (harness.repo / "calc.py").read_text(encoding="utf-8")
    assert "passed" in harness.model.received_messages[3][-1].content
```

- [ ] **Step 2: Run the behavior test to verify Red**

Run: `python -m pytest tests/behavior/test_react_loop.py::test_runner_reads_edits_tests_and_finishes -q`

Expected: import failure for `AgentRunner`.

- [ ] **Step 3: Implement only the happy-path loop**

Implement `AgentRunner.run` as: transition to running, check limit, begin step, build context, call model, record `ModelStep`, dispatch one tool action and add its observation, or finish. Route all exits through one private method that selects status/reason and invokes the single `Finalizer` exactly once; the runner never appends a terminal event or writes final artifacts. Leave recovery branches unimplemented until the next task.

- [ ] **Step 4: Verify happy-path Green and inspect trajectory**

Run: `python -m pytest tests/behavior/test_react_loop.py::test_runner_reads_edits_tests_and_finishes -q`

Expected: pass, with ordered TaskStarted, model/tool events, and AgentFinished.

- [ ] **Step 5: Commit the runnable loop**

```bash
git add src/coding_agent/agent/runner.py tests/behavior/test_react_loop.py
git commit -m "feat: run minimal react coding loop"
```

### Task 10: Recovery, limits, interruption, and final evidence

**Files:**
- Modify: `src/coding_agent/agent/runner.py`
- Modify: `src/coding_agent/agent/state.py`
- Test: `tests/behavior/test_recovery.py`
- Test: `tests/behavior/test_termination.py`

**Interfaces:**
- Consumes: runner from Task 9 and artifact finalization from Task 2.
- Produces: complete specified termination and recovery behavior.

- [ ] **Step 1: Add failing recovery tests**

```python
def test_failed_test_becomes_observation_and_can_be_repaired(agent_harness) -> None:
    harness = agent_harness([run_pytest(), repair_edit(), run_pytest(), finish("verified")])
    result = harness.runner.run(harness.state)
    assert result.status.value == "completed"
    assert any(not item.ok and item.tool == "run_command" for item in result.recent_observations)


def test_tool_policy_failure_does_not_crash(agent_harness) -> None:
    harness = agent_harness(
        [tool("run_command", executable="cmd", args=["/c", "del", "*"]), finish("blocked")]
    )
    result = harness.runner.run(harness.state)
    assert result.status.value == "completed"
    assert any(item.error_code == "policy_error" for item in result.recent_observations)
```

Add malformed model output followed by correction and expected tool operational error followed by a valid action.

- [ ] **Step 2: Implement normalized recovery and verify it**

Convert model-format failures to `Observation(tool="model", error_code="format_error")`. Preserve non-zero command results as ordinary failed observations. Treat only corrupted repository root, artifact write failure, or unexpected programming exceptions as `failed`.

Run: `python -m pytest tests/behavior/test_recovery.py -q`

Expected: all tests pass.

- [ ] **Step 3: Add failing termination tests**

Assert exact statuses and single terminal events for step limit, budget limit based on reported usage, `KeyboardInterrupt` cancellation, finish action, and unexpected model exception. Assert no extra model call occurs after the step limit.

- [ ] **Step 4: Implement termination paths and final evidence**

Make one `try/finally` path select `completed`, `step_limit`, `budget_limit`, `cancelled`, or `failed` and invoke `Finalizer` once. The finalizer—not the runner—obtains `git_diff(base_commit)`, appends the sole terminal event, and writes `patch.diff` plus `summary.json`. Ensure model finish summary is metadata, never the success oracle.

Run: `python -m pytest tests/behavior/test_recovery.py tests/behavior/test_termination.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit resilient loop behavior**

```bash
git add src/coding_agent/agent tests/behavior
git commit -m "feat: bound and recover coding agent runs"
```

### Task 11: Typer CLI vertical slice

**Files:**
- Create: `src/coding_agent/config.py`
- Create: `src/coding_agent/cli.py`
- Test: `tests/integration/test_cli.py`

**Interfaces:**
- Consumes: all runtime components from Tasks 1-10.
- Produces: `coding-agent run REPOSITORY --task TEXT` and dependency composition for one run.

- [ ] **Step 1: Write failing CLI validation tests**

```python
from typer.testing import CliRunner

from coding_agent.cli import app


def test_cli_rejects_dirty_repo(dirty_repo) -> None:
    result = CliRunner().invoke(app, ["run", str(dirty_repo), "--task", "fix it"])
    assert result.exit_code == 2
    assert "clean working tree" in result.stdout.lower()
```

Cover missing/non-Git repository, empty task, effective max steps, timeout, output directory, model/base URL from arguments or environment, and API-key redaction.

- [ ] **Step 2: Verify Red, implement config and composition**

Use Pydantic settings assembled explicitly from Typer options and environment variables. The CLI validates before constructing the production model client, creates a run-specific artifact directory, composes the six tools, executes synchronously, prints status/patch/summary paths, and maps terminal status to documented exit codes.

- [ ] **Step 3: Add scripted-client injection and pass integration tests**

Expose one internal `build_runner(config, model_client=None)` composition function so tests can supply `ScriptedModelClient` without monkeypatching network code.

Run: `python -m pytest tests/integration/test_cli.py -q`

Expected: all tests pass without an API key.

- [ ] **Step 4: Verify CLI help and static checks**

Run: `python -m coding_agent.cli --help`

Expected: help lists repository, task, model/base URL, step limit, timeout, context limit, artifact directory, and trusted-repository warning.

Run: `ruff check src tests && mypy src/coding_agent`

Expected: both exit 0.

- [ ] **Step 5: Commit CLI vertical slice**

```bash
git add src/coding_agent/config.py src/coding_agent/cli.py tests/integration
git commit -m "feat: expose local coding agent cli"
```

### Task 12: Deterministic local baseline evaluation

**Files:**
- Create: `src/coding_agent/evaluation/fixtures.py`
- Create: `src/coding_agent/evaluation/runner.py`
- Create: `tests/fixtures/tasks/off-by-one/task.json`
- Create: `tests/fixtures/tasks/add-regression-test/task.json`
- Create: `tests/fixtures/tasks/change-contract/task.json`
- Test: `tests/e2e/test_fixture_manifests.py`
- Test: `tests/e2e/test_baseline_evaluation.py`

**Interfaces:**
- Consumes: CLI/runtime composition and run artifacts.
- Produces: `TaskManifest`, `prepare_fixture`, `evaluate_fixture`, and aggregate JSON metrics.

- [ ] **Step 1: Write failing manifest/oracle tests**

Define each `task.json` with `id`, `task`, `setup_files`, `oracle_command`, and `gold_files`. Test that setup initializes one clean Git commit, the initial oracle fails, and applying `gold_files` makes it pass.

- [ ] **Step 2: Implement fixture preparation and verify manifests**

Fixture setup writes only declared UTF-8 files into a temporary directory, initializes Git with local test-only identity, commits the initial revision, and runs the oracle through a dedicated evaluator subprocess rather than the agent command policy.

Run: `python -m pytest tests/e2e/test_fixture_manifests.py -q`

Expected: all three initial/gold oracle pairs behave as declared.

- [ ] **Step 3: Write failing independent-evaluation test**

```python
def test_finish_text_cannot_override_failed_oracle(prepared_fixture, scripted_agent) -> None:
    scripted_agent.responses = [finish("all tests pass")]
    result = evaluate_fixture(prepared_fixture, scripted_agent)
    assert not result.task_success
    assert result.agent_status == "completed"
    assert result.oracle_exit_code != 0
```

Also assert steps, tool counts, elapsed time, test result, tokens, and unavailable cost.

- [ ] **Step 4: Implement evaluator and verify all deterministic trajectories**

Run each prepared task through a scripted trajectory, then run the independent oracle and combine run summary plus oracle evidence into one result. Aggregate by task without interpreting the model's prose.

Run: `python -m pytest tests/e2e/test_baseline_evaluation.py -q`

Expected: all deterministic baseline cases pass.

- [ ] **Step 5: Commit local evaluation**

```bash
git add src/coding_agent/evaluation tests/e2e tests/fixtures/tasks
git commit -m "feat: add deterministic coding task evaluation"
```

### Task 13: Documentation, full review, and completion verification

**Files:**
- Create: `README.md`
- Modify: files identified by review only when a failing regression test demonstrates the defect.

**Interfaces:**
- Consumes: the complete MVP.
- Produces: reproducible developer instructions and verified completion evidence.

- [ ] **Step 1: Write the README around one three-minute path**

Document: problem statement, minimal architecture diagram, trusted-repository warning, installation, scripted offline demo, live model configuration, six tools, event/summary/patch examples, test commands, local evaluation, limitations, reference-driven decisions, and V2 candidates. State clearly that local execution is not a sandbox.

- [ ] **Step 2: Run the complete automated verification suite**

Run: `python -m pytest -q`

Expected: all unit, behavior, integration, and E2E tests pass with no network access.

Run: `ruff check . && ruff format --check .`

Expected: both Ruff checks exit 0.

Run: `mypy src/coding_agent`

Expected: strict type checking exits 0.

- [ ] **Step 3: Run the documented offline demo from a fresh fixture**

Run the exact README scripted-demo command against a newly prepared fixture.

Expected: status is `completed`; `events.jsonl` has contiguous events and one terminal event; `patch.diff` is non-empty; `summary.json` references both artifacts; the independent oracle passes.

- [ ] **Step 4: Perform focused architecture and security review**

Inspect dependency direction, runner size, path confinement, command policy, process cleanup, edit atomicity, secret redaction, terminal-event uniqueness, and scope exclusions. For each accepted defect, first add a regression test that fails, then apply the smallest fix and rerun its focused suite.

- [ ] **Step 5: Inspect scope and repository diff**

Run: `git status --short && git diff --check && git diff --stat HEAD~1`

Expected: no generated run artifacts or secrets are tracked; no whitespace errors; no implementation of excluded capabilities; changes match the OpenSpec tasks.

- [ ] **Step 6: Validate OpenSpec remains authoritative**

Run: `openspec.cmd validate build-coding-agent-mvp --strict`

Expected: `Change 'build-coding-agent-mvp' is valid`.

- [ ] **Step 7: Commit verified documentation**

```bash
git add README.md
git commit -m "docs: document coding agent mvp"
```
