### T006 — DONE
- [US1] Update `.specify/scripts/tests/test_db_core.py` to cover the symbols now in `db_core.py`: import from `db_core` directly (not `db`); ensure the following are covered: `_ClosingConnection` contex
- Files: .specify/scripts/tests/test_db_core.py, db_core.py
- Tokens in/out: 11/3533

### T007 — DONE
- [US1] Rename `.specify/scripts/tests/test_db_crud.py` → `.specify/scripts/tests/test_db_pipeline.py`; update all imports inside the file to import from `db_pipeline` directly (in addition to or instea
- Files: .specify/scripts/tests/test_db_crud.py, .specify/scripts/tests/test_db_pipeline.py, pytest.ini, conftest.py
- Tokens in/out: 9/805

### T008 — DONE
- [US2] Add `_NDJSONFormatter` class and `_setup_logging(json_mode: bool) -> None` function to `.specify/scripts/platform_cli.py` (place near top, after imports); add `--json` flag to the `ArgumentParse
- Files: .specify/scripts/platform_cli.py
- Tokens in/out: 45/8409

### T009 — DONE
- [US2] Add `_NDJSONFormatter` class (identical pattern to T008) and `_setup_logging()` to `.specify/scripts/dag_executor.py`; add `--json` to its `ArgumentParser`; replace all `print("[ok]")`, `print("
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 20/3466

### T010 — DONE
- [US2] Add `_NDJSONFormatter` class (identical pattern) and `_setup_logging()` to `.specify/scripts/post_save.py`; add `--json` to its `ArgumentParser`; replace all internal `print(...)` calls with app
- Files: .specify/scripts/post_save.py
- Tokens in/out: 14/3177

### T011 — DONE
- [US2] [P] Create `.specify/scripts/memory_consolidate.py` (~200 LOC) implementing: (1) CLI with `--dry-run` (default) and `--apply` flags; (2) `scan_memory_files(memory_dir: Path) -> list[dict]` — rea
- Files: .specify/scripts/memory_consolidate.py, MEMORY.md
- Tokens in/out: 15/4503

### T012 — DONE
- [US4] [P] Extend `lint_single_skill()` in `.specify/scripts/skill-lint.py` with two new checks: (1) **gate-valid** (ERROR): after frontmatter is parsed, `from errors import VALID_GATES`; if `frontmatt
- Files: .specify/scripts/skill-lint.py
- Tokens in/out: 22/3115

### T013 — DONE
- [US5] [P] Apply `@functools.lru_cache(maxsize=None)` to `_discover_platforms()` in `.specify/scripts/platform_cli.py`: add `from functools import lru_cache` to imports; decorate `_discover_platforms` 
- Files: .specify/scripts/platform_cli.py
- Tokens in/out: 23/2982

### T014 — DONE
- [US6] [P] Create `.specify/scripts/tests/test_vision_build.py` (~180 LOC) with ≥6 test cases using `unittest.mock.patch` and `tmp_path` fixture: (1) `test_containers_table_minimal` — call `_containers
- Files: .specify/scripts/tests/test_vision_build.py, unittest.mock.patch, subprocess.run, subprocess.run, subprocess.run
- Tokens in/out: 16/4669

### T015 — DONE
- [US6] [P] Create `.specify/scripts/tests/test_sync_memory.py` (~130 LOC) with ≥6 test cases using in-memory SQLite DB and `tmp_path` fixture: (1) `test_import_basic_frontmatter` — write a temp `.md` f
- Files: .specify/scripts/tests/test_sync_memory.py
- Tokens in/out: 9/2829

### T016 — DONE
- Fix any ruff violations introduced by previous tasks: run `make ruff` from repo root; apply `make ruff-fix` for auto-fixable issues; manually fix any remaining violations (E501 line length, F401 unuse
- Tokens in/out: 6/216

### T017 — DONE
- Run full verification checklist from quickstart.md: (1) `python3 -c "from db import get_conn, migrate, upsert_platform, insert_decision, create_trace; print('facade OK')"` from `.specify/scripts/`; (2
- Tokens in/out: 15/3193

