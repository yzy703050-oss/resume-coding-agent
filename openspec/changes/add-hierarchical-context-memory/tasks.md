## 0. Design Approval Gate

> 2026-09-15 audit: checked items below record the earlier implementation pass, not exhaustive acceptance. Outstanding design requirements are explicitly tracked in section 12; this change must not be called fully complete or archived until they are verified. Scripted preset runs are engineering checks, not model-quality evaluation.

- [x] 0.1 Review `proposal.md`, `design.md`, and all delta specs; obtain the user's second explicit design approval before any prerequisite archival or implementation planning.
- [x] 0.2 After approval, verify `build-coding-agent-mvp` is 4/4 complete and strictly valid, then archive it first so its capabilities become the main OpenSpec baseline.
- [x] 0.3 Reconcile this change against the archived base capabilities, add required `MODIFIED` deltas, and run strict validation again.
- [x] 0.4 Only after 0.1-0.3, use Superpowers `writing-plans` to create the detailed TDD implementation plan. Do not implement from this checklist alone.

## 1. Context Values and Budget Foundation

- [x] 1.1 Add failing unit tests for `ContextItem`, size estimation, fixed overhead, response reserve, section caps, spill order, atomic groups, impossible mandatory input, combined main/auxiliary usage, and auxiliary hard limits.
- [x] 1.2 Implement the minimal context value models, replaceable estimator, `ContextBudget`, run usage breakdown, and `AuxiliaryBudget`; verify focused tests, Ruff, and mypy.
- [x] 1.3 Review the slice against the hierarchical-context-memory budget requirements before continuing.

## 2. Working Memory and Baseline Compatibility

- [x] 2.1 Add failing tests for bounded pinned excerpts, changed paths, latest test, errors, progress, and deterministic snapshots.
- [x] 2.2 Implement `WorkingMemory` and a V1 compatibility item producer without changing runner behavior.
- [x] 2.3 Prove the baseline preset produces semantically equivalent scripted model context and keeps all existing context tests green; review the slice.

## 3. Episodic History and Canonical Event Recording

- [x] 3.1 Add failing tests for canonical in-memory events, deterministic correlation IDs, pre-audit history projection, independent history/audit sanitization, audit-only filtering, richer operational history than audit payloads, secret safety, and terminal-event ownership.
- [x] 3.2 Implement `RunEventRecorder`, `CanonicalRunEvent`, separate history/audit projectors and sanitizers, additive correlation metadata, and run-local `EpisodicMemory` while preserving JSONL compatibility.
- [x] 3.3 Prove `EventWriter` accepts only audit projections, `EpisodicMemory` never consumes audit-truncated events, and neither projection can be independently emitted as a competing event fact.
- [x] 3.4 Run existing event, artifact, tool, behavior, and CLI suites; review for duplicate event emission or persistence.

## 4. History Processor Pipeline

- [x] 4.1 Add failing immutable-view tests for pipeline order, deduplication, large output, test result handling, recent-tail protection, and action/result atomicity.
- [x] 4.2 Implement the processor protocol and initial deterministic processors with no model calls.
- [x] 4.3 Verify each processor independently and in composition; review transformation diagnostics and determinism.

## 5. Condensed Memory

- [x] 5.1 Add failing tests for soft/hard thresholds, safe prefixes, structured summaries, revisions, cooldown, per-component call limits, combined global usage, auxiliary token/cost hard limits, budget denial, and no-op/sliding behavior.
- [x] 5.2 Implement `NoOpCondenser` and `SlidingWindowCondenser`, then scripted failing tests for the LLM condenser before implementing it.
- [x] 5.3 Route LLM condensation only through `AuxiliaryModelGateway`, charge reported usage to auxiliary and global totals, add graceful fallback and diagnostics, then run large-history, budget-denied, and failed-condenser behavior tests and review the slice.

## 6. Context Selection and Formatting Boundary

- [x] 6.1 Add failing tests for deterministic multi-source ranking, mandatory inclusion, section caps, atomic groups, omission metadata, and final estimate enforcement.
- [x] 6.2 Implement `ContextSelector`, `PreparedContext`, and formatting-only `ContextBuilder`.
- [x] 6.3 Introduce `ContextManager.prepare` over existing sources and prove `ContextBuilder` has no store, processor, condenser, repository, or budget policy dependency; review the slice.

## 7. RunState and Runner Migration

- [x] 7.1 Add behavior tests for the target runner sequence and for advanced components being absent from runner branches.
- [x] 7.2 Move mutable context payloads out of `RunState`, add `ContextManager.start_run/record_step/finish_run`, and update composition.
- [x] 7.3 Run all state, behavior, finalization, CLI, and baseline tests; remove temporary compatibility properties only after parity; review the slice.

## 8. Python Repository Memory

- [x] 8.1 Add AST fixture tests for modules, imports, classes, functions, methods, parents, signatures, parse failures, stable ordering, relevance, and budget rendering.
- [x] 8.2 Implement the confined Python Repo Map with deterministic startup scan and single-file invalidation/refresh.
- [x] 8.3 Add edit-refresh behavior coverage and Repo Map timing/selection metrics; review the slice without adding tree-sitter or PageRank.

## 9. Persistent Project Memory

- [x] 9.1 Add failing `ProjectIdentityResolver` tests for canonical remote forms, credential stripping, same-project cross-run stability, linked worktrees, different-project isolation, and no-remote Git common-directory fallback.
- [x] 9.2 Implement versioned `project_id` hashing without storing or exposing raw remote URLs or local identity paths.
- [x] 9.3 Add failing extractor tests for deterministic run-summary/evidence candidates, optional structured LLM candidates, malformed output, no store dependency, and auxiliary-budget denial.
- [x] 9.4 Implement no-op, deterministic, and LLM-structured `ProjectMemoryCandidateExtractor` variants; route the LLM variant only through `AuxiliaryModelGateway`.
- [x] 9.5 Add failing promotion tests for candidate sanitization, type/evidence policy, provenance validation against canonical events, normalization, deduplication, and rejection before store access.
- [x] 9.6 Implement the promotion pipeline and make `ProjectMemoryStore` accept only `ValidatedProjectMemoryRecord`.
- [x] 9.7 Add failing SQLite tests for schema versioning, project isolation, validated-record writes, reconfirmation, limits, FTS fallback, and locking failure; then implement the standard-library SQLite store.
- [x] 9.8 Add failing retrieval-score tests, implement transparent hybrid retrieval, and test the semantic-scorer extension seam without embeddings.
- [x] 9.9 Add cross-run behavior tests for deterministic and structured architecture/convention candidates; review persistence safety and lifecycle.

## 10. Configuration, Artifacts, and Evaluation

- [x] 10.1 Add validated component configs, auxiliary hard limits, and named baseline/processor/condenser/repo-map/project-memory/full presets composed with no-op implementations; keep baseline as the default.
- [x] 10.2 Extend event/summary outputs additively with context and memory metrics while preserving terminal ownership and old readers.
- [x] 10.3 Extend deterministic evaluation with per-section context, selection, combined/main/auxiliary usage, condensation, candidate extraction/rejection, Repo Map, and retrieval metrics and run all presets on identical fixtures.
- [x] 10.4 Evaluate full mode as opt-in. Do not change the default in this change; a future default switch requires separate evidence-backed approval.

## 11. Complete Verification

- [x] 11.1 Run all unit, behavior, integration, and E2E tests without a network key.
- [x] 11.2 Run Ruff lint/format checks, strict mypy, and strict OpenSpec validation.
- [x] 11.3 Run a fresh Windows offline demo for baseline and full presets and inspect events, database placement, patch, summary, and independent oracle.
- [x] 11.4 Perform final architecture, persistence-safety, context-budget, failure-fallback, dependency, and scope review; add a failing regression test before every accepted fix.
- [x] 11.5 Record exact verification evidence and stop before archive/merge decisions.

## 12. Outstanding acceptance gaps (not part of the zero-paid-evaluation resume slice)

- [ ] 12.1 Enforce final rendered context overhead, runtime section allocation and recent/latest retention priorities.
- [ ] 12.2 Validate candidate content against canonical evidence, beyond sequence/path membership.
- [ ] 12.3 Constrain Repo Map symlink/ignored paths and add scan diagnostics/timing.
- [ ] 12.4 Complete SQLite schema-forward checks, lifecycle and graceful degradation diagnostics.
- [ ] 12.5 Complete auxiliary per-request hard reservations and failure-attempt accounting before production LLM wiring.
- [ ] 12.6 Build evaluator-owned hidden-test isolation before reporting autonomous model outcomes. Real evaluation remains deferred by user request; full remains opt-in.
