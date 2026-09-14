# Coding Agent V2 — Task State

Last updated: 2026-09-14 (Asia/Shanghai)

## Objective

Implement OpenSpec change `add-hierarchical-context-memory` on top of the archived and implemented `build-coding-agent-mvp` baseline. Preserve the synchronous one-action ReAct loop, fixed tool boundary, independent oracle, and sole terminal `Finalizer`.

## Implemented architecture

- Typed `ContextItem`, explicit total/section budgets, deterministic atomic-group selection, and formatting-only `ContextBuilder`.
- Bounded run-local `WorkingMemory`; canonical event recording with independent history and audit projections; immutable episodic processors and deterministic/LLM-capable condensers.
- One `AuxiliaryModelGateway` with separate auxiliary accounting plus combined token/cost enforcement.
- Static confined Python AST Repo Map with deterministic selection and single-file refresh.
- Stable versioned `project_id` from canonical sanitized origin or resolved Git common directory.
- Store-independent no-op, deterministic, and structured-LLM candidate extractors.
- Mandatory candidate sanitizer, policy, provenance validator, normalizer, deduplicator, and validated-record-only SQLite API.
- Project-isolated, versioned, bounded SQLite storage and inspectable retrieval with an optional semantic scorer seam.
- Named `baseline`, `processor`, `condenser`, `repo-map`, `project-memory`, and `full` presets. `baseline` remains the default.
- Additive main/auxiliary/combined usage and context/memory metrics in run summaries and evaluation results.

## Scope decisions

- Cross-process Run resumption remains out of scope; only curated L4 project knowledge persists.
- Full mode remains opt-in. A later evidence-backed design decision is required before any default change.
- No vector database, embeddings, tree-sitter, new runtime dependency, multi-agent runtime, or network requirement was added.

## Verification evidence

- `python -m pytest -q` → 125 passed in 45.87s, including fresh baseline/full preset evaluation and cross-run project-memory tests.
- `ruff check .` → all checks passed.
- `ruff format --check .` → 110 files already formatted.
- `mypy src/coding_agent` → success, no issues in 53 source files (strict mode).
- `openspec.cmd validate --all --strict` → 5 passed, 0 failed.
- `openspec.cmd validate add-hierarchical-context-memory --strict` → valid; two informational long-requirement notices only.
- `git diff --check` → exit 0; only Git line-ending conversion warnings were emitted.

OpenSpec implementation tasks are complete. The change has not been archived, committed, merged, or pushed; integration remains a user decision.
