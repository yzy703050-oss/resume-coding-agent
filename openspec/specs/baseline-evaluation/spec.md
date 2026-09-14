# baseline-evaluation Specification

## Purpose
Defines deterministic tests and tiny repository tasks that verify the first complete coding-agent loop before any SWE-bench or hosted demonstration integration.

## Requirements

### Requirement: Agent behavior tests do not require a live model
The test suite SHALL support scripted model responses so agent control flow, recovery, termination, context selection, tools, and event recording can be verified without network access or API cost.

#### Scenario: Scripted repair trajectory
- **WHEN** scripted responses read a file, edit it, run a failing test, repair the edit, rerun the test, and finish
- **THEN** the behavior test deterministically observes the full sequence and a completed run

### Requirement: Unit tests cover safety and lifecycle boundaries
Unit tests SHALL cover tool success and failure, path confinement, command policy, timeout cleanup, event ordering, state transitions, model-format recovery, and step-limit termination.

#### Scenario: Tool exception is normalized
- **WHEN** a tool raises an expected operational error in a unit test
- **THEN** the runner receives a structured failure observation rather than an uncaught exception

### Requirement: Local end-to-end fixtures exercise the complete loop
The repository SHALL contain at least three tiny Git repository fixtures representing a bug fix, a test addition, and a function-behavior change. Each fixture MUST define an initial revision, a task statement, an independent verification command, and a deterministic success oracle.

#### Scenario: Fixture task is evaluated
- **WHEN** the agent produces a patch for a local fixture
- **THEN** the evaluator runs the fixture's independent verification and records success or failure separately from the agent's self-reported finish action

### Requirement: Baseline evaluation reports operational metrics
The local evaluator SHALL report task success, test result, model steps, tool calls, elapsed time, token usage when supplied by the model endpoint, and estimated cost when pricing metadata is configured. Missing optional model accounting data MUST be reported as unavailable rather than estimated from invented values.

#### Scenario: Endpoint omits cost metadata
- **WHEN** a model response has token counts but no configured pricing
- **THEN** the evaluation reports token usage and marks cost as unavailable
