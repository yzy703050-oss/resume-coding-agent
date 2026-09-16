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

## 2026-09-15 audit correction and resume release

Later explicitly approved migration: compiled LangGraph guard/prepare/decide/execute/observe replaces the handwritten loop; live model composition uses LangChain init_chat_model/provider integrations, message conversion and original registry schema binding. Scripted clients go through the same graph. Existing memory gaps remain open; separate `migrate-langchain-langgraph` change expresses this later architecture increment without declaring the context-memory change complete.

The earlier checklist overstated coverage: the architecture is implemented as a foundation, not proof that every design requirement is complete. See `docs/RESUME.md` for pending budget, recency, provenance, repository confinement, SQLite lifecycle and auxiliary-call hardening. Earlier test evidence above is historical, not verification of today's changes.

Current approved scope: explicit DeepSeek preset/output cap, bounded deterministic summary, redact-before-truncate candidate sanitization, runtime secret propagation, combined remaining-token display, read-only evaluation protocol, honest scripted labels, Chinese evaluation/resume documentation and offline Windows CI. No paid calls, no real-model measurements. True metrics remain null.

The change has not been archived, committed, merged, or pushed; integration remains a user decision.

Fresh resume-slice verification (2026-09-15): `pytest -q` 131 passed in 27.03s; Ruff lint passed; Ruff format check 116 files; strict mypy passed on 54 source files; strict OpenSpec 5 passed/0 failed; diff whitespace check passed (line-ending warnings only). Evaluation-plan CLI exited 0 with `not_run`, null metrics and `api_calls_made=0`. Windows CI is configured but has not run here. No DeepSeek or other paid model endpoint was called.

Framework migration verification (later 2026-09-15): final production full suite 148 passed in 75.73s; one subsequently added malformed-function characterization passed separately (no implementation change), 149 tests now present. Ruff lint/format passed; mypy passed on 57 source files; OpenSpec 6 passed/0 failed; pip check and diff whitespace checks passed. Actual LangChain provider SDKs and CLI composition verified via mock HTTP only. Scripted framework smoke 3/3 is not autonomous success rate. Read-only review: no Critical/Important issues; one effective-config metadata Minor fixed with failing/passing regression. Dependencies and Python 3.14.6 local environment recorded in docs/FRAMEWORK.md; configured Python 3.12 CI remains unexecuted. Worktree preserved on feat/memory-engine; no commit/push/archive or paid call.
