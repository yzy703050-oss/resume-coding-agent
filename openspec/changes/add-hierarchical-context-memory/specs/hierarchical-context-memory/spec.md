## Purpose

Defines bounded model-context construction from run-local working memory, episodic history, compressed history, repository structure, and retrieved project memory while preserving the existing ReAct control flow.

## ADDED Requirements

### Requirement: Memory levels have distinct ownership and lifecycle
The system SHALL represent working memory, episodic memory, compressed history, and persistent project memory as separate components. `RunState` MUST own lifecycle and usage state rather than mutable context payload collections. Working, episodic, and compressed memory MUST be scoped to one run; project memory MUST be scoped to a stable project identity across runs.

#### Scenario: A new run starts
- **WHEN** a second run starts for the same project
- **THEN** it receives new empty run-local memories and may retrieve bounded records from the existing project-memory store

### Requirement: Context preparation uses a dedicated manager
The runner SHALL request each model context from `ContextManager`. The manager SHALL coordinate memory views, repository refresh, retrieval, condensation, selection, and budget diagnostics without requiring the runner to implement those policies.

#### Scenario: A tool result is recorded
- **WHEN** one tool action completes
- **THEN** the runner records the correlated outcome through the manager and continues without directly ranking, condensing, or persisting memory

### Requirement: The existing ReAct and finalization boundaries are preserved
Each model step SHALL remain exactly one structured tool action or one finish action. `ToolRegistry`, `ModelClient`, `ExecutionBackend`, and `Finalizer` SHALL retain their existing roles, and `Finalizer` MUST remain the sole terminal-event and final-artifact owner. Expected model, tool, context, or memory failures MUST use bounded recovery behavior and MUST NOT create a second tool execution or terminal path.

#### Scenario: Advanced context is enabled
- **WHEN** the full context-memory preset prepares and records a model step
- **THEN** the runner still performs at most one tool execution for that step and every terminal status still reaches the existing finalizer exactly once

### Requirement: Audit events and episodic history share one canonical emission
Ordinary runtime facts SHALL be emitted once as canonical in-memory events through a recorder. History projection and history sanitization SHALL consume the operationally bounded canonical payload before an independent audit sanitizer applies stricter audit truncation. `EventWriter` SHALL accept only the audit projection and MUST NOT feed episodic memory. Every projection MUST identify its canonical source sequence and MUST NOT be independently emitted as a competing event fact. Tool-related events MUST carry stable correlation metadata.

#### Scenario: A tool action produces multiple domain events
- **WHEN** one command action emits call, command, test, and result events
- **THEN** the audit records and projected history identify one atomic correlation group, history may retain more bounded operational detail than the audit copy, and both remain secret-free without independently re-emitting equivalent events

### Requirement: History processors are composable and non-destructive
Each history processor SHALL transform a read-only `HistoryView` into a new view. The configured pipeline MUST have deterministic order and MUST NOT mutate or delete raw episodic history. Correlated action/result groups MUST remain atomic.

#### Scenario: Large old command output is processed
- **WHEN** an old command result exceeds the processor limit
- **THEN** the context-visible copy contains a bounded representation with truncation metadata while raw episodic history remains inspectable

### Requirement: Condensation preserves recent raw history and structured progress
When processed historical context crosses the configured threshold, the system SHALL condense only a stable old prefix and SHALL retain a protected recent tail in raw form. An LLM-produced summary MUST use the configured structured fields and MUST NOT be treated as verification evidence.

#### Scenario: Old history exceeds its allocation
- **WHEN** a safe old prefix and threshold conditions exist
- **THEN** the visible history contains a structured summary of the covered prefix followed by unmodified recent correlated events

### Requirement: Condenser failure degrades gracefully
The LLM condenser SHALL have a per-run call limit, cooldown, minimum-new-event threshold, and deterministic fallback. Expected condenser failure MUST NOT fail the agent run.

#### Scenario: The summarization model fails
- **WHEN** an eligible condensation call returns a transport or format failure
- **THEN** the system records the failure and uses the sliding-window fallback while allowing the agent step to continue

### Requirement: Auxiliary model calls have hard accounting boundaries
LLM condensation and optional LLM project-memory candidate extraction SHALL use one auxiliary gateway. Reported auxiliary tokens and cost MUST be tracked separately and included in total run usage and global run limits. Auxiliary calls MUST also obey configured per-run call, token, cost, and per-component call limits. A call that cannot fit either remaining budget MUST NOT start. Unknown cost MUST NOT be treated as zero; when any cost limit is configured, every enabled main and auxiliary model client MUST provide reported cost or deterministic pricing metadata before the run starts.

#### Scenario: Condensation is denied by budget
- **WHEN** an LLM condensation request would exceed the global or auxiliary hard limit
- **THEN** no auxiliary model request is made, the deterministic sliding-window fallback is used, and usage is not invented

#### Scenario: Auxiliary usage reaches the global run limit
- **WHEN** a completed auxiliary call causes combined main and auxiliary usage to reach the run limit
- **THEN** no later main or auxiliary model call starts

### Requirement: Condensation is observable
Every condensation attempt SHALL record its trigger, covered range, source event count, outcome, fallback, and available token/cost usage. Condensed summaries MUST identify their source sequence range and revision.

#### Scenario: Condensation succeeds
- **WHEN** old events are replaced in the context view by a summary
- **THEN** run diagnostics identify exactly which event range was covered and the summary used for later selection

### Requirement: Python repository structure is indexed safely
The system SHALL build a deterministic Python Repo Map using static AST parsing of confined repository files. It SHALL extract imports, classes, functions, methods, parents, line numbers, and signatures without executing repository code. Individual read or parse failures MUST be diagnostic and non-fatal.

#### Scenario: A fixture repository is indexed
- **WHEN** a Python fixture contains imports, a class method, and a module function
- **THEN** the Repo Map reports the expected paths, qualified symbols, kinds, parents, imports, and signatures in stable order

### Requirement: Repository memory refreshes changed Python files
The Repo Map SHALL invalidate a successfully edited path and refresh it before the next context selection. Refresh MUST remove stale symbols when a file becomes absent or unparseable and MUST NOT require a full repository rescan for one ordinary edit.

#### Scenario: An indexed method is edited
- **WHEN** `edit_file` changes that method signature
- **THEN** the next model context can select the new signature and cannot select the stale one

### Requirement: Context candidates are explicit and inspectable
Every candidate supplied to selection SHALL include type, content, priority, estimated size, source, relevance, importance, recency, stable identity, and metadata. Selection MUST be deterministic for identical inputs.

#### Scenario: Candidates have equal scores
- **WHEN** two optional candidates have equal priority and scores
- **THEN** stable source and item identifiers determine a repeatable order

### Requirement: Context uses independent section budgets
The system SHALL allocate a total input budget and separate mandatory, working-memory, pinned-code, Repo Map, recent-history, compressed-history, and persistent-memory sections. Optional sections MUST NOT consume the mandatory reserve. Unused optional capacity MAY spill only according to configured deterministic rules.

#### Scenario: One command output is very large
- **WHEN** it is larger than the recent-history allocation
- **THEN** it is transformed or omitted without displacing the task, active constraints, latest test summary, or other mandatory working state

### Requirement: Prepared context fits the configured estimator budget
The budget SHALL include message content, fixed framing, tool schemas, and response reserve. The selector SHALL remove lowest-ranked optional atomic groups until the prepared context fits. An immutable task and minimum overhead that cannot fit MUST be rejected before the first model call rather than silently truncating the task.

#### Scenario: Mandatory input is impossible
- **WHEN** the immutable task and required overhead exceed the configured input allowance
- **THEN** run construction returns a clear configuration error before calling the model or editing files

### Requirement: ContextBuilder only formats selected items
`ContextBuilder` SHALL convert an ordered `PreparedContext` into model messages. It MUST NOT read memory stores, run processors, invoke condensers, score candidates, refresh repository indexes, or allocate budgets.

#### Scenario: Prepared items are formatted
- **WHEN** the builder receives the same ordered items twice
- **THEN** it returns identical messages without accessing mutable memory components

### Requirement: Context components are independently configurable
History processors, condenser, Repo Map, candidate extraction, and project-memory retrieval SHALL each be replaceable by a no-op implementation through validated configuration. The runner MUST NOT contain component-specific branches.

#### Scenario: Baseline preset is selected
- **WHEN** all advanced memory components are disabled
- **THEN** the agent retains V1-equivalent recent-observation and pinned-file behavior through a compatibility composition

### Requirement: Baseline remains the default preset
The baseline preset SHALL remain supported and SHALL remain the default throughout this change. Full mode MUST be opt-in and MUST NOT become the default without a later explicit design decision supported by comparative evaluation.

#### Scenario: No memory preset is supplied
- **WHEN** a user starts a run without selecting a context-memory preset
- **THEN** the system composes the baseline preset rather than full mode

### Requirement: Memory-enabled artifacts are additive and self-describing
Existing event, patch, summary, and terminal-ownership contracts SHALL remain readable and verifiable. Memory-enabled runs SHALL add effective preset, aggregate context sizes, condensation metrics, and component diagnostics when available without treating model summaries as success evidence.

#### Scenario: A full-mode run terminates
- **WHEN** finalization writes its existing patch and summary artifacts
- **THEN** the summary identifies enabled memory components and available context metrics while independent test evidence remains authoritative
