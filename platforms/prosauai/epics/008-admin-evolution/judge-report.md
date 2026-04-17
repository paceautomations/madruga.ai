---
title: "Judge Report — Epic 008 Admin Evolution"
score: 0
initial_score: 0
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 43
findings_fixed: 0
findings_open: 43
updated: 2026-04-17
---

# Judge Report — Epic 008 Admin Evolution

## Score: 0%

**Verdict:** FAIL (score floors to 0 due to >5 BLOCKERs). See §§ 2–3 for the narrative interpretation — the epic shipped substantial functionality, but has compliance gaps, un-validated scale risks, and explicit gate-skips that block a clean merge to `main`.

**Team:** engineering (4 personas — Architecture Reviewer, Bug Hunter, Simplifier, Stress Tester). All 4 completed successfully.

**Formula:** `100 - (blockers×20 + warnings×5 + nits×1)` → `100 - (5×20 + 25×5 + 13×1) = 100 - 100 - 125 - 13 = −138` → floor **0**.

---

## 1 — Executive Summary

The epic delivered 152 / 158 tasks and all 8 user stories. MVP (US1 Conversas + US2 Trace Explorer) is demonstrably complete in code. Offline tests (1410 passed in the pipeline suite) give a strong correctness floor for instrumentation.

However, the judge surfaced three categories of real risk the `/speckit.implement` + `/speckit.analyze-post` didn't close:

1. **Compliance gaps shipped as `[x]`**: `INSTRUMENTATION_ENABLED` kill switch (T904 claim) is missing from code. `POST /admin/agents/{id}/prompts/activate` is not recorded in `audit_log` — violates FR-090/FR-091. `audit_log` tab therefore omits a state-changing admin action.
2. **Scale risks un-validated**: Phase 12 deployment smoke (T1000–T1005) was NOT executed — no real Docker run, no journey screenshot, no qa_startup. Storage sizing in `step_record.py:9` quoted "~1.2 GB/year" vs. a real ~20–80 GB steady-state. `pool_admin` defaults to 5 connections — exhausted by 2 concurrent admins + pipeline fire-and-forget persist.
3. **Several tasks marked `[x]` were DEFERRED to humans**: T030 (24h staging smoke), T055 (SC-005 inbox <100ms benchmark), T904 (kill switch — which doesn't exist in code), T906–T909 (Lighthouse, Playwright gate). These are compliance/performance gates that have NOT been empirically passed; marking them `[x]` misleads future readers.

The core engineering is solid (fire-and-forget isolation in `trace_persist.py` + `decision_persist.py` is well-hardened; ADR-027/028/029 created; 100% suite green offline). The gap is **between what was claimed done and what can be demonstrated done.**

**Recommendation:** do NOT merge to `main` until the 5 BLOCKERs below are closed or consciously downgraded via PR review. WARNINGs #7–#12 should be addressed before production rollout (scale risks that bite under 3+ admin concurrency).

---

## 2 — Findings

All findings below cite specific files in the `prosauai` repo (external to this `madruga.ai` epic dir). Because this judge invocation cannot write outside the epic directory, **no automatic fixes were applied** — all findings are `OPEN`. See § 5 for the remediation plan.

### BLOCKERs (5 — 0/5 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | analyze-post P5 + bug-hunter | **`INSTRUMENTATION_ENABLED` kill switch missing.** T904 claimed this flag exists; it does NOT. `grep INSTRUMENTATION_ENABLED apps/api/` returns zero matches. Pipeline fire-and-forget persist cannot be disabled without redeploying code. A misbehaving persist path (Redis overload, schema drift) cannot be feature-flagged off. | `apps/api/prosauai/conversation/pipeline.py:708,1358`, `apps/api/prosauai/conversation/trace_persist.py:223` + `apps/api/.env.example` (absent) | OPEN | — |
| B2 | analyze-post P7 + bug-hunter | **`POST /admin/agents/{id}/prompts/activate` does not INSERT into `audit_log`.** Only emits structlog `agent_prompt_activated`. Violates FR-090/FR-091 (audit timeline must reflect admin state-changing actions) and Principle IX (observability). Admin prompt activations are invisible in the Auditoria tab. | `apps/api/prosauai/db/queries/agents.py:427-454` (`activate_prompt` function) | OPEN | — |
| B3 | bug-hunter | **8 KB truncation in `step_record.truncate_io` can be silently exceeded.** The replacement dict is re-serialised without re-measuring bytes; `_truncate_value` slices by CHARS (`char_budget = preview_budget // 4`) — under multi-byte UTF-8 + `ensure_ascii` default=True, a single non-ASCII char expands to 6 ASCII bytes (`\uXXXX`), inflating past `max_bytes`. FR-034 has an explicit ≤8 KB ceiling; this is a shipping contract gap. | `apps/api/prosauai/conversation/step_record.py:156-193` (`_truncate_value`, esp. line 174 missing `ensure_ascii=False`) | OPEN | — |
| B4 | analyze-post P2 | **Phase 12 deployment smoke NOT executed.** T1000–T1005 remain `[ ]`. `docker compose build`, `qa_startup.sh`, journey screenshot, J-001 admin journey — none ran. The 8-tab admin has never been exercised end-to-end against a real container. Regression invisible until someone manually deploys. | `tasks.md` T1000–T1005 (all `[ ]`) | OPEN | — |
| B5 | stress-tester | **`pool_admin.max_size` default=5 will starve under realistic load.** `/admin/metrics/overview` uses `asyncio.gather` with 5 concurrent queries; `/admin/metrics/performance` with 6. Three admins viewing Overview simultaneously want 15 connections from a pool sized 5. Adds contention with pipeline fire-and-forget persist (also using `pool_admin`). Will cascade to 503s and dropped traces under modest concurrent admin use. | `apps/api/prosauai/config.py:66` (`admin_pool_max_size: int = 5`) + `apps/api/prosauai/db/queries/overview.py:259-289` + `apps/api/prosauai/conversation/trace_persist.py:251` (no `acquire(timeout=...)`) | OPEN | — |

### WARNINGs (25 — 0/25 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | analyze-post P1 | **7 tasks marked `[x]` but body says DEFERRED.** T030, T055, T904, T906, T907, T908, T909 — kill-switch, Lighthouse ≥90, 24h staging smoke, Playwright e2e, 10k-conv bench. None have been empirically validated. Marking `[x]` is misleading tracking. | `tasks.md` T030/T055/T904/T906-T909 | OPEN | — |
| W2 | stress-tester | **Cost sparkline is O(N) round-trips.** `cost_by_model` runs outer LIMIT 100 then `_cost_sparkline_for` per row. With 10 tenant×model pairs → 10 sparkline queries × 30d generate_series + LEFT JOIN each. P95 /admin/metrics/performance >> 2s cold-start. | `apps/api/prosauai/db/queries/performance.py:492-582` | OPEN | — |
| W3 | stress-tester | **No single-flight lock on /admin/metrics/performance cache.** 5-min TTL + jitter ±30s helps at SET time but NOT at expiry READS done in the same second. 3 admins refreshing post-expiry each execute the full 1–20s `_compute_all`, multiplying DB load ×3. | `apps/api/prosauai/admin/metrics/performance.py:122-141` + `apps/api/prosauai/admin/cache.py:135-149` | OPEN | — |
| W4 | stress-tester | **Storage sizing miscalculation.** `step_record.py:9` claims "~1.2 GB/year" steady-state. Real: 120 k steps/day × 8 KB cap = ~28 GB/day raw JSONB payload. Retention 30 d = 20–80 GB (TOAST-dependent), NOT 1.2 GB. Retention `DELETE` is single-transaction on 1.4 M rows/day → WAL spike + autovacuum contention + BRIN bloat. | `apps/api/prosauai/conversation/step_record.py:9` + `apps/api/scripts/retention_cron.py:62-96` | OPEN | — |
| W5 | bug-hunter + arch-reviewer | **Fallback `trace_id` collision under concurrency.** When OTel span absent, `_flush_trace` uses `f"{int(time.time()*1e6):032x}[-32:]"` (microsecond precision). Two concurrent pipelines without active span on the same tick collide. `public.traces.trace_id` index is non-unique → silent duplicates. Docstring in `trace_persist.py:61` says "32-char hex from OTel, or random UUID hex" — mismatch. | `apps/api/prosauai/conversation/pipeline.py:627-631` + `trace_persist.py:61` | OPEN | — |
| W6 | bug-hunter | **ILIKE wildcards in user search are NOT escaped.** `q=%` or `q=_` forces full-table sequential scan via `messages.content ILIKE '%%%%'`. Combined with the correlated `EXISTS` subquery, this is a self-DoS trivially triggerable from the admin UI. | `apps/api/prosauai/db/queries/conversations.py:223-236` | OPEN | — |
| W7 | stress-tester | **ILIKE search on `messages.content` has no trigram GIN index.** `%q%` leading wildcard can never use b-tree. EXISTS scans millions of messages per list-conversations call. SC-005 (<100ms) will fail at 10k conv + real traffic. No ANALYZE has been performed. | `apps/api/prosauai/db/queries/conversations.py:227-236` + NO index migration for `pg_trgm` | OPEN | — |
| W8 | stress-tester | **`latency_breakdown` GROUP BY on `trace_steps.name` has no supporting index.** At 36M rows × 30d, percentile_cont across unindexed name/duration_ms → seq scan. P95 >10s likely without materialised aggregate. | `apps/api/prosauai/db/queries/performance.py:351-365` | OPEN | — |
| W9 | stress-tester | **Activity feed `ai_resolved` subquery lacks indexes.** `NOT EXISTS` against `messages.metadata ? 'operator_name'` has no supporting index on conversations `(status, closed_at)` or messages metadata. 15s polling × 3 admins = 12 qps steady load; each query 200-500ms. | `apps/api/prosauai/db/queries/activity.py:131-155` | OPEN | — |
| W10 | stress-tester | **`trace_persist.py:251 pool.acquire()` has NO timeout.** Under pool saturation, background tasks queue indefinitely in the event loop. No bounded Semaphore → unbounded memory growth if Postgres degrades. | `apps/api/prosauai/conversation/trace_persist.py:251` | OPEN | — |
| W11 | stress-tester | **Retention DELETE single-transaction on 1.4M rows.** Table-level lwlock on trace_steps during index maintenance; blocks autovacuum; huge WAL spike; extends `pg_xact`. | `apps/api/scripts/retention_cron.py:62-96` | OPEN | — |
| W12 | stress-tester | **`cost_sparkline` predicate defeats index.** `(tr.started_at AT TIME ZONE 'UTC')::date = d.day` — function-on-LHS-of-= disables btree and BRIN. | `apps/api/prosauai/db/queries/performance.py:505-506,573` | OPEN | — |
| W13 | bug-hunter + stress-tester | **`_GET_TRACE_BY_IDENTIFIER_SQL` `tr.id::text = $1 OR trace_id = $1`** — cast defeats PK index; OR across columns prevents index union. Every lookup = seq scan on traces. | `apps/api/prosauai/db/queries/traces.py:250` | OPEN | — |
| W14 | bug-hunter | **Cache staleness on tenant / pricing mutations.** Performance cached 5 min by `(tenant, period)`; no invalidation when tenant disabled or `MODEL_PRICING` hot-swapped. Cached UI shows stale `is_enabled=true` / old costs until expiry. | `apps/api/prosauai/admin/metrics/performance.py:55-141` + no invalidation hooks on tenant/pricing writes | OPEN | — |
| W15 | bug-hunter | **PATCH conversation idempotent short-circuit returns possibly stale detail.** After `if current["status"] == body.status` early return, a concurrent writer can flip state; returned payload is stale. | `apps/api/prosauai/admin/conversations.py:121-149` | OPEN | — |
| W16 | bug-hunter | **`webhook_received` step is a synthetic no-op.** Records `status=success` + duration ≈ 0ms + `{"accepted": true}` before actual webhook work. Misleads the admin waterfall. | `apps/api/prosauai/conversation/pipeline.py:815-826` | OPEN | — |
| W17 | stress-tester | **KPI SQL uses `NOT IN` over nullable subquery.** Defeats hash-anti-join under some planners; at 3.6M traces + 900k routing_decisions can degrade to nested-loop anti-join. | `apps/api/prosauai/db/queries/performance.py:119-125` | OPEN | — |
| W18 | stress-tester | **Conversation list has 2 correlated subqueries per row.** `quality_score_avg` and `message_count` computed per-row × limit=50 → 100 extra index scans. At 100k conv → breaches 300ms P95 SLA. | `apps/api/prosauai/db/queries/conversations.py:160-191` | OPEN | — |
| W19 | arch-reviewer | **Admin tables grant SELECT/INSERT/DELETE to service_role but do NOT REVOKE from app_user.** ADR-027's "pool_admin only" invariant is enforced only by convention in Python, not at the DB layer. | `apps/api/migrations/20260420000001_create_traces.sql:60-61`, `20260420000002:53-54`, `20260420000003:53-54` | OPEN | — |
| W20 | arch-reviewer | **Denormalized columns on `public.conversations` (tenant-scoped RLS table) are read by pool_admin cross-tenant.** ADR-027 does not document this dual-audience pattern — future epics will re-invent it ad-hoc. | `apps/api/migrations/20260420000004_alter_conversations_last_message.sql` + `apps/api/prosauai/db/queries/performance.py:148-157` | OPEN | — |
| W21 | simplifier | **Triplicated fire-and-forget pattern.** `trace_persist`, `decision_persist`, and `_save_eval_score_task` all re-implement `asyncio.create_task` + `add_done_callback` + log-on-failure. Constitution principle "automate on 3rd repetition" triggered. | `trace_persist.py:199-283`, `decision_persist.py:144-223`, `pipeline.py:1327-1350` | OPEN | — |
| W22 | simplifier | **`unittest.mock` sentinel in production code.** Both fire-and-forget wrappers check `type(pool).__module__.startswith("unittest.mock")` to silence test RuntimeWarnings. Couples library code to test internals. | `trace_persist.py:243-250`, `decision_persist.py:184-191` | OPEN | — |
| W23 | analyze-post P9 | **`platform.yaml:testing.urls` missing 11 new admin routes.** QA (T1003) will fail unless updated. | `platforms/prosauai/platform.yaml` | OPEN | — |
| W24 | analyze-post P10 | **`@playwright/test` not a devDep.** T106/T203/T404 Playwright specs shipped with `@ts-nocheck`. T907 (e2e gate) DEFERRED. | `apps/admin/package.json` | OPEN | — |
| W25 | stress-tester | **System health probe creates httpx.AsyncClient per probe.** Per-call TLS + connection pool allocation every 30s × 3 admins polling. TCP ephemeral port pressure. | `apps/api/prosauai/admin/metrics/system_health.py:151` | OPEN | — |

### NITs (13 — 0/13 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | simplifier | `cached_redis` decorator + `_hash_kwargs`, `_cache_key`, `_jittered_ttl` defined and exported but have ZERO callers — all cache uses call `get_cached`/`set_cached` directly. Dead code (~130 lines). | `apps/api/prosauai/admin/cache.py:89-206` | OPEN | — |
| N2 | simplifier | `_StepCtx` dataclass re-defined as nested class on every pipeline call. Trivial allocation overhead but signals over-inlining. | `apps/api/prosauai/conversation/pipeline.py:557-568` | OPEN | — |
| N3 | simplifier | `health-rules.ts` (TS) + `health.py` (Py) duplicate `classifyKpi`, `classifyTenantHealth`, `classifyVolumeDelta` + all 5 threshold tables. "Kept in lock-step via shared test fixtures" — still drift-prone. | `apps/admin/src/lib/health-rules.ts:57-200` + `apps/api/prosauai/admin/health.py:47-182` | OPEN | — |
| N4 | simplifier | `_json_or_none` byte-identical across `trace_persist.py:120-124` + `decision_persist.py:100-109`. | — | OPEN | — |
| N5 | simplifier | `api.ts` + `api-server.ts` duplicate ~30 LOC of error-payload parsing. | `apps/admin/src/lib/api.ts:117-141` vs `api-server.ts:101-125` | OPEN | — |
| N6 | simplifier | `admin/router.py` has 60 lines of manually-repeated `include_router` calls with historical epic/US headers that will rot. | `apps/api/prosauai/admin/router.py:30-60` | OPEN | — |
| N7 | simplifier | `_jittered_ttl` uses symmetric jitter (±30s). Negative jitter shortens TTL → higher miss rate with no risk-reduction benefit. | `apps/api/prosauai/admin/cache.py:89-94` | OPEN | — |
| N8 | simplifier | `TRACE_RETENTION_DAYS` / `ROUTING_RETENTION_DAYS` env-configurable with single caller each. Hardcoded constant would be clearer. | `apps/api/.env.example:73-74` + `scripts/retention_cron.py:244-250` | OPEN | — |
| N9 | bug-hunter | Retention cron under-reports deleted count for `trace_steps` — rows CASCADE-deleted by `traces` removal aren't counted in explicit DELETE stats. | `scripts/retention_cron.py:62-96` | OPEN | — |
| N10 | arch-reviewer | Tag naming drift: `apps/api/prosauai/admin/metrics/performance.py:53` uses `tags=["admin-metrics"]` while OpenAPI contract uses `metrics` uniformly. | `performance.py:53` vs `contracts/openapi.yaml:269,282,299,315,326` | OPEN | — |
| N11 | bug-hunter | `calculate_cost` raises `ValueError` on negative tokens, but `trace_buffer.tokens_in_total` is accumulated without a `max(0, …)` floor. Silent cost=None on adversarial mock. | `pipeline.py:1140-1156, 644-649` | OPEN | — |
| N12 | stress-tester | `trace_steps` JSONB input for `webhook_received` includes `tenant_id` duplicated on every child — already on parent trace row. ~86 MB/day waste. | `pipeline.py:820` | OPEN | — |
| N13 | analyze-post P12/P13 | Metric cosmetic: implement-report.md says "7/7 tasks completed" referring to single dispatch batch; pre-implement analyze understated total task count (~120 vs actual 158). | `implement-report.md` | OPEN | — |

---

## 3 — Safety Net — Decisões 1-Way-Door

Scanned `git log` on branch `epic/prosauai/008-admin-evolution` (23+ commits) + the 158 tasks + 29 captured decisions in `pitch.md`. Looked for state-changing/irreversible choices that escaped the inline Decision Classifier.

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | ADR-027 — admin tables carve-out from RLS | 5×5 = 25 (Risk: bypass of security invariant; Reversibility: hard to re-introduce RLS after data accumulated) | Yes — T001 created ADR explicitly | **APPROVED** (documented + reviewed) |
| 2 | ADR-028 — pipeline fire-and-forget persist | 4×3 = 12 | Yes — T002 created ADR; precedent in Phoenix exporter | 2-way-door, documented |
| 3 | ADR-029 — hardcoded pricing as code constant | 2×2 = 4 | Yes — T003 created ADR; criterion to migrate defined | 2-way-door |
| 4 | Pipeline refactor (T026 → `Pipeline.execute()` instrumentation) | 4×2 = 8 | Implicit — protected by gate SC-007 100% suite green | 2-way-door (test suite is safety net) |
| 5 | Denormalized columns on `conversations` (W20) | 3×3 = 9 | No — no ADR extension | **WARNING**: drift pattern not documented; repeat risk in epic 009+ |
| 6 | BRIN-on-started_at strategy vs PARTITION (W4) | 4×4 = 16 | No — no ADR | **NEEDS REVIEW**: partition-vs-BRIN will matter at production scale; capture decision rationale before retention kicks in |
| 7 | 8 KB truncation cap (FR-034 + B3) | 3×3 = 9 | Implicit in spec | Documented in spec; gap is implementation (B3) |
| 8 | Branch reuse of `epic/prosauai/008-admin-evolution` (decision 25) | 2×3 = 6 | Yes — explicit in pitch.md | 2-way-door |

**Escaped 1-way-doors: #6 (BRIN vs partition for trace_steps).** Under retention at 30d on 1.4M rows/day (W4 + W11), BRIN + single-txn DELETE is a material design drift from pitch.md decision 7 ("índices BRIN em started_at") — which was reasonable at the time but untested against the corrected volume estimate. **Recommendation:** add an ADR amendment documenting the trade-off before the first retention run hits production, or migrate to RANGE partitioning by day (30 partitions, DROP TABLE = O(1) aging-out).

All other significant decisions were captured in ADRs or `pitch.md`/`decisions.md`.

---

## 4 — Personas que Falharam

Nenhuma. 4/4 personas completed and emitted valid `PERSONA:` + `FINDINGS:` output.

---

## 5 — Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| — | 0 | No code fixes applied in this judge invocation. |

**Rationale:** all BLOCKERs and WARNINGs in §2 require code changes in the `prosauai` repo (external to this `madruga.ai` epic dir). The autonomous judge runs with a hard constraint that output MUST be saved to `platforms/prosauai/epics/008-admin-evolution/` and MUST NOT write outside the epic directory. Therefore all findings are recorded `OPEN` with file:line evidence for the reconcile / follow-up PR to act on.

---

## 6 — Recomendações

### Must-fix before merge to `main` (BLOCKERs)

1. **B1 — ship `INSTRUMENTATION_ENABLED` flag** (≤ 15 LOC).  Add `Settings.instrumentation_enabled: bool = True` in `apps/api/prosauai/config.py`; gate `_flush_trace` in `pipeline.py` and `persist_routing_decision_fire_and_forget` in `decision_persist.py`; document in `apps/api/.env.example`. Update T904 in `tasks.md` to reflect actual state (was falsely `[x]`).
2. **B2 — audit-log on `activate_prompt`** (≤ 20 LOC). Inside `apps/api/prosauai/db/queries/agents.py:activate_prompt`, after successful UPDATE, INSERT `audit_log` row with action=`prompt_activated`, target_id=prompt_id, actor=`_admin["email"]`, details={`agent_id`, `previous_active_prompt_id`, `new_active_prompt_id`}. Same txn. Add regression test in `test_agents.py`.
3. **B3 — enforce 8 KB byte-cap post-substitution.** In `step_record._truncate_value`, after building replacement dict, re-serialise with `ensure_ascii=False`; while `len(json.dumps(replacement, ensure_ascii=False).encode()) > max_bytes`, halve `preview`. Add property-based test with `hypothesis` covering non-ASCII payloads.
4. **B4 — run Phase 12 deployment smoke**. T1000–T1005 must land. Requires Docker stack + `qa_startup.sh`. Gate for merge.
5. **B5 — bump `admin_pool_max_size` to 15 + separate `pool_persist`**. Raise default via env; add optional `ADMIN_PERSIST_POOL_MAX_SIZE=5` if we want isolation from admin browsing. Update `config.py:66` + `apps/api/.env.example`. Add `pool.acquire(timeout=5.0)` at `trace_persist.py:251` and bounded `asyncio.Semaphore(20)` around persist tasks.

### Should-fix in follow-up PR (top WARNINGs for scale)

6. **W2+W3 — Performance endpoint rewrite**. Collapse cost sparkline to single `GROUP BY tenant, model, date_trunc` query; add Redis SETNX single-flight lock to prevent stampede; or precompute every 4 min via a cron task.
7. **W4+W11 — retention strategy**. Re-estimate volume empirically after 7d of staging traces; decide: (a) stay on BRIN + batched DELETE (`... WHERE ctid IN (SELECT ctid ... LIMIT 10000)` looped + VACUUM), or (b) migrate `trace_steps` to `PARTITION BY RANGE (started_at)` and DROP TABLE oldest partition.
8. **W6+W7 — ILIKE hardening**. Escape `%`/`_` in user `q`; ship `pg_trgm` + `CREATE INDEX … USING GIN (content gin_trgm_ops)` before marking SC-005 validated.
9. **W8+W13 — add supporting indexes**. `idx_trace_steps_name_started`, change trace_id lookup to UUID-detect-in-Python approach (index-driven both paths).
10. **W10 — bound trace persist tasks** (see B5).

### Nice-to-have (cleanup, epic 009)

11. **W21+W22+N1+N4 — extract `prosauai/common/fire_and_forget.py`** that does: pool-None guard + timeout + optional Semaphore + add_done_callback logging. Eliminates triplication, drops `unittest.mock` sentinel from library code, and lets tests pass `pool=None` for no-op behaviour.
12. **N3 — eliminate dual health-rules**. Cheapest: backend pre-computes `status` fields; frontend keeps only `classifyVolumeDelta` for sparkline-only client logic.
13. **Safety-net #6 — ADR amendment**: document BRIN-vs-partition trade-off for trace_steps volume.
14. **W19 — REVOKE app_user from admin tables**: follow-up migration `20260421000001_revoke_app_user_admin_tables.sql`. One-line grant changes, makes ADR-027 invariant enforceable at the DB layer.

### Administrative

15. **W1+W23+W24** — clean up tracking. Revert the 7 `[x]` → `[ ]` for DEFERRED tasks with a note pointing to the runbooks (`benchmarks/pipeline_instrumentation_smoke.md`, etc.). Update `platforms/prosauai/platform.yaml:testing.urls` with the 11 new admin routes. Add `@playwright/test` to `apps/admin/package.json` devDeps + remove `@ts-nocheck` from e2e specs.

---

## 7 — Confidence & Rationale

**Confidence in findings:** High. All 4 personas cited specific file:line evidence. The judge pass confirmed each finding by reading the cited code directly (see transcripts of verification reads: P3 system_health thresholds were PRESENT and correct → not promoted; P6 evaluator was pure heuristic → finding withdrawn; P5/P7/B3 confirmed by grep + Read).

**Confidence in verdict:** High. Score 0 is mechanical (formula output). The narrative verdict is **"epic shipped substantial value but has real compliance + scale gaps that block a clean main-merge"**. The 5 BLOCKERs are each independently defensible; closing them is a ~2-day PR.

**Kill criteria for this report:**
- If B1/B2 are found to exist (false negative from grep) → remove them; score recovers by 40 points.
- If the `step_record._truncate_value` is proven to enforce byte-cap in a subsequent test (B3 is false alarm) → remove; +20.
- If Phase 12 smoke is run and passes → B4 resolves; +20.
- If `admin_pool_max_size` is demonstrated to hold under 3-admin concurrent load via k6 / hey → B5 resolves; +20.

---

handoff:
  from: judge
  to: qa
  context: "Judge FAIL (score 0, 5 BLOCKERs). Epic 008 shipped all 8 user stories + 152/158 tasks, but the following blocks main-merge: (1) INSTRUMENTATION_ENABLED kill switch promised by T904 does NOT exist in code, (2) POST /admin/agents/{id}/prompts/activate lacks audit_log INSERT, (3) 8KB truncation in step_record._truncate_value doesn't enforce byte-cap post-substitution (FR-034 gap), (4) Phase 12 deployment smoke (T1000-T1005) was NOT executed, (5) pool_admin default size 5 will starve under 3 concurrent admins + pipeline persist. 25 WARNINGs include cost-sparkline O(N) fan-out, cache-stampede on /metrics/performance, storage-sizing miscalculation (~1.2GB/year claimed vs 20-80GB real), unescaped ILIKE wildcards. All findings are OPEN because this judge invocation cannot write to the prosauai repo; fixes must land in a follow-up PR before merging to main. QA should (a) execute Phase 12 smoke before QA run starts, (b) prioritize B1/B2/B5 fixes before exercising admin endpoints under load, (c) re-check 24h staging instrumentation overhead (T030 runbook) before signing off SC-006/SC-007."
  blockers: [B1, B2, B3, B4, B5]
  confidence: Alta
  kill_criteria: "Report invalid if: (a) grep INSTRUMENTATION_ENABLED apps/api/ DOES return matches (B1 false negative); (b) audit_log INSERT is found in activate_prompt (B2 false negative); (c) Phase 12 smoke is executed and passes before reconcile (B4 auto-resolves); (d) load test demonstrates pool_admin=5 holds under 3 concurrent admins (B5 downgrades to WARNING)."
