# Specification Analysis Report — 022-mermaid-migration

**Date**: 2026-04-05 | **Artifacts**: spec.md (179L), plan.md (405L), tasks.md (280L)
**Skill**: speckit.analyze (pre-implementation)

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Underspecification | HIGH | spec.md:L152, tasks.md:L80-81 | SC-001 says "22 arquivos .likec4" but actual count is 16 (8 per platform). The `model/` directories also contain `dist/` (55MB + 39MB, 178 built files), `.gitignore`, `likec4.json`, `likec4.config.json`, and `output/` — none of which are `.likec4` files but all must be deleted. Tasks T031/T032 say "8 files" ignoring these. | Fix SC-001 count to 16 `.likec4` files. Update T031/T032 descriptions to say "entire `model/` directory including dist/ (55MB+39MB), config, and build output" — not just "8 files". |
| B1 | Ambiguity | MEDIUM | plan.md:L139 | Plan says "Enhance existing deploy topology diagram OR add separate 'Containers' section" for Madruga-AI — indeterminate. During implementation, the executor won't know which option to pick. | Choose one option explicitly. Recommend: add separate "Containers" section (consistent with Fulano approach). |
| C1 | Coverage Gap | HIGH | spec.md:L168, plan.md:L108 | Spec assumption says "Todas as plataformas existentes tem os documentos hospedeiros (process.md)" — but Fulano does NOT have `business/process.md`. Plan correctly identifies this (research finding #7) and task T023 creates it, but the spec assumption is factually wrong. | Update spec.md assumption to: "Fulano does not have `business/process.md` — it will be created during conversion." |
| C2 | Coverage Gap | MEDIUM | plan.md:L155-159, tasks.md | Plan specifies handling `platforms/fulano/engineering/context-map.md` (Option A: cross-reference to domain-model.md). No task in tasks.md covers updating this file. Task T021 adds context map to domain-model.md but never touches context-map.md itself. | Add task: "Update `platforms/fulano/engineering/context-map.md` with cross-reference to domain-model.md Context Map section" after T021. |
| C3 | Coverage Gap | MEDIUM | plan.md:L236-240, tasks.md:L35 | Plan specifies removing `head` scripts (`svg-pan-zoom.min.js`, `mermaid-interactive.js`) from `astro.config.mjs` (lines 149-150). Task T005 covers LikeC4VitePlugin and esbuild removal but does NOT mention these head scripts. | Add to T005 description: "also remove `svg-pan-zoom.min.js` and `mermaid-interactive.js` from `head[]` array (lines 149-150)". |
| C4 | Coverage Gap | MEDIUM | plan.md:L250-251, tasks.md:L45 | Plan specifies updating `PipelineDAG.tsx` to remove `.likec4` replacement logic (line 115 confirmed in source). Task T015 only mentions `constants.ts`. No task covers `PipelineDAG.tsx`. | Add to T015 or create new task: "Remove `.replace(/\.likec4$/, '')` from `portal/src/components/dashboard/PipelineDAG.tsx` line 115." |
| C5 | Coverage Gap | MEDIUM | plan.md:L282, tasks.md | Plan says to update/remove `register` subcommand in `platform_cli.py` (which injects LikeC4 loaders and validates LikeC4 model via `npx likec4 build`). No task covers this — tasks only handle platform.yaml and REQUIRED_DIRS. | Add task in Phase 5: "Update `platform_cli.py`: remove `_inject_platform_loader()` call in `cmd_register()`, remove `npx likec4 build` validation (lines 358-386), remove `CANONICAL_SPEC` ref (line 44)." |
| D1 | Inconsistency | LOW | plan.md:L316-377, tasks.md:L18-158 | Plan has 5 phases (Fase 1-5). Tasks has 8 phases (Phase 1-8). Phase numbering and naming differ. E.g., plan "Fase 1: Portal Cleanup" = tasks "Phase 2: Foundational". Causes confusion during handoff. | Not blocking. Add a mapping table in tasks.md header: Plan Phase → Tasks Phase. |
| D2 | Inconsistency | LOW | plan.md:L57, tasks.md:L80-81 | Plan says "~28 files removed" but does not count `model/dist/` (178 built files, 94MB). T031/T032 only mention "8 files". | Update to say "~28 source files + dist/ build artifacts (~94MB)" or just "entire model/ directories". |
| F1 | Inconsistency | MEDIUM | tasks.md:L151, plan.md | Task T049 references `.claude/rules/portal.md` — says "Delete or update to remove LikeC4 references". This file is NOT mentioned in spec.md or plan.md at all. Verified: file exists and likely has LikeC4 refs. | Good catch by tasks.md. Add `.claude/rules/portal.md` to the plan's MODIFY list. |
| G1 | Coverage Gap | LOW | spec.md:L98-101 | US6 acceptance scenario says "skills impactados nao referenciam .likec4 como output" — but no task greps `.claude/commands/` for `.likec4` references. T052 only greps portal source. | Add verification: `grep -r ".likec4" .claude/commands/ --include="*.md"` to Phase 8. |
| H1 | Underspecification | LOW | plan.md:L178-180 | Plan says "Check if madruga-ai needs business flow conversion (process.md)" — vague. Madruga-AI has `business/process.md` but no task verifies if it already has Mermaid business flow or needs conversion. | Add verification sub-step in Phase 3 Madruga-AI section. |

---

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (remove .likec4 files) | Yes | T031, T032 | Covered but file count inaccurate (A1) |
| FR-002 (remove portal LikeC4 components) | Yes | T005, T006, T007 | |
| FR-003 (remove 5 .astro pages) | Yes | T008-T012 | |
| FR-004 (convert to Mermaid inline) | Yes | T019-T030 | |
| FR-005 (nomenclature consistency) | Yes | T056 | Verification only |
| FR-006 (cross-references) | Yes | T024, T030 | |
| FR-007 (simplify sidebar) | Yes | T014, T033-T034 | |
| FR-008 (remove platform.yaml blocks) | Yes | T035, T036 | |
| FR-009 (update Copier template) | Yes | T037 | |
| FR-010 (remove vision-build.py) | Yes | T038 | |
| FR-011 (remove CI likec4 job) | Yes | T047 | |
| FR-012 (create ADR-020) | Yes | T039 | |
| FR-013 (supersede ADR-001) | Yes | T040 | |
| FR-014 (update ADR-003) | Yes | T041 | |
| FR-015 (update pipeline-dag-knowledge) | Yes | T042 | |
| FR-016 (update CLAUDE.md files) | Yes | T043, T044, T045 | |
| FR-017 (remove likec4.md rule) | Yes | T046 | |
| FR-018 (build/test/lint pass) | Yes | T018, T053-T055 | Multiple verification points |
| FR-019 (preserve all arch info) | Partial | T019-T030 | No explicit audit comparing .likec4 content vs Mermaid output |

---

## Constitution Alignment Issues

No CRITICAL constitution violations found. The epic is well-aligned with all 9 principles:

- **Principle I (Pragmatism)**: Core motivation — removing unnecessary complexity.
- **Principle VII (TDD)**: Spec notes "Test tasks omitted — validation via build/lint/test." This is acceptable for a deletion/migration epic (no new code requiring unit tests). Build validation serves as the safety net.

---

## Unmapped Tasks

| Task | Mapped to Requirement? | Notes |
|------|----------------------|-------|
| T001-T004 (read/inventory) | Infrastructure | Setup tasks, no direct FR mapping — OK |
| T049 (.claude/rules/portal.md) | FR-002 (partially) | Not in spec/plan but valid cleanup (F1) |
| T050 (verify buildViewPaths removal) | FR-002 | Verification of T013 |
| T056 (nomenclature verification) | FR-005 | Verification only |

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 19 |
| Total Tasks | 56 |
| Coverage % (FRs with >= 1 task) | **100%** (19/19) |
| Ambiguity Count | 2 (B1, H1) |
| Duplication Count | 0 |
| Critical Issues Count | **0** |
| High Issues Count | **2** (A1, C1) |
| Medium Issues Count | **6** (B1, C2, C3, C4, C5, F1) |
| Low Issues Count | **4** (D1, D2, G1, H1) |

---

## Next Actions

**No CRITICAL issues found.** The artifacts are well-structured and consistent for a simplification epic.

### Recommended before `/speckit.implement`:

1. **Fix A1** (HIGH): Update SC-001 count from 22 to 16 `.likec4` files. Update T031/T032 to mention `dist/` directories (94MB of build artifacts).
2. **Fix C1** (HIGH): Correct spec assumption about Fulano `process.md` existence.
3. **Fix C2-C5** (MEDIUM): Add missing tasks for `context-map.md` update, `head` scripts removal, `PipelineDAG.tsx` update, and `platform_cli.py` `register` command cleanup.
4. **Fix F1** (MEDIUM): Add `.claude/rules/portal.md` to plan's file inventory.

### Safe to proceed if:

- The 2 HIGH findings are addressed (factual corrections + task completeness).
- The 6 MEDIUM findings are at least acknowledged (they won't block implementation but may cause rework).
- The 4 LOW findings can be deferred (cosmetic/documentation consistency).

### Suggested commands:

- Proceed to `/speckit.implement madruga-ai` and address findings inline during execution (pragmatic approach given the simplification nature of this epic).
- Or: refine tasks.md first to add the ~4 missing tasks (C2-C5), then implement.

---

## Remediation Offer

Would you like me to suggest concrete remediation edits for the top 8 issues (2 HIGH + 6 MEDIUM)? I will NOT apply edits automatically — only provide the specific changes for your approval.

---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Pre-implementation analysis complete. 0 CRITICAL, 2 HIGH (incorrect file counts in SC-001, wrong assumption about Fulano process.md), 6 MEDIUM (missing tasks for context-map.md, head scripts, PipelineDAG.tsx, platform_cli register, portal.md rule). 100% FR coverage. Safe to proceed after addressing HIGH findings."
  blockers: []
  confidence: Alta
  kill_criteria: "If the missing tasks (C2-C5) cause implementation to silently skip important cleanup, leaving LikeC4 remnants in the codebase."
