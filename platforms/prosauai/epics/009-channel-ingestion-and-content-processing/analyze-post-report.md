# Specification Analysis Report — Epic 009 (Post-Implement)

**Epic**: Channel Ingestion Normalization + Content Processing
**Branch**: `epic/prosauai/009-channel-ingestion-and-content-processing`
**Date**: 2026-04-20
**Mode**: READ-ONLY post-implementation consistency audit (cross-checks spec/plan/tasks vs. shipped code in `paceautomations/prosauai`)
**Compared against**: pre-implement [analyze-report.md](./analyze-report.md) (12 findings) + 67 commits on the epic branch

---

## Executive summary

Implementation is materially complete: 67 commits on the epic branch, all three PRs (A/B/C) coded, tasks.md shows 164/164 boxes ticked (120 lower-case `[x]` + 44 upper-case `[X]`). However the auto-generated `implement-report.md` is a 1-line stub ("1/1 tasks completed (phase dispatch)") that does not enumerate dispatched tasks or surface failures, so post-implement audit relies on git log + filesystem inspection rather than the report.

Two **CRITICAL** post-implement findings emerge: (1) the SC-013 PR-C "diff zero in core" gate is **violated** by the trailing easter auto-commit (`b38efb0`), which touched 20 files inside `pipeline/`, `processors/`, and `core/router/` AFTER the PR-C Meta Cloud commits had landed — this exact failure mode is the kill-criterion declared in plan.md. (2) Three new public webhook routes were shipped without being declared in `platform.yaml::testing.urls`, so the deployment Smoke phase (T1103) cannot validate them.

Pre-implement findings status: I1 (frozen-ContentBlock vs. mutation) was resolved (mutation removed, see commits touching `result.py` + `content_process.py`); C1/C2 (image/document benchmarks) appear unaddressed in code; C3 (raw-bytes CI guard) shipped only as documentation; C4 (marker-in-trace assertion) partially addressed via integration tests but no dedicated assertion task.

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| **P1** | Inconsistency | **CRITICAL** | prosauai repo: `b38efb0` ("Auto-committed by easter after implement phase") vs. tasks.md T195 / spec SC-013 | `git diff b450ef5^..HEAD -- apps/api/prosauai/pipeline/ apps/api/prosauai/processors/ apps/api/prosauai/core/router/` returns 20 files / 61 insertions / 69 deletions. SC-013 explicitly requires PR-C diff to touch **zero** files in those paths — the gate test T195 would fail today. Most edits are polish (formatter, docstrings, small refactors) but the rule is binary. | Either (a) split the polish commit into a "PR-D polish" branch sequenced **before** PR-C re-application so the formal SC-013 boundary is restored; (b) re-baseline SC-013 to "no semantic change in pipeline/processors/router after Meta Cloud merge" and document the relaxation in ADR-035; or (c) revert the post-PR-C touches inside the three protected paths. Decide before tagging the epic shipped. |
| **P2** | Coverage Gap | **CRITICAL** | platforms/prosauai/platform.yaml `testing.urls` vs. shipped routes | Three new routes — `POST /webhook/evolution/{instance_name}`, `GET /webhook/meta_cloud/{tenant_slug}`, `POST /webhook/meta_cloud/{tenant_slug}` — are not declared in `platform.yaml::testing.urls`. The Smoke phase task T1103 (`qa_startup --validate-urls`) cannot exercise them, and FR-017 spirit (auto URL coverage) is bypassed. The legacy alias `/webhook/whatsapp/{instance_name}` is also undeclared but pre-existed. | Add the 3 routes to `testing.urls` with appropriate `expect_status` (401 for unauthenticated POST, 200/403 for the GET handshake). Alternative: classify them as "auth-gated, exclude from URL probe" and document the exclusion alongside `testing.urls`. |
| P3 | Inconsistency | HIGH | implement-report.md (3 lines) vs. tasks.md (164 ticked tasks) | The post-implement report contains only "1/1 tasks completed (phase dispatch)" with no enumeration, no failure list, no per-PR gate status. Audit must reverse-engineer state from git log. This breaks the documented contract that `implement-report.md` is the canonical record consumed by judge/qa/reconcile. | Have easter regenerate the report enumerating phases dispatched, tasks per phase, gates passed (SC-009, SC-010, SC-001, SC-002, SC-003, SC-013), and any skipped/deferred tasks. Until then, downstream phases must read the git log. |
| P4 | Coverage Gap | HIGH | spec.md SC-002 / SC-003 vs. implementation | Pre-implement finding C1 (image benchmark) and C2 (document benchmark) were marked HIGH in analyze-report.md. No `tests/benchmarks/test_image_e2e.py` or document equivalent appears in the commit history. SC-002 (image p95 < 9 s) and SC-003 (document p95 < 10 s) therefore remain unenforceable by automated gate. | Add the two benchmark scripts before the qa phase. Reuse T094 audio benchmark scaffolding. If deliberate skip, add Complexity-Tracking row to plan.md. |
| P5 | Underspecification | HIGH | spec.md FR-027 ("zero raw bytes persisted") vs. implementation | Pre-implement finding C3 demanded a CI/grep guard rejecting `open(..., "wb")` / `Path.write_bytes` inside `processors/`. The recipe was acknowledged in plan.md R4 mitigation but no Phase 10 task added it. Polish phase shipped `apps/api/docs/cost-projection.md` and `CHANGELOG.md` but no lint rule. | Add a pre-commit / ruff custom check OR a CI grep step. Cheap version: `! git grep -nE '(open\([^)]*"wb|Path\([^)]*\)\.write_bytes)' apps/api/prosauai/processors/`. |
| P6 | Inconsistency | HIGH | analyze-report.md A1 (path ambiguity) vs. shipped layout | Plan.md said `apps/api/prosauai/pipeline.py`; reality is package `apps/api/prosauai/pipeline/`. T195 (SC-013 gate) referenced `pipeline.py` literally. The git path actually used in P1 above had to be corrected to `pipeline/`. The gate script as written would silently pass on a non-existent path. | Update plan.md "Project Structure" + tasks.md T195 to use the package path. Re-run T195 with corrected glob. |
| P7 | Inconsistency | MEDIUM | spec.md FR-032 vs. implementation | FR-032 requires every fallback marker to land in `content_process.output.marker`. T064 (budget integration) and T093 (multi-message flush) were dispatched, but no commit message references an explicit marker assertion. Cannot tell from git log whether the assertion is present in the test bodies without diffing — analyze-report.md C4 had flagged this exact pattern. | Inspect `tests/integration/test_budget_exceeded_fallback.py`; if missing, add 1-line assertion `assert step.output["marker"] == "[budget_exceeded]"`. |
| P8 | Coverage Gap | MEDIUM | tasks.md Phase 11 (Smoke) vs. epic state | Smoke phase T1100–T1105 is marked complete in tasks.md, yet the implement-report does not mention startup execution or any health-check evidence. Without screenshots (T1104) or journey log (T1105) being committed, the "complete" check is unverifiable. | Require `easter-tracking.md` to embed the smoke evidence (qa_startup logs, screenshot paths, journey transcript) before flagging Smoke green. |
| P9 | Ambiguity | MEDIUM | analyze-report.md A2/A3 vs. spec.md FR-017/FR-023 | Pre-implement findings A2 (parse-first-then-swap reload semantics) and A3 (per-worker breaker state) recommended tightening spec wording. spec.md was not edited (305 lines unchanged). The behaviors are coded in T072/T078 but the spec still under-specifies them. | One-line edits to FR-017 and FR-023 capturing the implemented invariants. |
| P10 | Underspecification | LOW | tasks.md Phase 10 T217 vs. business/features.md | T217 added entries for the four new features. Need to confirm copy is in PT-BR and uses business-facing language (per skill rule). | Brief manual review; edit if needed. |
| P11 | Inconsistency | LOW | pitch.md "Captured Decisions" vs. decisions.md (D1 unresolved) | D1 from pre-implement persists: pitch and decisions.md still hold duplicate snapshots. Low risk because no edits applied during this epic. | Add the snapshot disclaimer to pitch (one line). |
| P12 | Underspecification | LOW | spec.md SC-016 (cost projection methodology) | Pre-implement U2 unaddressed in code (T220 produces a single cost-projection doc but spec still lacks methodology formula). | One-line edit to SC-016. |

**Total**: 12 post-implement findings (2 CRITICAL, 4 HIGH, 4 MEDIUM, 2 LOW). 6 are direct carryovers from pre-implement analyze; 4 are new (P1, P2, P3, P8); 2 are reframings.

---

## Pre-implement findings — resolution status

| ID | Description | Status |
|----|-------------|--------|
| I1 | Frozen ContentBlock vs. mutation in T104 | **Resolved** — `processors/result.py` + `pipeline/steps/content_process.py` adopted sidecar approach (no longer mutates `block.text`). |
| C1 | Missing image perf benchmark (SC-002) | **Open** → P4 |
| C2 | Missing document perf benchmark (SC-003) | **Open** → P4 |
| C3 | No CI guard for FR-027 (raw bytes) | **Open** → P5 |
| C4 | Marker not asserted in trace (FR-032) | **Open** → P7 (downgraded to MEDIUM, integration tests partially cover) |
| A1 | Pipeline path ambiguity (file vs. package) | **Open** → P6 |
| A2 | Reload semantics underspecified | **Open** → P9 |
| A3 | Per-worker breaker state | **Open** → P9 |
| U1 | PII class enumeration missing | **Open** (no edit) — low risk; defer |
| U2 | SC-016 methodology missing | **Open** → P12 |
| D1 | Pitch/decisions duplication | **Open** → P11 |
| I2 | ADR-036 reservation drift | **Open** (no impact) |

**Score**: 1/12 resolved (8%). The remaining items either persisted into post-implement (5/12 carryover) or were defensible deferrals (6/12 low-impact). The two new CRITICALs (P1, P2) overshadow the carryover backlog.

---

## URL Coverage Check (FR-017 spirit, deployment Smoke)

Detected new FastAPI routes vs. `platform.yaml::testing.urls`:

| Route | Method | Declared in testing.urls? |
|-------|--------|---------------------------|
| `/webhook/evolution/{instance_name}` | POST | **No** — see P2 |
| `/webhook/meta_cloud/{tenant_slug}` | GET | **No** — see P2 |
| `/webhook/meta_cloud/{tenant_slug}` | POST | **No** — see P2 |
| `/webhook/whatsapp/{instance_name}` (legacy alias) | POST | No (pre-existing, out of scope) |
| `/api/admin/performance/media-cost` | GET | No (admin-gated, low Smoke value) |
| `/api/admin/traces/{trace_id}/media-analysis/{step_id}` | GET | No (admin-gated, low Smoke value) |

Framework: FastAPI (recognized).

---

## Coverage Summary (FR → Implementation)

Of the 32 FRs, FR coverage by tasks remained at **96.9 %** (data unchanged from pre-implement). Implementation coverage by commit message inspection:

- 30/32 FRs have a corresponding commit on the branch.
- FR-027 (no raw bytes) — code path exists in `audio.py` / `image.py` (download-to-memory only) but no automated guard enforces invariant (P5).
- FR-032 (marker in trace) — implemented in pipeline step but assertion gap (P7).

SC summary unchanged from pre-implement except that SC-013 (P1) is now **failing**, not "covered by T195 gate".

---

## Constitution Alignment Issues

None new. P1 (SC-013 violation) is a self-imposed gate, not a constitutional principle.

---

## Unmapped Tasks / Tasks Done Without Evidence

- All 164 tasks ticked, but Smoke phase evidence missing (P8).
- Implement-report does not enumerate per-task status; cannot detect silent skips (P3).

---

## Metrics

- **Total Functional Requirements**: 32
- **Total Success Criteria**: 16
- **Total User Stories**: 7
- **Total Tasks**: 164 (120 lower-case `[x]` + 44 upper-case `[X]`)
- **Branch commits since develop**: 67
- **Pre-implement findings carried over**: 11/12
- **New post-implement findings**: 4
- **Critical Issues**: 2 (P1, P2)
- **High Issues**: 4 (P3, P4, P5, P6)
- **Medium Issues**: 4 (P7, P8, P9, P10)
- **Low Issues**: 2 (P11, P12)
- **SC gates failing today**: 1 (SC-013 via P1) + 2 unenforceable (SC-002, SC-003 via P4)

---

## Next Actions

### Must resolve before `/madruga:judge` (blocks PR-C merge)

1. **P1 (CRITICAL)** — Decide on SC-013: split commit, revert, or re-baseline+ADR. Without action, Meta Cloud adapter promise (decision D21, pitch §Suggested Approach) is broken on paper.
2. **P2 (CRITICAL)** — Add 3 webhook routes to `testing.urls` so Smoke phase can validate them. Mandatory for deployment confidence.

### Should resolve before `/madruga:qa`

3. **P3** — Regenerate `implement-report.md` with per-phase, per-task, per-gate evidence.
4. **P4** — Add image + document benchmark scripts.
5. **P5** — Add raw-bytes CI guard.
6. **P6** — Update plan.md + T195 to package path; re-execute T195.
7. **P7** — Verify or add marker assertion in `test_budget_exceeded_fallback.py`.
8. **P8** — Embed Smoke evidence in `easter-tracking.md`.

### Nice-to-have (acceptable before reconcile)

9. **P9, P10, P11, P12** — Spec/doc cleanup; one-line edits.

### Suggested commands

- For P1: `git rebase -i b450ef5^` and reorder/squash polish into PR-A/PR-B; or `git revert b38efb0 -- apps/api/prosauai/pipeline/ apps/api/prosauai/processors/ apps/api/prosauai/core/router/` then re-apply selectively.
- For P2: edit `platforms/prosauai/platform.yaml` adding the 3 routes; re-run `python3 .specify/scripts/qa_startup.py --validate-urls --platform prosauai`.
- For P4–P7: scoped edits to tasks.md + new test files; no full re-plan needed.
- Re-run `/speckit.analyze` after P1/P2 fixes.

---

## Remediation Offer

Concrete edits available on request for:
- `platform.yaml` (P2 — add 3 routes).
- `plan.md` "Project Structure" + `tasks.md` T195 (P6 — package path).
- `tests/benchmarks/test_image_e2e.py` + `test_document_e2e.py` skeletons (P4).
- `.github/workflows` or `pre-commit` raw-bytes guard (P5).

No edits applied yet.

---

handoff:
  from: speckit.analyze
  to: madruga:judge
  context: "Post-implement audit on a complete branch (67 commits, 164/164 tasks). Two CRITICAL findings: SC-013 PR-C zero-core-diff gate is currently failing (20 files touched in pipeline/processors/router by trailing polish commit b38efb0), and 3 new webhook routes are not declared in platform.yaml::testing.urls. 11 of 12 pre-implement findings persisted; only I1 (frozen ContentBlock) resolved. implement-report.md is a 3-line stub — judge/qa must read git log directly. Recommend fixing P1+P2 before judge."
  blockers:
    - "P1: SC-013 violated by post-PR-C polish commit b38efb0."
    - "P2: 3 new webhook routes missing from platform.yaml testing.urls."
  confidence: Alta
  kill_criteria: "Report invalidated if epic branch is rebased / commits are squashed (changes diff baselines), or if implement-report.md is regenerated with materially different task counts."
