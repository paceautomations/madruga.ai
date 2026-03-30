# Tasks: BD como Source of Truth para Decisions + Memory

**Input**: Design documents from `platforms/madruga-ai/epics/009-decision-log-bd/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md
**Tests**: TDD required per constitution (Principle VII)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)

## Phase 1: Setup

**Purpose**: Fix migrate() and map ADR variations before any schema/code changes

- [x] T001 Map all existing ADR frontmatter fields and section headers by reading every `platforms/*/decisions/ADR-*.md` file — document variations in a comment block at top of test file `.specify/scripts/tests/test_db_decisions.py`
- [x] T002 Fix `migrate()` in `.specify/scripts/db.py` to handle `CREATE TRIGGER ... END;` blocks — detect trigger/view bodies and avoid splitting `;` inside them
- [x] T003 Add FTS5 availability check in `migrate()` in `.specify/scripts/db.py` — try `CREATE VIRTUAL TABLE` in `:memory:`, log warning and skip FTS statements if unavailable
- [x] T004 Write test for `migrate()` trigger handling in `.specify/scripts/tests/test_db_core.py` — verify migration with trigger bodies applies correctly

**Checkpoint**: migrate() can handle triggers. ADR format variations documented.

---

## Phase 2: Foundational — Schema + Core CRUD

**Purpose**: Migration 003 + expanded decision/memory API. MUST complete before any user story.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests (RED)

- [x] T005 [P] Write failing tests for new decision columns (content_hash, decision_type, context, consequences, tags_json) in `.specify/scripts/tests/test_db_decisions.py` — test insert with new fields and verify retrieval
- [x] T006 [P] Write failing tests for `memory_entries` CRUD (insert, get, update, delete) in `.specify/scripts/tests/test_db_decisions.py`
- [x] T007 [P] Write failing tests for `decision_links` CRUD (insert, get by id, get by direction) in `.specify/scripts/tests/test_db_decisions.py`
- [x] T008 [P] Write failing test for `get_decisions()` with filters (status, decision_type) in `.specify/scripts/tests/test_db_decisions.py`

### Implementation (GREEN)

- [x] T009 Write migration `003_decisions_memory.sql` in `.pipeline/migrations/` — ALTER TABLE decisions (5 columns), CREATE TABLE decision_links, CREATE TABLE memory_entries, CREATE indexes
- [x] T010 Expand `insert_decision()` in `.specify/scripts/db.py` — add kwargs for content_hash, decision_type, context, consequences, tags_json; update ON CONFLICT SET clause
- [x] T011 Expand `get_decisions()` in `.specify/scripts/db.py` — add optional filters: status, decision_type; preserve backward compatibility
- [x] T012 Implement `insert_memory()`, `get_memories()`, `update_memory()`, `delete_memory()` in `.specify/scripts/db.py`
- [x] T013 Implement `insert_decision_link()`, `get_decision_links()` in `.specify/scripts/db.py`
- [x] T014 Run tests — verify all T005-T008 pass (GREEN)

**Checkpoint**: Foundation ready — schema applied, CRUD works, tests green.

---

## Phase 3: User Story 1 — Registrar decisao via skill (Priority: P1) MVP

**Goal**: Decisions nascam no BD via `insert_decision()` e sejam exportadas como ADR-*.md Nygard.

**Independent Test**: Chamar `insert_decision()` + `export_decision_to_markdown()` e verificar arquivo gerado.

### Tests (RED)

- [x] T015 [P] [US1] Write failing test for `export_decision_to_markdown()` in `.specify/scripts/tests/test_db_decisions.py` — verify output file has correct frontmatter fields (title, status, decision, alternatives, rationale), correct sections (## Contexto, ## Decisao, ## Alternativas consideradas, ## Consequencias), and correct auto-numbering
- [x] T016 [P] [US1] Write failing test for `sync_decisions_to_markdown()` batch export in `.specify/scripts/tests/test_db_decisions.py` — insert 3 decisions, sync, verify 3 files created
- [x] T017 [P] [US1] Write failing test for supersede chain in `.specify/scripts/tests/test_db_decisions.py` — insert A (accepted), insert B that supersedes A, verify A.status=superseded and A.superseded_by=B.id

### Implementation

- [x] T018 [US1] Implement `export_decision_to_markdown()` in `.specify/scripts/db.py` — template string producing Nygard format with frontmatter YAML + sections; auto-number via max existing ADR number + 1 in output_dir
- [x] T019 [US1] Implement `sync_decisions_to_markdown()` in `.specify/scripts/db.py` — iterate all decisions for platform, call export for each, return count
- [x] T020 [US1] Add event logging in `insert_decision()` in `.specify/scripts/db.py` — call `insert_event()` with entity_type='decision', action='created'/'updated'
- [x] T021 [US1] Run tests — verify T015-T017 pass (GREEN)

**Checkpoint**: US1 complete — decisions can be created in BD and exported to markdown.

---

## Phase 4: User Story 2 — Importar ADRs existentes para o BD (Priority: P1)

**Goal**: Import retroativo dos ADRs existentes de qualquer plataforma para o BD.

**Independent Test**: Rodar `import_all_adrs(conn, "fulano", decisions_dir)` e verificar registros no BD.

### Tests (RED)

- [x] T022 [P] [US2] Write failing test for `_parse_adr_markdown()` helper in `.specify/scripts/tests/test_db_decisions.py` — create fixture ADR file with known frontmatter + sections, verify parsed dict has correct fields
- [x] T023 [P] [US2] Write failing test for `import_adr_from_markdown()` in `.specify/scripts/tests/test_db_decisions.py` — import fixture ADR, verify BD record matches; re-import same file, verify no duplicate (idempotent via content_hash)
- [x] T024 [P] [US2] Write failing test for `import_all_adrs()` in `.specify/scripts/tests/test_db_decisions.py` — create 3 fixture ADR files, import all, verify count=3 and all records correct
- [x] T025 [P] [US2] Write failing test for malformed frontmatter handling in `.specify/scripts/tests/test_db_decisions.py` — import file with broken YAML, verify warning logged and file skipped (no crash)

### Implementation

- [x] T026 [US2] Implement `_parse_adr_markdown()` helper in `.specify/scripts/db.py` — split frontmatter (pyyaml) + body sections (regex `## Heading`); return dict with title, status, decision, alternatives, rationale, context, consequences, and full body; handle variations documented in T001
- [x] T027 [US2] Implement `import_adr_from_markdown()` in `.specify/scripts/db.py` — call parser, compute content_hash, call `insert_decision()` with upsert; skip if hash unchanged
- [x] T028 [US2] Implement `import_all_adrs()` in `.specify/scripts/db.py` — glob `ADR-*.md` in decisions_dir, call `import_adr_from_markdown()` for each, count successes, log warnings for failures
- [x] T029 [US2] Run tests — verify T022-T025 pass (GREEN)
- [x] T030 [US2] Validate SC-001: Run `import_all_adrs()` on `platforms/fulano/decisions/` in a manual test script or pytest — verify all 19 ADRs imported with correct fields

**Checkpoint**: US2 complete — existing ADRs can be imported into BD. SC-001 validated.

---

## Phase 5: User Story 3 — Consultar decisoes no BD (Priority: P2)

**Goal**: Query decisions por filtros + full-text search via FTS5.

**Independent Test**: Insert decisions, query by filters e FTS5, verify correct results.

### Tests (RED)

- [x] T031 [P] [US3] Write failing test for FTS5 `search_decisions()` in `.specify/scripts/tests/test_db_decisions.py` — insert 3 decisions with distinct context text, search for keyword, verify only matching decision returned
- [x] T032 [P] [US3] Write failing test for FTS5 trigger sync in `.specify/scripts/tests/test_db_decisions.py` — insert decision via `insert_decision()`, verify FTS table has matching row; update decision, verify FTS updated

### Implementation

- [x] T033 [US3] Add FTS5 virtual tables + triggers to `003_decisions_memory.sql` in `.pipeline/migrations/` — decisions_fts (title, context, consequences) + memory_fts (name, description, content); include INSERT/UPDATE/DELETE triggers
- [x] T034 [US3] Implement `search_decisions()` in `.specify/scripts/db.py` — FTS5 MATCH query with optional platform_id filter; return list[dict] ordered by rank
- [x] T035 [US3] Run tests — verify T031-T032 pass (GREEN)

**Checkpoint**: US3 complete — decisions queryable by filters and full-text.

---

## Phase 6: User Story 4 — Registrar e consultar memory entries (Priority: P2)

**Goal**: Memory CRUD + import from `.claude/memory/` + FTS5 search + export to markdown.

**Independent Test**: Insert memories, import from files, search, export.

### Tests (RED)

- [x] T036 [P] [US4] Write failing test for `_parse_memory_markdown()` helper in `.specify/scripts/tests/test_db_decisions.py` — fixture memory file with frontmatter (name, description, type) + body
- [x] T037 [P] [US4] Write failing test for `import_memory_from_markdown()` in `.specify/scripts/tests/test_db_decisions.py` — import fixture, verify BD record; re-import, verify idempotent
- [x] T038 [P] [US4] Write failing test for `export_memory_to_markdown()` in `.specify/scripts/tests/test_db_decisions.py` — insert memory, export, verify file has correct frontmatter + body
- [x] T039 [P] [US4] Write failing test for `search_memories()` FTS5 in `.specify/scripts/tests/test_db_decisions.py`

### Implementation

- [x] T040 [US4] Implement `_parse_memory_markdown()` helper in `.specify/scripts/db.py` — split frontmatter + body; extract name, description, type
- [x] T041 [US4] Implement `import_memory_from_markdown()` and `import_all_memories()` in `.specify/scripts/db.py`
- [x] T042 [US4] Implement `export_memory_to_markdown()` and `sync_memories_to_markdown()` in `.specify/scripts/db.py`
- [x] T043 [US4] Implement `search_memories()` in `.specify/scripts/db.py` — FTS5 MATCH with optional type filter
- [x] T044 [US4] Add event logging for memory operations in `.specify/scripts/db.py`
- [x] T045 [US4] Run tests — verify T036-T039 pass (GREEN)

**Checkpoint**: US4 complete — memory entries CRUD + import/export/search functional.

---

## Phase 7: User Story 5 — Rastrear links entre decisoes (Priority: P3)

**Goal**: Decision link graph — query dependencies, supersedes, contradicts.

**Independent Test**: Create 3 decisions with links, query graph.

### Tests (RED)

- [x] T046 [P] [US5] Write failing test for bidirectional link query in `.specify/scripts/tests/test_db_decisions.py` — insert A→B (supersedes), query from A, query from B, verify both return the link
- [x] T047 [P] [US5] Write failing test for link type filtering in `.specify/scripts/tests/test_db_decisions.py` — insert 3 links of different types, query by type

### Implementation

- [x] T048 [US5] Verify `insert_decision_link()` and `get_decision_links()` pass tests from T046-T047 (already implemented in T013, may need direction param)
- [x] T049 [US5] Run tests — verify T046-T047 pass (GREEN)

**Checkpoint**: US5 complete — decision link graph queryable.

---

## Phase 8: CLI Integration

**Purpose**: Expose import/export via `platform.py` subcommands.

### Tests (RED)

- [x] T050 [P] Write failing integration test for `platform.py import-adrs fulano` in `.specify/scripts/tests/test_platform.py` — mock filesystem, verify import called with correct args
- [x] T051 [P] Write failing integration test for `platform.py export-adrs fulano` in `.specify/scripts/tests/test_platform.py`

### Implementation

- [x] T052 Add `import-adrs` subcommand to `.specify/scripts/platform.py` — parse args, call `import_all_adrs()`
- [x] T053 Add `export-adrs` subcommand to `.specify/scripts/platform.py` — parse args, call `sync_decisions_to_markdown()`
- [x] T054 Add `import-memory` subcommand to `.specify/scripts/platform.py` — call `import_all_memories()`
- [x] T055 Add `export-memory` subcommand to `.specify/scripts/platform.py` — call `sync_memories_to_markdown()`
- [x] T056 Run tests — verify T050-T051 pass (GREEN)
- [x] T057 Validate SC-004 + SC-005: Run full round-trip — import ADRs, export, verify idempotent re-import

**Checkpoint**: CLI complete — all import/export operations available via platform.py.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, cleanup, observability.

- [x] T058 [P] Run ruff format on all modified Python files (`.specify/scripts/db.py`, `.specify/scripts/platform.py`, `.specify/scripts/tests/test_db_decisions.py`)
- [x] T059 [P] Run ruff check --fix on all modified Python files
- [x] T060 Validate SC-003: Run FTS5 search benchmark — insert 50+ decisions, measure query time < 100ms
- [x] T061 Validate SC-006: Import `.claude/memory/*.md`, verify queryable by type and FTS5
- [x] T062 Run full test suite: `cd .specify/scripts && python -m pytest tests/ -v`
- [x] T063 Update CLAUDE.md Active Technologies section if needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 - Register+Export)**: Depends on Phase 2
- **Phase 4 (US2 - Import)**: Depends on Phase 2 (can run parallel with Phase 3)
- **Phase 5 (US3 - Query+FTS5)**: Depends on Phase 2 (can run after Phase 3 for FTS trigger testing)
- **Phase 6 (US4 - Memory)**: Depends on Phase 2 (can run parallel with Phase 3-5)
- **Phase 7 (US5 - Links)**: Depends on Phase 2 (lowest priority, can defer)
- **Phase 8 (CLI)**: Depends on Phase 3 + Phase 4 + Phase 6
- **Phase 9 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (Register+Export)**: After Foundational — no other story dependencies
- **US2 (Import)**: After Foundational — no other story dependencies (can parallel with US1)
- **US3 (Query+FTS5)**: After Foundational — enhanced by US1/US2 having data, but testable independently
- **US4 (Memory)**: After Foundational — fully independent
- **US5 (Links)**: After Foundational — fully independent (P3, can defer)

### Parallel Opportunities

```
Phase 2 done →
  ├── US1 (Register+Export) ─┐
  ├── US2 (Import)          ─┼── Phase 8 (CLI) → Phase 9 (Polish)
  ├── US3 (Query+FTS5)       │
  ├── US4 (Memory)          ─┘
  └── US5 (Links) — can defer
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (fix migrate, map ADRs)
2. Complete Phase 2: Foundational (schema + CRUD)
3. Complete Phase 3: US1 — Register + Export
4. Complete Phase 4: US2 — Import retroativo
5. **STOP and VALIDATE**: Import 19 ADRs, verify BD populated, export back
6. This alone delivers core value: BD as source of truth

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → MVP (import/export functional)
3. US3 → FTS5 search adds query power
4. US4 → Memory in BD
5. US5 → Links (optional, can defer)
6. CLI → Platform.py integration
7. Polish → Final validation

---

## Notes

- Constitution requires TDD — write failing tests before each implementation block
- All new columns in `decisions` are nullable (ALTER TABLE constraint)
- FTS5 triggers require fixed `migrate()` (T002)
- Parser must handle variations documented in T001
- `decision_links` (US5) is P3 — can be deferred to next epic if needed
- Commit after each phase checkpoint
