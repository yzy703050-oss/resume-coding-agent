## Context

Approved detailed design: `docs/superpowers/specs/2026-09-15-langchain-langgraph-design.md`. Existing memory/tool/event components are retained.

## Goals / Non-Goals

Actual compiled graph controls iteration and routing; actual LangChain integration controls live model invocation. No checkpoint, replay, remote tracing or paid evaluation.

## Decisions

- Typed transient graph state transports one RunState and current messages/response/result. Guard clears stale response/result.
- Nodes are LangChain RunnableLambda objects; edges control iteration. Agent steps count model decisions, not graph super-steps. Recursion limit is max_steps * 5 + 10.
- AgentRunner owns context startup, exceptions and finalization. Memory-finish failures expose sanitized exception type in summary without losing primary artifacts.
- LangChain init_chat_model selects DeepSeek or OpenAI provider. bind_tools uses registry schema plus finish. Invalid/multiple calls are recoverable format observations.
- No tool implementation is replaced with framework shell tools; registry owns validation and emission. correlation_id remains step-N.
- Reported usage counts once; unknown cost stays unknown. Automatic provider retries capped at one, tracing disabled explicitly. Existing failure-usage accounting limitations remain documented.

## Risks / Trade-offs

Framework dependencies increase installation size. API compatibility is verified through mock transport, not paid end-to-end calls. RunState is a mutable run-local object, unsuitable for checkpoint replay; resumption is out of scope. Direct graph state/stream output is not an audit-sanitized public artifact.

## Migration Plan

Execute the approved TDD plan; preserve CLI/ModelClient protocol and scripted tests; validate the entire suite and update actual version evidence. Leave git integration to user.
