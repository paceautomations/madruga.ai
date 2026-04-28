---
id: "016"
title: "Trigger Engine — engine declarativo de mensagens proativas (cron-driven, 3 trigger types pre-built, cooldown granular, history viewer)"
slug: 016-trigger-engine
appetite: "2 semanas"
status: drafted
priority: P3
depends_on: ["010-handoff-engine-inbox"]
created: 2026-04-26
updated: 2026-04-26
---

# Epic 016 — Trigger Engine (mensagens proativas declarativas)

> **DRAFT** — planejado em sequencia apos 015. Promocao via `/madruga:epic-context prosauai 016` (sem `--draft`) faz delta review e cria branch.

## Problema

A [vision §6](../../business/vision.md) firma a tese comercial em duas pernas: **respostas user-initiated sao gratis** (service conversations Meta, desde Nov/2024) **+ custo variavel apenas em mensagens proativas** (templates). O glossario da vision define `Trigger | Mensagem proativa enviada pelo agente por evento ou agendamento` e da o exemplo canonico: *"Trigger de lembrete enviado 1h antes do jogo"*.

[ADR-006 (Agent-as-Data)](../../decisions/ADR-006-agent-as-data.md) §"Camadas de customizacao" promete em §"Triggers": *"Phase 1: 4 hardcoded. v2: IF condition THEN action configuravel"*. Hoje (pos epic 005-015) a Phase 2 **nunca foi implementada**:

1. **Zero infra de trigger no codigo**. Pesquisa em `apps/api/prosauai/` retorna so triggers contextuais (`@register_tool` decorator side-effects, `triggered = quality_score > threshold` em evals). Nenhum modulo `triggers/`. Nenhuma tabela `trigger_events`. Nenhum endpoint de proativos.

2. **Outbound atual e reactive-only**. `EvolutionProvider.send_text` envia free-form como resposta a inbound, **nao envia templates** pre-aprovados. Para enviar mensagem proativa via WhatsApp Business, Meta exige template aprovado (`namespace`, `language`, `name`, `components`) — sem isso, mensagem fora de service window e bloqueada. Codigo precisa de novo metodo `send_template()`.

3. **Use cases concretos parados**:
   - **ResenhAI** (vision example): "Trigger de lembrete enviado 1h antes do jogo" — operador hoje envia manualmente via WhatsApp pessoal. Nao escala alem de 5-10 partidas/semana.
   - **E-commerce** (vision §1.2 segmento): carrinho abandonado, follow-up apos compra, notificacao de estoque. Mercado real bloqueado.
   - **Servicos** (vision §1.3 segmento): lembrete de consulta, follow-up apos atendimento. Mercado real bloqueado.

4. **Risk #4 vision (ban WhatsApp)** sem mitigacao especifica para proativos. Mensagens proativas exageradas → Meta penaliza com tier downgrade ou ban. Epic 014 entrega quality monitoring + warm-up cap mas **nao tem cooldown anti-spam por cliente** — qualquer engine de trigger sem isso vira gerador de ban.

5. **Sem persistence de trigger fired**. Quando lembrete proativo for enviado, nao existe audit trail (quem disparou, quando, qual template, status, custo). Operador nao consegue responder pergunta basica: "este cliente recebeu nosso lembrete ontem?". LGPD SAR (ADR-018) tambem precisa cascadear esses dados.

6. **ADR-004 (PG LISTEN/NOTIFY)** travou o mecanismo geral de eventos real-time, mas com guarda explicito sobre **lock global** + threshold para migrar para bridge pattern. Para triggers (todos use cases v1 sao **scheduled/timed**, nao event-reactive), PG NOTIFY adicionaria complexity sem ganho — cron-only resolve com pattern reusado de epic 010/011.

7. **Sem caminho declarativo**. ADR-006 promete Phase 2 *"IF condition THEN action configuravel"* — Phase 2 e o que esta epic entrega. Sem isso, todo trigger novo exige PR + code review + deploy (anti-pattern #13 do ADR-006: onboarding de novo cliente nao depende de eng).

8. **Coupling forte com epic 014**. Send_template path precisa do circuit breaker per `(tenant, phone_number_id)` + warm-up cap enforcement (epic 014 drafted). 016 monta em cima dessa fundacao.

Epic 016 entrega:

- **Engine declarativo** com 3 trigger types pre-built (`time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`) + escape hatch `custom` em 016.1+.
- **Cron-driven scheduler** (15s cadence) com advisory lock singleton — pattern epic 010/011/014.
- **`tenants.yaml triggers.*` + `tenants.yaml templates.*` blocks** — config declarativa, hot reload <60s, zero infra nova.
- **Cooldown granular per `(tenant, customer, trigger_id)` + global daily cap per customer** — anti-spam + anti-ban.
- **Novo metodo `EvolutionProvider.send_template()`** integrado com breaker + warm-up cap do epic 014.
- **Tabela `public.trigger_events`** (admin-only ADR-027 carve-out) com audit trail + LGPD SAR cascade.
- **Admin history viewer read-only** — lista de execucoes recentes filtravel por tenant/customer/trigger/status. Editor de config vira 016.1+.
- **5 metricas Prometheus + 2 alert rules** (cost overrun + template rejection rate).

## Appetite

**2 semanas** (1 dev full-time, sequencia de 2 PRs mergeaveis em `develop`, reversivel via `triggers.enabled: false` per-tenant em <60s).

| Semana | Entrega | Gate |
|--------|---------|------|
| Sem 1 | Schema migration (`public.trigger_events`) + scheduler cron + 3 trigger types pre-built (matchers Python) + cooldown logic Redis + persistence + Pydantic models para `tenants.yaml triggers.*`/`templates.*` + unit tests verdes | Smoke: trigger de teste configurado em `tenants.yaml` Ariel dispara cron, cria row em `trigger_events`, mas nao envia (apenas log) |
| Sem 2 | `EvolutionProvider.send_template()` integrado com breaker + warm-up cap (epic 014) + Prometheus series + 2 alert rules + admin history viewer (lista filtravel + drill-down) + Ariel rollout shadow→on com 1 trigger real (lembrete jogo) | Ariel envia 1 template real para 1 cliente teste; admin Saude tab mostra row em `trigger_events`; cooldown bloqueia 2a tentativa <24h; cap diario bloqueia 4o trigger |

**Cut-line dura**: se semana 1 estourar (improvavel — scheduler + 3 matchers e escopo controlado), **PR-B vira 016.1**. PR-A entrega so engine + persistence + cooldown sem send real (apenas log "would send").

**Cut-line mole**: se semana 2 estourar (provavel risco: Evolution API `/sendTemplate` endpoint surpreende com semantica de components/parameters), **admin history viewer vira 016.1**. Send_template + breaker integration ficam em 016. Operador consulta `trigger_events` via SQL no curto prazo.

## Dependencies

Prerrequisitos:

- **010-handoff-engine-inbox (shipped)** — scheduler pattern (`prosauai/handoff/scheduler.py`) reusado integralmente: lifespan periodic task + `pg_try_advisory_lock(hashtext('triggers_engine_cron'))` singleton + cadence configuravel + structlog facade. Pattern de cooldown via Redis tambem reusado.
- **014-alerting-whatsapp-quality (drafted)** — Prometheus + Alertmanager + `prometheus_client` + send breaker per `(tenant, phone_number_id)` + warm-up cap. Esta epic emite series novas + 2 alert rules + integra com breaker. Hard dep — sem 014, send_template enviaria sem proteção contra ban.
- **011-evals (shipped)** — pattern fire-and-forget para emit de scores. Esta epic emit `trigger_events.cost_usd_estimated` via mesmo padrao para futuro billing (epic 019). Eval per-trigger output (LLM-as-judge se template foi adequado) adiado para 016.1+.
- **006-production-readiness (shipped)** — migration runner fail-fast no startup, idempotente. Schema change segue o pattern.
- **005-conversation-core (shipped)** — `EvolutionProvider` + customer/conversation/messages tables. Esta epic adiciona metodo novo `send_template()` ao provider e le `customers.scheduled_event_at` (coluna nova) + `conversations.closed_at` (existente) + `messages.created_at` (existente).
- **008-admin-evolution (shipped)** — admin Next.js 15 + pool_admin BYPASSRLS + TanStack Query v5 + shadcn/ui. Aba history viewer reusa pattern existente.

Pre-requisitos que **nao bloqueiam**:

- **012-tenant-knowledge-base-rag (shipped)** + **013-agent-tools-v2 (drafted)** — triggers v1 enviam apenas templates pre-approved (parametros simples). Sem RAG/tools per-trigger em v1.
- **015-agent-pipeline-steps (drafted)** — pipeline_steps eh para mensagens **inbound**; triggers sao **outbound proativos** sem reasoning multi-step. Zero coupling.

ADRs novos desta epic (draft — promocao pode ajustar):

- **ADR-049** — Trigger Engine declarativo (cron-driven + `tenants.yaml triggers.*` blocks + 3 types pre-built + custom escape hatch + cooldown granular + global daily cap)
- **ADR-050** — WhatsApp Template Catalog em `tenants.yaml templates.*` (per-tenant pre-approved Meta templates; manual sync com Meta Business Manager em v1; auto-sync via Graph API em 016.1+)

ADRs estendidos:

- **ADR-004** PG LISTEN/NOTIFY — **NAO usado em v1** para triggers (decision deliberate: cron-only). PG NOTIFY listener pode ser adicionado em 016.1+ se demanda real-time aparecer (e.g., abandoned cart trigger reativo a `INSERT INTO messages`).
- **ADR-006** agent-as-data — Phase 2 trigger config materializada como `tenants.yaml triggers.*` ao inves de `agents.config_jsonb`. Razao: triggers sao per-tenant (multi-agent), nao per-agent.
- **ADR-015** noisy-neighbor — circuit breaker do epic 014 reusado para send_template path. Sem novo breaker.
- **ADR-016** agent-runtime-safety — hard limits aplicam ao send_template (60s timeout, 3 retries). Cooldown anti-spam adicional adress **risk #4 vision** (ban WhatsApp).
- **ADR-018** data-retention-lgpd — SAR cascadeia `trigger_events` via `customer_id` (FK existing). Retention 90d via cron existente do epic 006.
- **ADR-027** admin-tables-no-rls — `public.trigger_events` herda carve-out (admin-only, append-only).
- **ADR-028** fire-and-forget — Prometheus emit + LGPD SAR fanout sao fire-and-forget. Send_template **nao** e fire-and-forget (orquestrador precisa do veredicto Meta para audit).
- **ADR-029** cost-pricing-constant — `cost_usd_estimated` em `trigger_events` deriva de pricing constant table (template = R$0.10 default; override per-template em `templates.*`).
- **ADR-040** autonomous-resolution-heuristic — proactive triggers que produzem inbound subsequente do cliente NAO contam para `auto_resolved=TRUE` (heuristica A condicao (a): `ai_active` permanece true). Triggers que sao mute-causing (e.g., proativo recebido + cliente pede humano) seguem fluxo handoff normal.

Dependencias externas:

- **WhatsApp Business templates pre-approved** — operador cadastra via Meta Business Manager. Time tipico de approval: 24-48h por template.
- **`pyyaml`** + **`ruamel.yaml`** — ja deps do projeto (epic 014 admin write-back). Reusa.
- **Sem outras deps novas.**

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Mecanismo de source | **Cron-only em v1** — periodic task lifespan (15s cadence, `pg_try_advisory_lock(hashtext('triggers_engine_cron'))` singleton). Pattern epic 010/011. PG NOTIFY listener adiado para 016.1+ quando demanda real-time aparecer. | Q1-A; ADR-049 novo; ADR-004 deferred |
| 2 | Trigger definition storage | **`tenants.yaml triggers.*` blocks** — array por tenant, cada item declara `id`, `type`, `enabled`, `match`, `template_ref`, `cooldown_hours`, `lookahead_hours`. Hot reload <60s via config_poller existente. Zero infra nova. | Q2-A; ADR-049; pattern epic 010/013/014 |
| 3 | Template catalog | **`tenants.yaml templates.*` blocks** — per-tenant pre-approved Meta templates. Schema: `name, language, components[], approval_id, cost_usd`. Manual ops cadastra apos approval Meta Business Manager. Auto-sync via Graph API adiado para 016.1+. | Q3-A; ADR-050 novo |
| 4 | Cooldown granularity | **Per `(tenant, customer, trigger_id)` cooldown (default 24h)** + **global daily cap per `(tenant, customer)`** (default 3 proativos/dia, override per-tenant em `tenants.yaml triggers.daily_cap_per_customer`). Redis state com TTL apropriado. | Q4-A; anti-spam + anti-ban risk #4 |
| 5 | Admin UI scope | **YAML-only config + history viewer read-only**. History viewer = lista de execucoes recentes filtravel por tenant/customer/trigger/status + drill-down em row mostra payload completo + erro detalhado. Editor de config form-based vira 016.1+. | Q5-B |
| 6 | Trigger types pre-built v1 | **3 types**: (i) `time_before_scheduled_event` (X horas antes de `customers.scheduled_event_at` — coluna nova opcional); (ii) `time_after_conversation_closed` (X horas apos `conversations.closed_at`); (iii) `time_after_last_inbound` (X horas apos `messages.created_at` ultima inbound — caso abandoned cart). Engine generico aceita `type: custom` em 016.1+. | Q6-A; ADR-049 |
| 7 | Persistence | Nova tabela `public.trigger_events` (admin-only carve-out ADR-027). Schema: `id UUID PK, tenant_id, customer_id, trigger_id TEXT, template_name TEXT, fired_at TIMESTAMPTZ, sent_at TIMESTAMPTZ NULL, status TEXT CHECK ('queued','sent','failed','skipped','rejected'), error TEXT NULL, cost_usd_estimated NUMERIC(10,4), payload JSONB`. Index `(tenant_id, fired_at DESC)` + `(customer_id, fired_at DESC)`. Append-only, retention 90d. | ADR-027 reaffirmed |
| 8 | Send path | Novo metodo `EvolutionProvider.send_template(template_name, language, components)` chamando `POST /message/sendTemplate/{instance}`. Decorado com breaker (epic 014) + warm-up cap (epic 014). Cost tracked via Phoenix span attr `trigger.cost_usd_estimated` + persisted em `trigger_events.cost_usd_estimated`. | epic 014 reaffirmed |
| 9 | Failure handling | **Template rejection** (Meta bounces 4xx) → log + skip + counter `trigger_template_rejected_total{reason}` + alert critical 1min via Slack. **Sem retry** (templates immutable; rejection e config issue). **Network error / 5xx** → retry 3x backoff (ADR-016) → se persistir, status=failed + alert. | ADR-016 reaffirmed; epic 014 alert pattern |
| 10 | Cooldown enforcement | Antes de fire, cron consulta Redis: `cooldown:{tenant}:{customer}:{trigger_id}` (TTL = `cooldown_hours * 3600`) + `daily_cap:{tenant}:{customer}:{date}` (counter, TTL 26h). Hit cooldown → status=skipped + counter `trigger_cooldown_blocked_total`. Hit cap → status=skipped + counter `trigger_daily_cap_blocked_total`. | Q4-A implementation |
| 11 | LGPD compliance | Opt-in herdado (cliente que mandou ≥1 msg = consentido por servico — pattern existente epic 005). SAR cascadeia `trigger_events` via `customer_id` (FK CASCADE para `customers`). Retention 90d via cron epic 006 estendido. | ADR-018 reaffirmed |
| 12 | Cost monitoring | Gauge Prometheus `trigger_cost_today_usd{tenant}` derivado de `SUM(cost_usd_estimated) FROM trigger_events WHERE fired_at::date = CURRENT_DATE`. Alert rule (epic 014): `trigger_cost_today_usd > 50` per tenant → warning 5min. Calibracao inicial conservadora; ajusta apos producao. | epic 014 alert pattern |
| 13 | Cardinality | Labels Prometheus: `tenant` (≤100), `trigger_id` (≤20 per tenant ≤2000 total), `status` (≤5), `reason` (≤10), `template_name` (≤50 per tenant ≤5000 total). Total <50K series. Lint no startup. | epic 014 reaffirmed |
| 14 | Eval impact | Triggers introduzem proactive msgs que podem influenciar `auto_resolved` metric (epic 011). Em ADR-040 condicao (a) — `ai_active` permanece true durante toda a conversa — e satisfeita mesmo se proativo trigger gerar inbound resposta. **Observa-se pos-rollout** sem acao automatica em v1. | ADR-040 reaffirmed |
| 15 | Trigger schema YAML | ```yaml\ntriggers:\n  daily_cap_per_customer: 3\n  enabled: true\n  list:\n    - id: ariel_match_reminder\n      type: time_before_scheduled_event\n      enabled: true\n      lookahead_hours: 1\n      cooldown_hours: 24\n      template_ref: match_reminder_pt\n      match:\n        intent_filter: any\n        agent_id_filter: any\n``` | ADR-049 schema concrete |
| 16 | Template schema YAML | ```yaml\ntemplates:\n  match_reminder_pt:\n    name: ariel_match_reminder\n    language: pt_BR\n    components:\n      - type: body\n        parameters:\n          - type: text\n            ref: '{customer.name}'\n          - type: text\n            ref: '{customer.scheduled_event_at | format_time}'\n    approval_id: 'meta_approval_xyz123'\n    cost_usd: 0.0085\n``` | ADR-050 schema concrete |
| 17 | Match parameter rendering | Template parameters declarados via path-like syntax (`{customer.name}`, `{customer.scheduled_event_at | format_time}`). Renderer Jinja-like sandboxed (ja existe via epic 015 PR-A). Filters builtin: `format_time`, `format_date`, `truncate`, `default`. Sem code execution. | epic 015 reaffirmed |
| 18 | Customers table extension | Migration: `ALTER TABLE customers ADD COLUMN scheduled_event_at TIMESTAMPTZ NULL`. Permite Ariel cadastrar "proximo jogo do cliente" via API admin (`PATCH /admin/customers/{id}`). Default NULL = trigger `time_before_scheduled_event` skip esse customer. | minimo invasivo |
| 19 | Trigger executor module | Novo `apps/api/prosauai/triggers/`: `engine.py` (matcher dispatcher), `matchers.py` (3 match types), `scheduler.py` (cron periodic task), `events.py` (persist `trigger_events`), `cooldown.py` (Redis ops). Pattern espelha `prosauai/handoff/`. | novo modulo |
| 20 | Send orchestration | Cron tick: (1) Read `tenants.yaml triggers.list` per tenant; (2) Per trigger, run matcher returning candidate customer_ids; (3) Per customer, check cooldown + daily cap; (4) Render template parameters; (5) Insert `trigger_events` row status=queued; (6) Call `provider.send_template()`; (7) Update row status=sent OR failed; (8) Emit Prometheus + structlog; (9) Update Redis cooldown + cap counters. | ADR-049 |
| 21 | Idempotencia | Cron pode rodar mais de 1x sem duplicate sends. Antes do send, verifica `trigger_events` existing row por `(tenant, customer, trigger_id, lookahead_window_iso)` — se existe com status `sent OR queued`, skip + log. Window ISO = `{trigger_id}:{customer}:{fired_at::date}`. | ADR-049 |
| 22 | Match conditions v1 | Cada match suporta: `intent_filter` (lista de intents permitidas), `agent_id_filter` (lista de agent_ids permitidos), `min_message_count` (filtra customers com >= N msgs), `consent_required` (default true — checa opt-in registrado). v1 nao suporta SQL custom; tudo declarativo. | ADR-049 |
| 23 | Observability | 5 series Prometheus via facade: `trigger_executions_total{tenant, trigger_id, status}`, `trigger_template_sent_total{tenant, trigger_id, template_name}`, `trigger_skipped_total{tenant, trigger_id, reason}`, `trigger_cooldown_blocked_total{tenant, trigger_id}`, `trigger_template_rejected_total{tenant, template_name, reason}`. Logs structlog: `tenant_id, customer_id, trigger_id, template_name, status, error, cost_usd_estimated`. | epic 014 dep |
| 24 | OTel baggage | Span novo `trigger.cron.tick` (root) com children `trigger.match`, `trigger.cooldown_check`, `trigger.send`. Trace correlation via Phoenix com `tenant_id, customer_id, trigger_id`. | epic 002 reaffirmed |
| 25 | Admin history viewer | `GET /admin/triggers/events?tenant=X&trigger_id=Y&customer_id=Z&status=W&from=DT&to=DT` paginado. Renderiza tabela com row drilldown (modal mostra payload completo + cost + erro detalhado). Reusa pattern epic 008 trace explorer. | Q5-B implementation |
| 26 | Backend endpoint | `GET /admin/triggers/events` no admin API com query params + cursor pagination. Cache Redis 30s nao aplica (audit trail tem que ser fresh). | Q5-B implementation |
| 27 | Rollout | Ariel **agente-piloto novo** (nao migrar agentes existentes) com 1 trigger ativo (`ariel_match_reminder`). Shadow 3d (`enabled: false` no trigger mas matcher executa + persiste `trigger_events.status='dry_run'` sem send) → flip para `enabled: true` se taxa de match esta no esperado. ResenhAI fica para 016.1+ apos validacao Ariel. | epic 010/011/015 pattern |
| 28 | Sample size guard | Matcher v1: hard cap 100 customers per trigger per tick. Acima disso → log warn + processa primeiros 100 (sorted by `customers.created_at`). Anti-tsunami quando trigger config errado captura demais. | safety net |
| 29 | Drift detection | Blueprint glossario tem `Trigger` + `Cooldown` mas section 3 (Folder Structure) nao lista `triggers/` package. Anote para reverse-reconcile pos-promocao. | drift detectado |
| 30 | Cost overrun alert | Alert rule new (Prom): `trigger_cost_today_usd{tenant} > 50` 5min → warning. Calibrado conservador para v1; ajusta apos 30d producao. Tenant alem de R$50/dia em proativos sinaliza config errado OU campanha intencional (operador pode silenciar via Alertmanager). | epic 014 alert pattern |

## Resolved Gray Areas

Decisoes tomadas durante este epic-context (2026-04-26, modo `--draft`):

1. **Mecanismo de source (Q1)** — Cron-only em v1. Todos os use cases v1 sao scheduled/timed. PG NOTIFY listener (ADR-004) adiado para 016.1+ quando demanda real-time aparecer.

2. **Trigger definition storage (Q2)** — `tenants.yaml triggers.*` blocks. Pattern consolidado em 4 epics (010 helpdesk, 013 integrations, 014 warmup, 015 nfr override). Hot reload <60s.

3. **Template catalog (Q3)** — `tenants.yaml templates.*` blocks. Manual ops cadastra IDs Meta. Auto-sync via Graph API adiado.

4. **Cooldown granularity (Q4)** — Per `(tenant, customer, trigger_id)` cooldown + global daily cap per customer. Anti-spam + anti-ban risk #4 mitigation.

5. **Admin UI scope (Q5)** — YAML-only config + history viewer read-only. Editor de config vira 016.1+. History viewer e must (auditabilidade + LGPD).

6. **Trigger types v1 (Q6)** — 3 pre-built (`time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`) + escape hatch `custom` em 016.1+. Cobre 80% use cases roadmap.

7. **Persistence (sem pergunta)** — Nova tabela `public.trigger_events` admin-only ADR-027 carve-out. Audit trail completo.

8. **Send path (sem pergunta)** — Novo metodo `EvolutionProvider.send_template()` com breaker + warm-up cap do epic 014.

9. **Failure handling (sem pergunta)** — Template rejection → skip + alert (sem retry, immutable). Network error → retry 3x + handoff via epic 010.

10. **Cost monitoring (sem pergunta)** — Gauge Prometheus + alert rule (epic 014) > R$50/dia/tenant.

## Applicable Constraints

**Do blueprint** ([engineering/blueprint.md](../../engineering/blueprint.md)):

- Python 3.12, FastAPI, asyncpg, redis[hiredis], structlog, opentelemetry, httpx, jinja2 (sandboxed). **Sem novas deps externas.**
- NFR Q1 (p95 <3s) — triggers sao **outbound proativos**, nao impactam pipeline inbound (pull-based via cron). Send_template adiciona ~500ms ao envio mas nao afeta NFR Q1.
- NFR Q2 (uptime 99.5%) — cron tem pg advisory lock singleton, sem dep externa nova.
- NFR Q4 (safety bypass <1%) — templates pre-approved Meta + sandwich pattern nao aplica (templates sao puros, sem injection user-controlled).
- ADR-006 — Phase 2 trigger config materializada via `tenants.yaml`.
- ADR-015 — circuit breaker do epic 014 reusado.
- ADR-016 — hard limits aplicam ao send_template.
- ADR-017 — credentials Evolution ja em `tenants.yaml`. Sem mudanca.
- ADR-018 — SAR + retention aplicados a `trigger_events`.
- ADR-027 — `trigger_events` admin-only carve-out.
- ADR-028 — fire-and-forget para Prom + LGPD fanout. Send_template e syncrono.
- ADR-029 — pricing constant.
- ADR-040 — proactive triggers nao quebram heuristica `auto_resolved`.

**Do epic 010** (handoff pattern reusado):

- Scheduler periodic task lifespan + advisory lock singleton + cadence configuravel.
- structlog facade.

**Do epic 014** (quality + breaker):

- Send_template integra com breaker per `(tenant, phone_number_id)`.
- Warm-up cap aplica ao send_template (1000/dia default).
- Prometheus + Alertmanager containers.
- Cardinality control rigoroso.

**Do epic 011** (eval pattern):

- Eval per-trigger output (LLM-as-judge) adiado para 016.1+.
- Reference-less metrics aplicaveis (Toxicity em template body) em 016.1+.

**Do epic 008** (admin pattern):

- pool_admin BYPASSRLS para queries cross-tenant.
- Trace explorer pattern reusado para history viewer.

## Suggested Approach

**2 PRs sequenciais** mergeaveis em `develop`. Cada PR atras de feature flag (`triggers.enabled: false` per-tenant default) — risco zero em prod.

### PR-A (Sem 1) — Engine + persistence + cooldown (sem send real)

Backend foundation. Sem features user-facing. Tudo unit-tested.

- Migration: `CREATE TABLE public.trigger_events (...)` + index + `ALTER TABLE customers ADD COLUMN scheduled_event_at TIMESTAMPTZ NULL`.
- `apps/api/prosauai/triggers/models.py`: Pydantic models — `TriggerConfig`, `TriggerType enum`, `TriggerMatch`, `TriggerEvent`, `TemplateConfig`.
- `apps/api/prosauai/triggers/matchers.py`: 3 matchers — `match_time_before_scheduled_event`, `match_time_after_conversation_closed`, `match_time_after_last_inbound`. Cada um retorna `list[CustomerMatch]`.
- `apps/api/prosauai/triggers/cooldown.py`: Redis ops — `check_cooldown`, `set_cooldown`, `check_daily_cap`, `increment_daily_cap`.
- `apps/api/prosauai/triggers/scheduler.py`: periodic task lifespan + advisory lock + 15s cadence.
- `apps/api/prosauai/triggers/engine.py`: orchestrator — read `tenants.yaml`, per trigger run matcher, per match check cooldown/cap, persist `trigger_events` (status=`dry_run` em PR-A).
- `apps/api/prosauai/triggers/template_renderer.py`: Jinja-like parameter rendering reusando renderer epic 015.
- `apps/api/prosauai/triggers/events.py`: persist `trigger_events` row + emit Prometheus + structlog.
- Unit tests: matchers contra fixtures, cooldown logic, daily cap, idempotencia, Pydantic validation `tenants.yaml`.

Gate: `pytest` verde; smoke test — Ariel `tenants.yaml` com 1 trigger configurado; cron tick produz row `trigger_events` status='dry_run'; cooldown bloqueia 2a tentativa; daily cap bloqueia 4o trigger.

### PR-B (Sem 2) — send_template + admin + Ariel rollout

End-to-end real send + observabilidade.

- `apps/api/prosauai/channels/outbound/evolution.py`: novo metodo `send_template(template_name, language, components)` chamando Evolution `/message/sendTemplate/{instance}`. Decorado com breaker (epic 014) + warm-up cap (epic 014).
- `apps/api/prosauai/triggers/engine.py`: PR-B wires send_template no orchestrator (status=`queued` → `sent`/`failed`/`rejected`).
- 5 series Prometheus + 2 alert rules em `config/rules/triggers.yml`.
- `apps/api/prosauai/api/admin/triggers.py`: `GET /admin/triggers/events` paginado + filtros + drill-down.
- `contracts/openapi.yaml`: novos paths + types regenerados via `pnpm gen:api`.
- `apps/admin/app/(dashboard)/triggers/page.tsx`: history viewer (lista filtravel + drill-down modal).
- Ariel rollout: cadastra template `ariel_match_reminder` em Meta Business Manager (operador) → adiciona em `tenants.yaml` → adiciona trigger `ariel_match_reminder` → shadow 3d (`enabled: false` no trigger mas matcher executa em dry-run) → flip para `enabled: true` se match rate esperado.
- Documentacao runbook em `apps/api/prosauai/triggers/RUNBOOK.md`.

Gate: Ariel envia 1 template real para 1 cliente teste; admin history viewer mostra row sent; cooldown bloqueia 2a tentativa <24h; daily cap bloqueia 4o trigger.

### Cut-line execucao

| Cenario | Acao |
|---------|------|
| Sem 1 estourar (>5d) | PR-A entrega so engine + persistence sem cooldown logic. PR-B comeca com tarefa adicional. |
| Sem 2 estourar (>5d, parte 1: send_template Evolution complica) | Send_template vira 016.1. PR-B entrega so admin history viewer (consultando dry-runs do PR-A). |
| Sem 2 estourar (>5d, parte 2: admin history viewer estoura) | Admin viewer vira 016.1. Send_template + Prometheus ficam em 016. Operador consulta `trigger_events` via SQL. |
| Tudo no prazo | ResenhAI rollout em 016.1 (observa Ariel 7d antes). |

## Riscos especificos desta epic

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Trigger config errado causa tsunami de templates (>1000 customers em 1 tick) | Alto (custo + ban) | Media | Hard cap 100 customers/trigger/tick. Cooldown global per customer (max 3/dia). Cost alert >R$50/dia/tenant. |
| Template rejection rate alto (Meta config invalida) | Medio | Alta (config inicial) | Counter `trigger_template_rejected_total` + alert critical 1min Slack. Operador corrige + redeploy template Meta. |
| Cron tick lento (matcher full table scan) | Medio | Media | Indexes em `customers.scheduled_event_at`, `conversations.closed_at`, `messages.created_at` (todos ja existem ou sao adicionados em PR-A). Hard cap 100 customers garante tick <2s. |
| Cooldown Redis perdido (Redis restart) | Medio | Baixa | Trigger_events tem timestamp + idempotencia hash — re-tick valida via SELECT. Redis perda apenas reseta cooldown (envio duplo se exatamente no momento de restart e config errada). |
| Customer scheduled_event_at sem timezone normalization | Medio | Media | Coluna TIMESTAMPTZ obriga TZ explicito. Matcher usa `NOW() AT TIME ZONE 'UTC' + INTERVAL` consistente. Test fixtures cobrem casos com TZ diferentes. |
| Evolution `/sendTemplate` semantica de components surpreende | Medio | Alta | PR-B comeca com smoke test isolado em template aprovado de teste. Documentacao runbook lista pegadinhas conhecidas. |
| LGPD opt-in nao registrado para customer pre-existing | Alto | Baixa | Default consent_required=true em match. Customer sem record de consent → trigger skip + counter `trigger_consent_missing_total`. Operador audita pre-rollout. |
| Trigger conflict com mute em handoff (epic 010) | Medio | Baixa | Cron consulta `conversations.ai_active=true` + `handoff_events` antes de fire — customer mute → trigger skip status='skipped_handoff'. |
| Cost gauge atrasa por agregacao SQL (>1s) | Baixo | Baixa | Cache Redis 30s no endpoint admin. Prometheus gauge atualizado por cron 1min separado. |
| Trigger events table cresce sem retention cron | Medio | Baixa | Retention cron epic 006 estendido para `trigger_events` (90d). PR-A inclui ALTER cron. |

## Anti-objetivos (out of scope)

- **PG LISTEN/NOTIFY listener** — adiado para 016.1+ se demanda real-time aparecer. v1 cron-only.
- **Custom trigger types** — engine generico aceita custom em 016.1+. v1 ships com 3 pre-built.
- **Auto-sync templates Meta Graph API** — manual ops em v1. Auto-sync vira 016.1+.
- **Admin form-based editor de config** — YAML-only em v1. Editor vira 016.1+.
- **Eval per-trigger output** (LLM-as-judge se template adequado) — adiado para 016.1+ apos baseline 30d.
- **A/B testing per template** — comparacao template variantes adia 016.X.
- **Schedule absoluto** (e.g., "todo dia as 9h") — v1 so suporta relative time (X horas antes/apos evento). Cron-style absoluto vira 016.1+.
- **Multi-step trigger** (e.g., trigger A → wait 24h → trigger B se nao respondeu) — vira flows engine separado em epic dedicado.
- **Self-service tenant-facing trigger config** — Pace controla catalogo em v1. Self-service via Tenant Self-Admin (epic 017 dep).
- **Per-customer custom variables** alem das builtin (`{customer.name}`, `{customer.scheduled_event_at}`) — adicionar custom JSONB em 016.1+ se demanda.
- **Trigger result attribution** (este trigger gerou X conversoes/leads) — analytics avancado fica em 016.X+.

---

> **Proximo passo (apos promocao via `/madruga:epic-context prosauai 016` sem `--draft`)**: `/speckit.specify prosauai 016-trigger-engine` para spec formal a partir desta pitch + delta review se mudou algo entre 2026-04-26 e a promocao.
