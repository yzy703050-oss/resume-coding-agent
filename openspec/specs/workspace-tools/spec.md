# workspace-tools Specification

## Purpose
Defines deterministic repository tools and host-execution constraints that let the agent inspect and modify a trusted local project without unrestricted shell access.

## Requirements

### Requirement: All repository paths are confined
Every file-oriented tool SHALL resolve paths against the run repository root, reject absolute paths, reject traversal outside the root, and reject symlink or junction resolution outside the root.

#### Scenario: Traversal is rejected
- **WHEN** a tool receives a path that resolves outside the repository root
- **THEN** the tool returns a policy-error observation and performs no read or write

### Requirement: Repository inspection tools are deterministic
The system SHALL provide `list_files`, `search_code`, and `read_file`. Results MUST use repository-relative paths, deterministic ordering, configurable result limits, and explicit truncation metadata.

#### Scenario: Search output is limited
- **WHEN** `search_code` finds more matches than the configured result limit
- **THEN** it returns the deterministic first result set and reports that additional matches were omitted

### Requirement: File edits use checked replacement
The system SHALL provide `edit_file` using an exact expected-text replacement. The edit MUST fail without modifying the file when the expected text is absent or occurs more than once. File creation SHALL require an explicit create operation and MUST fail if the target already exists.

#### Scenario: Unique replacement succeeds
- **WHEN** the expected text occurs exactly once in a confined UTF-8 text file
- **THEN** the system replaces that occurrence, preserves the rest of the file, and reports the changed path

#### Scenario: Ambiguous replacement fails safely
- **WHEN** the expected text occurs multiple times
- **THEN** the system leaves the file unchanged and returns an edit-conflict observation

### Requirement: Commands use structured arguments and policy checks
The system SHALL provide `run_command` with an executable plus argument array, a repository-relative working directory, and a timeout. It MUST NOT accept shell command strings, pipes, redirections, command separators, or shell expansion. Only configured executable and argument patterns SHALL run.

#### Scenario: Allowed test command runs
- **WHEN** the agent requests an allowed `python -m pytest` command within the repository
- **THEN** the backend runs it without a shell and returns stdout, stderr, exit code, duration, and truncation metadata

#### Scenario: Disallowed command is blocked
- **WHEN** the requested executable or arguments violate command policy
- **THEN** the backend performs no process launch and returns a policy-error observation

### Requirement: Timed-out processes are cleaned up
The local execution backend SHALL enforce a command timeout and attempt to terminate the entire spawned process tree before returning a timeout result.

#### Scenario: Child process exceeds timeout
- **WHEN** a command or its child process remains active beyond the configured timeout
- **THEN** the backend terminates the process tree and returns a timeout observation with captured output

### Requirement: Git diff is read-only evidence
The system SHALL provide `git_diff` that returns the current patch and changed-file summary relative to the starting revision without modifying repository state.

#### Scenario: Edited repository has a diff
- **WHEN** the agent has changed tracked files
- **THEN** `git_diff` returns the corresponding patch and changed-file list
