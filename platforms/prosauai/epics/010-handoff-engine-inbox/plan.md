# Implementation Plan: Handoff Engine + Multi-Helpdesk Integration

**Branch**: `epic/prosauai/010-handoff-engine-inbox` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/010-handoff-engine-inbox/spec.md`

## Summary

Materializar o bit de estado **`conversations.ai_active`** — hoje o status `pending_handoff` e declarado mas nao existe (cf. [db/queries/conversations.py:16](apps/api/prosauai/db/queries/conversations.py#L16) "not yet materialised in the DB schema") e o fact `conversation_in_handoff` ([core/router/facts.py:66](apps/api/prosauai/core/router/facts.py#L66)) e **sempre false**. Resultado pratico em producao: o bot do ProsaUAI continua respondendo por cima do atendente humano que ja esta interagindo via Chatwoot. Este epic fecha o buraco com (a) um unico bit de estado na conversation, (b) um **`HelpdeskAdapter` Protocol** espelhando o `ChannelAdapter` do epic 009 (`ChatwootAdapter` + `NoneAdapter` no v1), (c) admin composer de emergencia para Pace ops, (d) 4 cards de metricas na aba Performance AI. Arquitetura multi-tenant e multi-helpdesk desde o dia um.

**Abordagem tecnica**: 6 colunas novas em `conversations` (`ai_active`, `ai_muted_reason`, `ai_muted_at`, `ai_muted_by_user_id`, `ai_auto_resume_at`, `external_refs JSONB`) sob RLS existente ([ADR-011](../../decisions/ADR-011-pool-rls-multi-tenant.md)); 2 tabelas novas admin-only em `public.*` (`handoff_events` append-only, `bot_sent_messages` tracking) sob carve-out [ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md); `pg_advisory_xact_lock(hashtext(conversation_id))` em toda transicao (serializa webhook + toggle + fromMe + auto-resume); pipeline step `generate` ganha `SELECT ai_active FOR UPDATE` safety net; pipeline step `customer_lookup` amortiza leitura de `ai_active` (substitui read Redis atual); scheduler `handoff_auto_resume_cron` como asyncio periodic task singleton via `pg_try_advisory_lock`; webhook idempotente via Redis SETNX. Side effects (push private note, sync externo) sao fire-and-forget ([ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md)) — **nunca** antes do commit do bit.

Execucao em **3 PRs mergeaveis isoladamente em `develop`**, cada um reversivel via feature flag `handoff.mode: off | shadow | on` (default `off`):

- **PR-A (1 semana)** Data model (6 colunas + 2 tabelas), `HelpdeskAdapter` Protocol + registry, `ChatwootAdapter` basico (HMAC + API v1), `state.mute_conversation/resume_conversation`, pipeline step `generate` safety net, `customer_lookup` amortiza read + popula `external_refs.chatwoot`. Mute manual via SQL direto ja funciona.
- **PR-B (1 semana)** `NoneAdapter` (`fromMe` deteccao via `bot_sent_messages`), webhooks `/webhook/helpdesk/chatwoot/{tenant}` (HMAC + idempotency + 2 event types), circuit breaker per-helpdesk, scheduler `handoff_auto_resume_cron` + `bot_sent_messages_cleanup_cron` + `handoff_events_cleanup_cron`, push de transcripts como private notes, config_poller estendido (`helpdesk` + `handoff` blocks), **shadow mode**.
- **PR-C (1 semana)** Admin UI (badges + toggle + composer emergencia), endpoint `POST /admin/conversations/{id}/reply` delegando ao adapter, Performance AI 4 cards (taxa, duracao, breakdown, SLA breaches), rollout gradual Ariel `off→shadow→on` → ResenhAI mesmo caminho.

**Cut-line explicito**: se PR-B estourar semana 2 → **PR-C sai de escopo** e vira follow-up (admin UI e visibilidade, nao valor core). O valor user-facing (bot nao fala em cima do humano) e entregue em PR-A+B isoladamente via SQL/curl de ops.

## Technical Context

**Language/Version**: Python 3.12 (backend FastAPI; frontend Next.js 15 do epic 008 estendido sem refatoracao — apenas badge + botao + composer + 4 cards Recharts).

**Primary Dependencies**:
- Existentes: FastAPI >=0.115, pydantic 2.x, asyncpg >=0.30, redis[hiredis] >=5.0, httpx, structlog, opentelemetry-sdk, opentelemetry-instrumentation-{fastapi,httpx,redis}, arize-phoenix-otel.
- **Nenhuma lib nova**. Chatwoot API v1 acessada via httpx. HMAC via stdlib `hmac` + `hashlib`.

**Storage**:
- PostgreSQL 15 (Supabase) — 3 migrations novas (`20260501_create_handoff_fields.sql`, `20260501_create_handoff_events.sql`, `20260501_create_bot_sent_messages.sql`); todas aditivas. Novas colunas em `conversations` herdam RLS existente; novas tabelas `handoff_events` e `bot_sent_messages` ficam em `public.*` sob carve-out [ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md) (admin-only via `pool_admin` BYPASSRLS).
- Redis 7 — novo prefixo `handoff:wh:{chatwoot_event_id}` (idempotency webhook, TTL 24h). **Nao conflita** com `buf:*` (debounce epic 001), `proc:*` (processor cache epic 009), `idem:*` (idempotencia epic 003). `handoff:{tenant}:{sender_key}` legacy (epic 004 placeholder) **mantido em PR-A com read tracing `handoff_redis_legacy_read`** e removido em PR-B apos 7d com zero leituras.

**Testing**: pytest + testcontainers-postgres + fakeredis + respx (httpx mock) + `AsyncMock` para scheduler. Cobertura alvo: `handoff/state.py` ≥95%, `handoff/chatwoot.py` ≥95%, `handoff/none.py` ≥95%, webhooks ≥90%. Fixtures: 2+ webhooks Chatwoot reais capturados em dev (assignee_changed + resolved) + 13 Evolution fixtures epic 009 reusadas para testar fromMe.

**Target Platform**: Linux server (uvicorn workers em container). Chatwoot instance Pace (VPS propria operacional). Evolution API existente (sem alteracao). Admin Next.js em Vercel (sem mudanca de infra).

**Project Type**: Backend-heavy com novo modulo `handoff/`; zero novo projeto/package Python. Frontend admin (epic 008) ganha badges + composer + 4 cards Recharts (sem refatoracao estrutural).

**Performance Goals**:
- p95 **texto** pos-PR-A: ≤ baseline (epic 009) +5ms (gate merge PR-A). Novo SELECT `ai_active` e amortizado em `customer_lookup` (single-roundtrip com resolucao de customer) — nao adiciona query extra ao hot path.
- p95 **webhook Chatwoot → mute efetivo**: < 500ms (gate merge PR-B, SC-002).
- p95 **admin composer → outbound entregue**: < 2s end-to-end (gate merge PR-C, SC-003).
- p95 **admin UI lista conversas (com badge)**: < 100ms (sem regressao epic 008).
- p95 **admin UI detalhe conversa**: < 2s (SC-013).
- Scheduler `handoff_auto_resume_cron` MUST retomar dentro de 60s da hora (SC-008).

**Constraints**:
- **Zero regressao** nos 173 tests epic 005 + 191 tests epic 008 + suites epic 009 — gate obrigatorio de merge de cada PR (SC-005).
- **Persistencia fire-and-forget**: falha de insert em `handoff_events`, push de private note, sync de assignee — NUNCA bloqueiam pipeline ou mute ([ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md)).
- **Single source of truth**: Postgres `conversations.ai_active`. Router le direto do PG. Redis key legacy e fact `conversation_in_handoff` sao **deprecated em PR-A** (log `handoff_redis_legacy_read` para telemetria) e **removidos em PR-B** apos 7d com zero leituras.
- **Ordenacao estrita**: commit DB → emissao evento → side effects fire-and-forget. NUNCA push private note antes do commit de `ai_active=false`.
- **Advisory lock obrigatorio**: toda transicao de `ai_active` MUST adquirir `pg_advisory_xact_lock(hashtext(conversation_id))` — race prevention entre 4 triggers possiveis (webhook, fromMe, manual, scheduler).
- **Composer identity trade-off aceito**: `sender_name = admin_user.email` (JWT sub) expoe email interno Pace no Chatwoot do tenant — trade-off consciente ([Decisao 15](./pitch.md#captured-decisions), [A14](./spec.md#assumptions)).
- **Group chat skip**: NoneAdapter pula deteccao `fromMe` silenciosamente em `is_group=true` ([Decisao 21](./pitch.md#captured-decisions)) — v1 handoff so 1:1.
- **Feature flag reload**: config_poller re-le `tenants.yaml` a cada 60s. Mudanca de `handoff.mode` entra em vigor sem deploy — RTO rollback ≤60s (FR-042).

**Scale/Scope**:
- 2 tenants ativos (Ariel, ResenhAI); rollout progressivo `off → shadow (7d) → on`, Ariel primeiro, ResenhAI replica 7d depois.
- Volume planejado: ~500 eventos de handoff/tenant/mes inicial → baixo (comparado a 10k+ midias/mes epic 009). `handoff_events` retention 90d em full detail (alinhado com `trace_steps` epic 008).
- `bot_sent_messages`: pico ~100k linhas/tenant (mensagens bot ultimas 48h) com cleanup cron 12h cadence.
- Nova camada: ~8 arquivos Python em `apps/api/prosauai/handoff/`, 3 migrations, 2 novos endpoints admin, 4 cards Recharts.
- Scope-out explicito: Blip, Zendesk, Freshdesk, Front, handoff em grupo, transfer entre atendentes, dashboard operator leaderboard, SLA breach via Slack/email, templates Meta Cloud fora da janela 24h.

## Constitution Check

*GATE: passa antes do Phase 0 research. Re-checked apos Phase 1 design.*

| Principio | Avaliacao | Justificativa |
|-----------|-----------|---------------|
| I — Pragmatismo & Simplicidade | PASS | Reusa 100% da stack Python do prosauai. **Zero libs novas**. Single bit boolean substitui state machine multi-step (decisao 1 em pitch). Protocol pattern ja validado no epic 009. Tabelas admin-only herdam carve-out ADR-027 existente. Nenhum framework novo. Shadow mode e `tenants.yaml` block — nao ha DSL novo. |
| II — Automate repetitive | PASS | Retention cron `handoff_events_cleanup_cron` usa mesmo padrao dos crons existentes (epic 006 + epic 009). Advisory lock singleton reusa mecanismo de `ops/migrate.py`. Fire-and-forget pattern ADR-028 aplicado. Pricing e OTel auto-instrumentation ja presentes. |
| III — Knowledge structured | PASS | `decisions.md` com 22 micro-decisoes. 3 ADRs novos (036-037-038) estendendo 4 existentes sem substituir. `research.md` preserva escopo tecnico integral. `pitch.md` mantem Shape Up canonico. Spec pos-clarify com 5 Q&As resolvidos autonomamente. |
| IV — Fast action | PASS | 3 PRs sequenciais com cut-line explicito (PR-C sacrificavel). Daily checkpoint em `easter-tracking.md` (convencao epic 008) flagra bleed cedo. Rollout shadow→on gradual reversivel em <60s. |
| V — Alternativas & trade-offs | PASS | `research.md` §Alternativas documenta 6 decisoes rejeitadas (state machine enum, Redis como source of truth, ARQ worker scheduler, tracking em Redis, DSL novo para rules, shared "Pace Ops" agent). Spec §Assumptions registra trade-offs aceitos (email Pace no Chatwoot, retention 48h bot_sent_messages, shadow mode opcional). |
| VI — Brutal honesty | PASS | Spec §Clarifications expoe 5 Q&As autonomamente resolvidos (retention 90d handoff_events, 2 event types Chatwoot, rules como referencia ao epic 004, `auto_resume_after_hours` range 1..168, linkage via `customer_lookup`). Confianca Media em Q2/Q5 declarada (depende de fixture real Chatwoot a capturar). Risco R9 (email Pace exposto) aceito conscientemente. |
| VII — TDD | PASS | 3 camadas (contract tests para HelpdeskAdapter Protocol + unit ≥95% state/adapters + integration testcontainers-postgres + fakeredis + respx Chatwoot). Gate merge PR-A: 173+191 tests PASS + latencia texto ≤baseline+5ms. Race tests explicitos (`asyncio.gather` com 10 mutes concorrentes). Contract tests bloqueiam drift de Protocol. |
| VIII — Collaborative decisions | PASS | 6 ambiguidades resolvidas na clarify pass (retention, event types, shape rules, range auto_resume, linkage external_refs, range human_pause_minutes). Pushback protocol aplicado nos Q&As epic-context (Q1-B escolhido PG-only, Q3-B shadow mode adicionado). |
| IX — Observability | PASS | `handoff_events` e audit trail append-only completo sem truncamento. OTel baggage `conversation_id + tenant_id` propagado do webhook inbound ate POST pro helpdesk. Metricas Prometheus novas: `handoff_events_total{tenant,event_type,source}`, `handoff_duration_seconds_bucket{tenant}`, `helpdesk_webhook_latency_seconds`, `helpdesk_breaker_open`. Logs estruturados structlog. Performance AI tab renderiza 4 cards. |

**Violacoes**: nenhuma. `Complexity Tracking` vazio.

### Post-Phase-1 re-check

| Risco | Status |
|-------|--------|
| R1 Chatwoot muda formato de webhook entre versoes | Mitigado: fixtures reais capturadas em dev (PR-A task T000) + contract test + versao Chatwoot fixada no `tenants.yaml` per-tenant |
| R2 fromMe false positive (bot echo mata bot) | Mitigado: `bot_sent_messages` tracking + janela tolerancia `sent_at < 10s` + teste dedicado `test_bot_echo_does_not_mute` |
| R3 Advisory lock contention em alto volume | Aceito: lock e per-`conversation_id` (hash 64-bit), granularidade alta. Stress test com 100 conversas paralelas valida |
| R4 Circuit breaker esconde falhas legitimas Chatwoot | Mitigado: metric `helpdesk_breaker_open{tenant}` + alerta >5min aberto (integracao com epic 014) |
| R5 Auto-resume 24h re-engaja bot em conversa encerrada | Mitigado: bot silencioso on resume (nao envia "oi"); primeiro inbound pos-resume passa por guards normais |
| R6 Composer emergencia cria confusao identidade | Mitigado: badge visivel no Chatwoot note + `sender_name=<admin.email>` explicito + audit log |
| R7 Chatwoot shared Pace vira bottleneck >20 tenants | Aceito (later): rate limit per-tenant via token bucket Redis se virar problema (monitorado via `helpdesk_api_4xx`) |
| R8 Migration `ai_active=true` default em conversa ativa | Aceito: migration aditiva; `handoff.mode: off` default protege rollout |
| R9 Composer expoe email Pace no Chatwoot do tenant | Aceito conscientemente (Q4-A clarify): fallback "Pace Ops" agent e ~30 LOC se virar problema |
| R10 Deprecacao Redis key `handoff:*` quebra leitor esquecido | Mitigado: PR-A mantem read path com log `handoff_redis_legacy_read`; PR-B remove so apos 7d zero leituras |
| Shadow mode desnecessario / overhead | Mitigado: ~50 LOC + 4 testes, removivel pos-validacao (decisao operacional) |
| Double advisory lock (cron + state) causa deadlock | Mitigado: cron usa `pg_try_advisory_lock` (non-blocking); `state.mute` usa `pg_advisory_xact_lock` (transaction-scoped, auto-release) — escopos disjuntos |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/010-handoff-engine-inbox/
├── plan.md                   # Este arquivo (/speckit.plan output)
├── spec.md                   # Feature specification (pos-clarify, 50+ FRs + 14 SCs)
├── pitch.md                  # Shape Up pitch (L2 — epic-context)
├── decisions.md              # 22 micro-decisoes capturadas
├── research.md               # Phase 0 — escopo tecnico integral + alternativas rejeitadas
├── data-model.md             # Phase 1 — schemas Pydantic + SQL + ER diagram + Redis namespaces
├── contracts/
│   ├── README.md             # Indice + gates de contrato
│   ├── helpdesk-adapter.md   # Protocol HelpdeskAdapter (Python) + ChatwootAdapter + NoneAdapter
│   └── openapi.yaml          # OpenAPI 3.1 (webhooks helpdesk + endpoints admin)
├── quickstart.md             # Phase 1 — setup dev + validacao US1-US7 + rollback
├── checklists/               # Ja populado via epic-context
└── tasks.md                  # Phase 2 output (gerado por /speckit.tasks — NAO por este comando)
```

### Source Code (repository root — repo externo `paceautomations/prosauai`)

```text
apps/
├── api/                                              # backend FastAPI (existente)
│   ├── prosauai/
│   │   ├── main.py                                   # register HelpdeskAdapter via registry (aditivo) + start lifespan schedulers
│   │   ├── config.py                                 # EXTEND: HELPDESK_POLL_INTERVAL, HANDOFF_AUTO_RESUME_INTERVAL_SECONDS
│   │   ├── api/
│   │   │   ├── webhooks/                             # do epic 009
│   │   │   │   ├── evolution.py                      # EXTEND: hook NoneAdapter fromMe detection (PR-B)
│   │   │   │   └── helpdesk/                         # NEW (PR-B)
│   │   │   │       ├── __init__.py
│   │   │   │       └── chatwoot.py                   # POST /webhook/helpdesk/chatwoot/{tenant_slug}
│   │   │   └── admin/                                # ja existe (epic 008)
│   │   │       └── conversations.py                  # EXTEND: mute/unmute/reply endpoints
│   │   ├── handoff/                                  # NEW — modulo formal
│   │   │   ├── __init__.py
│   │   │   ├── base.py                               # HelpdeskAdapter Protocol + errors
│   │   │   ├── registry.py                           # register/get/registered_helpdesks
│   │   │   ├── state.py                              # mute_conversation / resume_conversation (advisory lock)
│   │   │   ├── events.py                             # HandoffEvent dataclass + persist_event fire-and-forget
│   │   │   ├── breaker.py                            # CircuitBreaker per-helpdesk (reusa padrao epic 009)
│   │   │   ├── chatwoot.py                           # ChatwootAdapter (httpx + HMAC + API v1)
│   │   │   ├── none.py                               # NoneAdapter (Evolution fromMe hook)
│   │   │   └── scheduler.py                          # asyncio periodic tasks (auto_resume, cleanup handoff_events, cleanup bot_sent_messages)
│   │   ├── channels/
│   │   │   └── outbound/
│   │   │       └── evolution.py                      # EXTEND: grava bot_sent_messages apos send (PR-A)
│   │   ├── conversation/
│   │   │   └── pipeline/steps/
│   │   │       ├── customer_lookup.py                # EXTEND: amortiza read `ai_active` + popula external_refs.chatwoot
│   │   │       └── generate.py                       # EXTEND: SELECT ai_active FOR UPDATE safety net + skip ai_muted_skip
│   │   ├── core/
│   │   │   └── router/
│   │   │       ├── facts.py                          # EXTEND: conversation_in_handoff lido de ai_active + log legacy_read (PR-A)
│   │   │       └── rules.py                          # EXTEND: rule match emite state.mute(reason='rule_match', metadata={rule_name})
│   │   ├── observability/
│   │   │   └── step_record.py                        # EXTEND: ai_muted_skip step type
│   │   ├── db/
│   │   │   ├── queries/
│   │   │   │   └── conversations.py                  # EXTEND: remove TODO pending_handoff (decisao 1); add mute/resume queries
│   │   │   └── migrations/
│   │   │       ├── 20260501000001_create_handoff_fields.sql         # NEW (PR-A) — 6 colunas + 2 indices parciais
│   │   │       ├── 20260501000002_create_handoff_events.sql         # NEW (PR-A) — append-only table
│   │   │       └── 20260501000003_create_bot_sent_messages.sql      # NEW (PR-A) — tracking table
│   │   ├── admin/                                    # existente do epic 008
│   │   │   └── metrics/
│   │   │       └── performance.py                    # EXTEND: 4 queries agregadas handoff_events
│   │   └── tenants/                                  # existente do epic 003
│   │       └── config_poller.py                      # EXTEND: schema tenants.yaml (helpdesk + handoff blocks)
│   ├── tests/
│   │   ├── contract/
│   │   │   └── test_helpdesk_adapter_contract.py     # NEW — Protocol conformance para ChatwootAdapter + NoneAdapter
│   │   ├── unit/
│   │   │   ├── handoff/
│   │   │   │   ├── test_state.py                     # NEW — mute/resume + advisory lock
│   │   │   │   ├── test_chatwoot.py                  # NEW — HMAC + API mocks via respx
│   │   │   │   ├── test_none.py                      # NEW — fromMe detection + group skip + echo tolerance
│   │   │   │   ├── test_events.py                    # NEW — HandoffEvent persistence fire-and-forget
│   │   │   │   ├── test_breaker.py                   # NEW — circuit breaker per-helpdesk
│   │   │   │   ├── test_scheduler.py                 # NEW — auto_resume cron + cleanup crons + singleton lock
│   │   │   │   └── test_registry.py                  # NEW
│   │   │   ├── pipeline/
│   │   │   │   ├── test_generate_safety_net.py       # NEW — pipeline skip quando ai_active=false
│   │   │   │   └── test_customer_lookup_amortized.py # NEW — single SELECT + external_refs populate
│   │   │   └── api/
│   │   │       ├── webhooks/
│   │   │       │   └── test_helpdesk_chatwoot.py     # NEW — HMAC + idempotency + 2 event types
│   │   │       └── admin/
│   │   │           └── test_conversations_handoff.py # NEW — mute/unmute/reply endpoints + 409 NoneAdapter
│   │   ├── integration/
│   │   │   ├── test_handoff_flow_chatwoot.py         # NEW — webhook → mute → inbound skip → resume → inbound responds
│   │   │   ├── test_handoff_flow_none_adapter.py     # NEW — fromMe → mute → auto_resume cron → bot volta
│   │   │   ├── test_handoff_concurrent_transitions.py# NEW — race test asyncio.gather 10 mutes
│   │   │   └── test_handoff_composer_admin.py        # NEW — POST /admin/reply → Chatwoot API
│   │   ├── benchmarks/
│   │   │   ├── test_text_latency_no_regression.py    # NEW — gate SC-004 PR-A (≤ baseline+5ms)
│   │   │   └── test_webhook_latency.py               # NEW — gate SC-002 PR-B (< 500ms p95)
│   │   └── fixtures/
│   │       └── captured/
│   │           ├── chatwoot_conversation_updated_assignee.input.json  # NEW (PR-A)
│   │           ├── chatwoot_conversation_updated_unassigned.input.json# NEW (PR-A)
│   │           ├── chatwoot_conversation_status_resolved.input.json   # NEW (PR-A)
│   │           └── evolution_fromMe_human.input.json                  # NEW (PR-B)
│   └── scripts/
│       └── sign_chatwoot_webhook.py                  # NEW (PR-A) — helper HMAC para dev
├── admin/                                            # Next.js — epic 008
│   └── src/
│       └── app/admin/(authenticated)/
│           ├── conversations/
│           │   ├── page.tsx                          # EXTEND: badge ai_active por linha (PR-C)
│           │   └── [id]/page.tsx                     # EXTEND: botao toggle + composer emergencia (PR-C)
│           └── performance/
│               └── page.tsx                          # EXTEND: linha "Handoff" com 4 cards Recharts (PR-C)
└── tenants.yaml                                      # EXTEND: blocos helpdesk.* + handoff.* per tenant
```

**Structure Decision**: Backend-heavy com **novo modulo `handoff/`** em `apps/api/prosauai/` — padrao ja validado no epic 009 (`channels/`, `processors/`). Protocol-based contract para multi-helpdesk, registry por tipo, fire-and-forget side effects. Zero novo projeto/package Python — tudo sob o namespace `prosauai.*` existente. Frontend admin do epic 008 ganha apenas extensoes localizadas (2 paginas existentes + 1 linha Performance AI + 1 endpoint admin novo). Testes reutilizam estrutura `tests/{contract,unit,integration,benchmarks,fixtures}` ja estabelecida.

## Complexity Tracking

> Nenhuma violacao de Constitution Check identificada. Esta tabela permanece vazia.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 — Research (already complete)

**Output**: [research.md](./research.md) — preserva escopo tecnico integral e alternativas consideradas. Todas as `NEEDS CLARIFICATION` estao resolvidas:

- [pitch.md](./pitch.md) §Captured Decisions — 22 decisoes locked com referencias.
- [pitch.md](./pitch.md) §Resolved Gray Areas — 14 pontos tipicamente perguntados pelo skill epic-context, decididos autonomamente na activation 2026-04-23.
- [spec.md §Clarifications](./spec.md#clarifications) — 6 Q&As resolvidos autonomamente durante o clarify pass (retention handoff_events, 2 event types Chatwoot, rules como referencia epic 004, range auto_resume_after_hours, linkage via customer_lookup, range human_pause_minutes).
- [decisions.md](./decisions.md) — 22 decisoes ordenadas com data, skill e referencia.

**Alternativas consideradas e rejeitadas** (resumo — detalhes em [research.md](./research.md) §Alternativas):

| Alternativa | Rejeitada por |
|-------------|---------------|
| Enum state machine `open → pending_handoff → in_handoff → resolved` | Overengineering: conversa sempre aparece no Chatwoot+WhatsApp; o que muda e **se bot responde**. Single bit captura semantica; enum adiciona estados falsos ("in_handoff" quando humano ja assumiu = mesma coisa que "handoff iniciado"). |
| Redis como fonte de verdade (write-through PG) | Cria classe de bugs de divergencia Redis↔PG sob particao. Router ja faz `SELECT customer` em `customer_lookup` — amortizar `ai_active` no mesmo SELECT elimina o problema sem custo. |
| ARQ worker dedicado para auto_resume scheduler | Infra nova para ~100 conversas/min SLA. Asyncio periodic task + advisory lock singleton entrega mesma garantia com zero overhead. ARQ fica no backlog caso outro caso de uso justifique. |
| `bot_sent_messages` em Redis (TTL 48h) | Cross-restart data loss risco: se bot reinicia e Evolution retorna echo de mensagem pre-restart, Redis perdeu o ID → false positive mute. PG garante durabilidade. Tradeoff: +1 tabela + cleanup cron, mas previne false positive. |
| DSL novo para `handoff.rules[]` | Epic 004 ja tem engine de regras com evaluator YAML. Reuso integral — `rules[]` e array de **nomes** de regras ja existentes. Zero DSL novo. |
| Shared "Pace Ops" agent no Chatwoot (composer identity) | Perde auditoria granular: atendente do tenant nao sabe quem da Pace interveio. Email `admin_user.email` identifica individualmente. R9 aceito conscientemente. |
| Evento `pending_handoff` como status de conversation | Sugerido no comment original do codigo. Mas viola decisao 1 (boolean vs enum). Remove TODO, mantem status operacional simples (`open`/`closed`). |
| Store operator name (Chatwoot agent profile fetch) | Privacy concern cross-tenant + overhead de fetch. ID externo em `metadata` basta para audit. Display "Agent #123" no admin. |

## Phase 1 — Design Artifacts

### Artefatos gerados neste plan

| Artefato | Proposito | Referencia |
|----------|-----------|-----------|
| **data-model.md** | Schemas Pydantic (`HandoffState`, `HandoffEventRecord`, `BotSentMessageRecord`); SQL das 3 migrations; ER diagram; Redis key pattern + TTL; extensao `tenants.yaml` schema; validacoes por camada; rejected alternatives | [data-model.md](./data-model.md) |
| **contracts/helpdesk-adapter.md** | Protocol `HelpdeskAdapter` + 5 metodos obrigatorios + `HelpdeskAdapterError`/`InvalidPayloadError`/`AuthError`; comportamento de `ChatwootAdapter` e `NoneAdapter`; contract tests com `isinstance` + Protocol check | [contracts/helpdesk-adapter.md](./contracts/helpdesk-adapter.md) |
| **contracts/openapi.yaml** | OpenAPI 3.1 dos endpoints novos (`POST /webhook/helpdesk/chatwoot/{tenant_slug}`, `POST /admin/conversations/{id}/mute`, `POST /admin/conversations/{id}/unmute`, `POST /admin/conversations/{id}/reply`); schemas `ChatwootWebhookPayload`, `MuteRequest`, `ReplyRequest`, `ErrorResponse` | [contracts/openapi.yaml](./contracts/openapi.yaml) |
| **quickstart.md** | Setup dev + validacao incremental por PR (PR-A / PR-B / PR-C); validacao por User Story (US1-US7); rollback de emergencia; troubleshooting | [quickstart.md](./quickstart.md) |

### ADRs planejados (3 novos, estendem 4 existentes)

Geracao e tarefa explicita do PR-A (ADRs 036-037) e PR-B (ADR-038). Esbocos ja em [decisions.md](./decisions.md):

| # | Titulo | Escopo | PR |
|---|--------|--------|-----|
| ADR-036 | `ai_active` unified mute state (boolean single-bit) | Substitui discussao `pending_handoff` / enum multi-step (decisao 1 pitch) | PR-A |
| ADR-037 | HelpdeskAdapter pattern (multi-helpdesk integration) | Protocol + registry, espelha ADR-031 (ChannelAdapter) | PR-A |
| ADR-038 | fromMe auto-detection semantics (NoneAdapter) | `bot_sent_messages` tracking + 10s echo tolerance + group skip | PR-B |

**ADRs estendidos (nao substituidos)**:
- [ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md) — `handoff_events` e `bot_sent_messages` herdam carve-out admin-only.
- [ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md) — push private note, sync assignee, `handoff_events` insert: todos fire-and-forget.
- [ADR-011](../../decisions/ADR-011-pool-rls-multi-tenant.md) — novas colunas em `conversations` (tabela tenant-scoped) herdam RLS via `pool_app` com `SET LOCAL tenant_id`.
- [ADR-018](../../decisions/ADR-018-data-retention-lgpd.md) — estendido com retention policy 90d `handoff_events` + 48h `bot_sent_messages`.

### Agent context update

Apos merge de cada PR, `update-agent-context.sh claude` reflete:
- PR-A: novo modulo `handoff/` e 3 tabelas (aditivo, sem tech nova).
- PR-B: adapters registrados, scheduler no lifespan.
- PR-C: nada novo — UI extensao localizada.

---

## Sequenciamento & guardrails

### Cronograma

| Semana | PR | Entregaveis | Gate de merge |
|--------|----|-------------|---------------|
| 1 early | PR-A coding | ADRs 036-037 draft; fixtures Chatwoot reais capturadas; `handoff/base.py`, `registry.py`, `state.py`, `events.py`, `breaker.py`; `ChatwootAdapter` stub sem auth; 3 migrations; `generate` safety net; `customer_lookup` amortiza read + popula `external_refs.chatwoot`; Redis legacy read + log `handoff_redis_legacy_read` | — |
| 1 merge | PR-A merge | 173+191 tests PASS + zero regression pipeline 009; latencia texto ≤baseline+5ms; mute manual via SQL direto funciona end-to-end (conversa mutada → bot skip → trace mostra `ai_muted_skip`); contract tests PASS | SC-004, SC-005 |
| 2 early | PR-B coding | ADR-038 draft; `NoneAdapter` (Evolution hook); webhook `/webhook/helpdesk/chatwoot/{tenant_slug}` com HMAC + idempotency + 2 event types; scheduler `handoff_auto_resume_cron` + `bot_sent_messages_cleanup_cron` + `handoff_events_cleanup_cron`; circuit breaker; push private note fire-and-forget; config_poller extends; **shadow mode** | — |
| 2 merge | PR-B merge | webhook Chatwoot → mute em <500ms p95; fromMe → mute + auto_resume cron funcional; race test 10 concurrent mutes → apenas 1 ganha; shadow mode emite eventos sem mutar; circuit breaker valida isolamento; Redis legacy ja sem leituras (log counter = 0) | SC-002, SC-006, SC-007, SC-008, SC-009, SC-011 |
| 3 early | PR-C coding | Admin UI badges + toggle + composer (`POST /admin/conversations/{id}/reply` delegando ao adapter); endpoint 409 para NoneAdapter; Performance AI 4 cards (taxa, duracao, breakdown, SLA breaches); Playwright E2E | — |
| 3 merge | PR-C merge | composer admin funcional (Chatwoot Ariel) → WhatsApp cliente em <2s p95; Performance AI renderiza 4 cards em <3s com dataset real; Playwright E2E verde; rollout Ariel `off→shadow→on` preparado | SC-003, SC-010, SC-013, SC-014 |
| Pos-3 | Rollout | Ariel `off→shadow` (observa 7d) → `on` (48h validacao) → ResenhAI replica mesmo trajeto | SC-001, SC-012 |

### Reconcile apos cada PR-merge

Hook automatico fire do `madruga:reconcile` detecta drift entre docs e codigo implementado. Esperado: zero drift (artefatos Phase 1 detalham 1:1 o codigo-alvo).

### Cut-line explicito

Se PR-B estourar semana 2 → **cortar PR-C** → admin UI vira follow-up epic 010.1. Criterio: valor user-facing (bot nao fala em cima do humano) e entrega minima — e cumprido por PR-A+B via SQL direto (mute manual) + webhook Chatwoot (mute automatico). PR-C entrega visibilidade e escape hatch ops, nao core — sacrificavel.

### Daily checkpoint

`easter-tracking.md` (convencao epic 008) flagra bleed cedo. Daily standup async com 3 bullets: (a) o que foi mergeavel ontem, (b) o que e mergeavel hoje, (c) o que esta bloqueando.

---

## Testing strategy (resumo)

- **Unit** (≥95% handoff/state.py, handoff/chatwoot.py, handoff/none.py; ≥90% webhooks/schedulers): `respx` para Chatwoot API mock; `AsyncMock` para httpx wrapper; `fakeredis` para idempotency; `testcontainers-postgres` para advisory lock validation; `freezegun` para cron time-travel.
- **Contract** (Protocol conformance): `isinstance(adapter, HelpdeskAdapter)`. Garante que `ChatwootAdapter` e `NoneAdapter` respeitam API. Novos adapters em epic 010.1 entram no mesmo teste parametrizado.
- **Integration** (testcontainers-postgres + fakeredis + respx Chatwoot): fluxos completos por US — US1 (Chatwoot assign→mute→skip→resolve→resume→bot responde), US2 (timeout scheduler), US4 (NoneAdapter fromMe + group skip), US5 (composer emergencia).
- **Race tests** (proposital concurrency): `asyncio.gather` com 10 mutes concorrentes na mesma conversa → apenas 1 ganha (advisory lock valida). `asyncio.gather` com 5 webhooks duplicados (mesmo event_id) → apenas 1 gera evento (Redis SETNX valida).
- **E2E Playwright** (reuso infra epic 008): US3 (admin badge + toggle manual), US5 (composer admin → Chatwoot → Evolution → cliente).
- **Benchmarks** (gate merge): `test_text_latency_no_regression.py` (SC-004 PR-A), `test_webhook_latency.py` (SC-002 PR-B).
- **Fixtures reais**: 2+ webhooks Chatwoot capturados em dev (task T000 em PR-A) + Evolution `fromMe` fixture + 13 Evolution fixtures epic 009 reusadas.
- **Smoke prod**: runbook `apps/api/benchmarks/handoff_smoke.md` pre-rollout cada tenant.

---

## Dependencias externas

| Item | Origem | Escopo |
|------|--------|--------|
| Chatwoot API v1 credentials per-tenant | Chatwoot Pace (operacional) | PR-A (token em `tenants.yaml`) |
| Chatwoot webhook secret per-tenant | Chatwoot Pace | PR-B (HMAC X-Webhook-Secret) |
| Evolution API operacional | Existente (sem mudanca) | Todos PRs (hook fromMe em PR-B) |
| Nenhuma lib Python nova | — | — |

**Sem blockers**: epic 008 e 009 fechados (reconcile reports existem). Infraestrutura Redis 7 + Postgres 15 via Supabase ja provisionada. Chatwoot Pace operacional com integracao Evolution desde 2026-03. Ariel e ResenhAI ja tem `chatwootConversationId` injetado em todo webhook Evolution.

---

## Estrutura de PR (contratos explicitos)

Cada PR carrega:

1. **Descricao**: qual decisao arquitetural esta sendo entregue + qual User Story(ies) sao servidas.
2. **Checklist de gates**: itens SC-NNN que devem passar antes do merge.
3. **Rollback plan**: sequencia exata para desligar a feature (`handoff.mode: on → off` per tenant no `tenants.yaml` → aguarda poll 60s → webhook volta a ser no-op → bot responde tudo).
4. **Observability plan**: quais metricas acompanhar nas primeiras 24h em staging (`handoff_events_total`, `helpdesk_webhook_latency_seconds`, `helpdesk_breaker_open`, `bot_sent_messages` volume).

### Rollback matrix

| Cenario | Acao | RTO |
|---------|------|-----|
| Mute indevido de tenant especifico | `tenants.yaml` → `handoff.mode: on → off` | ≤60s (config_poller) |
| Webhook Chatwoot flood | `tenants.yaml` → `handoff.mode: shadow` (ignora mute real mas mede) | ≤60s |
| Circuit breaker cascading | Metric alerta; Chatwoot admin investiga; shadow mode como fallback | Manual |
| Migration regressao producao | `dbmate rollback` nas 3 migrations (todas aditivas, sem data loss) | Deploy window |
| Scheduler mata conversas ativas (bug auto_resume) | `HANDOFF_AUTO_RESUME_ENABLED=0` env + deploy | ≤5min |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan consolidado com 3 PRs (PR-A data model + Chatwoot stub + pipeline safety net, PR-B NoneAdapter + webhooks + scheduler + shadow mode, PR-C admin UI + metricas + rollout). Zero libs novas. 3 migrations aditivas, 3 ADRs novos (036-037-038). Cut-line: PR-C sacrificavel se PR-B estourar semana 2. Pronto para quebrar em tasks.md T001+."
  blockers: []
  confidence: Alta
  kill_criteria: "Se fixture real de webhook Chatwoot (tarefa T000 PR-A) revelar shape incompativel com o contrato em contracts/helpdesk-adapter.md, ou se stress test de advisory lock mostrar contention significativo (>5% p95 degradation) em 100 conversas paralelas, reabrir decisoes 3 (adapter) e 11 (lock granularity) antes de prosseguir."
