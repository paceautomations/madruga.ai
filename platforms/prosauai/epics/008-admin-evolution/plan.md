# Implementation Plan: Admin Evolution — Plataforma Operacional Completa

**Branch**: `epic/prosauai/008-admin-evolution` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/008-admin-evolution/spec.md`

## Summary

Evoluir o admin entregue no epic 007 (sidebar mínima + login + dashboard com 1 KPI) para uma plataforma operacional com 8 abas funcionais: **Overview** (enriquecido com 6 KPIs + activity feed + system health + tenant health), **Conversas** (inbox com thread + perfil), **Trace Explorer** (waterfall das 12 etapas do pipeline com input/output por step), **Performance AI** (agregações de qualidade/custo com 5 tipos de gráficos), **Agentes** (configuração + diff de prompts), **Roteamento** (decisões MECE persistidas incluindo DROPs), **Tenants** (admin CRUD + toggle) e **Auditoria**.

**Abordagem técnica**: camada de persistência dedicada (3 novas tabelas + denormalização da inbox) com instrumentação **fire-and-forget** do pipeline (R3) para zero impacto no caminho crítico; backend FastAPI expondo ~25 endpoints cobertos por OpenAPI 3.1; frontend Next.js 15 App Router reusando stack do epic 007 (shadcn/ui + Tailwind v4 + Recharts via shadcn Chart + TanStack Query) com Server Components para first paint rápido e polling para live data. Filtro global de tenant é **URL param** (`?tenant=<slug>`) como fonte única de verdade — Server Components leem via `searchParams`.

Instrumentação do pipeline (PR 2) é o único toque em código do epic 005 — **gate de merge explícito**: 100% da suíte existente de epics 004 e 005 passando antes do merge (SC-007).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend Next.js 15)
**Primary Dependencies**: FastAPI >=0.115, asyncpg >=0.30, pydantic 2.x, redis[hiredis] >=5.0, opentelemetry-sdk; Next.js 15.x, shadcn/ui, Tailwind v4, Recharts v2, @tanstack/react-query v5, lucide-react
**Storage**: PostgreSQL 15 (Supabase) com `pool_admin` (BYPASSRLS) para todas as queries admin; Redis 7 para cache de agregações (5 min TTL) e activity feed (10 s TTL); migrations via `dbmate`
**Testing**: pytest + testcontainers-postgres (backend), pnpm test + Playwright (frontend e2e para 3 fluxos críticos)
**Target Platform**: Linux server (FastAPI em uvicorn); browser desktop (Chrome/Safari recentes) para admin UI (dark mode único)
**Project Type**: Web application — backend FastAPI em `apps/api/prosauai/admin/*` + frontend Next.js 15 em `apps/admin`
**Performance Goals**:
- p95 endpoints de listagem (conversas/traces/audit) ≤300 ms em dataset de 10 k conversas + 50 k traces
- p95 Performance AI ≤2 s sem cache, ≤200 ms com cache (Redis 5 min)
- Inbox render server-side ≤100 ms em 10 k conversas (requer denormalização)
- Overhead de instrumentação no pipeline ≤10 ms (p95)
**Constraints**:
- Dark mode único na v1 (tokens OKLCH já definidos no epic 007)
- Fire-and-forget obrigatório para persistência de trace/routing — nenhuma falha pode bloquear delivery ao cliente final
- Novas tabelas **sem RLS**, acessíveis apenas via `pool_admin` (ADR novo documenta o carve-out do ADR-011)
- Schema `public.*` (drift aceito via ADR-024) — cleanup para `prosauai` fica em backlog
- Input/output de trace_steps truncados em 8 KB no servidor
- Branch `epic/prosauai/008-admin-evolution` já existe no repo externo — reaproveitar (não recriar)
**Scale/Scope**:
- 2 tenants ativos, ~5 k mensagens/dia/tenant
- Admin: 3–10 usuários simultâneos no pico
- Novas tabelas: ~3.6 M traces/ano + 43 M trace_steps/ano + 3.6 M routing_decisions/ano (com retention 30d/90d = ~1.5 GB estáveis)
- 25 endpoints novos + ~35 componentes frontend novos

## Constitution Check

*GATE: passa antes do Phase 0 research. Re-checked após Phase 1 design.*

| Princípio | Avaliação | Justificativa |
|-----------|-----------|---------------|
| I — Pragmatismo & Simplicidade | ✅ | Reusa 100% da stack do epic 007. Zero novas libs UI. Hardcode de pricing (10 linhas) vs. tabela DB (overkill v1). URL params para tenant (sem context/cookie). |
| II — Automate repetitive | ✅ | OpenAPI → tipos gerados (`openapi-typescript`). Retention-cron reusado do epic 006. dbmate já estabelecido. |
| III — Knowledge structured | ✅ | `decisions.md` registra 25 decisões com referências. ADR novo para RLS carve-out das novas tabelas. |
| IV — Fast action | ✅ | 10 PRs sequenciais, cada um deixando o sistema funcional. PR 0 é só ADR + audit (3h). Cut-line documentado em F5/F6. |
| V — Alternativas & trade-offs | ✅ | `research.md` apresenta 2–4 alternativas por decisão crítica (R1–R16) com pros/cons e justificativa de rejeição. |
| VI — Brutal honesty | ✅ | Spec marca pitch como "decisão consciente de exceder appetite Shape Up" (decisão 2). Cut-line explícito se >5 semanas. Pricing gpt-5-mini `[VALIDAR]`. |
| VII — TDD | ✅ | 3 camadas (unit + integration + e2e). PR 2 tem gate de merge: 100% da suíte existente passando. 4 testes unit novos (instrumentação) escritos antes do refactor. |
| VIII — Collaborative decisions | ✅ | 5 ambiguidades já resolvidas no clarify (thresholds, ILIKE vs full-text, definição de fallback, regra de tenant health, origem de bolhas humanas). |
| IX — Observability | ✅ | Pipeline mantém emissão OTel (epic 002). Endpoints admin emitem spans `admin.endpoint.*`. Persistência de trace falha com log estruturado (nunca silenciosa). |

**Violações**: nenhuma. `Complexity Tracking` vazio.

### Post-Phase-1 re-check

| Risco | Status |
|-------|--------|
| Refactor do pipeline introduz regressão | Mitigado: gate SC-007 (100% suite passa) + smoke test 24 h em staging antes do prod |
| Novas tabelas sem RLS violam invariante ADR-011 | Mitigado: ADR novo na PR 0 documenta carve-out — tabelas admin-only são a exceção explícita |
| Overhead de instrumentação >10 ms | Mitigado: fire-and-forget com `asyncio.create_task`; benchmark A/B em staging obrigatório |
| Explosão de storage (trace_steps JSONB) | Mitigado: truncate 8 KB + retention 30 d → ~1.2 GB estáveis |
| Branch externa conflito | Mitigado: decisão 25 explicita checkout de branch existente (não criar) |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/008-admin-evolution/
├── plan.md                  # Este arquivo
├── spec.md                  # Feature specification (pós-clarify)
├── pitch.md                 # Shape Up pitch (L2 — epic-context)
├── decisions.md             # 25 micro-decisões capturadas
├── reference-spec.md        # Ground truth visual (layouts)
├── research.md              # Phase 0 — R1..R16 decisões com alternativas
├── data-model.md            # Phase 1 — schemas SQL + ER diagram
├── quickstart.md            # Phase 1 — setup + validação US1..US8
├── contracts/
│   ├── README.md
│   └── openapi.yaml         # OpenAPI 3.1 (~25 endpoints)
├── checklists/              # pré-existente
└── easter-tracking.md       # pré-existente (operacional)
```

### Source Code (repository root — repo `paceautomations/prosauai`)

```text
apps/
├── api/                                          # backend FastAPI (existente)
│   ├── prosauai/
│   │   ├── main.py                               # register admin routers
│   │   ├── admin/                                # (epic 007 + novos)
│   │   │   ├── auth.py                           # cookie JWT (existente)
│   │   │   ├── conversations.py                  # NEW — list/detail/patch/messages
│   │   │   ├── customers.py                      # NEW — list/detail
│   │   │   ├── tenants.py                        # NEW — list/detail/patch
│   │   │   ├── traces.py                         # NEW — list/detail
│   │   │   ├── metrics/
│   │   │   │   ├── overview.py                   # NEW — 6 KPIs + sparklines
│   │   │   │   ├── activity_feed.py              # NEW — UNION ALL + Redis 10s
│   │   │   │   ├── performance.py                # NEW — cached 5min
│   │   │   │   ├── tenant_health.py              # NEW — hierarchical rule
│   │   │   │   └── system_health.py              # NEW — PG/Redis/Evolution/Phoenix checks
│   │   │   ├── routing.py                        # NEW — rules/decisions/stats
│   │   │   ├── agents.py                         # NEW — list/detail/prompts
│   │   │   └── audit.py                          # NEW — paginated timeline
│   │   ├── conversation/                         # (epic 005 — modificado neste epic)
│   │   │   ├── pipeline.py                       # MODIFIED — buffer StepRecord + fire-and-forget persist
│   │   │   ├── agent.py                          # MODIFIED — expor tokens/model para pricing
│   │   │   ├── pricing.py                        # NEW — MODEL_PRICING constant + calculate_cost
│   │   │   └── trace_persist.py                  # NEW — async persister para traces+steps
│   │   ├── router/                               # (epic 004 — modificado)
│   │   │   └── engine.py                         # MODIFIED — hook persist_decision fire-and-forget
│   │   ├── observability/
│   │   │   ├── phoenix_exporter.py               # (existente — padrão de fire-and-forget)
│   │   │   └── trace_context.py                  # NEW — helper get_trace_id_hex()
│   │   └── db/
│   │       ├── pool.py                           # (existente — pool_admin)
│   │       └── queries/
│   │           ├── conversations.py              # NEW
│   │           ├── traces.py                     # NEW
│   │           ├── routing_decisions.py          # NEW
│   │           └── activity.py                   # NEW (UNION ALL)
│   ├── migrations/                               # dbmate
│   │   ├── 20260420000001_create_traces.sql
│   │   ├── 20260420000002_create_trace_steps.sql
│   │   ├── 20260420000003_create_routing_decisions.sql
│   │   └── 20260420000004_alter_conversations_last_message.sql
│   ├── scripts/
│   │   ├── backfill_last_message.py              # NEW — backfill pós-PR 4
│   │   └── retention_cron.py                     # MODIFIED — estender para novas tabelas
│   └── tests/
│       ├── unit/
│       │   ├── conversation/
│       │   │   ├── test_pipeline_instrumentation.py   # NEW
│       │   │   └── test_pricing.py                    # NEW
│       │   ├── router/
│       │   │   └── test_routing_persistence.py       # NEW
│       │   └── admin/
│       │       └── test_health_rules.py               # NEW (FR-011, FR-015)
│       └── integration/
│           └── admin/
│               ├── test_conversations.py              # NEW
│               ├── test_traces.py                     # NEW
│               ├── test_performance.py                # NEW (cache hit/miss)
│               ├── test_routing.py                    # NEW
│               └── test_overview.py                   # NEW
└── admin/                                        # frontend Next.js 15 (existente — epic 007)
    ├── src/
    │   ├── app/
    │   │   ├── (dashboard)/
    │   │   │   ├── layout.tsx                    # MODIFIED — sidebar 8 items + tenant dropdown
    │   │   │   ├── page.tsx                      # MODIFIED — Overview enriched
    │   │   │   ├── conversations/{page.tsx,[id]/page.tsx}   # NEW
    │   │   │   ├── traces/{page.tsx,[trace_id]/page.tsx}    # NEW
    │   │   │   ├── performance/page.tsx           # NEW
    │   │   │   ├── agents/{page.tsx,[id]/page.tsx}          # NEW
    │   │   │   ├── routing/page.tsx              # NEW
    │   │   │   ├── tenants/{page.tsx,[slug]/page.tsx}       # NEW
    │   │   │   └── audit/page.tsx                # NEW
    │   │   └── login/page.tsx                    # (existente)
    │   ├── components/
    │   │   ├── ui/                               # shadcn primitives + novos: intent-badge, quality-score-badge, sla-indicator, json-tree, kpi-card
    │   │   ├── conversations/                    # ConversationList, ThreadView, ContactProfile, MessageBubble
    │   │   ├── traces/                           # TraceList, WaterfallChart, StepAccordion, StepDetailPanel
    │   │   ├── performance/                      # IntentDistribution, QualityTrend, LatencyWaterfall, ErrorHeatmap, CostBars
    │   │   ├── agents/                           # AgentList, AgentDetailTabs, PromptDiffView, PromptViewer
    │   │   ├── routing/                          # RulesTable, DecisionsDonut, DecisionsList, DecisionDetailPanel
    │   │   ├── tenants/                          # TenantList, TenantDetail, TenantToggle
    │   │   ├── audit/                            # AuditTimeline, AuditFilters
    │   │   └── shared/                           # TenantDropdown, Sidebar, ActivityFeed, SystemHealth
    │   ├── lib/
    │   │   ├── api.ts                            # fetch wrapper + 401 redirect
    │   │   ├── query-client.ts                   # TanStack Query config
    │   │   ├── format.ts                         # formatCurrency, formatDuration, maskPhone, truncate
    │   │   └── health-rules.ts                   # NEW — thresholds FR-011 + tenant health FR-015
    │   ├── types/
    │   │   └── api.ts                            # GENERATED from contracts/openapi.yaml
    │   └── app/globals.css                       # (existente — tokens OKLCH)
    └── tests/
        ├── unit/                                 # lib/health-rules, lib/format
        └── e2e/                                  # Playwright — 3 fluxos críticos
            ├── login-to-overview.spec.ts
            ├── conversation-to-trace.spec.ts
            └── trace-explorer-filter.spec.ts
```

**Structure Decision**: **Web application** — backend existente em `apps/api/prosauai/*` recebe novos routers sob `admin/` + modificações mínimas em `conversation/` e `router/`; frontend existente em `apps/admin/` recebe novos components/pages organizados por feature folder (decisão 24). Tipos TypeScript gerados a partir de `contracts/openapi.yaml` via `openapi-typescript`.

## Phase 0 — Research

Todos os unknowns resolvidos em [`research.md`](./research.md) (R1–R16):

- **R1** Modelo de persistência de traces (tabelas dedicadas + BRIN)
- **R2** Propagação de `trace_id` (OTel context via contextvars)
- **R3** Estratégia de batch INSERT (fire-and-forget em 1 txn)
- **R4** Cost calculation (hardcoded constant)
- **R5** Denormalização `conversations.last_message_*`
- **R6** Cache Redis Performance AI (5 min TTL)
- **R7** Routing decisions (fire-and-forget + sem RLS)
- **R8** Activity feed (UNION ALL + Redis 10 s)
- **R9** Frontend state (Server Components + TanStack Query + URL params)
- **R10** Charts (shadcn Chart + heatmap custom + json-tree custom)
- **R11** Migrations (4 independentes via dbmate)
- **R12** Branch reuse (checkout existente)
- **R13** Folder structure frontend
- **R14** Pricing table v1 (gpt-4o / gpt-4o-mini / gpt-5-mini)
- **R15** Testing strategy (3 camadas)
- **R16** Observabilidade do admin

**Zero NEEDS CLARIFICATION remanescentes.**

## Phase 1 — Design & Contracts

### Data model
[`data-model.md`](./data-model.md) — 3 tabelas novas (`traces`, `trace_steps`, `routing_decisions`) + `ALTER conversations` com denormalização. ER diagram em Mermaid. Volume & retention matrix. Política LGPD.

### API contracts
[`contracts/openapi.yaml`](./contracts/openapi.yaml) — OpenAPI 3.1 cobrindo:
- 4 endpoints de conversations
- 2 de customers
- 3 de tenants
- 2 de traces
- 5 de metrics (overview, activity-feed, performance, tenant-health, system-health)
- 4 de routing
- 4 de agents
- 1 de audit

Auth: cookie JWT `admin_token` (global). Tenant filter: parâmetro `?tenant=<slug>` (global). Paginação: cursor-based. Cache: `Cache-Control: max-age=300` em `/admin/metrics/performance`.

### Quickstart
[`quickstart.md`](./quickstart.md) — Setup local em 7 passos. Validação de US1..US5 com critérios cronometrados (SC-001 a SC-003). Benchmarks esperados + troubleshooting.

### Agent context update

O arquivo `CLAUDE.md` do repo `prosauai` (e este repo madruga.ai) ganha entrada na seção "Active Technologies" via script `.specify/scripts/bash/update-agent-context.sh claude`:

- Novas tecnologias: `@tanstack/react-query v5`, `openapi-typescript` (dev-only), shadcn Chart wrapper
- Tabelas novas: `public.traces`, `public.trace_steps`, `public.routing_decisions`
- Constants: `apps/api/prosauai/conversation/pricing.py` (MODEL_PRICING)

## Phases 2..10 — Rollout Plan (resumo high-level — detalhes em `tasks.md`)

| PR | Foco | Modifica código de | Gate |
|----|------|---------------------|------|
| **PR 0** | ADR + audit | — | Review do ADR novo (1-way-door: RLS carve-out) |
| **PR 1** | Migrations (4 files) | schema | `dbmate up && dbmate down && dbmate up` verde |
| **PR 2** | Pipeline instrumentation | epic 005 | 100% testes epics 004 + 005 passando + 4 testes unit novos + 24h staging |
| **PR 3** | Routing persistence hook | epic 004 | 100% testes router + 1 teste unit novo |
| **PR 4** | Denorm `conversations.last_message_*` + backfill | epic 005 | 100% testes + backfill idempotente + benchmark <100ms |
| **PR 5** | Backend endpoints: Conversations + Customers + Tenants | — | Integration tests + OpenAPI válido + tipos gerados |
| **PR 6** | Backend endpoints: Traces + Performance + Routing + Audit | — | Integration tests + cache hit ratio >80% em benchmark |
| **PR 7** | Frontend: Sidebar 8 itens + Overview enriquecido + Conversations | — | Playwright US1 verde + Lighthouse >90 |
| **PR 8** | Frontend: Trace Explorer (waterfall + accordions) | — | Playwright US2 verde |
| **PR 9** | Frontend: Performance AI (5 charts) | — | Visual regression em Chromatic (opcional) + cache funcional |
| **PR 10** | Frontend: Agents + Routing + Tenants + Audit + polish + e2e | — | Playwright US3/US5 + docs atualizadas |

**Cut-line (decisão 2 pitch)**: ao final do PR 8, reavaliar. Se passar de 5 semanas, cortar PR 9 (Performance AI) + PR 10 parcialmente para **epic 009**, shipando PR 0–8 com Overview + Conversations + Trace Explorer + Routing básico.

## Complexity Tracking

> Vazio. Nenhuma violação do Constitution Check.

## Risks & Mitigations

| Risco | Impacto | Prob. | Mitigação |
|-------|---------|-------|-----------|
| Regressão no pipeline após refactor | Crítico (entrega de mensagens) | Baixa | Fire-and-forget + 100% suite + 24h staging (PR 2) |
| Explosão de storage (trace_steps JSONB) | Médio (custo Supabase) | Baixa | Truncate 8 KB + retention 30 d default → ~1.2 GB estáveis |
| Cache Redis thundering herd em Performance | Médio | Média | Jitter no TTL (300 ± 30 s) + request coalescing se >1 miss simultâneo (backlog se P95 degradar) |
| Backfill de `conversations.last_message_*` bloqueia prod | Médio | Baixa | Script incremental com LIMIT + sleep, rodar off-peak |
| Concurrency em PATCH conversation (duplo fechamento) | Baixo (UX) | Média | 409 + refetch client-side |
| Preço de gpt-5-mini `[VALIDAR]` incorreto | Baixo ($ errado no UI) | Baixa | PR de 1 linha em `pricing.py` quando confirmar |
| Branch externa sem commits recentes | Baixo | Baixa | Decisão 25: checkout explícito (não recriar) |
| 10 PRs sequenciais em 6–8 semanas excede Shape Up | Médio (atraso) | Alta | Cut-line em PR 8: cortar 9–10 para epic 009 |

## Progress Tracking

- [x] Phase 0 — Research concluído (R1..R16)
- [x] Phase 1 — data-model.md + contracts/openapi.yaml + quickstart.md
- [x] Constitution Check inicial: PASS (0 violações)
- [x] Constitution Check pós-Phase 1: PASS
- [ ] Phase 2 (tasks.md) — **não gerado neste comando** (responsabilidade de `/speckit.tasks`)

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plano técnico completo com research.md (16 decisões com alternativas), data-model.md (3 tabelas novas + ALTER), contracts/openapi.yaml (~25 endpoints), quickstart.md (validação de US1-US5 cronometradas). Sequência de 10 PRs com gates explícitos: PR 0 (ADRs), PR 1 (migrations), PR 2 (pipeline instrumentation — gate SC-007 100% testes), PR 3 (routing persist), PR 4 (inbox denorm + backfill), PR 5-6 (backend endpoints), PR 7-10 (frontend). Cut-line em PR 8 para epic 009 se >5 semanas. tasks.md deve quebrar cada PR em tasks atômicas com dependencies (BRIN indexes antes de queries, tipos gerados antes do frontend, etc.) e agrupar em fases [X] paralelas onde possível (ex: Conversations + Customers + Tenants endpoints em paralelo dentro do PR 5)."
  blockers: []
  confidence: Alta
  kill_criteria: "Este plano fica inválido se: (a) Pipeline.execute() sofre refactor estrutural que muda os 12 nomes de steps antes do PR 2; (b) Supabase muda pricing plan e 1.5 GB extras ficam proibitivos; (c) descoberta de que `trace_id` OTel já está sendo consumido por outro consumer que exige formato diferente (UUID v7 vs hex 32); (d) decisão de abandonar admin proprietário em favor de Retool/Metabase; (e) cut-line real cai para 3 semanas durante o PR 2 (stop-ship)."
