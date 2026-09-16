# LangChain / LangGraph Implementation Plan

> **For agentic workers:** Use executing-plans inline, with TDD and review checkpoints. No subagent delegation or git integration.

**Goal:** Replace the handwritten ReAct loop with compiled LangGraph and default live model composition with LangChain.

**Architecture:** Keep RunState as the run-local lifecycle owner. A typed graph transports transient messages/response/result; nodes invoke existing context, model, tool and observation boundaries. AgentRunner owns exceptions and Finalizer.

**Tech Stack:** Python 3.12, LangGraph 1.x, LangChain 1.x, provider integrations, Pydantic, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-09-15-langchain-langgraph-design.md`

## Global constraints

- Preserve existing uncommitted changes and public runner API; no git commits/pushes.
- No paid API calls, LangSmith tracing, checkpoint or resumption; baseline remains default.
- One model action per agent step, one terminal event per run, unchanged authoritative tool schemas and execution policy.
- Token limits remain post-response reported-usage stops; do not claim a billing hard cap.

### Task 1: Graph execution and lifecycle

Files: modify `agent/runner.py`; create `agent/graph.py`; test `tests/behavior/test_graph_runtime.py`.

Interfaces: `ReActGraphState` has `run: RunState`, transient messages, response and result. `build_react_graph(context_manager,model,tools,event_writer)` produces compiled graph. Runner invokes with recursion limit `max_steps * 5 + 10`.

- [x] RED: add startup and finish-memory failure regressions; execute `pytest tests/behavior/test_graph_runtime.py -q` and observe missing finalization. Long-cycle characterization uses 12 read actions then finish, expects step_count=13 and one terminal event.
  ```python
  def broken_start():
      raise RuntimeError("secret")


  monkeypatch.setattr(harness.context_manager, "start_run", broken_start)
  assert harness.runner.run(harness.state).status is RunStatus.FAILED
  assert len(terminal_events(harness.run_dir)) == 1
  ```
- [x] GREEN: implement guard/prepare/decide/execute/observe nodes. Guard clears transient results; decide maps format errors to observation and checks usage before routing. Preserve correlation scope around registry. Move context start into try; finish-memory errors record sanitized diagnostic; finalize regardless.
- [x] Verify: `pytest tests/behavior tests/integration/test_cli.py -q`; inspect graph execution trace through real compiled graph. No implementation commits.

### Task 2: LangChain model composition

Files: create `models/langchain_client.py`, `models/tool_binding.py`; modify `cli.py`, `config.py`, `pyproject.toml`; create `tests/unit/models/test_langchain_client.py`.

Interfaces: `LangChainModelClient(chat_model: BaseChatModel).complete(messages, tool_schemas) -> ModelResponse`; factory consumes RunConfig. Tool conversion returns LangChain-compatible OpenAI function schemas from registry schema plus finish schema.

- [x] RED: tests construct ChatDeepSeek/ChatOpenAI with mock HTTP, call adapter and assert real outgoing tool schema/max_tokens/thinking/endpoint, decoded action and usage. Reject no/multiple/malformed tool calls. Verify default CLI composition uses new adapter without executing network.
  ```python
  reply = client.complete([Message("user", "fix")], schemas)
  assert reply.usage.total_tokens == 8
  assert reply.action.kind == "finish"
  assert payload["thinking"] == {"type": "disabled"}
  ```
- [x] GREEN: bind tools, convert messages, inspect AIMessage tool_calls/invalid_tool_calls, validate finish arguments, map usage_metadata without cost invention. Use explicit callbacks=[] to avoid implicit tracing and configure provider retries. Add provider field and output/request settings to effective config.
- [x] Verify: focused model/CLI tests, Ruff and mypy; install compatible dependencies only, no model invocation outside mock HTTP.

### Task 3: Documentation and acceptance

Files: README, docs/RESUME.md, TASK_STATE, new OpenSpec graph migration change.

- [x] Update real architecture/reading route/version evidence, not merely aspirational resume wording; preserve outstanding memory gaps.
- [x] Run full pytest, Ruff check/format, strict mypy, strict OpenSpec and offline protocol/demo. Record exact fresh outputs and zero live calls.
- [x] Leave worktree and branch untouched; report completed migration and keep the approved no-integration choice, no commit/push.

## Acceptance evidence

Windows Python 3.14.6; dependencies listed in docs/FRAMEWORK.md. Final production revision: 148 full-suite tests passed in 75.73s; one additional malformed-provider-fields characterization passed separately without production changes. Ruff lint/format passed, mypy 57 files passed, OpenSpec 6/6 passed, pip check passed. Offline scripted smoke 3/3 and read-only evaluation plan passed. No paid calls. Focused read-only reviewer found no Critical/Important issues; effective-thinking metadata Minor fixed and verified. Run-local mutable state/no checkpoint is deliberate. Existing memory and failed-usage accounting acceptance gaps remain deferred, not silently completed.
