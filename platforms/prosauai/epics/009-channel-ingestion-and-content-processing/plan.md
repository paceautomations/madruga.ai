# Implementation Plan: Channel Ingestion Normalization + Content Processing

**Branch**: `epic/prosauai/009-channel-ingestion-and-content-processing` | **Date**: 2026-04-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/009-channel-ingestion-and-content-processing/spec.md`

## Summary

Refatorar a camada de entrada do prosauai em **dois módulos formais source-agnostic** — `Channel Ingestion` (pattern adapter/strategy por canal) e `Content Processing` (pattern strategy por `ContentBlock.kind`) — habilitando (a) processamento real de áudio (Whisper), imagem (GPT-4o-mini vision), documentos PDF/DOCX, stickers, reações, localização e contatos; (b) observabilidade completa de cada análise de mídia (custo, latência, cache hit, transcript) no Trace Explorer (entregue no epic 008); e (c) validação arquitetural ao plugar um segundo adapter real (Meta Cloud API) sem nenhuma alteração em `pipeline/`, `processors/` ou `core/router/` (gate SC-013).

**Abordagem técnica**: tríade Pydantic in-process `CanonicalInboundMessage` → `ContentBlock` (união discriminada por `kind`) → `ProcessedContent` (resultado do processor). Pipeline ganha 2 steps novos (`content_process` #6 no waterfall, `STEP_NAMES` 12→14). Duas tabelas novas admin-only em `public.*` (`media_analyses`, `processor_usage_daily`) sob carve-out [ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md). Cache Redis (`proc:*`, TTL 14d) + budget enforcement per-tenant + circuit breaker (5 falhas/60s → 30s open + backoff exponencial) + retry com jitter ±25%. Persistência fire-and-forget ([ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md)) garante zero impacto no caminho crítico. **Estratégia unificada de fallback** (FR-031): todo erro/limite produz `ProcessedContent.marker` em bracket notation; LLM de resposta traduz em mensagem tonalizada conforme persona do tenant; hard-coded string por tenant em `fallback_messages.{marker}` serve como última rede.

Execução em **3 PRs mergeáveis isoladamente em `develop`**, cada um reversível via feature flag por tenant:
- **PR-A (2 semanas)** Canonical schema + EvolutionAdapter + step 6 stub (`TextProcessor` identity). Texto passa idêntico, mídia aparece no trace mas retorna fallback textual.
- **PR-B (2 semanas)** Processors reais (audio/image/document/others), cache, budget, admin UI (gráfico custo diário).
- **PR-C (1 semana)** Meta Cloud Adapter. Gate de merge = diff zero em core (prova que abstração suporta segundo canal).

Cut-line explícito (se PR-B estourar semana 4): cortar PR-C → validação arquitetural vira follow-up epic 010. Valor user-facing (mídia funcionando) é entrega mínima.

## Technical Context

**Language/Version**: Python 3.12 (backend FastAPI; nenhuma alteração frontend — admin do epic 008 renderiza `content_process` via `StepAccordion` genérico sem código novo)

**Primary Dependencies**:
- Existentes: FastAPI >=0.115, pydantic 2.x, asyncpg >=0.30, redis[hiredis] >=5.0, httpx, structlog, opentelemetry-sdk, opentelemetry-instrumentation-{fastapi,httpx,redis}, arize-phoenix-otel (epic 002).
- **Novas**: `openai>=1.50`, `pypdf>=4.0`, `python-docx>=1.1`.

**Storage**:
- PostgreSQL 15 (Supabase) — 2 migrations novas (`20260420_create_media_analyses.sql` em PR-A, `20260505_create_processor_usage_daily.sql` em PR-B); zero alteração em tabelas existentes. Acesso admin via `pool_admin` (BYPASSRLS, epic 008) herdando carve-out ADR-027.
- Redis 7 — novo prefixo `proc:*` (TTL 14d, LRU compartilhada). Não conflita com `buf:*` (debounce epic 001), `ps:*` (handoff epic 004), `idem:*` (idempotência epic 003).

**Testing**: pytest + testcontainers-postgres + fakeredis + respx (httpx mock) + `AsyncMock` para AsyncOpenAI. Cobertura alvo: processors ≥90%, adapters/auth ≥95%. Fixtures: 13 Evolution reais (reuso existente) + 4 Meta Cloud reais (PR-C) + casos de borda (PDF encriptado, áudio 25MB, URL expirada 410).

**Target Platform**: Linux server (uvicorn workers em container); OpenAI API público (STT + vision); Evolution API existente (sem alteração); Meta Cloud API sandbox (apenas PR-C).

**Project Type**: Backend-heavy refactor + nova integração provider. Frontend admin reusado sem mudança estrutural (só extensão de `STEP_NAMES` lista + 1 gráfico Recharts na Performance AI).

**Performance Goals**:
- p95 **texto** pós-PR-A: ≤ baseline (epic 008) +5ms (gate de merge PR-A).
- p95 **áudio 10s end-to-end**: < 8s (SC-001, gate PR-B).
- p95 **imagem** end-to-end: < 9s (SC-002).
- p95 **documento 3 páginas** end-to-end: < 10s (SC-003).
- Cache hit rate após 7d prod: ≥ 30% (SC-007).
- Overhead do step `content_process` quando `kind=text`: < 1ms (pure passthrough).

**Constraints**:
- **Zero regressão** nos 173 tests epic 005 + 191 tests epic 008 — gate obrigatório de merge de cada PR (SC-010).
- **Persistência fire-and-forget**: falha de insert em `media_analyses`/`processor_usage_daily` NUNCA bloqueia a resposta ao cliente ([ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md)).
- **Bytes raw NUNCA persistidos**: memória apenas; URL signed WhatsApp tem retenção 14d alinhada com expiração natural do Meta; transcript plaintext 90d em `media_analyses.text_result` (FR-027/FR-028).
- **Adapter é tradutor puro**: NÃO acessa DB, Redis, LLM ou OTel (emitido pelo pipeline).
- **Processor nunca instancia SDK** — tudo via `ProcessorContext.providers` (testabilidade + swap futuro).
- **Feature flag reload**: poll periódico 60s por worker — RTO rollback ≤60s sem deploy (FR-017).
- **Idempotency key canônico**: `sha256(source + source_instance + external_message_id)` — evita colisão cross-source (decisão D11).
- **Retrocompat webhook**: alias `/webhook/whatsapp/{instance_name}` → handler Evolution (FR-005); remoção em epic futuro.

**Scale/Scope**:
- 2 tenants ativos (Ariel, ResenhAI); rollout progressivo (Ariel primeiro, ResenhAI após 7d em prod sem regressão).
- Volume planejado: **10k+ mídias/mês/tenant** (decisão D7) → força cache + budget + circuit breaker obrigatórios.
- Nova camada: ~14 arquivos Python (`channels/`, `processors/`), 2 migrations, 0 frontend novo.
- Scope-out explícito: Instagram, Telegram, video frames, PDF tabular, streaming transcription, detecção OCR auto em PDF escaneado (epics 010-012).

## Constitution Check

*GATE: passa antes do Phase 0 research. Re-checked após Phase 1 design.*

| Princípio | Avaliação | Justificativa |
|-----------|-----------|---------------|
| I — Pragmatismo & Simplicidade | ✅ | Reusa 100% da stack Python do prosauai. Zero libs novas além de openai+pypdf+python-docx. Pydantic Protocol pattern (stdlib-compatible). Tabelas admin-only herdam carve-out ADR-027 existente. Nenhum framework novo. |
| II — Automate repetitive | ✅ | Retention cron do epic 006 estendido (não recriado). Fire-and-forget pattern do ADR-028 reusado. Pricing table ADR-029 estendido com 2 linhas (whisper + vision). OTel auto-instrumentation já cobre httpx → OpenAI. |
| III — Knowledge structured | ✅ | `decisions.md` com 22 micro-decisões. 6 ADRs novos (030 canonical, 031 adapter, 032 processor strategy, 033 OpenAI provider, 034 media retention, 035 meta cloud) estendem 029/027/018/011 existentes sem substituir. `research.md` preserva escopo técnico integral. |
| IV — Fast action | ✅ | 3 PRs sequenciais com cut-line explícito (PR-C é sacrificável se PR-B estourar). Daily checkpoint em `easter-tracking.md` (convenção 008) flagra bleed cedo. Reconcile após cada PR-merge. |
| V — Alternativas & trade-offs | ✅ | `research.md` §9 documenta 5 decisões rejeitadas (discriminated union, S3 raw bytes, tabela processor_runs, compressão cache, text_result só em trace_steps). Spec §Assumptions registra UX síncrona vs. async, provider lock-in OpenAI, cache storage JSON. |
| VI — Brutal honesty | ✅ | Spec §Clarifications expõe 5 Q&As autonomamente resolvidas na clarify pass. Pitch §Appetite mostra cut-line explícito. Assumption "se p95 áudio > 5s em 1 mês, revisitar UX em retro". Provider OpenAI é lock-in consciente. |
| VII — TDD | ✅ | 3 camadas (contract tests para Protocols + unit ≥90% processors/adapters + integration testcontainers + E2E Playwright). Gate merge PR-A: 173+191 tests passam. Cada PR tem benchmark script (latency gate). Contract tests bloqueiam drift de Protocol. |
| VIII — Collaborative decisions | ✅ | 5 ambiguidades resolvidas no clarify (marker+LLM fallback strategy, circuit breaker numérico, reload 60s, unsupported kinds com sub_type, metodologia amostragem SC-011/SC-012). |
| IX — Observability | ✅ | 6 OTel spans novos (`processor.audio.transcribe`, `processor.image.describe`, `processor.document.extract`, `openai.whisper.create`, `openai.vision.responses.create`, `content_process.step`). `media_analyses` é audit trail completo sem truncamento. `processor_usage_daily` alimenta Performance AI tab. Markers em trace_steps facilitam análise de volume de incidentes (FR-032). |

**Violações**: nenhuma. `Complexity Tracking` vazio.

### Post-Phase-1 re-check

| Risco | Status |
|-------|--------|
| `ConversationRequest` refactor quebra 173 tests (R1) | Mitigado: gate merge PR-A ("173+191 tests PASS") + deprecation shim 1 release + test compat-layer |
| Latência inline > 5s degrada UX (R2) | Mitigado: budget 15s audio/12s image; cache agressivo 14d TTL; revisita via retro se p95 > 5s |
| MetaCloudAdapter descobre abstração Evolution-shaped (R3) | Mitigado: test-first (`MetaCloudAdapter.normalize()` contra fixtures ANTES de terminar PR-A); SC-013 gate (diff zero core) |
| Explosão de storage em `media_analyses.raw_response` | Mitigado: truncate 32KB no insert; anulação em 14d junto com source_url |
| Feature flag race window budget | Aceito: ≤1 chamada acima do limite por minuto (Assumption §Budget) — gradiente converge via retries |
| Bump de `prompt_version` invalida cache + custo de transição | Mitigado: ~$30 extra em 14d por bump; aceitável (D19) |
| Idempotency key colisão cross-source | Mitigado: `sha256(source+instance+ext_id)` — source entra no input (D11) |
| Feature disabled via yaml não chega a todos os workers | Aceito: poll 60s worker-local; durante janela, request pode bater provider (conta no budget) |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/009-channel-ingestion-and-content-processing/
├── plan.md                  # Este arquivo (/speckit.plan output)
├── spec.md                  # Feature specification (pós-clarify, 32 FRs + 16 SCs)
├── pitch.md                 # Shape Up pitch (L2 — epic-context)
├── decisions.md             # 22 micro-decisões capturadas
├── research.md              # Phase 0 — escopo técnico integral (ex-EPIC009_full_escope.md)
├── data-model.md            # Phase 1 — schemas Pydantic + SQL + ER diagram + Redis namespaces
├── contracts/
│   ├── README.md            # Índice + gates de contrato
│   ├── channel-adapter.md   # Protocol ChannelAdapter (Python)
│   ├── content-processor.md # Protocol ContentProcessor + ProcessorContext (Python)
│   └── openapi.yaml         # OpenAPI 3.1 (webhooks Evolution + Meta Cloud + alias legado)
├── quickstart.md            # Phase 1 — setup dev + validação US1-US7 + rollback
└── tasks.md                 # Phase 2 output (gerado por /speckit.tasks — NÃO por este comando)
```

### Source Code (repository root — repo externo `paceautomations/prosauai`)

```text
apps/
├── api/                                              # backend FastAPI (existente)
│   ├── prosauai/
│   │   ├── main.py                                   # register adapters via registry (aditivo)
│   │   ├── config.py                                 # EXTEND: OPENAI_API_KEY, processor defaults, poll_interval=60
│   │   ├── api/
│   │   │   ├── webhooks.py                           # DEPRECATED → alias forwarder (retrocompat FR-005)
│   │   │   └── webhooks/                             # NEW — handlers por canal
│   │   │       ├── __init__.py
│   │   │       ├── dispatch.py                       # NEW — lógica comum (tenant resolve, auth, debounce enqueue)
│   │   │       ├── evolution.py                      # NEW — POST /webhook/evolution/{instance_name}
│   │   │       └── meta_cloud.py                     # NEW (PR-C) — GET/POST /webhook/meta_cloud/{tenant_slug}
│   │   ├── channels/                                 # REFATORADO — antes só evolution.py (outbound)
│   │   │   ├── __init__.py
│   │   │   ├── canonical.py                          # NEW — CanonicalInboundMessage, ContentBlock, ContentKind
│   │   │   ├── base.py                               # NEW — ChannelAdapter Protocol + errors
│   │   │   ├── registry.py                           # NEW — register/get/registered_sources
│   │   │   ├── inbound/                              # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── evolution/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── adapter.py                    # NEW — EvolutionAdapter (migrado de formatter.py)
│   │   │   │   │   └── auth.py                       # NEW — X-Webhook-Secret verify
│   │   │   │   └── meta_cloud/                       # NEW (PR-C)
│   │   │   │       ├── __init__.py
│   │   │   │       ├── adapter.py                    # NEW — MetaCloudAdapter
│   │   │   │       └── auth.py                       # NEW — HMAC X-Hub-Signature-256 verify
│   │   │   └── outbound/
│   │   │       └── evolution.py                      # MOVED — ex channels/evolution.py (delivery)
│   │   ├── processors/                               # NEW — content processing layer (PR-B)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                               # ContentProcessor Protocol + ProcessorContext
│   │   │   ├── registry.py                           # register/get por ContentKind
│   │   │   ├── result.py                             # ProcessedContent model + ProcessorStatus enum
│   │   │   ├── cache.py                              # ProcessorCache (Redis proc:*)
│   │   │   ├── budget.py                             # BudgetTracker (processor_usage_daily)
│   │   │   ├── breaker.py                            # CircuitBreaker (por tenant+provider)
│   │   │   ├── providers/                            # NEW — provider wrappers
│   │   │   │   ├── __init__.py
│   │   │   │   ├── openai_stt.py                     # OpenAI Whisper wrapper
│   │   │   │   ├── openai_vision.py                  # OpenAI Responses API (gpt-4o-mini)
│   │   │   │   └── local_document.py                 # pypdf + python-docx
│   │   │   ├── text.py                               # TextProcessor (identity, PR-A stub)
│   │   │   ├── audio.py                              # AudioProcessor (PR-B)
│   │   │   ├── image.py                              # ImageProcessor (PR-B)
│   │   │   ├── document.py                           # DocumentProcessor (PR-B)
│   │   │   ├── sticker.py                            # StickerProcessor (deterministic)
│   │   │   ├── location.py                           # LocationProcessor
│   │   │   ├── contact.py                            # ContactProcessor
│   │   │   ├── reaction.py                           # ReactionProcessor
│   │   │   ├── unsupported.py                        # UnsupportedProcessor (marker [content_unsupported: {sub_type}])
│   │   │   └── errors.py                             # MediaTooLarge, ProviderError, etc
│   │   ├── core/
│   │   │   ├── formatter.py                          # DEPRECATED → thin re-export durante PR-A1..A3
│   │   │   ├── debounce.py                           # EXTEND: flush retorna list[CanonicalInboundMessage]
│   │   │   └── router/
│   │   │       └── facts.py                          # EXTEND: _derive_content_kind lê canonical.content[0].kind
│   │   ├── conversation/
│   │   │   ├── request.py                            # EXTEND: ConversationRequest.canonical_messages (list)
│   │   │   └── request_compat.py                     # NEW — shim @deprecated aceitando `text` legacy 1 release
│   │   ├── observability/
│   │   │   ├── step_record.py                        # EXTEND: STEP_NAMES 12→14, order validation 1..14
│   │   │   └── pricing.py                            # EXTEND: PRICING_TABLE += whisper-1, gpt-4o-mini vision
│   │   ├── pipeline/                                 # existente
│   │   │   └── steps/
│   │   │       └── content_process.py                # NEW — step #6 (delega a processors.registry)
│   │   └── admin/                                    # existente do epic 008
│   │       └── metrics/
│   │           └── performance.py                    # EXTEND: query processor_usage_daily para gráfico custo
│   ├── db/
│   │   └── migrations/
│   │       ├── 20260420_create_media_analyses.sql          # NEW (PR-A)
│   │       └── 20260505_create_processor_usage_daily.sql   # NEW (PR-B)
│   ├── tests/
│   │   ├── contract/
│   │   │   ├── test_channel_adapter_contract.py            # NEW — Protocol conformance
│   │   │   └── test_content_processor_contract.py          # NEW
│   │   ├── unit/
│   │   │   ├── channels/
│   │   │   │   ├── test_evolution_adapter.py               # NEW
│   │   │   │   └── test_meta_cloud_adapter.py              # NEW (PR-C)
│   │   │   ├── processors/
│   │   │   │   ├── test_audio.py                           # NEW
│   │   │   │   ├── test_image.py                           # NEW
│   │   │   │   ├── test_document.py                        # NEW
│   │   │   │   ├── test_cache.py                           # NEW
│   │   │   │   ├── test_budget.py                          # NEW
│   │   │   │   └── test_breaker.py                         # NEW
│   │   ├── integration/
│   │   │   ├── test_audio_end_to_end.py                    # NEW
│   │   │   ├── test_image_end_to_end.py                    # NEW
│   │   │   └── test_budget_exceeded_fallback.py            # NEW
│   │   ├── benchmarks/
│   │   │   ├── test_text_latency.py                        # NEW — gate SC-009 (PR-A)
│   │   │   └── test_audio_e2e.py                           # NEW — gate SC-001 (PR-B)
│   │   └── fixtures/
│   │       ├── canonical/                                  # NEW (PR-A) — JSON do output normalizado
│   │       │   └── *.canonical.json                        # 13 Evolution + 4 Meta Cloud
│   │       └── captured/
│   │           └── meta_cloud_*.input.json                 # NEW (PR-C) — 4 payloads reais
│   └── scripts/
│       └── sign_meta_webhook.py                            # NEW (PR-C) — helper HMAC para dev
├── admin/                                             # Next.js — epic 008 (sem mudança estrutural)
│   └── src/
│       └── app/performance-ai/
│           └── page.tsx                               # EXTEND: +1 Recharts stacked bar "Custo mídia/dia"
└── tenants.yaml                                       # EXTEND: content_processing.* por tenant + fallback_messages
```

**Structure Decision**: Backend-heavy refactor em `apps/api/prosauai/`. Dois novos módulos formais (`channels/`, `processors/`) com Protocol-based contracts. Zero novo projeto/package Python — tudo sob o namespace `prosauai.*` existente. Frontend admin do epic 008 ganha apenas 1 gráfico novo + 1 entry em `STEP_NAMES`. Testes reutilizam estrutura `tests/{contract,unit,integration,benchmarks,fixtures}` já estabelecida.

## Complexity Tracking

> Nenhuma violação de Constitution Check identificada. Esta tabela permanece vazia.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 — Research (already complete)

**Output**: [research.md](./research.md) — preserva escopo técnico integral do `EPIC009_full_escope.md v2026-04-19`. Todas as `NEEDS CLARIFICATION` estão resolvidas:

- §1 "Decisões travadas (usuário confirmou 2026-04-19)" — 22 decisões locked com referências arquiteturais.
- [spec.md §Clarifications](./spec.md#clarifications) — 5 Q&As resolvidas autonomamente durante o clarify pass (marker+LLM fallback, circuit breaker numérico, reload 60s, unsupported kinds com sub_type, metodologia amostragem).
- [decisions.md](./decisions.md) — 22 decisões ordenadas com data, skill e referência.

**Alternativas consideradas e rejeitadas** (resumo — detalhes em `research.md` §9 e `data-model.md` §9):

| Alternativa | Rejeitada por |
|-------------|---------------|
| Discriminated Union Pydantic por `kind` (class AudioContent etc) | Aumenta complexidade de serialização; `attrs` achatados + validators é suficiente para v1 |
| Persistir raw bytes em S3 | LGPD FR-027 — memory-only; replay via URL signed enquanto válida |
| Tabela `processor_runs` + `media_analyses` | Duplicação sem ganho — `media_analyses` cobre audit; `processor_usage_daily` cobre agregação |
| Cache com compressão gzip | Payload < 2KB stripped → overhead > ganho |
| `text_result` só em `trace_steps.output_jsonb` | Truncate 8KB quebra transcripts longos; `media_analyses.text_result` TEXT completo |
| Webhook único `/webhook/{source}/...` genérico | Perde type safety por source; FastAPI auth decorator genérico fica complexo |
| Payload debounce com `CanonicalInboundMessage` serializado + `text` duplicado | Rejeitado por ambiguidade — payload carrega APENAS canonical (§7.3 research) |
| Streaming transcription (partial results) | Scope-out v1 (decisão D8) — complexidade alta, ganho marginal em PT-BR curto |

## Phase 1 — Design Artifacts

### Artefatos gerados neste plan

| Artefato | Propósito | Referência |
|----------|-----------|-----------|
| **data-model.md** | Schemas Pydantic (CanonicalInboundMessage, ContentBlock, ProcessedContent, ProcessorContext); SQL das 2 tabelas novas (migrations plan); Redis key pattern + TTL; extensão de `STEP_NAMES`; validações por camada; rejected alternatives | [data-model.md](./data-model.md) |
| **contracts/channel-adapter.md** | Protocol `ChannelAdapter` + `ChannelAdapterError`/`InvalidPayloadError`/`AuthError`; comportamento `verify_webhook` + `normalize` para Evolution e Meta Cloud; contract tests | [contracts/channel-adapter.md](./contracts/channel-adapter.md) |
| **contracts/content-processor.md** | Protocol `ContentProcessor` + `ProcessorContext` + `ProcessorCache` + `BudgetTracker`; pseudo-algoritmo genérico (9 passos); registry; policy de circuit breaker; contract tests | [contracts/content-processor.md](./contracts/content-processor.md) |
| **contracts/openapi.yaml** | OpenAPI 3.1 dos 4 endpoints (`POST /webhook/evolution/...`, `POST /webhook/whatsapp/...` alias, `GET/POST /webhook/meta_cloud/...`); schemas EvolutionWebhookPayload + MetaCloudWebhookPayload + AcceptedResponse + ErrorResponse | [contracts/openapi.yaml](./contracts/openapi.yaml) |
| **quickstart.md** | Setup dev + validação incremental por PR (PR-A / PR-B / PR-C); validação por User Story; rollback de emergência; troubleshooting | [quickstart.md](./quickstart.md) |

### ADRs planejados (6 novos, estendem 4 existentes)

Geração é tarefa explícita do PR-A (ADRs 030-031) e PR-B (ADRs 032-034), PR-C (ADR-035). Esboços já em `decisions.md`:

| # | Título | Escopo | PR |
|---|--------|--------|-----|
| ADR-030 | Canonical Inbound Message model | Substitui InboundMessage Evolution-specific | PR-A |
| ADR-031 | Multi-source channel adapter pattern | ChannelAdapter Protocol + registry | PR-A |
| ADR-032 | Content processing strategy | ContentProcessor Protocol + ProcessorContext | PR-B |
| ADR-033 | OpenAI as STT + vision provider (v1) | Whisper + gpt-4o-mini; documenta alternativas (Deepgram, Azure, Claude, Gemini) | PR-B |
| ADR-034 | Media retention policy | Estende ADR-018 (URL 14d, transcript 90d, raw never) | PR-B |
| ADR-035 | Meta Cloud adapter integration | Validação arquitetural do ADR-031 | PR-C |

### Agent context update

Após merge de cada PR, `update-agent-context.sh claude` é executado em CI para refletir:
- PR-A: novas tecnologias `openai>=1.50`
- PR-B: `pypdf>=4.0`, `python-docx>=1.1`
- PR-C: nenhuma tech nova

---

## Sequenciamento & guardrails

### Cronograma

| Semana | PR | Entregáveis | Gate de merge |
|--------|----|-------------|---------------|
| 1 | PR-A coding | ADRs 030-031 draft; `canonical.py`, `channels/base.py`, `registry.py`; `EvolutionAdapter.normalize()`; migration `media_analyses`; step 6 stub (TextProcessor identity); `ConversationRequest.canonical_messages`; `STEP_NAMES` 14 entries; alias `/webhook/whatsapp/` | — |
| 2 | PR-A merge | 173+191 tests PASS; latência texto ≤baseline+5ms; payload mídia aparece no trace com `content_process.output.providers=["text-placeholder"]` | SC-009, SC-010 |
| 2-3 | PR-B coding audio/image | `AudioProcessor` + `openai_stt.py`; `ImageProcessor` + `openai_vision.py`; `ProcessorCache`, `BudgetTracker`, `CircuitBreaker`; migration `processor_usage_daily`; `pricing.py` extends; `tenants.yaml` schema | — |
| 3-4 | PR-B coding document/others + admin | `DocumentProcessor` + `local_document.py`; `StickerProcessor`, `LocationProcessor`, `ContactProcessor`, `ReactionProcessor`, `UnsupportedProcessor`; admin Performance AI gráfico custo diário | — |
| 4 | PR-B merge | Áudio real (mocked Whisper) responde em ≤8s p95 (SC-001); imagem ≤9s (SC-002); budget exceeded → marker+LLM fallback (SC-008); 173+191 tests PASS | SC-001, SC-002, SC-008, SC-010 |
| 5 | PR-C coding + merge | ADR-035; `MetaCloudAdapter.normalize()` + auth HMAC; fixtures 4 reais; handler `/webhook/meta_cloud/`; diff zero em `pipeline/`/`processors/`/`core/router/` (SC-013) | SC-013, SC-014 |

### Reconcile após cada PR-merge

Hook automático fire do `madruga:reconcile` detecta drift entre docs e código implementado. Esperado: zero drift (artefatos Phase 1 detalham 1:1 o código-alvo).

### Cut-line explícito

Se PR-B estourar semana 4 → cortar PR-C → validação arquitetural vira follow-up epic 010. Critério: valor user-facing (mídia funcionando) é entrega mínima. PR-C sem PR-B = zero valor ao cliente.

### Daily checkpoint

`easter-tracking.md` (convenção do epic 008) flagra bleed cedo. Daily standup async com 3 bullets: (a) o que foi mergeável ontem, (b) o que é mergeável hoje, (c) o que está bloqueando.

---

## Testing strategy (resumo)

- **Unit** (≥90% processors, ≥95% adapters/auth): `respx` para httpx mock; `AsyncMock` para AsyncOpenAI; `fakeredis` para cache; `freezegun` para budget reset date.
- **Contract** (Protocol conformance): `isinstance(adapter, ChannelAdapter)`, `isinstance(processor, ContentProcessor)`. Garante que novos adapters/processors respeitam API.
- **Integration** (testcontainers-postgres + fakeredis + OpenAI mocked): fluxos completos por source+kind.
- **E2E Playwright** (reuso infra epic 008): abrir Trace Explorer → expandir step `content_process` → confirmar transcript visível.
- **Benchmarks** (gate merge): `test_text_latency.py` (SC-009 PR-A), `test_audio_e2e.py` (SC-001 PR-B).
- **Fixtures reais**: 13 Evolution em `tests/fixtures/captured/` existentes + 4 Meta Cloud novos em PR-C + casos de borda (PDF encriptado, áudio 25MB, URL expirada 410).

---

## Dependências externas

| Item | Origem | Escopo |
|------|--------|--------|
| OpenAI API key | `OPENAI_API_KEY` env | PR-B (Whisper + vision) |
| Evolution API operacional | Existente | Todos PRs (sem mudança) |
| Meta Business App sandbox | Novo account prosauai | Apenas PR-C |
| Bibliotecas Python: `openai>=1.50`, `pypdf>=4.0`, `python-docx>=1.1` | PyPI | PR-A/B |

**Sem blockers**: epic 008 foi fechado 2026-04-19; infraestrutura Redis 7 + Postgres 15 via Supabase já provisionada; OpenAI account ativa via `platform@prosauai.com`.

---

## Estrutura de PR (contratos explícitos)

Cada PR carrega:

1. **Descrição**: qual decisão arquitetural está sendo entregue + qual User Story(ies) são servidas.
2. **Checklist de gates**: itens SC-NNN que devem passar antes do merge.
3. **Rollback plan**: sequência exata para desligar a feature se quebrar prod.
4. **Observability plan**: quais métricas acompanhar nas primeiras 24h em staging.

Template de descrição em `.github/PULL_REQUEST_TEMPLATE.md` do repo prosauai (se não existir, PR-A cria).

---

## Riscos & mitigações

(Condensado; detalhes em `research.md` §12 e pitch §Suggested Approach)

| # | Risco | Prob × Impacto | Mitigação |
|---|-------|----------------|-----------|
| R1 | `ConversationRequest` refactor quebra epic 005 tests | Alta × Alto | Gate "173 tests PASS" bloqueia merge PR-A; shim deprecation aceita `text` legado 1 release; testes de compat no benchmark baseline |
| R2 | Latência inline > 5s degrada UX | Média × Alto | Budget time por step (15s audio, 12s image); cache TTL 14d; revisitar retro se p95 > 5s em 1 mês (D3) |
| R3 | MetaCloudAdapter descobre abstração Evolution-shaped | Média × Médio | **Test-first**: escrever `MetaCloudAdapter.normalize()` contra fixtures ANTES de terminar PR-A; SC-013 gate (diff zero core) |
| R4 | Raw bytes persistidos por engano | Baixa × Alto (LGPD) | Code review obrigatório busca por `open(...).write` em processors; CI regex bloqueante |
| R5 | Cache bump invalida sem aviso | Baixa × Médio | `prompt_version` explícito no key; changelog ADR-033 registra bumps |
| R6 | Provider OpenAI incidente prolongado | Baixa × Alto | Circuit breaker 30s + backoff 30→60→120→300s; marker `[provider_unavailable]`; admin UI mostra estado breaker por tenant |

---

## Saída esperada

Este plan.md é **output parcial** do skill `/speckit.plan`. Artefatos completos gerados:

- ✅ `plan.md` (este arquivo)
- ✅ `research.md` (Phase 0 — reutilizado do escopo integral, ack no header)
- ✅ `data-model.md` (Phase 1 — schemas novos)
- ✅ `contracts/README.md`, `contracts/channel-adapter.md`, `contracts/content-processor.md`, `contracts/openapi.yaml` (Phase 1)
- ✅ `quickstart.md` (Phase 1)
- ⏭ `tasks.md` é gerado pelo próximo skill `/speckit.tasks`

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan consolidado com 3-PR sequencing (A/B/C, 5 semanas). Phase 0 ack'd ao research.md integral; Phase 1 gerou data-model.md (Pydantic + 2 SQL migrations + Redis proc:* namespace), contracts/ com 2 Python Protocols + OpenAPI 3.1 dos webhooks, quickstart.md com validação por PR e User Story. Constitution Check PASS sem violações. Próximo skill quebra em ~150 tasks hierarquizadas por PR, com gates SC-NNN explícitos."
  blockers: []
  confidence: Alta
  kill_criteria: "Invalidado se (a) o cost estimate de OpenAI p/ 10k+ mídias/mês/tenant superar $500/mês por tenant em benchmark real (força rever provider ADR-033); (b) Pydantic frozen=True com ContentBlock attrs achatados gerar falsos positivos de validation em fixtures reais (força discriminated union); (c) SC-013 falhar — MetaCloudAdapter exigir mudança em pipeline/ ou processors/ (força rearquitetar adapter Protocol antes do merge PR-A)."
