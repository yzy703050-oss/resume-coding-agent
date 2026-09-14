## MODIFIED Requirements

### Requirement: Runs produce append-only events
The system SHALL append one audit event per line to a run-local event file. Every audit event MUST contain a schema version, run identifier, monotonic canonical sequence number, UTC timestamp, event type, and type-specific payload. Existing event lines MUST NOT be rewritten during a run. Runtime facts MUST be emitted once as canonical in-memory events; history and audit projections MUST derive independently from that fact before `EventWriter` writes the audit projection.

#### Scenario: Event order is inspectable
- **WHEN** a run emits multiple canonical events
- **THEN** audit sequence numbers are unique, contiguous, ordered by append position, and match the source sequences used by projected episodic history

### Requirement: The minimal event vocabulary covers the complete loop
The event vocabulary SHALL include `TaskStarted`, `ModelStep`, `ToolCalled`, `ToolResult`, `FileEdited`, `CommandExecuted`, `TestResult`, `AgentFinished`, and `AgentFailed`, and MAY add context-preparation, condensation, and memory-promotion diagnostics. Tool-related events MUST carry stable correlation metadata. Event payloads MUST contain observable inputs and results needed for debugging but MUST NOT contain API keys or other registered secrets.

#### Scenario: File edit is recorded
- **WHEN** `edit_file` changes a file successfully
- **THEN** the run contains the related correlated tool call, tool result, and `FileEdited` audit event with the repository-relative path

#### Scenario: Secret settings are omitted
- **WHEN** a run is configured with an API key
- **THEN** no audit event, episodic history entry, persistent-memory record, or summary contains the key value

#### Scenario: Audit output is more strictly truncated than history
- **WHEN** a producer-bounded command result exceeds the audit string limit
- **THEN** JSONL contains the audit-truncated projection while episodic history may retain a richer sanitized operational projection for later processors

### Requirement: Runs produce a machine-readable summary and patch
For every normally finalized terminal status, the system SHALL write a summary containing status, task, repository identity, effective non-secret configuration, combined and separately attributed model usage, elapsed time, step count, tool counts, changed files, latest test evidence, context-memory preset, aggregate context sizes, condensation metrics, memory-component diagnostics, and artifact paths. The final patch SHALL be stored separately in standard unified-diff form, including an empty file when no changes were produced.

#### Scenario: Completed run artifacts are self-describing
- **WHEN** a run terminates normally
- **THEN** its summary identifies the event file and patch and contains enough context, memory, main-model, and auxiliary-model metadata to compare it with another run
