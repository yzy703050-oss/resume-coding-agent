## Why

Independent developers need a small, inspectable coding agent that can turn a local repository issue into a tested patch without hiding the execution loop behind a large agent framework. The project also needs reproducible run evidence so its behavior, failures, and engineering trade-offs can be demonstrated and evaluated credibly.

## What Changes

- Add a Typer CLI that accepts a local repository and coding task, then runs a single ReAct-style coding loop.
- Add deterministic repository tools for listing, searching, reading, editing, command execution, and diff inspection.
- Add a controlled Windows-local execution backend with workspace confinement, command policy checks, timeouts, output capture, and process cleanup.
- Add a minimal context builder that selects task instructions, recent observations, explicitly read code, and important command results for each model step.
- Add lightweight append-only run events plus final patch and run summaries for debugging, replay, and evaluation.
- Add unit, behavior, and small local end-to-end evaluations before integrating the separate Linux SWE-bench Lite evaluator.

## Capabilities

### New Capabilities

- `agent-run`: CLI-driven coding-task execution, the ReAct loop, model/tool interaction, retry behavior, limits, and termination.
- `workspace-tools`: Confined repository inspection, editing, command execution, and Git diff operations through deterministic tools.
- `run-artifacts`: Versioned append-only run events and final patch/run summaries.
- `baseline-evaluation`: Deterministic agent behavior scenarios and small local repository tasks that exercise the complete loop.

### Modified Capabilities

None.

## Impact

- Introduces a greenfield Python package, Typer CLI, test fixtures, and project configuration.
- Requires an OpenAI-compatible model endpoint for real runs; tests use scripted model responses and require no network access.
- Executes approved commands directly in a trusted local repository on Windows; general sandboxing is explicitly deferred.
- Does not include FastAPI, a web UI, persistent memory, multiple agents or strategies, MCP, worktrees, or distributed execution.
- Establishes stable seams for a future sandboxed execution backend and richer context engine without implementing either in this change.
