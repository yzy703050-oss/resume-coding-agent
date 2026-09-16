## ADDED Requirements

### Requirement: Execute through a compiled ReAct state graph
The system SHALL use a compiled LangGraph graph with separate budget checking, context preparation, model decision, tool execution and observation nodes. Conditional edges SHALL control iteration and termination; a handwritten loop wrapped in one graph node MUST NOT be the default runtime.

#### Scenario: Tool decision progresses through nodes
- **WHEN** a model emits one valid tool action within limits
- **THEN** the graph executes the existing registry once, updates memory from its observation and returns to the budget guard

#### Scenario: Limits count model decisions
- **WHEN** a run takes multiple graph nodes per model action
- **THEN** max_steps counts model decisions including format failures, and graph recursion allowance does not stop an otherwise permitted run early

### Requirement: Integrate live models through LangChain
The system SHALL use LangChain provider integration, message conversion and tool binding for default live CLI runs. Existing registry schemas SHALL remain authoritative. Each response MUST decode into exactly one valid tool or finish action; malformed or multiple actions SHALL be recoverable observations.

#### Scenario: DeepSeek connection settings are applied
- **WHEN** a DeepSeek run is composed
- **THEN** its provider key, endpoint, disabled thinking and configured output limit are applied through the LangChain SDK without a second maintained tool schema

#### Scenario: Response usage is counted once
- **WHEN** the SDK returns prompt and completion usage
- **THEN** those values are added once to run accounting and unavailable cost remains unknown

### Requirement: Preserve finalization and audit boundaries
The system SHALL retain the sole Finalizer, existing tool safety policy and single event fact source. Context startup exceptions MUST enter finalization. Optional memory-finish exceptions MUST NOT prevent patch, summary and terminal event creation. Framework tracing and checkpoint replay SHALL remain disabled in default runs.

#### Scenario: Startup context fails
- **WHEN** context startup raises an exception
- **THEN** the run becomes failed without a model call and produces one terminal event with run artifacts

#### Scenario: Optional memory cleanup fails
- **WHEN** memory finish raises after the selected run status
- **THEN** the primary artifacts are finalized and the summary records only a sanitized exception type diagnostic
