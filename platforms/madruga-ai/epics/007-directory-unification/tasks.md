# Tasks: Directory Unification

**Input**: Design documents from `/specs/003-directory-unification/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: Constitution requires TDD (Principle VII). Tests included for script changes and migration.

**Organization**: Tasks grouped by user story. Stories 1-3 (P1) can be implemented in any order after foundational phase. Stories 4-5 (P2) and 6-8 (P3) follow after.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Migrate legacy artifacts and prepare workspace

- [x] T001 Move `specs/001-atomic-skills-dag-pipeline/` to `platforms/madruga-ai/epics/005-atomic-skills-dag/` using `git mv`
- [x] T002 Move `specs/002-sqlite-foundation/` to `platforms/madruga-ai/epics/006-sqlite-foundation/` using `git mv`
- [x] T003 Verify `git log --follow` works for moved files (spot check 2-3 files)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Script infrastructure that enables all user stories

**CRITICAL**: No user story work can begin until `--base-dir` is functional

### Tests

- [x] T006 [P] Write test: `create-new-feature.sh --base-dir /tmp/test-epic` creates spec.md in custom dir — file `.specify/scripts/bash/tests/test_base_dir.sh`
- [x] T007 [P] Write test: `create-new-feature.sh` without `--base-dir` still creates in `specs/` — file `.specify/scripts/bash/tests/test_base_dir.sh`
- [x] T008 [P] Write test: `check-prerequisites.sh --json` with `SPECIFY_BASE_DIR` set resolves to custom dir — file `.specify/scripts/bash/tests/test_base_dir.sh`

### Implementation

- [x] T009 Add `SPECIFY_BASE_DIR` env var support to `find_feature_dir_by_prefix()` in `.specify/scripts/bash/common.sh` — when set, return `$SPECIFY_BASE_DIR` directly (skip prefix matching)
- [x] T010 Add `SPECIFY_BASE_DIR` env var support to `get_feature_paths()` in `.specify/scripts/bash/common.sh` — pass through to `find_feature_dir_by_prefix`
- [x] T011 Add `--base-dir <path>` flag parsing to `.specify/scripts/bash/create-new-feature.sh` — set `SPECS_DIR` to provided path, export `SPECIFY_BASE_DIR`
- [x] T012 [P] Add `--base-dir <path>` flag parsing to `.specify/scripts/bash/setup-plan.sh` — export `SPECIFY_BASE_DIR` before calling `get_feature_paths`
- [x] T013 [P] Add `--base-dir <path>` flag parsing to `.specify/scripts/bash/check-prerequisites.sh` — export `SPECIFY_BASE_DIR` before calling `get_feature_paths`
- [x] T014 Run tests T006-T008 and verify all pass

**Checkpoint**: `--base-dir` works. SpecKit can operate in any directory.

---

## Phase 3: User Story 3 — Skills Renamed (Priority: P1)

**Goal**: Rename 5 skills + delete 3 skills atomically. Zero references to old names.

**Independent Test**: `grep -rn "discuss\b\|adr-gen\|test-ai\|vision-one-pager\|folder-arch\|pipeline-status\|pipeline-next" .claude/ CLAUDE.md platforms/madruga-ai/platform.yaml .specify/templates/` returns zero results.

- [x] T015 [P] [US3] Rename `.claude/commands/madruga/vision-one-pager.md` → `vision.md` and update internal references (frontmatter name, usage examples, handoff refs)
- [x] T016 [P] [US3] Rename `.claude/commands/madruga/discuss.md` → `epic-context.md` and update internal references
- [x] T017 [P] [US3] Rename `.claude/commands/madruga/adr-gen.md` → `adr.md` and update internal references
- [x] T018 [P] [US3] Rename `.claude/commands/madruga/test-ai.md` → `qa.md` and update internal references
- [x] T019 [US3] Update all skill name references in `CLAUDE.md` — DAG table, per-epic cycle table, common commands, skill counts
- [x] T020 [US3] Update all skill name references in `.claude/knowledge/pipeline-dag-knowledge.md` — canonical DAG table (§1), handoff examples (§7), per-epic cycle table (§8)
- [x] T021 [US3] Update skill names in `platforms/madruga-ai/platform.yaml` — pipeline.nodes[].skill fields
- [x] T022 [US3] Update skill names in `.specify/templates/platform/template/platform.yaml.jinja` — pipeline.nodes[].skill fields
- [x] T023 [US3] Run validation grep to confirm zero references to old names (excluding git history, this tasks.md, and pitch/context docs)

**Checkpoint**: All skills use new names. Old names do not exist.

---

## Phase 4: User Story 6 — Folder-arch Merged into Blueprint (Priority: P3, but blocks DAG update)

**Goal**: Absorb folder-arch content into blueprint. DAG goes from 14→13 nodes.

**Independent Test**: `folder-arch.md` does not exist in `.claude/commands/madruga/`. Blueprint template has "Folder Structure" section. DAG has 13 nodes.

- [x] T024 [US6] Read current `platforms/madruga-ai/engineering/folder-structure.md` content
- [x] T025 [US6] Add "## Folder Structure" section to `.specify/templates/platform/template/engineering/blueprint.md.jinja` with content from T024
- [x] T026 [US6] Delete `.claude/commands/madruga/folder-arch.md` skill file
- [x] T027 [US6] Delete `.specify/templates/platform/template/engineering/folder-structure.md.jinja` template
- [x] T028 [US6] Remove `folder-arch` node from `platforms/madruga-ai/platform.yaml` pipeline.nodes and update `domain-model` depends (verify it already depends on `blueprint` not `folder-arch`)
- [x] T029 [US6] Remove `folder-arch` node from `.specify/templates/platform/template/platform.yaml.jinja`
- [x] T030 [US6] Update `.claude/knowledge/pipeline-dag-knowledge.md` — remove folder-arch row from canonical DAG (14→13 nodes), remove folder-arch handoff example
- [x] T031 [US6] Update `CLAUDE.md` — DAG table node count (14→13), remove folder-arch from DAG nodes table

**Checkpoint**: DAG has 13 nodes. folder-arch eliminated.

---

## Phase 5: User Story 1 — SpecKit in Epic Dir (Priority: P1)

**Goal**: Operator runs SpecKit commands and all artifacts land in `epics/<NNN>/`.

**Independent Test**: `create-new-feature.sh --base-dir platforms/prosauai/epics/001-test` creates `spec.md` in epic dir.

**Note**: This story depends on Phase 2 (`--base-dir` working) and Phase 3+4 (renamed skills, updated DAG).

- [x] T032 [US1] Update `speckit.specify.md` skill prompt instructions to set `SPECIFY_BASE_DIR=platforms/<name>/epics/<NNN>/` before invoking `create-new-feature.sh` when epic context is provided
- [x] T033 [P] [US1] Update `speckit.plan.md` skill prompt instructions to export `SPECIFY_BASE_DIR` env var before invoking `setup-plan.sh`
- [x] T034 [P] [US1] Update `speckit.tasks.md` skill prompt instructions to export `SPECIFY_BASE_DIR` env var before invoking `check-prerequisites.sh`
- [x] T035 [P] [US1] Update `speckit.clarify.md` skill prompt instructions to export `SPECIFY_BASE_DIR` env var for epic dir resolution
- [x] T036 [P] [US1] Update `speckit.implement.md` skill prompt instructions to export `SPECIFY_BASE_DIR` env var for epic dir resolution
- [x] T037 [P] [US1] Update `speckit.analyze.md` skill prompt instructions to export `SPECIFY_BASE_DIR` env var for epic dir resolution

**Checkpoint**: SpecKit operates within epic dir when invoked with epic context.

---

## Phase 6: User Story 8 — epic_cycle in Copier Template (Priority: P2)

**Goal**: New platforms scaffolded via Copier include `epic_cycle` section.

**Independent Test**: `copier copy .specify/templates/platform/ /tmp/test-platform/` generates `platform.yaml` with `epic_cycle.nodes` containing 10 nodes.

### Test

- [x] T038 [US8] Write pytest test: Copier-generated `platform.yaml` contains `epic_cycle.nodes` with 10 entries — file `.specify/templates/platform/tests/test_epic_cycle.py`

### Implementation

- [x] T039 [US8] Add `epic_cycle` section to `.specify/templates/platform/template/platform.yaml.jinja` with 10 nodes (epic-context, specify, clarify, plan, tasks, analyze, implement, verify, qa, reconcile)
- [x] T040 [US8] Add `epic_cycle` section to `platforms/madruga-ai/platform.yaml` (live manifest, same content)
- [x] T041 [US8] Run test T038 and verify pass
- [x] T042 [US8] Run `pytest .specify/templates/platform/tests/` to verify zero regression in existing template tests

**Checkpoint**: Copier template generates epic_cycle. Live manifest updated.

---

## Phase 7: User Story 4 — Epic Cycle in SQLite (Priority: P2)

**Goal**: `check-platform-prerequisites.sh --epic` queries epic cycle status from filesystem and SQLite.

**Independent Test**: `check-platform-prerequisites.sh --json --platform madruga-ai --epic 007-directory-unification --status` returns 10 nodes with statuses.

### Test

- [x] T043 [US4] Write test: `check-platform-prerequisites.sh --epic 007-directory-unification --status --json --platform madruga-ai` returns valid JSON with epic cycle nodes. Include edge case: query for non-existent epic returns all nodes as `pending` — file `.specify/scripts/bash/tests/test_epic_flag.sh`

### Implementation

- [x] T044 [US4] Add `--epic <NNN-slug>` flag parsing to `.specify/scripts/bash/check-platform-prerequisites.sh`
- [x] T045 [US4] Implement epic cycle node status checking: read `epic_cycle.nodes` from `platform.yaml`, check output file existence in `epics/<NNN>/`, determine ready/blocked/done status
- [x] T046 [US4] When `--use-db` is combined with `--epic`: query `epic_nodes` table via `db.py get_epic_nodes()` for enhanced status
- [x] T047 [US4] Run test T043 and verify pass

**Checkpoint**: `--epic` flag works. Epic cycle observable via CLI.

---

## Phase 8: User Story 5 — HANDOFF Blocks (Priority: P2)

**Goal**: Skills produce HANDOFF YAML in artifact footer. DAG knowledge has `handoff_template` per node.

**Independent Test**: Read any skill's output template section and verify HANDOFF block format is present.

- [x] T048 [US5] Add `handoff_template` field to each node in `.claude/knowledge/pipeline-dag-knowledge.md` §1 canonical DAG table (13 nodes)
- [x] T049 [US5] Update HANDOFF examples in `.claude/knowledge/pipeline-dag-knowledge.md` §7 to use new skill names and include `context` + `blockers` fields
- [x] T050 [P] [US5] Add HANDOFF block template to `epic-context.md` skill output section (from: epic-context, to: specify)
- [x] T051 [P] [US5] Add HANDOFF block template to `vision.md` skill output section (from: vision, to: solution-overview)
- [x] T052 [P] [US5] Add HANDOFF block template to `solution-overview.md` skill output section
- [x] T053 [P] [US5] Add HANDOFF block template to `business-process.md` skill output section
- [x] T054 [P] [US5] Add HANDOFF block template to `blueprint.md` skill output section
- [x] T055 [P] [US5] Add HANDOFF block template to `domain-model.md` skill output section
- [x] T056 [P] [US5] Add HANDOFF block template to `containers.md` skill output section
- [x] T057 [P] [US5] Add HANDOFF block template to `context-map.md` skill output section
- [x] T058 [P] [US5] Add HANDOFF block template to `roadmap.md` skill output section
- [x] T059 [P] [US5] Add HANDOFF block template to `verify.md` skill output section
- [x] T060 [P] [US5] Add HANDOFF block template to `reconcile.md` skill output section
- [x] T061 [P] [US5] Add HANDOFF block template to `adr.md` skill output section (1-way-door)
- [x] T062 [P] [US5] Add HANDOFF block template to `tech-research.md` skill output section (1-way-door)
- [x] T063 [P] [US5] Add HANDOFF block template to `epic-breakdown.md` skill output section (1-way-door)

**Checkpoint**: All skills with human/1-way-door gate produce HANDOFF blocks.

---

## Phase 9: User Story 2 — `/pipeline` Unified (Priority: P1)

**Goal**: Single `/pipeline` command shows L1 + L2 status with Mermaid diagram.

**Independent Test**: `/pipeline madruga-ai` outputs L1 table + L2 table per epic + Mermaid with colors.

- [x] T064 [US2] Create `.claude/commands/madruga/pipeline.md` skill — unified status + next recommendation
- [x] T065 [US2] Implement L1 section: read `check-platform-prerequisites.sh --status --json --use-db`, render table + Mermaid with color classes (done=green, pending=yellow, skipped=gray, blocked=red, stale=orange)
- [x] T066 [US2] Implement L2 section: for each epic from DB, query `epic_nodes`, render per-epic table + Mermaid
- [x] T067 [US2] Implement "next step" recommendation: find first ready node in L1 or L2, suggest command
- [x] T068 [US2] Delete `.claude/commands/madruga/pipeline-status.md`
- [x] T069 [US2] Delete `.claude/commands/madruga/pipeline-next.md`
- [x] T070 [US2] Update `CLAUDE.md` — replace `pipeline-status` and `pipeline-next` references with `/pipeline`, update utility skills table

**Checkpoint**: `/pipeline madruga-ai` shows complete two-level status.

---

## Phase 10: User Story 7 — Migrate specs/ Artifacts (Priority: P3)

**Goal**: `specs/` directory eliminated. All artifacts in `epics/`.

**Note**: This was partially done in Phase 1 (T001-T004). This phase handles any remaining cleanup.

- [x] T071 [US7] Move `specs/003-directory-unification/` to `platforms/madruga-ai/epics/007-directory-unification/`
- [x] T072 [US7] Delete `specs/` directory after all moves complete
- [x] T073 [US7] Verify `specs/` directory no longer exists
- [x] T074 [US7] Verify `git log --follow` (will show full history after commit)
- [x] T075 [US7] No internal links reference `specs/` paths (all already updated)

**Checkpoint**: `specs/` eliminated. Git history preserved.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation updates, regression testing

- [x] T076 [P] Run `grep -rn "discuss\b\|adr-gen\|test-ai\|vision-one-pager\|folder-arch\|pipeline-status\|pipeline-next" .claude/ CLAUDE.md platforms/madruga-ai/platform.yaml .specify/templates/` — zero results confirmed
- [x] T077 [P] Run `pytest .specify/templates/platform/tests/` — 15 passed, 2 skipped
- [x] T078 [P] Run existing pytest suite (`pytest`) — 24 passed
- [x] T079 [P] Run `python3 .specify/scripts/platform.py lint --all` — all platforms valid
- [x] T080 [P] Validate HANDOFF blocks: 14/14 skills have handoff blocks with from, to, context, blockers fields
- [x] T081 Update `.claude/knowledge/pipeline-dag-knowledge.md` §8 per-epic cycle table with new skill names and HANDOFF references
- [x] T082 Final review: all 7 success criteria met (SC-001 through SC-007)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup/Migration)     → no deps, start immediately
Phase 2 (Foundational)        → no deps on Phase 1 (can run in parallel)
Phase 3 (Rename Skills)       → after Phase 2 (needs common.sh stable)
Phase 4 (Merge folder-arch)   → after Phase 3 (rename commit first)
Phase 5 (SpecKit in epic dir) → after Phase 2 + Phase 3 (needs --base-dir + new names)
Phase 6 (Copier epic_cycle)   → after Phase 4 (needs 13-node DAG)
Phase 7 (SQLite --epic)       → after Phase 6 (needs epic_cycle in manifest)
Phase 8 (HANDOFF blocks)      → after Phase 3 (needs renamed skills)
Phase 9 (/pipeline unified)   → after Phase 7 + Phase 8 (needs SQLite L2 + HANDOFF)
Phase 10 (Cleanup)            → after Phase 1
Phase 11 (Polish)             → after all phases
```

### User Story Dependencies

- **US1 (SpecKit in epic dir)**: Depends on Phase 2 (--base-dir) + Phase 3 (renamed skills)
- **US2 (/pipeline unified)**: Depends on US4 (SQLite --epic) + US5 (HANDOFF)
- **US3 (Rename skills)**: After Phase 2 only
- **US4 (SQLite --epic)**: After US8 (epic_cycle in manifest)
- **US5 (HANDOFF blocks)**: After US3 (renamed skills)
- **US6 (folder-arch merge)**: After US3 (rename commit)
- **US7 (Migrate specs/)**: After Phase 1 (already moved)
- **US8 (Copier epic_cycle)**: After US6 (13-node DAG)

### Parallel Opportunities

- Phase 1 and Phase 2 can run in parallel
- T015-T018 (rename skills) can all run in parallel
- T032-T037 (SpecKit skill updates) can all run in parallel
- T050-T063 (HANDOFF blocks in skills) can all run in parallel
- T074-T077 (validation) can all run in parallel

---

## Implementation Strategy

### MVP First (US3 + US1 + US2)

1. Complete Phase 1 + 2 → Foundation ready
2. Complete Phase 3 (Rename) + Phase 4 (Merge) → Clean DAG
3. Complete Phase 5 (SpecKit in epic dir) → Core value delivered
4. **STOP and VALIDATE**: SpecKit works in epic dir
5. Continue to Phase 6-9 for full observability

### Incremental Delivery

1. Phases 1-2 → Infrastructure ready
2. Phase 3-4 → Clean naming + 13-node DAG
3. Phase 5 → SpecKit unified (MVP!)
4. Phase 6-7 → Epic cycle in manifest + SQLite
5. Phase 8 → HANDOFF blocks (context propagation)
6. Phase 9 → /pipeline unified (full observability)
7. Phase 10-11 → Cleanup + validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Constitution VII (TDD): tests T006-T008, T038, T043 written before implementation
- Total: 82 tasks across 11 phases
- Commit after each phase completion for clean git history
