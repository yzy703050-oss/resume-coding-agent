## Purpose

Defines deterministic verification and comparative measurement for the hierarchical context and memory engine.

## ADDED Requirements

### Requirement: Memory components have focused network-free tests
The test suite SHALL independently cover working memory, canonical event projections, history processors, condensers, context and auxiliary budgets, selection, Repo Map extraction/refresh, project identity, candidate extraction/promotion, persistent storage, and retrieval. Tests MUST use scripted model responses and temporary local repositories/databases rather than a live API.

#### Scenario: LLM condensation is tested
- **WHEN** a scripted condenser response returns a structured summary
- **THEN** the test deterministically verifies its covered range, preserved recent tail, usage accounting, and selected context

### Requirement: Required memory behaviors are tested end to end
Behavior tests SHALL cover old-history condensation, condenser fallback, bounded pinned files, cross-run project-memory retrieval, Repo Map extraction, atomic action/result retention, and mandatory context preservation.

#### Scenario: Large history and files coexist
- **WHEN** a scripted run produces many observations and reads multiple large files
- **THEN** prepared context fits its budget, recent history and important working files remain, and older history is summarized or explicitly omitted

### Requirement: Evaluation supports named ablation presets
The evaluator SHALL run identical tasks with baseline, processor, condenser, Repo Map, project-memory, and full presets. Each report MUST identify the effective component configuration.

#### Scenario: Two variants are compared
- **WHEN** baseline and full presets run the same task set
- **THEN** their results are separately attributable and use the same success oracle and fixture inputs

### Requirement: Evaluation records context and memory metrics
In addition to task success, independent test success, steps, tool calls, model usage, cost, and elapsed time, evaluation SHALL record total/per-section context estimates, selected and omitted item counts, separate main/auxiliary and combined usage, auxiliary budget denials, condensation calls and usage, candidate proposals/rejections, Repo Map timing/selections, and project-memory query timing/selections.

#### Scenario: No condenser call is needed
- **WHEN** history remains below the trigger threshold
- **THEN** the report records zero condenser calls rather than omitting or inventing usage

### Requirement: Project identity and candidate safety are behavior-tested
The suite SHALL verify same-project cross-run identity, different-project isolation, repositories without an origin remote, canonical remote normalization, deterministic extraction, optional structured LLM extraction, and rejection before persistence for invalid candidates.

#### Scenario: Two no-remote projects share an artifact root
- **WHEN** each project completes multiple runs
- **THEN** runs within one project share an ID while the two projects cannot retrieve each other's records

### Requirement: Audit truncation does not define model history fidelity
The suite SHALL prove that a canonical event can produce a strictly truncated audit payload and a richer bounded history projection while both outputs remain sanitized and share sequence/correlation provenance.

#### Scenario: A large command result is recorded
- **WHEN** the result exceeds the audit string limit but remains within the tool operational limit
- **THEN** JSONL contains the audit-truncated form while episodic history retains the sanitized operational form for later processing

### Requirement: Existing baseline contracts remain verifiable
The existing scripted CLI, ReAct behavior, terminal events, patch, summary, and three independent fixture oracles MUST remain green under the compatibility baseline during migration.

#### Scenario: Advanced memory is disabled
- **WHEN** the current three-task scripted baseline runs with the baseline preset
- **THEN** it preserves the existing successful outcomes and artifact contracts
