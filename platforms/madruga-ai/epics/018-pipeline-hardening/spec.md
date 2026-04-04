# Feature Specification: Pipeline Hardening & Safety

**Feature Branch**: `epic/madruga-ai/018-pipeline-hardening`  
**Created**: 2026-04-04  
**Status**: Draft  
**Input**: Epic 018 pitch — Pipeline Hardening & Safety for madruga-ai platform

## User Scenarios & Testing

### User Story 1 - Safe Resource Cleanup During Pipeline Execution (Priority: P1)

As a pipeline operator, I need database connections to be automatically cleaned up regardless of how execution ends (success, error, or interruption), so that I never encounter connection leaks or locked databases.

**Why this priority**: Connection leaks are the most frequent reliability issue — they cause silent failures that compound over time and can lock the SQLite database for subsequent runs.

**Independent Test**: Run a pipeline that errors mid-execution and verify the database connection is properly released (no WAL lock remains).

**Acceptance Scenarios**:

1. **Given** a pipeline execution in progress, **When** an exception occurs mid-execution, **Then** the database connection is released automatically without explicit cleanup code.
2. **Given** a pipeline execution that reaches a pending gate, **When** execution pauses for human approval, **Then** the database connection is released automatically.
3. **Given** a pipeline execution completes successfully, **When** the run finishes, **Then** no connection handles remain open.

---

### User Story 2 - Fail-Closed Gate Validation (Priority: P1)

As a pipeline operator, I need invalid or misspelled gate types to be treated as requiring human approval (fail-closed), so that a typo like `gate: "humam"` never causes a node to execute without the required approval.

**Why this priority**: This is a safety-critical issue — a typo in gate configuration currently bypasses human approval entirely, allowing potentially destructive operations to run unreviewed.

**Independent Test**: Configure a node with `gate: "humam"` (typo) and verify it requires human approval instead of executing automatically.

**Acceptance Scenarios**:

1. **Given** a DAG definition with `gate: "humam"` on a node, **When** the pipeline parses the DAG, **Then** a warning is logged and the gate is treated as `human`.
2. **Given** a DAG definition with `gate: "auto"`, **When** the pipeline parses the DAG, **Then** the node executes automatically (valid gate, no warning).
3. **Given** a DAG definition with an empty gate field, **When** the pipeline parses the DAG, **Then** the default gate type is applied per existing behavior.

---

### User Story 3 - Circuit Breaker for Repeated Skill Failures (Priority: P1)

As a pipeline operator, I need the system to stop retrying a skill after 3 consecutive failures, so that cascading failures are contained and resources are not wasted on a persistently broken skill.

**Why this priority**: Without a circuit breaker, a broken skill can consume unbounded retries, wasting time and API calls while blocking pipeline progress.

**Independent Test**: Trigger a skill that always fails and verify that after 3 consecutive failures, retries stop and a clear error message is reported.

**Acceptance Scenarios**:

1. **Given** a skill that fails on dispatch, **When** it fails 3 times consecutively, **Then** retries are disabled and the failure is reported with a clear message.
2. **Given** a skill that fails twice then succeeds, **When** it succeeds on the 3rd attempt, **Then** the consecutive failure counter resets and execution continues normally.
3. **Given** a skill that hits the circuit breaker, **When** the pipeline reports results, **Then** the output indicates the skill was disabled due to consecutive failures.

---

### User Story 4 - Path and Input Security (Priority: P1)

As a pipeline operator, I need platform names and repository URLs to be validated against injection and path traversal attacks, so that malicious or accidental input cannot compromise the system.

**Why this priority**: The pipeline runs shell commands (e.g., `git clone`) with user-provided input. Unsanitized input is a direct injection vector.

**Independent Test**: Attempt to create a platform with name `"../../../etc"` and verify it is rejected with a clear error.

**Acceptance Scenarios**:

1. **Given** a platform name containing `../`, **When** the user attempts to create or use it, **Then** the operation is rejected with a clear error message.
2. **Given** a platform name with valid characters (lowercase, digits, hyphens), **When** the user creates or uses it, **Then** the operation proceeds normally.
3. **Given** a repository binding with org/name containing shell metacharacters, **When** the pipeline loads the repo binding, **Then** the operation is rejected with a clear error message.
4. **Given** a platform name starting with a hyphen, **When** the user attempts to use it, **Then** the operation is rejected (prevents flag injection).

---

### User Story 5 - Structured Input Validation (Priority: P2)

As a pipeline operator, I need DAG node definitions and platform configurations to be validated at parse time with clear error messages, so that malformed input is caught early instead of causing cryptic failures downstream.

**Why this priority**: Currently, a missing field in `platform.yaml` causes a `KeyError` several nodes downstream — far from the actual source of the problem, making debugging difficult.

**Independent Test**: Provide a DAG node definition missing a required field and verify a clear validation error is raised at parse time.

**Acceptance Scenarios**:

1. **Given** a DAG node definition missing the `id` field, **When** the pipeline parses the DAG, **Then** a validation error is raised immediately with a message identifying the missing field.
2. **Given** a DAG node definition missing the `skill` field, **When** the pipeline parses the DAG, **Then** a validation error is raised immediately with a message identifying the missing field.
3. **Given** a platform configuration with all required fields, **When** the pipeline validates it, **Then** validation passes and execution continues.

---

### User Story 6 - Typed Error Hierarchy (Priority: P2)

As a pipeline operator, I need errors to be categorized by type (pipeline, validation, dispatch, gate), so that I can quickly identify the nature of a failure and take appropriate action.

**Why this priority**: The current mix of `SystemExit`, `log.error+return`, and `print("[error]")` makes it impossible to programmatically distinguish error types or apply targeted recovery.

**Independent Test**: Trigger a validation error and verify the raised exception is of the correct typed error class (not a generic `SystemExit`).

**Acceptance Scenarios**:

1. **Given** an invalid YAML input, **When** the pipeline attempts to parse it, **Then** a validation-specific error is raised (not `SystemExit`).
2. **Given** a skill dispatch failure, **When** the dispatch subprocess fails, **Then** a dispatch-specific error is raised.
3. **Given** an invalid gate type at runtime, **When** the gate is evaluated, **Then** a gate-specific error is raised (after being treated as `human` per fail-closed).
4. **Given** a pipeline structural error (cycle, missing node), **When** the DAG is validated, **Then** a pipeline-specific error is raised.

---

### User Story 7 - Graceful Shutdown on Interruption (Priority: P2)

As a pipeline operator, I need Ctrl+C during pipeline execution to cleanly terminate any running subprocess, save a checkpoint, and print a resume command, so that I can safely interrupt and resume without orphaned processes or lost progress.

**Why this priority**: Currently, Ctrl+C leaves orphaned subprocesses running and doesn't save a checkpoint, requiring manual cleanup and full pipeline restart.

**Independent Test**: Start a pipeline execution, press Ctrl+C during skill dispatch, and verify the subprocess is terminated and a resume hint is printed.

**Acceptance Scenarios**:

1. **Given** a pipeline executing a skill via subprocess, **When** the operator presses Ctrl+C, **Then** the active subprocess is terminated.
2. **Given** a pipeline interrupted by Ctrl+C, **When** the interruption is handled, **Then** a message is printed with the `--resume` command to continue.
3. **Given** a pipeline interrupted by Ctrl+C, **When** the interruption is handled, **Then** the process exits with code 130 (standard SIGINT exit code).

---

### Edge Cases

- What happens when the database file is locked by another process during connection cleanup?
- How does the circuit breaker behave when multiple different skills fail (not consecutive same-skill)?
- What happens when Ctrl+C is pressed during database writes (not during subprocess dispatch)?
- How does path validation handle Unicode characters in platform names?
- What happens when a DAG node has a valid gate type but in different casing (e.g., "Human" vs "human")?

## Requirements

### Functional Requirements

- **FR-001**: System MUST use automatic resource management (context managers) for all database connections in the pipeline executor — no manual `close()` calls.
- **FR-002**: System MUST validate gate types against a canonical set (`auto`, `human`, `1-way-door`, `auto-escalate`) and treat unrecognized values as `human` (fail-closed).
- **FR-003**: System MUST log a warning when an unrecognized gate type is encountered, identifying the node and the invalid value.
- **FR-004**: System MUST stop retrying a skill after 3 consecutive failures of the same skill, reporting a clear error.
- **FR-005**: System MUST reset the consecutive failure counter when a skill succeeds.
- **FR-006**: System MUST validate platform names against a strict pattern (lowercase alphanumeric and hyphens, starting with alphanumeric).
- **FR-007**: System MUST validate repository org/name values against a safe character pattern, rejecting shell metacharacters.
- **FR-008**: System MUST reject any user-provided path containing `..` segments (path traversal prevention).
- **FR-009**: System MUST validate DAG node definitions at parse time, raising clear errors for missing required fields (`id`, `skill`).
- **FR-010**: System MUST validate platform configuration at load time, raising clear errors for missing or invalid fields.
- **FR-011**: System MUST use a typed error hierarchy instead of generic `SystemExit` for all error conditions in the 4 main scripts (dag_executor, post_save, ensure_repo, platform_cli).
- **FR-012**: System MUST handle SIGINT (Ctrl+C) by terminating active subprocesses, printing a resume hint, and exiting with code 130.
- **FR-013**: System MUST NOT break any existing tests (`make test` passes).
- **FR-014**: System MUST pass linting (`make ruff` passes).

### Key Entities

- **DAG Node**: A unit of work in the pipeline with an id, skill reference, dependencies, gate type, outputs, and optional flag. Validated at parse time.
- **Platform Configuration**: Metadata about a platform loaded from `platform.yaml` — name, repo binding, lifecycle stage. Validated at load time.
- **Gate**: An approval mechanism on a DAG node. Types: `auto`, `human`, `1-way-door`, `auto-escalate`. Fail-closed for unknown types.
- **Error Type**: Categorized exception class representing the nature of a failure — pipeline, validation, dispatch, or gate.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero database connection leaks during pipeline execution — all connections are released regardless of execution outcome (success, error, interruption).
- **SC-002**: 100% of unrecognized gate types result in fail-closed behavior (treated as human approval required) with a logged warning.
- **SC-003**: Skill retry storms are contained — no skill is retried more than 3 consecutive times.
- **SC-004**: 100% of path traversal attempts (e.g., `../`) and shell metacharacter injection attempts are rejected at input validation.
- **SC-005**: Malformed DAG node definitions are caught at parse time — zero `KeyError` or `AttributeError` failures downstream from missing fields.
- **SC-006**: All pipeline errors are raised as typed exceptions — zero `SystemExit` calls remain in the 4 main scripts for error conditions.
- **SC-007**: Ctrl+C during pipeline execution results in clean subprocess termination and a usable resume command within 2 seconds.
- **SC-008**: All existing tests continue to pass, and new tests cover the added validation and safety behaviors.

## Assumptions

- The existing `_ClosingConnection` context manager in `db.py` works correctly and does not need modification.
- The `CircuitBreaker` pattern already present in `dag_executor.py` is a valid reference for the dispatch circuit breaker.
- Gate type validation is case-sensitive — `"Human"` is treated as invalid (fail-closed to `human`). This follows the existing convention where all gate types are lowercase.
- The error hierarchy covers the 4 main scripts initially and can be expanded to other scripts in future epics.
- Unicode characters in platform names are out of scope — only ASCII lowercase, digits, and hyphens are valid.
- SIGINT is the only signal handled for graceful shutdown — SIGTERM and other signals are out of scope for this epic.
- No changes to the SQLite schema, portal, `db.py` internals, or skill files (`.claude/commands/`) are in scope.
