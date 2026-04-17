---
epic: 008-admin-evolution
title: "Admin Evolution — Plataforma Operacional Completa"
appetite: 6-8 semanas
status: drafted
created: 2026-04-17
updated: 2026-04-17
---
# Epic 008 — Admin Evolution

## Problem

O épico 007 entregou apenas a fundação visual (sidebar com 3 itens, login, dashboard com volume diário de mensagens). O resto da operação continua dependendo de `psql`, `journalctl`, e Phoenix UI. Quatro consequências operacionais:

1. **Conversas invisíveis**: não existe inbox. Para inspecionar uma mensagem precisa-se de SQL contra `messages` + `customers` + `conversations`. Onboarding e troubleshooting de cliente são opacos.
2. **Pipeline de IA é caixa preta**: hoje as 12 etapas (`webhook_received` → `deliver`) só aparecem fragmentadas em `messages.metadata`, `eval_scores.details` e spans Phoenix. Não há visualização step-by-step. Debug de regressão de prompt depende de `pg_dump` + parsing manual.
3. **Sem analytics de qualidade**: containment rate, distribuição de intents, fallback rate, custo por tenant/modelo — nada disso é acessível em UI. Decisões de melhoria de prompt são guiadas por intuição.
4. **Sem visibilidade do roteador MECE**: epic 004 entregou roteamento declarativo mas nenhum decisão (`RESPOND`/`DROP`/`LOG_ONLY`/`BYPASS_AI`/`EVENT_HOOK`) é persistida — só logs structlog e spans OTel. "Por que essa mensagem foi descartada?" exige `journalctl | rg trace_id`.

Este épico **transforma o admin de fundação em plataforma operacional**: 8 abas funcionais cobrindo todo ciclo de vida da conversa — observação (Conversations, Trace Explorer, Performance), gestão (Agents, Routing, Tenants), segurança (Audit), e dashboard (Overview). Spec detalhada em `reference-spec.md` (ground truth para layouts e queries específicas).

A entrega prova-se por um operador conseguir, em <30 segundos cada: (a) abrir uma conversa específica e ver o thread completo + perfil do contato, (b) clicar numa mensagem e ver o waterfall das 12 etapas com input/output de cada step, (c) ver o quality score médio e custo do dia.

## Appetite

**6-8 semanas** (1 dev full-time). Estouro do appetite Shape Up de 3 semanas é **decisão consciente** do usuário — escopo intencionalmente coeso para aplicar design system uma vez só. Mitigações:

- **Cut-line em F5/F6** (frontend Conversations + Trace Explorer): se >5 semanas, cortar Routing/Audit/Agents para épico 009 e shipar o resto.
- **Daily checkpoint** via `easter-tracking.md` para flagrar bleed cedo.
- **PR 0+1 são bloqueantes**: instrumentação do pipeline e schemas DB devem ser PRs isolados, não escondidos em features.

Distribuição estimada:
- F0 Pré-voo (ADRs, audit, decisão de pricing por modelo): ~3h
- F1 Schema + Pipeline instrumentation (`traces`, `trace_steps`, `routing_decisions`, denorm `conversations.last_message_*`, refactor `Pipeline.execute()`): ~5 dias
- F2 Backend Conversations + Customers endpoints: ~4 dias
- F3 Backend Trace Explorer endpoints: ~3 dias
- F4 Backend Performance + Routing + Tenants + Audit + Agents endpoints: ~5 dias
- F5 Frontend Sidebar + Overview enriched + Conversations + Contact profile: ~5 dias
- F6 Frontend Trace Explorer (waterfall + json-tree + step-detail): ~5 dias
- F7 Frontend Performance (4 gráficos: intent distribution, quality trend, latency waterfall, error heatmap, cost bars): ~5 dias
- F8 Frontend Agents + Routing + Tenants + Audit: ~4 dias
- F9 Polish + docs + e2e: ~2 dias

## Dependencies

- **Epic 007 (Admin Front Foundation)** — sidebar, layout, auth JWT, `pool_admin`, dbmate, shadcn/ui setup. Este épico **estende** todos esses artefatos.
- **Epic 005 (Conversation Core)** — pipeline 12-step alvo da instrumentação. Refactor de `Pipeline.execute()` para emitir `StepRecord` toca código crítico — testes do pipeline devem passar antes do merge.
- **Epic 004 (Router MECE)** — `classify()` + `RoutingEngine`. Adicionar persist hook de `Decision` para tabela `routing_decisions`.
- **Epic 002 (Observability — Phoenix + OTel)** — espelhamos o `trace_id` que já é gerado pelo OTel SDK; **não consultamos** Phoenix API neste épico (out-of-scope).
- **Epic 006 (Production Readiness)** — `retention-cron` será estendido para purgar `traces` + `routing_decisions` por LGPD.

Sem dependências em épicos pendentes — tudo já shipped.

## Captured Decisions

| # | Área | Decisão | Referência Arquitetural |
|---|------|---------|-------------------------|
| 1 | Roadmap | Adotar slot **008** para "Admin Evolution"; bumpar 008→009 (Agent Tools), 009→010 (Handoff), etc no roadmap-reassess final | planning/roadmap.md |
| 2 | Escopo | Épico único cobrindo 9 abas (sidebar + Overview + Conversations + Trace Explorer + Performance AI + Agents + Routing + Tenants + Audit) — decisão consciente de exceder appetite Shape Up | reference-spec.md |
| 3 | Trace data model | Tabelas dedicadas `public.traces` + `public.trace_steps` (NÃO usar `messages.metadata` JSONB) — schema enforced, queries 10x mais rápidas, espelha estrutura Phoenix sem dependência de API | precedente: madruga-ai/017 (`traces` em SQLite) |
| 4 | Pipeline instrumentation | Refactor de `Pipeline.execute()` em apps/api: buffer in-memory `List[StepRecord]`, batch INSERT (1 transação) no fim do pipeline. Falha do INSERT NÃO bloqueia entrega da resposta (log + skip, mesmo padrão do Phoenix exporter) | apps/api/prosauai/conversation/pipeline.py |
| 5 | Phoenix coupling | Out-of-scope para v1. Espelhamos `trace_id` mas não consumimos Phoenix API. Enrichment via Phoenix vira épico futuro (017?) | epic 002 |
| 6 | Routing persistence | Nova tabela `public.routing_decisions` populada no hot path do `RoutingEngine.evaluate()`. Fields: `tenant_id`, `decision_type`, `decision_reason`, `matched_rule` (JSONB snapshot), `facts` (JSONB MessageFacts), `trace_id`, `created_at`. Sem RLS (acesso `pool_admin`) | apps/api/prosauai/router/ |
| 7 | Inbox denormalization | Adicionar colunas `last_message_id`, `last_message_at`, `last_message_preview` (TEXT 200 char) em `conversations`. Update no `save_outbound`/`save_inbound` do pipeline. Justificativa: lista de 320px-column precisa ser <100ms para >10k conversas | epic 005 pipeline |
| 8 | Performance cache | Redis 5-min TTL nos endpoints `/admin/metrics/performance` (heatmap + percentis + cost). Sem materialized views v1 — adotar quando P95 do endpoint >2s | epic 005 (Redis já presente) |
| 9 | Tenant filter | URL query param `?tenant=xxx` — fonte única de verdade. Server Components leem via `searchParams` prop. Default = `all`. Header dropdown faz `router.push('?tenant=xxx')`. NÃO usar Context/cookie | Next.js 15 App Router pattern |
| 10 | Stack frontend | Next.js 15 App Router + shadcn/ui + Tailwind v4 + Recharts + TanStack Query + lucide-react (já estabelecidos em 007). NÃO introduzir Tremor, MUI ou outras libs UI | epic 007 / ADR-010 |
| 11 | Dark mode | Forçado (princípio 5 da spec). Sem toggle light no v1. CSS variables OKLCH já configuradas em globals.css | reference-spec.md |
| 12 | Pool DB | Todas queries via `pool_admin` (BYPASSRLS). Sem nova role | ADR-011 / epic 007 |
| 13 | Migrations | dbmate, próxima sequência `20260420000001_create_traces.sql` + ... | epic 007 |
| 14 | Auth | JWT cookie `admin_token` existente. NÃO migrar para httpOnly aqui (segue follow-up de 007) | epic 007 |
| 15 | Live activity feed | Polling 15s contra UNION de queries SQL (novas conversas, fechadas sem handoff, SLA breach, fallback intent, errors em traces). Socket.io NÃO entra (blueprint topology mas não implementado) | docs spec |
| 16 | Inbox search full-text | ILIKE (`customers.display_name ILIKE %q%` UNION `messages.content ILIKE %q%`) para v1. Migrar para `tsvector + GIN` quando >10k conversas ou P95 >500ms | docs spec |
| 17 | Cost calculation | `traces.cost_usd` calculado no fim do pipeline: `tokens_in × $/1k_in + tokens_out × $/1k_out`. Mapping de preço por modelo em `apps/api/prosauai/conversation/pricing.py` (constante hardcoded v1; futuro: tabela DB editável via admin) | apps/api/prosauai/conversation/agent.py |
| 18 | Schema location | Novas tabelas em `public.*` (segue drift conhecido de ADR-024 — epic 007 documentou esse trade-off). Cleanup para schema `prosauai` continua em backlog | ADR-024 known drift / epic 007 decisão 6 |
| 19 | Activity feed events derivados | NÃO criar tabela de eventos. Derivar via UNION ALL de SELECTs em `conversations`, `conversation_states`, `traces` com filtro `created_at > $last_seen`. Cada UNION limitado por LIMIT 10 + GLOBAL ORDER BY DESC LIMIT 50 | minimização de novas tabelas |
| 20 | Routing UI scope | Aba Routing inclui: tabela de regras ativas (lendo do estado in-memory do `RoutingEngine` via novo endpoint `/admin/routing/rules`), distribuição de decisões (donut), tabela de decisões recentes (incluindo DROPs), top-N reasons | docs spec |
| 21 | Performance heatmap data | Heatmap 24×7 de erros: query `SELECT EXTRACT(hour FROM started_at), EXTRACT(dow FROM started_at), COUNT(*) FROM traces WHERE status='error' AND started_at > now()-7d GROUP BY 1,2`. Cache Redis 5min | docs spec |
| 22 | Trace step input/output size | `trace_steps.input_jsonb` e `output_jsonb` truncados em **8KB cada** no insert (UI mostra `[truncated]` + link para Phoenix se passar). Evita explosão de storage com prompts longos | bound storage |
| 23 | Retention de traces | `retention-cron` (epic 006) estendido: DELETE traces + trace_steps WHERE `started_at < now() - retention_days`. Default 30 dias. Configurável via env | LGPD epic 006 |
| 24 | Naming convention frontend | Componentes em `apps/admin/src/components/<feature>/`: `conversations/`, `traces/`, `performance/`, `agents/`, `routing/`, `tenants/`, `audit/`. UI primitives compartilhadas em `components/ui/` | docs spec layout |
| 25 | Branch reuse | Branch externa `epic/prosauai/008-admin-evolution` foi criada manualmente no repo prosauai antes deste draft. No momento da promoção (Path B do skill), reaproveitar a branch existente em vez de tentar criar — evita conflito de worktree | easter-tracking.md incidente epic 004 |

## Resolved Gray Areas

**Trace_id propagation no pipeline (3A)**
Q: como o `trace_id` único (já gerado pelo OTel SDK) chega ao buffer de StepRecord para vincular as 12 rows ao mesmo trace?
R: Usar `opentelemetry.trace.get_current_span().get_span_context().trace_id` no início de `Pipeline.execute()` — converter para hex string e propagar via context async. Já existe instrumentação OTel ativa (epic 002) — sem código novo de geração.

**Cost calc precision (17A)**
Q: pricing por modelo é volátil (OpenAI muda preços) — hardcode aceitável?
R: **Sim para v1**. Constante em `apps/api/prosauai/conversation/pricing.py` documentada. Quando preços mudarem, PR de 5 linhas. Tabela DB editável via admin é overkill agora — vira backlog quando >3 modelos ativos.

**Routing decisions volume (6A)**
Q: persistir TODA decisão (incluindo DROPs de bots) explode storage?
R: Volume estimado: ~5k webhooks/dia/tenant × 2 tenants × 365 = 3.6M rows/ano. Com 10 colunas + JSONB ~200B = ~720MB/ano. Aceitável. Retention-cron purga após 90 dias (configurável).

**Trace step truncation (22A)**
Q: 8KB de input/output é suficiente?
R: System prompts da Pace estão em ~3KB. Histórico de mensagens raramente passa de 5KB. 8KB cobre 95% dos casos. UI degrada com `[truncated — ver Phoenix]` e link.

**Migration order (1A)**
Q: F1 cria 3 migrations (traces, routing_decisions, alter conversations). Ordem importa?
R: Não — são independentes. dbmate aplica em ordem alfabética por timestamp. Sequência: `20260420000001_create_traces.sql`, `20260420000002_create_routing_decisions.sql`, `20260420000003_alter_conversations_last_message.sql`.

**Pipeline regression risk (4A)**
Q: refactor de `Pipeline.execute()` é em hot path crítico — como mitigar?
R: (a) Buffer + batch INSERT é fire-and-forget — falha NÃO bloqueia delivery. (b) Suite de testes do epic 005 (52 test files) deve passar 100% antes do merge. (c) Smoke test em staging com tenant Ariel real por 24h antes de prod.

**Activity feed scaling (19A)**
Q: UNION de 5 SELECTs a cada 15s × N admins simultâneos não derruba o BD?
R: Cada SELECT tem LIMIT 10 + índice apropriado em `created_at`. Para 3 admins simultâneos = 1 query/sec total. Cache Redis 10s mitiga (latência aceita até 25s no feed). Materialized view fica como follow-up se >10 admins.

## Applicable Constraints

Do blueprint + ADRs + estado real:

- **Python 3.12 + FastAPI >=0.115** (blueprint, decisão 1).
- **asyncpg >=0.30**, `statement_cache_size=0` em ambos os pools (Supavisor compat — herdado).
- **Redis 7** disponível para cache de Performance + idempotência de feed.
- **RLS obrigatório** (ADR-011): tabelas existentes mantêm `FORCE ROW LEVEL SECURITY` + `tenant_id` policy. Novas tabelas (`traces`, `trace_steps`, `routing_decisions`) NÃO têm RLS — admin only via `pool_admin`.
- **PT-BR em prose, EN em código** (CLAUDE.md).
- **Porta API = 8050**. Frontend `NEXT_PUBLIC_API_URL`.
- **Branch naming**: `epic/prosauai/008-admin-evolution` — JÁ EXISTE no repo externo (criada manualmente). Reaproveitar.
- **Supabase compat**: novos objetos só em schemas nossos (`public` aceito como drift, nunca `auth`).
- **Variável RLS**: `app.current_tenant_id` (helper `public.tenant_id()`) — usado pelo pipeline existente, não tocado neste épico.
- **dbmate** como migration tool (epic 007 estabelecido).
- **shadcn/ui Chart wrapper** (não Recharts direto) para coerência de tokens `--chart-1..5`.

## Suggested Approach

Implementar em ~10 PRs sequenciais, cada um deixando o sistema funcional:

**PR 0 — F0 pré-voo**: ADR para `traces`/`trace_steps`, ADR para `routing_decisions` + RLS exception rationale, decisão de cost mapping por modelo, audit no pipeline (`rg "metadata\["` confirma quais campos são tocados hoje). Sem código.

**PR 1 — F1.1 schemas**: 3 migrations dbmate (`traces`, `trace_steps`, `routing_decisions`, `ALTER conversations ADD last_message_*`). Índices BRIN em `started_at`, BTREE em `(tenant_id, started_at DESC)`. Smoke test: migrations up + down + up funcionam.

**PR 2 — F1.2 pipeline instrumentation**: buffer `List[StepRecord]` em `Pipeline.execute()`, batch INSERT em finalizador, cost calc via `pricing.py`, propagação de `trace_id` do OTel context. Suite epic 005 deve passar 100%. **Gate de merge**: smoke test 24h em staging.

**PR 3 — F1.3 routing persistence**: hook em `RoutingEngine.evaluate()` para INSERT em `routing_decisions`. Async fire-and-forget (não bloqueia decisão). Suite router epic 004 deve passar.

**PR 4 — F1.4 inbox denormalization**: trigger SQL OU update Python no save_outbound/save_inbound do pipeline para popular `conversations.last_message_*`. Backfill script para conversas existentes (~30 min em prod). Suite epic 005 passa.

**PR 5 — F2.1 backend Conversations + Customers + Tenants endpoints**: 7 endpoints (`GET /admin/conversations`, `/admin/conversations/{id}`, `/admin/conversations/{id}/messages`, `PATCH /admin/conversations/{id}`, `GET /admin/customers`, `/admin/customers/{id}`, `GET /admin/tenants`). Cursor-based pagination. Pydantic response models.

**PR 6 — F2.2 backend Trace Explorer + Performance + Routing + Audit endpoints**: `GET /admin/traces`, `/admin/traces/{trace_id}`, `/admin/metrics/overview`, `/admin/metrics/activity-feed`, `/admin/metrics/performance` (Redis cache 5min), `/admin/metrics/tenant-health`, `/admin/routing/rules`, `/admin/routing/decisions`, `/admin/routing/stats`, `/admin/agents` + `/admin/agents/{id}/prompts`, `/admin/audit`.

**PR 7 — F3.1 frontend Sidebar + Overview enriched + ContactProfile + ConversationList + Thread**: estender sidebar para 8 itens, refatorar Overview com KPI cards (sparkline + delta), 3-column Conversations layout. Componentes `intent-badge`, `quality-score-badge`, `sla-indicator` no `components/ui/`.

**PR 8 — F3.2 frontend Trace Explorer**: lista + waterfall (barras proporcionais) + step-detail (accordion + json-tree component). `json-tree.tsx` é reutilizado em outras telas.

**PR 9 — F3.3 frontend Performance AI**: 4 charts (intent distribution barH, quality trend area+line, latency waterfall stacked barH, error heatmap 24×7 grid) + cost bars. shadcn Chart wrapper.

**PR 10 — F3.4 frontend Agents + Prompts + Routing + Tenants + Audit + polish**: tabs internas em Agents, prompt diff view, donut de routing, audit timeline. Polish, e2e Playwright para 3 fluxos críticos (login → conversation → trace).

**Princípios operacionais:**

- **Pipeline é intocável**: PR 2 + 3 + 4 mexem em código de epic 005/004 — 100% dos testes existentes passam ou abort.
- **Backend antes de frontend**: PR 5+6 (endpoints prontos) antes de PR 7+. Frontend consome contratos OpenAPI gerados via `packages/types`.
- **Cut-line documentado**: ao fim do PR 8 (Trace Explorer pronto), reavaliar se Performance/Agents/Routing/Audit cabem em 8 semanas. Se não, cortar para épico 009.
- **Spec doc é ground truth para layouts**: cada PR de frontend referencia seção específica de `reference-spec.md`.
- **Follow-ups registrados**:
  - tsvector + GIN em `messages.content` quando >10k conversas (Q16).
  - Phoenix API enrichment do Trace Explorer (épico futuro).
  - Tabela DB editável de pricing por modelo quando >3 modelos.
  - Cookie httpOnly + refresh token (segue follow-up de 007).
  - Schema cleanup ADR-024 (move tabelas para `prosauai`).
  - Materialized views se Performance endpoints P95 >2s.
