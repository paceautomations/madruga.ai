---
id: "014"
title: "Alerting + WhatsApp Quality — Prometheus self-hosted + quality monitoring dual-path + per-number breaker + warm-up cap + admin Saude tab"
slug: 014-alerting-whatsapp-quality
appetite: "2 semanas"
status: drafted
priority: P2
depends_on: ["006-production-readiness"]
created: 2026-04-26
updated: 2026-04-26
---

# Epic 014 — Alerting + WhatsApp Quality

> **DRAFT** — planejado em sequencia apos 013 (Agent Tools v2). Promocao via `/madruga:epic-context prosauai 014` (sem `--draft`) faz delta review e cria branch.

## Problema

A [vision](../../business/vision.md#L118) lista **"Ban de numero WhatsApp"** como **risco #4 (probabilidade Media, impacto Alto)** com mitigacao explicita: *"Quality score monitoring, opt-in rigoroso, rate limiting, warm-up."* Hoje (pos epic 010 + epic 013 drafted) **nada disso esta implementado**:

1. **Nao ha alerting**. O modulo `prosauai/observability/metrics.py` (epic 010) e uma **facade structlog**: emite eventos `event=metric` com `metric_name/metric_type/value/labels`, mas o proprio docstring confirma: *"a shipping layer can filter on event=metric and export to Prometheus / Phoenix without changing the application code."* Essa shipping layer **nunca foi construida**. Logs viram metricas no Pace log aggregator, mas nao ha Prometheus, sem Alertmanager, sem alertas. Qualquer regressao p95, qualquer spike de erro, qualquer breaker abrindo — operador descobre por acaso ou via log grep.

2. **Nenhum sinal de quality_rating WhatsApp** entra no sistema. Meta Cloud Graph API expoe `quality_rating` (`GREEN/YELLOW/RED`) e `messaging_limit_tier` (`TIER_1K → TIER_UNLIMITED`) por `phone_number_id`, mas o `MetaCloudAdapter` (epic 009/[ADR-035](../../decisions/ADR-035-meta-cloud-adapter-integration.md)) so usa Graph API para **resolver media URLs**. Quality fica invisivel ate o numero ser banido.

3. **Tenants em Evolution API** (Ariel + ResenhAI hoje, 2 numeros reais em prod) nao tem **nenhum** sinal de quality. Evolution e wrapper sobre Meta Cloud mas **nao expoe quality_rating** na sua API REST. Sem caminho alternativo, esses tenants ficam descobertos.

4. **Sem warm-up de numero**. Numero novo no WhatsApp Business Platform comeca em `TIER_1K` (1000 conversas iniciadas/24h), sobe automatico se quality continuar GREEN. Hoje, qualquer tenant novo pode estourar tier no dia 1 com volume de teste — Meta penaliza com downgrade ou ban temporario. Risco real para o **gate de producao do 1o cliente externo** (objetivo declarado da epic no [roadmap](../../planning/roadmap.md#L93)).

5. **Sem circuit breaker outbound**. Patterns existentes (ADR-015 per-tenant inbound, epic 010 per-`(tenant,helpdesk)`, epic 013 drafted per-`(tenant,integration)`) **nao cobrem o caminho de envio de mensagem WhatsApp**. Se Meta retornar `RATE_LIMIT_HIT` ou `BLOCKED_USER` em sequencia, o `EvolutionProvider.send_text` continua tentando — auto-DoS. ADR-015 §"Anti-pattern: retry loop em 429" ja documenta o problema; epic 014 entrega o controle.

6. **Admin nao ve nada disso**. Epic 008 entregou 8 abas operacionais mas a "Overview" tem so um card de "system health" hardcoded em verde. Sem aba de Saude/Metricas, ops monitora via log SSH no VPS.

Epic 014 entrega o **gate de producao para 1o cliente externo** ([milestone](../../planning/roadmap.md#L154)) construindo:

- **Prometheus + Alertmanager self-hosted** no `docker-compose.prod.yml` existente (consistencia com Phoenix, Infisical, retention-cron pattern epic 006).
- **Migration controlada** da facade structlog para `prometheus_client` lib + endpoint `/metrics` scraped.
- **Dual-path quality monitoring**: Meta Cloud Graph API poll (authoritative quando tenant em Meta direct) + Evolution-hosted inferred (proxy via error rate local + read-receipt ratio).
- **Send circuit breaker per `(tenant, phone_number_id)`** integrado no `EvolutionProvider.send_text`.
- **Warm-up cap manual** via `tenants.yaml warmup.daily_cap_per_number` (auto-warmup vira 014.1+).
- **Admin nova aba "Saude"**: alertas firing + sparklines key metrics + lista de numeros com quality_rating.

## Appetite

**2 semanas** (1 dev full-time, sequencia de 2 PRs mergeaveis em `develop`, reversivel via `alerting.enabled: false` global em <60s + warm-up via `tenants.yaml`).

| Semana | Entrega | Gate |
|--------|---------|------|
| Sem 1 | Prometheus + Alertmanager containers no `docker-compose.prod.yml` + `prometheus_client` lib + endpoint `/metrics` exporta 100% das series existentes (handoff, eval, tool, pipeline) + 6 alert rules base + Slack incoming webhook | Smoke: `curl /metrics` retorna 200 com series; rule `up{job='prosauai-api'} == 0` dispara em 1min via Slack |
| Sem 2 | Quality poller (Meta Cloud Graph API per tenant Meta-direct) + quality inferred (Evolution local error rate + read receipts) + send breaker per `(tenant, phone_number_id)` + warm-up cap enforcement em `EvolutionProvider.send_text` + admin nova aba "Saude" (firing alerts + 6 sparklines + lista numeros) + 4 alert rules WhatsApp-specific | Ariel: aba Saude renderiza com dados reais; alert `WhatsAppQualityRed` simulado dispara via Slack; breaker abre em 50 send errors/5min; cap throttla envio acima de 1000/dia |

**Cut-line dura**: se semana 1 estourar (improvavel — Prometheus container deploy + `prometheus_client` lib sao trilhas batidas), **PR-B vira 014.1**. PR-A entrega so monitoring + base alerts (sem WhatsApp-specific). Valor user-facing critico (visibilidade de regressao p95) sobrevive.

**Cut-line mole**: se semana 2 estourar (provavel risco: Meta Cloud Graph API auth complica com service account ou rate limits surpreendem), **admin "Saude" tab vira 014.1**. Quality poll + breaker + warm-up cap (logica core do anti-ban) ficam em 014. Operador consulta Prometheus query API direto via terminal no curto prazo.

## Dependencies

Prerrequisitos (todos `shipped`):

- **006-production-readiness** — `docker-compose.prod.yml` ja consolidado (Phoenix Postgres, Netdata, retention-cron). Adicionar `prometheus` + `alertmanager` services reusa pattern. Log rotation existente cobre Prometheus storage (TSDB local em volume).
- **008-admin-evolution** — admin Next.js 15 + pool_admin BYPASSRLS + TanStack Query v5 + shadcn/ui + Recharts. Nova aba "Saude" reusa pattern existente; nao precisa de nova autenticacao ou DB.
- **009-channel-ingestion-and-content-processing** — `MetaCloudAdapter` ja resolve `phone_number_id` por tenant (em `tenants.yaml` block `meta_cloud.phone_number_id`). Quality poller le essa mesma config.
- **010-handoff-engine-inbox** — facade `prosauai/observability/metrics.py` ja emite metricas via structlog. Endpoint `/metrics` so precisa instrumentar `prometheus_client.Counter/Histogram/Gauge` em paralelo (dual-emit) durante migration.
- **005-conversation-core** — `EvolutionProvider.send_text` e o ponto unico de envio outbound. Wrap com breaker + warm-up cap em <50 LOC. Padrao herdado da `ChatwootAdapter` do epic 010 (breaker como dependency injection).

Pre-requisitos que **nao bloqueiam**:

- **011-evals (em curso)** — `eval_*` series Prometheus serao expostas pelo `/metrics` automaticamente ao migrar para `prometheus_client`. Zero coupling de timing.
- **013-agent-tools-v2 (drafted)** — `tool_*` series idem. Quando 013 mergar, alert rules para `tool_breaker_open_total > 0` ja funcionam sem mudanca em 014.
- **Meta Business Manager onboarding ResenhAI** (em onboarding por ADR-035 §Contexto) — quality poll Meta-direct funciona quando finalizado. Ate la, ResenhAI fica em path Evolution-inferred (Q3-A dual path cobre).

ADRs novos desta epic (draft — promocao pode ajustar):

- **ADR-045** — Prometheus self-hosted alerting stack (deploy + scrape strategy + Alertmanager routing)
- **ADR-046** — WhatsApp quality monitoring dual-path (Meta Cloud Graph API poll + Evolution local inference)

ADRs estendidos (nao substituidos):

- **ADR-015** noisy-neighbor — circuit breaker estendido para outbound: per `(tenant, phone_number_id)` para WhatsApp send. Mantem inbound rate limit + LLM spend cap + queue priority + per-tenant breaker existentes.
- **ADR-020** phoenix-observability — Phoenix continua para tracing (drill-down trace_id). Prometheus assume metricas + alerting. Boundaries claros: Phoenix = traces, Prometheus = metrics, structlog = logs estruturados.
- **ADR-027** admin-tables-no-rls — sem novas tabelas admin-only. Aba "Saude" consome Prometheus query API + `tenants.yaml` runtime.
- **ADR-028** fire-and-forget — quality poller usa pattern fire-and-forget (poll falha → log warn, sem bloquear nada).

Dependencias externas:

- **`prometheus-client`** (Python lib) — single dep nova, ~50KB, zero runtime overhead em produccao.
- **`prom/prometheus:v2.55`** + **`prom/alertmanager:v0.27`** — containers oficiais.
- **Meta Cloud Graph API** — endpoint `/v19.0/{phone-number-id}` ja referenciado pelo `MetaCloudAdapter`. Rate limit ~200/hora — facilmente acomoda 1 poll/15min por tenant.
- **Slack incoming webhook** — 1 channel `#prosauai-alerts`, configuracao via `ALERTMANAGER_SLACK_WEBHOOK_URL` env var.
- **Sem nova dep no admin frontend** — Recharts + shadcn/ui ja na stack epic 007/008.

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Stack alerting | **Prometheus + Alertmanager self-hosted** no `docker-compose.prod.yml`. 2 services novos (`prometheus`, `alertmanager`) reusam log rotation pattern epic 006. TSDB local em volume `./data/prometheus` com retention 15 dias. Grafana Cloud / managed providers ficam em 014.1+ se VPS apertar. | Q1-A; ADR-045 novo |
| 2 | Metrics exposure | **`prometheus_client` Python lib** + endpoint `GET /metrics` no FastAPI app, scraped pelo Prometheus. Migration controlada: structlog facade existente continua emitindo em paralelo (dual-emit) durante semana 1; cleanup em 014.1+ quando confianca for total. | Q2-A; ADR-045 |
| 3 | Quality monitoring source | **Dual path**: (i) Meta Cloud direct → poller chama Graph API `GET /v19.0/{phone-number-id}?fields=quality_rating,messaging_limit_tier` a cada 15min, autoriza com `META_CLOUD_ACCESS_TOKEN` per tenant ja em `tenants.yaml`; (ii) Evolution-hosted → quality **inferida de error rate local** (5xx Evolution, `RATE_LIMIT_HIT`, ratio read receipts/sent). Mesma metrica `whatsapp_phone_quality{tenant, phone_number_id, source}` com label `source=meta_cloud\|evolution_inferred`. | Q3-A; ADR-046 novo |
| 4 | Warm-up | **Cap manual configuravel** em `tenants.yaml warmup.daily_cap_per_number` (default `1000` — alinhado com Meta TIER_1K). Hot reload <60s via config_poller existente. Auto-warmup baseado em quality + idade do numero adiado para 014.1+ quando 5+ tenants externos justificarem. | Q4-B |
| 5 | Send breaker | **Per `(tenant, phone_number_id)`** — pattern epic 010/013. Abre quando: (a) `error_rate >5%` em janela 5min OU (b) `quality_rating == RED` OU (c) `messaging_limit_tier == TIER_1K` apos 14d (downgrade Meta — sinal de quality grave). Half-open apos 5min testa com 1 envio. DLQ Redis `dlq:whatsapp:{tenant}:{phone_number_id}` para mensagens bloqueadas. | Q5-A; ADR-015 extended |
| 6 | Cut-line v1 | **Tudo em 2 semanas** (Q6-B): monitoring + alerting + breaker + warm-up cap + admin Saude tab. Cut-line mole: admin tab vira 014.1 se sem 2 estourar; quality poll + breaker (anti-ban core) ficam em 014. | Q6-B |
| 7 | Admin "Saude" tab | **Nova aba** no admin (9a aba no menu lateral). Reusa Recharts + shadcn/ui. Conteudo v1: (a) lista de alerts firing (Alertmanager API `/api/v2/alerts`); (b) 6 sparklines: pipeline p95, send error rate global, eval coverage %, handoff rate, tool breaker count, autonomous resolution %; (c) lista de numeros WhatsApp ativos com quality_rating + tier + cap usado today. Read-only — actions ficam para 014.1+. | user-added 2026-04-26 |
| 8 | Backend endpoint | `GET /admin/metrics/health` no admin API: proxy para Prometheus query API (`/api/v1/query` + `/api/v1/query_range`) + Alertmanager API (`/api/v2/alerts`) + read direto de `tenants.yaml` para warm-up caps. Cache Redis 30s para reduzir scrape pressure. | derivado #7 |
| 9 | Failure handling poller | **Fire-and-forget per task** — quality poller falha em 1 tenant → log warn + emit `whatsapp_quality_poll_errors_total{tenant, source}`. Nao para o cron geral. ADR-028 pattern. | ADR-028 reaffirmed |
| 10 | Failure handling Prometheus | **App nao depende de Prometheus** — scrape pull, sem dep no startup. Prometheus down → metricas perdidas mas tudo continua funcionando. App expoe `/metrics` em-process; Prometheus liga e scrape quando voltar. | ADR-045 |
| 11 | Failure handling Alertmanager | **Alertmanager down** → Prometheus continua avaliando rules, alerta fica em estado `pending` ate Alertmanager voltar. Sem perda permanente. Slack webhook tem retry build-in. | ADR-045 |
| 12 | Alert routing | **Slack incoming webhook** para channel `#prosauai-alerts`. Email ops fallback (configurado mas opcional). PagerDuty fica para 1o cliente externo (014.1+). 3 severidades: `critical` (instant), `warning` (5min group), `info` (1h group). | sem pergunta — recomendacao base |
| 13 | Alert rules base (sem 1) | 6 rules: (a) `up{job=...} == 0` (service down) → critical; (b) `pipeline_p95_ms > 3000` 10min → warning (NFR Q1); (c) `eval_score_below_threshold_total` increase 24h → warning (NFR Q10); (d) `tool_breaker_open_total > 0` 1min → critical (epic 013 dep); (e) `helpdesk_breaker_open > 0` 1min → critical (epic 010 dep); (f) `handoff_events_total{event_type='breaker_open'}` rate > 0 → critical. | ADR-045 |
| 14 | Alert rules WhatsApp (sem 2) | 4 rules: (a) `whatsapp_phone_quality{quality='RED'} == 1` 5min → critical; (b) `whatsapp_phone_quality{quality='YELLOW'} == 1` 30min → warning; (c) `whatsapp_send_breaker_open == 1` 1min → critical; (d) `whatsapp_send_throttled_total` rate > 0 5min → info (warm-up cap hit). | ADR-046 |
| 15 | Quality poll cadence | **15min interval**, cron singleton via `pg_try_advisory_lock(hashtext('whatsapp_quality_poll'))` (pattern epic 010 + 011). Poll todos os tenants com `meta_cloud.phone_number_id` configurado. Backoff 60s on Meta API 429; circuit breaker apos 3 erros consecutivos. | epic 010/011 pattern |
| 16 | Quality inferred derivation | Janela 5min: `quality_inferred = "RED" if error_rate > 0.10 else "YELLOW" if error_rate > 0.05 OR read_receipt_ratio < 0.50 else "GREEN"`. Read receipt ratio so calculado se >= 20 mensagens enviadas no periodo (evita ruido). Erros incluem 4xx Evolution + 5xx + RATE_LIMIT_HIT. | ADR-046 |
| 17 | Warm-up cap enforcement | `EvolutionProvider.send_text` consulta Redis counter `warmup:{tenant}:{phone_number_id}:{date}` antes de enviar. Acima do cap → `WhatsAppCapExceeded` exception → orquestrador escala para handoff via epic 010 OU mensagem amigavel "Voltarei em alguns minutos" (configuravel). Counter TTL 26h (margem timezone). | Q4-B implementation |
| 18 | Phone numbers source | Nao cria nova tabela — `phone_number_id` por tenant fica em `tenants.yaml` (Meta Cloud) ou e derivado do instance name (Evolution). Lista de numeros para "Saude" tab e construida em runtime via leitura do TenantStore. | Q3-A consequencia |
| 19 | Migration metrics legacy | Eventos `event=metric` existentes (handoff, eval) **continuam emitindo em paralelo** durante semana 1. Em paralelo, novo modulo `prosauai/observability/prom.py` registra `prometheus_client.Counter/Histogram/Gauge` no startup e ProsaUAI emite via dois caminhos. Cleanup em 014.1+ apos validar Prometheus produz mesmas series que log aggregator. Zero downtime. | Q2-A migration plan |
| 20 | Endpoint `/metrics` security | Endpoint exposto SEM auth (Prometheus scrape pattern), bound apenas em rede interna Docker (sem `ports:` exposing). Acesso externo via firewall rule, nao via app. | ADR-045 |
| 21 | TSDB retention | **15 dias** (~150MB para volume estimado: 50 series × 1 sample/15s × 15d). Retencao curta intencional — alertas avaliam janelas de horas/dias, nao historico longo. Para historico: Phoenix (traces) + admin DB (eval_scores 30/90d). | ADR-045 |
| 22 | Cardinality control | Labels com cardinalidade alta proibidos: `customer_phone`, `message_id`, `trace_id` nao viram label. `tenant_id` (max 20-100) + `phone_number_id` (max ~50) + `metric_name` aceitaveis. Lint via `prometheus_client` validator no startup + CI check de cardinalidade. | ADR-045 |
| 23 | Sparklines `/admin/metrics/health` | 6 series fixas v1: pipeline_p95, send_error_rate, eval_coverage_percent, handoff_rate, tool_breaker_count, autonomous_resolution_percent. Janela: 24h, step 1min. Cache Redis 30s. Recharts `<LineChart>` reusado do epic 008. | #7 implementation |
| 24 | Alerts list `/admin/metrics/health` | Alertmanager API `GET /api/v2/alerts` retorna firing + active. Renderiza com badge severity (Recharts/shadcn `Badge`) + timestamp + link para runbook (`runbook_url` annotation). Acoes (silence/ack) ficam para 014.1+. | #7 implementation |
| 25 | Phone numbers list `/admin/metrics/health` | Tabela com colunas: tenant, phone_number_id, source (meta_cloud/evolution_inferred), quality_rating, messaging_limit_tier, sent_today, cap, % usado. Refresh on-demand (botao). | #7 implementation |
| 26 | Schema strict de envio | `EvolutionProvider.send_text` ja tem schema. Adicionar param opcional `phone_number_id` (deriva de instance name se nao passado). Breaker decoration via decorator `@with_send_breaker(tenant, phone_number_id)`. | minimo invasivo |
| 27 | Idempotencia send | **Inalterada** — `EvolutionProvider` ja gera `idempotency_key` para mensagens fire-and-forget (epic 010 T080). Breaker abre antes do send → mensagem nao perde idempotencia. | epic 010 reaffirmed |
| 28 | Observabilidade meta | Novas series: `whatsapp_phone_quality{tenant, phone_number_id, source, quality}` (gauge 0/1 per quality value), `whatsapp_phone_messaging_tier{tenant, phone_number_id}` (gauge enum), `whatsapp_send_total{tenant, phone_number_id, status}`, `whatsapp_send_throttled_total{tenant, phone_number_id, reason='warmup_cap'\|'breaker_open'}`, `whatsapp_send_breaker_open{tenant, phone_number_id}`, `whatsapp_quality_poll_total{tenant, source, status}`, `whatsapp_quality_poll_errors_total{tenant, source, error_code}`. | ADR-046 |
| 29 | OTel baggage | Span ja existente `pipeline.send_out` ganha attrs `whatsapp.phone_number_id`, `whatsapp.quality_rating`, `whatsapp.tier`. Trace correlation com Prometheus via `tenant_id` + `trace_id` (Phoenix). | epic 002 reaffirmed |
| 30 | Rollout | **Ariel sem 2: feature flag `alerting.enabled: true` + `whatsapp.quality_monitoring: true`** desde dia 1 (zero risco — pull-based, fire-and-forget). Send breaker entra em `shadow` (loga decisao mas nao bloqueia) por 3d antes de flip para `enforce`. Warm-up cap entra em `enforce` direto (cap default 1000/dia ja generoso para Ariel). ResenhAI segue 7d depois Ariel. | epic 010/011 pattern |

## Resolved Gray Areas

Decisoes tomadas durante este epic-context (2026-04-26, modo `--draft`):

1. **Stack alerting (Q1)** — Prometheus + Alertmanager self-hosted no `docker-compose.prod.yml`. Reusa pattern Phoenix/Infisical/retention-cron. Migracao para Grafana Cloud em 014.1+ se VPS apertar (sem premissa de migracao agora).

2. **Metrics exposure (Q2)** — `prometheus_client` lib + endpoint `/metrics`. Migration controlada via dual-emit (structlog facade existente + Prometheus em paralelo durante semana 1).

3. **Quality monitoring source (Q3)** — Dual path: Meta Cloud direct (poll Graph API) + Evolution-hosted (inferido de error rate local + read receipts). Sem dual, Ariel + ResenhAI ficariam descobertos hoje.

4. **Warm-up (Q4)** — Cap manual em `tenants.yaml`. Auto-warmup adiado para 014.1+ quando 5+ tenants externos justificarem.

5. **Send breaker scope (Q5)** — Per `(tenant, phone_number_id)`. Quality e per-numero; um numero saudavel nao deve ser bloqueado por degradacao de outro do mesmo tenant.

6. **Cut-line v1 (Q6)** — Tudo em 2 semanas (B). Cut-line mole: admin Saude tab vira 014.1 se sem 2 estourar; quality poll + breaker (anti-ban core) ficam em 014.

7. **Admin Saude tab (user-added 2026-04-26)** — Incluida no escopo de PR-B. v1 read-only com firing alerts + 6 sparklines + lista numeros. Acoes (silence/ack) e tooling avancado ficam para 014.1+.

8. **Alert routing (sem pergunta)** — Slack incoming webhook + email fallback. PagerDuty para 1o cliente externo (014.1+).

9. **Failure handling app vs Prometheus (sem pergunta)** — App nao depende de Prometheus (pull-based). Quality poller fire-and-forget. Alertmanager down nao perde alertas (Prom estado `pending`).

10. **Cardinality control (sem pergunta)** — Labels alta cardinalidade proibidos (sem `customer_phone`, `message_id`, `trace_id`). CI check de cardinalidade. Pre-empta blow-up de TSDB que mata Prometheus production.

## Applicable Constraints

**Do blueprint** ([engineering/blueprint.md](../../engineering/blueprint.md)):

- Python 3.12, FastAPI, asyncpg, redis[hiredis], structlog, opentelemetry, httpx — **so 1 lib nova** (`prometheus-client`).
- NFR Q1 (p95 <3s) — `/metrics` endpoint scraped tem latencia <50ms (proven em prod outras stacks). Quality poller e isolado (cron singleton, fire-and-forget). Send breaker check e Redis O(1) (~1ms).
- NFR Q2 (uptime 99.5%) — Prometheus self-hosted nao impacta (pull-based). App degrada graciosamente sem Prometheus.
- NFR Q5 (Starter throughput 100 RPM) + NFR Q6 (Business 500 RPM) — warm-up cap default 1000/dia esta acima de Starter (100 RPM × 60min × 24h = 144K teorico, mas realista <5K/dia). Cap kicks in so para clientes com volume real.
- ADR-015 — circuit breaker estendido para outbound per `(tenant, phone_number_id)` sem alterar inbound rate limit, LLM cap, queue priority.
- ADR-016 — sem novo schema de tools; warm-up nao usa LLM.
- ADR-020 — Phoenix continua para tracing; Prometheus assume metricas + alerting. Boundaries claros.
- ADR-027 — sem novas tabelas admin-only.
- ADR-028 — fire-and-forget para quality poll. Send breaker check **nao** e fire-and-forget (envio precisa do veredicto).

**Do epic 010** (helpdesk pattern reusado):

- Config_poller hot reload <60s para `tenants.yaml warmup.*` blocks.
- Circuit breaker pattern (closed/open/half-open) reusado para send breaker.

**Do epic 008** (admin pattern reusado):

- pool_admin BYPASSRLS para queries cross-tenant (lista de numeros).
- TanStack Query v5 + Recharts + shadcn/ui sem nova dep frontend.

**Do epic 009/035** (channel pattern reusado):

- `phone_number_id` por tenant ja resolvido pelo `MetaCloudAdapter`.
- ChannelAdapter Protocol nao e tocado (epic 014 nao adiciona inbound channel).

## Suggested Approach

**2 PRs sequenciais** mergeaveis em `develop`. Cada PR atras de feature flag — risco zero em prod.

### PR-A (Sem 1) — Prometheus + Alertmanager + metrics exposure

Backend foundation. Sem alerting WhatsApp ainda. Tudo unit-tested + 1 smoke real.

- `docker-compose.prod.yml`: 2 services novos (`prometheus`, `alertmanager`) com configs `./config/prometheus.yml` + `./config/alertmanager.yml`. Volume `./data/prometheus` (TSDB).
- `apps/api/prosauai/observability/prom.py`: novo modulo. Registra `Counter`/`Histogram`/`Gauge` para todas as metricas existentes (handoff, eval, tool, pipeline). Helpers `inc_counter()`, `observe_histogram()`, `set_gauge()` espelham assinatura da facade structlog.
- `apps/api/prosauai/main.py`: monta `/metrics` route via `prometheus_client.make_asgi_app()`. Lifespan adiciona structlog facade dual-emit.
- `config/prometheus.yml`: scrape config job `prosauai-api` (interval 15s). Rules em `config/rules/base.yml` com 6 alert rules base (Decision #13).
- `config/alertmanager.yml`: route default → Slack webhook `${ALERTMANAGER_SLACK_WEBHOOK_URL}`. Severity routing (critical instant / warning 5min / info 1h).
- `apps/api/tests/unit/observability/test_prom.py`: testa registro + dual-emit + `/metrics` shape.
- `apps/api/tests/integration/observability/test_prom_scrape.py`: smoke test sobe Prometheus container, scrape, query series, valida.

Gate: `docker compose up -d prometheus alertmanager` sobe; `curl localhost:9090/-/ready` retorna 200; rule `up{job='prosauai-api'} == 0` simulada (para o app) dispara em <2min via Slack.

### PR-B (Sem 2) — WhatsApp quality + send breaker + warm-up + admin Saude

Anti-ban core + observabilidade end-user.

- `apps/api/prosauai/quality/poller.py`: `whatsapp_quality_poll_cron` periodic task no FastAPI lifespan. 15min cadence + advisory lock. Para cada tenant com `meta_cloud.phone_number_id` configurado, chama Graph API `/v19.0/{phone-number-id}?fields=quality_rating,messaging_limit_tier`. Emit gauges.
- `apps/api/prosauai/quality/inferred.py`: deriva `quality_inferred` de error rate + read receipts em janela 5min. Roda como pos-step do pipeline ou cron 1min (escolha implementacao via flag).
- `apps/api/prosauai/quality/breaker.py`: `SendBreaker` per `(tenant, phone_number_id)`. State em Redis (`breaker:whatsapp:{tenant}:{phone_number_id}` + TTL). Pattern epic 010 `prosauai/handoff/breaker.py`.
- `apps/api/prosauai/quality/warmup.py`: `WarmupCap` lookup `tenants.yaml warmup.daily_cap_per_number`. Counter Redis `warmup:{tenant}:{phone_number_id}:{date}` TTL 26h. Hit cap → `WhatsAppCapExceeded`.
- `apps/api/prosauai/channels/outbound/evolution.py`: `EvolutionProvider.send_text` decorada com `@with_send_breaker` + `WarmupCap.consume_one_or_raise()` antes do POST.
- `apps/api/prosauai/api/admin/metrics_health.py`: `GET /admin/metrics/health` proxy para Prometheus query API (`/api/v1/query_range` para sparklines, `/api/v1/query` para gauges) + Alertmanager API (`/api/v2/alerts`) + leitura runtime de `tenants.yaml`. Cache Redis 30s.
- `contracts/openapi.yaml`: novo path `/admin/metrics/health` + types regenerados via `pnpm gen:api`.
- `apps/admin/app/(dashboard)/health/page.tsx`: nova aba "Saude". 3 secoes: alerts firing, sparklines (Recharts `LineChart` × 6), tabela numeros WhatsApp. Read-only.
- `config/rules/whatsapp.yml`: 4 alert rules WhatsApp (Decision #14).
- Smoke teste: aba renderiza com dados reais; alert simulado dispara via Slack; breaker abre em fault injection (50 erros em 5min); cap throttla acima de 1000/dia.

Gate: Ariel rollout em `shadow` (3d) → `enforce`. Aba Saude funcional em browser real. Slack recebe alert simulado.

### Cut-line execucao

| Cenario | Acao |
|---------|------|
| Sem 1 estourar (>5d) | PR-A entrega so containers + `/metrics` endpoint + 3 rules base. Migration de eventos legacy fica em 014.1. |
| Sem 2 estourar (>5d, parte 1: quality poll Meta API complica) | Quality poll Meta-direct vira 014.1. PR-B entrega so quality inferred (Evolution) + breaker + warm-up + admin tab parcial (sem coluna quality_rating Meta). |
| Sem 2 estourar (>5d, parte 2: admin tab estoura por integracao Recharts/Alertmanager API) | Admin tab vira 014.1. PR-B entrega quality poll + breaker + warm-up. Operador consulta Prometheus query API direto via terminal no curto prazo. |
| Tudo no prazo | ResenhAI rollout em 014.1 (fica observando 7d apos Ariel). |

## Riscos especificos desta epic

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Cardinality blow-up: label `phone_number_id` tem >100 valores em prod (improvavel mas possivel) | Alto (Prom OOM) | Baixa | CI check valida cardinalidade no startup. Hard cap 200 series por metric. |
| Meta Cloud Graph API rate limit (200/h) sai de baixo se 50+ tenants polando | Medio | Media | Cadence 15min × 50 tenants = 200/h exato. Alerta automatico se quota >80%. Cadence dinamica per-tenant em 014.1. |
| Quality_inferred diverge muito de quality_rating Meta | Medio | Media | Shadow mode 7d compara series. Se divergencia >30%, ajusta thresholds inferidos. ADR-046 documenta calibracao. |
| Prometheus TSDB cresce alem de 150MB | Baixo | Baixa | Retention 15d enforced. Volume monitorado via Netdata (epic 006). |
| Alertmanager Slack webhook expira/rotaciona | Baixo | Baixa | Env var ja documentada em `.env.example`. Rotation via `docker compose restart alertmanager`. |
| Breaker abre falsamente em quality_inferred com poucos sends | Medio | Media | Min sample size 20 mensagens em 5min antes de avaliar. Fallback para `GREEN` se sample insuficiente. |
| Warm-up cap default 1000/dia muito baixo para Business tier real | Baixo | Baixa | Per-tenant override em `tenants.yaml`. Default conservador justifica anti-ban. |
| Migration dual-emit causa diff em metricas (legacy vs Prometheus) | Medio | Media | Sem 1 PR-A inclui smoke test que compara N samples entre log aggregator e Prom query — diff <1% aceito. |
| `prometheus_client` Python lib nao suporta multiprocess (uvicorn workers) | Medio | Media | Documentado: usar single worker em prod (ja e o caso atual) OU `prometheus_client.multiprocess` mode. Validacao em PR-A. |
| Aba Saude carrega lentamente se Prometheus query agrega series largas | Medio | Media | Cache Redis 30s + step 1min em query_range. Se persistir, PR-B move agregacao para recording rules Prometheus-side. |

## Anti-objetivos (out of scope)

- **Auto-warmup baseado em quality + idade do numero** — manual cap (Q4-B) cobre v1. Auto vira 014.1+ com 5+ tenants externos.
- **PagerDuty integration** — Slack + email cobrem ops com 1 dev FT. PagerDuty para 1o cliente externo (gate diferente).
- **Grafana dashboards** — admin Saude tab cobre v1. Grafana para 014.1+ com requisitos de drill-down complexo.
- **Anomaly detection ML** — fora do escopo. Threshold-based alerting cobre v1.
- **Tenant-facing alerts** — alertas sao ops-internos. Tenant ve quality_rating no admin Saude tab apenas (read-only). Self-service alerting fica no epic 017 (Tenant Self-Admin).
- **Outbound Meta Cloud direct** — ADR-035 ja deferiu. Send breaker funciona so via Evolution em v1.
- **Quality alert per-tenant routing** — Slack channel unico `#prosauai-alerts` em v1. Per-tenant routing fica para 014.1+ se ops escalar.
- **Long-term metrics warehouse** — retention 15d em Prom. Historico longo via Phoenix (traces) + admin DB. Mimir/Thanos fora do escopo.
- **OTel Metrics SDK migration** — structlog facade + `prometheus_client` cobrem v1. Unificacao OTel fica para epic dedicado se valor justificar.
- **Silence/ack actions na admin Saude tab** — read-only v1. Actions ficam para 014.1+ se ops pedir.

---

> **Proximo passo (apos promocao via `/madruga:epic-context prosauai 014` sem `--draft`)**: `/speckit.specify prosauai 014-alerting-whatsapp-quality` para spec formal a partir desta pitch + delta review se mudou algo entre 2026-04-26 e a promocao.
