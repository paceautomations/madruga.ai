---
title: "Tasks — Epic 008: Quality & DX"
updated: 2026-03-29
---
# Tasks — Quality & Developer Experience

## Phase 1: Knowledge Files

- [x] T001 Create `pipeline-contract-base.md` in `.claude/knowledge/` with steps 0,1,3,4,5, tiered auto-review (3 tiers), gate behavior, save+report with BD integration, HANDOFF format
- [x] T002 [P] Create `pipeline-contract-business.md` in `.claude/knowledge/` with behavioral persona directive for business layer
- [x] T003 [P] Create `pipeline-contract-engineering.md` in `.claude/knowledge/` with behavioral persona directive for engineering layer
- [x] T004 [P] Create `pipeline-contract-planning.md` in `.claude/knowledge/` with behavioral persona directive for planning layer
- [x] T005 Create `likec4-syntax.md` in `.claude/knowledge/` with LikeC4 specification syntax, views syntax, common errors, repo conventions (≥50 lines)
- [x] T006 Update `pipeline-dag-knowledge.md` §4 — replace decorative persona labels with behavioral directives

## Phase 2: Refactor Skills — Business Layer

- [x] T007 Refactor `vision.md` — add contract reference, remove inline steps 0,3,4,5
- [x] T008 [P] Refactor `solution-overview.md` — add contract reference, remove inline steps 0,3,4,5
- [x] T009 [P] Refactor `business-process.md` — add contract reference, remove inline steps 0,3,4,5
- [x] T010 [P] Refactor `platform-new.md` — add contract reference, remove inline steps 0,3,4,5

## Phase 3: Refactor Skills — Research Layer

- [x] T011 Refactor `tech-research.md` — add contract reference (base only), remove inline steps 0,3,4,5
- [x] T012 [P] Refactor `codebase-map.md` — add contract reference (base only), remove inline steps 0,3,4,5

## Phase 4: Refactor Skills — Engineering Layer

- [x] T013 Refactor `adr.md` — add contract reference, remove inline steps 0,3,4,5
- [x] T014 [P] Refactor `blueprint.md` — add contract reference, remove inline steps 0,3,4,5
- [x] T015 [P] Refactor `domain-model.md` — add contract reference, remove inline steps 0,3,4,5, add `likec4 build` validation instruction
- [x] T016 [P] Refactor `containers.md` — add contract reference, remove inline steps 0,3,4,5, add `likec4 build` validation instruction
- [x] T017 [P] Refactor `context-map.md` — add contract reference, remove inline steps 0,3,4,5

## Phase 5: Refactor Skills — Planning Layer

- [x] T018 Refactor `epic-breakdown.md` — add contract reference, remove inline steps 0,3,4,5
- [x] T019 [P] Refactor `roadmap.md` — add contract reference, remove inline steps 0,3,4,5

## Phase 6: Refactor Skills — Utility + Epic Cycle

- [x] T020 Refactor `epic-context.md` — add partial contract reference (steps 0,5 only)
- [x] T021 [P] Refactor `verify.md` — add partial contract reference (steps 0,5 only)
- [x] T022 [P] Refactor `reconcile.md` — add partial contract reference (steps 0,5 only)
- [x] T023 [P] Refactor `qa.md` — add partial contract reference (steps 0,5 only), keep custom auto-review
- [x] T024 [P] Refactor `pipeline.md` — add partial contract reference (step 0 only)
- [x] T025 [P] Refactor `checkpoint.md` — add partial contract reference (step 0 only)

## Phase 7: Validate

- [x] T026 Run `wc -l` on all skills — result: avg 179 (18% reduction from 219). qa.md (407) is outlier with fully custom flow. Excluding qa: avg 167 (24%)
- [x] T027 Grep validation — all 13 DAG skills reference `pipeline-contract-base.md`
- [x] T028 Grep validation — zero inline "### 0. Prerequisites" sections remain in refactored skills
- [x] T029 Verify `domain-model.md` and `containers.md` mention `likec4 build`
- [x] T030 Verify `pipeline-dag-knowledge.md` §4 has behavioral directives (no "Senior", "Specialist")

## Dependencies

```
T001 → T007-T025 (contract-base must exist before skills reference it)
T002-T004 → T007-T019 (layer contracts before layer skill refactors)
T005 → T015,T016 (likec4-syntax before domain-model/containers)
T006 → independent (can parallel with T001-T005)
T007-T025 → T026-T030 (all refactors before validation)
```
