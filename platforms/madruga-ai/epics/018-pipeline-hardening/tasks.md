# Tasks: Pipeline Hardening & Safety

**Input**: Design documents from `platforms/madruga-ai/epics/018-pipeline-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. User stories US2 (Gate Validation) and US5 (Input Validation) are combined in Phase 4 because gate validation is implemented inside the Node dataclass `__post_init__`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No project scaffolding needed — all target files exist. Verify baseline.

- [X] T001 Verify baseline: run `make test` and `make ruff` pass on current branch before any changes

---

## Phase 2: Foundational (Error Hierarchy + Validation Primitives)

**Purpose**: Create `errors.py` with typed exception hierarchy and validation functions. ALL subsequent phases depend on this module.

**Why foundational**: US2 (gate validation), US4 (path security), US5 (input validation), and US6 (error migration) all import from `errors.py`. Creating it first unblocks all user stories.

- [X] T002 Create error hierarchy module with `MadrugaError`, `ValidationError`, `PipelineError`, `DispatchError`, `GateError` classes plus `VALID_GATES` frozenset, `PLATFORM_NAME_RE` regex, `REPO_COMPONENT_RE` regex, and validation functions (`validate_platform_name`, `validate_path_safe`, `validate_repo_component`) in `.specify/scripts/errors.py` (~50 LOC with docstrings)
- [X] T003 Create tests for error hierarchy and all validation functions — valid inputs, invalid inputs, edge cases (empty string, `..` in path, shell metacharacters, hyphen-leading names) in `.specify/scripts/tests/test_errors.py` (~60 LOC)

**Checkpoint**: `errors.py` importable, all validation functions tested, `make test` + `make ruff` pass.

---

## Phase 3: User Story 1 — Safe Resource Cleanup During Pipeline Execution (Priority: P1) 🎯 MVP

**Goal**: Replace all bare `conn = get_conn()` + `conn.close()` with `with get_conn() as conn:` so connections are released automatically on success, error, or interruption.

**Independent Test**: Run a pipeline that errors mid-execution and verify the database connection is properly released (no WAL lock remains).

### Implementation for User Story 1

- [X] T004 [US1] Replace bare `conn = get_conn()` pattern with `with get_conn() as conn:` in `run_pipeline_async()` (line ~924) — indent body into `with` block, remove all manual `conn.close()` calls (9 occurrences at lines ~958, 999, 1020, 1051, 1082, 1126, 1169, 1198) in `.specify/scripts/dag_executor.py`
- [X] T005 [US1] Replace bare `conn = get_conn()` pattern with `with get_conn() as conn:` in `run_pipeline()` (line ~1375) — indent body into `with` block, remove all manual `conn.close()` calls (8 occurrences at lines ~1395, 1438, 1453, 1477, 1521, 1563, 1591) in `.specify/scripts/dag_executor.py`
- [X] T006 [P] [US1] Replace bare `conn`/`conn.close()` in `cmd_gate_approve()` (lines 848/854), `cmd_gate_reject()` (lines 861/867), and `cmd_gate_list()` (lines 874/876) with `with get_conn() as conn:` in `.specify/scripts/platform_cli.py`
- [X] T007 [P] [US1] Replace bare `conn`/`conn.close()` in `detect_from_path()` (lines ~404/409) with `with get_conn() as conn:` in `.specify/scripts/post_save.py`
- [X] T008 [P] [US1] Replace bare `conn`/`conn.close()` in `_resolve_repos_base()` (lines ~60/62) with `with get_conn() as conn:` in `.specify/scripts/ensure_repo.py`

**Checkpoint**: Zero bare `conn = get_conn()` in any of the 4 scripts. `make test` passes.

---

## Phase 4: User Story 2 + User Story 5 — Fail-Closed Gate Validation + Structured Input Validation (Priority: P1 + P2)

**Goal**: Convert `Node` from `NamedTuple` to `dataclass(frozen=True, slots=True)` with `__post_init__` validation. Gate validation (US2) is implemented inside `__post_init__` — unknown gates are coerced to `"human"` with a warning. Missing required fields (`id`, `skill`) raise `ValidationError` at parse time (US5).

**Why combined**: Gate validation lives in `Node.__post_init__` per research decision R5. Implementing them separately would require writing gate validation twice (once in `parse_dag`, then moving it to `__post_init__`).

**Independent Test**: Configure a node with `gate: "humam"` (typo) and verify it is treated as `human`. Provide a node missing `id` and verify `ValidationError` is raised.

### Implementation for User Story 2 + 5

- [X] T009 [US2] [US5] Convert `Node` from `NamedTuple` (lines 454-462) to `@dataclass(frozen=True, slots=True)` with `__post_init__` validation: require non-empty `id` and `skill` (raise `ValidationError`), coerce unknown `gate` to `"human"` with `log.warning` using `object.__setattr__`. Import `ValidationError` from `errors`. Remove `NamedTuple` import if unused. In `.specify/scripts/dag_executor.py`
- [X] T010 [US2] [US5] Update `parse_dag()` (line ~497) to use keyword-only `Node(...)` construction — verify all fields are passed, rely on `__post_init__` for validation. Remove any ad-hoc gate validation if present. Replace `raise SystemExit` for missing nodes section (lines 483, 487) with `raise ValidationError(...)`. In `.specify/scripts/dag_executor.py`
- [X] T011 [US2] [US5] Add tests for Node dataclass: valid construction, missing `id` raises `ValidationError`, missing `skill` raises `ValidationError`, unknown gate coerced to `"human"`, valid gates unchanged. Add tests for `parse_dag` with invalid gate type. In `.specify/scripts/tests/test_dag_executor.py`

**Checkpoint**: `gate: "humam"` results in WARNING + `human` treatment. Missing `id`/`skill` raises `ValidationError`. `make test` passes.

---

## Phase 5: User Story 3 — Circuit Breaker for Repeated Skill Failures (Priority: P1)

**Goal**: Lower the circuit breaker threshold from 5 to 3 consecutive failures so that a persistently broken skill stops retrying sooner.

**Independent Test**: Trigger a skill that always fails and verify that after 3 consecutive dispatch failures, the circuit breaker opens.

### Implementation for User Story 3

- [X] T012 [US3] Change `CB_MAX_FAILURES = 5` to `CB_MAX_FAILURES = 3` (line 46) in `.specify/scripts/dag_executor.py`
- [X] T013 [US3] Update existing `CircuitBreaker` tests in `.specify/scripts/tests/test_dag_executor.py` — verify breaker opens after 3 failures (not 5), verify recovery at 300s still works, verify counter reset on success

**Checkpoint**: Circuit breaker opens after 3 consecutive failures. `make test` passes.

---

## Phase 6: User Story 4 — Path and Input Security (Priority: P1)

**Goal**: Validate platform names, repo org/name, and paths at all entry points to prevent injection and path traversal.

**Independent Test**: Attempt `platform_name = "../../../etc"` and verify rejection with clear error.

### Implementation for User Story 4

- [X] T014 [P] [US4] Add `validate_platform_name()` call in `platform_cli.py` at the top of `cmd_use()`, `cmd_lint()`, `cmd_status()`, `cmd_gate_list()`, and any other command that accepts a platform name argument — import from `errors`. In `.specify/scripts/platform_cli.py`
- [X] T015 [P] [US4] Add `validate_repo_component()` calls for `org` and `repo_name` in `_load_repo_binding()` (after lines 34-36) — import from `errors`. Replace `raise SystemExit(...)` (lines 25, 32, 37) with `raise ValidationError(...)`. In `.specify/scripts/ensure_repo.py`
- [X] T016 [P] [US4] Add `validate_platform_name()` call in `main()` of `dag_executor.py` for the `--platform` argument (after argparse, before pipeline execution). In `.specify/scripts/dag_executor.py`
- [X] T017 [US4] Create path security tests: platform name with `../`, with shell metacharacters (`; rm -rf`), with uppercase, starting with hyphen, valid names, repo component with spaces, repo component with `..`. In `.specify/scripts/tests/test_path_security.py` (~50 LOC)

**Checkpoint**: `"../../../etc"` rejected at all entry points. `make test` + `make ruff` pass.

---

## Phase 7: User Story 6 — Typed Error Hierarchy (Priority: P2)

**Goal**: Replace `raise SystemExit(...)` with typed errors (`PipelineError`, `ValidationError`) in the 4 main scripts. Entry points (`main()`) catch `MadrugaError` and convert to `sys.exit(1)`.

**Independent Test**: Trigger a validation error and verify the raised exception is `ValidationError` (not `SystemExit`).

### Implementation for User Story 6

- [X] T018 [US6] Replace `raise SystemExit(...)` in `topological_sort()` (lines ~525, 542) with `raise PipelineError(...)`. Import `PipelineError` from `errors`. In `.specify/scripts/dag_executor.py`
- [X] T019 [US6] Add `try/except MadrugaError` wrapper in `main()` of `dag_executor.py` (lines ~1617-1645) — catch `MadrugaError`, print error message, `sys.exit(1)`. Keep existing `sys.exit()` calls for normal exit codes. In `.specify/scripts/dag_executor.py`
- [X] T020 [P] [US6] Replace `sys.exit(1)` in validation paths of `platform_cli.py` — in `cmd_new()` name validation (line 158), `cmd_register()` failures, and other validation-only error paths. Add `try/except MadrugaError` in `main()`. Keep `sys.exit()` for argparse and normal flow. In `.specify/scripts/platform_cli.py`
- [X] T021 [P] [US6] Add `import errors` to `post_save.py` for forward compatibility — no functional changes needed (already clean per research R6). In `.specify/scripts/post_save.py`
- [X] T022 [US6] Add tests verifying `topological_sort` raises `PipelineError` on cycles and unknown deps (update existing tests or add new ones). In `.specify/scripts/tests/test_dag_executor.py`

**Checkpoint**: Zero `raise SystemExit(...)` in `parse_dag` and `topological_sort`. `make test` passes.

---

## Phase 8: User Story 7 — Graceful Shutdown on Interruption (Priority: P2)

**Goal**: Handle SIGINT (Ctrl+C) by terminating active subprocesses, printing a resume hint, and exiting with code 130.

**Independent Test**: Start a pipeline execution, send SIGINT, verify subprocess is terminated and resume hint is printed.

### Implementation for User Story 7

- [X] T023 [US7] Add module-level `_active_process: subprocess.Popen | None = None` variable and `_handle_sigint(sig, frame)` signal handler that terminates `_active_process`, logs resume hint, and calls `sys.exit(130)`. Register with `signal.signal(signal.SIGINT, _handle_sigint)`. Import `signal` module. In `.specify/scripts/dag_executor.py`
- [X] T024 [US7] Set `_active_process` before `subprocess.run()` in `dispatch_node()` (line ~675) and clear it after — use a module-level reference so the signal handler can access it. Handle `subprocess.Popen` vs `subprocess.run` difference (may need to switch to `Popen` for the active dispatch). In `.specify/scripts/dag_executor.py`
- [X] T025 [US7] Add `try/except KeyboardInterrupt` wrapper in `run_pipeline_async()` main loop — terminate `_active_process` if set, log resume hint, return 130. Context managers (T004) ensure connection cleanup. In `.specify/scripts/dag_executor.py`
- [X] T026 [US7] Add test verifying SIGINT handler sets exit code 130 and calls `terminate()` on active process (mock `subprocess.Popen` and `signal.signal`). In `.specify/scripts/tests/test_dag_executor.py`

**Checkpoint**: Ctrl+C during dispatch terminates subprocess, prints `--resume` hint, exits 130. `make test` passes.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all changes.

- [X] T027 Run full `make test` — all existing 43+ tests plus new tests must pass
- [X] T028 Run `make ruff` — zero lint violations
- [X] T029 Run `make ruff-fix` if needed, then re-run `make ruff` to confirm clean
- [X] T030 Run quickstart.md verification commands to confirm end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  └─► Phase 2 (Foundational: errors.py) ─── BLOCKS ALL user stories
        ├─► Phase 3 (US1: Context Managers) — independent
        ├─► Phase 4 (US2+US5: Node Dataclass + Gate Validation) — independent
        ├─► Phase 5 (US3: Circuit Breaker) — independent
        ├─► Phase 6 (US4: Path Security) — independent
        ├─► Phase 7 (US6: Error Migration) — depends on Phase 4 (uses new error types in parse_dag)
        └─► Phase 8 (US7: Graceful Shutdown) — depends on Phase 3 (context managers ensure cleanup)
              └─► Phase 9 (Polish) — depends on all phases
```

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2. No cross-story deps.
- **US2+US5 (P1+P2)**: Depends only on Phase 2. No cross-story deps.
- **US3 (P1)**: Depends only on Phase 2. No cross-story deps.
- **US4 (P1)**: Depends only on Phase 2. No cross-story deps.
- **US6 (P2)**: Depends on Phase 2 + Phase 4 (Node dataclass must exist before replacing SystemExit in parse_dag).
- **US7 (P2)**: Depends on Phase 2 + Phase 3 (context managers must be in place for clean connection cleanup on SIGINT).

### Within Each User Story

- Read existing code before modifying
- Modify source code first, then update/add tests
- Run `make test` + `make ruff` after each phase

### Parallel Opportunities

- **After Phase 2**: Phases 3, 4, 5, 6 can ALL run in parallel (they modify different sections of code or different files)
- **Within Phase 3**: T006, T007, T008 can run in parallel (different files: platform_cli, post_save, ensure_repo)
- **Within Phase 6**: T014, T015, T016 can run in parallel (different files)
- **Within Phase 7**: T020, T021 can run in parallel (different files)

---

## Parallel Example: After Phase 2

```text
# These 4 phases can start simultaneously after errors.py is created:
Phase 3: US1 — Context managers in dag_executor.py, platform_cli.py, post_save.py, ensure_repo.py
Phase 4: US2+US5 — Node dataclass + gate validation in dag_executor.py
Phase 5: US3 — Circuit breaker constant change in dag_executor.py
Phase 6: US4 — Path validation in platform_cli.py, ensure_repo.py, dag_executor.py

# Caution: Phases 3, 4, 5 all touch dag_executor.py — if running in parallel,
# coordinate to avoid merge conflicts in the same file sections.
# Recommended serial order for dag_executor.py changes: Phase 4 → Phase 3 → Phase 5
```

---

## Implementation Strategy

### MVP First (Phase 2 + Phase 4 Only)

1. Complete Phase 1: Verify baseline
2. Complete Phase 2: Create `errors.py` + tests
3. Complete Phase 4: Node dataclass + fail-closed gate validation
4. **STOP and VALIDATE**: `gate: "humam"` treated as `human`, missing fields caught at parse time
5. This alone fixes the most safety-critical bug (gate bypass)

### Recommended Full Order

1. Phase 2: `errors.py` (unblocks everything)
2. Phase 4: Node dataclass + gate validation (safety-critical)
3. Phase 6: Path security (injection prevention)
4. Phase 3: Context managers (reliability)
5. Phase 5: Circuit breaker (single constant — 30s)
6. Phase 7: Error migration (cleanup)
7. Phase 8: Graceful shutdown (SIGINT)
8. Phase 9: Polish

### Incremental Delivery

Each phase is a testable increment. After any phase, `make test` + `make ruff` must pass.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to spec.md user stories for traceability
- US2 and US5 are combined because gate validation lives in Node `__post_init__`
- All LOC estimates from pitch should be multiplied by 1.5-2x per Python conventions
- `errors.py` is ~50 LOC (not 30) once docstrings and validation functions are included
- `post_save.py` is already clean — only forward-compatible import added (T021)
- `sys.exit()` in `main()` functions is kept (correct CLI pattern) — only `raise SystemExit` in library functions is replaced
