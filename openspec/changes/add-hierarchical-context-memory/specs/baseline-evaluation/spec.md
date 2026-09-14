## MODIFIED Requirements

### Requirement: Agent behavior tests do not require a live model
The test suite SHALL support scripted main-model and auxiliary-model responses so agent control flow, recovery, termination, context selection, condensation, candidate extraction, tools, and event recording can be verified without network access or API cost.

#### Scenario: Scripted repair trajectory
- **WHEN** scripted responses read a file, edit it, run a failing test, repair the edit, rerun the test, and finish while scripted auxiliary responses exercise configured memory components
- **THEN** the behavior test deterministically observes the full sequence, attributed usage, and a completed run

### Requirement: Baseline evaluation reports operational metrics
The local evaluator SHALL report task success, independent test result, model steps, tool calls, elapsed time, main/auxiliary/combined model usage and cost when available, effective context-memory preset, estimated total and per-section context size, selected/omitted context counts, auxiliary budget denials, condensation metrics, candidate extraction/rejection metrics, Repo Map metrics, and project-memory retrieval metrics when their components are enabled. Missing optional accounting data MUST be reported as unavailable or zero as semantically appropriate rather than invented.

#### Scenario: Endpoint omits cost metadata
- **WHEN** model responses have token counts but no configured pricing and no cost limit is enabled
- **THEN** the evaluation reports attributed token usage and marks cost as unavailable

## ADDED Requirements

### Requirement: Evaluation compares context-memory variants
The evaluator SHALL support baseline, processor, condenser, Repo Map, project-memory, and full presets over identical task inputs and independent success oracles. Baseline MUST remain the default; full mode MUST remain opt-in unless a later evidence-backed design changes the default.

#### Scenario: An ablation suite runs
- **WHEN** the user requests all memory variants
- **THEN** the output contains one attributable result set per preset and enough metrics to compare success, cost, context size, and tool behavior
