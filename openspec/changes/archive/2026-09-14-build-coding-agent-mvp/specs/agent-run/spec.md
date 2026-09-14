## Purpose

Defines the observable lifecycle of a local coding-agent run, from validated CLI input through iterative tool use to a bounded final result.

## ADDED Requirements

### Requirement: Start a coding task from the CLI
The system SHALL accept a Git repository path, a non-empty task description, model connection settings, and optional step, command-timeout, and token or cost limits. The system MUST reject a missing repository, a non-Git directory, an empty task, or a repository with pre-existing tracked changes before any model call or file edit.

#### Scenario: Valid task starts
- **WHEN** the user supplies a clean local Git repository and a non-empty task
- **THEN** the system starts one run rooted at that repository and records its effective configuration

#### Scenario: Dirty repository is rejected
- **WHEN** the repository has tracked staged or unstaged changes
- **THEN** the system exits before invoking the model and reports that a clean working tree is required

### Requirement: Execute a bounded ReAct loop
The system SHALL perform each model step as exactly one structured tool action or one finish action, execute valid tool actions, convert every result into an observation, and use that observation in a later model step. The system MUST count model steps consistently, including malformed responses that require model correction.

#### Scenario: Tool result feeds the next step
- **WHEN** the model requests a valid tool action
- **THEN** the tool executes once and its structured observation is available to the next model request

#### Scenario: Malformed action is recoverable
- **WHEN** the model response is not a valid tool action or finish action
- **THEN** the system records a format-error observation and allows a later model step while limits remain

### Requirement: Tool failures do not crash the run
The system SHALL represent policy rejection, invalid arguments, missing files, edit conflicts, non-zero command exits, and command timeouts as structured observations. The runner MUST continue while limits remain unless the failure prevents the repository from being used safely.

#### Scenario: Failed command is observed
- **WHEN** an allowed command exits with a non-zero status
- **THEN** the model receives its exit code and captured output as an observation and can attempt a repair

### Requirement: Runs terminate explicitly
The system SHALL terminate with one of `completed`, `step_limit`, `budget_limit`, `cancelled`, or `failed`. Every terminal status MUST enter one common finalization path exactly once. A model finish action MUST NOT itself claim correctness; the result SHALL report the repository diff and the latest available verification evidence.

#### Scenario: Model finishes
- **WHEN** the model emits a valid finish action within all limits
- **THEN** the run ends as `completed` and produces a patch and summary

#### Scenario: Step limit is reached
- **WHEN** the next model request would exceed the configured step limit
- **THEN** the run ends as `step_limit` without making another model request

#### Scenario: Any terminal cause is finalized uniformly
- **WHEN** a run completes, reaches a step or budget limit, is cancelled, or fails
- **THEN** the same finalization boundary receives the selected status and reason exactly once

### Requirement: Context is bounded and task-focused
Each model request SHALL include system instructions, the current task, an explicit remaining-budget summary, recent actions and observations, code explicitly returned by repository tools, and the latest important command result. The system MUST enforce a configurable context budget and MUST preserve the task, system instructions, and latest test result when pruning older material. Pinned code MUST use repository-relative path identity and most-recent-read order only: a repeated read replaces older content for that path, and least-recently-read paths are evicted first when the pinned budget is exceeded. The MVP MUST NOT use an additional model, embeddings, semantic ranking, or implicit edited-file priority for this selection.

#### Scenario: Old observations exceed the budget
- **WHEN** accumulated observations exceed the configured context budget
- **THEN** older low-priority observations are deterministically elided while the task, instructions, recent observations, and latest verification result remain present

#### Scenario: Pinned files exceed their budget
- **WHEN** successful file reads exceed the pinned-context character budget
- **THEN** the least-recently-read paths are evicted until the budget fits, and rereading a path replaces its content and moves it to the newest position
