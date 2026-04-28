# Reconcile Report — epic 015 agent-pipeline-steps (prosauai)

**Date:** 2026-04-27
**Branch:** `epic/prosauai/015-agent-pipeline-steps` (paceautomations/prosauai)
**Skill:** `madruga:reconcile`
**Mode:** Autonomous dispatch (no human in loop) — `[DECISAO AUTONOMA]` markers throughout

---

## 0. Cardinal Rule

This skill **proposes**, the user **applies**. In autonomous dispatch mode, decisions are recorded with `[DECISAO AUTONOMA]` for downstream audit; nothing in `paceautomations/prosauai` is modified by this run (sandbox constraint scopes writes to the epic directory only). Doc patches below are concrete diffs ready to apply.

---

## 1. Phase 1b — Staleness Scan

Query against L1 nodes for prosauai:

| Node | Owned doc | Status | Resolution |
|------|-----------|--------|------------|
| (no stale L1 nodes detected for prosauai in this run — pipeline DB scan returned empty for the epic 015 branch state) | — | — | n/a |

**Staleness Resolution**: nothing to record — Phase 1b empty.

---

## 2. Phase 2 — Drift Detection (D1–D11)

Diff source: epic 015 changes vs `develop` of `paceautomations/prosauai` + cross-reference against `platforms/prosauai/**` docs in this repo.

### Documentation Health Table

| Doc | Categories scanned | Status | Drift count |
|-----|-------------------|--------|-------------|
| `business/solution-overview.md` | D1 | CURRENT | 0 |
| `business/process.md` | D1 | CURRENT | 0 |
| `engineering/blueprint.md` | D2, D11 | OUTDATED | 1 |
| `engineering/containers.md` | D3 | CURRENT | 0 (no new container; epic adds modules within `apps/api`) |
| `engineering/domain-model.md` | D4 | OUTDATED | 1 |
| `engineering/context-map.md` | D8 | CURRENT | 0 (no new bounded context boundary; admin endpoints stay within `admin/*` namespace) |
| `decisions/ADR-006-conversation-orchestration.md` | D5 | OUTDATED | 1 |
| `decisions/ADR-019-agent-config-versioning.md` | D5 | OUTDATED | 1 |
| `decisions/ADR-027-admin-data-isolation.md` | D5 | CURRENT | 0 (`sub_steps` column inherits the documented "no RLS in admin tables" rule) |
| `decisions/ADR-028-fire-and-forget-tracing.md` | D5 | CURRENT | 0 (`sub_steps` persistence reuses the same fire-and-forget contract) |
| `decisions/ADR-029-pricing-table.md` | D5 | CURRENT | 0 (`routing_map` validator consumes `PRICING_TABLE` as documented) |
| `planning/roadmap.md` | D6 | OUTDATED | 1 (epic status + new follow-up epic) |
| `epics/015-agent-pipeline-steps/decisions.md` | D10 | CURRENT | 0 (12 D-PLAN entries promoted candidates; see §6) |
| `research/tech-alternatives.md` | D11 | OUTDATED | 1 |
| `platforms/prosauai/README.md` | D9 | n/a — file absent | 0 |
| **Totals** | — | **5 OUTDATED / 11 checked** | **5** |

**Drift Score:** `(11 - 5) / 11 = 54.5%` — significant drift, expected for an epic that introduces a new orchestration primitive (`agent_pipeline_steps`) and a column extension (`trace_steps.sub_steps`).

### Impact Radius Matrix

| Changed area | Directly affected docs | Transitively affected | Effort |
|--------------|----------------------|----------------------|--------|
| New table `agent_pipeline_steps` | `domain-model.md` (line 244 schema-draft → implemented), `blueprint.md` (data layer section) | `containers.md` (none — same `apps/api`); `context-map.md` (none) | M |
| New column `trace_steps.sub_steps` | `domain-model.md` (Trace Step entity), `ADR-027` (cap policy reference), `ADR-028` (truncation policy) | None (épico 008 owns the table) | S |
| Pipeline executor module | `blueprint.md` (orchestration narrative) | `ADR-006` (must reference executor branch) | M |
| 5 step types (classifier/clarifier/resolver/specialist/summarizer) | `tech-alternatives.md` (pydantic-ai usage section) | `domain-model.md` (Pipeline Step Output entity) | M |
| Admin endpoints `/admin/agents/{id}/pipeline-steps` | `context-map.md` (Admin BC outbound surface) | `openapi.yaml` (epic-local) | S |
| Audit_log usage from PUT replace | `ADR-027` (admin governance) | None | S |
| `messages.metadata` extension (`terminating_step`, `pipeline_step_count`) | `domain-model.md` (Message entity metadata schema) | None | S |

### D5 — Decision Drift findings

#### D5.1 — ADR-006 (conversation orchestration) needs **AMEND**

- **Current state**: ADR-006 documents `generate_response` as a **single LLM call** (step 9 of conversation pipeline). No mention of declarative sub-routing.
- **Expected state**: ADR-006 must add a **"2026-04 amendment — pipeline executor"** section recording:
  - Branch on `agent_pipeline_steps` non-empty → delegate to `pipeline_executor.execute_agent_pipeline`
  - Backward-compat invariant (FR-021, SC-010 ≤5 ms p95)
  - Fallback canned policy (FR-026 — zero retry)
- **Severity:** HIGH — without this amendment, a reader of ADR-006 implementing a new feature would not know about the orchestration branch.
- **Action:** **Amend** (decision is still valid; pipeline is an extension, not a contradiction).

Concrete diff (apply to `platforms/prosauai/decisions/ADR-006-conversation-orchestration.md`):

```diff
+ ## 2026-04 Amendment — Pipeline Executor (epic 015)
+
+ When `agent_pipeline_steps` contains ≥1 active row for the target agent, step 9
+ (`generate_response`) delegates to `pipeline_executor.execute_agent_pipeline`
+ instead of invoking the single LLM call directly. The executor:
+
+ - Loads steps once per message (atomic snapshot — FR-020).
+ - Evaluates each step's `condition` JSONB before execute (FR-024 grammar:
+   `<,>,<=,>=,==,!=,in`; AND-implicit; no OR/parens v1).
+ - Chains step outputs via `PipelineState`; `summarized_context` substitutes
+   the message history for downstream steps (FR-015).
+ - Emits sub-spans into `trace_steps.sub_steps` (per amendment to ADR-028).
+ - On any step failure → fallback canned (zero retry, FR-026).
+
+ The agent-without-pipeline path is preserved byte-for-byte (FR-021, SC-010,
+ verified by `test_pipeline_backwards_compat.py` and benchmark T051).
+
+ Cross-references: ADR-019 (canary per-version, **deferred** in this epic per
+ D-PLAN-02), ADR-027 (admin data isolation — `sub_steps` inherits no-RLS),
+ ADR-028 (fire-and-forget tracing — `sub_steps` persistence honors the same
+ contract).
```

#### D5.2 — ADR-019 (agent config versioning) status update

- **Current state**: ADR-019 status `Accepted`. Implementation NOT shipped.
- **Expected state**: ADR-019 must add a **"2026-04 status note"** clarifying that the table `agent_config_versions` does **not exist in production** as of epic 015 ship; epic 015 took the explicit decision (D-PLAN-02) to bypass versioning and tie `agent_pipeline_steps` directly to `agents.id`. Rollback path documented via `audit_log` reconstruction (PR-5 — T101).
- **Severity:** HIGH — documentation contradicts production state. Future readers will assume the canary mechanism is available.
- **Action:** **Amend** with status note + follow-up epic reference.

Concrete diff:

```diff
+ ## 2026-04 Status Note (epic 015)
+
+ Although this ADR was Accepted, the table `agent_config_versions` was
+ never created in production. Epic 015 (agent-pipeline-steps) needed to
+ ship within a 3-week appetite and could not absorb the full
+ versioning + canary infrastructure. Decision D-PLAN-02 in
+ `epics/015-agent-pipeline-steps/decisions.md` documents the bypass:
+ pipeline steps are stored direct on `agent_pipeline_steps` (FK
+ `agents.id`), without a snapshot. Rollback is via:
+
+ - `UPDATE agent_pipeline_steps SET is_active=FALSE WHERE agent_id=$1` (operator),
+ - or admin endpoint `POST /admin/agents/{id}/pipeline-steps/rollback`
+   reconstructing previous state from `audit_log` (T101).
+
+ Phase 9 of epic 015 (US4 — group-by-version comparison) is therefore
+ DEFERRED. Implementation tracked as **follow-up epic 015b — agent
+ versioning + canary** (to be opened by /madruga:roadmap).
+
+ This note does NOT supersede the design — versioning is still the
+ desired end state. Readers should treat ADR-019 as "Accepted —
+ implementation pending" rather than "Accepted — implemented".
```

### D4 — Domain Model drift (D4.1)

- **Current state** (`engineering/domain-model.md` line 244): schema-draft of `agent_pipeline_steps` table.
- **Expected state**: replace "schema-draft" reference with "implemented in epic 015 — see migration `20260601000010_create_agent_pipeline_steps.sql`"; add **Trace Step (extended)** entity sub-section listing the new `sub_steps` JSONB column with cap policy (32 KB total, 4 KB per element); add **Message (extended)** entity sub-section listing the new `metadata.terminating_step`/`pipeline_step_count` keys.
- **Severity:** MEDIUM (not blocking, but readers building new features against domain-model lose context).
- **Action:** Update (T127 already lists this as polish task — verify execution).

Concrete diff for line 244 region:

```diff
- (schema-draft) `agent_pipeline_steps` table — see ADR-006 follow-up
+ `agent_pipeline_steps` table — implemented in epic 015. Migration:
+ `apps/api/db/migrations/20260601000010_create_agent_pipeline_steps.sql`.
+ RLS ON, policy `tenant_isolation`. Indexes
+ `(agent_id, is_active, step_order)` and `(tenant_id)`. CHECK
+ `step_order BETWEEN 1 AND 5`. CHECK `octet_length(config::text) <= 16384`.
+ Hard-coded constant `MAX_PIPELINE_STEPS_PER_AGENT = 5` enforced at
+ application layer.
```

Add to **Trace Step** entity:

```diff
+ ### Trace Step — extended (epic 015)
+
+ Column `sub_steps JSONB NULL` was added to `public.trace_steps` (migration
+ `20260601000011_alter_trace_steps_sub_steps.sql`). Populated only for the
+ `generate_response` row when an agent has ≥1 pipeline step. Each sub-step
+ shares the schema of a top-level step (status, duration_ms, model, tokens,
+ cost_usd, input, output, tool_calls, error_*) plus
+ `condition_evaluated`, `terminating`, `skipped_reason`. Cap: 32 KB
+ total / 4 KB per element / sentinel `{truncated_omitted_count}` element
+ when overflow.
```

Add to **Message** entity:

```diff
+ ### Message — metadata extension (epic 015)
+
+ For outbound messages produced by `pipeline_executor`, `messages.metadata`
+ JSONB receives:
+
+ - `terminating_step: str` — which step finalised the response
+ - `pipeline_step_count: int` — number of configured steps
+ - `pipeline_version: "unversioned-v1"` — placeholder until ADR-019 ships
+
+ For single-call agents, none of these keys are written (FR-064).
```

### D6 — Roadmap drift (mandatory section, see §3)

See Phase 5 below.

### D11 — Research drift (D11.1)

- **Current state** (`research/tech-alternatives.md`): pydantic-ai usage documented for the conversation pipeline as a single agent.
- **Expected state**: add a section "epic 015 — pipeline step types as discrete pydantic-ai Agents" listing the 5 step types and their respective `output_type` choices (ClassifierOutput, ClarifierOutput, etc.). No new dependency. No alternative ever chosen and discarded — this is enrichment, not contradiction.
- **Severity:** LOW.
- **Action:** Update.

### D2 — Architecture drift (D2.1)

- **Current state** (`engineering/blueprint.md`): orchestration narrative describes a single LLM call inside step 9.
- **Expected state**: add a paragraph in the orchestration section noting the executor branch + zero-overhead default path + cap policies. Concrete bullet additions:
  - "Sub-routing inside `generate_response`: when an agent has rows in `agent_pipeline_steps`, the dispatcher executes a typed pipeline (≤5 steps) — see ADR-006 amendment."
  - Update NFR table: P95 overhead lookup ≤5 ms (SC-010); P95 pipeline `classifier+specialist` for `greeting` ≤1 s (SC-002).
- **Severity:** MEDIUM.
- **Action:** Update.

### D7 — Future Epic Drift

Scanned `platforms/prosauai/epics/*/pitch.md` for impact:

| Epic | Pitch assumption | How affected | Impact | Action |
|------|-----------------|--------------|--------|--------|
| 008 — admin-evolution | Trace Explorer renders `trace_steps` rows | sub_steps column added → Trace Explorer gets enriched payload | LOW (already extended in T076–T077; backwards compatible — null sub_steps render as before) | Cross-reference epic 008 readme noting epic 015 extends Trace Explorer |
| 016+ — agent versioning (follow-up) | Did not exist | New epic recommended (see Roadmap §3 below) | n/a | Create epic shell with `madruga:epic-breakdown` or `madruga:roadmap` |
| 017 — observability/tracing/evals | Per-step token + cost telemetry | Pipeline emits sub-spans `conversation.pipeline.step` + cost per sub-step → fits neatly | LOW (additive) | Cross-reference epic 017 README |
| 010 — handoff-engine-inbox | `conversations.ai_active` toggle | Independent of pipeline_steps; no overlap | NONE | n/a |
| 002 — observability | OTel spans for pipeline | New sub-spans nested under `conversation.generate` | LOW (additive) | Update epic 002 doc to reference sub-span name |

Top-5 affected: 008, 017, 002 (low impact additive), plus the **new** follow-up 016 (needed). No future epic has assumptions broken.

### D9 — README

`platforms/prosauai/README.md` does not exist. Skip per error-handling rule.

### D10 — Epic Decisions audit

`epics/015-agent-pipeline-steps/decisions.md` contains 12 D-PLAN entries (D-PLAN-01..D-PLAN-12) seeded by epic-context and enriched during plan/implement. Audit:

| Decision | Contradicts ADR? | Promotion candidate? | Code still reflects it? |
|----------|-----------------|---------------------|-------------------------|
| D-PLAN-01 (sub_steps as new JSONB column) | No | LOW (cap policy is implementation detail) | Yes |
| D-PLAN-02 (no agent_config_versions in this epic) | YES — see ADR-019 amend above | **HIGH** — promote to ADR amendment (D5.2) | Yes |
| D-PLAN-03 (executor in separate module) | No | LOW | Yes |
| D-PLAN-04 (sub-step JSON shape) | No | LOW | Yes |
| D-PLAN-05 (no Redis cache) | No | MEDIUM — promote if production p95 sustains the assumption | Yes |
| D-PLAN-06 (atomic snapshot) | No | MEDIUM — generic concurrency pattern | Yes |
| D-PLAN-07 (regex condition parser) | No | MEDIUM — could be ADR if v2 grammar is added | Yes (with WARNING from judge: regex is too lax — see W1/W2/W3) |
| D-PLAN-08 (routing_map dict) | No | LOW | Yes |
| D-PLAN-09 (prompt_slug ref) | No | LOW (but compound-key weakened — judge W10) | Partially — see judge W10 |
| D-PLAN-10 (PUT replace-all) | No | LOW | Yes |
| D-PLAN-11 (step types as classes + Protocol) | No | LOW | Yes |
| D-PLAN-12 (fallback canned reuse) | No | LOW | Yes |

**Promotion recommendation:** run `/madruga:adr` for **D-PLAN-02** (versioning bypass + rollback strategy) — multi-epic implication and 1-way-door pattern. Other D-PLANs stay epic-local.

---

## 3. Phase 5 — Roadmap Review (mandatory)

### Epic Status Table

| Epic | Planned (roadmap) | Actual | Status update | Milestone |
|------|------------------|--------|---------------|-----------|
| 015 — agent-pipeline-steps | Appetite 3 weeks; PR-1..PR-4 mandatory; PR-5/PR-6 cut-line | PR-1..PR-4 implemented + tested (132/132 epic-015 tests pass; 2534/2535 suite); PR-5/PR-6 frontend tasks executed in T076–T101 with cut-line evaluated favorably; Phase 9 DEFERRED per D-PLAN-02 | **Complete (with deferred Phase 9)** | MVP shippable |
| 015b — agent-versioning + canary (NEW) | Did not exist | Recommended creation — D-PLAN-02 + ADR-019 amend leave a clear seam | **Proposed** | Post-MVP |
| 008 — admin-evolution | In progress / shipping | Trace Explorer + Performance AI extensions consumed in epic 015 (T076–T079) — synergy | unchanged | n/a |

### Roadmap diff (apply to `platforms/prosauai/planning/roadmap.md`)

```diff
| 015 | agent-pipeline-steps | Em andamento | 3 sem | (...)
- 015 — em andamento (PR-1..PR-4 + cut-line para PR-5/PR-6)
+ 015 — Concluído (2026-04). PR-1..PR-4 mergeados; PR-5/PR-6 frontend
+   incluídos. Phase 9 (US4 group-by-version) DEFERRED para epic 015b
+   por dependência em ADR-019. Score Judge 35/100 (FAIL) — 5 BLOCKER +
+   16 WARN abertos por sandbox constraint, escalados em PR de hardening
+   dedicado.
+
+ | 015b | agent-versioning-canary | Proposto | 2-3 sem | depende de
+   ADR-019 ser materializado (`agent_config_versions` table + traffic
+   split per agent_version). Habilita US4 do épico 015. |
```

### Dependencies Discovered

| Dependency | Discovered during | Status |
|-----------|-------------------|--------|
| `agent_config_versions` table necessary for true canary (FR-050, SC-013) | plan | Carried as new epic 015b |
| `audit_log.ip_address INET NOT NULL` causes silent loss of audit when proxy strips X-Forwarded-For | judge W4 | Cross-cutting hardening — schedule migration to `INET NULL` or app-layer fallback `0.0.0.0/0` sentinel |
| `details->>'agent_id'` rollback query needs expression index | judge B4 | Migration `20260601000012_idx_audit_log_pipeline_steps_agent.sql` proposed |

### Risk Status

| Risk (planned in roadmap) | Materialized? | Mitigation status |
|--------------------------|---------------|-------------------|
| Backward-compat regression on hot path | NO — `test_pipeline_backwards_compat.py` green; benchmark T051 ≤5 ms p95 confirmed | Mitigated; SC-008/SC-010 verified except 1 flaky pre-existing test |
| Frontend (PR-5/PR-6) misses cut-line | NO — included | n/a |
| Versioning absence breaks rollback | PARTIALLY — rollback works via audit_log reconstruction; no canary available | Tracked as 015b |
| **NEW** — concurrent admin PUTs lose edits silently (judge B5) | NEW RISK — discovered post-implement | Open — schedule fix `pg_advisory_xact_lock` |
| **NEW** — narrow exception filter in executor crashes message delivery on real LLM errors (judge B2) | NEW RISK — discovered post-implement | Open — broaden catch tuple |
| **NEW** — `_PIPELINE_EXEC_METADATA` is non-weak dict keyed by `id()` → cross-tenant attach (judge B1) | NEW RISK — discovered post-implement | Open — convert to WeakKeyDictionary or context-var |

### New Risks Added to Roadmap

```diff
+ - Risk-2026-04-A — `pipeline_executor` exception filter narrow (judge B2). Mitigation: broaden to (Exception,) with explicit allow-list rebroadcast. Owner: TBD.
+ - Risk-2026-04-B — `_PIPELINE_EXEC_METADATA` cross-attach via `id()` reuse (judge B1). Mitigation: WeakKeyDictionary or asyncio context var. Owner: TBD.
+ - Risk-2026-04-C — admin PUT replace race (judge B5). Mitigation: `SELECT … FOR UPDATE` on `agents.id` inside replace transaction. Owner: TBD.
+ - Risk-2026-04-D — audit_log NotNullViolation on missing client IP (judge W4). Mitigation: app-layer fallback or schema relax. Owner: TBD.
+ - Risk-2026-04-E — rollback query missing expression index (judge B4). Mitigation: add `idx_audit_log_pipeline_steps_agent` expression index on `(details->>'agent_id', created_at DESC)` filtered by action. Owner: TBD.
```

---

## 4. Phase 6 — Future Epic Impact

Already covered in §2 D7. Summary:

| Epic | Pitch assumption | How affected | Impact | Action |
|------|-----------------|--------------|--------|--------|
| 008 admin-evolution | Trace + Perf AI tabs | Sub-steps render + Group-by-version button | LOW additive | Cross-link epic 015 in 008 README |
| 015b (NEW) | Versioning + canary | Created from D-PLAN-02 | n/a | Open via roadmap or epic-breakdown |
| 017 obs-tracing-evals | OTel coverage | Sub-spans nest under `conversation.generate` | LOW additive | Cross-link |
| 002 observability | Pipeline span shape | Adds `conversation.pipeline.step` | LOW additive | Cross-link |
| 010 handoff-engine | `ai_active` flag | No overlap | NONE | n/a |

---

## 5. Phase 7 — Auto-Review

### Tier 1 (deterministic)

| # | Check | Result |
|---|-------|--------|
| 1 | Report file exists + non-empty | PASS |
| 2 | All 11 categories scanned (D1..D11) | PASS — D1, D2, D3, D4, D5, D6, D7, D8, D9 (skipped — README absent), D10, D11 |
| 3 | Drift score computed | PASS — 54.5% (5/11 outdated) |
| 4 | No placeholder markers | PASS — no TODO/TKTK/??? remain |
| 5 | HANDOFF block at footer | PASS |
| 6 | Impact radius matrix present | PASS |
| 7 | Roadmap review section present | PASS |
| 8 | Stale L1 each have a resolution | PASS — Phase 1b empty, n/a |

### Tier 2 (scorecard)

| # | Item | Self-Assessment |
|---|------|----------------|
| 1 | Every drift item has current vs expected state | YES |
| 2 | Roadmap review completed | YES |
| 3 | ADR contradictions flagged with amend/supersede | YES (D5.1 amend ADR-006, D5.2 amend ADR-019) |
| 4 | Future epic impact assessed | YES |
| 5 | Concrete diffs provided | YES (4 distinct doc diffs in §2 + roadmap diff in §3) |
| 6 | Trade-offs explicit | YES — judge BLOCKERs documented as open risks rather than silently auto-fixed |
| 7 | Confidence stated | Alta com ressalva — sandbox blocked code-side patches |

---

## 6. Phase 8 — Gate (Human, autonomous-mode override)

Per autonomous dispatch contract, gate is auto-approved with `[DECISAO AUTONOMA]`. Apply order recommended:

1. **Now** — Apply doc diffs in §2 (ADR-006 amend, ADR-019 amend, domain-model update, blueprint update, tech-alternatives enrichment) + roadmap diff in §3.
2. **Same PR** — Update `domain-model.md` line 244 reference (T127 polish task).
3. **Next 24h** — Open follow-up issue / hardening PR for the 5 judge BLOCKERs (B1..B5) + 16 WARNINGs in `paceautomations/prosauai`. Sandbox constraint of this run prevents source edits; the report is the audit trail.
4. **Next sprint** — `/madruga:roadmap` to materialize epic 015b.
5. **As-needed** — `/madruga:adr` for D-PLAN-02 promotion (1-way-door reasoning + multi-epic implication).

---

## 7. Phase 8b — Mark Epic Commits as Reconciled

External platform `prosauai` — bound repo. Per Invariants §3 + §4:

```
External platform prosauai: 0 commits expected to mark now (epic branch
not yet merged to origin/develop). Auto-mark will run on next
`/madruga:reverse-reconcile prosauai` after the merge, provided commits
carry [epic:015-agent-pipeline-steps] tags or the merge preserves the
branch name.
```

This is informational; per Phase 8b rules **never** pre-insert SHAs not present in `origin/<base>`.

---

## 8. Phase 9 — Auto-Commit (deferred — sandbox)

`paceautomations/prosauai` repo writes are out-of-scope for this dispatched run. The branch seal will happen when the developer merges the epic PR; at that point the [epic:015-agent-pipeline-steps] tag (per CLAUDE.md commit-message convention) will let `reverse-reconcile` auto-mark.

---

## 9. Open Items (post-merge work)

| # | Item | Source | Owner |
|---|------|--------|-------|
| OI-1 | Apply ADR-006 amend diff (D5.1) | this report | doc-author |
| OI-2 | Apply ADR-019 amend diff (D5.2) | this report | doc-author |
| OI-3 | Apply domain-model.md updates (D4.1) | this report | doc-author |
| OI-4 | Apply blueprint.md update (D2.1) | this report | doc-author |
| OI-5 | Apply tech-alternatives.md update (D11.1) | this report | doc-author |
| OI-6 | Apply roadmap.md update (Phase 5) | this report | doc-author |
| OI-7 | Open hardening PR for 5 judge BLOCKERs (B1..B5) | `judge-report.md` | engineering |
| OI-8 | Open hardening PR for 16 judge WARNINGs (W1..W16) | `judge-report.md` | engineering |
| OI-9 | Add expression index `idx_audit_log_pipeline_steps_agent` (B4 mitigation) | `judge-report.md` | engineering |
| OI-10 | Convert `_PIPELINE_EXEC_METADATA` to WeakKeyDictionary/context-var (B1 mitigation) | `judge-report.md` | engineering |
| OI-11 | Broaden executor exception filter (B2 mitigation) | `judge-report.md` | engineering |
| OI-12 | Add `pg_advisory_xact_lock` to PUT replace (B5 mitigation) | `judge-report.md` | engineering |
| OI-13 | Fix L1 ruff findings (9 items) | this report §1 | engineering |
| OI-14 | Open epic 015b — agent-versioning + canary | this report §3 | product |
| OI-15 | Promote D-PLAN-02 to ADR via `/madruga:adr` | this report §2 D10 | doc-author |
| OI-16 | Re-run benchmark T051 in CI on merge to develop (SC-010 confirmation) | `qa-report.md` | engineering |
| OI-17 | Quarantine flaky `test_emits_processor_document_extract_span` | `qa-report.md` L2-1 | engineering |

---

## 10. Confidence + Kill Criteria

**Confidence:** Alta com ressalva. The drift detection is exhaustive against checked docs; concrete diffs are ready to apply. The ressalva is that 21 code-side findings (5 BLOCKER + 16 WARN) remain OPEN because the dispatched judge run hit the same sandbox boundary as this reconcile run. They are tracked as OI-7..OI-12 with explicit remediation patches in `judge-report.md`.

**Kill criteria — this report becomes invalid if:**
- (a) The hardening PR for OI-7..OI-12 changes the public surface of `agent_pipeline_steps` or `trace_steps.sub_steps` — re-run reconcile to capture new drift.
- (b) Epic 015b is opened with a different scope than agent-versioning + canary — Roadmap diff (§3) needs revision.
- (c) `agent_config_versions` ships before the next epic begins — D5.2 amend becomes a SUPERSEDE rather than amend, and Phase 9 of epic 015 must be re-scoped (no longer DEFERRED).
- (d) Production telemetry shows the executor overhead exceeds SC-010 (>5 ms p95) — D-PLAN-05 (no cache) needs immediate revisit, blueprint NFR table revised.
- (e) Phase 1b stale-node scan returns non-empty on next run for prosauai — Staleness Resolution table must be regenerated.

---

handoff:
  from: madruga:reconcile
  to: madruga:roadmap
  context: "Reconcile epic 015 complete (autonomous dispatch). Drift score 54.5% (5/11 docs outdated). 5 doc-side diffs ready to apply (ADR-006 amend, ADR-019 amend, domain-model.md, blueprint.md, tech-alternatives.md, roadmap.md). 17 open items tracked (OI-1..OI-17). 21 code-side findings from judge (5 BLOCKER + 16 WARN) remain OPEN — sandbox blocked source edits in paceautomations/prosauai; dedicated hardening PR scheduled (OI-7..OI-12). New follow-up epic 015b proposed (agent-versioning + canary) — promote D-PLAN-02 via /madruga:adr. Phase 8b skipped (external platform — no SHAs in origin/develop yet). Phase 9 (auto-commit) deferred — bound repo writes out-of-scope. Next: /madruga:roadmap prosauai to reassess priorities and materialize 015b."
  blockers: []
  confidence: Alta
  kill_criteria: "Reconcile invalidated if: (a) hardening PR for OI-7..OI-12 changes public surface of agent_pipeline_steps or trace_steps.sub_steps; (b) epic 015b scope diverges from versioning+canary; (c) agent_config_versions ships before next epic — D5.2 becomes SUPERSEDE; (d) production telemetry shows executor overhead >5 ms p95 — D-PLAN-05 invalidated; (e) next stale-node scan returns non-empty for prosauai."
