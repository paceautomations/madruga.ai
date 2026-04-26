---
title: "Judge Report — Epic 011 Evals (post-implement)"
score: 50
initial_score: 10
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 35
findings_fixed: 2
findings_open: 33
updated: 2026-04-25
---

# Judge Report — Epic 011 Evals

## Score: 50%

**Verdict:** FAIL (initial score 10 → 50 after fixing both BLOCKERs)
**Team:** engineering (4 personas — arch-reviewer, bug-hunter, simplifier, stress-tester)
**Branch:** `epic/prosauai/011-evals`
**Code repo:** `paceautomations/prosauai` (binding from `platform.yaml`)

The two privacy-grade BLOCKERs (LGPD SAR was effectively broken) are **fixed in the same Judge pass** — see §Files Changed. The remaining 33 findings are non-blocking but represent real technical debt and scale concerns that should be addressed in a follow-up polish (011.1) before ResenhAI flips from `shadow → on`.

The score reflects honest filtering: 5 WARNINGs (real v1 production-quality concerns) + 28 NITs (cleanup, edge cases, dead code, observability gaps). No code path identified during the Judge pass would cause a customer-visible failure under v1 traffic levels (Ariel/ResenhAI ~3K-10K msgs/tenant/day) — the WARNINGs are about correctness drift in observability + KPI accuracy + pre-emptive scale guards.

## Findings

### BLOCKERs (2 — 2/2 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | bug-hunter + stress-tester (consensus) | LGPD SAR sets the WRONG GUC name AND uses unsupported parameter binding. `SET LOCAL app.tenant_id = $1` is invalid on two counts: (a) Postgres rejects `$1` parameter binding in `SET` utility commands (already documented in `conversation/customer.py:103-108`); (b) the RLS helper `public.tenant_id()` reads `app.current_tenant_id`, NOT `app.tenant_id` (migration `20260101000001_create_schema.sql:25`). Net effect: every tenant-scoped DELETE in `_TENANT_SCOPED_STATEMENTS` either errors or silently affects 0 rows under RLS — customer PII (messages, eval_scores, conversations) is **NEVER erased** while the audit log claims success. | `apps/api/prosauai/privacy/sar.py:287` (pre-fix) | **FIXED** | Replaced with `await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))` — matches the established pattern in `conversation/customer.py:106`. Updated unit test `test_erase_customer_runs_every_delete_in_order` accordingly. |
| B2 | bug-hunter | LGPD SAR phase ordering breaks cross-pool joins. Phase 1 (tenant pool) deletes the `conversations` row BEFORE Phase 2 (admin pool) queries `IN (SELECT id FROM public.conversations WHERE tenant_id=$1 AND customer_id=$2)`. By the time Phase 2 runs, the subquery returns zero rows → `handoff_events`, `bot_sent_messages`, `trace_steps`, `traces` are NEVER deleted → `public.golden_traces` ON DELETE CASCADE never fires. The reported `golden_traces (cascade)` count would be a fake zero. | `apps/api/prosauai/privacy/sar.py:282-297` (pre-fix) | **FIXED** | Swapped phase order — admin phase runs FIRST while conversations are alive as the join target; tenant phase runs second and ends with the conversations DELETE. Updated module docstring §Concurrency. Added new test `test_erase_customer_propagates_failure_in_admin_phase` to lock the new ordering against regression. |

### WARNINGs (5 — 0/5 fixed)

These are non-blocking for the next rollout but should land before ResenhAI `shadow → on` (or in 011.1).

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | arch-reviewer + bug-hunter (consensus) | `autonomous_resolution.py` docstring says "the advisory lock is released *before* the UPDATE loop" but the code holds the lock for the entire batched SELECT/UPDATE while-loop (`async with AdvisoryLockGuard` wraps the whole loop, lines 307-342). Either docs or implementation is wrong — operators reading the docstring will assume two replicas can update disjoint batches concurrently. The implementation is correct (NULL-filter idempotency protects against partial-tick race); the docstring is the bug. | `apps/api/prosauai/evals/autonomous_resolution.py:43-48, 240-243` | OPEN | Recommend rewriting the docstring to say "lock held for the whole tick; `auto_resolved IS NULL` filter protects against any racing replicas". 1-line fix. |
| W2 | bug-hunter | Heuristic A regex `\y(humano\|atendente\|pessoa\|alguem real)\y` doesn't match accented PT-BR forms — `alguém real` falls through (false-positive on `auto_resolved=TRUE`). PT-BR users very commonly type `alguém`. Affects North Star KPI accuracy. | `apps/api/prosauai/evals/autonomous_resolution.py:142` | OPEN | Add `\|alguém real` to the alternation, or normalize via `unaccent()` extension. Zero infra cost for the alternation route. |
| W3 | bug-hunter + stress-tester (consensus) | `count_coverage` denominator counts ALL outbound messages without applying the same filters the persistence path applies (`is_direct=TRUE` for groups, `LENGTH(content) ≤ 32000` for DeepEval). Numerator is filtered, denominator isn't → SC-001 dashboard reports systematically-low coverage (cards show e.g. 95% when actual is 99%). | `apps/api/prosauai/db/queries/eval_scores.py:228-313` | OPEN | Either filter the denominator to match persistence invariants, OR document that coverage is an upper bound on missing scores and decouple from SC-001 gating. |
| W4 | bug-hunter | `EvalMetricsFacade._budget_breach_alerted` and `_cost_running_sum` are never pruned by tenant churn or day rollover for `_budget_breach_alerted` — `(tenant, yesterday)` keys persist forever. Slow memory leak over months. | `apps/api/prosauai/evals/metrics.py:91-94, 246-279` | OPEN | At the start of `_update_budget_accumulator`, prune entries whose `date` < today. ~3 LOC. |
| W5 | stress-tester | DeepEval `_call_with_retry` retries the whole metric measurement (each may make multiple internal LLM calls). On a 429 storm, one message → 3 attempts × N internal calls; the chunk's four parallel metric tasks compound to ~40 concurrent in-flight Bifrost requests with no concurrency cap. Real risk under Bifrost rate-limit pressure. | `apps/api/prosauai/evals/deepeval_batch.py:325-372, 657-685` | OPEN | Add `asyncio.Semaphore(4)` per chunk; consider tenant-scoped circuit breaker (mirror epic 010's `helpdesk_breaker_open`). |

### NITs (28 — 0/28 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | arch-reviewer | `evals/persist.py` reaches into private `conversation.customer._acquire_conn`. Coupling violation across bounded contexts. | `evals/persist.py:144` | OPEN | Promote `_acquire_conn` to a public shared helper (`prosauai/db/rls.py::acquire_tenant_conn`). |
| N2 | arch-reviewer | `PoolPersister` docstring asserts pool MUST be `pool_tenant`, but `main.py` lifespan registers the persister with `pools.admin` (BYPASSRLS) for the DeepEval cron. Contract drift. | `evals/persist.py:115-120` vs `main.py:505-509` | OPEN | Update docstring to document dual-mode contract (BYPASSRLS bypasses RLS harmlessly). |
| N3 | arch-reviewer | OpenAPI single-source-of-truth drift versus `CLAUDE.md`. Epic 011 created a parallel `epics/011-evals/contracts/openapi.yaml` and `pnpm gen:api:evals → src/types/api.evals.ts`; the admin UI now has two type roots. | `apps/admin/package.json:12-13` | OPEN | Either merge into the canonical 008 contract, or amend `CLAUDE.md` to document the per-epic OpenAPI fragment pattern. |
| N4 | arch-reviewer | `EvalScoreRecord.evaluator_type` literal `heuristic_v1\|deepeval\|human` excludes the legacy `heuristic` value still emitted by `pipeline.py:429`. Loading historical rows through `EvalScoreRecord.model_validate(...)` would fail. Today no code path triggers this; future migrations / admin queries are footguns. | `evals/models.py:48-54` vs `conversation/pipeline.py:429` | OPEN | Add `heuristic` as deprecated alias OR run a one-shot relabel migration. |
| N5 | arch-reviewer | `ToxicityWrapper` and `BiasWrapper` share the same threshold key (`alerts.toxicity_max`). Carries a known semantic conflation in production for ops. | `evals/persist.py:243-249`, `evals/models.py:197-209` | OPEN | Add `bias_max: float = Field(default=0.05)` to `EvalAlerts` and split. |
| N6 | arch-reviewer | `heuristic_online.persist_heuristic` instantiates fresh `PoolPersister` per call (per-message, hot path). Epic 010 convention is single instance on `app.state`. | `evals/heuristic_online.py:191-193` | OPEN | Mirror `app.state.helpdesk_registry`: build one `PoolPersister` at lifespan, store on `app.state.eval_persister_online`. |
| N7 | bug-hunter | `_get_async_client` lazy-init has no race in current single-event-loop asyncio (no await between check and assign), but the pattern is fragile against any future change that introduces an `await`. Defensive guard recommended. | `evals/deepeval_model.py:295-300` | OPEN | Add `asyncio.Lock` and double-check inside lock, or initialize eagerly in `__init__`. |
| N8 | bug-hunter | `tenants_yaml_writer.write_evals_block` provides no cross-replica/cross-process coordination. Single-process FastAPI is safe (read+mutate+rename are synchronous, no await between them); multi-replica deployments race. | `apps/api/prosauai/admin/tenants_yaml_writer.py:98-227` | OPEN | Add `fcntl.flock(LOCK_EX)` on a sentinel file in same dir, or stat-cas mtime before rename. |
| N9 | bug-hunter | `tenants.py::patch_tenant_evals_endpoint` reads YAML via `read_text(encoding="utf-8")` outside the `try/except yaml.YAMLError`. A non-UTF-8 byte (operator manually edited) raises `UnicodeDecodeError` → 500 with stack trace, not the curated `tenants.yaml_invalido` 500. | `apps/api/prosauai/admin/tenants.py:227-246` | OPEN | Catch `UnicodeDecodeError` and translate to the same curated 500. |
| N10 | bug-hunter | Heuristic A SQL evaluates the regex EXISTS twice and the silence sub-select MAX twice. At scale of 1000 conversations per tick the duplicated MAX is measurable. | `apps/api/prosauai/evals/autonomous_resolution.py:144-159` | OPEN | Use a LATERAL subquery to compute `last_inbound_at` once. |
| N11 | bug-hunter | `EvalScoreRecord._clip_score` logs a warning when clipping but does NOT mark `details.clipped=True` — observability lossy. | `apps/api/prosauai/evals/models.py:142-154` | OPEN | When clipping fires, also include `clipped=True` and `raw_score=score` in `record.details`. |
| N12 | bug-hunter | `fetch_golden_records` swallows the connection on _reconstruct_pair errors — a single bad row aborts the entire generator. | `apps/api/prosauai/evals/promptfoo/generate.py:357-377` | OPEN | Wrap `_reconstruct_pair` in `try/except`; log skip; continue. |
| N13 | bug-hunter | `BifrostDeepEvalModel._headers` lower-cases `authorization` header. Most servers tolerate but Bifrost custom auth filters / proxies that case-match `Authorization` may reject. | `apps/api/prosauai/evals/deepeval_model.py:268-274` | OPEN | Use canonical `Authorization`. WARN once at startup if `_api_key` is empty. |
| N14 | bug-hunter | `httpx.HTTPStatusError` `else 500` branch is dead code — `HTTPStatusError` always carries `response`. | `apps/api/prosauai/evals/deepeval_batch.py:317-319` | OPEN | Drop the defensive `else 500` so the natural attribute access raises if the upstream contract changes. |
| N15 | bug-hunter | `persist_heuristic` schedules `asyncio.create_task(...)` and returns the task, but neither caller stores a strong reference. Under heavy load, GC may collect the task before completion → `Task was destroyed but it is pending!` warning. | `apps/api/prosauai/evals/heuristic_online.py:206-220` | OPEN | Maintain a module-level `_inflight: set[asyncio.Task]`, anchor via `add_done_callback(_inflight.discard)`. |
| N16 | bug-hunter | `golden_traces.notes` reaches DB as raw string; pydantic enforces `max_length=2000` but no scrubbing of CRLF/control chars → log forging via structlog `golden_trace_starred`. Low impact (admin-authenticated endpoint). | `apps/api/prosauai/db/queries/golden_traces.py:43-123` | OPEN | Strip control chars before INSERT. |
| N17 | bug-hunter | `_eligible_tenants` defaults to `mode='off'` for missing/malformed config but does NOT lowercase the value — `'OFF'` or `'On'` are silently rejected with no operator signal. | `apps/api/prosauai/evals/autonomous_resolution.py:189-209` | OPEN | Lowercase `mode`; emit `tenant_evals_mode_unknown` debug log if unknown after lowercasing. |
| N18 | simplifier | `EvalsScheduler` exposes both `register_periodic` (test-only) and `register` (production). Two methods doing the same thing. handoff scheduler has only `register`. | `apps/api/prosauai/evals/scheduler.py:132-176` | OPEN | Drop `register_periodic`; update tests to use `register(PeriodicTask(...))`. |
| N19 | simplifier | `_null_advisory_lock` defined but zero callers. | `apps/api/prosauai/evals/deepeval_batch.py:989-993` | OPEN | Delete. |
| N20 | simplifier | `intent_stratified` parameter on `sample_messages` is documented as "reserved for a future uniform-fallback path" and immediately discarded with `_ = intent_stratified`. YAGNI. | `apps/api/prosauai/evals/deepeval_batch.py:259, 273` | OPEN | Remove the parameter. |
| N21 | simplifier | `_eligible_tenants` defined twice with near-identical bodies in autonomous_resolution.py and deepeval_batch.py. | `apps/api/prosauai/evals/autonomous_resolution.py:189` + `apps/api/prosauai/evals/deepeval_batch.py:629` | OPEN | Move to `prosauai/evals/_tenants.py`; pass differing flag (`offline_required: bool`) at call site. |
| N22 | simplifier | `_MetricWrapperBase` + 4 near-empty subclasses total ~110 LOC for what is effectively `(metric_name, deepeval_metric_factory)` pairs. The Protocol + abstract base + 4 subclasses is over-engineering for one production set. | `apps/api/prosauai/evals/deepeval_batch.py:380-602` | OPEN | Replace with single function `evaluate_metric(msg, metric_name, deepeval_metric_obj)` and a `METRICS = [(...), ...]` table. |
| N23 | simplifier | Triple try/suppress: `metrics.py::_emit` is wrapped in `with suppress(Exception)`, then call sites further wrap in another try/except. Belt-and-suspenders without justification. | `evals/metrics.py:98-106` + `persist.py:181-194` | OPEN | Pick one place to swallow; drop `_safe_metric_ok_error`. |
| N24 | simplifier | `_update_budget_accumulator` uses `with suppress(Exception):` *inside which* it has another `try/except (TypeError, ValueError)`. Outer suppress already covers it. | `apps/api/prosauai/evals/metrics.py:255-264` | OPEN | Drop inner try/except. |
| N25 | simplifier | `tenants_yaml_writer.py` is 230 LOC for what is essentially a 2-level dict mutation + atomic write. Custom `_deep_merge` + `.bak` backup are overkill. | `apps/api/prosauai/admin/tenants_yaml_writer.py:64-77, 182-218` | OPEN | Drop generic deep_merge + `.bak`; use `Path.write_text + os.replace`. |
| N26 | stress-tester | Cross-tenant queries (`tenant=all`) lose the leading-column index advantage of `idx_eval_scores_tenant_evaluator_metric_created`. At v1 scale (~1.5M rows steady state) acceptable; at 10x scale (15M rows) admin cards exceed the 3s acquire timeout. | `apps/api/prosauai/db/queries/eval_scores.py:165, 261, 366` | OPEN | Add `(evaluator_type, metric, created_at DESC)` index for cross-tenant view; or pre-aggregate via materialized view. |
| N27 | stress-tester | `eval_scores_retention_cron` DELETE has no LIMIT and uses `RETURNING tenant_id` — at v1 scale (~7K rows/day per tenant) acceptable. After missed ticks (>2 weeks), 100K+ rows in one DELETE could lock the table for minutes and block PoolPersister INSERTs. | `apps/api/prosauai/evals/retention.py:92, 182` | OPEN | Switch to chunked DELETE: `DELETE … WHERE ctid IN (SELECT ctid … LIMIT 5000) RETURNING tenant_id` in a loop with `asyncio.sleep(0)` between iterations. Cap per-tick total at 200k. |
| N28 | stress-tester | `admin_pool_max_size = 5` is tight for concurrent burst (DeepEval batch fires 40 parallel persists per chunk + autonomous + retention). Acceptable at v1 (operations sequenced via different cron times: 02/03/04 UTC) but reduces headroom under future overlap. | `apps/api/prosauai/config.py:72`, `apps/api/prosauai/main.py:506` | OPEN | Raise `admin_pool_max_size` to ≥20, OR queue persists through `asyncio.Semaphore` inside `_process_message`, OR route DeepEval persists through `pools.tenant`. |

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | 5 schema migrations (eval_scores ADD COLUMN metric, traces UNIQUE trace_id, conversations auto_resolved, messages is_direct DEFAULT TRUE, golden_traces new table) | Risk 3 × Reversibility 3 = 9 (2-way) | N/A — has `migrate:down` for all 5 | Aprovada via plan/data-model — backfill `is_direct=TRUE` documented as conscious R6 in plan.md |
| 2 | DeepEval as dependency (deepeval>=3.0) using Bifrost as judge | Risk 2 × Reversibility 3 = 6 (2-way) | N/A | Aprovada — extends ADR-008; reversible via `evals.offline_enabled=false` in `tenants.yaml` |
| 3 | Heuristic A regex codified | Risk 3 × Reversibility 4 = 12 (2-way) | N/A | Aprovada via ADR-040 — accepts initial KPI imprecision as tradeoff for v1 |
| 4 | `evaluator_type` ADD COLUMN vs RENAME (eval_scores backward compat) | Risk 2 × Reversibility 3 = 6 (2-way) | N/A | Aprovada via ADR-039 — ADD COLUMN with `metric` is aditivo |
| 5 | SAR phase ordering swap (TODAY in this judge pass — fix B2) | Risk 2 × Reversibility 2 = 4 (2-way) | N/A | Corrective fix — replaces broken implementation; not a discretionary architectural decision |

**Resultado**: Nenhuma decisão 1-way-door escapou. Todas as decisões irreversíveis tiveram cobertura ADR ou foram registradas explicitamente no plan/spec. As migrations têm `migrate:down`. Feature flag `evals.mode: off` permite rollback completo em ≤60s via `tenants.yaml` (config_poller).

## Personas que Falharam

Nenhuma. Todas as 4 personas (arch-reviewer, bug-hunter, simplifier, stress-tester) retornaram findings no formato esperado (`PERSONA:` header + `FINDINGS:` section). Aplicada degradação **normal** — score em todas as findings.

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `apps/api/prosauai/privacy/sar.py` | B1 + B2 | (a) Replaced broken `SET LOCAL app.tenant_id = $1` with `SELECT set_config('app.current_tenant_id', $1, true)`. (b) Swapped phase ordering: admin phase (`pool_admin`) runs FIRST while conversations are alive as the join target; tenant phase (`pool_app`) runs second and ends with the conversations DELETE. (c) Updated module docstring §Concurrency to reflect the new ordering and the LGPD invariant. |
| `apps/api/tests/unit/privacy/test_sar.py` | B1 + B2 (test contract) | (a) `_tenant_command_tags` now starts with `"SELECT 1"` (set_config) instead of `"SET"`. (b) `test_erase_customer_runs_every_delete_in_order` asserts admin phase runs FIRST; tenant phase second uses canonical `set_config` call. (c) Renamed/extended failure-propagation tests: `test_erase_customer_propagates_failure_in_tenant_phase` (admin already done when tenant explodes) + new `test_erase_customer_propagates_failure_in_admin_phase` (tenant never reached when admin explodes — locks the new ordering against regression). |

**Verification**: `pytest tests/unit/privacy/test_sar.py -v` → **14 passed in 2.58s**, sar.py module coverage 100%. `ruff format --check` clean. Pre-existing repo-level lint patterns (`UP037` quoted asyncpg.Pool, `SIM117` nested `async with`, `N818` `_BoomPg`) untouched — out of scope for the BLOCKER fix.

## Recomendações

### Imediato (antes do próximo deploy de prosauai)
1. **Mergear o SAR fix** já aplicado — sem isto, qualquer requisição LGPD/GDPR atual deixa PII residual. Esta é a única bloqueante crítica.
2. Comunicar com privacidade/jurídico sobre eventuais SARs processados desde o merge do epic 011: validar que não rodaram em produção ou refazer manualmente via SQL para os casos afetados.

### Antes de ResenhAI flip `shadow → on` (semanas 3-4)
3. **W1** — corrigir o docstring drift de `autonomous_resolution.py` para evitar ops misreading (1 linha).
4. **W2** — adicionar `alguém real` à alternação do regex (KPI accuracy).
5. **W3** — alinhar denominador de `count_coverage` com filtros de persistência OU desacoplar do gate SC-001.
6. **W4** — pruning diário do `_budget_breach_alerted` (3 LOC).
7. **W5** — `asyncio.Semaphore(4)` em `_process_message` para evitar storm Bifrost em 429 burst.

### Polish 011.1 (próximo ciclo)
8. Resolver os 28 NITs em ondas:
   - **Onda 1 (cleanup)**: N18 (drop `register_periodic`), N19 (drop `_null_advisory_lock`), N20 (drop `intent_stratified`), N23+N24 (collapse triple try/suppress), N25 (simplificar yaml writer), N14 (drop dead branch).
   - **Onda 2 (refactor)**: N22 (collapse 5-class wrapper hierarchy), N21 (dedup `_eligible_tenants`), N6 (`PoolPersister` em `app.state`), N1 (promote `_acquire_conn`).
   - **Onda 3 (observability)**: N11 (clipped flag em details), N15 (anchor task strong ref), N17 (lowercase mode), N3 (resolver OpenAPI SoT drift).
   - **Onda 4 (scale guards)**: N26 (índice cross-tenant), N27 (chunked retention DELETE), N28 (raise admin pool sizing).

### Constituição
A implementação respeita os 9 princípios da `constitution.md`:
- **I Pragmatism** — 1 lib nova (`deepeval`), zero infra nova; reuso do Bifrost existente; reuso do scheduler/advisory-lock pattern do epic 010.
- **VII TDD** — Cobertura ≥95% nos módulos críticos; testes unit + integration + race + benchmark.
- **IX Observability** — 5 metrics Prometheus via structlog facade, OTel spans, canonical log keys.

Não há violação de princípio. O score 50 reflete o volume de tech-debt, não falha estrutural. Após o SAR fix mergeado e os 5 WARNINGs resolvidos em 011.1, a estimativa é que o score saltaria para ≥80 (PASS).

---

<!-- HANDOFF -->
---
handoff:
  from: madruga:judge
  to: madruga:qa
  context: "Judge complete — score 50 (FAIL by threshold but improving from initial 10 after fixing 2 LGPD-grade BLOCKERs in SAR module). 5 WARNINGs + 28 NITs remain OPEN as 011.1 polish backlog. SAR fix is in-tree (sar.py + test_sar.py) and validated via pytest (14/14 passed). Recommend QA test plan focuses on: (a) end-to-end SAR erasure validation in staging — assert non-zero deletes for messages, eval_scores, traces, golden_traces; (b) 7-day shadow run for Ariel evals.mode validation (coverage ≥80%, autonomous_resolution KPI sanity, DeepEval cost ≤R$3/day, zero persist errors); (c) regression check on epic 005/008/010 test suites unaffected."
  blockers: []
  confidence: Alta
  kill_criteria: "(a) SAR fix triggers integration test failure in staging that wasn't caught at unit level → revert and investigate phase coupling. (b) NEW WARNING manifests in shadow Ariel that wasn't in this report (e.g. p95 regression from heuristic persist) → re-open Judge with focus on the regressed area. (c) 011.1 polish slips beyond 14d → escalate to product owner — NIT cleanup is non-blocking but accumulating debt deters epic 012 RAG (which builds on eval_scores schema)."
