## Why

The user approved migrating the existing single-agent ReAct runtime to real LangGraph orchestration and LangChain model integration. A wrapper around the handwritten loop would not deliver this architecture.

## What Changes

- Replace the loop with guard/prepare/decide/execute/observe graph nodes and conditional edges.
- Use LangChain provider integrations and authoritative registry schemas for live models.
- Preserve run-local memory, tool validation, event facts and sole Finalizer ownership.
- Finalize context-start failures and degrade safely on memory-finish failures.
- Keep all verification offline; make no autonomous model-quality claims.

## Capabilities

### New Capabilities
- `framework-runtime`: Framework orchestration and provider integration with the existing runtime contracts.

### Modified Capabilities
None. Existing lifecycle/tool/artifact behaviors remain authoritative; this change adds an implementation architecture requirement without weakening their specifications.

## Dependencies and Scope

Depends on the archived `2026-09-14-build-coding-agent-mvp` baseline and the currently implemented foundation of active `add-hierarchical-context-memory`. It does not claim the latter's outstanding section 12 acceptance gaps are complete, nor require archiving that change. The memory change preserves ReAct semantics; this change replaces its implementation mechanism while retaining those semantics. Its original no-framework dependency restriction applies to that original increment, not this explicitly approved later migration.

No checkpoint/resumption, LangSmith tracing, multi-agent runtime or paid evaluation. Baseline remains default and full remains opt-in.

## Impact

New framework/provider dependencies; graph and model-adapter modules; CLI composition; offline tests and documentation. Public AgentRunner and artifact schema version 1 remain compatible, with additive configuration metadata.
