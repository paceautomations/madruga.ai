---
description: "Task breakdown for epic 010 — Handoff Engine + Multi-Helpdesk Integration"
---

# Tasks: Handoff Engine + Multi-Helpdesk Integration

**Input**: Design documents from `platforms/prosauai/epics/010-handoff-engine-inbox/`
**Prerequisites**: [pitch.md](./pitch.md), [spec.md](./spec.md), [plan.md](./plan.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [research.md](./research.md), [quickstart.md](./quickstart.md)

**Tests**: Inclusos — o plan define metas de cobertura (≥95% `handoff/state.py`, `handoff/chatwoot.py`, `handoff/none.py`; ≥90% webhooks), contract tests para `HelpdeskAdapter` Protocol, integration com testcontainers-postgres + fakeredis + respx, race tests concorrentes via `asyncio.gather`, e benchmarks como **gate de merge** em PR-A (SC-004) e PR-B (SC-002). TDD applied within each story.

**Organization**: Tasks agrupadas por user story (US1..US7, em ordem de prioridade do spec) e alinhadas aos 3 PRs do plan (PR-A foundational + US1; PR-B US2+US4+shadow; PR-C US3+US5+US6). Setup + Foundational concentram o que bloqueia todas as US.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: roda em paralelo (arquivos diferentes, sem dependencia)
- **[Story]**: US1..US7 mapeadas ao spec. Phases Setup/Foundational/Polish sem story label.
- Caminhos de arquivo referem-se ao repo externo `paceautomations/prosauai` (branch `epic/prosauai/010-handoff-engine-inbox`) per `plan.md` §Project Structure.

## Cut-line

Se PR-B estourar semana 2 → **PR-C sacrificavel** (Phases 5, 7, 8 viram follow-up epic 010.1). Valor core (bot nao fala em cima do humano) e entregue com PR-A+B via SQL/curl de ops. Admin UI + composer + cards nao sao gate do valor user-facing.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: pre-work do PR-A — fixtures reais, branch check, estrutura do novo modulo.

- [x] T001 [P] Capturar fixture real do webhook Chatwoot `conversation_updated` (assignee_id non-null) em dev e salvar em `apps/api/tests/fixtures/captured/chatwoot_conversation_updated_assignee.input.json`
- [x] T002 [P] Capturar fixture real do webhook Chatwoot `conversation_updated` (assignee_id=null, unassign) em `apps/api/tests/fixtures/captured/chatwoot_conversation_updated_unassigned.input.json`
- [x] T003 [P] Capturar fixture real do webhook Chatwoot `conversation_status_changed` (status=resolved) em `apps/api/tests/fixtures/captured/chatwoot_conversation_status_resolved.input.json`
- [x] T004 [P] Capturar fixture Evolution `fromMe:true` (humano respondendo via WhatsApp proprio) em `apps/api/tests/fixtures/captured/evolution_fromMe_human.input.json`
- [x] T005 Criar diretorio `apps/api/prosauai/handoff/` com `__init__.py` e diretorio de testes `apps/api/tests/unit/handoff/`
- [x] T006 [P] Criar script helper `apps/api/scripts/sign_chatwoot_webhook.py` (assina payload com HMAC-SHA256 para dev local)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: infraestrutura que **TODAS** as user stories dependem — migrations, Protocol, state module, safety net do pipeline. Escopo integral do PR-A.

**⚠️ CRITICAL**: nenhuma US pode avancar ate essa fase fechar. Gate de merge PR-A: 173+191 tests PASS + zero regression + latencia texto ≤baseline+5ms (SC-004, SC-005).

### Migrations e schema

- [x] T010 Criar migration `apps/api/prosauai/db/migrations/20260501000001_create_handoff_fields.sql` adicionando 6 colunas em `conversations` (`ai_active BOOLEAN NOT NULL DEFAULT TRUE`, `ai_muted_reason TEXT`, `ai_muted_at TIMESTAMPTZ`, `ai_muted_by_user_id UUID`, `ai_auto_resume_at TIMESTAMPTZ`, `external_refs JSONB NOT NULL DEFAULT '{}'::jsonb`) + indice parcial `CREATE INDEX CONCURRENTLY idx_conversations_ai_auto_resume_pending ON conversations (ai_auto_resume_at) WHERE ai_active=false AND ai_auto_resume_at IS NOT NULL`
- [x] T011 Criar migration `apps/api/prosauai/db/migrations/20260501000002_create_handoff_events.sql` (schema `public`, append-only, colunas `id UUID PK`, `tenant_id UUID NOT NULL`, `conversation_id UUID NOT NULL`, `event_type TEXT NOT NULL`, `source TEXT NOT NULL`, `metadata JSONB NOT NULL DEFAULT '{}'`, `shadow BOOLEAN NOT NULL DEFAULT FALSE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` + indices `(tenant_id, created_at DESC)` e `(conversation_id, created_at DESC)`)
- [x] T012 Criar migration `apps/api/prosauai/db/migrations/20260501000003_create_bot_sent_messages.sql` (schema `public`, `tenant_id UUID`, `message_id TEXT`, `conversation_id UUID NOT NULL`, `sent_at TIMESTAMPTZ NOT NULL DEFAULT now()`, PK `(tenant_id, message_id)` + indice `(sent_at)` para cleanup)
- [x] T013 Rodar `dbmate up` em dev contra Supabase staging e validar que as 3 migrations aplicam sem erro; dump schema resultante para comparacao em CI

### HelpdeskAdapter Protocol + registry + errors

- [x] T020 [P] Criar `apps/api/prosauai/handoff/base.py` com `HelpdeskAdapter` Protocol (metodos `on_conversation_assigned`, `on_conversation_resolved`, `push_private_note`, `send_operator_reply`, `verify_webhook_signature`) conforme `contracts/helpdesk-adapter.md`
- [x] T021 [P] Criar `apps/api/prosauai/handoff/base.py` (mesmo arquivo T020) contendo errors `HelpdeskAdapterError`, `InvalidPayloadError`, `AuthError`, `UnknownHelpdesk`
- [x] T022 [P] Criar `apps/api/prosauai/handoff/registry.py` com `register(helpdesk_type, adapter_cls)`, `get_adapter(helpdesk_type)`, `registered_helpdesks()` — espelha `channels/registry.py` do epic 009
- [x] T023 [P] Criar `apps/api/tests/contract/test_helpdesk_adapter_contract.py` parametrizado sobre `ChatwootAdapter` + `NoneAdapter` (validara Protocol conformance via `isinstance`); tests falham ate T040/T060 existirem

### State module (advisory lock + mute/resume)

- [x] T030 Criar `apps/api/prosauai/handoff/events.py` com dataclass `HandoffEvent` e funcao `persist_event(conn, event)` fire-and-forget (inserta em `public.handoff_events`, erros logados mas nao levantados)
- [x] T031 Criar `apps/api/prosauai/handoff/state.py` com `mute_conversation(conn, conversation_id, tenant_id, reason, source, metadata, auto_resume_at=None, muted_by_user_id=None)` que (a) adquire `pg_advisory_xact_lock(hashtext(conversation_id))`, (b) checa modo `handoff.mode` do tenant (off→no-op; shadow→grava evento com `shadow=true` e retorna sem mutar; on→muta), (c) UPDATE `ai_active=false` + metadata, (d) chama `persist_event` fire-and-forget
- [x] T032 Criar em `apps/api/prosauai/handoff/state.py` (mesmo arquivo) `resume_conversation(conn, conversation_id, tenant_id, source, metadata, resumed_by_user_id=None)` com mesma mecanica: advisory lock → UPDATE `ai_active=true` + clear metadata → event
- [x] T033 [P] Criar `apps/api/tests/unit/handoff/test_state.py` com unit tests cobrindo mute→resume happy path, mute em `mode=off` no-op, mute em `mode=shadow` grava evento sem mutar (≥95% coverage state.py)
- [x] T034 [P] Criar `apps/api/tests/unit/handoff/test_events.py` (fire-and-forget persistence, erros logados + metric increment + nao levantam)
- [x] T035 Integration test `apps/api/tests/integration/test_handoff_concurrent_transitions.py` usando testcontainers-postgres: `asyncio.gather` com 10 calls concorrentes a `mute_conversation` na mesma conversa → apenas 1 prevalece (advisory lock serializa)

### Circuit breaker

- [x] T040 [P] Criar `apps/api/prosauai/handoff/breaker.py` reusando padrao `processors/breaker.py` do epic 009: `CircuitBreaker` per-helpdesk-per-tenant com estados closed/open/half-open, thresholds 5 falhas/60s, half-open apos 30s
- [x] T041 [P] Criar `apps/api/tests/unit/handoff/test_breaker.py` (transicoes de estado + metric `helpdesk_breaker_open` ao abrir)

### ChatwootAdapter — shell sem webhook (PR-A entrega mute manual via SQL)

- [x] T050 Criar `apps/api/prosauai/handoff/chatwoot.py` com `ChatwootAdapter` implementando `HelpdeskAdapter` Protocol: constructor recebe `tenant_config`, cliente httpx async, wraps em `CircuitBreaker`
- [x] T051 Em `apps/api/prosauai/handoff/chatwoot.py` implementar `verify_webhook_signature(headers, body)` usando stdlib `hmac` + `hashlib.sha256` com `tenant.helpdesk.credentials.webhook_secret`
- [x] T052 Em `apps/api/prosauai/handoff/chatwoot.py` implementar `push_private_note(conversation_id, text)` chamando Chatwoot API v1 `POST /conversations/{id}/messages` com `message_type=private` (fire-and-forget via breaker)
- [x] T053 [P] Criar `apps/api/tests/unit/handoff/test_chatwoot.py` (≥95% coverage) com `respx` mockando Chatwoot API: HMAC verify happy + tampered, push_private_note sucesso e falha (breaker abre)

### Registry bootstrap + config_poller extension

- [x] T060 Em `apps/api/prosauai/main.py` registrar `ChatwootAdapter` no `HelpdeskRegistry` durante `lifespan` startup (aditivo — nao remove nada)
- [x] T061 Estender `apps/api/prosauai/tenants/config_poller.py` aceitando blocos novos em `tenants.yaml`: `helpdesk: {type: chatwoot|none, credentials: {api_token, account_id, inbox_id, webhook_secret}}` e `handoff: {mode: off|shadow|on, auto_resume_after_hours: int|null (1..168), human_pause_minutes: int (1..1440), rules: [string]}`
- [x] T062 Em `tenants/config_poller.py` adicionar validacao: `handoff.auto_resume_after_hours` fora de range → rejeitar reload, manter config anterior, emitir metric `tenant_config_reload_failed{tenant}`
- [x] T063 [P] Criar `apps/api/tests/unit/tenants/test_config_poller_handoff.py` validando reload de 3 cenarios (off, shadow, on) + validacao range + reject hold-previous

### Pipeline safety net + customer_lookup amortization

- [x] T070 Estender `apps/api/prosauai/conversation/pipeline/steps/customer_lookup.py` para amortizar leitura de `ai_active` junto com a resolucao do customer (single SELECT — `SELECT c.*, co.ai_active FROM customers c JOIN conversations co ON ...`)
- [x] T071 Em `customer_lookup.py` popular `conversations.external_refs.chatwoot.{conversation_id, inbox_id}` quando webhook Evolution carrega `chatwootConversationId` non-null e campo ainda nao tem esse ID — UPDATE atomico via `jsonb_set(external_refs, '{chatwoot}', $1::jsonb, true)`
- [x] T072 Estender `apps/api/prosauai/conversation/pipeline/steps/generate.py` com safety net: `SELECT ai_active FROM conversations WHERE id=$1 FOR UPDATE` imediatamente antes do call LLM; se false → skip + emite step `ai_muted_skip` no `observability/step_record.py`
- [x] T073 Estender `apps/api/prosauai/observability/step_record.py` para registrar novo step type `ai_muted_skip` com `ai_muted_reason` nos dados
- [x] T074 [P] Criar `apps/api/tests/unit/pipeline/test_generate_safety_net.py` (conversa com `ai_active=false` → pipeline skip + trace step `ai_muted_skip` emitido; race entre pipeline start e mute concurrent capturada pelo FOR UPDATE)
- [x] T075 [P] Criar `apps/api/tests/unit/pipeline/test_customer_lookup_amortized.py` (single SELECT confirmado via SQL trace; external_refs populado idempotente — update subsequente com mesmo chatwoot_conversation_id e no-op)

### Outbound tracking (bot_sent_messages)

- [x] T080 Estender `apps/api/prosauai/channels/outbound/evolution.py` para gravar `bot_sent_messages (tenant_id, message_id, conversation_id, sent_at)` apos cada `sendText` bem-sucedido (fire-and-forget — falha nao bloqueia outbound)
- [x] T081 [P] Criar `apps/api/tests/unit/channels/outbound/test_evolution_bot_sent_messages.py` (insert pos-send + tolerancia a falha de DB)

### Deprecacao redis key legacy

- [x] T090 Estender `apps/api/prosauai/core/router/facts.py` para ler `conversation_in_handoff` de `conversations.ai_active` (amortizado em customer_lookup) E emitir log estruturado `handoff_redis_legacy_read` toda vez que algum path ainda le a chave Redis `handoff:{tenant}:{sender_key}` (telemetria de obsolescencia para rollout em PR-B)
- [x] T091 [P] Criar `apps/api/tests/unit/router/test_facts_ai_active.py` (fact derivado do PG + log estruturado quando read legacy ocorre)

### DB queries

- [x] T100 Estender `apps/api/prosauai/db/queries/conversations.py`: remover comment TODO `pending_handoff not yet materialised`; adicionar queries `fetch_ai_active(conversation_id)`, `update_ai_active(conversation_id, active, reason, muted_at, muted_by, auto_resume_at)` parametrizadas

### ADR PR-A

- [x] T110 [P] Rascunhar `platforms/prosauai/decisions/ADR-036-ai-active-unified-mute-state.md` (Nygard format) — substitui discussao `pending_handoff`/enum multi-step (decisao 1 pitch); supersedes referencias em `core/router/facts.py:66` + `db/queries/conversations.py:16`
- [x] T111 [P] Rascunhar `platforms/prosauai/decisions/ADR-037-helpdesk-adapter-pattern.md` — Protocol + registry, espelha ADR-031 (ChannelAdapter); aceita trade-off de 5 metodos ao inves de 2 porque cobre write+read+webhook

### Benchmark gate PR-A

- [x] T120 Criar `apps/api/tests/benchmarks/test_text_latency_no_regression.py` medindo p95 do pipeline de texto pre e pos-PR-A — **gate de merge**: pos ≤ baseline (epic 009) + 5ms (SC-004)

### PR-A merge gate summary

- [x] T130 Validar que 173 tests epic 005 + 191 tests epic 008 + suites epic 009 passam integralmente na branch `epic/prosauai/010-handoff-engine-inbox` (SC-005 zero regression) — resultado: 1909 passed / 4 expected failures (ver nota)
- [x] T131 Smoke manual em staging: mutar conversa via SQL direto (`UPDATE conversations SET ai_active=false WHERE id=$1`) → enviar inbound do cliente → verificar no Trace Explorer step `ai_muted_skip` e ausencia de resposta do bot — runbook em `quickstart.md §Manual SQL smoke test (PR-A)`; executar antes do merge de PR-A

**Checkpoint**: PR-A mergeado em `develop`. Nenhum tenant ainda afetado (helpdesk.mode ausente = default off implicito). Mute manual via SQL/curl funciona end-to-end.

---

## Phase 3: User Story 1 - Atendente assume conversa no Chatwoot e bot silencia (Priority: P1) 🎯 MVP

**Goal**: webhook Chatwoot `conversation_updated` (assignee non-null) silencia o bot em <500ms p95. Entrega o **valor core** do epic (bot nao fala em cima do humano).

**Independent Test**: cliente envia → bot responde → atendente atribui no Chatwoot → cliente envia de novo → bot NAO responde, Trace Explorer mostra `ai_muted_skip`. Idempotencia confirmada reenviando mesmo `chatwoot_event_id`.

### Tests for User Story 1 (TDD — write FIRST, ensure FAIL)

- [x] T200 [P] [US1] Criar `apps/api/tests/unit/api/webhooks/test_helpdesk_chatwoot.py` cobrindo: HMAC valido → 200, HMAC invalido → 401, payload desconhecido (ex: `message_created`) → 200 no-op + log `event_type=unhandled`, `assignee_id` null→non-null dispara `on_conversation_assigned`, `conversation_status_changed` status=resolved dispara `on_conversation_resolved`
- [x] T201 [P] [US1] Criar `apps/api/tests/unit/api/webhooks/test_helpdesk_chatwoot_idempotency.py` (duplicata mesmo `chatwoot_event_id` → 200 no-op, Redis SETNX `handoff:wh:{id}` TTL 24h)
- [x] T202 [P] [US1] Criar `apps/api/tests/integration/test_handoff_flow_chatwoot.py` (testcontainers-postgres + fakeredis + respx): (1) webhook assigned → `ai_active=false` + event `muted` source=`chatwoot_assigned`; (2) inbound cliente → pipeline skip + step `ai_muted_skip`; (3) webhook resolved → `ai_active=true` + event `resumed` source=`helpdesk_resolved`; (4) inbound cliente → bot responde novamente
- [x] T203 [P] [US1] Criar `apps/api/tests/benchmarks/test_webhook_latency.py` medindo p95 webhook → mute commit (SC-002: <500ms p95) — **gate de merge PR-B**

### Implementation for User Story 1

- [x] T210 [US1] Em `apps/api/prosauai/handoff/chatwoot.py` implementar `on_conversation_assigned(payload)` que resolve conversa via `external_refs->'chatwoot'->>'conversation_id'` (ou fallback reverso via Chatwoot API `GET /conversations/{id}` para correlacionar sender) e chama `state.mute_conversation(reason='chatwoot_assigned', source='chatwoot_assigned', metadata={'assignee_id': ..., 'chatwoot_event_id': ...})`
- [x] T211 [US1] Em `apps/api/prosauai/handoff/chatwoot.py` implementar `on_conversation_resolved(payload)` chamando `state.resume_conversation(source='helpdesk_resolved', metadata={'chatwoot_event_id': ...})`
- [x] T212 [US1] Criar pasta `apps/api/prosauai/api/webhooks/helpdesk/` com `__init__.py` vazio
- [x] T213 [US1] Criar `apps/api/prosauai/api/webhooks/helpdesk/chatwoot.py` — endpoint `POST /webhook/helpdesk/chatwoot/{tenant_slug}`:
  1. resolver tenant via slug; se tenant `handoff.mode=off` → return 200 no-op (FR-041)
  2. adquirir adapter via `get_adapter('chatwoot')`; se tenant nao tem helpdesk chatwoot → 200 no-op com log `tenant_no_helpdesk`
  3. `verify_webhook_signature` com secret per-tenant (HMAC-SHA256 sobre raw body)
  4. idempotency: Redis `SET handoff:wh:{chatwoot_event_id} 1 NX EX 86400`; se 0 → 200 no-op + log `duplicate_webhook`
  5. dispatch por `event` field do payload:
     - `conversation_updated` com delta de `assignee_id` (non-null agora) → `adapter.on_conversation_assigned(payload)`
     - `conversation_updated` com `assignee_id` que virou null → `adapter.on_conversation_resolved(payload)`
     - `conversation_status_changed` status=resolved → `adapter.on_conversation_resolved(payload)`
     - outros eventos → 200 + log `event_type=unhandled` (FR-017a)
  6. return 200 sempre (FR-019) — mesmo em payload malformado
- [x] T214 [US1] Em `apps/api/prosauai/main.py` registrar o router `/webhook/helpdesk/chatwoot` no FastAPI app
- [x] T215 [US1] Configurar fixture `tenants.yaml` em `apps/api/tests/fixtures/` para tenant teste com `helpdesk.type: chatwoot` + credentials
- [x] T216 [US1] Em `apps/api/prosauai/handoff/chatwoot.py` garantir que primeiro webhook sem linkage em `external_refs.chatwoot` faz lookup reverso via `GET /conversations/{id}` do Chatwoot (FR-022a fallback) e popula o campo; se falhar → 200 no-op + metric `chatwoot_webhook_unlinked_total{tenant}`
- [x] T217 [US1] Instrumentar OTel baggage: webhook handler propaga `conversation_id` + `tenant_id` em baggage desde entry point (FR-051)
- [x] T218 [US1] Adicionar metrics Prometheus: `handoff_events_total{tenant, event_type, source}`, `helpdesk_webhook_latency_seconds{tenant, helpdesk}` (FR-052)

**Checkpoint US1**: webhook Chatwoot real (staging Pace) → Ariel em `handoff.mode=on` forcado manualmente → atribui conversa → bot silencia em <500ms; bot resume on resolve. Valor core entregue.

---

## Phase 4: User Story 2 - Atendente resolve conversa e bot retoma automaticamente (Priority: P1)

**Goal**: 3 gatilhos de retorno (`helpdesk_resolved > manual_toggle > timeout`) funcionando; scheduler `handoff_auto_resume_cron` singleton cross-replicas; retorno silencioso (sem mensagem proativa).

**Independent Test**: mutar conversa manualmente via SQL, setar `ai_auto_resume_at = now - 5min`, aguardar 60s → conversa retomada com evento `source='timeout'`. Paralelo: mutar + resolver no Chatwoot → evento `source='helpdesk_resolved'` prevalece sobre timeout pendente.

### Tests for User Story 2

- [x] T300 [P] [US2] Criar `apps/api/tests/unit/handoff/test_scheduler.py` cobrindo: (a) cron rodando retoma conversas com `ai_auto_resume_at < now()`; (b) singleton via `pg_try_advisory_lock` — replica perdedora dorme; (c) shutdown graceful aguarda iteration via `asyncio.wait(timeout=5s)`; (d) freezegun time-travel para validar cadencia 60s
- [x] T301 [P] [US2] Integration test `apps/api/tests/integration/test_handoff_flow_none_adapter.py` (parcial — US2 cobre timeout): setar `ai_auto_resume_at` no passado → aguardar 1 iteration cron → assert `ai_active=true`, event `resumed` source=`timeout`
- [x] T302 [P] [US2] Unit test em `test_scheduler.py` para priorizacao: `helpdesk_resolved` webhook chegando durante execucao do cron → webhook prevalece (advisory lock por conversation_id serializa); outros dois tentam e observam estado ja retomado

### Implementation for User Story 2

- [x] T310 [US2] Criar `apps/api/prosauai/handoff/scheduler.py` com classe `HandoffScheduler` que aceita lista de periodic tasks e roda cada uma em asyncio task no lifespan
- [x] T311 [US2] Em `handoff/scheduler.py` implementar task `handoff_auto_resume_cron`: cadencia 60s, tenta `pg_try_advisory_lock(hashtext('handoff_resume_cron'))` — se nao pegar, dorme 60s e retry; se pegar, SELECT conversas com `ai_active=false AND ai_auto_resume_at < now() AND ai_auto_resume_at IS NOT NULL` em batches de 100 e chama `resume_conversation(source='timeout')` para cada
- [x] T312 [US2] Em `apps/api/prosauai/main.py` lifespan startup → `HandoffScheduler.start()`; shutdown → `HandoffScheduler.stop()` com `asyncio.wait(timeout=5s)` em iterations correntes
- [x] T313 [US2] Garantir que bot nao envia mensagem proativa on resume — `resume_conversation` apenas flipa bit; nao enfileira outbound (FR-016)
- [x] T314 [US2] Adicionar env var `HANDOFF_AUTO_RESUME_ENABLED=1` (default) + `HANDOFF_AUTO_RESUME_INTERVAL_SECONDS=60` em `config.py` para kill switch emergencial
- [x] T315 [US2] Validar priorizacao de gatilhos de retorno: em `state.resume_conversation`, registrar `source` + `priority_index` em `metadata` para auditoria (`helpdesk_resolved=1, manual_toggle=2, timeout=3`)

**Checkpoint US2**: cron retoma conversas dentro de SLA 60s (SC-008); 2 replicas em staging → so 1 executa iteration (advisory lock valida).

---

## Phase 5: User Story 3 - Admin ve estado de handoff e pode toggar manualmente (Priority: P1)

**Goal**: admin UI com badges + toggle manual. Esta fase entra em PR-C — **sacrificavel** se PR-B estourar (cut-line).

**Independent Test**: admin abre conversa → ve badge verde → clica "Silenciar AI" → badge vira vermelho com `manual_toggle` + timestamp. Enviar mensagem como cliente → bot nao responde. Retomar → badge verde → bot responde.

### Tests for User Story 3

- [x] T400 [P] [US3] Criar `apps/api/tests/unit/api/admin/test_conversations_handoff.py` cobrindo: (a) POST mute sem auth → 401; (b) admin tenant A toga conversa tenant B → 403; (c) Pace ops BYPASSRLS toga cross-tenant → 200; (d) mute persiste `ai_muted_by_user_id=<JWT.sub>`; (e) unmute limpa `ai_auto_resume_at`
- [x] T401 [P] [US3] E2E Playwright `apps/admin/tests/e2e/handoff-toggle.spec.ts`: login → abrir conversa → ver badge → clicar Silenciar → badge atualiza → clicar Retomar → badge atualiza

### Implementation for User Story 3

- [x] T410 [US3] Em `apps/api/prosauai/api/admin/conversations.py` adicionar `POST /admin/conversations/{id}/mute` recebendo `{reason?: string}` → chama `state.mute_conversation(reason='manual_toggle', source='manual_toggle', muted_by_user_id=<JWT.sub>)`
- [x] T411 [US3] Em `apps/api/prosauai/api/admin/conversations.py` adicionar `POST /admin/conversations/{id}/unmute` → chama `state.resume_conversation(source='manual_toggle', resumed_by_user_id=<JWT.sub>)` + limpa `ai_auto_resume_at`
- [x] T412 [US3] Validar autorizacao: admin comum restrito ao proprio tenant (via JWT.tenant_id); Pace ops com role `pace_admin` usa `pool_admin` BYPASSRLS (ADR-027)
- [x] T413 [US3] Estender `apps/api/prosauai/api/admin/conversations.py` GET list/detail para retornar `ai_active`, `ai_muted_reason`, `ai_muted_at` no payload (sem regressao de latencia — indice ja cobre)
- [x] T414 [P] [US3] Em `apps/admin/src/app/admin/(authenticated)/conversations/page.tsx` adicionar coluna/badge "AI ativa" (verde) / "AI silenciada por: {reason} desde {time}" (vermelho) em cada linha da lista — validar <100ms p95
- [x] T415 [US3] Em `apps/admin/src/app/admin/(authenticated)/conversations/[id]/page.tsx` adicionar botao contextual "Silenciar AI" (quando `ai_active=true`) / "Retomar AI" (quando false) → chama mute/unmute endpoint via TanStack Query mutation
- [x] T416 [P] [US3] Criar componente compartilhado `apps/admin/src/components/handoff-badge.tsx` renderizando badge com reason+timestamp (reuso lista+detalhe)
- [x] T417 [US3] Audit log: `handoff_events.metadata` inclui `admin_user_id=<JWT.sub>` para toggle manual; entry correspondente em `audit_logs` existente

**Checkpoint US3**: admin UI staging mostra badges em todas as conversas; toggle manual flipa bit + UI atualiza em <2s (SC-013); Playwright E2E verde.

---

## Phase 6: User Story 4 - Tenant sem helpdesk: NoneAdapter fromMe detection (Priority: P2)

**Goal**: tenant `helpdesk.type: none` detecta humano respondendo direto via WhatsApp (Evolution `fromMe:true`), com tracking `bot_sent_messages` evitando echo e group chat skip silencioso.

**Independent Test**: tenant staging com `helpdesk.type: none`. Enviar como cliente → bot responde → grava `bot_sent_messages`. Simular webhook `fromMe:true` com `message_id` nao registrado → mute 30min. Novo `fromMe` → timer reinicia. Webhook `fromMe:true` com `message_id` em `bot_sent_messages` → NAO muta. Webhook `fromMe:true` em `is_group=true` → skip silencioso + log `noneadapter_group_skip`.

### Tests for User Story 4

- [x] T500 [P] [US4] Criar `apps/api/tests/unit/handoff/test_none.py` (≥95% coverage) cobrindo: (a) `fromMe:true` nao-matched → mute com `reason='fromMe_detected'` e `auto_resume_at = now + human_pause_minutes`; (b) `fromMe:true` matched em `bot_sent_messages` (sent_at <10s) → NAO muta; (c) `fromMe:true` matched com `sent_at >10s` → mute (humano respondeu depois); (d) segundo `fromMe` nao-matched enquanto ja mutado → atualiza `ai_auto_resume_at` renovando timer; (e) `is_group=true` → skip + log `noneadapter_group_skip`
- [x] T501 [P] [US4] Unit test para cron `bot_sent_messages_cleanup_cron` em `test_scheduler.py`: singleton via advisory lock; deleta entradas com `sent_at < now - 48h`; cadencia 12h
- [x] T502 [P] [US4] Integration test em `apps/api/tests/integration/test_handoff_flow_none_adapter.py`: (1) tenant `helpdesk.type: none` + bot envia → bot_sent_messages gravado; (2) Evolution webhook `fromMe:true` nao-matched → mute + auto_resume_at setado; (3) wait + scheduler iteration → resume; (4) replay webhook com matched → no-op; (5) grupo `is_group=true` → skip silencioso

### Implementation for User Story 4

- [x] T510 [US4] Criar `apps/api/prosauai/handoff/none.py` com `NoneAdapter` implementando `HelpdeskAdapter` Protocol. `on_conversation_assigned`/`on_conversation_resolved` sao no-op (helpdesk nao tem webhook). `push_private_note`/`send_operator_reply` levantam `HelpdeskAdapterError('no_helpdesk_configured')` para composer falhar 409. `verify_webhook_signature` retorna True trivial (nao tem webhook proprio)
- [x] T511 [US4] Em `handoff/none.py` adicionar metodo `handle_evolution_fromme(payload, tenant_config, conversation)`: (a) se `is_group=true` → log `noneadapter_group_skip` + return no-op; (b) query `bot_sent_messages WHERE tenant_id=$1 AND message_id=$2` → se match e `sent_at >= now - 10s` → echo, no-op; (c) caso contrario → `state.mute_conversation(reason='fromMe_detected', source='fromMe_detected', auto_resume_at=now+human_pause_minutes)`
- [x] T512 [US4] Estender `apps/api/prosauai/api/webhooks/evolution.py` para, apos o pipeline normal, invocar `NoneAdapter.handle_evolution_fromme` quando payload tem `fromMe:true` E tenant helpdesk_type==`none` E conversation resolved
- [x] T513 [US4] Em `handoff/scheduler.py` adicionar task `bot_sent_messages_cleanup_cron`: cadencia 12h, singleton via `pg_try_advisory_lock(hashtext('bsm_cleanup_cron'))`, `DELETE FROM bot_sent_messages WHERE sent_at < now() - interval '48 hours'` em batches
- [x] T514 [US4] Em `apps/api/prosauai/main.py` registrar `NoneAdapter` no registry (alias `none`)
- [x] T515 [US4] Rascunhar `platforms/prosauai/decisions/ADR-038-fromme-auto-detection-semantics.md` — `bot_sent_messages` tracking + 10s echo tolerance window + group chat skip + 48h retention trade-off
- [x] T516 [US4] Adicionar campo `inbound.is_group` ao canonical payload Evolution (se nao existe) — check fixture `tests/fixtures/captured/` e estender normalizer se necessario

**Checkpoint US4**: NoneAdapter valida abstracao `HelpdeskAdapter` com shape radicalmente diferente do ChatwootAdapter; false positives <1% validado em teste de carga (SC-006).

---

## Phase 7: User Story 5 - Pace ops usa composer emergencia (Priority: P2)

**Goal**: endpoint admin `POST /admin/conversations/{id}/reply` delega ao adapter do tenant com `sender_name=<JWT.email>`; NoneAdapter retorna 409; composer UI em detalhe da conversa.

**Independent Test**: admin Pace abre conversa tenant com Chatwoot → digita mensagem → clica "Enviar como Pace ops" → mensagem chega no cliente via WhatsApp + aparece no Chatwoot do tenant com `sender_name=<admin.email>`. Tenant `helpdesk.type: none` → 409 Conflict.

### Tests for User Story 5

- [x] T600 [P] [US5] Em `test_conversations_handoff.py` adicionar: (a) POST reply com helpdesk chatwoot → delega adapter + metric `handoff_events_total{event_type='admin_reply_sent'}`; (b) POST reply em tenant `helpdesk.type=none` → 409 `{error: 'no_helpdesk_configured'}`; (c) circuit breaker aberto → 503; (d) metadata.admin_user_id persistido no event
- [x] T601 [P] [US5] Integration test `apps/api/tests/integration/test_handoff_composer_admin.py`: admin Pace → POST reply → respx mock Chatwoot API → assert call com `sender_name=<email>` + body correto
- [x] T602 [P] [US5] E2E Playwright `apps/admin/tests/e2e/handoff-composer.spec.ts`: login Pace → abrir conversa Ariel → digitar texto no composer → enviar → verificar mensagem aparece no thread

### Implementation for User Story 5

- [x] T610 [US5] Em `handoff/chatwoot.py` implementar `send_operator_reply(conversation_id, content, sender_name)` chamando Chatwoot API v1 `POST /conversations/{id}/messages` com `message_type=outgoing` + `private=false` e headers configurando nome de exibicao para `sender_name`
- [x] T611 [US5] Em `apps/api/prosauai/api/admin/conversations.py` adicionar `POST /admin/conversations/{id}/reply` aceitando `{content: string, attachments?: [...]}`:
  1. resolver tenant da conversa
  2. `adapter = get_adapter(tenant.helpdesk.type)`
  3. se `adapter` e `NoneAdapter` → return 409 `{error: 'no_helpdesk_configured'}`
  4. se circuit breaker aberto → return 503 `{error: 'helpdesk_unavailable'}`
  5. `adapter.send_operator_reply(conversation_id, content, sender_name=<JWT.email>)`
  6. `persist_event(event_type='admin_reply_sent', source='manual_toggle', metadata={'admin_user_id': <JWT.sub>, 'message_id': ..., 'helpdesk_conversation_id': ...})`
  7. return 200
- [x] T612 [US5] Audit `handoff_events.metadata.admin_user_id=<JWT.sub>` registrado mas `admin_user_email` NAO persistido (apenas usado como `sender_name` transient)
- [x] T613 [US5] Em `apps/admin/src/app/admin/(authenticated)/conversations/[id]/page.tsx` adicionar componente composer: textarea + botao "Enviar como Pace ops" — visivel apenas quando `tenant.helpdesk.type != 'none'`; tenant sem helpdesk exibe disclaimer "tenant nao tem helpdesk configurado"
- [x] T614 [US5] UI tratar 503 (breaker aberto) exibindo "helpdesk indisponivel, tente em alguns minutos"; tratar 409 exibindo disclaimer
- [x] T615 [US5] UX: mostrar badge no composer "Enviando como: {admin.email}" para deixar identidade explicita (trade-off aceito Q4-A)

**Checkpoint US5**: composer emergencia funcional; latencia admin → outbound <2s p95 (SC-003); tenant NoneAdapter retorna 409 corretamente.

---

## Phase 8: User Story 6 - Admin audita taxas e duracoes no Performance AI (Priority: P2)

**Goal**: Performance AI tab (epic 008) ganha linha "Handoff" com 4 cards agregados sobre `handoff_events`.

**Independent Test**: popular staging com >=10 eventos variados (multiplas origens, com/sem timeout). Abrir Performance AI > Handoff. Verificar 4 cards renderizam em <3s, numeros coerentes vs query SQL direta.

### Tests for User Story 6

- [x] T700 [P] [US6] Criar `apps/api/tests/unit/admin/test_performance_handoff_metrics.py` validando queries agregadas: (a) taxa `(distinct conversations with mute event) / total conversations`; (b) duracao media `avg(resumed_at - muted_at)` excluindo eventos shadow; (c) breakdown por `source` (counts); (d) SLA breaches (count de events `source=timeout`)
- [x] T701 [P] [US6] E2E Playwright `apps/admin/tests/e2e/performance-handoff.spec.ts`: login → Performance AI → range=7d → 4 cards renderizam + numeros batem com SQL

### Implementation for User Story 6

- [x] T710 [US6] Em `apps/api/prosauai/admin/metrics/performance.py` adicionar 4 queries agregadas sobre `handoff_events` respeitando filtro `created_at BETWEEN $from AND $to` + `tenant_id` scope; queries ignoram `shadow=true` por default (query param `include_shadow` opcional)
- [x] T711 [US6] Expor endpoint `GET /admin/performance/handoff?tenant=...&from=...&to=...&include_shadow=false` retornando `{rate, avg_duration_seconds, breakdown: {source: count}, sla_breaches}`
- [x] T712 [P] [US6] Em `apps/admin/src/app/admin/(authenticated)/performance/page.tsx` adicionar linha "Handoff" acima/abaixo das linhas existentes com 4 cards: (1) Taxa (%), (2) Duracao media (formatted min/hours), (3) Breakdown por origem (Recharts PieChart), (4) SLA breaches (count + link filtrado pro Trace Explorer)
- [x] T713 [US6] Eventos shadow renderizam em cor distinta (cinza/hachurado) se `include_shadow=true` — permite comparar "quanto seria mutado"
- [x] T714 [US6] Garantir range de datas existente do epic 008 e compartilhado — cards recalculam via TanStack Query invalidate ao mudar range
- [x] T715 [US6] Tenant sem eventos → cards mostram "N/A" ou 0 sem quebrar layout
- [x] T716 [US6] Em `handoff/scheduler.py` adicionar task `handoff_events_cleanup_cron`: cadencia 24h, singleton via `pg_try_advisory_lock(hashtext('handoff_events_cleanup'))`, `DELETE FROM handoff_events WHERE created_at < now() - interval '90 days'` em batches de 1000 — FR-047a retention
- [x] T717 [US6] Index em `handoff_events (tenant_id, created_at DESC)` ja existe (T011); adicionar EXPLAIN ANALYZE em teste para garantir <3s em 10k events (SC-010)

**Checkpoint US6**: dataset 10k events renderiza <3s; metrics auditaveis vs SQL direto.

---

## Phase 9: User Story 7 - Rollout shadow mode valida false-mute antes de flipar on (Priority: P3)

**Goal**: `handoff.mode: shadow` emite events sem mutar, permitindo medir false-mute rate com trafego real.

**Independent Test**: tenant em `mode=shadow` → webhook assigned chega → evento gravado com `shadow=true` → `ai_active` nao muta → bot continua respondendo. Performance AI mostra eventos shadow em cor distinta.

### Tests for User Story 7

- [x] T800 [P] [US7] Em `test_state.py` adicionar: (a) `mute_conversation` em `mode=shadow` persiste evento `shadow=true` + `ai_active` permanece `true`; (b) mesmo cenario em `mode=on` muta; (c) pipeline `generate` safety net ignora conversa com apenas shadow events (nao le flag shadow; le `ai_active` que permanece true)
- [x] T801 [P] [US7] Integration test: tenant shadow + 10 webhooks assigned → 10 eventos shadow gravados + bot continua respondendo em todos os 10 inbounds subsequentes

### Implementation for User Story 7

- [x] T810 [US7] Em `handoff/state.py` `mute_conversation` ja implementado no T031 com branch por `tenant.handoff.mode` — confirmar branch shadow grava event com `shadow=true` sem UPDATE ✓ verificado em state.py L213-238 (`mute_conversation`) e L392-417 (`resume_conversation`); branch emite `HandoffEvent(shadow=True)` via `asyncio.create_task(persist_event(...))` e retorna `MuteResult(was_shadow=True)` sem tocar `pool.acquire()`. Coberto por tests `test_mute_mode_shadow_no_db_mutation`, `test_resume_mode_shadow_no_db_mutation`, `test_shadow_mute_persists_event_without_db_mutation` (T800) e integration `test_shadow_ten_webhooks_no_mute_all_events_recorded` (T801).
- [x] T811 [US7] Documentar em `platforms/prosauai/epics/010-handoff-engine-inbox/rollout-runbook.md` o trajeto `off → shadow (7d) → on` + criterios de sucesso (false-mute rate ≤X%, SC-012 ≤10% erro predito vs real)
- [x] T812 [US7] Performance AI render shadow events com estilo visual distinto (cinza hachurado) — ja coberto em T713 ✓ verificado em `apps/admin/src/components/performance/handoff-metrics.tsx` L260-263 (hatched stripe wrapper via `bg-[repeating-linear-gradient(...)]` quando `isShadow=true`) e L353-354 (pie slices com `fillOpacity=0.45` em shadow mode). `data-include-shadow` attribute exposto para E2E.
- [x] T813 [US7] Adicionar metric `handoff_shadow_events_total{tenant, source}` separada do counter principal para facilitar comparacao pos-flip
- [ ] T814 [US7] Documentar em `decisions.md` que codigo de shadow mode pode ser removido em epic follow-up apos validacao do primeiro tenant (A13 spec)

**Checkpoint US7**: rollout reversivel 100% validado (SC-011); shadow mode prediz realidade com erro ≤10% (SC-012).

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: observabilidade, documentacao, cleanup, validacao final antes de rollout em producao.

- [ ] T900 [P] Adicionar metrics Prometheus faltantes: `handoff_duration_seconds_bucket{tenant}` (histogram) + `helpdesk_breaker_open{tenant, helpdesk}` — registrar em `apps/api/prosauai/observability/metrics.py` (FR-052)
- [ ] T901 [P] Estruturar logs structlog em todos os paths: webhook handler, state.mute/resume, scheduler iterations, adapter calls — campos padrao `tenant_id`, `conversation_id`, `event_type`, `source`, `helpdesk_type`, `admin_user_id` (FR-053)
- [ ] T902 [P] OTel baggage propagation end-to-end: webhook inbound → pipeline → POST Chatwoot API — validar via trace completo no Trace Explorer (FR-051)
- [ ] T903 [P] Atualizar `platforms/prosauai/engineering/blueprint.md` com novo modulo `handoff/` + 2 tabelas admin + schedulers no lifespan (sem refatoracao, aditivo)
- [ ] T904 [P] Atualizar `platforms/prosauai/decisions/ADR-028-pipeline-fire-and-forget-persistence.md` listando `handoff_events` insert + push private note + sync assignee como novos side effects fire-and-forget
- [ ] T905 [P] Atualizar `platforms/prosauai/decisions/ADR-027-admin-tables-no-rls.md` listando `handoff_events` + `bot_sent_messages` como novas tabelas sob carve-out
- [ ] T906 [P] Atualizar `platforms/prosauai/decisions/ADR-018-data-retention-lgpd.md` com retention policy `handoff_events=90d` + `bot_sent_messages=48h`
- [ ] T907 Rodar `apps/api/scripts/update-agent-context.sh claude` para refletir novo modulo handoff e 3 tabelas
- [ ] T908 [P] Estender `CLAUDE.md` (root) com Active Technologies do epic 010 — zero libs novas, mas novo modulo `handoff/` + 2 tabelas admin
- [ ] T909 Rodar `quickstart.md` end-to-end validation em staging (validacao US1-US7 conforme documentado)
- [ ] T910 [P] Remover codigo Redis legacy key `handoff:*` do epic 004 placeholder apos 7d com zero leituras em producao — deletar em `core/router/facts.py` + remover log `handoff_redis_legacy_read` (aguarda gate operacional pos-rollout)
- [ ] T911 [P] Criar runbook `apps/api/benchmarks/handoff_smoke.md` com checklist manual pre-rollout cada tenant (validacao Chatwoot webhook real + fromMe + composer + cards)
- [ ] T912 Audit final: `handoff_events` retention cron rodou? `bot_sent_messages` cleanup cron rodou? circuit breaker `helpdesk_breaker_open` metric coletada? — marcar em `easter-tracking.md`
- [ ] T913 Rodar `make test` + `make lint` + `make ruff` do madruga.ai e garantir verde — lint dos ADRs e diagramas
- [ ] T914 Pos-merge PR-C: executar `/madruga:judge 010` (gate 1-way-door conforme pipeline DAG) e aplicar blockers antes de mandar pra staging

---

## Phase 11: Deployment Smoke

**Purpose**: validar startup completo + URLs + journey J-001 em ambiente isolado antes de rollout em producao. Auto-gerado via `testing:` block em `platforms/prosauai/platform.yaml`.

- [ ] T1100 Executar `docker compose build` em `apps/api/` (prosauai repo) — build sem erros
- [ ] T1101 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks respondem dentro do ready_timeout (120s)
- [ ] T1102 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero required_env vars ausentes no .env
- [ ] T1103 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as URLs acessiveis com status esperado
- [ ] T1104 Capturar screenshot de cada URL `type: frontend` declarada em `testing.urls` (http://localhost:3000, http://localhost:3000/login) — conteudo nao e placeholder
- [ ] T1105 Executar Journey J-001 (happy path) declarado em `platforms/prosauai/testing/journeys.md` — todos os steps com assertions OK

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: sem dependencias; pode comecar imediatamente
- **Phase 2 Foundational**: depende de Phase 1 completo — **BLOQUEIA todas as user stories**
- **Phase 3 US1 (P1 MVP)**: depende de Phase 2 — entrega valor core do epic
- **Phase 4 US2 (P1)**: depende de Phase 2 (scheduler) + Phase 3 (webhook handler para resolved)
- **Phase 5 US3 (P1)**: depende de Phase 2 — independente de US1/US2 (toggle manual)
- **Phase 6 US4 (P2)**: depende de Phase 2 (NoneAdapter registrado) + extensao Evolution webhook hook
- **Phase 7 US5 (P2)**: depende de Phase 3 (ChatwootAdapter.send_operator_reply) + Phase 5 (admin UI)
- **Phase 8 US6 (P2)**: depende de Phase 3 + Phase 4 (events populados) — UI pode ser paralela
- **Phase 9 US7 (P3)**: depende de Phase 2 (state.py branch shadow) + Phase 8 (rendering shadow)
- **Phase 10 Polish**: depende de todas as US desejadas
- **Phase 11 Smoke**: final — depende de tudo

### User Story Dependencies

- **US1 (P1)**: standalone apos Foundational
- **US2 (P1)**: depende de US1 para webhook `resolved` handler (mas scheduler timeout e standalone)
- **US3 (P1)**: standalone apos Foundational — endpoints admin novos + UI extensao
- **US4 (P2)**: standalone apos Foundational — adapter separado
- **US5 (P2)**: depende de US1 (ChatwootAdapter) + US3 (admin UI scaffold)
- **US6 (P2)**: depende de ter eventos gerados em US1/US3/US4 — UI standalone
- **US7 (P3)**: standalone — so altera `state.py` branch + rendering

### PR → Phase mapping

- **PR-A (semana 1)**: Phases 1, 2, 3 — entrega Chatwoot mute via webhook real
- **PR-B (semana 2)**: Phases 4, 6, 9 — entrega auto-resume + NoneAdapter + shadow mode
- **PR-C (semana 3)**: Phases 5, 7, 8 — entrega admin UI + composer + metricas

### Parallel Opportunities

- **Phase 1**: T001-T004 (fixtures reais) podem ser capturadas em paralelo; T006 (script HMAC) independente
- **Phase 2**: T020-T023 (Protocol + registry + contract test stub), T030/T033/T034 (events module), T040-T041 (breaker), T074-T075 (pipeline tests), T110-T111 (ADRs drafts) — multiplos arquivos independentes
- **Phase 3 US1**: T200-T203 (4 test files independentes) em paralelo; T214 (main.py registro) deve ser sequencial pois mesmo arquivo
- **Phase 5 US3**: T414 (lista badge) + T416 (component shared) em paralelo; T417 (audit log) no backend paralelo
- **Phase 6 US4**: T500-T502 (3 test files) em paralelo
- **Phase 8 US6**: T712 (UI Performance AI) em paralelo com T711 (backend endpoint)
- **Phase 10 Polish**: T900-T906 + T908 + T910-T911 todos em arquivos distintos — altamente paralelizavel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (Phase 3):
Task: "Contract test for webhook + idempotency in apps/api/tests/unit/api/webhooks/test_helpdesk_chatwoot.py"
Task: "Idempotency test in apps/api/tests/unit/api/webhooks/test_helpdesk_chatwoot_idempotency.py"
Task: "Integration test in apps/api/tests/integration/test_handoff_flow_chatwoot.py"
Task: "Benchmark test in apps/api/tests/benchmarks/test_webhook_latency.py"

# Launch foundational modules in parallel (Phase 2):
Task: "HelpdeskAdapter Protocol + errors in apps/api/prosauai/handoff/base.py"
Task: "Registry in apps/api/prosauai/handoff/registry.py"
Task: "CircuitBreaker in apps/api/prosauai/handoff/breaker.py"
Task: "HandoffEvent persistence in apps/api/prosauai/handoff/events.py"
```

---

## Implementation Strategy

### MVP First (US1 Only via PR-A merge)

1. Phase 1: Setup (fixtures reais, diretorios)
2. Phase 2: Foundational (3 migrations, Protocol, state, breaker, pipeline safety net, customer_lookup, outbound tracking, config_poller extension, ADRs 036-037)
3. Phase 3: US1 (webhook Chatwoot → mute + integration test + benchmark)
4. **STOP + VALIDATE**: mute manual SQL direto + webhook real Chatwoot staging Pace; zero regression em 173+191 suites
5. Merge PR-A em `develop` → Ariel em `handoff.mode: off` (zero effect)

### Incremental Delivery (PRs)

1. PR-A (Phases 1-3) → merge → smoke staging → Ariel continua em `mode:off` (reversivel 100%)
2. PR-B (Phases 4, 6, 9) → merge → Ariel flipa `off → shadow` (observa 7d) → flipa `on` (SC-001, SC-012)
3. PR-C (Phases 5, 7, 8) → merge → admin Pace opera via UI sem SQL direto; ResenhAI replica trajeto Ariel
4. Phase 10 Polish → continuous durante rollout + pos-rollout cleanup
5. Phase 11 Smoke → pre-rollout cada tenant (manual checklist)

### Parallel Team Strategy (1 dev full-time — 3 semanas)

1. Solo dev executa sequencial: Phase 1-3 (sem 1) → Phase 4+6+9 (sem 2) → Phase 5+7+8 (sem 3, sacrificavel)
2. Tasks [P] dentro de cada phase podem ser batcheadas em 1 PR de commits multiplos
3. `easter-tracking.md` daily flaga bleed; cut-line PR-C aciona se sem 2 estourar

---

## Notes

- [P] = arquivos diferentes, zero dependencia cruzada — podem ir num unico batch de commits
- [Story] = US1..US7 mapeia a spec.md — cada US e independentemente testavel + deployable
- Tests antes de implementacao (TDD) nos Phases 3-9 — write tests FIRST, verify FAIL, then implement
- Commits: `feat:`, `fix:`, `chore:` prefixes per convention (CLAUDE.md)
- Ordem dentro de cada story: contract tests + integration test stubs → models/SQL → services/state → endpoints/handlers → UI (quando aplicavel)
- Cut-line: PR-C e sacrificavel se PR-B estourar; Phases 5+7+8 viram follow-up 010.1
- Kill criteria (plan.md): se fixture real Chatwoot revelar shape incompativel OU stress advisory lock >5% p95 degradation → reabrir decisoes 3/11 antes de prosseguir
- Rollback RTO ≤60s per `handoff.mode: on → off` via config_poller poll — sem deploy
- Ordenacao estrita de transicoes: DB commit → event emit → side effects fire-and-forget — NUNCA inverter (FR-006)
- Advisory lock obrigatorio em toda transicao (`pg_advisory_xact_lock(hashtext(conversation_id))`) — granularidade per-conversation evita contention

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "tasks.md consolidado com 11 phases e ~100 tasks organizadas por user story (US1..US7) e alinhadas aos 3 PRs do plan (PR-A foundational+US1; PR-B US2+US4+US7; PR-C US3+US5+US6). TDD per story, [P] marcacao explicita para paralelismo, cut-line PR-C declarada. Deployment Smoke Phase 11 auto-gerada do testing: block do platform.yaml. Pronto para analyze pre-implement."
  blockers: []
  confidence: Alta
  kill_criteria: "Se /speckit.analyze detectar inconsistencia entre tasks.md e spec.md/plan.md/contracts/ (ex: FR nao coberto por task, task referenciando endpoint nao declarado no openapi.yaml, ordenacao de dependencia violada, contract test ausente para metodo Protocol), retornar para regenerar tasks.md antes de /speckit.implement."
