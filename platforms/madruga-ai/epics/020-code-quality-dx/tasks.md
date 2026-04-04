# Tasks: Code Quality & DX — Epic 020

**Branch**: `epic/madruga-ai/020-code-quality-dx`  
**Input**: `platforms/madruga-ai/epics/020-code-quality-dx/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story (US1–US6)
- All paths relative to repo root unless noted

---

## Phase 1: Foundational — db.py Split (Blocks US1 + US2)

**Purpose**: Split the 2,268-line `db.py` monolith into 4 focused modules and replace `db.py` with a re-export facade. All existing `from db import X` callers continue working unchanged. This must complete before the structured logging tasks (US2) because those scripts' imports must be stable before being modified.

**⚠️ CRITICAL**: Phases 2 and 3 cannot begin until T001–T006 are complete and `make test` passes.

**Prerequisite check**: Confirm `.specify/scripts/errors.py` exists and exports `VALID_GATES = frozenset({"auto", "human", "1-way-door", "auto-escalate"})`.

- [X] T001 [US1] Create `.specify/scripts/db_core.py` (~400 LOC) by extracting all 15 symbols listed in data-model.md §1 (`_check_fts5`, `_sanitize_fts5_query`, `_escape_like`, `_fts5_search`, `_now`, `_file_mtime_iso`, `_ClosingConnection`, `get_conn`, `_BatchConnection`, `transaction`, `_split_sql_statements`, `migrate`, `to_relative_path`, `compute_file_hash`, `_FTS5_AVAILABLE`) from `.specify/scripts/db.py`; imports: stdlib only (`sqlite3`, `hashlib`, `json`, `pathlib`, `os`, `logging`, `contextlib`, `datetime`) + `config` + `errors`; this is the leaf module — no imports from other db_ modules

- [X] T002 [US1] Create `.specify/scripts/db_pipeline.py` (~550 LOC) by extracting all 29 symbols listed in data-model.md §1 (from `upsert_platform` through `seed_from_filesystem`, plus `insert_provenance` and `get_provenance`) from `.specify/scripts/db.py`; imports: `from db_core import get_conn, transaction, migrate, _now, _file_mtime_iso, to_relative_path, compute_file_hash` + stdlib + `yaml` + `config`; must NOT import from `db_decisions` or `db_observability`

- [X] T003 [US1] Create `.specify/scripts/db_decisions.py` (~820 LOC) by extracting all 22 symbols listed in data-model.md §1 (from `insert_decision` through `search_memories`) from `.specify/scripts/db.py`; imports: `from db_core import get_conn, transaction, _fts5_search, _check_fts5, _now, to_relative_path` + stdlib + `yaml`; must NOT import from `db_pipeline` or `db_observability`

- [X] T004 [US1] Create `.specify/scripts/db_observability.py` (~280 LOC) by extracting all 8 symbols listed in data-model.md §1 (`create_trace`, `complete_trace`, `get_traces`, `get_trace_detail`, `insert_eval_score`, `get_eval_scores`, `get_stats`, `cleanup_old_data`) from `.specify/scripts/db.py`; imports: `from db_core import get_conn, transaction, _now` + stdlib; must NOT import from other db_ modules

- [X] T005 [US1] Replace `.specify/scripts/db.py` with a 10-line re-export facade: `from db_core import *  # noqa: F401, F403` / `from db_pipeline import *  # noqa: F401, F403` / `from db_decisions import *  # noqa: F401, F403` / `from db_observability import *  # noqa: F401, F403`; add a module docstring explaining that new code should import from the submodule directly; verify with `python3 -c "from db import get_conn, migrate, upsert_platform, insert_decision, create_trace; print('OK')"` from `.specify/scripts/`

- [X] T006 [US1] Update `.specify/scripts/tests/test_db_core.py` to cover the symbols now in `db_core.py`: import from `db_core` directly (not `db`); ensure the following are covered: `_ClosingConnection` context manager closes connection on exit, `migrate()` is idempotent (run twice → same schema), `transaction()` rolls back on exception, `_check_fts5()` returns a boolean and is idempotent, `_fts5_search()` falls back to LIKE when FTS5 unavailable; keep existing passing tests, add any missing coverage for the 5 cases above

- [X] T007 [US1] Rename `.specify/scripts/tests/test_db_crud.py` → `.specify/scripts/tests/test_db_pipeline.py`; update all imports inside the file to import from `db_pipeline` directly (in addition to or instead of `db`); verify tests still pass with `python3 -m pytest .specify/scripts/tests/test_db_pipeline.py -v` from repo root; update any `Makefile` or `pytest.ini`/`conftest.py` references if the old filename is hardcoded

**Checkpoint**: Run `make test` — must pass fully before proceeding to Phase 2.

---

## Phase 2: User Story 2 — Machine-Parseable Script Output (Priority: P1)

**Goal**: All internal script operations emit structured log messages (not bare `print()`). Scripts support `--json` flag for NDJSON output suitable for CI consumption.

**Independent Test**: `python3 .specify/scripts/platform_cli.py status --all --json | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]; print('All lines valid JSON')"` must succeed with no errors.

**Dependency**: T001–T007 (db.py split) must be complete — these scripts import from db.

- [X] T008 [US2] Add `_NDJSONFormatter` class and `_setup_logging(json_mode: bool) -> None` function to `.specify/scripts/platform_cli.py` (place near top, after imports); add `--json` flag to the `ArgumentParser`; call `_setup_logging(args.json)` in `main()` before any operations; replace every `print(f"  [ok] ...")`, `print(f"  [warn] ...")`, `print(f"  [error] ...")`, `print(f"  [skip] ...")` with `log.info(...)`, `log.warning(...)`, `log.error(...)`, `log.info(...)` respectively; keep `print()` only for final user-visible table output and formatted reports; `_NDJSONFormatter.format()` must emit: `{"timestamp": "<ISO8601Z>", "level": "<LEVELNAME>", "message": "<msg>", "logger": "<name>"}`

- [X] T009 [US2] Add `_NDJSONFormatter` class (identical pattern to T008) and `_setup_logging()` to `.specify/scripts/dag_executor.py`; add `--json` to its `ArgumentParser`; replace all `print("[ok]")`, `print("[error]")`, `print("[skip]")`, `print("[warn]")` and similar internal-operation prints with structured log calls; keep `print()` only for final progress summaries printed to the user; call `_setup_logging(args.json)` in entry point before any operations

- [X] T010 [US2] Add `_NDJSONFormatter` class (identical pattern) and `_setup_logging()` to `.specify/scripts/post_save.py`; add `--json` to its `ArgumentParser`; replace all internal `print(...)` calls with appropriate `log.*()` calls; verify existing `--reseed` and `--reseed-all` modes still produce correct output; call `_setup_logging(args.json)` in entry point before any operations

**Checkpoint**: `python3 .specify/scripts/platform_cli.py status --all --json | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]; print('OK')"` passes with no errors. Human mode output unchanged.

---

## Phase 3: User Story 3 — Memory Health Monitoring (Priority: P2)

**Goal**: A single command reports stale memory entries, possible duplicates, and MEMORY.md index health. Dry-run by default. No files modified without `--apply`.

**Independent Test**: `python3 .specify/scripts/memory_consolidate.py --dry-run` completes in <5 seconds and prints a report. No files are created or modified.

**Dependency**: None — fully independent from US1/US2.

- [X] T011 [US2] [P] Create `.specify/scripts/memory_consolidate.py` (~200 LOC) implementing: (1) CLI with `--dry-run` (default) and `--apply` flags; (2) `scan_memory_files(memory_dir: Path) -> list[dict]` — reads all `*.md` in the memory dir, parses frontmatter via `yaml.safe_load`, skips malformed files appending them to `unparseable_files`, extracts `name`, `type`, `description`, and `mtime` from `Path.stat().st_mtime`; (3) `find_stale(entries, threshold_days=90) -> list[dict]` — returns entries where `(datetime.utcnow() - datetime.utcfromtimestamp(mtime)).days > threshold_days`; (4) `find_possible_duplicates(entries, similarity_threshold=0.4) -> list[tuple]` — for each pair of entries with same `type`, compute `jaccard = len(A∩B)/len(A∪B)` on lowercased description tokens, return pairs where jaccard > threshold; (5) `check_index_health(memory_dir: Path) -> dict` — count lines in `MEMORY.md`, return `{"lines": N, "status": "OK"|"WARNING"|"CRITICAL"}` where WARNING is ≥180, CRITICAL is ≥200; (6) `print_report(stale, duplicates, health, unparseable)` — print the report format defined in data-model.md §3; (7) `apply_stale_markers(stale_entries)` — prepend `[STALE - review by YYYY-MM-DD]` header to body of each stale file (never deletes, never merges); (8) `main()` entry point wiring all above; memory dir is `.claude/projects/-home-gabrielhamu-repos-paceautomations-madruga-ai/memory/` resolved from repo root

**Checkpoint**: `python3 .specify/scripts/memory_consolidate.py --dry-run` prints a report and exits 0. Running it a second time produces the same output (idempotent read).

---

## Phase 4: User Story 4 — Skill Contract Compliance Detection (Priority: P2)

**Goal**: `skill-lint.py` detects skills with invalid `gate` values (ERROR) and missing `## Output Directory` section (WARNING) for all skill archetypes.

**Independent Test**: Running `skill-lint.py --json` reports warnings/errors for any skill that is missing `## Output Directory`. Running it on a skill with `gate: invalid-value` in frontmatter reports an ERROR.

**Dependency**: `errors.py` must exist with `VALID_GATES` (epic 018 prerequisite).

- [X] T012 [US4] [P] Extend `lint_single_skill()` in `.specify/scripts/skill-lint.py` with two new checks: (1) **gate-valid** (ERROR): after frontmatter is parsed, `from errors import VALID_GATES`; if `frontmatter.get("gate")` is not None and not in `VALID_GATES`, call `add("ERROR", f"Invalid gate value '{gate}'. Valid: {sorted(VALID_GATES)}")`; if frontmatter parse failed, skip this check; (2) **output-dir** (WARNING): change the existing `## Output Directory` check from pipeline-archetype-only to all archetypes — find the condition that currently gates this check and remove or broaden it so `if "## Output Directory" not in body: add("WARNING", "Missing '## Output Directory' section")` applies to ALL skills regardless of archetype; confirm `handoffs` NIT check already covers all archetypes (verify at line ~248) and widen scope if not; verify with `python3 .specify/scripts/skill-lint.py --json | python3 -m json.tool` — output is valid JSON

**Checkpoint**: `python3 .specify/scripts/skill-lint.py --json` produces valid JSON. Skills without `## Output Directory` show `severity: "WARNING"`.

---

## Phase 5: User Story 5 — Faster Repeated Status Queries (Priority: P3)

**Goal**: `_discover_platforms()` caches filesystem reads for the session lifetime. Cache is invalidated after `new` and `sync` subcommands.

**Independent Test**: Import `_discover_platforms` from `platform_cli`, call it twice, assert `p1 is p2` (same object returned from cache).

**Dependency**: T008 (platform_cli.py modifications) should be complete to avoid merge conflicts, but this change is localized.

- [X] T013 [US5] [P] Apply `@functools.lru_cache(maxsize=None)` to `_discover_platforms()` in `.specify/scripts/platform_cli.py`: add `from functools import lru_cache` to imports; decorate `_discover_platforms` at its definition; after the `new` subcommand handler completes, add `_discover_platforms.cache_clear()`; after the `sync` subcommand handler completes, add `_discover_platforms.cache_clear()`; verify cache hit: `python3 -c "import sys; sys.path.insert(0, '.specify/scripts'); from platform_cli import _discover_platforms; p1=_discover_platforms(); p2=_discover_platforms(); assert p1 is p2; print('cache hit OK')"` from repo root

**Checkpoint**: Cache hit assertion passes. `platform_cli.py status --all` still produces correct output.

---

## Phase 6: User Story 6 — Test Coverage for Untested Scripts (Priority: P3)

**Goal**: `test_vision_build.py` and `test_sync_memory.py` exist with ≥5 test cases each and pass under `make test`.

**Independent Test**: `python3 -m pytest .specify/scripts/tests/test_vision_build.py .specify/scripts/tests/test_sync_memory.py -v` — all tests green.

**Dependency**: T001–T006 must be complete (sync_memory.py uses db_decisions functions; tests import from db submodules).

- [X] T014 [US6] [P] Create `.specify/scripts/tests/test_vision_build.py` (~180 LOC) with ≥6 test cases using `unittest.mock.patch` and `tmp_path` fixture: (1) `test_containers_table_minimal` — call `_containers_table()` with a minimal JSON dict containing one container, assert output is a non-empty string with the container name; (2) `test_domains_table_minimal` — same for `_domains_table()`; (3) `test_update_markdown_round_trip` — write a temp markdown file with an AUTO section, call `update_markdown()`, assert the section is updated correctly; (4) `test_export_json_success` — mock `subprocess.run` to return a `CompletedProcess` with `returncode=0` and valid JSON in stdout, assert `export_json()` returns parsed dict; (5) `test_export_png_missing_cli` — mock `subprocess.run` to raise `FileNotFoundError`, assert `export_png()` raises a clear exception or prints an error message without an unhandled traceback; (6) `test_validate_model_nonzero_returncode` — mock `subprocess.run` to return `returncode=1`, assert `validate_model()` raises or returns a falsy result; all tests use `sys.path.insert(0, str(Path(__file__).parent.parent))` to import from `.specify/scripts/`

- [X] T015 [US6] [P] Create `.specify/scripts/tests/test_sync_memory.py` (~130 LOC) with ≥6 test cases using in-memory SQLite DB and `tmp_path` fixture: (1) `test_import_basic_frontmatter` — write a temp `.md` file with valid YAML frontmatter (`name`, `type: user`, `description`, body), call `import_memory_from_markdown()`, assert a memory row is in DB; (2) `test_all_four_types_round_trip` — for each of `user`, `feedback`, `project`, `reference`: import → DB → export → verify `type` field preserved exactly; (3) `test_export_produces_valid_frontmatter` — after import, call `export_memory_to_markdown()`, parse output YAML, assert required keys present; (4) `test_full_round_trip_no_data_loss` — import a file, export to temp path, re-import the exported file, assert body and all frontmatter fields match original; (5) `test_malformed_frontmatter_skipped` — write a file with broken YAML (`key: [unclosed`), call import, assert function returns None or raises a recoverable error (does NOT crash with unhandled exception); (6) `test_memory_index_update` — after export, verify MEMORY.md index file is updated (or that the update function can be called without error); all tests use an in-memory SQLite DB created via `sqlite3.connect(":memory:")` with `migrate()` called on it

**Checkpoint**: `python3 -m pytest .specify/scripts/tests/test_vision_build.py .specify/scripts/tests/test_sync_memory.py -v` — all green.

---

## Phase 7: Polish & Final Verification

**Purpose**: Ensure full test suite passes, ruff is clean, and all acceptance criteria are met.

- [X] T016 Fix any ruff violations introduced by previous tasks: run `make ruff` from repo root; apply `make ruff-fix` for auto-fixable issues; manually fix any remaining violations (E501 line length, F401 unused imports in db.py facade require `# noqa` comments already placed in T005)

- [X] T017 Run full verification checklist from quickstart.md: (1) `python3 -c "from db import get_conn, migrate, upsert_platform, insert_decision, create_trace; print('facade OK')"` from `.specify/scripts/`; (2) `python3 .specify/scripts/platform_cli.py status --all --json | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]; print('NDJSON OK')"`; (3) `python3 .specify/scripts/memory_consolidate.py --dry-run`; (4) `python3 .specify/scripts/skill-lint.py --json | python3 -m json.tool`; (5) `make test && make ruff` — both must exit 0; capture any failures and fix before closing the epic

---

## Dependencies

```
T001 ──┐
T002 ──┤
T003 ──┼──► T005 (facade) ──► T006 (test_db_core) ──► make test checkpoint
T004 ──┤                  └──► T007 (rename test_db_crud)
       │
       └──── (stable imports) ──► T008 ──► T013 (lru_cache, platform_cli.py)
                                ├──► T009
                                └──► T010

T011 ──── independent (no deps)
T012 ──── independent (needs errors.py from epic 018 prerequisite)
T014 ──── independent (needs vision-build.py in same dir; T001-T006 stable)
T015 ──── independent (needs db_decisions functions; T001-T006 stable)

T016, T017 ──► all previous tasks complete
```

**Parallel execution**: After T001–T007 complete and `make test` passes:
- T008, T009, T010 can be done in sequence (all touch different files)
- T011, T012 can run in parallel with T008–T010
- T013 can run in parallel with T011, T012 (after T008)
- T014, T015 can run in parallel with each other (after T001–T007)

---

## Implementation Strategy

**MVP Scope**: US1 (T001–T007) alone delivers the highest-risk structural improvement. If time is constrained, ship US1 + US2 (T001–T010) as a first merge — these two P1 stories deliver the foundational code quality goals.

**Execution order** (sequential, no parallelism):
1. T001 → T002 → T003 → T004 → T005 → T006 → T007 → `make test` ✓
2. T008 → T009 → T010 → verify NDJSON ✓
3. T011 (independent) → T012 (independent) → T013 (independent)
4. T014 → T015 → `make test` ✓
5. T016 → T017 → final gate

**Total tasks**: 17  
**Estimated LOC net change**: ~2,760 LOC new/modified  
**Ruff compliance**: All new files must pass `make ruff` before T017

---

## Acceptance Criteria Traceability

| Acceptance Criterion | Tasks |
|---------------------|-------|
| `db.py` split in 4 modules, re-export facade functional | T001–T005 |
| `from db import X` callers unchanged | T005 |
| Zero `print("[ok]")` / `print("[error]")` in scripts | T008–T010 |
| `platform_cli.py status --all --json` emits NDJSON | T008 |
| `memory_consolidate.py --dry-run` produces report | T011 |
| `skill-lint.py` detects missing `## Output Directory` (WARNING) | T012 |
| `_discover_platforms()` uses `lru_cache` | T013 |
| `test_vision_build.py` ≥5 test cases | T014 |
| `test_sync_memory.py` ≥5 test cases | T015 |
| All existing `from db import ...` imports work | T005, T006, T007 |
| `make test` passes | T006, T007, T016, T017 |
| `make ruff` passes | T016 |
