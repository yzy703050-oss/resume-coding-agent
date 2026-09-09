# Coding Agent MVP — Task Recovery State

Last updated: 2026-09-09 (Asia/Shanghai)

## Current objective

Build a resume-ready, publicly demonstrable baseline Coding Agent that accepts a clean local Git repository plus a coding task and completes this loop:

`explore -> search/read -> reason -> edit -> run commands/tests -> observe -> retry/repair -> patch + summary`

OpenSpec change `build-coding-agent-mvp` is the sole requirements and acceptance source. V1 architecture is frozen. Do not add Memory, RepoMap/RAG, Multi-Agent, Docker/general sandboxing, FastAPI/Web UI, MCP, Skills, Worktree, multiple strategies, or distributed execution.

## Architecture clarifications already frozen

1. `Finalizer` is the sole owner of `AgentFinished` / `AgentFailed`; `AgentRunner` cannot append terminal events through the public writer API.
2. `completed`, `step_limit`, `budget_limit`, `cancelled`, and `failed` all enter `Finalizer` exactly once. Finalization writes the terminal event, `patch.diff`, and `summary.json`.
3. Pinned code uses deterministic path identity and read recency: reread replaces and becomes MRU; LRU paths are evicted by character budget. No extra LLM, embeddings, semantic ranking, or edited-file priority.

## Completed implementation

- Python 3.12+ package and Typer CLI (`coding-agent run`).
- Explicit action, observation, usage, limit, status, and run-state models.
- One synchronous ReAct `AgentRunner` with recovery, step/token/cost limits, cancellation, fatal failure handling, and one finalization path.
- Deterministic `ContextBuilder` with bounded messages, pinned-file LRU-like policy, recency window, and latest-test retention.
- Fixed six-tool registry: `list_files`, `search_code`, `read_file`, `edit_file`, `run_command`, `git_diff`.
- Repository path confinement, deterministic UTF-8 inspection, exact unique replacement, exclusive create, and Git clean-tree checks.
- Windows-first local subprocess backend using `shell=False`, immutable command-prefix policy, stream capture, timeout, truncation, and Windows Job Object process-tree cleanup.
- Append-only, redacted, bounded JSONL events and single-owner final artifacts.
- Scripted model client and offline-tested OpenAI-compatible adapter with structured tool parsing and bounded transient retries.
- CLI validation, clean-repository enforcement, secret handling, offline response scripts, and artifact-path isolation outside the target repository.
- Three deterministic repository fixtures with independent pytest oracles and a checked-in 3/3 scripted baseline report.
- README architecture, safety boundary, three-minute offline demo, live-model command, verification commands, and V1 limitations.
- Focused review regressions for Job Object assignment failure, invalid-script partial artifacts, bare-Python interpreter resolution, cost budgeting, untracked files in patches, artifact directory isolation, executable-path bypasses, symlink search escapes, effective configuration recording, final-patch changed files, and credential-bearing base URLs.

## File inventory and purpose

### Requirements and planning

- `openspec/changes/build-coding-agent-mvp/proposal.md`: project motivation, scope, and capability list.
- `openspec/changes/build-coding-agent-mvp/design.md`: frozen V1 decisions, state/data flow, single Finalizer ownership, deterministic pinned-context policy, exclusions, and risks.
- `openspec/changes/build-coding-agent-mvp/specs/*/spec.md`: acceptance requirements for agent runs, tools, artifacts, and baseline evaluation.
- `openspec/changes/build-coding-agent-mvp/tasks.md`: implementation checklist; all 29/29 tasks are complete.
- `docs/superpowers/plans/2026-09-09-coding-agent-mvp.md`: vertical-slice TDD implementation plan; Ruff reformatted Python examples in the current uncommitted diff.
- `.agents/skills/openspec-*/SKILL.md`: OpenSpec-generated local workflow skills; deliberately ignored as machine-local workflow integration rather than product source.

### Runtime source

- `pyproject.toml`: package metadata, Typer/Pydantic/httpx dependencies, pytest/Ruff/mypy configuration, and CLI entry point.
- `src/coding_agent/agent/actions.py`: actions, observations, JSON values, and correct optional model-usage/cost accumulation.
- `src/coding_agent/agent/state.py`: `RunStatus`, `RunLimits`, `RunState`, effective non-secret configuration, state transitions, observations, pinned files, and changed-file tracking.
- `src/coding_agent/agent/runner.py`: the single ReAct loop, terminal-state selection, and non-secret startup metadata.
- `src/coding_agent/context/builder.py`: deterministic bounded context construction.
- `src/coding_agent/events/models.py`: versioned nine-event vocabulary.
- `src/coding_agent/events/writer.py`: append-only JSONL writer with redaction/truncation and public terminal-event rejection.
- `src/coding_agent/events/artifacts.py`: one-shot `Finalizer`, terminal mapping, patch writing, and atomic summary writing.
- `src/coding_agent/execution/base.py`: command request/result values and backend protocol.
- `src/coding_agent/execution/policy.py`: immutable allowed-prefix, exact executable-path, and shell-syntax policy.
- `src/coding_agent/execution/local.py`: host subprocess execution, bare-Python resolution, and Windows process-tree cleanup including Job assignment failures.
- `src/coding_agent/tools/paths.py`: canonical repository confinement.
- `src/coding_agent/tools/files.py`: list/search/read/edit implementations with per-candidate symlink confinement.
- `src/coding_agent/tools/git.py`: clean-tree, HEAD, and read-only diff helpers including untracked files.
- `src/coding_agent/tools/commands.py`: command result normalization and command/test event emission.
- `src/coding_agent/tools/registry.py`: fixed six-tool schema/dispatch registry.
- `src/coding_agent/models/base.py`: synchronous model protocol and response model.
- `src/coding_agent/models/scripted.py`: queued offline model client.
- `src/coding_agent/models/openai_compatible.py`: production HTTP adapter.
- `src/coding_agent/config.py`: validated runtime configuration, safe base-URL validation, and optional artifact root for a repository-sibling default.
- `src/coding_agent/cli.py`: Typer command and dependency composition; validates model/script before artifact creation and keeps artifacts outside the target repository.
- `src/coding_agent/evaluation/fixtures.py`: manifest setup, Git initialization, gold application, and independent oracle execution.
- `src/coding_agent/evaluation/runner.py`: per-task and aggregate metrics.
- `src/coding_agent/evaluation/baseline.py`: reproducible three-task scripted baseline.

### Tests, fixtures, and public artifacts

- `tests/unit/agent/test_state.py`: action/state/usage transitions, including first reported cost.
- `tests/unit/events/*`: event ordering, redaction, single terminal owner, all terminal statuses, and repeated-finalize rejection.
- `tests/unit/tools/*`: path, symlink confinement, file, edit, Git, registry, and command contracts; Git tests prove untracked files enter the patch without index mutation.
- `tests/unit/execution/*`: executable policy, streams, exits, confinement, truncation, timeout tree cleanup, and Job assignment failure cleanup.
- `tests/unit/context/test_builder.py`: mandatory context, replacement/MRU, LRU eviction, no edit priority, determinism.
- `tests/unit/models/*`: scripted queue and OpenAI-compatible transport/parse/retry contracts.
- `tests/behavior/*`: real temporary Git repositories and real tool/backend loops, including token/cost budgets.
- `tests/integration/test_cli.py`: CLI validation and offline end-to-end run, including passing test evidence, secret-safe URL rejection, invalid-script cleanup, and artifact isolation.
- `tests/e2e/*`: fixture validity, independent oracle authority, three scripted repairs, and aggregate report.
- `tests/fixtures/tasks/*/task.json`: off-by-one fix, regression-test addition, and contract-change tasks.
- `benchmarks/baseline-scripted.json`: checked-in 3/3 deterministic baseline metrics.
- `examples/offline-script.json`: checked-in deterministic script used by the README demo.
- `README.md`: checked-in public project guide and demo.

Package `__init__.py` files only establish their package namespaces and have no pending behavior.

## Current Git state

- Branch: `main`.
- Pre-completion checkpoint: `dcce433 feat: add deterministic baseline evaluation`; the final V1 checkpoint is the commit containing this document.
- Earlier vertical slices are committed separately (lifecycle, artifacts, repository tools, execution, registry, context, model boundary, ReAct loop, CLI, evaluation).
- The final V1 completion checkpoint includes the review fixes, README, example script, refreshed baseline report, completed OpenSpec checklist, and this recovery document.
- `.agents/`, virtual environments, caches, run outputs, and demo outputs are deliberately ignored.
- `git diff --check` exits 0. No merge markers or whitespace errors were found before the completion checkpoint.
- Generated demo runs are under ignored `outputs/` and are not shown by Git.

## Latest test and validation evidence

Commands use the repository-local `.venv` on Windows:

- `.\\.venv\\Scripts\\python.exe -m pytest -q` -> **94 passed** on the final V1 tree.
- `.\\.venv\\Scripts\\ruff.exe check .` -> **All checks passed**.
- `.\\.venv\\Scripts\\ruff.exe format --check .` -> **62 files already formatted**.
- `.\\.venv\\Scripts\\mypy.exe src/coding_agent` -> **Success: no issues found in 31 source files**.
- `openspec.cmd validate build-coding-agent-mvp --strict` -> **valid**.
- Fresh offline demo -> `completed`, latest test `ok=true`, exactly one terminal event, and a patch containing only the intended source change.
- Deterministic baseline report -> 3 tasks, 3 successes, success rate 1.0.

## Known issues / unresolved decisions

- No known failing test, static-analysis error, OpenSpec validation error, or incomplete V1 task.
- A live network model smoke run has not been performed because it requires a user-supplied endpoint/key and is intentionally excluded from CI. The README contains the manual secret-safe command.
- Host command execution is not a sandbox and remains limited to trusted repositories, as documented.

## Optional next steps

1. Archive the completed OpenSpec change when its history no longer needs to remain active.
2. Run the documented live-model smoke command with a user-supplied key if external-model validation is desired.
3. Observe real run failures before proposing a separately scoped V2 change.

## Exact resume point

V1 has no pending implementation step. Start by verifying the checkpoint:

```powershell
git status --short
git diff --check
.\\.venv\\Scripts\\python.exe -m pytest -q
```

Then use `openspec.cmd status --change build-coding-agent-mvp` before starting any separately scoped follow-up.
