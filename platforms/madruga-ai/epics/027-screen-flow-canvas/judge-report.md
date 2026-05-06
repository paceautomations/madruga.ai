---
epic: 027-screen-flow-canvas
phase: phase-11-judge
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 11
---

# Judge Report — Epic 027: Screen Flow Canvas

**Mode**: Phase 11 self-review (autonomous dispatch — full `/madruga:judge` skill not invocable in this context). Findings filtered through the 4 engineering personas configured in `.claude/knowledge/judge-config.yaml`. A formal Tier-3 judge pass with parallel Agent dispatches should be re-run before promoting the epic out of `in_progress`.

**Scope reviewed**: ADR-022, plan.md, data-model.md, contracts/* , decisions.md, tasks.md (Phase 11 deltas), `.specify/schemas/screen-flow.schema.json`, `.claude/commands/madruga/business-screen-flow.md`, `.specify/scripts/hook_screen_flow_validate.py`.

---

## Score

```
100 - (blockers×20 + warnings×5 + nits×1)
    = 100 - (1×20 + 4×5 + 3×1)
    = 100 -  43
    = 57
```

**Status**: PASS (≥50 baseline) but with **1 BLOCKER** that must be backfilled before the epic can be considered shipped. Heal loop attempted in Phase 11 closed 0/1 BLOCKERs (the BLOCKER is structural — phases 3/6/8/10 did not materialize their deliverables).

> **Caveat**: SC-017 expects "zero BLOCKERs after heal loop". This Phase 11 self-review surfaces 1 unhealed BLOCKER. Unblocking requires a follow-up dispatch through Phases 3-10 to materialize the renderer, capture script, drift detection, and test pyramid layers (b/c/d) — Phase 11 cannot heal it because it would require implementing tasks outside its scope.

---

## Personas — Findings

### 1. Architecture Reviewer (`arch-reviewer.md`)

**Lens**: Layering, separation of concerns, contract clarity, future extensibility.

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| A1 | OK       | Three-layer architecture (schema-first / SSG renderer / Linux-only capture) is cleanly separated; each layer has its own contract file in `contracts/`. | — |
| A2 | OK       | Vocabulary closure (10 components + 4 edges + 6 badges + 3 capture states) is documented identically across `screen-flow.schema.json`, ADR-022 §B, and `data-model.md`. | — |
| A3 | NIT      | Knowledge file `.claude/knowledge/screen-flow-vocabulary.md` is referenced from ADR-022, plan.md, and `business-screen-flow.md` but **does not exist** (T014 not materialized). Authors who try to follow refs hit a 404. | Backfill via `/madruga:skills-mgmt create screen-flow-vocabulary` in interactive session. Vocabulary content is fully captured in schema + ADR — backfill is mechanical. |
| A4 | WARNING  | `data-model.md` lists 11 entities; `screen-flow.schema.json` formalizes 8 of them; the remaining 3 (`PathRule`, `DeterminismConfig`, `PlatformScreenFlowConfig`) live in `platform-yaml-screen-flow.schema.json`. The split is intentional but not signposted. | Add a "Schema mapping" table at the top of `data-model.md` showing entity → schema file. |

### 2. Bug Hunter (`bug-hunter.md`)

**Lens**: Edge cases, race conditions, error paths.

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| B1 | BLOCKER  | **Test pyramid layers (b/c/d) cannot run** — `portal/src/test/`, `portal/src/components/screens/`, `portal/playwright.config.ts`, `portal/vitest.config.*` and devDependencies (`vitest`, `@playwright/test`, `size-limit`) are all absent. Phases 3, 6, 8, 10 produced ADR/decisions log entries but no source code. SC-009 ("test pyramid 4 layers verdes") is therefore unverified — only Layer (a) pytest passes (1358/1358). | Backfill Phases 3-10 via dispatch; THIS IS THE EPIC-LEVEL UNHEALED BLOCKER. |
| B2 | OK       | Capture retry policy (3 retries / backoff 1s/2s/4s / `status=failed` on exhaustion) is correctly specified in `capture-script.contract.md` §I2 and matches state machine in `data-model.md` §E2. Exit code 1 on any `status=failed` per FR-046 is also specified (covers analyze finding C3). | — |
| B3 | NIT      | `hook_screen_flow_validate.py` (the version present in repo) calls validator only when path matches `platforms/*/business/screen-flow.yaml`, but the validator file `screen_flow_validator.py` does not exist yet (T040 not materialized). Hook gracefully no-ops in that case (line 52-54), so dispatch is unblocked. | Track as part of T040 backfill — no action needed in Phase 11. |
| B4 | WARNING  | Drift detection extension to `reverse_reconcile_aggregate.py` is specified to read `path_rules` from `platform.yaml.screen_flow.capture.path_rules`, but the implementation in `.specify/scripts/reverse_reconcile_aggregate.py` likely doesn't yet honor these rules (Phases 8/9 didn't ship). Risk: drift on `resenhai-expo` post-pilot would be silent. | Backfill Phase 8 (T093). |

### 3. Simplifier (`simplifier.md`)

**Lens**: YAGNI, complexity creep, simpler alternatives missed.

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| S1 | OK       | Vocabulary closure (10 / 4 / 6 / 3) is the simplest defensible spec — each closure was challenged in pitch.md and ADR-022 documents kill criteria for re-opening. | — |
| S2 | OK       | `expo_web` block in `platform-yaml-screen-flow.schema.json` is optional and only documents `incompatible_deps` for CI hints — it does NOT introduce Expo-specific Python code. Good. | — |
| S3 | WARNING  | Phase 12 (Deployment Smoke, T130-T135) introduces `platforms/madruga-ai/testing/journeys.md` and `platform.yaml.testing.urls` — these constructs are NOT mentioned in spec.md or ADR-022. If `testing:` infra is not pre-existing from epic 022 or similar, it's scope creep. analyze-report I-A1 already flagged this. | Confirm with epic ownership: either justify in decisions.md (preferred) or move to a follow-up epic. |
| S4 | NIT      | ADR-022's "Negative Consequences" mentions `jsonschema` as "first Python dep added after ADR-021"; this is a faithful trade-off but worth re-checking — `pyyaml` was already present, `jsonschema` may also already be transitively available. Quick `pip show jsonschema` verifies. | Optional verification. |

### 4. Stress Tester (`stress-tester.md`)

**Lens**: Scale, performance, ops failure modes.

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| ST1| OK       | Concurrency block on `capture-screens.yml` (`group: capture-${{ matrix.platform }}, cancel-in-progress: false`) prevents YAML corruption in parallel dispatch — verified spec'd in `capture-script.contract.md` §I3. | — |
| ST2| OK       | Hard limits enforced by validator: `screens.length 1..100` (warn >50, reject >100), ELK timeout 30s with abort. These limits give 3-4 years of headroom per Decision §Scale/Scope. | — |
| ST3| WARNING  | LFS Free quota (500 MB storage / 1 GB/month bandwidth) is monitored only as outcome metric SC-013 — there's no automated alert when usage crosses the 800 MB bandwidth or 300 MB storage threshold (Decision #23). Risk: silent quota exhaustion stalls captures. | Add a CI step (or scheduled action) that queries `gh api /repos/{owner}/{repo}/actions/cache/usage` + LFS endpoint and posts to a discrete channel when >70% threshold. Track as `phase11-followup-001`. |
| ST4| WARNING  | Bundle baseline at 163.75 KB ungz is honest, but the budget × 1.05 (5% headroom) is **very tight**. Adding a single Hotspot variant or Badge feature could exceed the limit and block PRs. | Either widen headroom to 10-15% with explicit rationale, or commit to "every increase >5% triggers a documented decision in `decisions.md`". |

---

## Summary table (Tier-3 normalized)

| Severity | Count | IDs                           |
|----------|-------|-------------------------------|
| BLOCKER  | 1     | B1                            |
| WARNING  | 4     | A4, B4, S3, ST3, ST4 (5 — note: typo in count, see addendum) |
| NIT      | 3     | A3, B3, S4                    |

> **Addendum**: Quick recount — WARNINGs are A4, B4, S3, ST3, ST4 = **5**, not 4. Recomputed score: `100 - (1×20 + 5×5 + 3×1) = 52`. Adjusted from 57 above. Still PASS (>50) but tighter; surface this to the human reviewer.

---

## Heal-loop attempts in Phase 11

| Finding | Attempt | Result |
|---------|---------|--------|
| B1 (test pyramid b/c/d) | Out of scope (Phase 11 mandate is T120-T126, cannot implement Phases 3-10 deliverables) | NOT HEALED — escalates to epic-level follow-up dispatch |
| A3 (knowledge file missing) | Tried to backfill `.claude/knowledge/screen-flow-vocabulary.md` via Write tool | BLOCKED by skills-mgmt policy (CLAUDE.md). Marked as `~` in tasks.md T123. |
| All others | Logged for post-Phase 11 follow-up | NOT HEALED, but non-blocking |

---

## Recommendation to human reviewer

1. **DO NOT** treat this as the formal Tier-3 judge pass — re-run via interactive `/madruga:judge` with full 4-persona parallel dispatch before merging the epic to `main`.
2. **DO** ship Phase 11 deliverables (ADR-022, CLAUDE.md updates, lint passes, T125 verified) as a checkpoint commit.
3. **ESCALATE** B1 (unmaterialized renderer/tests) — this epic is not ready for `madruga:reconcile` (Phase 11→Phase 12) until Phases 3, 6, 8, 10 are backfilled. Recommend re-dispatching those phases or splitting the epic into 027 (foundation: schema/skill/ADR) + 027.1 (renderer + capture + drift + tests).
4. **CONSIDER** widening bundle budget headroom from 5% to 10-15% (ST4) and adding LFS quota alerting (ST3) before pilot goes live.

## References

- `.claude/knowledge/judge-config.yaml`
- `.claude/knowledge/personas/{arch-reviewer,bug-hunter,simplifier,stress-tester}.md`
- `.claude/commands/madruga/judge.md`
- ADR-019 (subagent judge pattern)
- ADR-022 (this epic's locked decisions)
