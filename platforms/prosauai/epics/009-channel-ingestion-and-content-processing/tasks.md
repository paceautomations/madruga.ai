# Tasks: Channel Ingestion Normalization + Content Processing

**Input**: Design documents from `platforms/prosauai/epics/009-channel-ingestion-and-content-processing/`
**Prerequisites**: plan.md (required), spec.md (7 user stories), research.md, data-model.md, contracts/ (channel-adapter.md, content-processor.md, openapi.yaml)
**Target repo**: `paceautomations/prosauai` (base branch `develop`); current branch `epic/prosauai/009-channel-ingestion-and-content-processing`

**Tests**: INCLUDED — spec SC-010 requires 173+191 existing tests to pass + ≥90% coverage on new processors + contract tests for Protocols (hard gate for merge).

**Organization**: 11 phases grouped by Shape Up PR (A → B → C) and within each PR by user story priority (P1 → P2 → P3). Each user story phase is independently testable and maps 1:1 to spec.md US1–US7. Deployment Smoke phase auto-appended because `platforms/prosauai/platform.yaml::testing` block is present (`startup.type: docker`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1..US7). Setup / Foundational / Polish / Smoke phases carry no story label
- File paths use absolute layout from the prosauai repo root (`apps/api/prosauai/...`)

---

## Phase 1: Setup (Shared Infrastructure — PR-A prep)

**Purpose**: Workspace preparation, dependency install, PR template. No behavioral change.

- [x] T001 Ensure working directory is the prosauai repo (`paceautomations/prosauai`) on branch `epic/prosauai/009-channel-ingestion-and-content-processing`, rebased on `origin/develop`. Run `python3 $REPO_ROOT/.specify/scripts/ensure_repo.py prosauai` from madruga.ai to verify the mapping
- [x] T002 [P] Add Python dependencies to `apps/api/pyproject.toml` (or `requirements.txt`): `openai>=1.50`, `pypdf>=4.0`, `python-docx>=1.1`. Regenerate lockfile if applicable
- [x] T003 [P] Add `OPENAI_API_KEY`, `META_CLOUD_APP_SECRET`, `META_CLOUD_VERIFY_TOKEN`, `CONTENT_PROCESSING_POLL_INTERVAL_SECONDS=60` placeholders to `apps/api/.env.example`
- [x] T004 [P] Create `.github/PULL_REQUEST_TEMPLATE.md` in prosauai repo (if missing) with sections: Description, User Stories served, SC gate checklist, Rollback plan, Observability plan (24h metrics to watch)
- [x] T005 [P] Create `apps/api/prosauai/channels/__init__.py`, `apps/api/prosauai/channels/inbound/__init__.py`, `apps/api/prosauai/channels/outbound/__init__.py`, `apps/api/prosauai/processors/__init__.py`, `apps/api/prosauai/processors/providers/__init__.py`, `apps/api/prosauai/api/webhooks/__init__.py`, `apps/api/prosauai/pipeline/steps/__init__.py` (ensure namespace packages exist)
- [x] T006 [P] Create fixture directories: `apps/api/tests/fixtures/canonical/` (empty, tracked via `.gitkeep`) and verify `apps/api/tests/fixtures/captured/` exists with 13 Evolution fixtures (from epic 005)
- [x] T007 Capture current latency baseline for text-only conversations by running `pytest apps/api/tests/benchmarks/test_text_latency.py --baseline --json-report=baseline.json` (creates reference for SC-009 gate). Commit `baseline.json` under `apps/api/tests/benchmarks/baselines/pre-epic-009.json`
- [x] T008 Run `pytest apps/api/tests/ -x -k "not (slow or e2e)"` and record the pass count. Document pre-epic totals (expect 173+191=364) in `apps/api/tests/TEST_BASELINE.md` — gate reference for SC-010

**Checkpoint**: Workspace ready; deps installed; baseline captured.

---

## Phase 2: Foundational (Blocking Prerequisites — PR-A Core)

**Purpose**: Introduce Canonical model, ChannelAdapter Protocol, ContentProcessor Protocol, webhook split, STEP_NAMES extension, `media_analyses` migration, and TextProcessor identity stub. Ensures every downstream user story can be implemented.

**CRITICAL**: No user story work (Phase 3+) can begin until this phase is complete AND the PR-A merge gate passes (173+191 tests PASS, text latency ≤ baseline+5ms).

### 2.1 Canonical Pydantic model (source of truth)

- [X] T010 Create `apps/api/prosauai/channels/canonical.py` with `ContentKind` StrEnum, `SenderRef`, `ConversationRef`, `ContentBlock`, `CanonicalInboundMessage` (frozen=True) — field definitions per data-model.md §2.1
- [X] T011 Add `@field_validator` for `ContentBlock.sub_type` (only allowed when `kind=UNSUPPORTED`) and for `CanonicalInboundMessage.idempotency_key` (64-char lowercase sha256 hex). Reference data-model.md §2.1
- [X] T012 [P] Create `apps/api/tests/unit/channels/test_canonical_model.py` — validate frozen behavior, sub_type rule, idempotency hex format, min_length=1 on `content` list (≥10 assertions)

### 2.2 ChannelAdapter Protocol + registry

- [X] T013 Create `apps/api/prosauai/channels/base.py` with `ChannelAdapterError`, `InvalidPayloadError`, `AuthError` exception hierarchy and `@runtime_checkable` `ChannelAdapter` Protocol — signatures per contracts/channel-adapter.md §1
- [X] T014 Create `apps/api/prosauai/channels/registry.py` with `register(adapter)`, `get(source)`, `registered_sources()` module-level functions backed by `_REGISTRY: dict[str, ChannelAdapter]`. Raise `ValueError` on duplicate source
- [X] T015 [P] Create `apps/api/tests/contract/test_channel_adapter_contract.py` (skeleton) — parametrized `test_implements_protocol` using `isinstance(..., ChannelAdapter)`. Adapters filled in later tasks

### 2.3 ContentProcessor Protocol + registry + result

- [X] T016 Create `apps/api/prosauai/processors/result.py` with `ProcessorStatus` StrEnum (OK/ERROR/BUDGET_EXCEEDED/UNSUPPORTED) and `ProcessedContent` (frozen=True) per data-model.md §2.2
- [X] T017 Add invariant tests to `apps/api/tests/unit/processors/test_result_invariants.py`: (a) `status==OK` ⇒ `marker is None`, (b) `status!=OK` ⇒ `marker is not None`, (c) cost=0 when cache_hit=True or status in {BUDGET_EXCEEDED, UNSUPPORTED}
- [X] T018 Create `apps/api/prosauai/processors/base.py` with `ContentProcessor` Protocol + `STTProvider`, `VisionProvider`, `DocumentExtractor` protocols + `ProcessorProviders` + `ProcessorContext` (frozen, arbitrary_types_allowed) — per contracts/content-processor.md §1-2
- [X] T019 Create `apps/api/prosauai/processors/registry.py` with `register/get/registered_kinds` by `ContentKind` — per contracts/content-processor.md §7
- [X] T020 [P] Create `apps/api/tests/contract/test_content_processor_contract.py` (skeleton) — parametrized `test_implements_protocol`; processors filled per-US

### 2.4 Migration 1 — `public.media_analyses` (PR-A)

- [X] T021 Create migration `apps/api/db/migrations/20260420_create_media_analyses.sql` with full DDL per data-model.md §3.1 (14 columns + 4 indexes + `OWNER TO app_owner` + grants to `service_role`; no RLS per ADR-027)
- [X] T022 [P] Add rollback block (`-- migrate:down`) in the same migration file: `DROP TABLE public.media_analyses CASCADE;`
- [X] T023 Apply migration locally: `cd apps/api && dbmate up` — verify 14 columns, `RLS=off`, indexes present (via `\d+ public.media_analyses`)
- [X] T024 [P] Extend retention cron in `apps/api/prosauai/observability/retention.py` with two SQL statements: nullify `source_url` + `raw_response` after 14d, DELETE after 90d (per data-model.md §3.1). Add unit test `tests/unit/observability/test_retention_media_analyses.py` covering both branches

### 2.5 Pipeline STEP_NAMES + content_process stub (TextProcessor identity)

- [X] T025 Edit `apps/api/prosauai/observability/step_record.py` — extend `STEP_NAMES` list from 12 to 14 entries: insert `"content_process"` between `"save_inbound"` (index 4) and `"build_context"`. Update the `order` validator range from `1..12` to `1..14`. Preserve backwards compatibility: traces with `order ∈ 1..12` keep rendering (no migration)
- [X] T026 Update `apps/api/tests/unit/observability/test_step_record.py` — assert `len(STEP_NAMES) == 14`, assert `"content_process"` at index 5, assert validator accepts `order=14` and rejects `order=15`
- [X] T027 Create `apps/api/prosauai/processors/text.py` with `TextProcessor` class: attrs `kind=TEXT`, `version="1.0.0"`, `prompt_version="v0-identity"`. `process()` returns `ProcessedContent(kind=TEXT, provider="internal/text", text_representation=block.text or "", status=OK, cost_usd=0, latency_ms=0, cache_hit=False)` — pure passthrough, never calls provider
- [X] T028 [P] Unit test `apps/api/tests/unit/processors/test_text.py` — assert identity behavior + latency <1ms + cost_usd=0 (SC-009 overhead constraint)
- [X] T029 Create `apps/api/prosauai/pipeline/steps/content_process.py` with `async def run_content_process(req: ConversationRequest, ctx: PipelineContext) -> ConversationRequest`. For each message in `req.canonical_messages`, for each block in `message.content`: look up processor via `registry.get(block.kind)`, call `processor.process(block, processor_context)`, replace `block.text` with `result.text_representation`. Emit OTel span `content_process`. In PR-A only TEXT kind is wired; other kinds fall back to TextProcessor with `text_representation="[fallback: {kind} not yet processed]"` (visible in trace, per plan.md §PR-A gate)
- [X] T030 Wire `run_content_process` into the pipeline between step `save_inbound` and `build_context` in `apps/api/prosauai/pipeline/__init__.py` (or equivalent orchestrator)
- [X] T031 [P] Unit test `apps/api/tests/unit/pipeline/test_content_process_step.py` — given a ConversationRequest with TEXT content, asserts `text_representation` is preserved and step is emitted as 6th in waterfall

### 2.6 ConversationRequest refactor + compat shim

- [X] T032 Edit `apps/api/prosauai/conversation/request.py` — replace `text: str` with `canonical_messages: Annotated[list[CanonicalInboundMessage], Field(min_length=1, max_length=50)]`. Add `@property sender_key`, `@property group_id`, `@property concatenated_text` per data-model.md §2.4
- [X] T033 Create `apps/api/prosauai/conversation/request_compat.py` — `@deprecated` shim that accepts legacy `{text, tenant_id, ...}` payload shape from Redis debounce buffers in flight and builds a synthetic `CanonicalInboundMessage` with a single TEXT block. Log warning on invocation. TTL: remove in epic 010
- [X] T034 [P] Unit test `apps/api/tests/unit/conversation/test_request_shape.py` — (a) new shape round-trips via `model_dump_json → model_validate_json`, (b) shim accepts legacy payload and produces equivalent canonical_messages, (c) `concatenated_text` joins multiple messages with single space

### 2.7 EvolutionAdapter (inbound) + outbound rename

- [X] T035 [P] Move `apps/api/prosauai/channels/evolution.py` (outbound delivery) to `apps/api/prosauai/channels/outbound/evolution.py`. Update all imports via `git mv` + grep. No behavioral change
- [X] T036 Create `apps/api/prosauai/channels/inbound/evolution/auth.py` with `verify_evolution_webhook(request, tenant_config)` — reads `X-Webhook-Secret`, compares (constant-time) with `tenant_config.webhook_secret`. Raise `AuthError` on mismatch
- [ ] T037 Create `apps/api/prosauai/channels/inbound/evolution/adapter.py` — `EvolutionAdapter` class with attrs `source="evolution"`, `source_version="1.0.0"`. Migrate logic from existing `apps/api/prosauai/core/formatter.py::parse_evolution_message` to `normalize(payload, source_instance) -> list[CanonicalInboundMessage]`. Map `data.messageType` per contracts/channel-adapter.md §2.1. Compute `idempotency_key = sha256(f"evolution:{source_instance}:{data.key.id}".encode()).hexdigest()`. Prefer `data.message.base64` when present (skip download later)
- [ ] T038 Register EvolutionAdapter in `apps/api/prosauai/main.py` startup hook: `from prosauai.channels.inbound.evolution.adapter import EvolutionAdapter; register(EvolutionAdapter())`
- [ ] T039 Deprecate `apps/api/prosauai/core/formatter.py::parse_evolution_message` — keep a thin re-export that calls into EvolutionAdapter for 1 release, emits `DeprecationWarning`

### 2.8 Webhook handlers split

- [ ] T040 Create `apps/api/prosauai/api/webhooks/dispatch.py` — shared pipeline: resolve tenant from `source_instance`, enqueue idempotency key check, push `CanonicalInboundMessage` list to debounce buffer. Exposes `async def dispatch(messages: list[CanonicalInboundMessage], correlation_id: str)`
- [ ] T041 Create `apps/api/prosauai/api/webhooks/evolution.py` with `POST /webhook/evolution/{instance_name}` FastAPI route: call `EvolutionAdapter.verify_webhook`, parse body, call `adapter.normalize`, forward to `dispatch.dispatch`. Return 202 Accepted with correlation_id
- [ ] T042 Edit `apps/api/prosauai/api/webhooks.py` — convert to alias forwarder: keep path `POST /webhook/whatsapp/{instance_name}`, internally forward to the new Evolution handler. Emit structured log `POST /webhook/whatsapp/{instance_name} (legacy alias → evolution)`. Do NOT remove — slated for epic 010 after metrics confirm zero legacy traffic (FR-005)
- [ ] T043 Register the new Evolution router in `apps/api/prosauai/main.py` via `app.include_router(evolution_router)`
- [ ] T044 [P] Integration test `apps/api/tests/integration/test_webhook_alias_retrocompat.py` — POST to `/webhook/whatsapp/test-instance` returns 202 AND dispatches via EvolutionAdapter (mock `dispatch`)

### 2.9 Core module refactor (facts + debounce)

- [ ] T045 Edit `apps/api/prosauai/core/router/facts.py::_derive_content_kind` — replace the Evolution-specific `message.media_type` check with `canonical_message.content[0].kind == ContentKind.X`. Preserve the exact ContentKind→RouteFact output (no behavioral change). Reference data-model.md §6
- [ ] T046 Edit `apps/api/prosauai/core/debounce.py` — update serialization of buffered messages to `CanonicalInboundMessage.model_dump_json()`. Update flush to return `list[CanonicalInboundMessage]` (not `str`). Preserve Redis key format (`buf:{sender_key}`) unchanged
- [ ] T047 [P] Unit test `apps/api/tests/unit/core/test_debounce_canonical_shape.py` — buffer serialization round-trips; flush returns list

### 2.10 Fixtures (canonical outputs for 13 Evolution payloads)

- [ ] T048 [P] For each of the 13 Evolution fixtures in `apps/api/tests/fixtures/captured/evolution_*.input.json`, run `EvolutionAdapter.normalize` and save the canonical output JSON to `apps/api/tests/fixtures/canonical/evolution_{name}.canonical.json`. Commit both input and canonical pairs
- [ ] T049 [P] Fill the parameterized case list of `apps/api/tests/contract/test_channel_adapter_contract.py::test_normalize_produces_valid_canonical` with the 13 Evolution fixtures. Each fixture MUST produce ≥1 CanonicalInboundMessage that survives Pydantic validation

### 2.11 Regression + latency gate

- [ ] T050 Full suite run: `cd apps/api && pytest -x tests/ -k "not (slow or e2e)"` — MUST pass 173 (epic 005) + 191 (epic 008) = 364 tests unchanged (SC-010 gate)
- [ ] T051 Create `apps/api/tests/benchmarks/test_text_latency.py` — runs 1000 text-only requests through the refactored pipeline and reports p95. Compares against `baselines/pre-epic-009.json`. Fails if p95 > baseline + 5ms (SC-009 gate)
- [ ] T052 [P] Draft ADR-030 at `platforms/prosauai/decisions/ADR-030-canonical-inbound-message.md` — Nygard format: Context (Evolution coupling in InboundMessage), Decision (CanonicalInboundMessage + frozen + discriminated-via-kind via attrs-flattened), Consequences (phased PR-A1/A2/A3 migration, compat shim lifetime), Alternatives rejected (Discriminated Union Pydantic per kind — data-model.md §9.2)
- [ ] T053 [P] Draft ADR-031 at `platforms/prosauai/decisions/ADR-031-multi-source-channel-adapter.md` — Nygard format: adapter-as-pure-translator policy, registry lookup, validation gate SC-013

**Checkpoint (PR-A Merge Gate)**: `apps/api/tests/ -x` PASS ×364 (SC-010), text latency p95 ≤ baseline+5ms (SC-009), `/webhook/whatsapp/{instance_name}` alias returns 202, trace waterfall shows 14 steps with `content_process` containing `{"providers":["text-placeholder"],"kind":"text|fallback"}` for media payloads (plan.md PR-A gate). **MERGE PR-A TO `develop` BEFORE STARTING PHASE 3.**

---

## Phase 3: User Story 5 — Feature flags + budget + cache + circuit breaker (Priority: P1)

**Goal**: Admin can flip `content_processing.enabled`, per-kind flags, and `daily_budget_usd` per tenant via `tenants.yaml` with RTO ≤ 60s (no deploy). Budget exceeded → graceful marker fallback. This story delivers the rollout-safety infrastructure consumed by US1/US2/US3.

**Independent Test**: Set `content_processing.enabled=false` on a tenant → send any media → trace shows `content_process.output.marker="[feature_disabled: {kind}]"` with ZERO provider calls. Flip flag back → next message honors new value within 60s. Saturate `processor_usage_daily` → new media returns `[budget_exceeded]` marker, zero provider calls.

### Tests for User Story 5

- [ ] T060 [P] [US5] Unit test `apps/api/tests/unit/processors/test_feature_flag_disabled.py` — processor honors `content_processing.enabled=false` and returns marker without touching provider
- [ ] T061 [P] [US5] Unit test `apps/api/tests/unit/processors/test_budget.py` — BudgetTracker.check_allowed returns False when `spent_today + estimated > daily_budget_usd`; `record_usage` performs atomic UPSERT
- [ ] T062 [P] [US5] Unit test `apps/api/tests/unit/processors/test_breaker.py` — 5 consecutive failures in 60s → open; probe after 30s → re-open if fail with 30→60→120→300s backoff cap; reset after 10 min clean
- [ ] T063 [P] [US5] Unit test `apps/api/tests/unit/processors/test_cache.py` — `set` then `get` round-trips ProcessedContent; `raw_response` stripped before serialize; TTL=14d via `fakeredis`
- [ ] T064 [P] [US5] Integration test `apps/api/tests/integration/test_budget_exceeded_fallback.py` — full request flow from webhook → budget saturated → fallback marker returned, ZERO OpenAI calls (respx asserts). Acceptance Scenario 3
- [ ] T065 [P] [US5] Integration test `apps/api/tests/integration/test_feature_flag_reload.py` — `freezegun` + poll; flip yaml → 60s later next call honors new value (Acceptance Scenario 4)

### Implementation for User Story 5

- [ ] T070 [US5] Extend `apps/api/tenants.yaml` schema — add top-level `content_processing` per tenant: `{enabled, audio_enabled, image_enabled, document_enabled, daily_budget_usd, fallback_messages: {marker → persona-tonalized string}}`. Document in `apps/api/prosauai/config.py` Pydantic models
- [ ] T071 [US5] Edit `apps/api/prosauai/config.py` — add `TenantContentProcessingConfig` Pydantic model + `TenantConfig.content_processing` field. Add `CONTENT_PROCESSING_POLL_INTERVAL_SECONDS=60` env var (default 60, min 10)
- [ ] T072 [US5] Create `apps/api/prosauai/config_poller.py` — background task that reloads `tenants.yaml` every `poll_interval` seconds, swaps in-memory `_TENANT_REGISTRY`. Emits OTel span `config.reload` with attrs `{changed: bool, tenant_count}`. Safe reload: parse-first-then-swap; errors keep previous version
- [ ] T073 [US5] Wire poller startup in `apps/api/prosauai/main.py` via `@app.on_event("startup")` and shutdown via `@app.on_event("shutdown")`
- [ ] T074 Create migration `apps/api/db/migrations/20260505_create_processor_usage_daily.sql` with composite PK, checks, grants per data-model.md §3.2. Add `-- migrate:down` block dropping the table
- [ ] T075 Apply migration: `dbmate up` — verify composite PK and admin grants
- [ ] T076 [US5] Create `apps/api/prosauai/processors/budget.py` with `BudgetTracker` implementing `check_allowed(tenant_id, daily_budget_usd)` (single-row SELECT via `pool_admin`) and `record_usage(tenant_id, kind, provider, cost_usd, cache_hit)` (fire-and-forget UPSERT per data-model.md §3.2). Race window ≤1 call over limit per spec Assumptions
- [ ] T077 [P] [US5] Create `apps/api/prosauai/processors/cache.py` with `ProcessorCache` — Redis key pattern `proc:{kind}:v{prompt_version}:{sha256_hex}`, TTL=14d, value is `ProcessedContent.model_dump_json(exclude={"raw_response"})` (data-model.md §4). Uses existing Redis client from epic 001
- [ ] T078 [P] [US5] Create `apps/api/prosauai/processors/breaker.py` with in-memory `CircuitBreaker` per `(tenant_id, provider)` — parameters 5 failures/60s window → open 30s → 1 half-open probe → backoff 30/60/120/300s cap → reset after 10min clean (FR-023). State is worker-local (accepted per contracts/content-processor.md §8)
- [ ] T079 [P] [US5] Create `apps/api/prosauai/processors/errors.py` with exception hierarchy: `ProcessorError`, `ProviderError`, `MediaTooLargeError(size_mb)`, `DownloadError`, `TimeoutError` (override if needed), `PDFScannedError`, `PDFEncryptedError`, `AudioSilentError`
- [ ] T080 [US5] Extend `apps/api/prosauai/observability/pricing.py::PRICING_TABLE` — add `"openai/whisper-1"` ($0.006/min) and `"openai/gpt-4o-mini-vision-low"` (85 tokens fixed × $0.15/1M), `"openai/gpt-4o-mini-vision-high"` (~765 tokens × $0.15/1M). Add helper `calculate_audio_cost(duration_s)` + `calculate_vision_cost(detail, images_count)`
- [ ] T081 [US5] Add fallback marker → persona-tonalized string lookup in pipeline step `generate` (or equivalent LLM step): when the concatenated input contains a marker in brackets, instruct the LLM via system prompt segment "MARKER_HANDOFF: {marker} → respond in persona tone requesting ..."; if LLM generation fails, fall back to `tenant_config.content_processing.fallback_messages.get(marker, DEFAULT_FALLBACKS[marker])`. Add DEFAULT_FALLBACKS constant in `apps/api/prosauai/processors/fallbacks.py` (FR-031)
- [ ] T082 [US5] Update `apps/api/prosauai/processors/text.py` to a feature-flag-aware base: add abstract `_is_enabled(tenant_config) -> bool` on the future BaseProcessor, default to True for TextProcessor. No behavior change for TEXT

**Checkpoint**: Feature flags + budget + cache + breaker infra operational; T060-T065 tests GREEN. Rollout kill-switch validated (T065).

---

## Phase 4: User Story 1 — Audio (Priority: P1) MVP

**Goal**: Customer sends PTT/attached audio → Whisper transcribes (≤8s p95 end-to-end) → LLM responds in context. Trace step `content_process` shows transcript + cost + latency + cache_hit.

**Independent Test**: Send a 10s PTT fixture to `/webhook/evolution/ariel-dev` with `audio_enabled=true` and budget room → within 8s the worker emits an outbound response that references the spoken content; Trace Explorer shows step 6 with the Whisper transcript full text (no truncation) and `status=ok`.

### Tests for User Story 1

- [ ] T090 [P] [US1] Contract test parametrized row in `apps/api/tests/contract/test_content_processor_contract.py`: `AudioProcessor` implements `ContentProcessor`; provider 5xx → returns `[provider_unavailable]`; timeout → `[timeout]`; `audio_enabled=false` → `[feature_disabled: audio]`; budget exceeded → `[budget_exceeded]`; size>25MB → `[media_too_large: 26.3]`
- [ ] T091 [P] [US1] Unit test `apps/api/tests/unit/processors/test_audio.py` — (a) happy path with mocked `AsyncOpenAI` via respx returns transcript, (b) cache hit on second call (same sha256) returns `cache_hit=True` + `cost_usd=0` + `latency_ms<50`, (c) hallucination filter: duration<2s OR blocklist match → `[audio_silent]`, (d) base64 inline bypasses httpx download
- [ ] T092 [P] [US1] Integration test `apps/api/tests/integration/test_audio_end_to_end.py` — full webhook → dispatch → debounce → content_process → generate → outbound delivery; validates trace has 14 steps, step 6 has transcript, outbound message references content. Uses `evolution_audio_ptt.input.json` fixture
- [ ] T093 [P] [US1] Integration test `apps/api/tests/integration/test_audio_multi_message_flush.py` — audio + text in same debounce flush produce concatenated `text_representation` single speech (Acceptance Scenario 5 / FR-012)
- [ ] T094 [P] [US1] Benchmark `apps/api/tests/benchmarks/test_audio_e2e.py` — 30 audio fixtures × 3 rounds, reports p95. Gate: p95 < 8000ms (SC-001). Uses mocked Whisper with realistic 500-1500ms response distribution

### Implementation for User Story 1

- [ ] T100 [P] [US1] Create `apps/api/prosauai/processors/providers/openai_stt.py` — `OpenAISTTProvider` class wrapping `AsyncOpenAI.audio.transcriptions.create(model="whisper-1", language="pt", file=...)`. Returns `(transcript: str, raw_response: dict)`. Timeout 15s. No caching (caller manages)
- [ ] T101 [US1] Create `apps/api/prosauai/processors/audio.py` — `AudioProcessor(ContentProcessor)` class: `kind=AUDIO`, `version="1.0.0"`, `prompt_version="v1"`. Implements `process()` per contracts/content-processor.md §6 pseudocode — feature flag → sha256 → cache → budget → breaker → download (httpx stream, max 25MB, 10s timeout, rejects on content-length>25MB per FR-020) OR base64 inline (FR-021) → `provider.stt.transcribe` with retry (3 attempts, base 500ms, jitter ±25%, per FR-024) → hallucination filter (duration<2s OR blocklist match → `[audio_silent]` per FR-025) → cache.set + budget.record_usage → return ProcessedContent
- [ ] T102 [P] [US1] Create `apps/api/prosauai/processors/hallucination_filter.py` with `AUDIO_HALLUCINATION_BLOCKLIST = ["Legendas em português.", "Legendas pela comunidade.", "...", ...]` (PT-BR common Whisper artifacts) and `is_hallucinated(transcript, duration_s) -> bool` — unit-tested independently
- [ ] T103 [US1] Register `AudioProcessor` in `main.py` startup: instantiate with `OpenAISTTProvider` via DI, `registry.register(processor)`
- [ ] T104 [US1] Wire audio path in `pipeline/steps/content_process.py` — for `block.kind == AUDIO`, call AudioProcessor via registry. Update `block.text = result.text_representation` (or pass via sidecar field in ConversationRequest if frozen prevents)
- [ ] T105 [US1] Add fire-and-forget persist of `MediaAnalysis` after AudioProcessor returns — `apps/api/prosauai/observability/media_analyses_repo.py::insert(...)` uses `pool_admin` and swallows exceptions with structured log (ADR-028). Invoked from the pipeline step (not from the processor, per contracts/content-processor.md §10)
- [ ] T106 [P] [US1] Emit OTel spans `processor.audio.transcribe` (wrapping the whole process) and `openai.whisper.create` (wrapping the SDK call) with attributes `{tenant.id, processor.kind, processor.provider, processor.cache_hit, processor.cost_usd, processor.prompt_version}` per plan.md Technical Context
- [ ] T107 [P] [US1] Add Ruff/Mypy compliance pass on new audio files: `ruff check apps/api/prosauai/processors/audio.py apps/api/prosauai/processors/providers/openai_stt.py --fix`
- [ ] T108 [P] [US1] Draft ADR-033 at `platforms/prosauai/decisions/ADR-033-openai-stt-vision-provider.md` — rationale for whisper-1 + gpt-4o-mini (v1), alternatives considered (Deepgram, Azure Speech, Google STT, gpt-4o-mini-transcribe, Claude Haiku), swap migration path via `ProcessorContext.providers`

**Checkpoint**: US1 independently verifiable via T092 integration test + T094 benchmark. Audio end-to-end works with mocked Whisper; real Whisper works when `OPENAI_API_KEY` is set.

---

## Phase 5: User Story 2 — Image (Priority: P1)

**Goal**: Customer sends image (with/without caption) → GPT-4o-mini describes → LLM responds contextually (≤9s p95). Supports `detail="low"` default and `detail="high"` per-tenant config.

**Independent Test**: Send an image fixture with caption "tem esse?" to an `image_enabled=true` tenant → within 9s the response references the described object. Trace shows `detail=low`, cost ≈ $0.013, description complete.

### Tests for User Story 2

- [ ] T110 [P] [US2] Contract test parametrized row: `ImageProcessor` implements `ContentProcessor`; 5xx → `[provider_unavailable]`; timeout → `[timeout]`; `image_enabled=false` → `[feature_disabled: image]`; budget exceeded → `[budget_exceeded]`
- [ ] T111 [P] [US2] Unit test `apps/api/tests/unit/processors/test_image.py` — (a) happy with/without caption, (b) `detail="high"` honored when `tenant_config.processor_config.image.detail="high"`, (c) PII mask applied before text_representation is returned (Acceptance Scenario 4 / FR-026), (d) cache hit on repeat sha256
- [ ] T112 [P] [US2] Integration test `apps/api/tests/integration/test_image_end_to_end.py` — webhook → vision mock returns "Red shoe on white background" → LLM response references the shoe. Uses `evolution_image_with_caption.input.json`
- [ ] T113 [P] [US2] Unit test `apps/api/tests/unit/processors/test_image_pii_masking.py` — description containing CPF pattern → masked to `[REDACTED_CPF]` before trace/logs (FR-026)

### Implementation for User Story 2

- [ ] T120 [P] [US2] Create `apps/api/prosauai/processors/providers/openai_vision.py` — `OpenAIVisionProvider.describe(image_bytes, mime_type, detail, prompt) -> (text, raw)` using `AsyncOpenAI.responses.create(model="gpt-4o-mini", input=[{role:"user", content:[{type:"input_image", image_url:"data:{mime};base64,{b64}", detail:detail}, {type:"input_text", text:prompt}]}])` per contracts/content-processor.md §2. Timeout 12s
- [ ] T121 [US2] Create `apps/api/prosauai/processors/image.py` — `ImageProcessor(ContentProcessor)` class: `kind=IMAGE`, `version="1.0.0"`, `prompt_version="v1"`. Constant prompt: `"Descreva brevemente o conteúdo desta imagem em português. Inclua objetos visíveis, texto relevante, e contexto aparente."`. Reads `detail` from `tenant_config.processor_config.image.detail` default `"low"`. Same skeleton as AudioProcessor (feature flag → sha256 → cache → budget → breaker → download → vision.describe → PII mask → cache.set)
- [ ] T122 [US2] Wire `PIIMasker` from existing `apps/api/prosauai/core/output_guard.py` (epic 004) on `text_representation` BEFORE caching and returning. Add test confirming mask runs
- [ ] T123 [US2] Register `ImageProcessor` in `main.py` startup. Wire image path in `pipeline/steps/content_process.py`
- [ ] T124 [P] [US2] Emit OTel spans `processor.image.describe` and `openai.vision.responses.create` with attrs including `detail`
- [ ] T125 [P] [US2] Add PII mask unit coverage at `apps/api/tests/unit/core/test_output_guard_image_flow.py` — feeds image descriptions containing CPF/card/email; asserts masking before return

**Checkpoint**: US2 verifiable via T112; US1+US2 both work independently; PII never leaks into trace per T125.

---

## Phase 6: User Story 4 — Trace Explorer / Admin audit (Priority: P1)

**Goal**: Admin opens Trace Explorer → `content_process` step appears as 6th in waterfall with input, output, provider, cost_usd, latency_ms, cache_hit. Performance AI tab gets "Custo de mídia/dia" stacked bar chart. Zero truncation of transcripts/descriptions.

**Independent Test**: Run 5 audios + 5 images through → open each trace in portal → confirm step 6 visible, fields populated, full transcript visible on expand. Open Performance AI → stacked bar shows audio + image segments summing to expected USD.

### Tests for User Story 4

- [ ] T130 [P] [US4] E2E Playwright test `apps/admin/tests/e2e/trace_explorer_content_process.spec.ts` — seed trace with audio content_process step → open Trace Explorer → expand trace → assert 14 rows in waterfall, row 6 label="content_process", expand row → modal shows full transcript (>1000 chars without ellipsis)
- [ ] T131 [P] [US4] E2E Playwright test `apps/admin/tests/e2e/performance_ai_media_cost.spec.ts` — seed `processor_usage_daily` with 3 days × (audio, image, document) → open Performance AI → assert stacked bar has 3 segments, legend shows 3 kinds, hover tooltip shows USD per kind per day
- [ ] T132 [P] [US4] Unit test `apps/api/tests/unit/admin/test_media_cost_query.py` — `GET /api/admin/performance/media-cost?from=X&to=Y&tenant_id=Z` returns aggregated rows from `processor_usage_daily`; uses `pool_admin`
- [ ] T133 [P] [US4] Unit test `apps/api/tests/unit/observability/test_media_analyses_persist.py` — fire-and-forget insert (ADR-028): DB failure does NOT propagate; structured log emitted with `error.type=persist_failed`

### Implementation for User Story 4

- [ ] T140 [US4] Create `apps/api/prosauai/observability/media_analyses_repo.py::async_insert_fire_and_forget(analysis: ProcessedContent, tenant_id, message_id, content_sha256, prompt_version)` — dispatches to event loop via `asyncio.create_task`, wraps with try/except that logs but never raises. Called from `pipeline/steps/content_process.py` after each processor.process() returns
- [ ] T141 [US4] Create API endpoint `apps/api/prosauai/api/admin/performance.py::GET /api/admin/performance/media-cost` — params `from`, `to`, `tenant_id` (admin auth enforced via existing middleware from epic 008). Query `processor_usage_daily` aggregating by `(day, kind)`. Returns JSON `[{day, kind, cost_usd_sum, count, cache_hits, cache_misses}, ...]`
- [ ] T142 [US4] Extend OpenAPI codegen: regenerate `apps/admin/src/lib/api-types.ts` via `openapi-typescript` (existing tooling from epic 008) to include the new endpoint
- [ ] T143 [P] [US4] Create React component `apps/admin/src/components/performance/MediaCostChart.tsx` — Recharts `<ResponsiveContainer><BarChart stackId="kind"><Bar dataKey="audio"/><Bar dataKey="image"/><Bar dataKey="document"/>`. Uses TanStack Query v5 (`useQuery({queryKey: ["media-cost", range, tenant]})`). Hover tooltip shows per-kind USD + count
- [ ] T144 [US4] Insert `<MediaCostChart/>` into `apps/admin/src/app/performance-ai/page.tsx` below existing charts. Respect tenant filter from the existing page state
- [ ] T145 [P] [US4] Update `apps/admin/src/components/trace-explorer/StepAccordion.tsx` — confirm it already renders arbitrary `input_jsonb`/`output_jsonb` (epic 008 generic behavior); add a conditional "Open full transcript" button when `output.kind in {audio, image, document}` and `output.text_representation.length > 500`, opens Dialog with untruncated text (reads from `media_analyses` via new `GET /api/admin/traces/{trace_id}/media-analysis/{step_id}`)
- [ ] T146 [P] [US4] Add `GET /api/admin/traces/{trace_id}/media-analysis/{step_id}` returning the matching `media_analyses` row (by `message_id + kind + prompt_version`, latest). Admin auth only
- [ ] T147 [P] [US4] Emit inbox-bubble icon by `content.kind` — update `apps/admin/src/components/inbox/MessageBubble.tsx` to show 🎤/📷/📎/📍 prefix next to message preview when `conversations.last_message_kind` is media (re-use denormalized column from epic 008; no DB change needed)

**Checkpoint**: US4 verifiable via T130+T131 Playwright. Admin can observe cost/latency/cache in real time; full transcripts visible without truncation.

---

## Phase 7: User Story 3 — Document (Priority: P2)

**Goal**: Customer sends PDF/DOCX → text extracted locally (pypdf / python-docx) → LLM responds (≤10s p95). Scanned PDF → marker `[pdf_scanned]`; encrypted → `[pdf_encrypted]`.

**Independent Test**: Send a PDF payment receipt (selectable text, ≤10 pages) with caption "recebeu?" → response confirms receipt referencing amount/date extracted. Send scanned PDF → response asks for manual text.

### Tests for User Story 3

- [ ] T150 [P] [US3] Contract test parametrized row: `DocumentProcessor` implements `ContentProcessor`; scanned PDF → `[pdf_scanned]`; encrypted PDF → `[pdf_encrypted]`; timeout → `[timeout]`; `document_enabled=false` → `[feature_disabled: document]`
- [ ] T151 [P] [US3] Unit test `apps/api/tests/unit/processors/test_document.py` — (a) 3-page PDF with selectable text → transcript contains key phrases, (b) scanned PDF (empty extract) → `[pdf_scanned]`, (c) encrypted PDF → `[pdf_encrypted]`, (d) DOCX → python-docx extracts paragraphs, (e) cache hit on repeat
- [ ] T152 [P] [US3] Integration test `apps/api/tests/integration/test_document_end_to_end.py` — PDF fixture → pipeline response references content. Uses `evolution_document_pdf.input.json` (create fixture if absent from captured/)
- [ ] T153 [P] [US3] Add scanned + encrypted PDF fixtures to `apps/api/tests/fixtures/captured/`: `evolution_document_pdf_scanned.input.json`, `evolution_document_pdf_encrypted.input.json` — small synthetic PDFs

### Implementation for User Story 3

- [ ] T160 [P] [US3] Create `apps/api/prosauai/processors/providers/local_document.py` — `LocalDocumentExtractor.extract(doc_bytes, mime_type, max_pages=20) -> (text, raw)`. Uses `pypdf.PdfReader` for PDFs; raises `PDFEncryptedError` if encrypted, returns empty+raise `PDFScannedError` if extracted string is empty. Uses `python-docx.Document` for DOCX. Returns combined pages text separated by `\n\n`
- [ ] T161 [US3] Create `apps/api/prosauai/processors/document.py` — `DocumentProcessor(ContentProcessor)`: `kind=DOCUMENT`, `version="1.0.0"`, `prompt_version="v1"`. Skipping budget check (local cost trivial — note in code comment referencing contracts/content-processor.md §5). Flow: feature flag → sha256 → cache → download (or base64) → `provider.document_extractor.extract` → cache.set → return. Error mapping: `PDFEncryptedError` → `[pdf_encrypted]`, `PDFScannedError` → `[pdf_scanned]`, empty text → `[pdf_scanned]`
- [ ] T162 [US3] Register `DocumentProcessor` in `main.py` startup. Wire document path in `pipeline/steps/content_process.py`
- [ ] T163 [P] [US3] Emit OTel span `processor.document.extract` with attrs `{processor.kind, processor.provider="internal/pypdf|python-docx", pages_extracted}`

**Checkpoint**: US3 independently verifiable via T152. All three P1/P2 media kinds (audio, image, document) work end-to-end.

---

## Phase 8: User Story 7 — Sticker / Reaction / Location / Contact / Unsupported (Priority: P3)

**Goal**: Stickers, reactions, locations, contacts, and unknown kinds (video, poll, payment, etc.) produce deterministic `text_representation` with ZERO provider calls. Prevents silent drops while keeping cost/latency negligible.

**Independent Test**: Send one of each 5 kinds → trace shows `provider="internal/deterministic"` or `"internal/unsupported"`, `cost_usd=0`, `latency_ms<10`, and a sane `text_representation`. LLM response is contextually coherent ("cliente reagiu com 👍", etc.).

### Tests for User Story 7

- [ ] T170 [P] [US7] Contract test parametrized rows: `StickerProcessor`, `LocationProcessor`, `ContactProcessor`, `ReactionProcessor`, `UnsupportedProcessor` all implement `ContentProcessor`
- [ ] T171 [P] [US7] Unit test `apps/api/tests/unit/processors/test_sticker.py` — `text_representation` = `"[sticker: {alt_text or 'emoji'}]"`, no provider call
- [ ] T172 [P] [US7] Unit test `apps/api/tests/unit/processors/test_location.py` — `text_representation` includes `latitude,longitude` + optional `location_name`. Format: `"[localização: {name or 'sem nome'}] ({lat:.5f}, {lng:.5f})"`
- [ ] T173 [P] [US7] Unit test `apps/api/tests/unit/processors/test_contact.py` — `text_representation` = `"[contato compartilhado: {name} — {phone}]"` parsed from vCard
- [ ] T174 [P] [US7] Unit test `apps/api/tests/unit/processors/test_reaction.py` — `text_representation` = `"[reação: {emoji} à mensagem {target_id}]"`
- [ ] T175 [P] [US7] Unit test `apps/api/tests/unit/processors/test_unsupported.py` — for each `sub_type ∈ {video, poll, payment, call_notification, edited, system}` returns marker `[content_unsupported: {sub_type}]` and `text_representation="[conteúdo não suportado: {sub_type} — por favor, envie texto]"` (FR-011 exact string)
- [ ] T176 [P] [US7] Integration test `apps/api/tests/integration/test_light_kinds_flow.py` — 5 payloads in sequence, each trace has `content_process` step with `cost_usd=0, latency_ms<10`

### Implementation for User Story 7

- [ ] T180 [P] [US7] Create `apps/api/prosauai/processors/sticker.py` — `StickerProcessor(ContentProcessor)`: deterministic `text_representation` from `block.attrs.get("alt_text")` or emoji; `status=OK`, no cache, no budget
- [ ] T181 [P] [US7] Create `apps/api/prosauai/processors/location.py` — `LocationProcessor`: format lat/lng to 5 decimals; include optional name
- [ ] T182 [P] [US7] Create `apps/api/prosauai/processors/contact.py` — `ContactProcessor`: parse vCard (stdlib `email.parser` or simple regex) to extract FN + TEL
- [ ] T183 [P] [US7] Create `apps/api/prosauai/processors/reaction.py` — `ReactionProcessor`: interprets emoji + `reaction_target_external_id`
- [ ] T184 [P] [US7] Create `apps/api/prosauai/processors/unsupported.py` — `UnsupportedProcessor`: always returns marker `[content_unsupported: {sub_type}]` with `status=UNSUPPORTED` (not ERROR — per ProcessorStatus enum)
- [ ] T185 [US7] Register all 5 processors in `main.py` startup. Wire branches in `pipeline/steps/content_process.py`

**Checkpoint**: All 9 ContentKinds covered end-to-end. Zero silent drops (SC-004).

---

## Phase 9: User Story 6 — Meta Cloud Adapter (Priority: P2) — PR-C

**Goal**: Plug Meta Cloud API as second canal without touching pipeline/processors/router (SC-013 gate). Validates the ChannelAdapter abstraction was not Evolution-shaped.

**Independent Test**: Feed a real Meta Cloud payload fixture → pipeline produces a trace structurally identical to Evolution (same 14 steps). Diff of the PR touches zero bytes in `apps/api/prosauai/pipeline.py`, `apps/api/prosauai/processors/`, `apps/api/prosauai/core/router/`.

### Tests for User Story 6

- [ ] T190 [P] [US6] Contract test parametrized row: `MetaCloudAdapter` implements `ChannelAdapter`; `verify_webhook` GET handshake + POST HMAC validation; `normalize` handles text/audio/image/interactive/video/unsupported types
- [ ] T191 [P] [US6] Unit test `apps/api/tests/unit/channels/test_meta_cloud_adapter.py` — `test_normalize_text_payload`, `test_normalize_audio`, `test_normalize_image`, `test_normalize_interactive_button_reply` maps to TEXT, `test_normalize_video` maps to UNSUPPORTED with `sub_type="video"`
- [ ] T192 [P] [US6] Unit test `apps/api/tests/unit/channels/test_meta_cloud_auth.py` — (a) GET `hub.verify_token` match → returns `hub.challenge`, (b) GET mismatch → 403, (c) POST valid `X-Hub-Signature-256` → pass, (d) POST invalid signature → AuthError
- [ ] T193 [P] [US6] Integration test `apps/api/tests/integration/test_meta_cloud_end_to_end.py` — POST a Meta Cloud audio payload with valid HMAC → trace completes with 14 steps, response delivered. Uses existing AudioProcessor without modification (validates SC-013 at runtime)
- [ ] T194 [P] [US6] Cross-source idempotency test `apps/api/tests/integration/test_cross_source_idempotency.py` — same `external_message_id` delivered via both Evolution (source=evolution, instance=ariel) and Meta Cloud (source=meta_cloud, instance=phone_number_id_123) — both processed as distinct messages (decision D11, Acceptance Scenario 2)
- [ ] T195 [P] [US6] SC-013 zero-core-change gate test `apps/api/tests/ci/test_pr_c_scope.py` — runs `git diff develop..HEAD --stat apps/api/prosauai/pipeline.py apps/api/prosauai/processors/ apps/api/prosauai/core/router/` and asserts empty output. Runs in CI as PR-C merge gate

### Implementation for User Story 6

- [ ] T200 [P] [US6] Capture 4 real Meta Cloud fixtures to `apps/api/tests/fixtures/captured/`: `meta_cloud_text.input.json`, `meta_cloud_audio.input.json`, `meta_cloud_image.input.json`, `meta_cloud_interactive.input.json`. Use sandbox account, scrub PII; retain the official payload shape
- [ ] T201 [P] [US6] Generate canonical outputs: for each fixture above, run `MetaCloudAdapter.normalize` and commit `meta_cloud_*.canonical.json` under `tests/fixtures/canonical/`
- [ ] T202 [US6] Create `apps/api/prosauai/channels/inbound/meta_cloud/auth.py` — `verify_meta_cloud_webhook(request, config)`: GET → compare `hub.verify_token` with `config.meta_cloud.verify_token` (constant-time), return `hub.challenge` string; POST → `hmac.new(app_secret, body_bytes, sha256)` and compare with header `X-Hub-Signature-256` (strip `sha256=` prefix), constant-time (FR-029)
- [ ] T203 [US6] Create `apps/api/prosauai/channels/inbound/meta_cloud/adapter.py` — `MetaCloudAdapter` class with `source="meta_cloud"`, `source_version="1.0.0"`. `normalize(payload, source_instance=phone_number_id)`: iterate `entry[*].changes[*].value.messages[*]`, map per contracts/channel-adapter.md §2.2 (text/audio/image/document/sticker/location/contacts/reaction/interactive/video/order/system/unsupported). Compute `idempotency_key = sha256(f"meta_cloud:{source_instance}:{message.id}")`
- [ ] T204 [US6] Create `apps/api/prosauai/api/webhooks/meta_cloud.py` — routes `GET /webhook/meta_cloud/{tenant_slug}` (handshake) and `POST /webhook/meta_cloud/{tenant_slug}` (auth → normalize → dispatch). Register router in `main.py`
- [ ] T205 [US6] Register `MetaCloudAdapter` in `main.py` startup: `register(MetaCloudAdapter(config=settings.meta_cloud))`
- [ ] T206 [P] [US6] Create `apps/api/scripts/sign_meta_webhook.py` — CLI helper that takes `payload_path` + `app_secret` and prints `X-Hub-Signature-256: sha256=...`. Used in dev (quickstart.md §3.3)
- [ ] T207 [P] [US6] Draft ADR-035 at `platforms/prosauai/decisions/ADR-035-meta-cloud-adapter-integration.md` — Nygard: Context (prove abstraction), Decision (implement adapter test-first per pitch decision D21), Consequences (SC-013 gate, zero pipeline change), Alternatives rejected (Evolution-only + shim)
- [ ] T208 [P] [US6] Create `apps/api/prosauai/channels/README.md` — playbook "How to add a new inbound channel in 4 steps": 1) implement ChannelAdapter, 2) implement auth, 3) add webhook handler, 4) register in main + add fixtures + contract test row. Links to ADR-031 and ADR-035

**Checkpoint (PR-C Merge Gate)**: T195 asserts zero diff in core files (SC-013). T193 passes end-to-end. T194 asserts cross-source IDs do not collide.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Finalize ADRs, documentation, retention wiring, reconcile hooks, portal updates.

- [ ] T210 [P] Draft ADR-032 at `platforms/prosauai/decisions/ADR-032-content-processing-strategy.md` — Strategy pattern per ContentKind, ProcessorContext DI, Registry lookup, alternatives rejected (monolithic processor, discriminated union). Reference contracts/content-processor.md
- [ ] T211 [P] Draft ADR-034 at `platforms/prosauai/decisions/ADR-034-media-retention-policy.md` — URL 14d + transcript 90d + raw bytes never persisted (LGPD, FR-027/FR-028). Extends ADR-018
- [ ] T212 [P] Update `platforms/prosauai/decisions/ADR-029-pricing-constant.md` with an addendum noting whisper-1 and gpt-4o-mini-vision entries added in epic 009. OR add a new ADR-029-addendum file if history-preservation matters in the project's ADR convention
- [ ] T213 [P] Update `platforms/prosauai/engineering/containers.md` — add `Content Processing` and `Channel Ingestion` as new logical containers within the existing FastAPI process. Update Mermaid C4 L2 diagram. Preserve dominant structure from epic 008
- [ ] T214 [P] Update `platforms/prosauai/engineering/context-map.md` — add `Ingestion` (with Evolution and Meta Cloud sub-contexts) and `Content Processing` bounded contexts with arrows to existing `Conversation Pipeline`
- [ ] T215 [P] Update `platforms/prosauai/engineering/domain-model.md` — add aggregate `MediaAnalysis` (admin-only, ADR-027 carve-out), `ProcessorUsageDaily` (aggregate-less). Note `CanonicalInboundMessage` replaces `InboundMessage`
- [ ] T216 [P] Update `platforms/prosauai/planning/roadmap.md` — mark epic 009 status `in_progress` → `shipped` upon merge; add follow-up epics 010 (Instagram/Telegram), 011 (PDF OCR), 012 (streaming transcription)
- [ ] T217 [P] Create `platforms/prosauai/business/features.md` entries for "Transcrição de áudio", "Descrição de imagem", "Extração de texto de documentos", "Suporte a Meta Cloud API" — PT-BR, business-facing language
- [ ] T218 [P] Add `CHANGELOG.md` entries to prosauai repo: PR-A (Canonical + EvolutionAdapter), PR-B (Processors + cache + budget), PR-C (MetaCloud adapter). Include rollback instructions per PR
- [ ] T219 [P] Run `apps/api && ruff format apps/api/prosauai/{channels,processors,api/webhooks,pipeline/steps}/` + `ruff check --fix` — enforce lint on new code
- [ ] T220 Cost-projection analysis: run `apps/api/tests/benchmarks/test_audio_e2e.py --cost-projection` (new flag) — projects monthly cost per tenant at 10k media/month. Document in `apps/api/docs/cost-projection.md`. Invalidates kill_criteria if > $500/month/tenant (plan.md kill_criteria)
- [ ] T221 Update `apps/api/README.md` with `Channels` and `Processors` sections linking to contracts/README.md and channels/README.md
- [ ] T222 [P] Run full regression: `apps/api && pytest tests/ -x` — 173+191+new tests all PASS (SC-010 final)
- [ ] T223 Run reconcile dry-run from madruga.ai: `python3 .specify/scripts/reverse_reconcile_ingest.py --platform prosauai --dry-run --json` — expect zero drift (artifacts match code 1:1)
- [ ] T224 Validate quickstart.md end-to-end: follow every step in `platforms/prosauai/epics/009-channel-ingestion-and-content-processing/quickstart.md` §1-§3 against a local stack. Record notes in `easter-tracking.md`

**Checkpoint**: Epic documentation complete, ADRs 030-035 drafted and linked, regression suite green, quickstart.md verified end-to-end.

---

## Phase 11: Deployment Smoke

**Purpose**: Validate the running system against `platforms/prosauai/platform.yaml::testing` (docker startup). Gate ALL tasks above must be complete and merged before Smoke runs.

- [ ] T1100 Executar `docker compose build` no diretório da plataforma — build sem erros
- [ ] T1101 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks respondem dentro do ready_timeout
- [ ] T1102 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero required_env vars ausentes no .env
- [ ] T1103 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as URLs acessíveis com status esperado
- [ ] T1104 Capturar screenshot de cada URL `type: frontend` declarada em `testing.urls` — conteúdo não é placeholder
- [ ] T1105 Executar Journey J-001 (happy path) declarado em `testing/journeys.md` — todos os steps com assertions OK

**Checkpoint**: System boots cleanly in Docker, all env vars + URLs valid, frontend renders real content, happy-path journey green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1. BLOCKS all user stories. Must pass PR-A merge gate (173+191 tests PASS, latency baseline+5ms)
- **Phase 3 (US5 — flags/budget/cache/breaker infra)**: Depends on Phase 2 — P1 priority and enables budget enforcement for US1/US2
- **Phase 4 (US1 — Audio MVP)**: Depends on Phase 3 — STT/cache/budget required
- **Phase 5 (US2 — Image)**: Depends on Phase 3 — vision/cache/budget required. Can run in parallel with Phase 4
- **Phase 6 (US4 — Trace Explorer)**: Depends on Phase 4 OR Phase 5 (needs real persist from at least one processor to validate E2E). Parallel-safe after US1 is feature-complete
- **Phase 7 (US3 — Document)**: Depends on Phase 3 (cache). Parallel with US1/US2. P2 — cut-candidate if timeline slips
- **Phase 8 (US7 — Light kinds)**: Depends on Phase 3 (only feature flag path). Parallel with all above. P3 — cut-candidate
- **Phase 9 (US6 — Meta Cloud)**: Depends on Phase 2 solid + at least one Processor live (Phase 4 recommended — lets US6 reuse AudioProcessor to validate SC-013). PR-C. Cut-candidate if Phase 4-7 slip
- **Phase 10 (Polish)**: Depends on Phases 4, 5, 6 minimum. ADRs can be drafted in parallel with each PR
- **Phase 11 (Deployment Smoke)**: Depends on ALL prior phases merged to `develop`

### User Story Dependencies

- **US1 (P1, Audio)**: Depends on US5 infra (feature flags, budget, cache, breaker). No other US dependencies
- **US2 (P1, Image)**: Depends on US5 infra. Independent of US1
- **US4 (P1, Admin audit)**: Depends on US1 OR US2 producing real persist rows to render in admin
- **US5 (P1, Flags/budget)**: Depends only on Phase 2 (Foundational)
- **US3 (P2, Document)**: Depends on US5 (cache only — skips budget)
- **US6 (P2, Meta Cloud)**: Depends on Phase 2 solid; pairs with at least US1 being live to validate SC-013 at runtime
- **US7 (P3, Light kinds)**: Depends only on US5 infra (feature flag scaffolding)

### Within Each User Story

- Tests (T0XX [P]) — write FIRST, ensure they FAIL before implementation (TDD gate per Constitution)
- Providers before Processors (e.g., T100 OpenAISTTProvider before T101 AudioProcessor)
- Processors before registry wiring (T101 before T103 register in main)
- Registry wiring before pipeline step integration (T103 before T104 wire path)
- Pipeline integration before integration tests (T104 before T092 E2E)
- Observability spans/persist parallel with processor implementation

### Parallel Opportunities

- **Phase 2 parallel**: T012, T015, T020, T022 (tests/contracts) can run alongside schema/Protocol writes (T010, T013, T016, T018). Also T024 (retention cron) + T034 (request compat) + T047 (debounce test) + T048/T049 (fixtures)
- **Phase 3 parallel**: T060-T065 (tests), T076-T081 (infra components) — each on different files
- **Phase 4 (US1) parallel**: T090-T094 tests; T100 (provider) vs T102 (hallucination filter) vs T107 (lint) vs T108 (ADR)
- **Phase 5 (US2) parallel**: T110-T113 tests; T120 (provider) vs T124 (spans) vs T125 (PII test)
- **Phase 6 (US4) parallel**: T130, T131 Playwright independently scoped; T140 (repo) vs T143 (React) vs T146 (transcript endpoint) vs T147 (inbox bubble)
- **Phase 7 (US3) parallel**: T150-T153 tests; T160 (extractor) vs T163 (spans)
- **Phase 8 (US7) parallel**: T170-T176 all parallel (different processor files); T180-T184 all parallel
- **Phase 9 (US6) parallel**: T190-T195 tests; T200 (fixtures) vs T206 (CLI helper) vs T207 (ADR) vs T208 (README)
- **Phase 10 parallel**: T210-T219 all [P]

### Cross-story parallel teams

After Phase 3 (US5) completes:

- **Developer A**: US1 (Audio — Phase 4)
- **Developer B**: US2 (Image — Phase 5) 
- **Developer C**: US7 (Light kinds — Phase 8) + US4 admin UI (Phase 6 T143-T144) once US1/US2 integrate

After Phase 4 (US1) merge:

- Developer A: US4 persist wiring (Phase 6 T140, T145-T147)
- Developer B: US3 (Document — Phase 7)
- Developer C: US6 (Meta Cloud — Phase 9)

---

## Parallel Example: User Story 1 (Audio — MVP)

```bash
# Batch A — Tests first (TDD):
Task: "Contract test row for AudioProcessor in apps/api/tests/contract/test_content_processor_contract.py"
Task: "Unit test for AudioProcessor happy/cache/hallucination/base64 in apps/api/tests/unit/processors/test_audio.py"
Task: "Integration test audio end-to-end in apps/api/tests/integration/test_audio_end_to_end.py"
Task: "Multi-message flush test in apps/api/tests/integration/test_audio_multi_message_flush.py"
Task: "Benchmark test_audio_e2e.py gate SC-001"

# Batch B — Implementation (after tests FAIL as expected):
Task: "OpenAISTTProvider in apps/api/prosauai/processors/providers/openai_stt.py"
Task: "Hallucination filter in apps/api/prosauai/processors/hallucination_filter.py"
# Then sequential:
Task: "AudioProcessor in apps/api/prosauai/processors/audio.py (depends on provider + filter)"
Task: "Register + wire in main.py + pipeline/steps/content_process.py"
Task: "Fire-and-forget persist in apps/api/prosauai/observability/media_analyses_repo.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only + gates)

1. Phase 1: Setup (T001-T008)
2. Phase 2: Foundational — PR-A (T010-T053)
3. Merge PR-A (gate SC-009 + SC-010 texto + trace waterfall)
4. Phase 3: US5 infra — half of PR-B (T060-T082)
5. Phase 4: US1 Audio (T090-T108)
6. **STOP AND VALIDATE**: Audio end-to-end demo with real Ariel tenant. Validate SC-001, SC-004, SC-005
7. Ship PR-B to staging

### Incremental Delivery (Full epic)

1. PR-A (Phases 1-2) → staging → bake 24h → prod for Ariel
2. PR-B infra + US1 (Phases 3-4) → staging → bake 48h → prod for Ariel
3. Add US2 (Phase 5), US4 (Phase 6), US3 (Phase 7), US7 (Phase 8) — bundled or drip
4. Merge PR-B → staging → bake 7d in Ariel → enable ResenhAI
5. PR-C (Phase 9 + SC-013 gate) → staging → ship
6. Polish (Phase 10) + Smoke (Phase 11) → close epic

### Cut-line Decision Points

- **Week 4 EOD review**: if Phase 7 (US3 Document) and Phase 8 (US7 Light kinds) are not done AND Phase 9 (US6 Meta Cloud) hasn't started → drop Phase 9, defer to epic 010. Document in `easter-tracking.md` + roadmap
- **Week 5 EOD review**: if Phase 9 T195 (SC-013 diff gate) FAILS → abstraction is Evolution-shaped; do NOT force-merge. Revisit Phase 2 Canonical model in a follow-up mini-epic

### Parallel Team Strategy

With 3 developers:

1. Sprint 1 (Week 1): all 3 on Phase 2 Foundational — critical path. Split: Dev A owns canonical/protocols (T010-T020), Dev B owns migrations/STEP_NAMES/step6 stub (T021-T031), Dev C owns EvolutionAdapter + webhook split (T035-T049). Dev A owns ConversationRequest refactor (T032-T034) in parallel
2. Sprint 2 (Week 2): Dev A → US5 infra (Phase 3); Dev B + C → drive 173+191 regression to GREEN, then start US1/US2 tests
3. Sprint 3 (Week 3): Dev A → US1 finish; Dev B → US2; Dev C → US4 admin UI
4. Sprint 4 (Week 4): Dev A → US3; Dev B → US7; Dev C → Meta Cloud kick-off + fixtures
5. Sprint 5 (Week 5): Dev A + B → Polish (ADRs, docs); Dev C → US6 finish + SC-013 gate

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability and gate evaluation
- Each user story (US1..US7) is independently completable and testable
- Verify tests fail BEFORE implementation (TDD — Constitution Principle VII)
- Commit after each task or logical group; use conventional prefixes `feat:`, `fix:`, `chore:`
- PR commit messages MUST include trailer `Epic: 009-channel-ingestion-and-content-processing` for reverse-reconcile attribution (see CLAUDE.md reverse-reconcile loop invariants)
- Stop at each Checkpoint to validate story independently
- Avoid: vague tasks, same-file parallel conflicts, cross-story dependencies that break independence
- SC-013 gate (zero diff in `pipeline.py` / `processors/` / `core/router/` for PR-C) is automated in T195 — run in CI as required status check

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "tasks.md consolidated with 11 phases, ~165 tasks. Phase 2 (Foundational/PR-A) unblocks all 7 user stories; Phases 3-8 cover the 7 user stories priority-ordered (US5/US1/US2/US4 P1 → US3/US6 P2 → US7 P3); Phase 9 is PR-C Meta Cloud with SC-013 diff gate; Phase 10 Polish; Phase 11 auto-added Deployment Smoke (platform.yaml has testing.startup.type=docker). Tests explicit per contract gate (SC-010: 173+191 pass unchanged). Parallelism annotated with [P]. Cut-line explicit at Phase 7/8/9."
  blockers: []
  confidence: Alta
  kill_criteria: "Invalidated if (a) Phase 2 T050 can't achieve 173+191 tests PASS without substantial rework (forces rearchitecting Canonical model), (b) T094 benchmark shows audio p95 > 15s with realistic Whisper mock (forces UX sync→async debate from pitch D3), or (c) T195 SC-013 diff gate fails (pipeline or processors must change to accept MetaCloud — means ChannelAdapter abstraction is Evolution-shaped and needs redesign before PR-A goes to prod)."
