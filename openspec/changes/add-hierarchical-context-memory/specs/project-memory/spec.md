## Purpose

Defines safe, bounded, inspectable persistence and retrieval of coding-project knowledge across independent agent runs.

## ADDED Requirements

### Requirement: Project memory is external and project-scoped
The system SHALL store project memory in a SQLite database outside the target repository. Every record MUST include a normalized project identifier, type, source run, timestamp, importance, confidence, provenance, and stable identifier.

#### Scenario: An artifact root serves two repositories
- **WHEN** both repositories use the same external artifact root
- **THEN** a query for one project cannot return records owned only by the other project

### Requirement: Project identity calculation is stable and versioned
The system SHALL calculate `project_id` as a versioned SHA-256 digest. It SHALL prefer a sanitized canonical `remote.origin.url`; when no origin exists it SHALL use the normalized, absolute, resolved Git common-directory path. Remote credentials and raw local identity paths MUST NOT be stored in project records or exposed to model context.

#### Scenario: The same remote is used across runs
- **WHEN** separate runs or clones resolve to equivalent sanitized canonical origin URLs
- **THEN** they calculate the same `project_id`

#### Scenario: Projects are different
- **WHEN** repositories resolve to different canonical remotes or different no-remote Git common directories
- **THEN** they calculate different `project_id` values and their records remain isolated

#### Scenario: No Git remote exists
- **WHEN** repeated runs use a repository without `remote.origin.url`
- **THEN** its normalized resolved Git common directory produces a stable identifier across those runs and linked worktrees

### Requirement: Candidate extraction cannot write project memory
The system SHALL expose a `ProjectMemoryCandidateExtractor` interface with no store dependency. It SHALL support no-op and deterministic implementations and MAY support an opt-in structured LLM implementation. LLM extraction MUST use the auxiliary model gateway and MUST return typed candidates with source event sequences rather than writing the store.

#### Scenario: Structured LLM extraction succeeds
- **WHEN** the optional extractor returns schema-valid candidates
- **THEN** they remain unvalidated proposals and no database write occurs until the promotion pipeline accepts them

#### Scenario: Structured LLM extraction is unavailable
- **WHEN** its output is malformed, its call fails, or its auxiliary budget is exhausted
- **THEN** no LLM-derived candidate is persisted, deterministic extraction may continue, and the agent run does not fail

### Requirement: Every candidate passes one promotion pipeline
Every deterministic or LLM-derived candidate MUST pass candidate sanitization, `ProjectMemoryPolicy`, provenance validation, normalization, and deduplication before persistence. Provenance validation SHALL verify the source run, cited canonical event sequences, and related repository paths. `ProjectMemoryStore` MUST accept only a validated record type, not raw candidates or strings.

#### Scenario: An LLM proposes unsupported memory
- **WHEN** a candidate cites a nonexistent event, contains a secret, violates its type policy, or duplicates an existing normalized record
- **THEN** the corresponding validation or deduplication stage rejects or merges it before the store can create a new record

### Requirement: Only typed curated knowledge is persisted
The promotion pipeline SHALL accept architecture facts, conventions, important modules, testing conventions, known failures, past attempts, project decisions, useful commands, and run summaries. It MUST reject credentials, personal information, unbounded file/command content, transient errors, untyped prose, and records without valid provenance.

#### Scenario: Raw command output is proposed
- **WHEN** a persistence candidate contains unbounded stdout or a configured secret
- **THEN** the policy rejects or sanitizes it before any database write and the secret does not appear in the database

### Requirement: Persistent records are deduplicated and bounded
Records SHALL be deduplicated by project, type, and normalized content. Repeated confirmation SHALL update provenance and recency rather than create an equivalent row. The store MUST enforce configurable global and per-type active-record limits.

#### Scenario: The same convention is confirmed twice
- **WHEN** two runs submit normalized-equivalent convention records
- **THEN** one active record remains with updated confirmation metadata and both source runs represented in provenance

### Requirement: Retrieval uses transparent hybrid scoring
Retrieval SHALL combine keyword relevance, related-path overlap, type/importance priors, bounded recency, and confirmation evidence. It MUST return no more than the requested limit with component scores or metadata sufficient to inspect why each record ranked.

#### Scenario: A new run mentions a known module
- **WHEN** the project store contains an architecture record related to that module
- **THEN** the record ranks ahead of unrelated stale records, subject to the persistent-memory context budget

### Requirement: Retrieval has a no-extension fallback
The SQLite implementation SHOULD use FTS5 when available and MUST retain deterministic keyword retrieval when FTS5 is unavailable. It MUST NOT require a vector database or network service.

#### Scenario: FTS5 is unavailable
- **WHEN** database initialization detects no FTS5 support
- **THEN** project-memory insert, deduplication, bounded query, and deterministic keyword ranking still work

### Requirement: Persistent-memory failure does not fail the run
Database open, migration, query, or write failures SHALL be recorded as diagnostics and SHALL disable only persistent memory for the current run. They MUST NOT prevent context construction from other sources or final artifact creation.

#### Scenario: The database is locked
- **WHEN** the store cannot complete a query within its configured timeout
- **THEN** the current context proceeds without project-memory items and the run remains able to finish

### Requirement: SQLite schema changes are versioned
The database SHALL maintain an explicit schema version and forward migration path. Migration tests MUST load every committed historical fixture; existing records MUST NOT be silently discarded on upgrade.

#### Scenario: A version-one store is opened by a later implementation
- **WHEN** a supported forward migration exists
- **THEN** the store upgrades transactionally and preserves the original records and provenance
