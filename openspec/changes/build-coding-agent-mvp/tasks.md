## 1. Project Foundation and Domain Types

- [x] 1.1 Add the Python package, Typer entry point, pytest/lint/type-check configuration, and empty test layout; verify installation and the initial quality commands run successfully.
- [x] 1.2 Write failing tests for action, observation, usage, limits, and run-state validation, then implement the minimal typed domain models; verify the focused state/model tests pass.
- [x] 1.3 Write failing tests for legal and illegal lifecycle transitions, then implement explicit terminal-state and step-limit transitions; verify terminal states cannot be mutated or exceeded.

## 2. Append-only Run Artifacts

- [x] 2.1 Write failing tests for event envelope validation, contiguous sequence numbers, JSONL append order, and flush behavior, then implement the event model and writer; verify the event unit tests pass.
- [x] 2.2 Write failing tests proving configured secrets and oversized payloads are redacted or truncated, then implement payload sanitation; verify no fixture secret appears in event output.
- [x] 2.3 Write failing tests proving `Finalizer` is the sole terminal-event owner, rejects repeated invocation, and writes terminal summary plus unified patch for every terminal status; then implement artifact finalization and verify synthetic runs produce self-describing `events.jsonl`, `summary.json`, and `patch.diff`.

## 3. Confined Repository Tools

- [x] 3.1 Write failing Windows-aware tests for absolute paths, traversal, symlinks, and junction escapes, then implement one canonical path-confinement helper; verify all escape attempts fail without filesystem changes.
- [x] 3.2 Write failing tests for deterministic ordering, limits, and truncation in `list_files`, `search_code`, and `read_file`, then implement those tools; verify their focused unit tests pass.
- [x] 3.3 Write failing tests for unique replacement, absent/duplicate expected text, UTF-8 handling, and explicit file creation, then implement `edit_file`; verify failed edits are atomic and successful edits report the changed path.
- [x] 3.4 Write failing tests for clean-tree validation and read-only diff collection, then implement the Git helpers; verify dirty repositories are rejected and `git_diff` returns the expected patch without changing state.

## 4. Local Command Execution

- [x] 4.1 Write failing tests for allowed and blocked executable/argument prefixes, shell metacharacters, and immutable policy configuration, then implement `CommandPolicy`; verify disallowed requests never reach a process launcher.
- [x] 4.2 Write failing tests for stdout/stderr capture, non-zero exits, working-directory confinement, spawn errors, duration, and output truncation, then implement `LocalExecutionBackend`; verify the execution tests pass on Windows.
- [x] 4.3 Write a failing process-tree timeout test, then implement timeout termination and cleanup; verify no spawned parent or child process remains after the test.
- [ ] 4.4 Add `run_command` through the registry and emit command/test events; verify allowed failing tests return observations and blocked commands produce policy observations without crashing.

## 5. Tool Registry and Working Context

- [ ] 5.1 Write failing tests for tool schema exposure, argument validation, unknown tools, normalized operational errors, and call/result events, then implement the immutable six-tool registry; verify all dispatch paths return `ToolResult`.
- [ ] 5.2 Write failing tests for mandatory context sections, path-keyed replacement, most-recent-read ordering, least-recently-read pinned eviction, latest verification retention, deterministic observation ordering, and budget elision; then implement `ContextBuilder` using only character counts and verify repeated inputs produce identical messages within budget.

## 6. Model Boundary and ReAct Runner

- [ ] 6.1 Write failing tests for queued actions and usage accounting, then implement `ModelClient` types and `ScriptedModelClient`; verify behavior tests can run without network access.
- [ ] 6.2 Write failing adapter contract tests using a fake HTTP transport, then implement the OpenAI-compatible client with structured action parsing, secret-safe configuration, and bounded transient retries; verify no live endpoint is required by CI.
- [ ] 6.3 Write a failing read-edit-test-finish behavior test, then implement the minimal synchronous ReAct loop and event emission; verify the observation from each tool call is present in the next model request.
- [ ] 6.4 Add failing behavior tests for malformed actions, tool failure recovery, failing-test repair, budget exhaustion, step limits, interruption, and fatal failure; then route every terminal state exactly once through `Finalizer` and verify the runner never writes `AgentFinished` or `AgentFailed` directly.

## 7. CLI Vertical Slice

- [ ] 7.1 Write failing CLI tests for required inputs, clean repository checks, limits, model settings, artifact location, and exit codes, then implement dependency composition in Typer; verify a scripted-model CLI run completes end to end.
- [ ] 7.2 Add a manual live-model smoke command and secret-safe example configuration without making it part of CI; verify CLI help documents the trusted-repository boundary and all effective limits.

## 8. Baseline Evaluation

- [ ] 8.1 Create three tiny task manifests and repository fixtures for a bug fix, test addition, and function-contract change; verify each initial revision fails its independent oracle and each gold state passes it.
- [ ] 8.2 Write failing tests for fixture setup, independent oracle execution, and metric collection, then implement the local evaluation runner; verify model finish text cannot override a failing oracle.
- [ ] 8.3 Run all three fixtures with deterministic scripted trajectories and generate baseline artifacts; verify the report includes task success, tests, steps, tool calls, elapsed time, token availability, and cost availability.

## 9. Quality and Scope Verification

- [ ] 9.1 Run pytest, lint, type checking, and relevant CLI/E2E tests; fix only failures within this OpenSpec change and record the exact successful commands.
- [ ] 9.2 Inspect the final diff against all four delta specs and confirm no FastAPI, web UI, sandbox, memory, multi-agent, RepoMap, MCP, skills, worktree, multi-strategy, or distributed-execution implementation entered the MVP.
- [ ] 9.3 Perform a security and architecture review of path confinement, command policy, process cleanup, secret handling, runner size, and dependency direction; add regression tests for every accepted defect before fixing it.
- [ ] 9.4 Add concise README architecture, safety, local demo, artifact, test, and known-limitations sections; verify a fresh checkout can follow the documented scripted demo without a network key.
