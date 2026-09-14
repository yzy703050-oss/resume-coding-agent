# Hierarchical Context and Memory Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the V1 coding agent with bounded working, episodic, compressed, repository, and persistent project memory while preserving its synchronous one-action ReAct loop and audit artifacts.

**Architecture:** `ContextManager` becomes the runner-facing facade. Canonical in-memory events independently produce a rich sanitized history projection and a stricter audit projection; selection and budgeting produce `ContextItem` values that a formatting-only `ContextBuilder` renders. Project memory uses a validated candidate promotion pipeline and standard-library SQLite.

**Tech Stack:** Python 3.12, Pydantic 2, dataclasses, sqlite3/FTS5, ast, pytest, Ruff, mypy, OpenSpec

**Spec:** `openspec/changes/add-hierarchical-context-memory/`

## Global Constraints

- Preserve one synchronous model action or finish action per `AgentRunner` step.
- `Finalizer` remains the sole terminal-event and final-artifact owner.
- Baseline remains the default preset; full mode is opt-in.
- Cross-process L1/L2/L3 resumption is out of scope.
- No LangChain, LangGraph, vector database, tree-sitter, or new runtime dependency.
- LLM auxiliary work uses one gateway, counts toward global usage, and obeys stricter auxiliary hard limits.
- Project-memory extractors never receive a store and stores accept validated records only.
- Every task follows failing test -> observed failure -> minimal implementation -> passing focused tests -> review.

---

### Task 1: Context values, working memory, and budgets

**Files:**
- Create: `src/coding_agent/context/items.py`
- Create: `src/coding_agent/context/budget.py`
- Create: `src/coding_agent/memory/models.py`
- Create: `src/coding_agent/memory/working.py`
- Test: `tests/unit/context/test_budget.py`
- Test: `tests/unit/memory/test_working.py`

**Interfaces:**
- Produces: `ContextItem`, `ContextSection`, `PreparedContext`, `SizeEstimator`, `CharacterEstimator`, `ContextBudget`, `AuxiliaryBudget`, `WorkingMemory`.

- [ ] Write failing tests proving mandatory reserve, section caps, spill behavior, impossible mandatory input, pinned replacement/bounds, changed paths, latest test, and recent errors.
- [ ] Run `python -m pytest tests/unit/context/test_budget.py tests/unit/memory/test_working.py -q` and confirm import/test failures.
- [ ] Implement frozen value models, conservative character estimation, deterministic budget allocation, and bounded working-memory snapshots.
- [ ] Rerun the focused tests, Ruff, and mypy for the new modules.

### Task 2: Canonical events and episodic projection

**Files:**
- Modify: `src/coding_agent/events/models.py`
- Modify: `src/coding_agent/events/writer.py`
- Create: `src/coding_agent/events/recorder.py`
- Create: `src/coding_agent/events/projections.py`
- Create: `src/coding_agent/memory/episodic.py`
- Modify: `src/coding_agent/tools/registry.py`
- Modify: `src/coding_agent/tools/commands.py`
- Modify: `src/coding_agent/events/artifacts.py`
- Test: `tests/unit/events/test_recorder.py`
- Test: `tests/unit/memory/test_episodic.py`

**Interfaces:**
- Produces: `CanonicalRunEvent`, `AuditRunEvent`, `RunEventRecorder.record`, correlation context, `HistoryProjector`, `AuditProjector`, `EpisodicMemory`.

- [ ] Write failing tests proving one canonical sequence, shared correlation, richer history than audit truncation, separate secret sanitization, and validated terminal ownership.
- [ ] Run the focused tests and observe failures.
- [ ] Refactor `EventWriter` into an audit sink while retaining its legacy `append` compatibility; implement recorder and projections.
- [ ] Compose runtime tools/finalizer through the recorder and keep legacy event tests green.
- [ ] Run all event, tool-registry, command, and artifact tests plus Ruff/mypy review.

### Task 3: History processors and condensers

**Files:**
- Create: `src/coding_agent/memory/processors.py`
- Create: `src/coding_agent/memory/auxiliary.py`
- Create: `src/coding_agent/memory/condenser.py`
- Test: `tests/unit/memory/test_processors.py`
- Test: `tests/unit/memory/test_condenser.py`

**Interfaces:**
- Produces: `HistoryView`, `HistoryProcessorPipeline`, deterministic processors, `AuxiliaryModelGateway`, `NoOpCondenser`, `SlidingWindowCondenser`, `LLMSummarizingCondenser`.

- [ ] Write failing immutable-view and atomic-correlation tests for deduplication, large-output compaction, latest-test retention, and recent-tail selection.
- [ ] Implement processors and verify deterministic pipeline output.
- [ ] Write failing tests for soft/hard condensation, safe prefixes, structured summaries, cooldown/call limits, global/auxiliary budget denial, usage accounting, and fallback.
- [ ] Implement the auxiliary gateway and three condensers using a scripted structured-output client protocol.
- [ ] Run focused tests and static checks.

### Task 4: Python Repo Map

**Files:**
- Create: `src/coding_agent/repository/__init__.py`
- Create: `src/coding_agent/repository/symbols.py`
- Create: `src/coding_agent/repository/repomap.py`
- Test: `tests/unit/repository/test_repomap.py`

**Interfaces:**
- Produces: `RepoSymbol`, `PythonRepoMap.build`, `invalidate`, `refresh`, `select`, and budgeted rendering.

- [ ] Write a fixture test covering imports, classes, functions, methods, signatures, parents, syntax failures, stable ordering, relevance, and incremental refresh.
- [ ] Run it to observe the missing implementation.
- [ ] Implement confined `.py` scanning with `ast`, content hashes, lexical/path relevance, and per-file refresh.
- [ ] Run the focused suite and static checks.

### Task 5: Project identity and validated persistence

**Files:**
- Create: `src/coding_agent/memory/identity.py`
- Create: `src/coding_agent/memory/candidates.py`
- Create: `src/coding_agent/memory/promotion.py`
- Create: `src/coding_agent/memory/persistent.py`
- Create: `src/coding_agent/memory/retrieval.py`
- Test: `tests/unit/memory/test_identity.py`
- Test: `tests/unit/memory/test_candidates.py`
- Test: `tests/unit/memory/test_persistent.py`

**Interfaces:**
- Produces: `ProjectIdentityResolver`, extractor protocol/no-op/deterministic/LLM implementations, promotion pipeline, `ValidatedProjectMemoryRecord`, `ProjectMemoryStore`, `ProjectMemoryRetriever`.

- [ ] Write failing identity tests for canonical remotes, credential stripping, repeated runs, linked worktrees, different projects, and no-remote common-directory fallback.
- [ ] Implement versioned SHA-256 project identity and verify it never returns raw identity material.
- [ ] Write failing tests proving extractors have no store dependency and every candidate passes sanitization, policy, provenance, normalization, and dedup before write.
- [ ] Implement candidate extraction/promotion with LLM extraction routed through the auxiliary gateway.
- [ ] Write failing SQLite tests for schema version, validated-only writes, project isolation, dedup/reconfirmation, limits, FTS fallback, retrieval scores, and locked-store degradation.
- [ ] Implement the SQLite store and hybrid retriever; run focused tests and static checks.

### Task 6: Context selection, formatting, and manager facade

**Files:**
- Create: `src/coding_agent/context/selector.py`
- Create: `src/coding_agent/context/manager.py`
- Rewrite: `src/coding_agent/context/builder.py`
- Test: `tests/unit/context/test_selector.py`
- Rewrite: `tests/unit/context/test_builder.py`
- Test: `tests/unit/context/test_manager.py`

**Interfaces:**
- Produces: `ContextSelector.select`, formatting-only `ContextBuilder.build(PreparedContext)`, `ContextManager.start_run/prepare/record_step/finish_run`.

- [ ] Write failing selection tests for mandatory items, stable scoring, atomic groups, section caps, omission counts, and final estimate enforcement.
- [ ] Implement deterministic selection.
- [ ] Rewrite builder tests to prove it only formats `PreparedContext` and has no memory/repository/budget dependencies.
- [ ] Implement `ContextManager` composition and candidate collection from enabled components.
- [ ] Run all context and memory tests plus static checks.

### Task 7: RunState, runner, CLI, and preset migration

**Files:**
- Modify: `src/coding_agent/agent/state.py`
- Modify: `src/coding_agent/agent/runner.py`
- Modify: `src/coding_agent/config.py`
- Modify: `src/coding_agent/cli.py`
- Modify: `tests/behavior/conftest.py`
- Modify: `tests/behavior/test_react_loop.py`
- Modify: `tests/behavior/test_recovery.py`
- Modify: `tests/integration/test_cli.py`
- Test: `tests/behavior/test_context_memory.py`

**Interfaces:**
- Consumes all prior tasks; produces baseline-default/full-opt-in runtime composition and combined usage enforcement.

- [ ] Write failing behavior tests for manager-driven context, correlated events, large-history condensation/fallback, Repo Map refresh, and cross-run retrieval.
- [ ] Move mutable context ownership out of `RunState`, retain lifecycle/final metrics, and add main/auxiliary usage breakdown.
- [ ] Update runner to use the manager without component-specific branches and preserve one tool execution per step.
- [ ] Add validated CLI/config preset and auxiliary limits; keep baseline default.
- [ ] Run state, behavior, CLI, event, artifact, and existing baseline regression suites.

### Task 8: Evaluation and artifacts

**Files:**
- Modify: `src/coding_agent/events/artifacts.py`
- Modify: `src/coding_agent/evaluation/runner.py`
- Modify: `src/coding_agent/evaluation/baseline.py`
- Modify: `tests/e2e/test_baseline_evaluation.py`
- Test: `tests/e2e/test_memory_ablation.py`

**Interfaces:**
- Produces additive memory metrics in summary/evaluation and named ablation execution.

- [ ] Write failing tests for main/auxiliary/combined usage, per-section context, condensation, candidate, Repo Map, retrieval, and disabled-component metrics.
- [ ] Add additive summary fields without changing patch or terminal authority.
- [ ] Implement named ablation reports over identical scripted fixtures.
- [ ] Run E2E and artifact tests plus static checks.

### Task 9: Documentation and complete verification

**Files:**
- Modify: `README.md`
- Modify: `TASK_STATE.md`
- Modify: `openspec/changes/add-hierarchical-context-memory/tasks.md`

- [ ] Document the architecture, presets, budgets, database placement, safety boundaries, event projections, and offline commands.
- [ ] Run `python -m pytest -q`.
- [ ] Run `ruff check .`, `ruff format --check .`, and `mypy src/coding_agent`.
- [ ] Run `openspec.cmd validate --all --strict` and `openspec.cmd validate add-hierarchical-context-memory --strict`.
- [ ] Run a fresh baseline offline demo and a full-mode scripted demo, inspect artifacts/database isolation, and record exact evidence.
- [ ] Review the complete diff for scope, secrets, generated files, migration compatibility, and terminal-event uniqueness.
