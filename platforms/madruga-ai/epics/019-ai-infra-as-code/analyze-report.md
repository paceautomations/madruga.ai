# Specification Analysis Report

**Epic**: 019-ai-infra-as-code  
**Platform**: madruga-ai  
**Date**: 2026-04-04  
**Artifacts analyzed**: spec.md, plan.md, tasks.md, research.md, data-model.md  
**Constitution**: `.specify/memory/constitution.md` v1.1.0

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Constitution | HIGH | tasks.md Phase 2 (T001→T002) | **TDD ordering violation**: T001 implements `build_knowledge_graph()` before T002 writes the test. Constitution Principle VII mandates "Write tests before implementation — No exceptions." Phases 3 and 7 correctly follow TDD; Phase 2 does not. | Swap T001/T002 ordering: write `test_build_knowledge_graph` first (Red), then implement `build_knowledge_graph()` (Green). |
| F1 | Inconsistency | MEDIUM | research.md R5 vs plan.md T14 vs tasks.md T013-T014 | **`all-pipeline` scope mismatch**: research.md R5 says `all-pipeline` resolves to `pipeline.nodes[].id` (L1 only). Plan and tasks say `pipeline.nodes[].id` AND `pipeline.epic_cycle.nodes[].id` (L1 + L2). Since `pipeline-contract-base.md` is consumed by L2 skills (judge, qa, reconcile, epic-context), the plan/tasks interpretation is correct — research is incomplete. | Update research.md R5 to say L1 + L2. No code change needed (plan/tasks are already correct). |
| F2 | Inconsistency | LOW | plan.md "Project Structure" | Plan says test file `.specify/scripts/tests/test_skill_lint.py` is "CREATE or MODIFY" — but no such file exists (verified via Glob). It should be CREATE only. | Minor wording fix. No impact on implementation. |
| U1 | Underspecification | LOW | spec.md SC-004, tasks.md | **SC-004 ("CI ai-infra job < 60 seconds") has no enforcement task**. No task measures or validates this performance target. The job is simple enough that it will likely meet the target, but it's unstated. | Add a note to T024 (quickstart verification) to time the ai-infra job after first CI run. Or accept as an implicit outcome. |
| U2 | Underspecification | LOW | tasks.md T008 | **Security scan regex scope for `.specify/scripts/` only**. If a dangerous pattern (e.g., `eval()`) appears in a future Python file outside `.specify/scripts/`, the scan won't catch it. The spec (FR-002) says "CI MUST scan all PRs" but the regex scope is limited. | Acceptable for current codebase (all Python is in `.specify/scripts/`). Document the scope limitation. If Python files appear elsewhere later, expand the scan path. |
| U3 | Underspecification | LOW | skill-lint.py:38, tasks.md T016 | **`judge` skill not classified in skill-lint.py**. `SPECIALIST_SKILLS = {"qa"}` excludes `judge`. `get_archetype("judge")` returns "unknown". T016 declares `judge-config.yaml` with consumer `[judge]`. Impact analysis for `judge-config.yaml` will show archetype "unknown". | Out of scope for this epic (pre-existing). Note for future: add `judge` to `SPECIALIST_SKILLS` or create a separate classification set. Does not block implementation. |

---

## Coverage Summary

### Functional Requirements → Tasks

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 (CODEOWNERS review) | Yes | T007 | + manual GitHub settings step |
| FR-002 (dangerous patterns scan) | Yes | T008 | grep-based regex |
| FR-003 (secrets scan) | Yes | T008 | .env + API key patterns |
| FR-004 (--impact-of flag) | Yes | T001, T005, T006 | Core function + CLI integration |
| FR-005 (skill name + archetype) | Yes | T005 | Table output in cmd_impact_of |
| FR-006 (CI skill-lint + impact) | Yes | T009 | Conditional ai-infra job |
| FR-007 (CI skip on no AI changes) | Yes | T009 | git diff detection step |
| FR-008 (platform.yaml knowledge:) | Yes | T016 | 8 knowledge file entries |
| FR-009 (validate declared files) | Yes | T014 | WARNING severity |
| FR-010 (warn undeclared refs) | Yes | T014 | Cross-check vs knowledge graph |
| FR-011 (all-pipeline resolution) | Yes | T014 | Dynamic from pipeline + epic_cycle nodes |
| FR-012 (SECURITY.md) | Yes | T018 | ~150-200 lines |
| FR-013 (CONTRIBUTING.md) | Yes | T019 | ~80 lines |
| FR-014 (PR template) | Yes | T020 | ~25 lines |
| FR-015 (doc-change matrix) | Yes | T021 | CLAUDE.md section |
| FR-016 (Copier template) | Yes | T017 | Optional knowledge: section |

### Success Criteria → Tasks

| Criterion | Has Task? | Task IDs | Notes |
|-----------|-----------|----------|-------|
| SC-001 (code owner approval) | Yes | T007 | Manual verification post-merge |
| SC-002 (CI blocks patterns) | Yes | T008 | Integration test via CI |
| SC-003 (impact analysis correct) | Yes | T001-T004 | Unit tests verify known graph |
| SC-004 (CI < 60 seconds) | Partial | T009 | No explicit timing verification task |
| SC-005 (GitHub recognizes docs) | Yes | T018-T020 | Manual verification post-merge |
| SC-006 (make test + make ruff) | Yes | T022, T023 | Phase 10 polish |

### User Stories → Tasks

| Story | Tasks | Coverage |
|-------|-------|----------|
| US1 (CODEOWNERS) | T007 | Complete |
| US2 (Security scan) | T008 | Complete |
| US3 (Impact analysis) | T001-T006 | Complete |
| US4 (CI gate) | T009 | Complete |
| US5 (Knowledge declarations) | T010-T017 | Complete |
| US6 (Governance docs) | T018-T020 | Complete |
| US7 (Doc-change matrix) | T021 | Complete |

### Edge Cases → Coverage

| Edge Case | Addressed? | How |
|-----------|-----------|-----|
| Indirect/alias knowledge refs | Yes | Documented limitation (regex-only detection) |
| `all-pipeline` resolution | Yes | T013, T014 (dynamic resolution) |
| Security scan false positives | Yes | Regex tuned for assignment patterns |
| CI on branch with no .claude/ changes | Yes | T009 (detect step + conditional skip) |

### Unmapped Tasks

| Task | Purpose | Acceptable? |
|------|---------|-------------|
| T022 | `make test` validation | Yes — cross-cutting quality gate |
| T023 | `make ruff` validation | Yes — cross-cutting quality gate |
| T024 | Quickstart verification | Yes — manual acceptance check |
| T025 | DB artifact registration | Yes — standard pipeline bookkeeping |

---

## Constitution Alignment

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism | PASS | Simple regex over SAST, file creation over automation |
| II. Automate Repetitive | PASS | CI automates previously manual checks |
| III. Structured Knowledge | PASS | Knowledge declarations make deps explicit |
| IV. Fast Action | PASS | 9 logical tasks, 2w appetite |
| V. Alternatives | PASS | research.md documents alternatives for all 6 decisions |
| VI. Brutal Honesty | PASS | Pitch inaccuracies corrected in research.md |
| **VII. TDD** | **FAIL** | Phase 2: T001 (implement) before T002 (test). See finding C1. |
| VIII. Collaborative Decision | PASS | Straightforward decisions, no ambiguity |
| IX. Observability | N/A | No runtime code; CI logs suffice. Acceptable. |

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 16 |
| Total Success Criteria | 6 |
| Total Tasks | 25 |
| FR Coverage % | **100%** (16/16 with ≥1 task) |
| SC Coverage % | **83%** (5/6 fully covered; SC-004 partial) |
| User Story Coverage % | **100%** (7/7) |
| Edge Case Coverage % | **100%** (4/4) |
| Ambiguity Count | 0 |
| Duplication Count | 0 |
| Critical Issues | 0 |
| High Issues | 1 (C1 — TDD ordering) |
| Medium Issues | 1 (F1 — all-pipeline scope) |
| Low Issues | 4 (F2, U1, U2, U3) |
| **Total Findings** | **6** |

---

## Next Actions

1. **Before `/speckit.implement`**: Fix finding **C1** (HIGH) — swap T001/T002 ordering in tasks.md so the test is written before the implementation. This is a constitution requirement (Principle VII, TDD).

2. **Optional improvements** (LOW/MEDIUM, can proceed without):
   - **F1**: Update research.md R5 to clarify `all-pipeline` = L1 + L2 (documentation alignment only).
   - **U3**: Future task — add `judge` to `SPECIALIST_SKILLS` in skill-lint.py (out of scope for this epic).

3. **No CRITICAL issues found**. The artifacts are well-aligned with strong traceability across all three files. The dependency graph in tasks.md correctly reflects plan.md ordering. Research corrections (pitch inaccuracies) are properly propagated to implementation tasks.

**Verdict**: Ready for implementation after fixing C1 (TDD ordering in Phase 2).

---

*Generated by `/speckit.analyze` — read-only analysis, no files modified.*
