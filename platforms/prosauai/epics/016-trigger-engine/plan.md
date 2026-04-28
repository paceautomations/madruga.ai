# Implementation Plan: Trigger Engine — engine declarativo de mensagens proativas

**Branch**: `epic/prosauai/016-trigger-engine` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/016-trigger-engine/spec.md`

## Summary

Habilitar **mensagens proativas declarativas** via engine cron-driven que materializa a Phase 2 do [ADR-006 (Agent-as-Data)](../../decisions/ADR-006-agent-as-data.md) — *"IF condition THEN action configuravel"* — nunca implementada antes. Hoje a plataforma e **reactive-only**: `EvolutionProvider.send_text()` so envia em resposta a inbound; nao existe modulo `triggers/`, tabela `trigger_events`, metodo `send_template()`, nem cooldown anti-ban. Use cases concretos parados: ResenhAI lembrete de jogo manual via WhatsApp pessoal (vision §6 exemplo canonico), e-commerce abandoned cart (vision §1.2), servicos lembrete consulta (vision §1.3).

**Abordagem tecnica**: novo modulo Python `apps/api/prosauai/triggers/` (espelha `prosauai/handoff/` do epic 010) com 6 arquivos de logica + scheduler periodic task lifespan + advisory lock singleton (pattern epic 010/011/014). Engine le `tenants.yaml triggers.*` + `templates.*` blocks per tenant (hot reload <60s via `config_poller` existente), executa 3 matchers pre-built (`time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`) via `pool_tenant` (RLS per-request, ADR-003), aplica cooldown granular per `(tenant, customer, trigger_id)` + global daily cap per `(tenant, customer)` via Redis com fallback SQL, persiste em nova tabela admin-only `public.trigger_events` (ADR-027 carve-out), renderiza parametros via Jinja-like sandboxed do epic 015, e envia via novo metodo `EvolutionProvider.send_template()` decorado com circuit breaker + warm-up cap do epic 014. Admin history viewer read-only `GET /admin/triggers/events` paginado com drill-down (UI Next.js 15 reusa pattern epic 008).

**Defesas anti-ban (multi-camada)**: (a) cooldown 24h default per `(tenant, customer, trigger_id)`; (b) global daily cap 3/dia per `(tenant, customer)` override via `triggers.daily_cap_per_customer`; (c) hard cap 100 customers/trigger/tick; (d) idempotencia em 2 niveis — app-check + partial UNIQUE INDEX no banco (decisao clarify Round 2); (e) opt-out hard filter via `customers.opt_out_at` (migration nova); (f) handoff-active filter (`conversations.ai_active=false` exclui customer); (g) shadow mode `mode: dry_run` para validacao 3d antes de flip.

**Cut-line operacional**: PR-A (semana 1) entrega engine + persistence + cooldown + 3 matchers em **dry_run only** — operador valida via SQL/logs. PR-B (semana 2) entrega `send_template()` real + Prometheus + alert rules + admin history viewer + Ariel rollout shadow→live. Cut-lines duros: (i) se PR-A estourar, PR-B vira 016.1; (ii) se Evolution `/sendTemplate` semantica surpreender em PR-B, send_template vira 016.1 e PR-B entrega so admin viewer; (iii) se admin viewer estourar, vira 016.1 (operador consulta SQL). Cada cenario deixa o sistema funcional.

**Non-goals decididos no plan** (registrados em decisions.md como D-PLAN-XX):

- Nao implementar PG LISTEN/NOTIFY listener para triggers reativos a `INSERT INTO messages` — adiado para 016.1+ se demanda real-time aparecer (D-PLAN-01).
- Nao implementar trigger types `custom` (escape hatch SQL/expression) — adiado para 016.1+ apos validacao dos 3 pre-built (D-PLAN-06).
- Nao implementar auto-sync templates via Meta Graph API — operador cadastra manualmente em `tenants.yaml templates.*` apos approval Meta Business Manager (D-PLAN-07).
- Nao implementar admin form-based editor de config — YAML-only via PR no `tenants.yaml` (D-PLAN-08).
- Nao implementar eval per-trigger LLM-as-judge (template adequacy) — adiado para 016.1+ apos baseline 30d.
- Nao implementar A/B testing per template, multi-step trigger flows, schedule absoluto cron-style ("todo dia 9h"), self-service tenant-facing UI — todos 016.X+ ou epic dedicado.
- Nao implementar detector NLP automatico de STOP/SAIR — operador registra opt-out manual via `PATCH /admin/customers/{id}` (D-PLAN-09).
- Nao implementar attribution explicita inbound-apos-trigger — apenas `messages.metadata.triggered_by` record-keeping para 016.X+ analytics (FR-039).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x (frontend Next.js 15) — apenas se PR-B entrar.
**Primary Dependencies**: FastAPI ≥0.135, asyncpg ≥0.31, pydantic ≥2.12, pydantic-settings ≥2.6, redis[hiredis] ≥7.0, structlog ≥25.0, opentelemetry-sdk 1.39.x, httpx ≥0.27, jinja2 (sandboxed, ja em uso pelo epic 015), prometheus_client (epic 014). **Zero novas dependencias Python**.
**Storage**:
- PostgreSQL 15 (Supabase) — nova tabela `public.trigger_events` (ADR-027 admin-only carve-out — sem RLS) + nova coluna `public.customers.scheduled_event_at TIMESTAMPTZ NULL` + nova coluna `public.customers.opt_out_at TIMESTAMPTZ NULL` + partial UNIQUE INDEX `trigger_events_idempotency_idx` (FR-017).
- Redis 7 — chaves volateis `cooldown:{tenant}:{customer}:{trigger_id}` (TTL = `cooldown_hours*3600`) + `daily_cap:{tenant}:{customer}:{YYYY-MM-DD}` (counter, TTL 26h). Recoverable via SQL fallback (FR-015).
- Migrations via `dbmate` em `apps/api/db/migrations/`.

**Testing**: pytest + pytest-asyncio + testcontainers-postgres + fakeredis (suite existente em `apps/api/tests/`); `respx` para mock Evolution API. Frontend: pnpm test + Playwright (apenas se PR-B/admin viewer entrar).
**Target Platform**: Linux server (FastAPI uvicorn em container `apps/api`); browser desktop para admin viewer.
**Project Type**: Web service (backend) — extensao do conversation pipeline existente (trigger e o primeiro caminho **outbound proativo** independente de inbound).
**Performance Goals**:
- Cron tick p95 ≤ **2s** com hard cap 100 customers/trigger × N triggers ativos (SC-004 hard gate).
- `send_template` adiciona ~500ms ao envio mas nao afeta NFR Q1 (p95 inbound <3s) — paths sao independentes.
- Endpoint `GET /admin/triggers/events` p95 < **300ms** com cursor pagination + index `(tenant_id, fired_at DESC)` (SC-006).
- Hot reload de `tenants.yaml` aplicada em **≤60s** (SC-010, herdado do `config_poller` existente).

**Constraints**:
- **Backward compatibility absoluta**: tenants/agentes sem `triggers.list` continuam reactive-only — zero deploy, zero regressao em pipeline inbound.
- Hard cap **100 customers/trigger/tick** (FR-011).
- Cooldown default **24h** per `(tenant, customer, trigger_id)`; global daily cap default **3** per `(tenant, customer)` (FR-012/FR-013).
- Cardinality Prometheus combinada **<50K series** com lint no startup (FR-033).
- LGPD SAR via `ON DELETE CASCADE` em `trigger_events.customer_id` (FR-019, hard delete v1; anonimizacao 016.1+ se DPO requerer — `[VALIDAR]`).
- Retention `trigger_events` **90d** via cron epic 006 estendido (FR-018).
- Idempotencia 2 niveis: app-check antes do send + partial UNIQUE INDEX `WHERE status IN ('sent','queued')` (FR-017).
- Stuck-detection: rows `status='queued' AND fired_at < NOW() - 5min AND retry_count < 3` reprocessadas via UPDATE in-place (FR-041).
- Snapshot atomico de config no inicio do tick — modificacoes durante tick nao afetam tick atual (FR-043).
- Branch `epic/prosauai/016-trigger-engine` ja existe — checkout direto.

**Scale/Scope**:
- 6 tenants ativos hoje, ~5 k mensagens inbound/dia/tenant.
- Adocao esperada: Ariel rollout v1 em 1 tenant com 1 trigger ativo (`ariel_match_reminder`); ResenhAI rollout em 016.1+ apos validacao 7d Ariel.
- Volume estimado v1: 3 triggers ativos × 100 customers/tick × 4 ticks/min × 60min × 24h × 30d = ~13M rows/mes/tenant **mas 99% sao skipped** (cooldown + cap + handoff filter) — apenas ~10K `sent`/mes/tenant. Index `(tenant_id, fired_at DESC)` suporta facilmente >100M rows. `[VALIDAR]` em load test.
- ~3 endpoints novos no admin: `GET /admin/triggers/events` + extension em `agents` listing (incluir `triggers_count`).
- Storage adicional: `trigger_events` ~1MB/dia/tenant em rows sent + ~10MB/dia/tenant em rows skipped (95% skipped quando cooldown/cap saturam) → ~330MB/mes/tenant × 6 tenants × 90d retention ≈ ~180GB cumulativos. Cabe folgado no orcamento Supabase.

## Constitution Check

*GATE: passa antes do Phase 0 research. Re-check apos Phase 1 design.*

| Principio | Avaliacao | Justificativa |
|-----------|-----------|---------------|
| I — Pragmatismo & Simplicidade | ✅ | Reusa tudo: pattern handoff scheduler (epic 010), pattern cooldown Redis (epic 010), pattern admin viewer (epic 008), Jinja renderer (epic 015), circuit breaker + warm-up cap (epic 014), pool_tenant RLS (epic 003), `config_poller` (epic 010/013/014). Zero deps novas. Cron-only em v1 (sem PG NOTIFY) — escolha consciente. 3 matchers pre-built — sem custom escape hatch v1. |
| II — Automate repetitive | ✅ | Reusa `prosauai/handoff/scheduler.py` pattern integralmente; `EvolutionProvider` ganha 1 metodo novo (`send_template`) com mesma estrutura de `send_text`; admin viewer reusa pattern trace explorer (epic 008); migrations via `dbmate` existing; Prometheus facade (epic 014) sem novo lib. |
| III — Knowledge structured | ✅ | `decisions.md` semeado pelo epic-context (30 itens 2026-04-26) + 5 atualizacoes do clarify Round 2 (2026-04-28) sera enriquecido com D-PLAN-01..D-PLAN-12 (cron-only, sub_steps storage como JSONB column, sem custom types, etc). Cross-reference para ADR-006/015/016/018/027/028/040 + 2 ADRs novos drafted (ADR-049 Trigger Engine, ADR-050 Template Catalog). |
| IV — Fast action | ✅ | 2 PRs sequenciais; PR-A (engine + persistence + cooldown em dry_run only) e ~5d; PR-B (send_template + Prometheus + admin viewer + Ariel rollout) e ~5d. Cada PR deixa sistema funcional + reversivel via `triggers.enabled: false` per-tenant em <60s. |
| V — Alternativas & trade-offs | ✅ | `research.md` (Phase 0) compara: (R1) cron-only vs PG NOTIFY listener vs hibrido; (R2) `tenants.yaml` blocks vs `triggers` table dedicada; (R3) cooldown Redis-only vs SQL-only vs hibrido com fallback; (R4) idempotencia app-check vs DB UNIQUE vs hibrido; (R5) admin viewer cursor pagination vs offset; (R6) stuck-detection nova-row vs UPDATE in-place; (R7) `trigger_events` carve-out admin vs RLS per-tenant. |
| VI — Brutal honesty | ✅ | Plan reconhece publicamente: (a) cron-only em v1 e **deliberada simplificacao** — abandoned cart fica menos responsivo (max 15s lag) que PG NOTIFY daria, mas v1 ships antes; (b) ADR-006 Phase 2 nunca foi implementado apesar de ADR aprovado — 016 entrega; (c) opt-out detector NLP fica em 016.1+ — operador precisa registrar manual em v1 (gap LGPD documentado); (d) hard delete LGPD via CASCADE remove evidencia per-customer (`[VALIDAR]` DPO). |
| VII — TDD | ✅ | Testes em 3 camadas: (a) unit puro (`matchers.py`, `cooldown.py`, `template_renderer.py` isolados com fixtures + fakeredis); (b) integration (`engine.py` end-to-end com testcontainers + asyncpg + RLS); (c) regression (suite existente passa intacta — gate de merge). PR-A escreve testes ANTES da integracao com scheduler. PR-B escreve test de chaos (Redis restart) antes de send_template real. |
| VIII — Collaborative decisions | ✅ | 30 decisoes do epic-context + 5 do clarify Round 2 expostas em `decisions.md`. 12 D-PLAN novas exposta para revisao (cron-only, idempotencia hibrida, stuck UPDATE in-place, etc). |
| IX — Observability | ✅ | 5 series Prometheus + gauge cost + 2 alert rules + spans OTel root `trigger.cron.tick` + children `trigger.match`/`trigger.cooldown_check`/`trigger.send` + structlog logs com `correlation_id` (trace_id) + `tenant_id` + `customer_id` + `trigger_id` + `template_name` + `status` + `cost_usd_estimated`. Failure de send gera `level=error` + `error_type` + `meta_response_status`. |

**Violacoes**: nenhuma. `Complexity Tracking` vazio.

### Post-Phase-1 re-check

| Risco | Status |
|-------|--------|
| Trigger config errado causa tsunami (>100 customers/tick) | Mitigado: hard cap 100 (FR-011) + cooldown 24h + daily cap 3 + cost alert R$50/dia. Test integracao verifica `count` exato apos cap. |
| Template rejection rate alto (Meta config invalida) | Mitigado: alert critical 1min via Slack/Telegram; counter `trigger_template_rejected_total{reason}`; sem retry (template immutable). |
| Cron tick lento (matcher full table scan) | Mitigado: indexes em `customers.scheduled_event_at`, `conversations.closed_at`, `messages.created_at` adicionados em PR-A; query plans validados via EXPLAIN. Hard cap 100 garante tick <2s. |
| Cooldown Redis perdido (Redis restart) | Mitigado: SQL fallback consultando `trigger_events` antes de qualquer send pos-restart (FR-015). Idempotencia DB partial UNIQUE INDEX (FR-017) protege contra duplicate. |
| Customer scheduled_event_at sem TZ | Mitigado: `TIMESTAMPTZ` obriga TZ explicito; matcher usa `NOW() + INTERVAL`; test fixtures cobrem TZs diferentes. |
| Evolution `/sendTemplate` semantica surpreende | Mitigado: PR-B comeca com smoke test isolado em template aprovado de teste antes de integrar com engine; runbook documenta pegadinhas conhecidas; cut-line: send_template vira 016.1 se >2d para corrigir. |
| LGPD opt-in nao registrado para customer pre-existing | Mitigado: filtro `consent_required` default true via `customers.opt_out_at IS NULL`; counter `trigger_skipped_total{reason="opt_out"}`; operador audita pre-rollout. |
| Trigger conflict com handoff (epic 010) | Mitigado: matcher INNER JOIN com `conversations` filtrando `WHERE ai_active=true`; counter `trigger_skipped_handoff_total`; test integracao verifica. |
| Cost gauge inflar tabela `trigger_events` em SUM | Mitigado: gauge atualizado a cada 60s por lifespan task separada com advisory lock proprio (FR-030); query usa index `(tenant_id, fired_at::date)` parcial; max 60s lag aceitavel para alert >R$50/dia em 5min. |
| Trigger events table cresce sem retention | Mitigado: PR-A inclui ALTER cron retention 90d (epic 006 estendido); test verifica delete de rows >90d. |
| Frontend Next.js admin viewer atrasar PR-B | Mitigado: cut-line — viewer vira 016.1; operador consulta `trigger_events` via SQL durante curto prazo; backend endpoint sempre shipa em PR-B (zero risco). |
| Race condition entre matcher concorrente | Mitigado: `pg_try_advisory_lock(hashtext('triggers_engine_cron'))` singleton garante 1 tick ativo por vez; partial UNIQUE INDEX como defense-in-depth captura race em multi-replica. |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/016-trigger-engine/
├── plan.md                  # Este arquivo
├── spec.md                  # Feature specification (pos-clarify, 5 + 5 decisoes autonomas)
├── pitch.md                 # Shape Up pitch (epic-context — referencia)
├── decisions.md             # Capturas L2 (30 + 5, semente do epic-context, enriquecido durante implement)
├── research.md              # Phase 0 — R1..R7 alternativas com pros/cons
├── data-model.md            # Phase 1 — DDL trigger_events + customers ALTER + ER + cap policy
├── quickstart.md            # Phase 1 — setup local + validacao US1..US5
├── contracts/
│   └── openapi.yaml         # Phase 1 — endpoints admin (PR-B)
├── checklists/
│   └── requirements.md      # pre-existente (gerado pelo specify)
└── tasks.md                 # Phase 2 — gerado por /speckit.tasks (NAO criado por este skill)
```

### Source Code (repository — `paceautomations/prosauai`, branch `epic/prosauai/016-trigger-engine`)

```text
apps/api/                                                  # backend FastAPI (existente)
├── db/migrations/                                         # dbmate
│   ├── 20260601000020_create_trigger_events.sql          # NEW — tabela admin-only + indexes + UNIQUE parcial
│   ├── 20260601000021_alter_customers_add_scheduled_event_at.sql  # NEW
│   ├── 20260601000022_alter_customers_add_opt_out_at.sql # NEW
│   └── 20260601000023_extend_retention_cron_trigger_events.sql  # NEW — adiciona DELETE >90d
├── prosauai/
│   ├── main.py                                            # MODIFIED — registrar router admin/triggers + 2 lifespan tasks (engine + cost_gauge)
│   ├── triggers/                                          # NEW dir (espelha prosauai/handoff/)
│   │   ├── __init__.py
│   │   ├── models.py                                      # NEW — Pydantic models (TriggerConfig, TriggerType enum, TriggerMatch, TemplateConfig, TriggerEventRecord)
│   │   ├── matchers.py                                    # NEW — 3 matchers + helpers (sorted by created_at, hard cap 100)
│   │   ├── cooldown.py                                    # NEW — Redis ops (check/set cooldown, check/inc daily_cap, SQL fallback)
│   │   ├── template_renderer.py                           # NEW — wrapper Jinja sandboxed reuso epic 015 + filters builtin
│   │   ├── engine.py                                      # NEW — orchestrator (read config → matcher → cooldown → render → persist → send → metrics)
│   │   ├── events.py                                      # NEW — repository trigger_events (insert, query, stuck-detection update)
│   │   ├── scheduler.py                                   # NEW — periodic task lifespan + advisory lock + 15s cadence
│   │   ├── cost_gauge.py                                  # NEW — periodic task separado + advisory lock proprio + 60s cadence
│   │   └── RUNBOOK.md                                     # NEW — operacao ops (cadastrar template, debug, kill-switch)
│   ├── channels/outbound/
│   │   └── evolution.py                                   # MODIFIED — adicionar metodo send_template(template_name, language, components, recipient_phone)
│   ├── config/
│   │   └── tenants_loader.py                              # MODIFIED — extender Pydantic models para triggers/templates blocks + cross-ref validation startup
│   ├── customers/
│   │   └── repository.py                                  # MODIFIED — endpoint admin PATCH /admin/customers/{id} aceita scheduled_event_at + opt_out_at
│   ├── admin/
│   │   ├── triggers.py                                    # NEW — GET /admin/triggers/events (cursor paginado + filtros)
│   │   ├── schemas/
│   │   │   └── triggers.py                                # NEW — Pydantic models p/ response (TriggerEventResponse, TriggerEventDetail)
│   │   ├── customers.py                                   # MODIFIED — PATCH suporta novos campos
│   │   └── agents.py                                      # MODIFIED — listing inclui triggers_count (so se PR-B entrar)
│   ├── observability/
│   │   ├── metrics.py                                     # MODIFIED — registrar 5 counters + 1 gauge + cardinality lint
│   │   └── otel.py                                        # MODIFIED — registrar span names trigger.*
│   ├── retention/
│   │   └── cron.py                                        # MODIFIED — ALTER cron epic 006 incluir trigger_events 90d
│   └── tests/  (em apps/api/tests/)
│       ├── triggers/
│       │   ├── test_matchers_unit.py                      # NEW — fixtures customers + assert match results
│       │   ├── test_cooldown_unit.py                      # NEW — fakeredis + cooldown/cap logic
│       │   ├── test_template_renderer_unit.py             # NEW — filters builtin + sandbox safety
│       │   ├── test_engine_unit.py                        # NEW — orchestrator mocks (matcher + send_template)
│       │   ├── test_models_unit.py                        # NEW — Pydantic validation TriggerConfig/TemplateConfig + cross-ref
│       │   ├── test_events_repo_pg.py                     # NEW (integration) — testcontainers + RLS-bypass admin pool + idempotency UNIQUE
│       │   ├── test_engine_pg.py                          # NEW (integration) — end-to-end fixtures + mock evolution
│       │   ├── test_send_template_evolution.py            # NEW — respx mock + breaker integration
│       │   ├── test_chaos_redis_restart.py                # NEW — chaos: clear redis state mid-tick + verify zero duplicate sent
│       │   ├── test_admin_triggers_events.py              # NEW (integration) — endpoint pagination + filters
│       │   └── test_idempotency_db_race.py                # NEW — concurrent INSERT triggers UniqueViolation handling
│       └── conftest.py                                    # MODIFIED — fixtures triggers_yaml, mock_evolution, fakeredis
│
config/rules/
├── triggers.yml                                            # NEW — 2 alert rules Prometheus (cost overrun + rejection rate)

apps/admin/                                                 # Next.js 15 (PR-B)
├── app/(dashboard)/triggers/
│   └── page.tsx                                            # NEW — history viewer (lista filtravel + drill-down modal)
├── components/
│   └── trigger-event-detail.tsx                            # NEW — modal payload completo + cost + erro detalhado
└── lib/api/triggers.ts                                     # NEW — TanStack Query hooks (cursor pagination)

contracts/
└── openapi.yaml                                            # MODIFIED — adicionar /admin/triggers/events + types regenerados via pnpm gen:api

tenants.yaml                                                # MODIFIED (per-tenant) — adicionar triggers.* + templates.* blocks (Ariel-only em PR-B)
```

**Structure Decision**: Single web-service repo (`paceautomations/prosauai`). Modulo `prosauai/triggers/` espelha `prosauai/handoff/` do epic 010 — mesma anatomia (models / scheduler / engine / events / cooldown), mesmas convenções de logging/OTel. Integra com `EvolutionProvider` (epic 005) via novo metodo `send_template`. Frontend (Next.js 15 em `apps/admin/`) entra em PR-B como aba `/triggers` que reusa shadcn/ui + TanStack Query do epic 008.

## Implementation Phases (Shape Up — sequenciamento por valor)

> Cada PR deixa o sistema funcional e mergeable. Reversivel via `triggers.enabled: false` per-tenant em `tenants.yaml` (hot reload <60s). Tenants/agentes sem `triggers.list` continuam reactive-only — gate de regressao zero.

### PR-A — Engine + persistence + cooldown em dry_run only (US1+US5 backbone, ~5d)

**Objetivo**: backend foundation sem features user-facing. Tudo unit-tested + 1 smoke E2E em dry_run.

#### A.1 Migrations (~2h)

- `20260601000020_create_trigger_events.sql` — tabela exatamente como em `data-model.md`:
  ```sql
  CREATE TABLE public.trigger_events (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id UUID NOT NULL REFERENCES public.tenants(id),
      customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
      trigger_id TEXT NOT NULL,
      template_name TEXT NOT NULL,
      fired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      sent_at TIMESTAMPTZ,
      status TEXT NOT NULL CHECK (status IN ('queued','sent','failed','skipped','rejected','dry_run')),
      error TEXT,
      cost_usd_estimated NUMERIC(10,4),
      payload JSONB,
      retry_count INT NOT NULL DEFAULT 0
  );
  -- ADR-027: admin-only, sem RLS
  CREATE INDEX idx_trigger_events_tenant_fired ON public.trigger_events (tenant_id, fired_at DESC);
  CREATE INDEX idx_trigger_events_customer_fired ON public.trigger_events (customer_id, fired_at DESC);
  CREATE UNIQUE INDEX trigger_events_idempotency_idx
      ON public.trigger_events (tenant_id, customer_id, trigger_id, (fired_at::date))
      WHERE status IN ('sent', 'queued');
  ```
- `20260601000021_alter_customers_add_scheduled_event_at.sql` — `ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS scheduled_event_at TIMESTAMPTZ;` + `CREATE INDEX IF NOT EXISTS idx_customers_scheduled_event ON public.customers (tenant_id, scheduled_event_at) WHERE scheduled_event_at IS NOT NULL;` (partial — anti-bloat).
- `20260601000022_alter_customers_add_opt_out_at.sql` — `ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS opt_out_at TIMESTAMPTZ;` (sem index — uso e WHERE filter, nao SELECT scan).
- `20260601000023_extend_retention_cron_trigger_events.sql` — registra `trigger_events` na cron retention do epic 006 (DELETE WHERE fired_at < NOW() - INTERVAL '90 days').

**Gate**: migrations idempotentes (`make test:migrations`); rollback testado.

#### A.2 Pydantic models + tenants.yaml schema (~4h)

- `prosauai/triggers/models.py` — Pydantic v2 models:
  ```python
  class TriggerType(StrEnum):
      time_before_scheduled_event = "time_before_scheduled_event"
      time_after_conversation_closed = "time_after_conversation_closed"
      time_after_last_inbound = "time_after_last_inbound"
      # custom = "custom"  # 016.1+

  class TriggerMatch(BaseModel):
      intent_filter: list[str] | Literal["any"] = "any"
      agent_id_filter: list[UUID] | Literal["any"] = "any"
      min_message_count: int = 0
      consent_required: bool = True

  class TriggerMode(StrEnum):
      live = "live"
      dry_run = "dry_run"

  class TriggerConfig(BaseModel):
      id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
      type: TriggerType
      enabled: bool = True
      mode: TriggerMode = TriggerMode.live
      lookahead_hours: int = Field(ge=0, le=168)  # max 1 semana
      cooldown_hours: int = Field(ge=1, le=720)  # min 1h, max 30d
      template_ref: str
      match: TriggerMatch = TriggerMatch()

  class TemplateComponent(BaseModel):
      type: Literal["body", "header", "footer", "button"]
      parameters: list[dict]  # passa direto p/ Meta — schema livre v1

  class TemplateConfig(BaseModel):
      name: str
      language: str = "pt_BR"
      components: list[TemplateComponent]
      approval_id: str
      cost_usd: Decimal = Field(ge=0, default=Decimal("0.0085"))

  class TenantTriggersConfig(BaseModel):
      enabled: bool = False  # default OFF per-tenant
      cadence_seconds: int = Field(ge=10, le=300, default=15)
      cost_gauge_cadence_seconds: int = Field(ge=30, le=600, default=60)
      daily_cap_per_customer: int = Field(ge=1, le=10, default=3)
      list: list[TriggerConfig] = []
  ```
- `tenants_loader.py` MODIFIED — adicionar campos `triggers: TenantTriggersConfig` + `templates: dict[str, TemplateConfig]` ao TenantSettings model.
- **Cross-reference validation no startup** (FR-042): `_validate_template_refs()` checa que toda `triggers.list[].template_ref` existe em `templates.<key>` daquele tenant. Falha rapido (servico nao sobe) se broken ref. Hot reload mantém snapshot anterior + warning + alert.
- Test `test_models_unit.py` — Pydantic validation positiva + negativa (custom type rejeitado, cooldown <1h rejeitado, template_ref orfao rejeitado).

**Gate**: Pydantic exhaustivo; cross-ref validation funciona; suite existente passa intacta.

#### A.3 Matchers (~6h)

- `prosauai/triggers/matchers.py` — 3 funcoes async:
  ```python
  async def match_time_before_scheduled_event(
      conn: asyncpg.Connection,  # pool_tenant (RLS aplica)
      trigger: TriggerConfig,
      now: datetime,
  ) -> list[CustomerMatch]:
      window_start = now
      window_end = now + timedelta(hours=trigger.lookahead_hours)
      rows = await conn.fetch("""
          SELECT id, phone_number_e164, name, scheduled_event_at, created_at
          FROM customers
          WHERE scheduled_event_at >= $1 AND scheduled_event_at < $2
            AND opt_out_at IS NULL
          ORDER BY created_at ASC
          LIMIT 100
      """, window_start, window_end)
      return [CustomerMatch.from_row(r) for r in rows]
  ```
  Idem para `match_time_after_conversation_closed` (JOIN conversations + WHERE ai_active=true filter de US3) e `match_time_after_last_inbound` (subquery latest message + JOIN conversations).
- Hard cap 100 sempre via `LIMIT 100` no SQL — defense layer 1.
- Filter `consent_required` aplica via `WHERE opt_out_at IS NULL`.
- Filter `intent_filter` / `agent_id_filter` aplica via `WHERE intent = ANY($N)` quando lista (skip clause se "any").
- Filter `min_message_count` aplica via `HAVING COUNT(messages.*) >= $N`.
- Test `test_matchers_unit.py` — fixtures de 5 customers (incluindo 1 com opt_out_at, 1 com handoff, 1 fora de janela), asserta retorno exato.

**Gate**: 100% line coverage matchers; queries verificadas via EXPLAIN (index usage).

#### A.4 Cooldown + daily cap (~4h)

- `prosauai/triggers/cooldown.py`:
  ```python
  async def check_cooldown(redis, tenant_id, customer_id, trigger_id) -> bool:
      key = f"cooldown:{tenant_id}:{customer_id}:{trigger_id}"
      return await redis.exists(key) == 1

  async def set_cooldown(redis, tenant_id, customer_id, trigger_id, hours) -> None:
      key = f"cooldown:{tenant_id}:{customer_id}:{trigger_id}"
      await redis.setex(key, hours * 3600, "1")

  async def check_daily_cap(redis, tenant_id, customer_id, cap) -> bool:
      today = datetime.now(UTC).date().isoformat()
      key = f"daily_cap:{tenant_id}:{customer_id}:{today}"
      count = await redis.get(key)
      return (int(count or 0)) >= cap

  async def increment_daily_cap(redis, tenant_id, customer_id) -> None:
      today = datetime.now(UTC).date().isoformat()
      key = f"daily_cap:{tenant_id}:{customer_id}:{today}"
      pipe = redis.pipeline()
      pipe.incr(key)
      pipe.expire(key, 26 * 3600)  # TTL 26h
      await pipe.execute()

  async def restore_state_from_sql(conn, tenant_id, since_hours=24) -> dict:
      """Pos-restart fallback. Le rows trigger_events.status='sent' das ultimas 24h
      e reconstrucao Redis state. Idempotente."""
  ```
- Test `test_cooldown_unit.py` — fakeredis + scenarios (cap exact 3, edge case 26h TTL, restore pos-restart).

**Gate**: TTL exato 26h verificado; restore_state_from_sql cobre Redis cold start.

#### A.5 Template renderer (~2h)

- `prosauai/triggers/template_renderer.py` — wrapper sobre `prosauai/conversation/jinja_sandbox.py` (epic 015):
  ```python
  def render_template_components(
      template: TemplateConfig,
      customer: CustomerMatch,
      now: datetime,
  ) -> list[dict]:
      """Renderiza parametros via Jinja sandboxed.
      Filters builtin: format_time, format_date, truncate, default."""
      env = get_sandboxed_env()  # do epic 015
      env.filters["format_time"] = lambda dt: dt.strftime("%H:%M")
      env.filters["format_date"] = lambda dt: dt.strftime("%d/%m/%Y")
      scope = {"customer": customer.model_dump(), "now": now}
      rendered_components = []
      for component in template.components:
          rendered_params = []
          for param in component.parameters:
              if param.get("type") == "text" and "ref" in param:
                  tpl = env.from_string(param["ref"])
                  rendered_params.append({"type": "text", "text": tpl.render(scope)})
              else:
                  rendered_params.append(param)
          rendered_components.append({"type": component.type, "parameters": rendered_params})
      return rendered_components
  ```
- Test `test_template_renderer_unit.py` — filters, sandbox safety (no `__import__`), missing var → `default`.

**Gate**: 0 unsafe constructs (eval, exec, __import__) — hypothesis fuzz test.

#### A.6 Events repository (~3h)

- `prosauai/triggers/events.py`:
  ```python
  async def insert_trigger_event(
      conn,  # pool_admin BYPASSRLS
      tenant_id, customer_id, trigger_id, template_name,
      status, payload, cost_usd_estimated, error=None,
  ) -> UUID:
      try:
          return await conn.fetchval("""
              INSERT INTO trigger_events
                  (tenant_id, customer_id, trigger_id, template_name, status,
                   payload, cost_usd_estimated, error, fired_at)
              VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
              RETURNING id
          """, ...)
      except UniqueViolationError:
          # FR-017 race condition handling
          return await conn.fetchval("""
              INSERT INTO trigger_events
                  (tenant_id, customer_id, trigger_id, template_name, status, error, fired_at)
              VALUES ($1, $2, $3, $4, 'skipped', 'idempotent_db_race', NOW())
              RETURNING id
          """, ...)

  async def update_status(conn, event_id, status, sent_at=None, error=None) -> None: ...

  async def find_stuck_queued(conn, max_age_minutes=5, max_retries=3) -> list[UUID]:
      """FR-041 — rows queued >5min com retry_count<3."""
      return await conn.fetch("""
          SELECT id FROM trigger_events
          WHERE status='queued'
            AND fired_at < NOW() - INTERVAL '5 minutes'
            AND retry_count < 3
          FOR UPDATE SKIP LOCKED
      """)

  async def reclaim_stuck(conn, event_id) -> bool:
      """UPDATE in-place: retry_count++, fired_at=NOW(). Atomic."""
      result = await conn.execute("""
          UPDATE trigger_events
          SET retry_count = retry_count + 1, fired_at = NOW()
          WHERE id = $1 AND retry_count < 3
      """, event_id)
      return result == "UPDATE 1"
  ```
- Test `test_events_repo_pg.py` (integration) — testcontainers; idempotency UNIQUE INDEX violation handled; stuck-detection retry up to 3.

**Gate**: pg_partman/UNIQUE constraint enforced em test concorrente.

#### A.7 Engine orchestrator (~6h)

- `prosauai/triggers/engine.py` — coracao do PR-A:
  ```python
  async def execute_tick(
      *, tenant_id, tenant_config, redis, db_admin_pool, db_tenant_pool, evolution_client,
      now, mode_override=None,
  ) -> TickResult:
      """1 tick para 1 tenant. Singleton garantido por advisory lock no scheduler."""
      if not tenant_config.triggers.enabled:
          return TickResult.skipped(reason="tenant_disabled")
      results = TickResult()
      # Snapshot atomico (FR-043)
      triggers_snapshot = list(tenant_config.triggers.list)
      templates_snapshot = dict(tenant_config.templates)

      # Stuck-detection primeiro (FR-041)
      async with db_admin_pool.acquire() as conn:
          stuck = await events.find_stuck_queued(conn)
          for event_id in stuck:
              if await events.reclaim_stuck(conn, event_id):
                  await _retry_send(...)

      for trigger in triggers_snapshot:
          if not trigger.enabled:
              continue
          template = templates_snapshot.get(trigger.template_ref)
          if not template:  # never reach if validation passed (FR-042)
              continue

          # Matcher (RLS via pool_tenant)
          async with db_tenant_pool.acquire() as conn:
              await conn.execute(f"SET LOCAL app.tenant_id = '{tenant_id}'")
              candidates = await dispatch_matcher(conn, trigger, now)

          for candidate in candidates:
              # 1. Handoff filter (FR-010)
              if candidate.ai_active is False:
                  await _record_skipped(...; reason="handoff")
                  continue
              # 2. Cooldown
              if await cooldown.check_cooldown(redis, tenant_id, candidate.id, trigger.id):
                  await _record_skipped(...; reason="cooldown")
                  continue
              # 3. Daily cap
              if await cooldown.check_daily_cap(redis, tenant_id, candidate.id, tenant_config.triggers.daily_cap_per_customer):
                  await _record_skipped(...; reason="daily_cap")
                  continue
              # 4. App-level idempotency check (FR-017 layer 1)
              if await events.exists_today(conn, tenant_id, candidate.id, trigger.id):
                  await _record_skipped(...; reason="idempotent")
                  continue
              # 5. Render
              rendered = render_template_components(template, candidate, now)
              # 6. Persist queued (or dry_run if mode override)
              effective_mode = mode_override or trigger.mode
              status = "dry_run" if effective_mode == TriggerMode.dry_run else "queued"
              event_id = await events.insert_trigger_event(...; status=status)
              if status == "dry_run":
                  results.dry_runs += 1
                  continue
              # 7. Send (PR-A: skip; PR-B: real)
              # PR-A always uses dry_run regardless — no real send
              ...
      return results
  ```
- **PR-A scope**: engine roda end-to-end ate persistencia + dry_run rows. **send_template nao e chamado em PR-A** — toda execucao em modo `dry_run` mesmo se trigger configurado com `mode: live`. PR-B remove esse override.
- Test `test_engine_unit.py` — mocks de matcher + redis + db; asserta rows criadas com status correto.

**Gate**: smoke E2E — Ariel `tenants.yaml` com 1 trigger configurado (`mode: dry_run`); cron tick produz row `trigger_events.status='dry_run'`; cooldown bloqueia 2a tentativa <24h.

#### A.8 Scheduler periodic task (~3h)

- `prosauai/triggers/scheduler.py`:
  ```python
  async def trigger_engine_loop(app: FastAPI) -> None:
      """Lifespan task. Singleton via advisory lock."""
      cadence = settings.triggers_cadence_seconds  # default 15
      lock_key = hashtext_int4("triggers_engine_cron")
      while not shutdown_event.is_set():
          start = monotonic()
          async with app.state.db_admin_pool.acquire() as conn:
              acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_key)
              if not acquired:
                  # standby — outra replica ja rodando
                  await asyncio.sleep(cadence)
                  continue
              try:
                  for tenant_id, tenant_config in get_tenants_with_triggers().items():
                      try:
                          await engine.execute_tick(...)
                      except Exception as exc:
                          logger.error("trigger_tick_failed", tenant_id=tenant_id, error=str(exc))
                          # tenant-isolated — proximo tenant continua
              finally:
                  await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
          elapsed = monotonic() - start
          await asyncio.sleep(max(0, cadence - elapsed))
  ```
- `main.py` MODIFIED — registra `trigger_engine_loop` no lifespan startup (apenas se `settings.triggers_enabled` global).
- Test integration: spin up FastAPI test instance; verify lock held in PG; verify tick interval ≤ cadence; verify shutdown clean.

**Gate**: lock visivel via `SELECT * FROM pg_locks WHERE locktype='advisory'`; ZERO parallel ticks em multi-replica test.

#### A.9 Tests + smoke (~4h)

- Fixture `mock_evolution` em `conftest.py` usando `respx` — captura POSTs em `/sendTemplate/{instance}` e retorna canned 2xx/4xx/5xx.
- Fixture `triggers_yaml` — base `tenants.yaml` com 1 tenant + 1 trigger + 1 template (Ariel match_reminder).
- Smoke test `test_engine_pg.py` — fixture customers (3) + cron tick + assert: 1 row `dry_run`, 1 row `skipped` (out of window), 1 row `skipped` (opt_out).
- Test `test_idempotency_db_race.py` — concurrent tasks INSERT mesmo trigger event; um vence (status='queued'/'dry_run'), outro captura UniqueViolation → status='skipped' reason='idempotent_db_race'.
- Test `test_chaos_redis_restart.py` — pre-condicao (Redis vazio + 5 rows trigger_events sent ha 12h); chamar `restore_state_from_sql`; asserta cooldown re-construido.

**Gate**: PR-A inteiro — `pytest -k triggers` passa; `make test` passa (zero regressao); PR mergeado em `develop` atras de feature flag `triggers_enabled=false` global.

---

### PR-B — send_template + admin viewer + Ariel rollout (US1+US2+US4 end-to-end, ~5d)

**Objetivo**: ponta-a-ponta real send + observabilidade + audit visivel. PR-B depende de PR-A merged.

#### B.1 EvolutionProvider.send_template + breaker integration (~1d)

- `prosauai/channels/outbound/evolution.py`:
  ```python
  async def send_template(
      self, *, tenant_id, phone_number_id, recipient_phone, template_name,
      language, components,
  ) -> SendTemplateResult:
      """POST /message/sendTemplate/{instance}. Decorado com breaker + warm-up cap (epic 014)."""
      with self._breaker(tenant_id, phone_number_id):
          if not self._warmup_cap_allow(tenant_id, phone_number_id):
              raise WarmupCapExceeded()
          payload = {
              "number": recipient_phone,
              "template": {
                  "name": template_name,
                  "language": {"code": language},
                  "components": components,
              },
          }
          response = await self.client.post(
              f"/message/sendTemplate/{self.instance}",
              json=payload,
              timeout=60,
          )
          if response.status_code in (400, 403, 422):  # Meta rejection
              raise TemplateRejected(reason=response.json().get("error"))
          response.raise_for_status()  # 5xx → retry via httpx-retries
          return SendTemplateResult.from_evolution(response.json())
  ```
- Smoke test isolado em template aprovado (`test_send_template_evolution.py`) usando `respx` para varios cenarios:
  - 2xx → SendTemplateResult OK
  - 4xx invalid_template → TemplateRejected
  - 5xx → retry exponential backoff (3x) via existing httpx-retries pattern
  - timeout 60s → propaga
- **Cut-line check**: se semantica de `components`/`parameters` Evolution API surpreender em mais de 8h de debug, abortar PR-B integration e shipar PR-B sem send_template (016.1+ retoma).

**Gate**: respx mocks cobrem 6 paths (success/4xx/5xx/timeout/breaker_open/warmup_cap_exceeded); breaker counter Prometheus visivel.

#### B.2 Engine wires send_template (~4h)

- `prosauai/triggers/engine.py` — remover `mode_override='dry_run'` global; agora respeita `trigger.mode`. Quando `trigger.mode == TriggerMode.live`:
  ```python
  # ... apos rendering + persist queued ...
  try:
      result = await evolution_client.send_template(
          tenant_id=tenant_id,
          phone_number_id=tenant_config.phone_number_id,
          recipient_phone=candidate.phone_number_e164,
          template_name=template.name,
          language=template.language,
          components=rendered,
      )
      await events.update_status(conn, event_id, status="sent", sent_at=now)
      await cooldown.set_cooldown(redis, tenant_id, candidate.id, trigger.id, trigger.cooldown_hours)
      await cooldown.increment_daily_cap(redis, tenant_id, candidate.id)
  except TemplateRejected as exc:
      await events.update_status(conn, event_id, status="rejected", error=str(exc))
      # alert critical 1min Slack — Prometheus counter trigger_template_rejected_total
  except (httpx.TimeoutException, httpx.NetworkError, BreakerOpen):
      await events.update_status(conn, event_id, status="failed", error=...)
  ```
- Tracking inbound: hook `messages.metadata.triggered_by` (FR-039) — quando `INSERT INTO messages` (inbound) acontecer dentro de 24h apos `trigger_events.sent_at` para mesmo customer, popula JSONB. Implementacao: subquery em `prosauai/conversation/inbound_handler.py` (no momento do persist da inbound).

**Gate**: end-to-end test_engine_pg.py com mock evolution emite real send + cooldown set; chaos test confirma idempotencia DB.

#### B.3 Prometheus metrics + cardinality lint (~4h)

- `prosauai/observability/metrics.py` MODIFIED — registrar 5 counters + 1 gauge:
  ```python
  trigger_executions_total = Counter("trigger_executions_total", "...",
      ["tenant", "trigger_id", "status"])
  trigger_template_sent_total = Counter("trigger_template_sent_total", "...",
      ["tenant", "trigger_id", "template_name"])
  trigger_skipped_total = Counter("trigger_skipped_total", "...",
      ["tenant", "trigger_id", "reason"])
  trigger_cooldown_blocked_total = Counter(...)
  trigger_template_rejected_total = Counter(...)
  trigger_cost_today_usd = Gauge("trigger_cost_today_usd", "...", ["tenant"])
  trigger_cost_gauge_errors_total = Counter(...)
  ```
- `cardinality_lint.py` startup — sum(unique combinations) por counter; abort se >50K.
- `cost_gauge.py` lifespan task separada com advisory lock proprio:
  ```python
  async def cost_gauge_loop(app):
      cadence = settings.triggers_cost_gauge_cadence_seconds  # default 60
      lock_key = hashtext_int4("triggers_cost_gauge_cron")
      while not shutdown_event.is_set():
          async with app.state.db_admin_pool.acquire() as conn:
              acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_key)
              if not acquired:
                  await asyncio.sleep(cadence); continue
              try:
                  rows = await conn.fetch("""
                      SELECT tenant_id, COALESCE(SUM(cost_usd_estimated), 0) AS total
                      FROM trigger_events
                      WHERE fired_at::date = CURRENT_DATE AND status = 'sent'
                      GROUP BY tenant_id
                  """)
                  for r in rows:
                      trigger_cost_today_usd.labels(tenant=str(r["tenant_id"])).set(float(r["total"]))
              except Exception as exc:
                  trigger_cost_gauge_errors_total.labels(reason=type(exc).__name__).inc()
                  logger.error("cost_gauge_failed", error=str(exc))
              finally:
                  await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
          await asyncio.sleep(cadence)
  ```
- `main.py` MODIFIED — registra `cost_gauge_loop` no lifespan junto com `trigger_engine_loop`.

**Gate**: cardinality lint < 50K em fixture com 100 tenants × 20 triggers cada; gauge atualizado em integration test.

#### B.4 Alert rules (~1h)

- `config/rules/triggers.yml`:
  ```yaml
  groups:
    - name: triggers
      rules:
        - alert: TriggerCostOverrun
          expr: trigger_cost_today_usd > 50
          for: 5m
          labels: { severity: warning }
          annotations:
            summary: "Tenant {{ $labels.tenant }} cost overrun: ${{ $value }}/day"
        - alert: TriggerTemplateRejectionHigh
          expr: rate(trigger_template_rejected_total[5m]) / rate(trigger_executions_total[5m]) > 0.1
          for: 1m
          labels: { severity: critical }
          annotations:
            summary: "Tenant {{ $labels.tenant }} template rejection >10% in last 5min"
  ```
- Test alert_rules.yml syntax valido via `promtool check rules`.

**Gate**: rules carregam em Alertmanager local sem erro; smoke test simulando custo agregado dispara alert.

#### B.5 Admin endpoint GET /admin/triggers/events (~6h)

- `prosauai/admin/triggers.py`:
  ```python
  @router.get("/admin/triggers/events", response_model=TriggerEventsPage)
  async def list_trigger_events(
      tenant: UUID | None = None,
      trigger_id: str | None = None,
      customer_phone: str | None = None,
      status: str | None = None,
      from_date: datetime | None = Query(None, alias="from"),
      to_date: datetime | None = Query(None, alias="to"),
      cursor: str | None = None,
      limit: int = Query(25, ge=1, le=200),
      _admin: AdminUser = Depends(require_admin),
  ) -> TriggerEventsPage:
      async with admin_pool.acquire() as conn:  # BYPASSRLS
          where = ["1=1"]
          params = []
          if tenant: where.append(f"tenant_id = ${len(params)+1}"); params.append(tenant)
          if trigger_id: where.append(f"trigger_id = ${len(params)+1}"); params.append(trigger_id)
          # ... etc
          # Cursor: base64({fired_at_iso}|{id})
          if cursor:
              fired_at, id_ = decode_cursor(cursor)
              where.append(f"(fired_at, id) < (${len(params)+1}::timestamptz, ${len(params)+2}::uuid)")
              params.extend([fired_at, id_])
          rows = await conn.fetch(
              f"SELECT ... FROM trigger_events JOIN customers c ON c.id=customer_id "
              f"WHERE {' AND '.join(where)} ORDER BY fired_at DESC, id DESC LIMIT $1",
              limit + 1, *params,
          )
          next_cursor = encode_cursor(rows[limit]) if len(rows) > limit else None
          return TriggerEventsPage(items=[map_row(r) for r in rows[:limit]], next_cursor=next_cursor)
  ```
- Schemas Pydantic em `admin/schemas/triggers.py` — `TriggerEventResponse` (lista resumida), `TriggerEventDetail` (drill-down com payload + retry_count completo).
- Auth reuso `require_admin` middleware do epic 008 (FR-035 — super-admin v1).
- Test `test_admin_triggers_events.py` — fixtures + paginacao + filtros + p95 < 300ms via 10K row fixture.

**Gate**: cursor paginacao verificada (3 paginas walk consistente); p95 < 300ms verificado em load test 10K rows.

#### B.6 Admin UI Next.js 15 (~6h)

- `apps/admin/lib/api/triggers.ts` — TanStack Query hooks com infinite cursor:
  ```typescript
  export function useTriggerEvents(filters: TriggerFilters) {
    return useInfiniteQuery({
      queryKey: ["triggers", filters],
      queryFn: ({ pageParam }) => fetcher(`/admin/triggers/events?...&cursor=${pageParam}`),
      getNextPageParam: (page) => page.next_cursor,
    });
  }
  ```
- `apps/admin/app/(dashboard)/triggers/page.tsx` — pagina:
  - Header: filtros (tenant select shadcn, trigger_id input com debounce 300ms, customer_phone input, status multiselect, date range picker).
  - Tabela: shadcn DataTable com colunas `fired_at, customer_phone, trigger_id, template_name, status badge, cost_usd, error_short, retry_count`.
  - Footer: cursor-based pagination button "Load more" + count "Showing X events" + filter reset.
  - Click row → modal `trigger-event-detail.tsx` (shadcn Dialog) com payload JSON pretty-print + cost + erro full + timestamps + retry_count + customer info card.
  - Reusa pattern admin-trace-explorer (epic 008) — mesma estetica, mesmas cores de status badge.
- `pnpm gen:api` regenera types TS de `contracts/openapi.yaml`.
- Test E2E Playwright (`apps/admin/tests/triggers.spec.ts`) — admin loga, filtra por tenant, expande row, ve modal.

**Gate**: UI carrega 25 rows em <500ms; filtros aplicam com debounce; modal renderiza payload JSON.

#### B.7 Ariel rollout shadow → live (~3h ops + 3d shadow observation)

- Operador cadastra template `ariel_match_reminder` em Meta Business Manager (PR-requisite — 24-48h approval; **se nao approved em D+1 da PR-B start, abortar B.7 e shipar PR-B sem rollout** — fica para 016.1).
- Edita `tenants.yaml` (Ariel-only):
  ```yaml
  ariel:
    triggers:
      enabled: true
      cadence_seconds: 15
      daily_cap_per_customer: 3
      list:
        - id: ariel_match_reminder
          type: time_before_scheduled_event
          enabled: true
          mode: dry_run  # SHADOW
          lookahead_hours: 1
          cooldown_hours: 24
          template_ref: match_reminder_pt
          match: { intent_filter: any, agent_id_filter: any, consent_required: true }
    templates:
      match_reminder_pt:
        name: ariel_match_reminder
        language: pt_BR
        components:
          - type: body
            parameters:
              - { type: text, ref: "{{ customer.name }}" }
              - { type: text, ref: "{{ customer.scheduled_event_at | format_time }}" }
        approval_id: meta_approval_xyz123
        cost_usd: 0.0085
  ```
- Aguarda 3d com `mode: dry_run` — observador admin viewer + grafana counters; valida match rate esperado (~5-10/dia para Ariel small base).
- Flip `mode: live`. Primeiro real send para 1 customer teste (operador). Operador confirma recebimento.
- 24h baseline; se zero rejection + zero cap-blocked + zero ban warning Meta dashboard, considerar success.
- Documentar `prosauai/triggers/RUNBOOK.md` — setup operador, debug, kill-switch (`triggers.enabled: false`), reverter para 016.1+ se preciso.

**Gate**: Ariel envia 1 template real para 1 cliente teste; admin viewer mostra row sent; cooldown bloqueia 2a tentativa <24h; daily cap bloqueia 4o trigger.

### Cut-line decisions

| Cenario | Acao |
|---------|------|
| PR-A estourar (>5d) | PR-B inteiro vira 016.1. PR-A entrega so engine + persistence + cooldown em dry_run. |
| PR-B B.1 estourar (Evolution send_template surpreende >2d) | send_template + B.7 viram 016.1. PR-B entrega so admin viewer (B.5+B.6) consultando dry-runs do PR-A. |
| PR-B B.6 estourar (admin UI atrasa) | Admin UI vira 016.1. Backend endpoint (B.5) shipa em PR-B; operador consulta via SQL durante curto prazo. |
| Meta template approval >D+2 | B.7 abortado, shipa PR-B sem rollout. Ariel rollout vira 016.1 quando approval chegar. |
| ResenhAI rollout | **Sempre fica em 016.1+** — observa Ariel 7d antes; nao expandir agente em 016. |
| Tudo no prazo | 016 ships completo PR-A + PR-B + Ariel live em 1 trigger. ResenhAI agendado 016.1. |

## Phase 0: Outline & Research

Ver [`research.md`](./research.md) para o detalhamento das 7 alternativas-chave (R1..R7), cada uma com pros/cons + decisao + justificativa.

Resumo das decisoes (D-PLAN-01..D-PLAN-12):

| # | Decisao | Alternativa rejeitada | Justificativa curta |
|---|---------|----------------------|---------------------|
| D-PLAN-01 | **Cron-only em v1** (15s cadence + advisory lock singleton) | PG NOTIFY listener para `INSERT INTO messages` | Todos use cases v1 sao scheduled/timed; PG NOTIFY adicionaria complexidade lock-global (ADR-004) sem ganho real. Listener vira 016.1+ se demanda real-time aparecer. |
| D-PLAN-02 | **`tenants.yaml triggers.* + templates.*` blocks** (per-tenant) | Tabelas dedicadas `triggers` + `templates` no PG | Pattern consolidado em 4 epics (010, 013, 014, 015); hot reload <60s ja existente; YAML PR review e auditavel. Tabela viraria custom UI workflow + migrations + APIs CRUD = scope creep. Self-service UI fica em epic 018. |
| D-PLAN-03 | **Cooldown Redis + SQL fallback** (FR-015) | Redis-only OR SQL-only | Redis-only quebra em restart (perda de estado); SQL-only adiciona latencia em cada check (~5ms × 100 customers = 500ms). Hibrido: Redis fast-path + SQL recovery garante zero duplicate sent pos-restart. |
| D-PLAN-04 | **Idempotencia 2 niveis** — app-check antes do send + partial UNIQUE INDEX `WHERE status IN ('sent','queued')` (FR-017) | App-check only OR DB-only | App-check protege contra re-tick normal; index protege contra race conditions (multi-replica) e contra bugs futuros que esquecam check aplicacional. Custo zero em writes (audit append-only). Decidido em clarify Round 2. |
| D-PLAN-05 | **Stuck-detection via UPDATE in-place + retry_count** (FR-041) | Insert nova row a cada retry | UPDATE preserva integridade do audit trail (1 row = 1 trigger fired logico); retry_count visivel no admin viewer ajuda diagnostico. Idempotencia DB nao quebra (mesma chave logica). Decidido em clarify Round 2. |
| D-PLAN-06 | **3 trigger types pre-built v1, sem custom** | Custom escape hatch via expression evaluator | Cobre 80% use cases roadmap; custom adiciona surface de attack (eval safety) + complexidade matchers. Custom vira 016.1+ apos baseline 30d. |
| D-PLAN-07 | **Manual ops cadastra templates Meta em `tenants.yaml`** | Auto-sync via Meta Graph API | Graph API = 1 nova dep + 1 webhook listener Meta + reconciliacao de approval state (24-48h async); fora da appetite. Manual em v1; auto-sync vira 016.1+. |
| D-PLAN-08 | **Admin viewer read-only em PR-B**; sem editor de config | Form-based editor em PR-B | YAML PR review e codigo vivente, audit nativo, zero risco de override em runtime. Editor vira 016.1+ — ops valida 30d uso real antes de investir UI editor. |
| D-PLAN-09 | **Opt-out manual via `customers.opt_out_at`** (migration nova) | Detector NLP automatico STOP/SAIR | Detector NLP exige modelo + treino + thresholds + reviewer humano = fora appetite. Manual em v1; detector vira 016.1+. |
| D-PLAN-10 | **`trigger_events` admin-only carve-out (sem RLS)** — ADR-027 | RLS per-tenant em trigger_events | ADR-027 ja firma carve-out para tabelas admin-only de auditoria; consistente com `traces`/`trace_steps`/`routing_decisions`. Filtro `tenant_id` na UI e cosmetic v1, vira security boundary em epic 018 (Tenant Self-Admin). |
| D-PLAN-11 | **Cost gauge separate lifespan task com advisory lock proprio** (FR-030) | Inline no trigger_engine_loop | Cron tick principal hot path 15s; gauge query agregada SUM custa ~50-100ms — desacoplar evita slow path. Advisory lock proprio garante 1 replica ativa. Decidido em clarify Round 2. |
| D-PLAN-12 | **Hard delete LGPD via CASCADE em `trigger_events.customer_id`** (FR-019) | Anonimizacao (set NULL + redact payload) | ADR-018 firma direito ao apagamento; metricas operacionais agregadas permanecem em Prometheus retention 30d (independente de customer_id). Anonimizacao adia para 016.1+ se DPO requerer — `[VALIDAR]`. |

## Phase 1: Design & Contracts

### Data model

Ver [`data-model.md`](./data-model.md) para DDL completo, ER e cap policy. Resumo:

```sql
-- NOVA tabela admin-only (ADR-027 carve-out)
CREATE TABLE public.trigger_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    trigger_id TEXT NOT NULL,
    template_name TEXT NOT NULL,
    fired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('queued','sent','failed','skipped','rejected','dry_run')),
    error TEXT,
    cost_usd_estimated NUMERIC(10,4),
    payload JSONB,
    retry_count INT NOT NULL DEFAULT 0
);
-- ADR-027: SEM RLS, admin-only
CREATE INDEX idx_trigger_events_tenant_fired ON public.trigger_events (tenant_id, fired_at DESC);
CREATE INDEX idx_trigger_events_customer_fired ON public.trigger_events (customer_id, fired_at DESC);
-- FR-017: idempotencia DB defense-in-depth
CREATE UNIQUE INDEX trigger_events_idempotency_idx
    ON public.trigger_events (tenant_id, customer_id, trigger_id, (fired_at::date))
    WHERE status IN ('sent', 'queued');

-- ALTER em customers (epic 005)
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS scheduled_event_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_customers_scheduled_event
    ON public.customers (tenant_id, scheduled_event_at)
    WHERE scheduled_event_at IS NOT NULL;
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS opt_out_at TIMESTAMPTZ;
```

Cap policy + retention:
- `trigger_events.payload` JSONB — soft cap 8 KB enforced em app (`pydantic.BaseModel.model_validate`); rows excedendo truncadas + warn.
- Retention 90 dias via cron epic 006 estendido (`DELETE WHERE fired_at < NOW() - INTERVAL '90 days'`).
- LGPD SAR via `ON DELETE CASCADE` em `customer_id`.

### Contracts

Ver [`contracts/openapi.yaml`](./contracts/openapi.yaml) para schemas completos. Endpoints novos (PR-B):

| Method | Path | Descricao |
|--------|------|-----------|
| GET | `/admin/triggers/events` | Lista paginada (cursor) com filtros tenant/trigger/customer/status/date range; admin only super-admin v1 |
| PATCH | `/admin/customers/{id}` (existente, MODIFIED) | Aceita `scheduled_event_at` + `opt_out_at` no body |
| GET | `/admin/agents/{id}` (existente, MODIFIED, opcional) | Inclui `triggers_count` na response |

Schema response trigger event:

```yaml
TriggerEventResponse:
  type: object
  required: [id, tenant_id, customer_id, customer_phone, trigger_id, template_name, status, fired_at, retry_count]
  properties:
    id: { type: string, format: uuid }
    tenant_id: { type: string, format: uuid }
    customer_id: { type: string, format: uuid }
    customer_phone: { type: string }   # phone_number_e164 join
    trigger_id: { type: string }
    template_name: { type: string }
    status: { type: string, enum: [queued, sent, failed, skipped, rejected, dry_run] }
    fired_at: { type: string, format: date-time }
    sent_at: { type: string, format: date-time, nullable: true }
    cost_usd_estimated: { type: number, nullable: true }
    error_short: { type: string, nullable: true }   # first 200 chars
    retry_count: { type: integer }

TriggerEventDetail:
  allOf:
    - $ref: '#/components/schemas/TriggerEventResponse'
    - type: object
      properties:
        payload: { type: object, additionalProperties: true }   # full JSONB
        error: { type: string, nullable: true }   # full error message
```

### Quickstart

Ver [`quickstart.md`](./quickstart.md) para passo-a-passo de:
- Setup local (Docker compose ou testcontainers).
- Aplicar migrations e seed Ariel + 1 template + 1 trigger.
- Configurar `tenants.yaml` para Ariel (com mode: dry_run).
- Validar US1 (lembrete antes do jogo) via dry_run rows + log.
- Validar US2 (re-engagement apos conversa fechada) idem.
- Validar US3 (abandoned cart) idem.
- Flip para `mode: live` + validacao admin viewer.
- Verificar cooldown + daily cap + opt_out via stress test.

### Agent context

Apos PR-A mergear, rodar `.specify/scripts/bash/update-agent-context.sh claude` para registrar:
- New module `prosauai/triggers/` (engine, scheduler, matchers, cooldown, template_renderer, events).
- Pattern `pg_try_advisory_lock(hashtext('triggers_<purpose>_cron'))` como referencia para futuros lifespan tasks singleton.
- Constantes `MAX_TRIGGER_CUSTOMERS_PER_TICK = 100`, `DEFAULT_COOLDOWN_HOURS = 24`, `DEFAULT_DAILY_CAP = 3`.
- New table `public.trigger_events` admin-only carve-out + idempotency partial UNIQUE INDEX pattern.

## Complexity Tracking

> Vazio — Constitution Check passou sem violations.

## Risks & Open Questions

| Risco / Questao | Mitigacao / Estado |
|----------------|--------------------|
| Evolution `/sendTemplate` semantica de `components`/`parameters` surpreender em PR-B | Mitigado: smoke test isolado em template aprovado de teste antes de integrar engine; runbook documenta pegadinhas. Cut-line: send_template vira 016.1 se >2d. |
| Cron-only em v1 deixa abandoned cart com max 15s lag (PG NOTIFY daria <100ms) | Aceito: D-PLAN-01. Use cases v1 (lembrete, follow-up, re-engage) toleram 15s lag; PG NOTIFY ADR-004 tem lock-global limitation. Reavaliar 016.1 se demanda real-time aparecer. |
| LGPD hard delete via CASCADE remove evidencia per-customer no audit trail | Aceito + `[VALIDAR]`: D-PLAN-12. Metricas agregadas permanecem em Prometheus retention 30d. DPO/juridico podem requerer anonimizacao em 016.1+. |
| Trigger config errado causa tsunami (>1000 customers em 1 tick) | Mitigado: hard cap 100/trigger/tick (FR-011) + cooldown 24h + daily cap 3 + cost alert R$50/dia. Multi-camada de defesa. |
| Template rejection rate alto (Meta config invalida inicial) | Mitigado: alert critical 1min via Slack/Telegram (FR-026); operador corrige tenants.yaml + redeploy template Meta; runbook documenta troubleshoot. |
| Cron tick lento por matcher full table scan | Mitigado: indexes partial em `customers.scheduled_event_at` + `conversations.closed_at` + `messages.created_at`; query plans validados via EXPLAIN em PR-A. Hard cap 100 garante tick <2s. |
| Cooldown Redis perdido pos-restart | Mitigado: SQL fallback `restore_state_from_sql` (FR-015) + idempotencia DB partial UNIQUE INDEX (FR-017). Zero duplicate sent verificado em chaos test. |
| Ariel template approval Meta atrasar (>D+2 da PR-B start) | Aceito: rollout vira 016.1; PR-B shipa sem B.7 (engine + admin viewer prontos). |
| Race condition entre matcher concorrente em multi-replica | Mitigado: `pg_try_advisory_lock(hashtext('triggers_engine_cron'))` singleton garante 1 tick ativo por vez; partial UNIQUE INDEX captura race exotica em testes. |
| Cardinality Prometheus saturada >50K series por tenant misconfig | Mitigado: lint no startup (FR-033); alert crit se passar baseline; max 100 tenants × 20 triggers × 5 statuses × 50 templates = 50K teorico, real esperado <10K. |
| Frontend admin viewer atrasar PR-B B.6 | Aceito: cut-line — vira 016.1; backend endpoint shipa em PR-B (zero risco operacional). |

## Decision Audit Trail

| ID | Decisao | Skill | Source |
|----|---------|-------|--------|
| 1..30 | Decisoes epic-context (cron-only, tenants.yaml blocks, cooldown granular, 3 types, persistence, send_template, etc) | epic-context | pitch.md Captured Decisions (2026-04-26) |
| 31..35 | Idempotencia 2 niveis, stuck UPDATE in-place + retry_count, LGPD hard delete CASCADE, admin auth super-admin, cost gauge separate task | clarify | spec.md Round 2 Clarifications (2026-04-28) |
| D-PLAN-01..12 | Ver tabela em Phase 0 acima | plan | autonoma — tradeoffs em research.md |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo para epic 016 trigger-engine. 12 D-PLAN documentadas em research.md (cron-only v1, tenants.yaml blocks, cooldown Redis+SQL fallback, idempotencia 2-niveis app+DB partial UNIQUE INDEX, stuck-detection UPDATE in-place + retry_count, 3 trigger types pre-built sem custom v1, manual template catalog, admin viewer read-only, opt-out manual via customers.opt_out_at, trigger_events admin-only ADR-027 carve-out, cost gauge separate lifespan task com advisory lock proprio, LGPD hard delete CASCADE). Sequencia: PR-A (5d) entrega engine + persistence + cooldown em dry_run only — 4 migrations, 6 modulos novos em prosauai/triggers/, 7 unit + 4 integration tests; PR-B (5d) entrega send_template + Prometheus 5 counters + 2 alert rules + admin viewer + Ariel rollout shadow→live. Hard gates: zero regressao em pipeline inbound (tenants/agentes sem triggers.list inalterados); cron tick p95 <=2s; admin endpoint p95 <300ms. Cut-lines: PR-A estourar → PR-B vira 016.1; Evolution semantica surpreender → send_template vira 016.1; admin UI atrasar → vira 016.1; Meta template approval atrasar → Ariel rollout vira 016.1. ResenhAI rollout sempre fica em 016.1+. Tasks devem cobrir 2 PRs com numeracao T001 (PR-A.1 migrations) ate T0XX (PR-B.7 rollout); cada PR comeca com tests-first quando aplicavel (TDD). Risco principal: Evolution /sendTemplate surpreender — mitigado por smoke test isolado antes de integrar."
  blockers: []
  confidence: Alta
  kill_criteria: "Plan invalido se: (a) Evolution /message/sendTemplate/{instance} nao existir ou semantica fundamentalmente diferente (precisa pivot para Cloud API direto via Meta Graph — re-spec required); (b) DPO/juridico requerer audit trail completo apos SAR (anonimizar em vez de hard delete) — FR-019 + schema migration precisam re-design; (c) bench em PR-A mostrar cron tick p95 >5s mesmo com hard cap 100 + indexes — repensar (matcher batch, async fan-out); (d) cardinality Prometheus saturar >50K em fixture realista — reduzir labels (drop template_name); (e) tests-suite existente exigir mais que 5% de modificacao para acomodar engine — refatorar antes do PR-A; (f) trigger_events crescer >50GB em 30d em load test — reduzir retention para 30d ou criar tabela particionada por mes; (g) decisao de produto cortar epic inteiro pos-PR-A → PR-B vira 016 cancelado, dry-runs do PR-A continuam consultaveis via SQL."
