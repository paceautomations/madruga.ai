---
epic: 009-channel-ingestion-and-content-processing
title: "Channel Ingestion Normalization + Content Processing"
appetite: 5 semanas
status: drafted
created: 2026-04-17
updated: 2026-04-17
depends_on: [008-admin-evolution]
---
# Epic 009 — Channel Ingestion Normalization + Content Processing

## Problem

Hoje mensagens não-texto (áudio, imagem sem caption, sticker, documento) são **descartadas silenciosamente** em [apps/api/prosauai/api/webhooks.py:258](apps/api/prosauai/api/webhooks.py#L258). A cláusula `if message.text:` filtra qualquer conteúdo sem string `text` preenchida. O parser (`parse_evolution_message`) extrai metadata de mídia, mas o debounce e o `ConversationRequest` carregam apenas `text: str`, então o pipeline não tem como sequer tentar processar áudio/imagem. Resultado operacional: cliente manda áudio no WhatsApp, webhook retorna 200 OK, nenhum trace é persistido, nenhuma resposta é gerada. O admin vê mensagem recebida no Chatwoot mas sem resposta — cliente silenciado.

Três problemas estruturais compostos agravam o bug:

1. **Acoplamento Evolution no core**: `InboundMessage` em [core/formatter.py:63](apps/api/prosauai/core/formatter.py#L63) carrega strings Evolution-específicas (`messageType: "audioMessage"`, `media_is_ptt`, campos achatados). Qualquer segundo canal (Meta Cloud API, Instagram, Telegram) exigiria ou reescrever webhook+formatter+debounce+router, ou emitir strings Evolution em adapters shim — ambos ruins.
2. **Ingestão monolítica**: a função `webhook_whatsapp` acumula 7 responsabilidades (auth, parse JSON, normalização, idempotência, handoff check, routing MECE, persistência + dispatch). Adicionar um segundo canal força duplicação quase total.
3. **Zero análise de mídia existe**: grep exaustivo em `apps/api/` confirma nenhum código de Whisper, OCR, ou vision. A mídia é mencionada apenas em [core/router/facts.py:148](apps/api/prosauai/core/router/facts.py#L148) para derivar `ContentKind.MEDIA`, usado apenas pelo roteador — nunca processado.

Este épico **reformata a camada de entrada em dois módulos formais**: (a) `Channel Ingestion` com pattern adapter/strategy para múltiplas fontes e (b) `Content Processing` com strategy por `ContentBlock.kind`, habilitando tratamento real de áudio (Whisper) e imagem (GPT-4o-mini vision). Valida a abstração com um segundo adapter real (Meta Cloud API) para garantir que não virou EvolutionShim.

Entrega prova-se quando: (a) áudio PTT do WhatsApp é transcrito e respondido em contexto; (b) imagem com ou sem caption é descrita e respondida; (c) documento PDF tem texto extraído; (d) Trace Explorer mostra `content_process` como step próprio com custo + latência + cache hit; (e) Meta Cloud adapter processa payload real sem nenhuma mudança em `pipeline.py`/`processors/`/`core/router/`.

## Appetite

**5 semanas** (1 dev full-time). Escopo intencionalmente dividido em 3 PRs mergeáveis isoladamente em `develop`, cada um reversível via feature flag por tenant.

- **PR-A (2 semanas)** — Canonical schema + EvolutionAdapter + pipeline 14 steps (step 6 como stub TextProcessor identity). Mensagens de texto continuam idênticas; mídia ainda retorna fallback textual mas agora aparece no trace.
- **PR-B (2 semanas)** — Processors reais (audio/image/document/location/contact/reaction/sticker/unsupported), cache Redis, budget per-tenant, admin UI.
- **PR-C (1 semana)** — Meta Cloud Adapter. Prova que a abstração suporta segundo canal sem tocar core.

Cut-line: se PR-B estourar semana 4, cortar PR-C. O valor user-facing (mídia funcionando) é a entrega mínima; validação da abstração fica como follow-up épico 010. Aceitável porque o risco arquitetural da adapter pattern é bidirecional — o real stress test já ocorre ao escrever MetaCloudAdapter, não ao mergeá-lo.

Daily checkpoint em `easter-tracking.md` (convenção do 008) flagrando bleed cedo. Mitigação de escopo: §2 e §3 do EPIC009_full_escope.md mapeiam 13 fixtures Evolution + 4 Meta Cloud + 10 casos de erro — cobertura alta pega regressões antes do PR-B tocar produção.

## Dependencies

Prerrequisitos (todos `shipped`):

- **008-admin-evolution** — Trace Explorer do 008 renderiza qualquer `input_jsonb`/`output_jsonb` via `StepAccordion` genérico. Step novo `content_process` aparece no waterfall sem mudança no frontend (só a adição da entry em `StepRecord.STEP_NAMES` de 12 → 14).
- **005-conversation-core** — pipeline 12 steps + `trace_steps` + `pool_admin` fire-and-forget já estabelecidos. `ConversationRequest` refactor precisa manter 100% dos 173 testes existentes passando.
- **004-router-mece** — `core/router/facts.py::_derive_content_kind` passa a casar em `canonical.content.kind` em vez de `message.media_type`. Lógica idêntica, campo diferente.
- **003-multi-tenant-foundation** — tenant resolution e RLS permanecem. Feature flag nova é aditiva em `tenants.yaml`.

ADRs que este épico estende (não substitui):

- **ADR-027** admin-tables-no-rls — `media_analyses` herda o carve-out (admin-only, sem RLS, acesso via `pool_admin`).
- **ADR-028** pipeline fire-and-forget — aplicável ao persist de `media_analyses`.
- **ADR-029** pricing constant — estendido com linhas `whisper-1` e `gpt-4o-mini-vision`.
- **ADR-018** LGPD retention — estendido por ADR-034 (14d URL, 90d transcript).

ADRs novos deste épico: **ADR-030** (Canonical model), **ADR-031** (multi-source adapter), **ADR-032** (content processing strategy), **ADR-033** (OpenAI provider STT+vision), **ADR-034** (media retention), **ADR-035** (Meta Cloud adapter). ADR-036 reservado para follow-ups não previstos.

Dependências externas: OpenAI API key (provisionar via `OPENAI_API_KEY`), Evolution API operacional (sem mudança), Meta Business App sandbox (só PR-C). Bibliotecas novas Python: `openai>=1.50`, `pypdf>=4.0`, `python-docx>=1.1`. Sem blockers; 008 closed 2026-04-19.

## Captured Decisions

| # | Área | Decisão | Referência arquitetural |
|---|------|---------|-------------------------|
| 1 | Canonical model | Substituir `InboundMessage` (Evolution-specific) por `CanonicalInboundMessage` source-agnostic, com `ContentBlock` como union discriminada por `kind`. Compatibility strategy em 3 fases (PR-A1/A2/A3) evita PR gigante. | ADR-030 (novo) |
| 2 | Adapter pattern | Cada source implementa `ChannelAdapter` Protocol com `verify_webhook()` + `normalize()`. Registry lookup por `source`. Adapters são tradutores puros — nunca acessam DB ou chamam LLM. | ADR-031 (novo); `channels/base.py` |
| 3 | UX de transcrição | **Inline** — usuário espera +2-5s (áudio) ou +3-6s (imagem). Sem follow-up async. Simplifica arquitetura; evita dobra de mensagens de saída. Revisitar em retro se p95 > 5s. | §11 risks EPIC009_full_escope.md |
| 4 | Provider STT | **OpenAI `whisper-1`** como default ($0.006/min, qualidade PT-BR ok). Upgrade a `gpt-4o-mini-transcribe` (50% corte custo) documentado mas fora de escopo v1. | ADR-033 (novo) |
| 5 | Provider vision | **OpenAI `gpt-4o-mini`** via Responses API com `detail: "low"` (85 tokens fixos, $0.013/img). Configurável para `"high"` (leitura de texto em imagens) via `processor_config.image.detail`. | ADR-033 (novo) |
| 6 | Retenção mídia | Transcript salvo conforme retenção messages (90d). URL WhatsApp retida 14d (alinha com expiração natural do signed URL Meta). Cache dedup por `sha256` do conteúdo. | ADR-034 (novo); estende ADR-018 |
| 7 | Volume esperado | **Alto** — planejar para 10k+ mídias/mês por tenant. Força cache obrigatório, budget per-tenant, circuit breaker, retry com jitter. | §9 cost analysis EPIC009_full_escope.md |
| 8 | Scope-out explícito | Instagram, Telegram, video frames, PDF tabular, streaming transcription → épicos 010-012. Evita creep. | §1 D6 EPIC009_full_escope.md |
| 9 | Download binário | `httpx` stream para memória, max 25MB (limite Whisper), timeout 10s GET + 15s Whisper. Rejeita antes de gastar banda se `content-length > 25MB`. | §6.4 algoritmos |
| 10 | Base64 inline | Pular download quando Evolution enviar `data.message.base64`. Reduz latência ~100-300ms em builds que suportam. | §6.4 audio step 4 |
| 11 | Idempotency key canônico | `sha256(source + source_instance + external_message_id)`. Evita colisão cross-source entre Meta e Evolution IDs. | §4.1 `CanonicalInboundMessage.idempotency_key` |
| 12 | Feature flag granular | `content_processing.{enabled, audio_enabled, image_enabled, document_enabled, daily_budget_usd}` por tenant. Rollback sem deploy; permite ligar Ariel primeiro, ResenhAI depois. | §6.6 tenants.yaml schema |
| 13 | Pricing register | Estender `pricing.py` (ADR-029) com `whisper-1` $0.006/min e `gpt-4o-mini` vision rates. Admin Performance tab mostra custo por processor. | Estende ADR-029 |
| 14 | Debounce multi-message merge | Pipeline recebe `list[CanonicalInboundMessage]`. Cada uma processada em step 6, concatenada em `text_representation` única. Suporta "áudio seguido de texto complementar" sem bug. | §5.5 decisão crítica |
| 15 | `ConversationRequest` shape | Carrega `canonical_messages: list[CanonicalInboundMessage]`; remove `text: str`. Helpers derivados (`sender_key`, `group_id`) mantêm compat de uso. | §7.3 |
| 16 | Pipeline 12 → 14 steps | Insere `content_process` como step #6 entre `save_inbound` (5) e `build_context` (7). `StepRecord.STEP_NAMES` passa a ter 14 entries; validação `order 1..12` vira `1..14`. Traces antigos continuam com 12 steps (sem migração). | §7.1, §7.2 |
| 17 | `media_analyses` table | Persiste cada análise completa (não-truncada) para audit. Admin-only, sem RLS, acessado via `pool_admin`. Retention cron: URL=NULL após 14d, DELETE após 90d. | §6.8; carve-out ADR-027 |
| 18 | `processor_usage_daily` table | Agregação diária por (tenant, kind, provider). Suporta enforcement de `daily_budget_usd`. Query single-row antes de cada processor run. | §6.6 |
| 19 | Cache strategy | Key = `proc:{kind}:v{prompt_version}:{sha256}` em Redis. TTL 14d (alinha URL WhatsApp). Versão do prompt na key → bump invalida cache quando prompt muda. | §6.5 |
| 20 | Budget fallback gracioso | Budget estourado → processor retorna `ProcessedContent(error="budget_exceeded", text_representation="[áudio recebido — limite diário atingido, responderei manualmente]")`. LLM contorna na resposta. | §6.6 |
| 21 | Meta Cloud validação | PR-C é stress test arquitetural: adapter escrito contra fixtures ANTES de terminar EvolutionAdapter. Zero mudança em `pipeline.py`/`processors/`/`core/router/` é gate de merge. | ADR-035 (novo); §14 PR-C |
| 22 | Retrocompat webhook URL | Manter alias `/webhook/whatsapp/{instance_name}` → chama `evolution.py`. Zero-break deploy; remover em épico futuro após métricas confirmarem zero tráfego. | §5.1 T020 |

## Resolved Gray Areas

O escopo fonte (EPIC009_full_escope.md §17) declara "Nenhuma pergunta aberta — todas as decisões-chave travadas em §1". As áreas cinza resolvidas abaixo são as que o skill `epic-context` normalmente pergunta mas já foram respondidas ali, registradas aqui para auditabilidade downstream:

1. **UX síncrona vs. assíncrona de transcrição** (D3): resolvido **inline**. Usuário espera a latência extra. Racional: dobra de mensagens de saída quebra expectativa do usuário WhatsApp (pressupõe resposta única ao input). Budget 15s para AudioProcessor. Se p95 > 5s após 1 mês em produção, revisitar em retro com telemetria real.
2. **Provider lock-in (OpenAI)** (D4/D5): aceito conscientemente para v1. Interface `ContentProcessor` + `ProcessorContext` permite swap futuro (ex.: Deepgram para STT, Claude Haiku para vision) sem mexer em pipeline. Mitigação: ADR-033 documenta alternativas consideradas (Azure Speech, Google STT, gpt-4o-mini-transcribe).
3. **Cache storage** (D19): Redis key-value JSON, sem compressão. Payload típico < 2KB. TTL 14d alinha com URL WhatsApp. Eviction policy LRU já configurada na infra Redis (verificado via epic 005). Monitoramento via Netdata existente.
4. **Merge semântico de múltiplas mensagens** (§5.5): 3 opções avaliadas (concat só texto, lista de canonicals, first-wins). Escolhido **lista de canonicals** porque é o único que suporta "áudio + texto complementar" sem bug. Custo: reescreve `_parse_flush_items` e assinatura do pipeline — contido no PR-A.
5. **Alucinação de silêncio Whisper** (§12 risks): filtro determinístico: `duration < 2s` OU match com blocklist conhecida ("Legendas em português" etc) → retornar `[áudio curto sem fala clara]`. Evita poluir contexto do LLM com ruído transcrito.
6. **Detail "low" vs "high" em vision** (D5): default `"low"` (85 tokens, $0.013/img) cobre 99% de descrição simples. `"high"` (~765 tokens, $0.11/img) habilitado via config quando caso de uso exigir (cardápio, nota fiscal). Decisão per-tenant em `processor_config.image.detail`.
7. **Base legal LGPD** (ADR-030 carve-out pendente): execução de contrato (atendimento automatizado) + legítimo interesse (debug). Transcrições plaintext em `media_analyses.text_result` com retenção 90d. Bytes raw NUNCA armazenados — só URL do WhatsApp (expira 14d naturalmente). Mascaramento PII (CPF, cartão) via `output_guard` existente cobre classes reconhecidas; novas classes são follow-up separado.

## Applicable Constraints

**Do blueprint** (`engineering/blueprint.md`):

- **Tech stack base**: Python 3.12, FastAPI >=0.115, pydantic 2.x, redis[hiredis] >=5.0, httpx, structlog, opentelemetry-sdk. Novo: `openai>=1.50`, `pypdf>=4.0`, `python-docx>=1.1`.
- **Persistence**: PostgreSQL 15 via asyncpg. Migrations via dbmate. Two pools (`pool_app` com RLS + `pool_admin` BYPASSRLS). `media_analyses` e `processor_usage_daily` em `public` schema (admin-only), acessadas via `pool_admin`.
- **Redis 7**: debounce buffers + idempotência existentes + cache de processors (novo prefixo `proc:*`).
- **OTel**: instrumentação fastapi/httpx/redis já automática. Novos spans: `processor.audio.transcribe`, `processor.image.describe`, `processor.document.extract`, `openai.whisper.create`, `openai.vision.responses.create`. Atributos: `processor.kind`, `processor.provider`, `processor.cache_hit`, `processor.cost_usd`, `tenant.id`.

**Dos ADRs existentes**:

- **ADR-011 RLS Supabase**: `media_analyses` em `public` sob carve-out ADR-027, acessada só via `pool_admin`. Não aplicar RLS.
- **ADR-027 admin-tables-no-rls**: `media_analyses`, `processor_usage_daily` herdam o padrão. `GRANT SELECT, INSERT, UPDATE, DELETE ... TO service_role` + `ALTER TABLE ... OWNER TO app_owner`.
- **ADR-028 pipeline fire-and-forget persistence**: persist de `media_analyses` é fire-and-forget após o step `content_process` retornar. Falha de insert nunca bloqueia resposta ao cliente.
- **ADR-029 pricing constant**: estender `pricing.PRICING_TABLE` com `whisper-1` e `gpt-4o-mini-vision`. `ProcessedContent.cost_usd` usa `pricing.calculate_*`.

**Do domain model** (`engineering/domain-model.md`):

- Bounded contexts afetados: **Ingestion** (novo módulo formal, absorve responsabilidades hoje em `api/webhooks.py`), **Conversation Pipeline** (adiciona step 6), **Observability** (novo agregado `MediaAnalysis`).
- Agregado `InboundMessage` (legacy) → `CanonicalInboundMessage` (novo); invariante de imutabilidade mantida (enriquecimento sempre via cópia).

**NFRs** aplicáveis:

- p95 latência **texto** ≤5ms pior que baseline 008 (gate de merge PR-A).
- p95 latência **áudio 10s** end-to-end < 8s (gate PR-B).
- Cache hit rate ≥30% após 7d prod (SC-007 EPIC009_full_escope.md).
- Zero regression nos 173 tests epic 005 + 191 tests epic 008 (SC-010).
- Budget enforcement: tenant que excede daily_budget vê fallback educado, não timeout/crash (SC-008).

## Suggested Approach

Execução em 3 PRs encadeados, cada um mergeável isoladamente em `develop` com feature flag por tenant.

### PR-A — Channel Ingestion Normalization (2 semanas)

**Entregáveis**:
- `apps/api/prosauai/channels/` (canonical.py, base.py, registry.py)
- `channels/inbound/evolution/{auth,adapter}.py` + `channels/outbound/evolution.py` (rename de channels/evolution.py)
- `api/webhooks/evolution.py` + `api/webhooks/dispatch.py` (quebra do webhook_whatsapp monolítico)
- Migration `20260420_create_media_analyses.sql`
- `StepRecord.STEP_NAMES` 14 entries; step 6 placeholder (TextProcessor identity)
- `ConversationRequest` carrega `canonical_messages: list[CanonicalInboundMessage]`
- Debounce payload Canonical serialized
- Alias `/webhook/whatsapp/{instance_name}` preserva retrocompat
- Tests 100% evolution adapter + canonical validation (13 fixtures Evolution reais)

**Gate de merge**:
- 173 tests epic 005 + 191 tests epic 008 passam (zero regression).
- Payload de mídia aparece no trace com `content_process.output.providers=["text-placeholder"]` (visível, mesmo sem processamento real).
- Latência texto ≤5ms pior que baseline.

### PR-B — Content Processing Layer (2 semanas)

**Entregáveis**:
- `apps/api/prosauai/processors/` (10 arquivos: base.py, context.py, registry.py, cache.py, budget.py, text.py, audio.py, image.py, document.py, location.py, contact.py, reaction.py, unsupported.py, sticker.py, errors.py)
- Migration `20260505_create_processor_usage_daily.sql`
- `tenants.yaml` schema estende com `content_processing: {enabled, audio_enabled, image_enabled, document_enabled, daily_budget_usd}`
- `config.py` + `.env.example`: `OPENAI_API_KEY`, processor defaults
- `pricing.py` estendido (whisper-1 + gpt-4o-mini vision)
- Retention cron estendido: `UPDATE media_analyses SET source_url=NULL WHERE created_at < 14d` + `DELETE WHERE created_at < 90d`
- Admin UI: Performance AI tab ganha gráfico "Custo de mídia/dia" (Recharts stacked bar); inbox mostra ícone de kind na bolha
- ADRs 030-034 escritos
- Tests ≥90% cobertura em cada processor; integration test `test_audio_end_to_end.py`

**Gate de merge**:
- Áudio PTT real → Whisper mocado responde → trace mostra transcrição → LLM responde em contexto (fixture-based).
- Budget exceeded → fallback gracioso, sem timeout/crash.
- p95 latência áudio 10s end-to-end < 8s.

### PR-C — Meta Cloud API Adapter (1 semana)

**Entregáveis**:
- `channels/inbound/meta_cloud/{auth,adapter}.py` + `api/webhooks/meta_cloud.py`
- Fixtures `tests/fixtures/captured/meta_cloud_{text,audio,image,interactive}.input.json`
- ADR-035
- Docs `apps/api/prosauai/channels/README.md` — playbook "Como adicionar um novo source" em 4 etapas

**Gate de merge**:
- Payload Meta Cloud real → Canonical válido → pipeline processa sem alteração.
- Cross-source idempotency: Evolution ID == Meta ID não colidem.
- **Zero mudança em código core** (pipeline, processors, router) — se mudar, abstração falhou e precisa revisitar.

### Sequenciamento & guardrails

Cronograma:

- **Semana 1**: Foundation (ADRs 030-031 draft, epic branch, pitch/spec/plan) → PR-A coding (canonical schema + EvolutionAdapter + step 6 stub)
- **Semana 2**: PR-A merge staging + PR-B coding audio/image
- **Semana 3**: PR-B coding document/others + admin UI + budget + ADRs 032-034
- **Semana 4**: PR-B integration tests + merge staging
- **Semana 5**: PR-C coding + merge + epic close

Daily `easter-tracking.md` checkpoint (convenção 008). Reconcile final após cada PR-merge (hook fire do `madruga:reconcile`).

### Testing strategy resumido

- **Unit**: coverage ≥90% em processors, ≥95% em adapters/auth. `respx` para mock httpx, `AsyncMock` para `AsyncOpenAI`.
- **Integration**: testcontainers-postgres + fakeredis + OpenAI mocado. Fluxos completos por source+kind.
- **E2E Playwright**: abrir Trace Explorer → expandir step `content_process` → confirmar transcript visível.
- **Fixtures reais**: reutilizar 13 existentes Evolution em `tests/fixtures/captured/` + adicionar 4 Meta Cloud + casos de borda (PDF encriptado, áudio 25MB, URL expirada 410).

### Riscos de maior impacto (§12 EPIC009_full_escope.md)

Os 3 riscos que justificam o sequenciamento:

1. **`ConversationRequest` refactor quebra epic 005 tests** (impacto alto, probabilidade alta) — mitigado com gate "173 tests passam" no PR-A + deprecation shim aceitando `text` legacy por 1 release.
2. **Latência inline > 5s degrada UX** (alto/média) — budget de 15s total no AudioProcessor + cache agressivo; se p95 > 5s após 1 mês, migrar para async (D3 revisitada em retro).
3. **MetaCloudAdapter descobre abstração Evolution-shaped demais** (médio/média) — mitigado com test-first: escrever `MetaCloudAdapter.normalize()` contra fixtures ANTES de terminar EvolutionAdapter. Se não couber, revisitar Canonical antes do merge PR-A.

---

**Material técnico completo**: este pitch é a visão condensada. O escopo integral (schemas Pydantic, mapping tables exaustivas, algoritmos dos processors linha-a-linha, 163 tasks T001-T163, 20 seções de referências OpenAI/Meta) está preservado em [research.md](./research.md) — conteúdo original do `EPIC009_full_escope.md` v2026-04-19 retido para `speckit.specify` / `speckit.plan` consumirem sem perda de informação.
