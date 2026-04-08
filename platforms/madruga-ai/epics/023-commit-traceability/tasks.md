# Tasks: Commit Traceability

**Input**: Design documents from `platforms/madruga-ai/epics/023-commit-traceability/`
**Prerequisites**: spec.md (required), pitch.md (required — contains architecture decisions and schema)
**Tests**: Included — constitution mandates TDD for all code.

**Organization**: Tasks grouped by user story. US1+US2 are both P1 but independent: US1 focuses on DB query capability, US2 on automatic capture via hook.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Migration and base schema for the `commits` table

- [x] T001 Create migration file `.pipeline/migrations/014_commits.sql` with CREATE TABLE commits (id, sha UNIQUE, message, author, platform_id, epic_id nullable, source DEFAULT 'hook', committed_at, files_json, created_at) and indexes on platform_id, epic_id, committed_at
- [x] T002 Verify migration applies cleanly by running `python3 -c "from .specify.scripts.db_core import migrate; migrate()"` against a fresh DB copy

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB CRUD functions that ALL user stories depend on. No story work can begin without these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

- [x] T003 [P] Write tests for `insert_commit()` in `.specify/scripts/tests/test_db_pipeline.py` — test single insert, duplicate SHA (INSERT OR IGNORE), multi-platform commit creates multiple rows, NULL epic_id for ad-hoc
- [x] T004 [P] Write tests for query functions in `.specify/scripts/tests/test_db_pipeline.py` — `get_commits_by_epic()` returns correct commits, `get_commits_by_platform()` filters by platform, `get_adhoc_commits()` returns only NULL epic_id rows, empty results return empty list

### Implementation for Foundational

- [x] T005 Implement `insert_commit(conn, sha, message, author, platform_id, epic_id, source, committed_at, files_json)` in `.specify/scripts/db_pipeline.py` — uses INSERT OR IGNORE for idempotency, files_json stored as JSON string
- [x] T006 Implement `get_commits_by_epic(conn, epic_id, platform_id=None)` in `.specify/scripts/db_pipeline.py` — returns list of dicts ordered by committed_at DESC
- [x] T007 [P] Implement `get_commits_by_platform(conn, platform_id, limit=100, offset=0)` in `.specify/scripts/db_pipeline.py` — paginated, ordered by committed_at DESC
- [x] T008 [P] Implement `get_adhoc_commits(conn, platform_id=None, limit=100)` in `.specify/scripts/db_pipeline.py` — WHERE epic_id IS NULL, optional platform filter
- [x] T009 Run tests from T003-T004 and verify all pass (Red→Green)

**Checkpoint**: DB layer ready — insert and query functions tested and working

---

## Phase 3: User Story 1 — Consultar commits de um epic (Priority: P1) 🎯 MVP

**Goal**: Operador pode consultar todos os commits associados a um epic via DB query, com dados corretos de SHA, mensagem, autor e data.

**Independent Test**: Executar backfill para um epic conhecido e verificar que `get_commits_by_epic()` retorna os commits corretos.

### Tests for User Story 1

- [x] T010 [P] [US1] Write integration test in `.specify/scripts/tests/test_db_pipeline.py` — insert 5 commits (3 for epic-012, 2 ad-hoc), verify `get_commits_by_epic('012-...')` returns exactly 3, verify `get_adhoc_commits()` returns exactly 2
- [x] T011 [P] [US1] Write integration test for empty epic query in `.specify/scripts/tests/test_db_pipeline.py` — query non-existent epic returns empty list without error

### Implementation for User Story 1

- [x] T012 [US1] Add `get_commit_stats(conn, platform_id=None)` in `.specify/scripts/db_pipeline.py` — returns dict with total_commits, commits_per_epic (dict), adhoc_count, adhoc_percentage for portal stats (FR-014)
- [x] T013 [US1] Run tests from T010-T011 and verify all pass

**Checkpoint**: US1 complete — DB queries return correct commits per epic, empty results handled gracefully

---

## Phase 4: User Story 2 — Registrar commits automaticamente via hook (Priority: P1)

**Goal**: Cada commit feito no repositório é registrado automaticamente no DB sem ação manual, com identificação correta de plataforma e epic.

**Independent Test**: Fazer um commit na branch `epic/madruga-ai/023-*` e verificar nova row na tabela `commits`.

### Tests for User Story 2

- [x] T014 [P] [US2] Write tests for platform detection logic in `.specify/scripts/tests/test_hook_post_commit.py` — branch `epic/prosauai/007-foo` → platform `prosauai`; file paths `platforms/prosauai/x.md` → platform `prosauai`; no match → fallback `madruga-ai`
- [x] T015 [P] [US2] Write tests for epic detection logic in `.specify/scripts/tests/test_hook_post_commit.py` — branch `epic/madruga-ai/023-commit-traceability` → epic `023-commit-traceability`; tag `[epic:015]` in message → epic `015` (override); no match → NULL
- [x] T016 [P] [US2] Write tests for multi-platform commit handling in `.specify/scripts/tests/test_hook_post_commit.py` — commit touching `platforms/X/` and `platforms/Y/` generates 2 rows, one per platform
- [x] T017 [P] [US2] Write test for hook error handling in `.specify/scripts/tests/test_hook_post_commit.py` — DB failure (locked, missing) does not raise exception, logs to stderr

### Implementation for User Story 2

- [x] T018 [US2] Create `.specify/scripts/hook_post_commit.py` with `parse_branch(branch_name)` function that returns `(platform_id, epic_id)` tuple from branch pattern `epic/<platform>/<NNN-slug>`
- [x] T019 [US2] Add `detect_platforms_from_files(file_list)` function in `.specify/scripts/hook_post_commit.py` — scans file paths for `platforms/<X>/` pattern, returns set of platform_ids, fallback `madruga-ai` if empty
- [x] T020 [US2] Add `parse_epic_tag(message)` function in `.specify/scripts/hook_post_commit.py` — extracts `[epic:NNN]` tag from commit message, returns epic slug or None
- [x] T021 [US2] Add `get_head_info()` function in `.specify/scripts/hook_post_commit.py` — runs `git log -1 --format=%H%n%s%n%an%n%aI` and `git diff-tree --no-commit-id --name-only -r HEAD` via subprocess, returns dict with sha, message, author, date, files
- [x] T022 [US2] Implement `main()` in `.specify/scripts/hook_post_commit.py` — orchestrates: get_head_info → parse_branch → detect_platforms → parse_epic_tag → insert_commit per platform; wrap in try/except for best-effort (FR-007)
- [x] T023 [US2] Create installable hook script at `.specify/scripts/git-hooks/post-commit` (shell wrapper that calls `python3 .specify/scripts/hook_post_commit.py`)
- [x] T024 [US2] Add `install-hooks` target in `Makefile` — copies `.specify/scripts/git-hooks/post-commit` to `.git/hooks/post-commit` and sets executable permission
- [x] T025 [US2] Run tests from T014-T017 and verify all pass

**Checkpoint**: US2 complete — every commit is automatically captured with correct platform/epic classification. Hook is best-effort (never blocks commits)

---

## Phase 5: User Story 3 — Visualizar commits no portal (Priority: P2)

**Goal**: Aba "Changes" no control panel do portal exibe tabela de commits com filtros e estatísticas.

**Independent Test**: Acessar portal, abrir control panel, verificar aba "Changes" com tabela, filtros por plataforma/epic/tipo, e stats.

### Implementation for User Story 3

- [x] T026 [P] [US3] Create JSON export function `export_commits_json(output_path)` in `.specify/scripts/post_save.py` — queries all commits from DB, writes to `portal/src/data/commits-status.json` with structure `{generated_at, commits: [...], stats: {by_epic, by_platform, adhoc_pct}}`
- [x] T027 [P] [US3] Write test for `export_commits_json()` in `.specify/scripts/tests/test_post_save.py` — verify JSON structure, verify empty DB produces valid empty JSON
- [x] T028 [US3] Integrate `export_commits_json()` call into `_refresh_portal_status()` in `.specify/scripts/post_save.py` — called alongside existing pipeline-status.json export
- [x] T029 [US3] Create `portal/src/components/changes/ChangesTab.tsx` — React component with: table (SHA as GitHub link, message, platform, epic/"ad-hoc", date), client-side filters (platform, epic, type, date range), stats summary (total per epic, % ad-hoc vs epic)
- [x] T030 [US3] Add "Changes" tab button and panel to `portal/src/pages/[platform]/control-panel.astro` — new tab button with `data-tab="changes"`, new panel div importing `ChangesTab` with `client:visible`, update `initTabs()` script to include 'changes' in hash list
- [x] T031 [US3] Update `make status-json` target in `Makefile` to also generate `commits-status.json`

**Checkpoint**: US3 complete — portal shows commits with filtering and stats. Operador responde "quais commits do epic X?" em <10s via browser

---

## Phase 6: User Story 4 — Popular histórico retroativo (Priority: P2)

**Goal**: Script de backfill popula o DB com todo o histórico de commits desde o epic 001, com classificação correta de plataforma e epic.

**Independent Test**: Executar backfill e verificar que os 21 commits do epic 001 estão vinculados corretamente, epics subsequentes identificados via merge history, e commits em main marcados como ad-hoc.

### Tests for User Story 4

- [x] T032 [P] [US4] Write tests for merge-based epic detection in `.specify/scripts/tests/test_backfill_commits.py` — mock `git log --merges` output, verify epic extraction from merge commit messages referencing `epic/*` branches
- [x] T033 [P] [US4] Write test for pre-006 commit classification in `.specify/scripts/tests/test_backfill_commits.py` — commits in range 5f62946..d6befe0 are linked to epic `001-inicio-de-tudo`
- [x] T034 [P] [US4] Write test for idempotency in `.specify/scripts/tests/test_backfill_commits.py` — run backfill twice, verify zero duplicate rows (count unchanged)

### Implementation for User Story 4

- [x] T035 [US4] Create `.specify/scripts/backfill_commits.py` with `get_merge_commits()` function — runs `git log main --merges --format=%H%n%s%n%P` to identify merge commits from epic branches
- [x] T036 [US4] Add `get_epic_commits_from_merge(merge_sha)` function in `.specify/scripts/backfill_commits.py` — runs `git log <merge>^..<merge> --format=%H%n%s%n%an%n%aI` and `git diff-tree --no-commit-id --name-only -r <sha>` for each commit in the merge
- [x] T037 [US4] Add `get_direct_main_commits()` function in `.specify/scripts/backfill_commits.py` — runs `git log --no-merges --first-parent main --format=%H%n%s%n%an%n%aI` for ad-hoc commits
- [x] T038 [US4] Add `classify_pre006(sha, cutoff_sha='d6befe0')` function in `.specify/scripts/backfill_commits.py` — returns epic `001-inicio-de-tudo` for commits before cutoff, None otherwise
- [x] T039 [US4] Implement `main()` in `.specify/scripts/backfill_commits.py` with argparse — orchestrates: merge commits → epic commits → direct main commits → classify_pre006 → insert_commit per entry; uses INSERT OR IGNORE for idempotency; prints summary (total inserted, by epic, ad-hoc count)
- [x] T040 [US4] Run tests from T032-T034 and verify all pass

**Checkpoint**: US4 complete — full git history from epic 001 to HEAD is in the DB with correct epic associations. Re-run is safe (idempotent)

---

## Phase 7: User Story 5 — Reseed corrige commits ausentes (Priority: P3)

**Goal**: `post_save.py --reseed` sincroniza commits, corrigindo gaps quando o hook falhou.

**Independent Test**: Remover um commit do DB, rodar reseed, verificar que reaparece.

### Tests for User Story 5

- [x] T041 [P] [US5] Write test for reseed commit sync in `.specify/scripts/tests/test_post_save.py` — insert 3 commits, delete 1, run reseed, verify all 3 present again
- [x] T042 [P] [US5] Write test for reseed idempotency in `.specify/scripts/tests/test_post_save.py` — reseed with all commits present, verify no duplicates or errors

### Implementation for User Story 5

- [x] T043 [US5] Add `sync_commits(conn, platform_id)` function in `.specify/scripts/post_save.py` — runs `git log --format=%H%n%s%n%an%n%aI` + file detection, calls `insert_commit()` for each (INSERT OR IGNORE handles existing)
- [x] T044 [US5] Integrate `sync_commits()` into the `reseed(platform)` function in `.specify/scripts/post_save.py` — called after existing node seeding, reuses platform detection logic from hook
- [x] T045 [US5] Run tests from T041-T042 and verify all pass

**Checkpoint**: US5 complete — reseed is the safety net. Any missed commits are recovered automatically

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Integration validation, performance, and documentation

- [x] T046 [P] Verify hook performance — time execution of `hook_post_commit.py` on 3 sample commits, confirm <500ms (FR-017)
- [x] T047 [P] Add `install-hooks` instructions to repository README or Makefile help target
- [x] T048 Run `make ruff` and fix any linting issues in new files (hook_post_commit.py, backfill_commits.py)
- [x] T049 Run full test suite `make test` to verify no regressions
- [x] T050 Execute backfill against real repository and verify epic 001 has 21 commits linked (SC-003)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (migration must exist) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (DB functions must exist)
- **US2 (Phase 4)**: Depends on Phase 2 (needs `insert_commit()`) — can run parallel with US1
- **US3 (Phase 5)**: Depends on Phase 2 (needs query functions + JSON export) — can run parallel with US1/US2
- **US4 (Phase 6)**: Depends on Phase 2 (needs `insert_commit()`) — can run parallel with US1/US2/US3
- **US5 (Phase 7)**: Depends on Phase 4 (reuses platform/epic detection from hook) — sequential after US2
- **Polish (Phase 8)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: Independent after foundational — pure query layer
- **US2 (P1)**: Independent after foundational — pure capture layer
- **US3 (P2)**: Independent after foundational — consumes JSON export, not direct DB
- **US4 (P2)**: Independent after foundational — standalone backfill script
- **US5 (P3)**: Depends on US2 (reuses hook detection logic via shared module import)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD per constitution)
- DB functions before scripts that consume them
- Backend before portal frontend (US3 needs JSON first)

### Parallel Opportunities

- T003 + T004 (foundational tests) — different test groups, same file but independent
- T014 + T015 + T016 + T017 (US2 tests) — all independent test scenarios
- T026 + T027 (US3 JSON export + test) — parallel files
- T032 + T033 + T034 (US4 tests) — independent test scenarios
- T041 + T042 (US5 tests) — independent test scenarios
- **Across stories**: US1, US2, US3, US4 can all proceed in parallel after Phase 2

---

## Parallel Example: User Story 2

```bash
# Launch all US2 tests together (T014-T017):
Task: "Test platform detection in .specify/scripts/tests/test_hook_post_commit.py"
Task: "Test epic detection in .specify/scripts/tests/test_hook_post_commit.py"
Task: "Test multi-platform handling in .specify/scripts/tests/test_hook_post_commit.py"
Task: "Test error handling in .specify/scripts/tests/test_hook_post_commit.py"

# Then implement sequentially (T018-T024) — each function builds on previous
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (migration)
2. Complete Phase 2: Foundational (DB CRUD)
3. Complete Phase 3: US1 (query commits by epic)
4. Complete Phase 4: US2 (post-commit hook)
5. **STOP and VALIDATE**: Make a test commit, verify it appears in DB via `get_commits_by_epic()`
6. Core traceability is functional — commits are captured and queryable

### Incremental Delivery

1. Setup + Foundational → DB layer ready
2. Add US1 + US2 → Core traceability working (MVP!)
3. Add US4 (backfill) → Full history available
4. Add US3 (portal) → Visual interface for browsing
5. Add US5 (reseed) → Safety net for consistency
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US2 (hook) — critical path
   - Developer B: US4 (backfill) — independent script
   - Developer C: US3 (portal) — independent frontend
3. US5 (reseed) after US2 merges — reuses detection logic
4. US1 tests can run alongside any other story

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 50 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 7 |
| Phase 3 (US1 - Query) | 4 |
| Phase 4 (US2 - Hook) | 12 |
| Phase 5 (US3 - Portal) | 6 |
| Phase 6 (US4 - Backfill) | 9 |
| Phase 7 (US5 - Reseed) | 5 |
| Phase 8 (Polish) | 5 |
| Parallel opportunities | US1-US4 after Phase 2; multiple [P] tasks within each phase |
| Suggested MVP | Phases 1-4 (US1+US2): migration + DB + hook = core traceability |

---

## Key Files

| File | Action | LOC (est.) |
|------|--------|------------|
| `.pipeline/migrations/014_commits.sql` | Create | ~15 |
| `.specify/scripts/db_pipeline.py` | Extend | ~80 new |
| `.specify/scripts/hook_post_commit.py` | Create | ~150 |
| `.specify/scripts/backfill_commits.py` | Create | ~200 |
| `.specify/scripts/post_save.py` | Extend | ~50 new |
| `.specify/scripts/git-hooks/post-commit` | Create | ~5 |
| `.specify/scripts/tests/test_hook_post_commit.py` | Create | ~150 |
| `.specify/scripts/tests/test_backfill_commits.py` | Create | ~120 |
| `.specify/scripts/tests/test_db_pipeline.py` | Extend | ~60 new |
| `.specify/scripts/tests/test_post_save.py` | Extend | ~40 new |
| `portal/src/components/changes/ChangesTab.tsx` | Create | ~200 |
| `portal/src/pages/[platform]/control-panel.astro` | Extend | ~10 new |
| `portal/src/data/commits-status.json` | Create (generated) | N/A |
| `Makefile` | Extend | ~5 new |

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "50 tasks em 8 fases para commit traceability — migration, DB CRUD, post-commit hook, backfill retroativo, portal Changes tab, reseed integration. MVP = Fases 1-4 (US1+US2). Plan.md não foi preenchido pelo speckit.plan (ainda é template), mas pitch.md tem todas as decisões arquiteturais detalhadas. TDD obrigatório por constituição — todos os testes incluídos."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a decisão de usar SQLite para commits for revertida ou se o padrão de post-commit hook for considerado invasivo demais, a abordagem precisa ser revista."
