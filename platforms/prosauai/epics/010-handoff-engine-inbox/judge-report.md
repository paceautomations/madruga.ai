---
title: "Judge Report — Epic 010 Handoff Engine + Multi-Helpdesk Integration"
score: 0
initial_score: 0
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 48
findings_fixed: 0
findings_open: 48
findings_deferred_to_follow_up: 48
updated: 2026-04-23
---

# Judge Report — Epic 010 Handoff Engine + Multi-Helpdesk Integration

## Score: 0%

**Verdict:** FAIL
**Team:** engineering (4/4 personas completed)
**Dispatch mode:** autonomous (no human in loop)
**Fix-phase status:** **DEFERRED** — this judge run cannot modify code in the `prosauai` repo (explicit harness constraint: writes only to `platforms/prosauai/epics/010-handoff-engine-inbox/`). All findings are `[OPEN]`; remediation is scheduled for a follow-up cycle (`/madruga:qa 010` or a dedicated post-judge fix PR) before PR-B / PR-C reach `develop`.

**Personas converged independently on 2 BLOCKERs** — when 2 of 4 reviewers surface the same issue without coordinating, the severity is locked in without further discussion.

---

## Executive Summary

Epic 010 ships a technically ambitious handoff engine: single-bit `conversations.ai_active`, `HelpdeskAdapter` Protocol + registry, `ChatwootAdapter` + `NoneAdapter`, 3 asyncio periodic schedulers, HMAC-authenticated webhook with Redis idempotency, shadow-mode rollout gate, admin composer emergency. `analyze-post-report.md` declared **zero CRITICAL findings at the artifact-level** — and the artifact analysis was correct; the issues uncovered here are **implementation-level bugs that a spec-consistency pass cannot catch**. The judge review converged on:

- **2 BLOCKERs** (implementation bugs — bot_sent_messages never populated in production wiring + fire-and-forget audit tasks GC-vulnerable) — **block PR-B / PR-C merge to develop**.
- **23 WARNINGs** spanning security (HMAC tolerance, CSRF, SSRF, cross-tenant idempotency collision), race conditions (pipeline FOR UPDATE vs pool_admin writes, outbound insert vs echo-check), scale (per-call httpx clients, missing rate limit, 32-bit advisory lock hash), and significant duplication (~240 LOC breaker, ~100 LOC cleanup crons, twin Result classes).
- **23 NITs** — ghost code (unemitted enum members, unused config fields, unread metadata keys), naming inconsistencies, and a reverse-lookup execution path (130 LOC) with zero unit test coverage.

**The existing 1909 passing tests do not catch the BLOCKERs** because they test the adapters in isolation (with a fully-wired EvolutionProvider in test fixtures) rather than the production lifespan wiring. A 20-minute integration test driving the full pipeline + asserting `bot_sent_messages` row-count would have flagged both.

**Recommendation**: **do not rollout Ariel → shadow until BLOCKERs are fixed**. PR-A is mergeable as-is (BLOCKERs manifest only in PR-B+ paths), but PR-B gate `off → shadow` is blocked until EvolutionProvider wiring is corrected in `main.py` and all `asyncio.create_task(persist_event(...))` sites gain a retained `_BACKGROUND_TASKS` set per the pattern already used elsewhere in the same codebase (`processors/_async.py:84`, `trace_persist.py:283`, `decision_persist.py:222`).

---

## Findings

### BLOCKERs (2 — 0/2 fixed, 2/2 deferred)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | bug-hunter + stress-tester (both persona convergence) | `EvolutionProvider` is constructed in `main.py:747-750` without `pool_admin`, `tenant_id`, or `conversation_id` arguments. The `_persist_sent` guard in `channels/outbound/evolution.py:106-110` requires all three to be truthy before inserting into `public.bot_sent_messages`. Consequence: `bot_sent_messages` **is never populated in production**. `NoneAdapter._is_bot_echo` (`handoff/none.py:344-357`) will therefore always miss the echo, and every `fromMe=true` ACK returned by Evolution **for the bot's own outbound message** will be classified as a human reply. When a tenant flips `handoff.mode: on` with `helpdesk.type: none`, the bot mutes itself after its first outbound message and auto-resumes after `human_pause_minutes` — a silent handoff loop that breaks User Story 4 (NoneAdapter) at rollout. Existing unit tests pass because `tests/unit/channels/outbound/test_evolution_bot_sent_messages.py` constructs `EvolutionProvider` with the full fixture. | `/home/gabrielhamu/repos/paceautomations/prosauai/apps/api/prosauai/main.py:747-750` vs `channels/outbound/evolution.py:106-110` vs `handoff/none.py:344-357` | OPEN | Deferred — fix in follow-up: pass `pool_admin=pools.admin, tenant_id=tenant.id, conversation_id=result.conversation_id` at EvolutionProvider construction inside `_flush_conversation`; add integration test asserting `SELECT COUNT(*) FROM bot_sent_messages WHERE message_id=$1` returns 1 after each successful `send_text`. |
| B2 | stress-tester | `asyncio.create_task(persist_event(...))` at `handoff/state.py:228, 297, 425, 499` and `admin/conversations.py:715` stores no strong task reference. CPython docs (`asyncio.create_task`, "Important" admonition) state tasks may be garbage-collected mid-execution if no reference is retained; under load this silently drops audit rows for both real and shadow transitions. This **violates FR-047a** (append-only contract) and **invalidates SC-012** (shadow-mode prediction ≤10% error vs real) because shadow events can vanish mid-write. The same codebase already uses the correct pattern in `processors/_async.py:84`, `trace_persist.py:283`, `decision_persist.py:222` — a module-level `_BACKGROUND_TASKS: set[asyncio.Task] = set()` with `task.add_done_callback(_BACKGROUND_TASKS.discard)`. | `handoff/state.py:228,297,425,499` + `admin/conversations.py:715` | OPEN | Deferred — fix in follow-up: introduce `_HANDOFF_BG_TASKS = set()` at module top of `handoff/state.py` and `admin/conversations.py`; wrap each `asyncio.create_task(...)` with `.add(task); task.add_done_callback(_HANDOFF_BG_TASKS.discard)`; graceful shutdown (lifespan) awaits the set with a timeout. Add a test that forces GC during `persist_event` execution and asserts the row is still written. |

### WARNINGs (23 — 0/23 fixed, 23/23 deferred)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | bug-hunter + arch-reviewer | Redis webhook idempotency key `handoff:wh:{chatwoot_event_id}` is **global across all tenants**. Plan.md A2 supports (a) shared Pace Chatwoot (current), (b) per-tenant Chatwoot in VPS. In case (b), two tenants' Chatwoot instances allocate overlapping auto-increment IDs; the second tenant's event is silently swallowed as `duplicate_webhook` and the mute/resume never runs. | `api/webhooks/helpdesk/chatwoot.py:63-64, 189` | OPEN | Prefix with resolved tenant: `f"{_WEBHOOK_IDEMPOTENCY_PREFIX}{tenant.slug}:{chatwoot_event_id}"`; add regression test sending same `event_id` from two distinct tenants and asserting both process normally. Update decisions.md §7. |
| W2 | bug-hunter + stress-tester | Pipeline safety-net `SELECT ai_active FOR UPDATE` at `conversation/pipeline.py:1339-1352` holds the row lock only while reading, releasing it before the LLM call. Concurrent `state.mute_conversation` (via pool_admin) bypasses RLS and flips `ai_active=false` **between the FOR UPDATE read and the LLM call** — pipeline proceeds to call the LLM and deliver a message on a just-muted conversation. The advisory lock in `state.mute_conversation` uses the same `hashtext(conversation_id)` namespace as none of the pipeline code, so there's no serialization. | `conversation/pipeline.py:1339-1352` vs `handoff/state.py:251-286` | OPEN | Before the `FOR UPDATE` read in the generate safety net, execute `SELECT pg_advisory_xact_lock(hashtext($1::text))` on the same connection with `conversation_id`. Use the identical key as state.mute/resume so pipeline serialises through the same mutex. Document the residual window (lock held for ~N ms during LLM call) in ADR-036. |
| W3 | stress-tester + arch-reviewer | Race between outbound `bot_sent_messages` INSERT (fire-and-forget in `channels/outbound/evolution.py:106-110`) and inbound `fromMe` echo-detection (`handoff/none.py:_is_bot_echo`). Evolution's outbound-ack webhook can arrive before the background INSERT has committed; the 10-second `BOT_ECHO_TOLERANCE_SECONDS` covers clock drift but not "not-yet-committed row". | `channels/outbound/evolution.py:106-110` + `handoff/none.py:327-365` | OPEN | Make the INSERT synchronous inside `send_text` before returning (p99 impact ~2ms, after the network hop — acceptable), OR maintain an in-process `set[(tenant_id, message_id)]` with TTL 10s that `_is_bot_echo` consults first. Synchronous is simpler and closes the window deterministically. |
| W4 | bug-hunter | HMAC verify uses exact `hmac.compare_digest(signature, expected)` without stripping whitespace, lowercasing, or handling a `sha256=` prefix. If Chatwoot changes its signature format, or an intermediate proxy uppercases the hex header, every webhook returns 401. | `handoff/chatwoot.py:173-182` | OPEN | Strip whitespace, strip any `sha256=` prefix, compare case-insensitively. Pin the accepted format via regression test. |
| W5 | bug-hunter | `ChatwootAdapter._resolve_config` dereferences `tenant_id` with `UUID(str(tenant_id))`; when the admin composer finds a conversation whose `tenant_id` column is NULL, it passes `tenant_uuid=None` → `UUID("None")` → `ValueError` → HTTP 500 instead of the documented 409 `no_helpdesk_configured`. | `handoff/chatwoot.py:600-613` reached from `admin/conversations.py:605, 655-661` | OPEN | In `_resolve_config`, short-circuit with `HelpdeskNotConfigured` when `tenant_id is None`. Alternatively, have the composer endpoint raise 409 explicitly when `tenant_uuid is None`. |
| W6 | bug-hunter | `HandoffScheduler.stop` awaits in-flight tasks with `SHUTDOWN_GRACE_SECONDS=5.0`, but each auto-resume tick can process up to 100 conversations (each acquiring its own pool connection + advisory lock + 2 roundtrips). Under a slow DB the batch easily exceeds 5s → `handoff_scheduler_shutdown_timeout` logged while `resume_conversation` is still mid-commit, leaving `persist_event` create_tasks scheduled after loop cancellation (see B2). | `handoff/scheduler.py:155, 262-311` + `handoff/state.py:499-502` | OPEN | Drop batch size during shutdown, OR increase grace proportional to `batch_size * per_row_budget`. Track post-commit `persist_event` tasks (fix via B2) and await them explicitly on shutdown. |
| W7 | bug-hunter | `mute_conversation` idempotent branch returns the *current* reason but does not re-mute when a higher-priority source arrives on an already-muted conversation. Example: `fromMe_detected` mute with `auto_resume_at=T1` wins; a subsequent `chatwoot_assigned` (higher priority, longer implicit timeout) silently loses; the scheduler resumes the bot while the human is actually still assigned in Chatwoot. | `handoff/state.py:262-276` | OPEN | Define explicit source-priority table (mirror `_RESUME_PRIORITY_INDEX`). When incoming source outranks stored, update `ai_muted_reason` + `ai_auto_resume_at` inside the same advisory-lock transaction and emit a `muted` event marking the escalation. |
| W8 | bug-hunter | `NoneAdapter._is_bot_echo` returns `False` on DB failure (including transient pool exhaustion). Combined with B1 this means a flaky admin DB auto-mutes on every bot outbound echo. The docstring's "fail-open" rationale is backward: fail-open here actually **triggers** unintended mutes. | `handoff/none.py:341-365` | OPEN | Treat lookup failure as "skip mute" (return `True` from `_is_bot_echo` so the mute is suppressed). Update docstring: fail-safe here is not muting, because the alternative is muting the bot on its own messages. |
| W9 | bug-hunter | `_reverse_lookup_via_chatwoot_api` interpolates webhook-provided `external_conversation_id` directly into the request URL without validating that it is numeric. Post-HMAC it is trusted, but with a leaked webhook secret an attacker can coerce arbitrary API paths under the Chatwoot host (path traversal / SSRF). | `handoff/chatwoot.py:730-733` | OPEN | Validate `external_conversation_id.isdigit()` (or `int(...)` try/except) before interpolating; reject otherwise with `InvalidPayloadError`. |
| W10 | bug-hunter | `admin/conversations.py` reply endpoint maps every `HelpdeskAPIError` to 503 `helpdesk_unavailable`, including 4xx responses (401/403/404). Mapping 404 "conversation not found in Chatwoot" to 503 tells the operator to retry indefinitely on a broken linkage. | `admin/conversations.py:668-691` | OPEN | Branch on `exc.http_status`: map 4xx (except 429) to 409/422 with a specific error code; keep 503 only for 5xx / breaker-open. |
| W11 | bug-hunter | Admin endpoints `/mute`, `/unmute`, `/reply` are cookie-authed with `SameSite=Lax` and no CSRF token. Epic 010 added destructive endpoints widening the blast radius of the pre-existing (epic 007) pattern. | `admin/conversations.py:332-512` + `auth_routes.py:153` | OPEN | Add double-submit CSRF token, OR require a custom header (e.g. `X-Admin-Csrf`) that attackers cannot set cross-origin. Noted as pre-existing from epic 007, but the destructive surface area grew. |
| W12 | arch-reviewer | ADR-027's "fail-loud" guarantee for admin-only tables requires explicit `REVOKE ALL ... FROM authenticated` on `handoff_events` and `bot_sent_messages`. The migrations rely on the epic 008 pattern (grant only to `service_role`) but a blanket `ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public GRANT ... TO authenticated` (migration `20260415000001:101-103`) silently gives CRUD to the tenant role. ADR-027's "InsufficientPrivilegeError from pool_tenant" regression test will pass 0-row reads instead of failing loudly. | `db/migrations/20260501000002_create_handoff_events.sql:55-56` + `db/migrations/20260501000003_create_bot_sent_messages.sql:38-39` | OPEN | Add `REVOKE ALL ON public.handoff_events FROM PUBLIC, authenticated;` + symmetric on `bot_sent_messages`. Backfill to epic 008 tables (`traces`, `trace_steps`, `routing_decisions`) in a separate migration. |
| W13 | stress-tester | `ChatwootAdapter` creates a fresh `httpx.AsyncClient(timeout=10.0)` per call (push_private_note, send_operator_reply, reverse-lookup). Every handoff assignment incurs a full TCP+TLS handshake to Chatwoot (~150ms) and consumes ephemeral ports. The `shared_http_client` pattern is already wired in `main.py:169-177` and used by content processors. | `handoff/chatwoot.py:437-442, 549-558, 735-744` + `main.py:329-335` | OPEN | Pass `http_client=shared_http_client` at `ChatwootAdapter` construction in lifespan; keep the `httpx.AsyncClient(timeout=10.0)` fallback for unit tests. |
| W14 | stress-tester | Webhook endpoint has no payload size limit or per-tenant rate limit. `await request.body()` reads full body before HMAC check; no `slowapi` `@limiter.limit(...)`. A misbehaving Chatwoot instance or leaked secret can flood → HMAC + Redis SETNX + 2 PG roundtrips + fire-and-forget persist per request → saturate pool_admin → starve other tenant's pipeline. | `api/webhooks/helpdesk/chatwoot.py:67-76` | OPEN | Add `@limiter.limit("120/minute")` keyed by `tenant_slug`; assert `int(request.headers.get("content-length","0")) < 64_000` before reading body (Chatwoot payloads are <5KB in practice). |
| W15 | stress-tester | No retry with jittered exponential backoff on transient Chatwoot 5xx/429. All 5 failures accumulate within ~60s, trip breaker OPEN for 30s/60s/120s/…/300s. Compounds with fresh-client-per-call (W13) during a Chatwoot outage: each TLS-handshake-timeout consumes the full 10s per attempt. | `handoff/chatwoot.py:435-458, 549-594` | OPEN | Add single retry for 429/503 with `backoff = random.uniform(0.25, 1.0) * 2**attempt` capped at 5s, max 2 attempts, for `push_private_note` only (admin composer stays single-shot to bound UI latency). Parse `Retry-After` on 429. |
| W16 | stress-tester | `handoff_events` indexes `(tenant_id, created_at DESC)` + `(conversation_id, created_at DESC)` do not cover Performance AI's shadow-exclusion filter. At 10x scale (~9M rows) the planner scans all per-tenant rows in the window and post-filters `shadow = FALSE`. | `db/migrations/20260501000002_create_handoff_events.sql:38-43` | OPEN | Add partial index `CREATE INDEX idx_handoff_events_real_tenant_created ON public.handoff_events (tenant_id, created_at DESC) WHERE shadow = FALSE`. Negligible size during shadow rollout; major post-cutover improvement. |
| W17 | stress-tester | `pg_advisory_xact_lock(hashtext($1::text))` uses `hashtext()` which returns int4 → 32-bit keyspace. UUID birthday collision reaches ~1% at 10k conversations, ~70% at 100k. Collisions don't deadlock but serialize unrelated mute/resume transitions, defeating the per-conversation granularity claimed in plan.md §Constitution Check. | `handoff/state.py:65` | OPEN | Use 2-arg form with a namespace classid (e.g. 77 for "handoff") and `hashtextextended(conversation_id::text, 0)::bigint` to widen to 64 bits; OR document known-acceptable risk at 2-tenant scale in plan.md R-section. |
| W18 | stress-tester | `DELETE … WHERE ctid IN (SELECT ctid FROM … WHERE sent_at < … LIMIT 5000)` has no `ORDER BY`. At 100k rows/tenant/48h, a 12h tick deletes 10k while insert rate is ~2k/h = 48k/48h → cron keeps up but zero headroom at 10x. ctid-subquery is also slower than explicit DELETE with ORDER BY. | `handoff/scheduler.py:509-517` | OPEN | Raise `BOT_SENT_MESSAGES_CLEANUP_BATCH_SIZE` to 25k (well-indexed DELETE stays <500ms) OR raise cadence from 12h to 3h (either gives 4x headroom). |
| W19 | simplifier | `handoff/breaker.py` (272 LOC) is ~95% copy-paste of `processors/breaker.py` (247 LOC). Identical state machine, same constants, differs only in key semantics + 20 lines emitting `helpdesk_breaker_open` Prometheus counter. Two copies = two places to fix the next bug. | `handoff/breaker.py:1-272` vs `processors/breaker.py:1-247` | OPEN | Parameterise generic `CircuitBreaker` with optional `on_open: Callable` hook (or `metric_name: str`). Delete `handoff/breaker.py`. Net saving: ~240 LOC + one class to maintain. |
| W20 | simplifier | `MuteResult` and `ResumeResult` in `state.py:73-131` are structurally identical (same 5 fields, same `__slots__`). Callers treat them uniformly. | `handoff/state.py:73-131` | OPEN | Collapse to single `TransitionResult` dataclass. Saves ~60 LOC. |
| W21 | simplifier | `run_bot_sent_messages_cleanup_once` and `run_handoff_events_cleanup_once` in `scheduler.py:505-752` are the same function with different table/retention. Same `pg_try_advisory_lock` → `DELETE … WHERE ctid IN (SELECT ctid … LIMIT)` → `pg_advisory_unlock` shape. ~220 LOC for one templated cleanup cron. | `handoff/scheduler.py:505-752` | OPEN | Extract `run_retention_cleanup_once(pool, *, table, retention_column, retention_value, lock_key, batch_size)` helper. Saves ~100 LOC and guarantees drift-free behavior. |
| W22 | simplifier | `_reverse_lookup_via_chatwoot_api` (130 LOC) has **no unit tests**. Grep for `reverse_lookup` in `tests/` → zero hits. 4 distinct early-return paths + network + DB write — unverifiable from the suite. This amplifies W9 (SSRF) since untested code has unknown behavior. | `handoff/chatwoot.py:706-834` | OPEN | For PR-B: either add `respx`-mocked unit tests covering all 4 return paths + the URL-interpolation edge case, OR feature-flag the fallback off until exercised. |
| W23 | simplifier | Shadow mode persists `metadata.real_ai_active_would_be` + `metadata.priority_index` on every event, but nothing in the codebase queries those keys. `db/queries/performance.py` does not reference `priority_index`; `apps/admin/src` does not either. Tests assert field existence; production never reads. Scaffolding without a consumer. | `handoff/state.py:225, 356-360, 487-490` | OPEN | Either wire the dashboard consumer that was documented as rationale, OR stop populating these keys in `metadata`. `_RESUME_PRIORITY_INDEX` serving only its own output is dead. |

### NITs (23 — 0/23 fixed, 23/23 deferred — all are OPEN, not skipped)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | arch-reviewer | Registry naming divergence: `channels.registry.get(source)` vs `handoff.registry.get_adapter(helpdesk_type)`. Docstrings explicitly reference each other as precedent. | `handoff/registry.py:46` vs `channels/registry.py:31` | OPEN | Rename `handoff.registry.get_adapter` → `handoff.registry.get` (keep `get_adapter` as alias if tests hard-code it). |
| N2 | arch-reviewer | `mute_conversation`/`resume_conversation` docstrings describe the `pool` arg as "the caller is expected to pass the correct pool" — ambiguous given ADR-027's epic 010 extension explicitly mandates `pool_admin`. | `handoff/state.py:171-173` | OPEN | Tighten docstring: "MUST be pool_admin (BYPASSRLS)". Optionally tag pools at creation and assert. |
| N3 | bug-hunter | `persist_event` fire-and-forget task (subset of B2) — dropped silently on shutdown, no log line. | `handoff/state.py:297-300, 499-502` | OPEN | Already covered by B2 fix (retain tasks in module-level set; await in lifespan shutdown). |
| N4 | bug-hunter | `_extract_event_id` returns `None` silently when `id`/`webhook_id`/`event_id` all missing, disabling idempotency for the request. | `api/webhooks/helpdesk/chatwoot.py:182, 188, 331-341` | OPEN | Log `chatwoot_webhook_missing_event_id` at WARNING when None. |
| N5 | bug-hunter | `_resolve_handoff_mode` in `admin/conversations.py` falls back to `"on"` when tenant store is not wired, contradicting `chatwoot.py:_resolve_handoff_mode` default of `"off"` (fail-closed). | `admin/conversations.py:190-214` vs `handoff/chatwoot.py:624-643` | OPEN | Unify to fail-closed (`"off"`). |
| N6 | bug-hunter | `send_operator_reply` builds content as `f"[{sender_name}] {text}"` — a malicious admin could embed newlines/markdown to spoof system messages. | `handoff/chatwoot.py:539` | OPEN | Strip control chars from `sender_name`, cap length; or move identity to `content_attributes` and drop visible prefix. |
| N7 | simplifier | Dead enum values: `HandoffEventType.BREAKER_OPEN`, `BREAKER_CLOSED`, `HandoffEventSource.RULE_MATCH`, `SAFETY_TRIP` declared but no code emits them. | `handoff/events.py:47-48, 57-58` + `admin/conversations.py:102-103` + `admin/schemas/conversations.py:54-55` | OPEN | Delete unused members; re-add when feature wires up. |
| N8 | simplifier | `HelpdeskAdapter` Protocol + `registry` + `_REGISTRY` dict at N=2 adapters is defensible but speculative. `UnknownHelpdesk` error + `registered_helpdesks()` introspection don't pay for themselves yet. | `handoff/base.py:137-284`, `handoff/registry.py:1-84` | OPEN | Accept as-is; revisit if epic 011/012 adds a third adapter. Document as "acknowledged over-abstraction for extensibility, N=2 baseline". |
| N9 | simplifier | `push_private_note` is Protocol-specified, implemented on both adapters + tested, but **no production caller** exists. Docstring implies it's "used to forward AI-transcribed content"; pipeline does not wire it in. | `handoff/base.py:231-254` + `handoff/chatwoot.py:390-458` + `handoff/none.py:162-178` | OPEN | Either wire audio/image processors now (original intent), OR delete the method until a consumer exists. ~80 LOC of ghost code. |
| N10 | simplifier | `NoneAdapter.get_handoff_config` constructor parameter accepted + stored (line 111) but **never read**. Docstring admits "reserved for future ergonomics". | `handoff/none.py:94-111` | OPEN | Delete parameter + attribute; re-add when a consumer exists. |
| N11 | simplifier | `ChatwootHelpdeskConfig.inbox_id` read only as fallback in `_reverse_lookup_via_chatwoot_api`, stored in `external_refs` but no downstream filters on it. | `handoff/chatwoot.py:83, 88, 95, 101, 772, 819` | OPEN | Drop `inbox_id` from config + tenants.yaml schema until a feature needs it. |
| N12 | simplifier | `handoff/__init__.py` docstring lists `bot_sent.py` and `external_refs.py` as modules inside `handoff/` — those files live in `db/queries/`. Doc drift. | `handoff/__init__.py:7-8` | OPEN | Delete bullets or point them at actual modules. |
| N13 | simplifier | `HandoffScheduler.register` raises `RuntimeError` if called after `start()` — no caller registers dynamically. | `handoff/scheduler.py:221-239` | OPEN | Enforce via frozen constructor OR drop running-state guard. |
| N14 | simplifier | Cron tick-log policy inconsistency: cleanup crons log only `if deleted > 0`; auto-resume logs only `if selected > 0`. Three crons, three rules. | `scheduler.py:461, 590, 718` | OPEN | Log on every iteration (with zeros) or never — consistency beats micro-optimisation on a 60s+ cron. |
| N15 | stress-tester | Shadow-mode task name `handoff_shadow_event_{id}` uses UUID generated per mute — unique per call, but still suffers B2's task-retention bug. | `handoff/state.py:228-230, 425-427` | OPEN | Covered by B2 fix. |
| N16 | stress-tester | `CircuitBreaker` uses `threading.Lock()` inside a single-event-loop asyncio app. Uncontended but adds kernel-level atomic ops and may mislead maintainers into assuming multi-thread safety. | `handoff/breaker.py:48, 134` | OPEN | Replace with `asyncio.Lock` OR drop the lock (state updates are already single-threaded under uvicorn). |
| N17 | stress-tester | `run_auto_resume_once` releases the advisory lock before processing the batch. Two replicas whose ticks align (<few ms gap) can process the same 100-row slice; the per-conversation advisory lock in `resume_conversation` and the `ai_active` idempotency branch handle it correctly, but this creates duplicated DB round trips at 10x scale. | `handoff/scheduler.py:402-413` | OPEN | Use `SELECT ... FOR UPDATE SKIP LOCKED` on pending rows inside the same connection that holds the cron advisory lock, processed inline. |
| N18 | arch-reviewer + bug-hunter (echo) | Error messages in `chatwoot.py` occasionally leak internal state (e.g., Chatwoot API URL fragments in structured logs). Low severity, flagged for ops-log privacy. | Various log calls in `handoff/chatwoot.py` | OPEN | Audit log fields; redact full URLs to `chatwoot.example/conversations/<id>` pattern. |
| N19 | stress-tester | `handoff_duration_seconds_bucket` metric defined but no verification that custom buckets fit expected handoff durations (minutes to hours, not the default Prometheus buckets of 0.005..10s). | `observability/metrics.py` | OPEN | Override `buckets=[60, 300, 1800, 3600, 21600, 86400]` (1min .. 24h). |
| N20 | simplifier | Spec + decisions refer to "shadow mode" as removable post-validation (A13), but no code comment or deprecation warning signals this. Future developers may treat it as permanent. | `handoff/state.py` shadow branch | OPEN | Add `# DEPRECATION: shadow mode is removable post-rollout — see A13` marker at shadow branch. |
| N21 | bug-hunter | Webhook handler logs `duplicate_webhook` at INFO but does not emit a metric counter. Spike in duplicates (misconfigured Chatwoot retries) is unobservable in dashboards. | `api/webhooks/helpdesk/chatwoot.py` around SETNX check | OPEN | Add `helpdesk_webhook_duplicate_total{tenant, helpdesk}` counter. |
| N22 | arch-reviewer | `contracts/helpdesk-adapter.md` specifies 5 methods but implementation reality is 6 (including `parse_webhook_event`). Doc drift between contract and code. | `contracts/helpdesk-adapter.md` vs `handoff/base.py` | OPEN | Sync contract doc to list all 6 methods OR rename/merge if `parse_webhook_event` is internal-only. |
| N23 | stress-tester | `admin/conversations.py` reply endpoint does not bound `content` size; Chatwoot's own API rejects >4096 chars but the 400 response bubbles up as generic 503. | `admin/conversations.py:605` + schema | OPEN | Enforce `content: str = Field(max_length=3500)` in the request schema; map Chatwoot 400 responses to 422. |

---

## Safety Net — Decisões 1-Way-Door

Scan of the epic branch (`epic/prosauai/010-handoff-engine-inbox`, 248 commits) against the Decision Classifier patterns:

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | New `conversations.ai_active` column (migration) | Risk 3 × Reversibility 1 = 3 | n/a (not inline-detectable — design-phase decision) | **APPROVED via ADR-036** (captured in `decisions.md` Decision 1). Aditiva migration; `handoff.mode: off` default protects rollout. 2-way-door via config flip. |
| 2 | New admin-only tables `handoff_events` (90d retention) + `bot_sent_messages` (48h) in `public.*` | Risk 3 × Reversibility 2 = 6 | n/a | **APPROVED via ADR-027 extension** (decisions.md Decision 17). Carve-out precedent from epic 008 (`traces`, `trace_steps`). |
| 3 | `HelpdeskAdapter` Protocol pattern + registry | Risk 2 × Reversibility 3 = 6 | n/a | **APPROVED via ADR-037**. Espelha `ChannelAdapter` (epic 009, ADR-031). Reversible — if abandoned, inline if/else at N=2. |
| 4 | Expose admin user email in Chatwoot (composer `sender_name`) | Risk 4 × Reversibility 3 = 12 | n/a (captured in clarify session Q4-A) | **APPROVED with risk accepted**. Documented trade-off in spec A14 + pitch Decision 15 + risk R9. Fallback to shared "Pace Ops" agent is ~30 LOC if needed. |
| 5 | Redis idempotency namespace `handoff:wh:{event_id}` NOT tenant-scoped | Risk 3 × Reversibility 5 = 15 | **NO — escaped** | **ESCAPED 1-WAY-DOOR CANDIDATE**. Elevates W1 in this report: if Pace onboards a second tenant with an independent Chatwoot instance (per Plan A2 case (b)), cross-tenant event_id collisions silently swallow real webhooks. Reversibility is now 5 (tenant-scope requires migration of in-flight Redis keys OR hard cutover window). **Recommendation**: tenant-scope the key before PR-B reaches prod. Already captured as W1. |
| 6 | Advisory lock via `hashtext()` (32-bit) | Risk 2 × Reversibility 4 = 8 | **NO — escaped** | **ESCAPED**. W17 in this report. 32-bit hash keyspace creates collision-probability that scales with active conversations. Acceptable at 2 tenants, problematic at scale. Recommendation: widen to 64-bit via `hashtextextended` + namespace classid. |
| 7 | Shadow mode as a 3-state flag rather than 2-state | Risk 2 × Reversibility 2 = 4 | n/a | **APPROVED via clarify session Q3-B** (decisions.md Decision 14). Removable post-validation per A13. |
| 8 | `EvolutionProvider` production wiring missing `pool_admin` / `tenant_id` / `conversation_id` | Risk 5 × Reversibility 1 = 5 | **NO — escaped implementation regression, not design** | **IMPLEMENTATION BUG — not a design decision**. Classified as BLOCKER B1 above. Not a 1-way-door — fix is ~3 lines in `main.py`. Flagged separately for process improvement: integration tests covering the full lifespan pipeline (not adapter-in-isolation) would catch this class of regression. |

**Summary**: 2 escaped 1-way-door candidates (W1 Redis idempotency + W17 hashtext collision). Both are **already surfaced as WARNINGs** above with remediation paths. Neither requires reverting a completed task — both are forward-fix in PR-B scope before staging rollout.

---

## Personas que Falharam

Nenhuma. All 4 personas completed with valid `PERSONA:` + `FINDINGS:` output format. Usage: arch-reviewer 177k tokens / 259s, bug-hunter 139k / 319s, simplifier 123k / 236s, stress-tester 133k / 248s.

---

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| — | 0 | **Fix phase deferred.** This judge run was executed under the autonomous dispatch harness constraint `Save ALL output to platforms/prosauai/epics/010-handoff-engine-inbox/` — writes outside the epic directory are explicitly disallowed. All 48 findings (2 BLOCKER + 23 WARNING + 23 NIT) apply to code in the sibling `paceautomations/prosauai` repo on branch `epic/prosauai/010-handoff-engine-inbox`; remediation is scheduled for a follow-up fix PR (or `/madruga:qa 010`) that can write to both repos. |

---

## Recomendações

### Immediate (before PR-B reaches `develop`)

1. **Fix B1 (EvolutionProvider wiring)** — 3-line change in `main.py:747-750`. Add integration test asserting `bot_sent_messages` row-count after `send_text`. Without this, **NoneAdapter tenants will auto-mute themselves on every bot reply when `handoff.mode: on`**.
2. **Fix B2 (Fire-and-forget task retention)** — replicate the `_BACKGROUND_TASKS` pattern from `processors/_async.py:84` at each of the 5 `asyncio.create_task(persist_event(...))` sites in `handoff/state.py` + `admin/conversations.py`. Await the set on lifespan shutdown. Without this, shadow-mode validation (SC-012) produces misleading metrics because events can vanish before insert.
3. **Fix W1 (Redis idempotency tenant-scoping)** — prefix Redis key with `tenant.slug`. Update `decisions.md §7` to reflect the change. Small patch, large correctness gain.

### Before PR-B rollout to staging

4. **W2, W3** (race conditions — pipeline safety-net lock, bot_sent_messages insert timing)
5. **W8** (`_is_bot_echo` fail-open inversion — current behavior causes mutes instead of suppressing them)
6. **W13** (shared httpx client — 150ms per handoff call savings + ephemeral port conservation)
7. **W14** (webhook rate limit + payload size — tenant isolation under DOS)

### Before epic 010 closes (PR-C + rollout runbook)

8. **W4, W5, W9, W10, W11** (security and error-handling gaps)
9. **W19, W20, W21** (~300 LOC of defensible deduplication — breaker, Result classes, cleanup crons)
10. **W22** (add tests or feature-flag the reverse-lookup — currently 130 LOC untested execution path)

### Long-term / epic 010.1

11. **W17** (hashtext collision widening — required if scaling past 2 tenants, each with >10k active conversations)
12. **W16** (partial index for shadow-filter — materializes only post-cutover)
13. **N9, N10, N11, N7** (prune ghost code, unemitted enum values, unused config fields)
14. **N8** (revisit Protocol+registry overhead when N=3 adapters arrives)

### Process improvement

15. **Integration-test gap**: existing unit tests for `EvolutionProvider` tracking construct the provider with the full fixture, masking the production-wiring regression (B1). Add a lifespan-level test that boots the FastAPI app + runs one inbound → assert `bot_sent_messages` grew by 1. This class of "adapter tested in isolation but not wired correctly in production" is a recurring pattern and would benefit from a harness-level smoke test.

---

## Gate Verdict

**FAIL** (score 0, 2 confirmed BLOCKERs). Epic 010 **must not advance to the Ariel `off → shadow` staging flip** until B1 and B2 are fixed. PR-A remains mergeable (BLOCKERs manifest only in paths exercised by PR-B+). Recommend scheduling a dedicated fix PR against `epic/prosauai/010-handoff-engine-inbox` resolving at minimum the 3 BLOCKERs-or-critical items (B1, B2, W1) before PR-B merges to `develop`.

---

handoff:
  from: madruga:judge
  to: madruga:qa
  context: "Judge review complete with 48 findings (2 BLOCKER + 23 WARNING + 23 NIT). Verdict FAIL (score 0). Fix phase deferred — harness constraint blocks writes outside epic dir. 2 escaped 1-way-door candidates documented (Redis idempotency namespace W1 + hashtext advisory lock W17). Recommend fix PR against epic branch resolving B1 + B2 + W1 before PR-B merges to develop; remaining warnings can ship progressively in PR-B/PR-C."
  blockers: [B1 EvolutionProvider production wiring, B2 Fire-and-forget task retention]
  confidence: Alta
  kill_criteria: "If fix PR resolving B1/B2/W1 is not landed before Ariel `off → shadow` flip, rollout MUST be paused — B1 produces silent handoff loop on first NoneAdapter outbound; B2 invalidates shadow-mode SC-012 validation data; W1 causes silent event drop under multi-Chatwoot tenant topology (Plan A2 case (b))."
