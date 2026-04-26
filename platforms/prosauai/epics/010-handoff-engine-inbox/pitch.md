---
epic: 010-handoff-engine-inbox
title: "Handoff Engine + Multi-Helpdesk Integration"
appetite: 3 semanas
status: shipped
created: 2026-04-22
updated: 2026-04-23
depends_on: [008-admin-evolution, 009-channel-ingestion-and-content-processing]
delivered_at: 2026-04-24
---
# Epic 010 — Handoff Engine + Multi-Helpdesk Integration

> Arquivo canonico em `pitch.md` seguindo convencao dos epics 008/009 (usuario referiu-se ao arquivo como `010-Handoff_Engine_Inbox.md` — mantido padrao speckit).

## Problem

O status `pending_handoff` esta **declarado mas nao materializado** ([apps/api/prosauai/db/queries/conversations.py:16](apps/api/prosauai/db/queries/conversations.py#L16) comenta explicitamente "not yet materialised in the DB schema"). Hoje nao existe mecanismo para **silenciar a IA quando um humano esta atendendo**. Resultado operacional em producao atual (Ariel + ResenhAI):

1. Cliente manda mensagem → pipeline processa → bot responde.
2. Atendente ve a mensagem no **Chatwoot** (Evolution ja esta integrado — injeta `chatwootConversationId` em todo webhook conforme [tests/fixtures/captured/README.md:208-211](apps/api/tests/fixtures/captured/README.md#L208-L211)) e responde via Chatwoot.
3. Chatwoot dispara via Evolution → cliente recebe resposta humana.
4. Cliente responde de volta.
5. **Bot responde em cima do humano.** Conversa dupla, UX quebrada, atendente frustrado.

Alem disso:

- Nenhuma regra de roteamento do epic 004 consegue aplicar `handoff` porque nao ha destinatario — flag `conversation_in_handoff` em [core/router/facts.py:66](apps/api/prosauai/core/router/facts.py#L66) e **sempre false** ("sera sempre False ate epic 005/011" — comentario estava errado desde 2026-04-12, nunca foi materializado).
- Safety guards (epic 005) podem disparar escalacao para humano mas nao existe via.
- Customer-initiated handoff ("quero falar com um atendente") e detectavel via classifier mas nao tem estado pra onde ir.

A **vision promete** ([business/vision.md:169](../../business/vision.md#L169)): "Handoff — Transferencia de conversa do agente para atendente humano com todo o contexto". E o principio de produto #2 ([business/solution-overview.md:86](../../business/solution-overview.md#L86)): "IA e copiloto, nao piloto. O agente responde e resolve, mas o humano sempre pode assumir". Ambos impossiveis hoje.

Este epic **fecha o buraco** com:

1. Um **unico bit de estado** (`ai_active`) na conversation indicando "bot pode responder".
2. Um **padrao adapter para helpdesks** (`ChatwootAdapter` + `NoneAdapter` no v1; Blip/Zendesk em epics futuros) que sincroniza esse bit com o que o helpdesk faz.
3. **Admin composer emergencia** pra Pace ops intervir em qualquer tenant.
4. **Metricas completas** no Performance AI tab (rate, duracao, breakdown por origem).

Multi-tenant e multi-helpdesk desde o dia um. Ariel/ResenhAI compartilham um Chatwoot da Pace; futuros clientes podem usar Chatwoot proprio em outra VPS, Blip, Zendesk, ou nenhum (respondem direto no WhatsApp no celular — `NoneAdapter`).

## Appetite

**3 semanas** (1 dev full-time). Dividido em 3 PRs mergeaveis isoladamente em `develop`, cada um reversivel via feature flag per-tenant.

- **PR-A (1 semana)** — Data model (`ai_active` + eventos), `HelpdeskAdapter` protocol + registry, `ChatwootAdapter` basico, pipeline short-circuit com advisory lock e safety net.
- **PR-B (1 semana)** — `NoneAdapter` com deteccao `fromMe`, webhook endpoints `/webhook/helpdesk/chatwoot/{tenant}`, idempotencia + HMAC, circuit breaker per-helpdesk, push de transcripts como private notes, `handoff_events` persistence.
- **PR-C (1 semana)** — Admin UI: status badges + composer emergencia + Performance AI tab handoff charts (rate, duracao, breakdown), feature flag rollout per-tenant.

**Cut-line**: se PR-B estourar, PR-C sai do escopo — admin UI vira follow-up. O valor user-facing (bot nao fala em cima do atendente) e entregue em PR-A+B. Admin UI e visibilidade, nao funcionalidade core.

## Dependencies

Prerrequisitos (todos `shipped`):

- **009-channel-ingestion-and-content-processing** — blueprint exato do padrao adapter ([channels/base.py](apps/api/prosauai/channels/base.py), [channels/registry.py](apps/api/prosauai/channels/registry.py)). `HelpdeskAdapter` espelha `ChannelAdapter`. Circuit breaker ([processors/breaker.py](apps/api/prosauai/processors/breaker.py)) reusado. Fire-and-forget pattern (ADR-028) aplicado a helpdesk side effects.
- **008-admin-evolution** — Trace Explorer, pool_admin BYPASSRLS, 8 abas. Status badges e composer ficam na aba Conversations existente. Performance AI tab ja renderiza Recharts stacked bar.
- **004-router-mece** — regras YAML podem emitir `mute_reason='rule_match'` para casar "cliente disse humano/atendente" sem hardcode.
- **003-multi-tenant-foundation** — TenantStore YAML carrega `helpdesk: {...}` block per-tenant. HMAC per-helpdesk reusa pattern X-Webhook-Secret.

ADRs novos deste epic: **ADR-036** (ai_active boolean model e unified mute state), **ADR-037** (HelpdeskAdapter pattern), **ADR-038** (fromMe auto-detection semantics para NoneAdapter).

ADRs estendidos (nao substituidos): **ADR-027** admin-tables-no-rls (`handoff_events` herda carve-out), **ADR-028** pipeline fire-and-forget (private notes e state sync ao helpdesk sao best-effort), **ADR-011** RLS (conversations mantem RLS; novas colunas ficam sob tenant_id existente).

Dependencias externas: Chatwoot instance Pace (ja operacional) — credenciais per-tenant. **Nenhuma nova lib Python** (reusa httpx + asyncpg + redis[hiredis]).

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Modelo de estado | **Boolean `ai_active` single bit** substitui state machine `open→pending_handoff→in_handoff→open/closed`. Conversation nunca muda de status operacional (`open`/`closed`); o que muda e se bot deve ou nao responder. Handoff nao e um estado intermediario — e a ausencia de AI. | ADR-036 novo |
| 2 | Source of truth | **[REVISADO 2026-04-23]** ProsaUAI (Postgres `conversations.ai_active`) e **fonte unica de verdade**. Router le `ai_active` direto do PG durante `customer_lookup` step — fact `conversation_in_handoff` e Redis key `handoff:{tenant}:{sender_key}` **deprecated** no PR-A, removidos no PR-B apos telemetria confirmar zero leitura residual. Helpdesk e autoritativo apenas para assignee/status externo (Chatwoot); eventos viram inputs que computam `ai_active`. | §B4; Q1-B epic-context 2026-04-23 |
| 3 | Adapter pattern | `HelpdeskAdapter` Protocol com `on_conversation_assigned()`, `on_conversation_resolved()`, `push_private_note()`, `send_operator_reply()`, `verify_webhook_signature()`. Registry por `helpdesk_type`. Espelha `ChannelAdapter` do epic 009. | ADR-037 novo |
| 4 | Escopo v1 adapters | **ChatwootAdapter** (Pace atual) + **NoneAdapter** (tenant sem helpdesk — detecta `fromMe` via Evolution). Blip/Zendesk adiados pra epic 010.1 quando houver cliente pedindo. Dois shapes radicalmente diferentes validam a abstracao (same racional do PR-C epic 009). | §B2 |
| 5 | Triggers de mute | 5 origens validas: `chatwoot_assigned`, `fromMe_detected`, `manual_toggle`, `rule_match` (router), `safety_trip` (guards). Cada uma gera evento `handoff_events.source`. | §B5 + safety guards existentes |
| 6 | Return-to-bot | **[REVISADO 2026-04-23]** 3 gatilhos: (a) helpdesk resolve → `assignee=null` ou `conversation.resolved` webhook; (b) timeout configuravel per-tenant (default **24h**); (c) toggle manual no admin. Priorizacao: (a) > (c) > (b). **Scheduler**: asyncio periodic task no FastAPI lifespan + `pg_try_advisory_lock(hashtext('handoff_resume_cron'))` singleton (so 1 replica roda o loop; outras dormem). Cadencia 60s. Shutdown graceful aguarda iteration corrente via `asyncio.wait(timeout=5s)`. Sem ARQ worker novo (escopo backlog). | §B6; Q2-A epic-context 2026-04-23 |
| 7 | Chatwoot sync | Webhook receiver idempotente via Redis SET NX (`handoff:wh:{chatwoot_event_id}`, TTL 24h). HMAC signature com secret per-tenant. Retry tolerant. Push de private note e fire-and-forget (ADR-028). | ADR-037; BP2, BP3 |
| 8 | NoneAdapter — detecao fromMe | **[REVISADO 2026-04-23]** Evolution webhook com `fromMe: true` cujo `message_id` nao casa com ID de envio do bot (tracking table `bot_sent_messages`) → `ai_muted_reason='fromMe_detected'`, `ai_auto_resume_at = now + tenant.human_pause_minutes` (default 30 min). Novo `fromMe` reseta o timer. **Group chat exclusion**: se canonical `inbound.is_group=true`, NoneAdapter skip silencioso da deteccao com log estruturado `noneadapter_group_skip` (alinhado com Decisao 21 — v1 handoff so 1:1). **Retention `bot_sent_messages`**: **48h** (nao 7d), cleanup cron roda **a cada 12h**. | ADR-038 novo; Q5 + Q2 add-on epic-context 2026-04-23 |
| 9 | Linkage ProsaUAI ↔ helpdesk | Coluna `conversations.external_refs JSONB` — ex: `{"chatwoot": {"conversation_id": 123, "inbox_id": 4}}`. Sem migration por helpdesk novo. Index GIN em chaves quentes se virar performance issue. | §B7 |
| 10 | Transcripts em handoff | Content processing do epic 009 continua rodando durante `ai_active=false` (atendente precisa ver transcript do audio). Adapter empurra como **private note** fire-and-forget. NoneAdapter nao suporta private note → skip silencioso (fica apenas no Trace Explorer). | §B8 |
| 11 | Race prevention | `pg_advisory_xact_lock(hashtext(conversation_id))` em qualquer transicao de `ai_active`. Previne corrida entre webhook Chatwoot + fromMe + toggle manual. | BP5 |
| 12 | Safety net no pipeline | Step `generate` faz `SELECT ai_active FROM conversations WHERE id=$1 FOR UPDATE` imediatamente antes do call LLM. Se flip aconteceu entre pipeline start e gen, skip sem delivery. | BP6 |
| 13 | Ordenacao de transicoes | **Mute primeiro (DB commit), side effects depois (fire-and-forget).** Push de private note, sync de assignee, etc. NUNCA antes do commit do `ai_active=false`. | BP7 |
| 14 | Feature flag per-tenant | **[REVISADO 2026-04-23]** `tenants.yaml` bloco `handoff.mode: off \| shadow \| on` (default `off`). Modo **shadow** emite `handoff_events` com `shadow=true` mas **nao** muta `ai_active` (bot continua respondendo) — permite medir false-mute rate com trafego real antes de flipar `on`. Rollout: Ariel `off→shadow` (observa 7d)→`on`; ResenhAI segue mesmo trajeto. Shadow e removivel apos validacao do primeiro tenant (decisao operacional pos-epic). | BP8; Q3-B epic-context 2026-04-23 |
| 15 | Admin composer (B3 hibrido) | **[REVISADO 2026-04-23]** Composer no admin ProsaUAI existe como **escape hatch de ops**, nao fluxo primario. Endpoint `POST /admin/conversations/{id}/reply` delega ao adapter do helpdesk do tenant → mensagem aparece no Chatwoot/WhatsApp como se tivesse saido do helpdesk. Uso esperado: ≤5% do trafego (emergencia Pace). **Identidade outbound**: `sender_name = admin_user.email` (JWT sub) → atendente do tenant ve especificamente quem da Pace respondeu. Trade-off aceito: expoe email interno Pace no Chatwoot do tenant. **Audit metadata**: `handoff_events.metadata.admin_user_id` registra o sub do JWT para auditoria granular. **NoneAdapter** (tenant sem helpdesk): composer retorna `409 Conflict` com `{error: 'no_helpdesk_configured'}`. | §B3; Q4-A epic-context 2026-04-23 |
| 16 | Shape tenants.yaml | Blocos separados `helpdesk: {type, credentials...}` + `handoff: {enabled, auto_resume, human_pause_minutes, rules}`. Ortogonal: helpdesk = infra, handoff = comportamento. | §B9 |
| 17 | Event sourcing | Nova tabela `handoff_events` append-only em `public` (admin-only, ADR-027 carve-out). Todo mute/unmute gera evento `{timestamp, conversation_id, tenant_id, event_type, source, metadata}`. Metricas derivam de queries sobre eventos. | BP1 |
| 18 | Metrica cardinality | Operator IDs externos sao armazenados em `metadata` dos eventos mas NAO tagueados em metricas Prometheus/Phoenix. Time series usa counters agregados (handoff_rate, avg_duration). | BP9 |
| 19 | OTel baggage | `conversation_id` + `tenant_id` em baggage desde o webhook inbound original ate o POST pro helpdesk. Trace Explorer mostra a cadeia completa. | BP10 |
| 20 | Chatwoot deployment | Suporta (a) Chatwoot compartilhado Pace com multiplos inboxes (Ariel/ResenhAI atual); (b) Chatwoot per-tenant em VPS propria; (c) sem Chatwoot (NoneAdapter). Shape do tenants.yaml acomoda os 3 casos sem codigo adicional. | §B10 (usuario) |
| 21 | Group chat | v1 so suporta handoff em conversa 1:1. Grupo (ResenhAI comunidades) continua sempre com bot — semantica de handoff em grupo e ambigua. Backlog. | §C (confirmado previamente) |
| 22 | Meta Cloud janela 24h | Quando helpdesk tenta responder via Meta Cloud fora da janela 24h, adapter retorna erro → admin mostra alerta "janela expirou, cliente precisa escrever primeiro". Nao tenta template. | §C |

## Resolved Gray Areas

Pontos que normalmente o skill `epic-context` pergunta e que foram decididos neste chat (2026-04-22):

1. **Estado: enum vs boolean** — optamos boolean porque usuario reformulou corretamente: "conversas sempre aparecem no Chatwoot e WhatsApp; handoff so muda se bot responde". State machine multi-step era overengineering.
2. **Admin ProsaUAI: composer ou read-only** — hibrido. Primario e helpdesk do atendente; composer admin e emergencia ops Pace. ~5% uso esperado.
3. **fromMe false positives** — tracking de `bot_sent_messages(message_id, sent_at, conversation_id)` resolve. Bot grava ID retornado pelo `sendText`; qualquer `fromMe:true` sem match → humano.
4. **Timeout default** — 24h OU helpdesk resolver (o que vier primeiro). Conservador para tenants nao-configurados.
5. **Operator identity** — armazenamos apenas ID externo do helpdesk (Chatwoot assignee_id). Nome nao e buscado. Privacidade per-tenant.
6. **Helpdesk downtime** — circuit breaker + fire-and-forget. Chatwoot down NAO bloqueia bot nem mute; so para de empurrar private notes ate breaker fechar.
7. **NoneAdapter discovery** — tenant declara `helpdesk.type: none` explicitamente. Sem `helpdesk:` no YAML → `handoff.mode:off` implicito.
8. **Quando bot volta, envia "oi" de volta?** — Silencioso. Bot so fala quando proximo inbound do cliente chega. Configurable via `handoff.resume_greeting: str | null`, default null.

**Adicionais 2026-04-23 (epic-context activation)**:

9. **Router integration (Q1)** — Router consulta `ai_active` direto do PG no `customer_lookup` step. Fact `conversation_in_handoff` e Redis key `handoff:*` deprecated no PR-A (mantidos para telemetria de obsolescencia), removidos no PR-B. Fonte unica de verdade elimina classe de bugs de divergencia Redis↔PG.
10. **Scheduler auto_resume (Q2)** — asyncio periodic task no FastAPI lifespan com singleton via `pg_try_advisory_lock`. Cadencia 60s. Zero infra nova (ARQ permanece em backlog).
11. **bot_sent_messages retention (Q2 add-on)** — **48h** retention (antes 7d), cleanup cron `bot_sent_messages_cleanup_cron` a cada **12h**. Trade-off: risco residual de falso positivo fromMe apos 48h e zero — bot nao re-envia a mesma mensagem com mesmo ID.
12. **Rollout shadow mode (Q3)** — `handoff.mode: off|shadow|on`. Shadow emite eventos sem mutar, mede false-mute rate antes de flipar `on`. +~50 LOC, +4 testes, removivel pos-validacao do primeiro tenant.
13. **Composer identity (Q4)** — `sender_name = admin_user.email` (JWT sub). Aceita trade-off de expor email interno Pace no Chatwoot do tenant. Audit metadata `admin_user_id` para granularidade interna. NoneAdapter: composer 409.
14. **Group + NoneAdapter (Q5)** — NoneAdapter skip silencioso da deteccao `fromMe` em conversas de grupo (`is_group=true`). Log estruturado `noneadapter_group_skip` para observabilidade. Consistente com Decisao 21 (handoff v1 = 1:1 apenas).

## Applicable Constraints

**Do blueprint** (`engineering/blueprint.md`):

- Python 3.12, FastAPI, asyncpg, redis[hiredis], httpx, structlog, opentelemetry — **zero libs novas**.
- PostgreSQL 15: `handoff_events` em `public` (admin-only, ADR-027). Novas colunas `conversations.*` sob RLS existente (ADR-011). **Advisory locks** (`pg_try_advisory_lock`) para singleton de schedulers — reuso do mecanismo ja presente em `ops/migrate.py`.
- Redis 7: idempotency webhooks + circuit breaker state per-helpdesk. **`bot_sent_messages` fica em PG** (nao Redis) para persistencia cross-restart; retention 48h via cron 12h.
- **Scheduler**: asyncio periodic task no FastAPI lifespan (`main.py`). ARQ worker **nao** e introduzido nesse epic (fica em backlog; blueprint sera reconciliado pos-epic).

**Dos ADRs existentes**:

- **ADR-011 RLS**: novas colunas em `conversations` (tabela tenant-scoped) herdam RLS — acessadas via `pool_app` com `SET LOCAL`. `handoff_events` (admin-only) via `pool_admin`.
- **ADR-027 admin-tables-no-rls**: `handoff_events` herda carve-out.
- **ADR-028 pipeline fire-and-forget**: push private note, sync assignee, metrics publish — todos fire-and-forget. Falha de helpdesk NUNCA bloqueia pipeline.
- **ADR-014 tool registry**: nao afetado (tools foram removidas na task paralela A1).

**Do domain model**:

- Bounded context **Conversation Pipeline** ganha novo gate `ai_active_check` no step `generate`.
- Novo bounded context **Handoff** (helpdesk adapters + events + rules). Isolado em `apps/api/prosauai/handoff/`.
- Bounded context **Observability** ganha agregado `HandoffEvent`.

**NFRs aplicaveis**:

- **p95 latencia texto** ≤ 5ms pior que baseline 009 (gate PR-A). Novo SELECT `ai_active` no path quente precisa ser indexado + cache se virar hotspot.
- **p95 webhook helpdesk → mute effective** < 500ms (gate PR-B). Webhook tolerante a duplicatas.
- **p95 composer admin → outbound** < 2s end-to-end (gate PR-C).
- **Zero regression** nos 173 tests epic 005 + 191 tests epic 008 + suites 009.

## Suggested Approach

### PR-A — Data model + HelpdeskAdapter + Chatwoot basico + pipeline (1 semana)

**Entregaveis**:

- Migration `20260501000001_create_handoff_fields.sql` — adiciona `ai_active`, `ai_muted_reason`, `ai_muted_at`, `ai_muted_by_user_id`, `ai_auto_resume_at`, `external_refs` em `conversations` + indices parciais (`ai_active = FALSE`, `ai_auto_resume_at IS NOT NULL`).
- Migration `20260501000002_create_handoff_events.sql` — tabela append-only em `public` (admin-only ADR-027) com `event_type`, `source`, `metadata jsonb`, indices por (tenant_id, created_at) e (conversation_id, created_at).
- Migration `20260501000003_create_bot_sent_messages.sql` — tracking de `message_id` enviados pelo bot para filtrar `fromMe` no NoneAdapter. PK `(tenant_id, message_id)`. **Retention 48h** (cleanup via cron 12h cadence no PR-B — ADR-018 extension).
- `apps/api/prosauai/handoff/` novo modulo:
  - `base.py` — `HelpdeskAdapter` Protocol
  - `registry.py` — factory por `helpdesk_type`
  - `chatwoot.py` — ChatwootAdapter (httpx client + HMAC verify + API v1 endpoints)
  - `state.py` — `mute_conversation()` / `resume_conversation()` com advisory lock + evento
  - `events.py` — `HandoffEvent` dataclass + `persist_event()` fire-and-forget
- `conversation/pipeline.py` step `generate` ganha safety net: `SELECT ai_active FOR UPDATE` + skip se false.
- `conversation/pipeline.py` step `customer_lookup` **amortiza** o read de `ai_active` junto com a resolucao do customer (single SELECT) para alimentar o router — substitui o read Redis em `api/webhooks/__init__.py:175`.
- `channels/outbound/evolution.py` grava `bot_sent_messages` apos cada send (fire-and-forget).
- Tests: 100% coverage em `state.py` + `chatwoot.py` (fixtures do webhook real Chatwoot).

**Gate de merge PR-A**:
- Todos tests existentes passam (zero regression).
- `ai_active=false` em conversation → pipeline nao chama LLM, emite trace step `ai_muted_skip`.
- Latencia texto ≤ 5ms pior que baseline 009.
- Conversa mutada manualmente via SQL direto funciona (validacao antes do webhook Chatwoot entrar).

### PR-B — NoneAdapter + webhooks + circuit breaker + transcripts (1 semana)

**Entregaveis**:

- `handoff/none.py` — `NoneAdapter` (detecta fromMe via hook no inbound Evolution).
- `api/webhooks/helpdesk/` novo package:
  - `chatwoot.py` — `POST /webhook/helpdesk/chatwoot/{tenant_slug}` com HMAC verify + idempotency
- `api/webhooks/evolution.py` estendido: se payload tem `fromMe: true` AND `message_id NOT IN bot_sent_messages` AND helpdesk_type==`none` → chama `state.mute(reason='fromMe_detected', auto_resume_at=now+human_pause_minutes)`.
- `handoff/breaker.py` — circuit breaker per-helpdesk (reusa padrao `processors/breaker.py`).
- `handoff/chatwoot.py` ganha `push_private_note(text)` chamado fire-and-forget apos content_process retornar.
- `config_poller.py` estendido: `tenants.yaml` schema novo `helpdesk: {...}` + `handoff: {mode: off|shadow|on, ...}`.
- Scheduler `handoff_auto_resume_cron` — **asyncio periodic task no FastAPI lifespan** (`main.py`). Singleton per-cluster via `pg_try_advisory_lock(hashtext('handoff_resume_cron'))` — replicas perdedoras dormem. Cadencia **60s**. Resume conversas com `ai_auto_resume_at < now()`. Shutdown graceful: `asyncio.wait(timeout=5s)` na iteration corrente.
- Scheduler `bot_sent_messages_cleanup_cron` — asyncio periodic task. Singleton via advisory lock `hashtext('bsm_cleanup_cron')`. Cadencia **12h**. `DELETE FROM bot_sent_messages WHERE sent_at < now() - interval '48 hours'`.
- **Shadow mode**: `state.mute_conversation()` checa `tenant.handoff.mode`; em `shadow`, emite evento com `shadow=true` e **nao** persiste `ai_active=false`. Pipeline `generate` safety net ignora `shadow` events. Metricas Performance AI mostram eventos shadow em cor distinta.
- Tests: integration com testcontainers-postgres + fakeredis + respx pra Chatwoot API mockada. Fixture real de webhook Chatwoot (capturar um em dev).

**Gate de merge PR-B**:
- Chatwoot webhook `assignee_changed` com non-null → `ai_active=false` em <500ms.
- Chatwoot `conversation_resolved` → `ai_active=true` + evento `event_type='resumed', source='helpdesk_resolved'`.
- NoneAdapter: `fromMe: true` injetado em fixture → mute. `bot_sent_messages` match → NAO muta.
- Circuit breaker: simular 5 timeouts Chatwoot → breaker abre → skip private notes → log `circuit_open`.
- Auto-resume cron: conversa com `auto_resume_at` no passado → muta=false, evento `source='timeout'`.
- Idempotencia: mesmo `Chatwoot-Event-Id` enviado 2x → segundo gera no-op + log `duplicate_webhook`.

### PR-C — Admin UI + metricas + rollout (1 semana)

**Entregaveis**:

- `apps/admin/src/app/admin/(authenticated)/conversations/[id]/page.tsx`:
  - Badge no topo: "AI ativa" (verde) / "AI silenciada por: {reason} desde {time}" (vermelho)
  - Botao "Silenciar AI" / "Retomar AI" (chama `/admin/conversations/{id}/mute` ou `/unmute`)
  - Composer emergencia: textarea + upload + "Enviar como Pace ops" — chama `/admin/conversations/{id}/reply` que delega pro adapter do tenant
- `apps/admin/src/app/admin/(authenticated)/performance/page.tsx`:
  - Nova row: "Handoff" com 4 cards
    - **Taxa de handoff** — % conversas com >=1 evento mute / total no periodo
    - **Duracao media silenciada** — avg (resumed_at - muted_at)
    - **Breakdown por origem** — Recharts pie chart sources
    - **SLA breaches** — count onde `auto_resume triggered` (timeout foi batido)
- Endpoint admin novo `POST /admin/conversations/{id}/reply` que delega ao adapter do helpdesk do tenant. Audit log entry per reply.
- `tenants.yaml` schema com `handoff.mode: off` default (valores: `off | shadow | on`). Migration operacional: Pace liga Ariel `off→shadow` (7d observacao), `shadow→on`, depois repete ResenhAI.
- **Admin composer identity**: endpoint `/admin/conversations/{id}/reply` injeta `sender_name=<JWT.email>` no payload do adapter. Audit entry em `handoff_events` com `metadata.admin_user_id=<JWT.sub>`. NoneAdapter: endpoint retorna 409.
- Playwright test: admin login → abrir conversa → clicar Silenciar → verificar badge → responder via composer → verificar mensagem enviada.

**Gate de merge PR-C**:
- Composer emergencia envia mensagem via Chatwoot API (tenant Ariel) → aparece no Chatwoot + no WhatsApp do cliente.
- Toggle manual flip `ai_active` + emite evento `source='manual_toggle'`.
- Performance AI tab renderiza 4 cards com dados reais do staging.
- Playwright E2E verde.
- Rollout: Ariel ligado em staging, observado 48h, ligado em prod.

## Testing Strategy

Resumo condensado (detalhe vai no `plan.md` pos-speckit):

- **Unit**: coverage ≥90% em `handoff/state.py`, ≥95% em `handoff/chatwoot.py` e `handoff/none.py`. Mocks via `respx` (httpx) e `AsyncMock`.
- **Integration**: testcontainers-postgres + fakeredis. Fluxos completos: (1) Chatwoot webhook → mute → inbound cliente → skip LLM → resume webhook → unmute → inbound cliente → bot responde. (2) fromMe detection → mute → auto_resume_cron → bot volta.
- **Contract**: `HelpdeskAdapter` protocol com parametrize sobre `ChatwootAdapter` + `NoneAdapter` (mesmo padrao do 009).
- **E2E Playwright**: J-003 (novo journey) — admin abre conversa com handoff ativo, ve badge, clica composer, envia, verifica outbound.
- **Race tests**: proposital concurrent update via `asyncio.gather` em 10 tentativas simultaneas de mute/unmute → apenas 1 ganha (advisory lock valida).
- **Smoke prod**: runbook `benchmarks/handoff_smoke.md` pre-rollout cada tenant.

## Risks

| # | Risco | Prob | Impacto | Mitigacao |
|---|-------|------|---------|-----------|
| R1 | Chatwoot muda formato de webhook entre versoes | Media | Medio | Fixtures reais capturadas em dev + contract test. Versao Chatwoot fixada no tenants.yaml per-tenant. |
| R2 | fromMe false positive (bot envia, recebe echo como fromMe, mata o proprio bot) | Baixa | Alto | `bot_sent_messages` tracking + teste dedicado "bot reply echo nao muta". Adicionalmente: `sent_at < 10s` tolerance window. |
| R3 | Advisory lock contention se tenant explode em volume | Baixa | Medio | Lock e per-conversation_id, nao global. Granularidade alta = zero contention em cargas reais. |
| R4 | Circuit breaker esconde falhas legitimas do Chatwoot | Media | Medio | Metrica `helpdesk_breaker_open` tagueada por tenant. Alerta quando >5min aberto. |
| R5 | Auto-resume 24h re-engaja bot em conversa que cliente ja deu por encerrada | Media | Baixa | Bot silencioso on resume (nao manda "oi"). Primeiro inbound apos resume passa por guard normal. |
| R6 | Composer emergencia Pace ops cria confusao "quem respondeu" — cliente X atendente X Pace | Baixa | Medio | Audit log + badge visivel no Chatwoot note "mensagem enviada via Pace ops admin". |
| R7 | Chatwoot shared Pace vira bottleneck com >20 tenants | Baixa | Medio (later) | Rate limit per-tenant na direcao ProsaUAI→Chatwoot (token bucket Redis). |
| R8 | Migration ai_active=true default em producao com tenants em conversa ativa | Media | Baixa | Migration e aditiva (nao altera comportamento). `handoff.mode:off` default protege rollout. |
| R9 | Composer expoe email Pace no Chatwoot do tenant (Q4 trade-off) | Media | Baixa | Aceito conscientemente: atendente do tenant identifica intervencao Pace especifica. Se virar problema, fallback para shared "Pace Ops" agent (Q4-B) e mudanca de ~30 LOC. |
| R10 | Deprecacao Redis key `handoff:*` quebra algum leitor esquecido | Baixa | Medio | PR-A mantem read path ativo com log estruturado `handoff_redis_legacy_read` para telemetria. PR-B remove so depois de 7d com zero leituras. |

## Scope-out (o que NAO entra)

Claramente fora pra evitar creep:

1. **Blip, Zendesk, Freshdesk, Front adapters** — epic 010.1 quando houver cliente. Interface do `HelpdeskAdapter` ja acomoda.
2. **Skills-based routing / queue prioritization no helpdesk** — helpdesk resolve isso nativamente (Chatwoot tem teams/assignments). ProsaUAI nao reimplementa.
3. **Handoff em group chat** — semantica ambigua. Backlog.
4. **Template Meta Cloud fora da janela 24h** — adapter retorna erro com alerta UI. Engenharia de templates aprovados e epic separado.
5. **Transfer entre atendentes** — Chatwoot ja faz. ProsaUAI nao precisa saber.
6. **SLA breach notifications em Slack/email** — publicamos metric events; integracao com canais de alerta e escopo do epic 014 (Alerting + WhatsApp Quality).
7. **Migration de conversas historicas** — epic nao re-processa conversas fechadas. `ai_active=true` default em todas existentes na migration.
8. **Dashboard agregado tipo "operator leaderboard"** — nao e valor user/ops. Se virar demanda, follow-up.

## Rollout Plan

Escalonado por tenant, opt-in:

| Dia | Passo | Verificacao |
|-----|-------|-------------|
| 0 | Merge PR-A em develop → deploy staging | Smoke: mute manual via SQL → bot nao responde |
| 2 | Merge PR-B → deploy staging | Webhook Chatwoot real (instancia staging Pace) → mute funcional |
| 5 | Merge PR-C → deploy staging | Playwright E2E passa; composer emergencia testado |
| 7 | Deploy prod com `handoff.mode:off` todos tenants | Zero mudanca observavel |
| 8 | Ariel → `handoff.mode:shadow` | Observar 7d: eventos shadow emitidos vs humano respondeu real — medir false-mute rate estimado |
| 15 | Ariel → `handoff.mode:on` | Observar 48h: metrica handoff_events real > 0, nenhum false mute reclamado |
| 17 | ResenhAI → `shadow` | Observar 7d |
| 24 | ResenhAI → `on` | Observar 48h |
| 28 | Review retrospectivo: metricas consolidadas, revisitar timeout default 24h + remover codigo shadow se nao agregar valor futuro | Ajustar defaults em tenants.yaml |

Kill switch: `handoff.mode:off` per-tenant flipa o bit (2 passos: `on→shadow→off` ou direto `on→off`), proximo webhook chatwoot e ignorado, bot volta a responder tudo. Reversivel sem deploy.

## Proximos Passos

Apos aprovacao deste pitch:

1. Branch `epic/prosauai/010-handoff-engine-inbox`
2. Skill `/madruga:epic-context 010` para gerar `spec.md`/`plan.md`/`tasks.md`
3. ADR-036, ADR-037, ADR-038 rascunho

> **Pre-epic cleanup executado em 2026-04-22 (develop):** agentes movidos para modo prompt-only. Deletados `apps/api/prosauai/tools/resenhai.py` + `apps/api/tests/tools/test_resenhai.py`. Seed migration `20260101000008_seed_data.sql` atualizado (`tools_enabled: []`). Nova migration forward `20260422000001_clear_tools_enabled.sql` limpa DBs existentes. 2117 tests passaram sem regressao. Registry pattern preservado para epic 013 (Agent Tools v2).

---

**Material tecnico completo**: este pitch cobre visao, decisoes travadas e sequenciamento. `spec.md` + `plan.md` + `tasks.md` serao gerados via skill `epic-context` e vao aprofundar schemas Pydantic exatos, algoritmos linha-a-linha, lista T001+ de tasks.
