## MODIFIED Requirements

### Requirement: Execute a bounded ReAct loop
The system SHALL perform each model step as exactly one structured tool action or one finish action, execute valid tool actions, convert every result into an observation, and make its correlated action/result history available to context management. The system MUST count model steps consistently, including malformed responses that require model correction. The runner MUST delegate memory processing, condensation, retrieval, selection, and context budgeting to `ContextManager` rather than implementing component-specific policy.

#### Scenario: Tool result feeds the next step
- **WHEN** the model requests a valid tool action
- **THEN** the tool executes once, the canonical correlated action/result events are recorded once, and the result is available to the next context preparation

#### Scenario: Malformed action is recoverable
- **WHEN** the model response is not a valid tool action or finish action
- **THEN** the system records a format-error history entry and allows a later model step while limits remain

### Requirement: Context is bounded and task-focused
Each model request SHALL be produced from selected context items that may include system instructions, task and remaining limits, working memory, recent correlated history, condensed history, pinned code, Python Repo Map, and retrieved project memory. The system MUST enforce a configurable estimator budget including tool schemas and response reserve. It MUST preserve the task and mandatory working state while pruning or transforming optional material. Selection and formatting MUST be separate responsibilities. The baseline preset SHALL remain available and SHALL remain the default during this change.

#### Scenario: Old observations exceed the budget
- **WHEN** accumulated history exceeds its configured allocation
- **THEN** processors and the configured condenser produce a bounded view that retains the task, mandatory working state, latest test summary, and protected recent correlated history

#### Scenario: Pinned files exceed their budget
- **WHEN** successful file reads exceed the pinned-context allocation
- **THEN** bounded excerpts from important, current, or changed files are selected ahead of stale reads and all selected context remains within the estimator budget

## ADDED Requirements

### Requirement: Model budgets include auxiliary calls
The system SHALL account for main-model and auxiliary-model usage separately and as a combined run total. Global token and cost limits MUST apply to their combined usage. Auxiliary calls MUST additionally obey per-run call, token, cost, and per-component call limits. A model call that cannot fit its applicable remaining hard limits MUST NOT start.

#### Scenario: Auxiliary usage exhausts the global limit
- **WHEN** a condenser or memory-extraction call causes combined usage to reach the global run limit
- **THEN** the run starts no later main or auxiliary model call and terminates through the existing budget-limit path when appropriate
