## Why

The V1 agent deliberately keeps context management small and deterministic, but the current `RunState` and `ContextBuilder` cannot preserve a complete run history, compress older work, expose repository structure, or retrieve useful knowledge from earlier runs. As command output and file reads grow, old observations are discarded rather than transformed into durable progress, facts, failed attempts, and verification evidence.

The next architecture increment should introduce a hierarchical context and memory engine without replacing the existing ReAct loop, tool surface, execution boundary, audit artifacts, or finalization ownership.

## What Changes

- Add a `ContextManager` that coordinates working memory, episodic history, condensed history, repository memory, persistent project memory, context selection, and budgeting.
- Reduce `ContextBuilder` to deterministic formatting of already-selected `ContextItem` values.
- Move context payload collections out of `RunState`, leaving lifecycle, limits, combined usage accounting, and final-result facts under its ownership while independently composed memory components own their data.
- Add a canonical in-memory runtime-event boundary. Audit sanitization/truncation and model-facing history projection independently derive from the same canonical event so `EventWriter` cannot accidentally constrain `EpisodicMemory` fidelity.
- Add composable history processors and pluggable no-op, sliding-window, and LLM-summarizing condensers with bounded triggering and graceful fallback.
- Add a Python AST repository map with incremental refresh and an independently budgeted context view.
- Add a stable, versioned `project_id` derived from a sanitized canonical Git remote when available, otherwise from the normalized resolved Git common-directory path.
- Add a `ProjectMemoryCandidateExtractor` boundary with deterministic extraction and an optional structured LLM extractor. Extractors only propose candidates; sanitization, policy, provenance validation, and deduplication must all succeed before the SQLite store accepts a validated record.
- Add a SQLite project-memory store with typed records, bounded retrieval, and a future vector-retrieval seam without introducing a vector database.
- Count every auxiliary model call against the global run token/cost limits and against stricter per-run auxiliary call/token/cost limits. Budget exhaustion skips optional extraction or uses deterministic condensation fallback.
- Add configuration flags and evaluation metrics for baseline, processor, condenser, Repo Map, persistent-memory, and full variants.

## Capabilities

### New Capabilities

- `hierarchical-context-memory`: Builds bounded model context from four distinct memory levels, repository structure, and tool contracts while keeping selection, compression, and formatting separate.
- `project-memory`: Persists and retrieves bounded, typed, provenance-linked project knowledge across runs.
- `memory-evaluation`: Verifies memory behavior and compares independently configurable context-engine variants.

### Modified Capabilities

- `agent-run`: Replace direct state-to-message context assembly with `ContextManager`, combined main/auxiliary budget accounting, and correlated episodic history while preserving the bounded ReAct loop.
- `run-artifacts`: Preserve append-only audit artifacts while deriving them from canonical in-memory events and adding correlation/context-memory diagnostics.
- `baseline-evaluation`: Add named memory ablations plus context, auxiliary-call, condensation, Repo Map, and project-memory metrics.

## Prerequisite / Change Dependency

This change depends on the implementation and acceptance baseline defined by the archived `2026-09-14-build-coding-agent-mvp` change and the resulting main capability specs.

The dependency lifecycle is:

1. The context-memory design was reviewed without altering the completed V1 baseline.
2. After explicit design approval, `build-coding-agent-mvp` was archived first as `2026-09-14-build-coding-agent-mvp`.
3. This change was reconciled against the resulting base specs and expresses behavior changes as `MODIFIED` deltas.
4. Strict validation and Superpowers `writing-plans` precede TDD implementation.

No implementation task in this change may weaken the archived V1 ReAct, event, artifact, safety, or independent-evaluation contracts.

## Impact

- Primary changes are limited to `agent/state.py`, `agent/runner.py`, `context/`, new `memory/` and `repository/` packages, event recording, configuration/composition, and evaluation.
- `ToolRegistry`, tool implementations, `ModelClient`, `ExecutionBackend`, `EventWriter`, `Finalizer`, and action models retain their current public roles.
- Existing run artifacts remain readable as schema version 1. New optional event fields and new context metrics are additive; an incompatible artifact shape would use a new schema version.
- The implementation depends on the archived V1 behavior and main specs produced by `2026-09-14-build-coding-agent-mvp`.
- SQLite is the only new persistence mechanism and uses the Python standard library. No LangChain, LangGraph, vector database, tree-sitter, or other framework-sized dependency is introduced.
- Cross-process run resumption remains out of scope. Run-local L1/L2/L3 state is not rehydrated after process exit.
- The baseline preset remains supported and remains the default for migration. Full mode may become the default only after evaluation demonstrates a justified quality/cost/reliability trade-off and a later explicit design decision approves the switch.
- Implementation is gated on design approval and will follow a separate Superpowers implementation plan with TDD and review checkpoints.
