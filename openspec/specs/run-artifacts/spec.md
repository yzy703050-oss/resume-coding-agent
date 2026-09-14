# run-artifacts Specification

## Purpose
Defines lightweight, versioned run records that support debugging, inspection, replay, and later evaluation without implementing a general event-sourcing platform.

## Requirements

### Requirement: Runs produce append-only events
The system SHALL append one JSON event per line to a run-local event file. Every event MUST contain a schema version, run identifier, monotonic sequence number, UTC timestamp, event type, and type-specific payload. Existing event lines MUST NOT be rewritten during a run.

#### Scenario: Event order is inspectable
- **WHEN** a run emits multiple events
- **THEN** their sequence numbers are unique, contiguous, and ordered by append position

### Requirement: The minimal event vocabulary covers the complete loop
The event vocabulary SHALL include `TaskStarted`, `ModelStep`, `ToolCalled`, `ToolResult`, `FileEdited`, `CommandExecuted`, `TestResult`, `AgentFinished`, and `AgentFailed`. Event payloads MUST contain observable inputs and results needed for debugging but MUST NOT contain API keys.

#### Scenario: File edit is recorded
- **WHEN** `edit_file` changes a file successfully
- **THEN** the run contains the related tool call, tool result, and `FileEdited` event with the repository-relative path

#### Scenario: Secret settings are omitted
- **WHEN** a run is configured with an API key
- **THEN** no event or summary contains the key value

### Requirement: Every started run has one terminal artifact
One finalization component SHALL be the sole writer of terminal events and final artifacts. For every run that reaches `completed`, `step_limit`, `budget_limit`, `cancelled`, or `failed`, it SHALL append exactly one `AgentFinished` or `AgentFailed` event and produce `patch.diff` and `summary.json`. The runner and tools MUST NOT write terminal events. `completed` SHALL map to `AgentFinished`; all other terminal statuses SHALL map to `AgentFailed` with the actual status in the payload. If the process is forcibly terminated or artifact I/O fails before finalization completes, readers SHALL classify the artifact as incomplete rather than completed.

#### Scenario: Step limit produces a terminal event
- **WHEN** a run reaches its step limit
- **THEN** the finalizer records one `AgentFailed` event whose payload identifies `step_limit` and writes the patch and summary

#### Scenario: Finalization cannot be repeated
- **WHEN** finalization has already been invoked for a run
- **THEN** a second invocation is rejected without appending another terminal event or rewriting final artifacts

### Requirement: Runs produce a machine-readable summary and patch
For every normally finalized terminal status, the system SHALL write a summary containing status, task, repository identity, effective non-secret configuration, model usage, elapsed time, step count, tool counts, changed files, latest test evidence, and artifact paths. The final patch SHALL be stored separately in standard unified-diff form, including an empty file when no changes were produced.

#### Scenario: Completed run artifacts are self-describing
- **WHEN** a run terminates normally
- **THEN** its summary identifies the event file and patch and contains enough metadata to compare it with another run
