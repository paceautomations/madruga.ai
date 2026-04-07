# Tasks: SQLite Foundation

**Input**: Design documents from `/specs/002-sqlite-foundation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: TDD per constitution §VII. pytest para db.py (CRUD, migration, seed, hash).

**Organization**: Tasks grouped by user story. Each story independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)

## Path Conventions

- Scripts: `.specify/scripts/`
- Migrations: `.pipeline/migrations/`
- Tests: `.specify/scripts/tests/`
- CI: `.github/workflows/`
- Skills: `.claude/commands/madruga/`
- Knowledge: `.claude/knowledge/`

---

## Phase 1: Setup

**Purpose**: Directory structure, gitignore, migration SQL

**Checkpoint**: `.pipeline/migrations/001_initial.sql` exists and is valid SQL.

- [x] T001 Create `.pipeline/` directory and add `.pipeline/madruga.db` to `.gitignore` (append line if not present)
- [x] T002 [P] Create `.pipeline/migrations/` directory
- [x] T003 [P] Create `.specify/scripts/tests/` directory with empty `__init__.py`
- [x] T004 Write `.pipeline/migrations/001_initial.sql` with full schema: 8 tables (platforms, pipeline_nodes, epics, epic_nodes, decisions, artifact_provenance, pipeline_runs, events) + all indexes + `_migrations` tracking table. Schema verbatim from `docs/process_improvement.md` and `specs/002-sqlite-foundation/data-model.md`. Include CHECK constraints and foreign keys.

**Validation Phase 1**:
- `test -d .pipeline/migrations` → exists
- `grep -q 'madruga.db' .gitignore` → found
- `python3 -c "import sqlite3; conn=sqlite3.connect(':memory:'); conn.executescript(open('.pipeline/migrations/001_initial.sql').read()); print('OK')"` → OK

---

## Phase 2: Foundational — db.py Core

**Purpose**: Connection management, migration runner, hash utility. All subsequent tasks depend on this.

**Checkpoint**: `python3 -c "from db import get_conn, migrate; migrate()"` creates DB with 8 tables.

- [x] T005 Create `.specify/scripts/db.py` with core functions: `get_conn()` (WAL mode, FK=ON, busy_timeout=5000, auto-creates .pipeline/ dir, row_factory=sqlite3.Row), `migrate()` (read .pipeline/migrations/*.sql in sorted order, track in _migrations table, each migration in transaction), `compute_file_hash(path)` (return "sha256:" + SHA256 hex truncated to 12 chars)
- [x] T006 Create `.specify/scripts/tests/conftest.py` with fixtures: `tmp_db` (creates temp DB, runs migration, yields connection, cleans up), `sample_platform_dir` (creates temp platform dir with platform.yaml + sample files)
- [x] T007 Create `.specify/scripts/tests/test_db_core.py` with tests: `test_get_conn_creates_db`, `test_get_conn_wal_mode`, `test_get_conn_foreign_keys`, `test_migrate_creates_tables` (verify 8 tables + _migrations), `test_migrate_idempotent` (run twice, no error), `test_migrate_partial_failure_rollback` (corrupt SQL file, verify previous tables still intact), `test_compute_file_hash_consistent`, `test_compute_file_hash_format` (starts with "sha256:")

**Validation Phase 2**:
- `cd .specify/scripts && python3 -m pytest tests/test_db_core.py -v` → all pass

---

## Phase 3: User Story 1 — Pipeline State Persistence (P1)

**Purpose**: CRUD functions for all 8 tables. Seed from filesystem. This is the core value.

**Independent Test**: Insert platform + nodes + epics, query them back, verify round-trip.

### CRUD Functions

- [x] T008 [US1] Implement `upsert_platform(conn, platform_id, name, repo_path, **kwargs)` and `get_platform(conn, platform_id)` in `.specify/scripts/db.py`. Uses INSERT OR REPLACE. Returns dict with all fields.
- [x] T009 [P] [US1] Implement `upsert_pipeline_node(conn, platform_id, node_id, status, **kwargs)` and `get_pipeline_nodes(conn, platform_id)` in `.specify/scripts/db.py`. Returns list of dicts. Accepts optional output_hash, input_hashes (JSON string), output_files (JSON string), completed_at, completed_by, line_count.
- [x] T010 [P] [US1] Implement `upsert_epic(conn, platform_id, epic_id, title, **kwargs)` and `get_epics(conn, platform_id)` in `.specify/scripts/db.py`. Returns list of dicts sorted by epic_id.
- [x] T011 [P] [US1] Implement `upsert_epic_node(conn, platform_id, epic_id, node_id, status, **kwargs)` and `get_epic_nodes(conn, platform_id, epic_id)` in `.specify/scripts/db.py`.
- [x] T012 [P] [US1] Implement `insert_decision(conn, platform_id, skill, title, **kwargs)` and `get_decisions(conn, platform_id, epic_id=None)` in `.specify/scripts/db.py`. Auto-generates decision_id if not provided (uuid4). Accepts decisions_json, assumptions_json, open_questions_json as Python lists (serialized to JSON internally).
- [x] T013 [P] [US1] Implement `insert_provenance(conn, platform_id, file_path, generated_by, **kwargs)` and `get_provenance(conn, platform_id)` in `.specify/scripts/db.py`. Uses INSERT OR REPLACE (file_path is part of PK — re-generation updates).
- [x] T014 [P] [US1] Implement `insert_run(conn, platform_id, node_id, **kwargs)` and `complete_run(conn, run_id, status, **kwargs)` and `get_runs(conn, platform_id)` in `.specify/scripts/db.py`. insert_run auto-generates run_id (uuid4) and sets started_at. complete_run sets completed_at and status.
- [x] T015 [P] [US1] Implement `insert_event(conn, platform_id, entity_type, entity_id, action, **kwargs)` and `get_events(conn, platform_id, entity_type=None, entity_id=None)` in `.specify/scripts/db.py`.

### Staleness Detection

- [x] T016 [US1] Implement `get_stale_nodes(conn, platform_id, dag_edges)` in `.specify/scripts/db.py`. Accepts `dag_edges` as dict `{node_id: [dep_node_ids]}` (parsed from platform.yaml by caller). Returns list of nodes where any dependency has `completed_at` > node's `completed_at`.
- [x] T017 [US1] Implement `get_platform_status(conn, platform_id)` in `.specify/scripts/db.py`. Returns summary dict: `{total_nodes, done, pending, stale, blocked, skipped, progress_pct}`.
- [x] T018 [US1] Implement `get_epic_status(conn, platform_id, epic_id)` in `.specify/scripts/db.py`. Same format as platform_status but for epic nodes.

### Seed

- [x] T019 [US1] Implement `seed_from_filesystem(conn, platform_id, platform_dir)` in `.specify/scripts/db.py`. Steps: (1) read platform.yaml → upsert_platform, (2) for each pipeline node in YAML: check if output files exist → upsert_pipeline_node with status done/pending + compute_file_hash if done, (3) scan epics/*/pitch.md → upsert_epic for each. Idempotent (safe to re-run).

### Tests

- [x] T020 [US1] Create `.specify/scripts/tests/test_db_crud.py` with tests: one test per CRUD function (upsert + get round-trip), test_upsert_idempotent (same data twice, no duplicate), test_insert_decision_auto_id, test_insert_run_auto_id, test_complete_run, test_get_stale_nodes (setup 2 nodes where dep is newer), test_get_platform_status_counts, test_get_epic_status_counts
- [x] T021 [US1] Create `.specify/scripts/tests/test_db_seed.py` with tests: test_seed_from_filesystem (mock platform dir with platform.yaml + some files, verify tables populated), test_seed_idempotent (run twice, same row count), test_seed_missing_platform_yaml (should raise or warn)

**Validation Phase 3**:
- `cd .specify/scripts && python3 -m pytest tests/ -v` → all pass
- `python3 -c "from db import *; migrate(); conn=get_conn(); seed_from_filesystem(conn,'prosauai','../../platforms/prosauai'); print(get_platform_status(conn,'prosauai'))"` → shows real status

---

## Phase 4: User Story 2 — CI Pipeline (P1)

**Purpose**: GitHub Actions workflow with 3 parallel jobs.

**Independent Test**: Push to branch, CI runs and reports.

- [x] T022 [US2] Create `.github/workflows/ci.yml` with 3 parallel jobs: (1) `lint` — checkout + setup-python 3.11 + pip install pyyaml copier + `python3 .specify/scripts/platform.py lint --all`, (2) `likec4` — checkout + setup-node 20 + `npx likec4 build` for each `platforms/*/model/` dir, (3) `templates` — checkout + setup-python + pip install copier pyyaml + copier copy to temp dir with --defaults + validate output. Trigger: push to main + pull_request.
- [x] T023 [P] [US2] Create `.specify/scripts/tests/test_ci_config.py` — test that `.github/workflows/ci.yml` is valid YAML, has 3 jobs, each job has expected steps, trigger includes push and pull_request.

**Validation Phase 4**:
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` → no error
- `cd .specify/scripts && python3 -m pytest tests/test_ci_config.py -v` → pass

---

## Phase 5: User Story 3 — Prerequisites via BD (P2)

**Purpose**: `--use-db` flag in prerequisites checker for DB-backed status queries.

**Independent Test**: `check-platform-prerequisites.sh --json --status --platform prosauai --use-db` returns DB-enhanced output.

- [x] T024 [US3] Add `--use-db` flag parsing to `.specify/scripts/bash/check-platform-prerequisites.sh`. When flag present and `.pipeline/madruga.db` exists: call Python via `python3 -c "import sys; sys.path.insert(0, '$REPO_ROOT/.specify/scripts'); from db import get_conn, get_pipeline_nodes; ..."` to query DB for node status (with output_hash, completed_at, stale detection). When DB doesn't exist: fallback to file-existence with warning "DB not found, using filesystem". Preserve all existing functionality when `--use-db` is not passed.
- [x] T025 [US3] Add stale detection to `--use-db` mode in `.specify/scripts/bash/check-platform-prerequisites.sh`. For each node in status output, add `"stale": true/false` field. Stale = any dependency node has `completed_at` > this node's `completed_at`. Parse DAG edges from platform.yaml to determine dependencies.

**Validation Phase 5**:
- `bash .specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform prosauai` → works as before (no --use-db)
- Seed prosauai first, then: `bash .specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform prosauai --use-db` → output includes hash and stale fields

---

## Phase 6: User Story 4 — Hallucination Guardrails (P2)

**Purpose**: Add escape hatch directives to research skills.

**Independent Test**: grep for guardrail text in skill files.

- [x] T026 [US4] Add hallucination guardrails to `.claude/commands/madruga/tech-research.md` Cardinal Rule section. Add 2 directives: (1) "Se research (Context7, web search) não retornar dados para uma alternativa, marcar toda a linha como `[DADOS INSUFICIENTES]` e recomendar adiar a decisão. NUNCA fabricar dados." (2) "Toda afirmação factual DEVE ter URL ou referência verificável. Sem URL → marcar `[FONTE NÃO VERIFICADA]`."
- [x] T027 [P] [US4] Add hallucination guardrails to `.claude/commands/madruga/adr-gen.md` Cardinal Rule section. Add directive: "Toda referência DEVE ter URL ou título específico de documento verificável. Sem URL → `[FONTE NÃO VERIFICADA]`. NUNCA fabricar sources."
- [x] T028 [P] [US4] Update `.claude/knowledge/pipeline-dag-knowledge.md` Section 6 (Auto-Review Checklist Template). Add universal check: "Sources verificáveis? Toda afirmação factual tem URL ou referência. Sem URL → [FONTE NÃO VERIFICADA]."
- [x] T029 [P] [US4] Update `.claude/knowledge/pipeline-dag-knowledge.md` Section 2 (Skill Uniform Contract). Add to step 5 (Save + Report): instructions for SQLite integration — "Após salvar artefato, se `.pipeline/madruga.db` existir: chamar `db.upsert_pipeline_node()` ou `db.upsert_epic_node()` conforme o nível, `db.insert_provenance()`, `db.insert_event()`. Se BD não existir, prosseguir normalmente."

**Validation Phase 6**:
- `grep -q "DADOS INSUFICIENTES" .claude/commands/madruga/tech-research.md` → found
- `grep -q "FONTE NÃO VERIFICADA" .claude/commands/madruga/adr-gen.md` → found
- `grep -q "FONTE NÃO VERIFICADA" .claude/knowledge/pipeline-dag-knowledge.md` → found
- `grep -q "upsert_pipeline_node" .claude/knowledge/pipeline-dag-knowledge.md` → found

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Final integration, documentation update.

- [x] T030 Run full test suite: `cd .specify/scripts && python3 -m pytest tests/ -v --tb=short`. All tests must pass.
- [x] T031 Run `python3 -c "from db import *; migrate(); conn=get_conn(); seed_from_filesystem(conn,'prosauai','../../platforms/prosauai'); seed_from_filesystem(conn,'madruga-ai','../../platforms/madruga-ai'); print(get_platform_status(conn,'prosauai')); print(get_platform_status(conn,'madruga-ai'))"` — verify both platforms seeded correctly.
- [x] T032 Validate CI workflow: `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); assert len(d['jobs'])==3; print('CI valid')"`.

---

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Core db.py)
Phase 2 → Phase 3 (CRUD + Seed) [US1]
Phase 2 → Phase 4 (CI) [US2] — can run in parallel with Phase 3
Phase 3 → Phase 5 (Prerequisites --use-db) [US3]
Phase 1 → Phase 6 (Guardrails) [US4] — can run in parallel with Phase 3
All → Phase 7 (Polish)
```

## Parallel Execution Opportunities

| Tasks | Can Parallel? | Reason |
|-------|--------------|--------|
| T002, T003 | Yes | Different directories |
| T009-T015 | Yes | Independent CRUD functions, different code sections |
| T022, T023 | Yes | CI config + test are independent files |
| T026, T027, T028, T029 | Yes | Different files |
| Phase 4 + Phase 3 | Yes | CI is independent of CRUD |
| Phase 6 + Phase 3 | Yes | Guardrails are independent of CRUD |

## Implementation Strategy

**MVP (minimum viable)**: Phase 1 + 2 + 3 (US1). Delivers: working DB with CRUD, seed, and staleness detection. Everything else builds on this.

**Full delivery**: All 7 phases. ~32 tasks total.

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 32 |
| US1 (State Persistence) | 14 tasks |
| US2 (CI) | 2 tasks |
| US3 (Prerequisites) | 2 tasks |
| US4 (Guardrails) | 4 tasks |
| Setup + Foundation + Polish | 10 tasks |
| Parallel opportunities | 6 groups |
