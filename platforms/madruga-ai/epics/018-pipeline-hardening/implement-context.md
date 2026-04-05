### T001 — DONE
- Verify baseline: run `make test` and `make ruff` pass on current branch before any changes
- Tokens in/out: 5/566

### T002 — DONE
- Create error hierarchy module with `MadrugaError`, `ValidationError`, `PipelineError`, `DispatchError`, `GateError` classes plus `VALID_GATES` frozenset, `PLATFORM_NAME_RE` regex, `REPO_COMPONENT_RE` 
- Files: .specify/scripts/errors.py
- Tokens in/out: 9/1794

### T003 — DONE
- Create tests for error hierarchy and all validation functions — valid inputs, invalid inputs, edge cases (empty string, `..` in path, shell metacharacters, hyphen-leading names) in `.specify/scripts/t
- Files: .specify/scripts/tests/test_errors.py
- Tokens in/out: 8/2115

### T004 — DONE
- [US1] Replace bare `conn = get_conn()` pattern with `with get_conn() as conn:` in `run_pipeline_async()` (line ~924) — indent body into `with` block, remove all manual `conn.close()` calls (9 occurren
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 25/11227

### T005 — DONE
- [US1] Replace bare `conn = get_conn()` pattern with `with get_conn() as conn:` in `run_pipeline()` (line ~1375) — indent body into `with` block, remove all manual `conn.close()` calls (8 occurrences a
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 11/2110

### T006 — DONE
- [P] [US1] Replace bare `conn`/`conn.close()` in `cmd_gate_approve()` (lines 848/854), `cmd_gate_reject()` (lines 861/867), and `cmd_gate_list()` (lines 874/876) with `with get_conn() as conn:` in `.sp
- Files: .specify/scripts/platform_cli.py
- Tokens in/out: 6/1203

### T007 — DONE
- [P] [US1] Replace bare `conn`/`conn.close()` in `detect_from_path()` (lines ~404/409) with `with get_conn() as conn:` in `.specify/scripts/post_save.py`
- Files: .specify/scripts/post_save.py
- Tokens in/out: 10/762

### T008 — DONE
- [P] [US1] Replace bare `conn`/`conn.close()` in `_resolve_repos_base()` (lines ~60/62) with `with get_conn() as conn:` in `.specify/scripts/ensure_repo.py`
- Files: .specify/scripts/ensure_repo.py
- Tokens in/out: 6/525

### T009 — DONE
- [US2] [US5] Convert `Node` from `NamedTuple` (lines 454-462) to `@dataclass(frozen=True, slots=True)` with `__post_init__` validation: require non-empty `id` and `skill` (raise `ValidationError`), coe
- Files: log.warning, .specify/scripts/dag_executor.py
- Tokens in/out: 19/2162

### T010 — DONE
- [US2] [US5] Update `parse_dag()` (line ~497) to use keyword-only `Node(...)` construction — verify all fields are passed, rely on `__post_init__` for validation. Remove any ad-hoc gate validation if p
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 7/966

### T011 — DONE
- [US2] [US5] Add tests for Node dataclass: valid construction, missing `id` raises `ValidationError`, missing `skill` raises `ValidationError`, unknown gate coerced to `"human"`, valid gates unchanged.
- Files: .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 11/1988

### T012 — DONE
- [US3] Change `CB_MAX_FAILURES = 5` to `CB_MAX_FAILURES = 3` (line 46) in `.specify/scripts/dag_executor.py`
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 9/514

### T013 — DONE
- [US3] Update existing `CircuitBreaker` tests in `.specify/scripts/tests/test_dag_executor.py` — verify breaker opens after 3 failures (not 5), verify recovery at 300s still works, verify counter reset
- Files: .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 7/1491

### T014 — DONE
- [P] [US4] Add `validate_platform_name()` call in `platform_cli.py` at the top of `cmd_use()`, `cmd_lint()`, `cmd_status()`, `cmd_gate_list()`, and any other command that accepts a platform name argume
- Files: platform_cli.py, .specify/scripts/platform_cli.py
- Tokens in/out: 38/7507

### T015 — DONE
- [P] [US4] Add `validate_repo_component()` calls for `org` and `repo_name` in `_load_repo_binding()` (after lines 34-36) — import from `errors`. Replace `raise SystemExit(...)` (lines 25, 32, 37) with 
- Files: .specify/scripts/ensure_repo.py
- Tokens in/out: 14/1654

### T016 — DONE
- [P] [US4] Add `validate_platform_name()` call in `main()` of `dag_executor.py` for the `--platform` argument (after argparse, before pipeline execution). In `.specify/scripts/dag_executor.py`
- Files: dag_executor.py, .specify/scripts/dag_executor.py
- Tokens in/out: 15/1683

### T017 — DONE
- [US4] Create path security tests: platform name with `../`, with shell metacharacters (`; rm -rf`), with uppercase, starting with hyphen, valid names, repo component with spaces, repo component with `
- Files: .specify/scripts/tests/test_path_security.py
- Tokens in/out: 7/1452

### T018 — DONE
- [US6] Replace `raise SystemExit(...)` in `topological_sort()` (lines ~525, 542) with `raise PipelineError(...)`. Import `PipelineError` from `errors`. In `.specify/scripts/dag_executor.py`
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 20/2043

### T019 — DONE
- [US6] Add `try/except MadrugaError` wrapper in `main()` of `dag_executor.py` (lines ~1617-1645) — catch `MadrugaError`, print error message, `sys.exit(1)`. Keep existing `sys.exit()` calls for normal 
- Files: dag_executor.py, .specify/scripts/dag_executor.py
- Tokens in/out: 15/2011

### T020 — DONE
- [P] [US6] Replace `sys.exit(1)` in validation paths of `platform_cli.py` — in `cmd_new()` name validation (line 158), `cmd_register()` failures, and other validation-only error paths. Add `try/except 
- Files: platform_cli.py, .specify/scripts/platform_cli.py
- Tokens in/out: 24/4813

### T021 — DONE
- [P] [US6] Add `import errors` to `post_save.py` for forward compatibility — no functional changes needed (already clean per research R6). In `.specify/scripts/post_save.py`
- Files: post_save.py, .specify/scripts/post_save.py
- Tokens in/out: 3/90

### T022 — DONE
- [US6] Add tests verifying `topological_sort` raises `PipelineError` on cycles and unknown deps (update existing tests or add new ones). In `.specify/scripts/tests/test_dag_executor.py`
- Files: .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 12/1806

### T023 — DONE
- [US7] Add module-level `_active_process: subprocess.Popen | None = None` variable and `_handle_sigint(sig, frame)` signal handler that terminates `_active_process`, logs resume hint, and calls `sys.ex
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 19/2002

### T024 — DONE
- [US7] Set `_active_process` before `subprocess.run()` in `dispatch_node()` (line ~675) and clear it after — use a module-level reference so the signal handler can access it. Handle `subprocess.Popen` 
- Files: subprocess.Popen, subprocess.run, .specify/scripts/dag_executor.py
- Tokens in/out: 7/1187

### T025 — DONE
- [US7] Add `try/except KeyboardInterrupt` wrapper in `run_pipeline_async()` main loop — terminate `_active_process` if set, log resume hint, return 130. Context managers (T004) ensure connection cleanu
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 27/5292

### T026 — DONE
- [US7] Add test verifying SIGINT handler sets exit code 130 and calls `terminate()` on active process (mock `subprocess.Popen` and `signal.signal`). In `.specify/scripts/tests/test_dag_executor.py`
- Files: subprocess.Popen, signal.signal, .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 9/1434

### T027 — DONE
- Run full `make test` — all existing 43+ tests plus new tests must pass
- Tokens in/out: 8/541

### T028 — DONE
- Run `make ruff` — zero lint violations
- Tokens in/out: 6/203

### T029 — DONE
- Run `make ruff-fix` if needed, then re-run `make ruff` to confirm clean
- Tokens in/out: 6/320

### T030 — DONE
- Run quickstart.md verification commands to confirm end-to-end
- Tokens in/out: 10/1284

