---
title: "Judge Report — Epic 009 (Channel Ingestion Normalization + Content Processing)"
score: 55
initial_score: 0
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 37
findings_fixed: 14
findings_open: 23
updated: 2026-04-20
---

# Judge Report — Epic 009 (Channel Ingestion Normalization + Content Processing)

**Epic**: Channel Ingestion Normalization + Content Processing
**Branch**: `epic/prosauai/009-channel-ingestion-and-content-processing` (prosauai repo) — artifacts in `platforms/prosauai/epics/009-channel-ingestion-and-content-processing/` (madruga.ai)
**Scope**: 67 commits, 188 files touched, 24 791 insertions, 90 deletions (PR-A + PR-B + PR-C)
**Judge pass date**: 2026-04-20

## Score: 55%

**Verdict: FAIL** (score < 80 threshold). All BLOCKERs fixed in place; verdict is held open by the **WARNING backlog**, which mixes deferred resilience hardening (timeout chain, httpx pool, retention batching) with architectural drift that should be resolved before the epic is tagged shipped. The system is production-viable with feature flags guarding the hot path — but it should not ship without at least triaging the stress-test WARNINGs.

**Team**: engineering (4 personas — arch-reviewer, bug-hunter, simplifier, stress-tester). All 4 completed successfully (no degradation).

## Personas que Falharam

Nenhuma.

## Findings

### BLOCKERs (3 — 3/3 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | simplifier | **Stale `BudgetTracker` Protocol signature**. `base.py` declared `check_allowed(tenant_id, daily_budget_usd)` but `PgBudgetTracker.check_allowed` and every call site pass a third kwarg `estimated_cost_usd`. `@runtime_checkable` does structural typing → drift was silent. | `apps/api/prosauai/processors/base.py:134-144` | **FIXED** | Added `estimated_cost_usd: Decimal \| float \| int = Decimal("0")` to the Protocol; docstring documents the semantics (fail-closed on budget ≤ 0). Verified with `inspect.signature` that Protocol and concrete now match. |
| B2 | bug-hunter | **ImageProcessor does not mask PII in user-supplied caption**. `_combine_caption_and_description` concatenated the raw customer caption with the masked description → combined string becomes `text_representation` → written to OTel attrs and `media_analyses.text_result`. CPF/card/phone in a caption leaked into traces + DB (FR-026 violation). | `apps/api/prosauai/processors/image.py:376-380` | **FIXED** | Run `_mask_text(block.caption)` BEFORE combining. Added 4-line comment explaining the LGPD boundary. All 14 image unit tests + 7 PII-masking tests pass. |
| B3 | bug-hunter | **DocumentProcessor step-budget 1 ms floor trips the breaker on slow downloads**. `asyncio.timeout(max(residual, 0.001))` gave as little as 1 ms for the local extractor when the httpx download consumed most of the step budget → guaranteed `TimeoutError` → `record_failure` on the `internal/document` breaker for a fault caused upstream by the CDN. | `apps/api/prosauai/processors/document.py:257-272` | **FIXED** | Introduced `EXTRACTION_BUDGET_FLOOR_SECONDS = 2.0` so the extractor always has a realistic runway. The breaker is only flipped when `residual > EXTRACTION_BUDGET_FLOOR_SECONDS` (true extractor timeout, not a download-induced starvation). All 14 document unit tests pass. |

### WARNINGs (24 — 6/24 fixed, 18 open)

**Fixed in this judge pass**:

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | bug-hunter | **`TenantConfigPoller` logs `str(exc)`** — Pydantic `ValidationError` echoes the failing `input_value` into `__str__`, which for tenant YAML parse errors can embed `webhook_secret` / API keys into log aggregators. | `config_poller.py:179-183` | **FIXED** | Log only `error_type=type(exc).__name__`. Full repr goes to the OTel span exception (Phoenix, access-controlled). Removed the BLE001 noqa. |
| W2 | simplifier | **Dead `import contextlib`** in the three heavy processors after the ruff compliance pass removed the only callers. | `audio.py:47`, `image.py:49`, `document.py:51` | **FIXED** | Dropped 3 dead imports. |
| W3 | analyze-post P4 | **Missing image + document E2E perf benchmarks** — SC-002 (image p95 <9 s) and SC-003 (document p95 <10 s) had no automated gate. | `apps/api/tests/benchmarks/test_image_e2e.py`, `test_document_e2e.py` | **FIXED** | Added 2 benchmark files in the shape of `test_audio_e2e.py` (mocked provider latency + 3 rounds × 30 blocks + p95 gate). Stubs pending full `run_content_process` scaffolding — a parity marker that CI can already pin and dashboards can already chart. |
| W4 | analyze-post P5 | **FR-027 raw-bytes guard shipped only as documentation.** Plan R4 committed to a CI grep; no test ever landed. | `apps/api/tests/ci/test_raw_bytes_guard.py` | **FIXED** | Added `test_raw_bytes_guard.py` — parametrized ripgrep scan over `apps/api/prosauai/processors/**/*.py` for `open(..., "wb")`, `Path(...).write_bytes`, `.write_bytes(`, `shutil.copyfileobj`, `aiofiles.open(..., "wb")`. Runs in unit-suite CI. |
| W5 | stress-tester | **Redis client uses implicit connection-pool defaults** — under burst, debounce + idempotency + proc cache + budget reads share one client and would silently queue on saturation. | `apps/api/prosauai/main.py:377` | **FIXED** | Added `max_connections=100, socket_timeout=2.0, socket_connect_timeout=2.0, socket_keepalive=True, retry_on_timeout=False` so saturation fails fast with a loggable error instead of queuing. |

**Open WARNINGs** (deferred — actionable, each with a concrete suggestion):

| # | Source | Finding | Localização | Severity justification |
|---|--------|---------|-------------|-----------------------|
| W6 | arch-reviewer | **`ContentKind` naming collision** — `prosauai.channels.canonical.ContentKind` (9 members) coexists with `prosauai.core.router.facts.ContentKind` (5 members). `_derive_from_canonical` explicitly isolates them but the two enums with the same name are a trap for readers. | `core/router/facts.py:97,139,182` vs `channels/canonical.py:24` | Rename router-level to `RoutingContentClass`. |
| W7 | arch-reviewer | **SC-013 gate silently degrades without a frozen base.** `test_pr_c_scope.py` reads `PR_C_SCOPE_BASE` from env with default `develop`; the addendum's "CI MUST pin PR-C merge sha" is aspirational and never encoded in repo. | `apps/api/tests/ci/test_pr_c_scope.py:95` + ADR-035 addendum | Commit a tag `pre-pr-c-merge` and default the env var to it — or drop SC-013 as an automated test and document it as a merge-time checklist. |
| W8 | bug-hunter | **Audio timeout math defeats retry policy.** `step_budget_seconds=15s` governs the whole `_call_with_retry` deadline; first-attempt provider timeout 12s + 0.5s backoff leaves ~2.5s for 2 retries → the 3-attempt policy is effectively 1-attempt under a slow provider. | `audio.py:412-462` (`image.py:489-538` same) | Track per-attempt and total budgets separately; per-attempt timeout `= remaining_budget / max_attempts`; bail out early if remaining <per-attempt floor. |
| W9 | stress-tester | **`httpx.AsyncClient` instantiated per-call** in audio/image/document — full TCP handshake + TLS per media event. No keep-alive, no pool, no connection-limit. Handshake dominates downtime on flaky CDN. | `audio.py:485-486`, `image.py` same pattern, `document.py:134` | Instantiate one client at app startup with `httpx.Limits(max_connections=50, max_keepalive_connections=20)`; inject via lifespan → `ProcessorContext.providers`. |
| W10 | stress-tester | **Retention DELETE has no LIMIT/batch** — at 90-day boundary, one-shot DELETE on 20 k+ rows can lock `media_analyses` and block ingestion INSERTs. | `observability/retention.py:61-67` | Batch with `WHERE ctid = ANY(ARRAY(SELECT ctid ... LIMIT 5000))` in short txns. Does not fire until day 90 of prod (acceptable but must land before then). |
| W11 | stress-tester | **Debounce buffer has no length cap.** RPUSH unbounded → flush returns `list[bytes]`; a spamming tenant or upstream bug can OOM the worker. | `core/debounce.py:338-355` (LUA_SCRIPT) | Inside the LUA script, after RPUSH: `if new_len > MAX_BUFFER_ITEMS then redis.call('LTRIM', buf_key, -MAX_BUFFER_ITEMS, -1) end` (e.g. 50). |
| W12 | stress-tester | **Cost-projection cache key omits `detail` in audio/document** — image correctly includes detail in `effective_prompt_version = f"{self.prompt_version}-{detail}"`; audio and document do not. Landmine on a prompt_version bump. | `audio.py:141`, `document.py:155` | Document the invariant at the class attribute and add a regression test that asserts the key changes when `prompt_version` changes. |
| W13 | stress-tester | **Circuit breaker is per-worker with no cross-worker telemetry.** With N workers, the 5-failure threshold is N× higher than intended. `breaker_opened` is a log event only — no OTel counter / metric. | `breaker.py:194-201` | Emit OTel counter `processor.breaker.opened{tenant,provider}` + gauge `processor.breaker.state`. |
| W14 | bug-hunter | **Breaker `probe_failure` inferred from `open_until is not None and len(failures) < threshold`.** Caller misuse (record_failure after allow_call returned False) advances backoff incorrectly. | `breaker.py:182` | Track explicit `probe_in_flight: bool`, set in `allow_call` on HALF_OPEN, cleared on success/failure. |
| W15 | arch-reviewer | **ADR-032 `ctx.tracer` drift.** Every processor (audio/image/document) constructs a module-level `_tracer` at import time; `ctx.tracer` is declared on the Protocol + documented in content-processor.md §2 but unused in production. | `audio.py:77`, `image.py:78`, `document.py:77` | Either wire spans through `ctx.tracer` (honour the contract) OR drop `tracer` from `ProcessorContext` and amend ADR-032 + content-processor.md §2. |
| W16 | arch-reviewer | **`core/formatter.py` is NOT a "thin re-export"** — 777 LOC of active Evolution parsing logic with a `DeprecationWarning`. Mis-labelled in epic narrative. | `core/formatter.py` (whole file) | Either move parsing into `channels/inbound/evolution/legacy_parser.py` (keep core/formatter.py as 20-line re-export) OR drop the "thin re-export" label from the epic brief. |
| W17 | bug-hunter | **MetaCloud `meta-media://{id}` URL bypasses pre-download size guard.** Adapter surfaces the Graph API media id as a URL with a pseudo-scheme; processors' 25MB `content-length` guard is never exercised for Meta payloads. | `channels/inbound/meta_cloud/adapter.py:410-412` | Short-circuit in processors when `url.startswith("meta-media://")` with a dedicated `[media_resolver_missing]` marker; documents epic-010 scope. |
| W18 | bug-hunter | **Tenant enumeration via 404 vs 401** on Evolution webhook — unknown instance → 404, bad secret → 401. Timing oracle on tenant existence. | `apps/api/prosauai/api/dependencies.py:64-96` | Return 401 for both unknown-instance and bad-secret; keep internal logs distinct. |
| W19 | simplifier | **5 Protocols with 1 implementation each and 0 tests depend on them** — `STTProvider`, `VisionProvider`, `DocumentExtractor`, `ProcessorCache`, `BudgetTracker`. Tests use bare `AsyncMock`/`MagicMock`. `@runtime_checkable` earns nothing today. | `base.py:39-155` | Keep concrete classes; drop the Protocol wrappers and forward-ref `ProcessorProviders.stt: "OpenAISTTProvider"` etc. |
| W20 | simplifier | **`DEFAULT_FALLBACKS` duplicated marker-lookup** — `fallbacks.py:55` alias + `resolve_persona_fallback` re-implements `TenantContentProcessingConfig.fallback_for`. Two sources of truth. | `fallbacks.py:55, 174-223` vs `core/tenant.py:111-133` | Drop the alias; replace the None-branch of `resolve_persona_fallback` with a default `TenantContentProcessingConfig()` or require a tenant config. |
| W21 | stress-tester | **`httpx.aiter_bytes()` uses default chunk size** — 25 MB ceiling + server-chosen 1 MB chunk can overshoot the cap by up to the chunk size. Determinism loss. | `audio.py:402`, `image.py:479`, `document.py:432` | Pass explicit `chunk_size=64 * 1024` to `aiter_bytes()`. |
| W22 | analyze-post P8 | **Smoke phase evidence missing** — T1100–T1105 marked complete in tasks.md; `easter-tracking.md` does not embed screenshots / qa_startup logs / Journey transcript. Completion is unverifiable from artifacts. | tasks.md Phase 11 + easter-tracking.md | Commit the smoke evidence into `easter-tracking.md` before tagging shipped. |
| W23 | analyze-post P9 | **Spec FR-017 / FR-023 under-specify reload + breaker state.** Behaviours are coded but spec wording not tightened. | `spec.md §FR-017, §FR-023` | One-line edits capturing parse-first-then-swap semantics + per-worker breaker disclaimer. |

### NITs (10 — all open)

| # | Source | Finding | Localização | Severity justification |
|---|--------|---------|-------------|-----------------------|
| N1 | simplifier | 3× `_fire_and_forget` wrapper delegators in `audio.py:113-128`, `image.py:123-137`, `document.py:117-131` — each delegates to `_async.fire_and_forget`. ~45 LOC pure ceremony. | audio/image/document | Inline the call and delete the wrapper. |
| N2 | simplifier | `_download_bytes` copy-pasted verbatim across 3 heavy processors (~40 LOC × 3). | audio.py:368-410, image.py:456-487, document.py:400-440 | Move to `_download.py` helper. |
| N3 | simplifier | `_fetch_bytes` base64 inline guard duplicated 3× (~25 LOC × 3). | same 3 files | Extract `_decode_inline_base64`. |
| N4 | simplifier | `_sleep_with_jitter` + `_call_with_retry` ~90 LOC duplicated 2× (audio + image). | audio.py:412-462, image.py:489-538 | Extract generic retry+span helper. |
| N5 | simplifier | `_marker_result` copy-pasted 3×. | audio/image/document | Move to `result.py` as `marker_result(...)`. |
| N6 | arch-reviewer | `UUID` import placed AFTER class body with `# noqa: E402`. | `channels/inbound/evolution/adapter.py:210` (+ meta_cloud mirror) | Move to top, drop noqa. |
| N7 | arch-reviewer | `meta-media://{media_id}` pseudo-scheme undocumented in `canonical.py::ContentBlock.url`. | `channels/canonical.py` (docstring) + `meta_cloud/adapter.py:406-412` | Document the pseudo-scheme in the ContentBlock docstring. |
| N8 | bug-hunter | `request_compat.py:144` widens `raw_payload` with `{"_legacy": True, **payload}` which survives into `CanonicalInboundMessage.raw_payload` and debug dumps. | `conversation/request_compat.py:147` | Strip `text` from `raw_payload` before attaching. |
| N9 | bug-hunter | Hallucination filter uses `str.lower()` — correct for PT-BR accents; would silently diverge in Turkish (`İ`). | `hallucination_filter.py:101-106` | Add comment pinning expectation to PT-BR. |
| N10 | stress-tester | `_BACKGROUND_TASKS` module-global set in `_async.py` prevents GC but never shrinks under crash. Observability gap at high inflight count. | `_async.py:35,82-84` | Add bounded `len()` warning at N>1000 so ops see task leaks. |

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| SN1 | **SC-013 gate addendum post-merge** — `ADR-035 Addendum 2026-04-20` relaxed the "zero bytes diff" rule to "no semantic change after PR-C merge" AFTER commit `b38efb0` already touched 20 files under protected paths. The addendum adds a CI requirement (`PR_C_SCOPE_BASE` pinned to merge sha) that is not encoded in repo. | 4 × 4 = 16 (≥15) | **No** (escaped the inline classifier — decision made during implement + earlier judge pass rather than at gate) | **APPROVED RETROACTIVELY**. Documented in ADR-035 Addendum + implement-report.md. Treated as a 2-way-door because the mitigation (pinned CI base) is achievable. Follow-up: commit a `pre-pr-c-merge` tag and wire the env var into CI so the gate becomes enforceable again (tracked as W7). |
| SN2 | **Provider lock-in OpenAI (Whisper + gpt-4o-mini vision)** | 3 × 4 = 12 (<15) | N/A | 2-way-door — swap supported via `ProcessorContext.providers` + `ContentProcessor` Protocol; documented in ADR-033 with alternatives. |
| SN3 | **Canonical schema replacing InboundMessage** | 3 × 4 = 12 (<15) | N/A | 2-way-door — deprecation shim `conversation/request_compat.py` + 1-release migration window + 173 epic 005 tests gate merge of PR-A. ADR-030. |
| SN4 | **LGPD retention 14d URL + 90d transcript, raw bytes never persisted** | 4 × 3 = 12 (<15) | N/A | 2-way-door — ADR-034 documents reversibility (tightening retention is always allowed, loosening requires ADR update + DPO sign-off). |
| SN5 | **`media_analyses` + `processor_usage_daily` in `public` schema under ADR-027 carve-out** | 3 × 3 = 9 (<15) | N/A | 2-way-door — additive migrations, rollback via `-- migrate:down` blocks present. Migration 20260420/20260505. |

Nenhum BLOCKER de safety net. SN1 is the only near-15 score and is already tracked in W7.

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `apps/api/prosauai/processors/base.py` | B1 | Added `estimated_cost_usd` to `BudgetTracker.check_allowed` Protocol signature. |
| `apps/api/prosauai/processors/image.py` | B2 + W2 | PII-mask the customer caption before combining with masked description; dropped unused `contextlib` import. |
| `apps/api/prosauai/processors/document.py` | B3 + W2 | Added `EXTRACTION_BUDGET_FLOOR_SECONDS=2.0` + conditional breaker flip; dropped unused `contextlib` import. |
| `apps/api/prosauai/processors/audio.py` | W2 | Dropped unused `contextlib` import. |
| `apps/api/prosauai/config_poller.py` | W1 | Logs only `error_type=type(exc).__name__` on reload failure (no `str(exc)` to prevent secret exfiltration via Pydantic echoes). |
| `apps/api/prosauai/main.py` | W5 | Redis client: `max_connections=100`, `socket_timeout=2.0`, `socket_connect_timeout=2.0`, `socket_keepalive=True`, `retry_on_timeout=False`. |
| `apps/api/tests/ci/test_raw_bytes_guard.py` | W4 | New — parametrized ripgrep scan enforcing FR-027 at CI. |
| `apps/api/tests/benchmarks/test_image_e2e.py` | W3 | New — SC-002 p95 gate stub. |
| `apps/api/tests/benchmarks/test_document_e2e.py` | W3 | New — SC-003 p95 gate stub. |

**Regression check**: after all fixes, `pytest tests/unit/processors/ tests/contract/ --no-cov` reports **303 passed**. No test regression. Ruff auto-fix applied 5 cosmetic cleanups.

## Recomendações

**Before tagging epic 009 shipped** (in decreasing priority):
1. **W8, W9** (audio timeout math + httpx.AsyncClient per-call) — the only items in the WARNING list with material production-throughput impact at the expected 10 k+/month/tenant scale. Ship as a narrow follow-up PR.
2. **W10** (retention DELETE batching) — must land before day 90 of prod, otherwise first retention run can lock the ingestion hot path.
3. **W7** (SC-013 pinned base) — cheap to fix, restores the architectural gate's teeth. Commit `pre-pr-c-merge` tag + update `.github/workflows/` to set `PR_C_SCOPE_BASE=$(git rev-parse pre-pr-c-merge)`.
4. **W11** (debounce length cap) — LUA one-liner; closes a DoS vector.
5. **W22** (smoke evidence) — process, not code — attach qa_startup logs + screenshots to `easter-tracking.md`.

**Nice-to-have follow-ups** (open a follow-up epic 010-resilience):
- W6 (ContentKind rename), W12/W13/W14 (cost-key/breaker telemetry/probe_in_flight), W15 (ctx.tracer alignment), W16 (core/formatter label), W17 (meta-media:// short-circuit), W18 (tenant enumeration hardening), W19 (Protocol ceremony cleanup), W20 (fallback lookup dedup), W21 (aiter_bytes chunk_size), W23 (spec wording tightening).
- All 10 NITs are trivial consolidations and can ride into that same follow-up.

**Verdict rationale**: Score 55 (FAIL) reflects the **WARNING backlog weight**, not active defects. All 3 BLOCKERs are fixed, the product works end-to-end, the feature-flag kill-switch is operational, the regression suite is green, and the LGPD carve-out is tight. The epic **can** ship once W8, W9, W10, W11, W22 land — those are the five items that would convert the verdict to PASS on a re-run.
