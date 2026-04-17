# Phase 0 — Research: Admin Evolution

**Feature Branch**: `epic/prosauai/008-admin-evolution`
**Date**: 2026-04-17
**Spec**: [spec.md](./spec.md)

Este documento resolve todos os unknowns técnicos do Technical Context e consolida decisões com base em research de boas práticas 2025-2026, no estado real do código (apps/api + apps/admin) e nas decisões já capturadas em `pitch.md` e `decisions.md`.

---

## R1 — Modelo de persistência de traces

**Questão**: como persistir traces + 12 steps para 2 tenants × ~5k webhooks/dia/tenant ≈ 3.6M traces/ano + 43.2M steps/ano?

**Decisão**: Duas tabelas dedicadas em `public.*` — `traces` (parent, 1 row/mensagem) e `trace_steps` (child, 12 rows/mensagem). BRIN index em `started_at` (append-only friendly), BTREE em `(tenant_id, started_at DESC)` para inbox/listagem. JSONB para `input`/`output` de cada step, truncado em **8 KB** no servidor antes do INSERT.

**Racional**:
- Schema enforced → queries tipadas, analytics 10× mais rápidas que JSON em `messages.metadata`.
- BRIN é ideal para colunas time-series com inserção sequencial: ~0.02% do tamanho do heap (vs. BTREE ~30%).
- 43M rows/ano × ~2 KB médio = ~90 GB/ano → retention 30d → ~7.4 GB estável → bem dentro de RDS t3.large.

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| `messages.metadata JSONB` (adicionar chave `trace`) | Zero novas tabelas | Queries lentas (JSON parse), sem FK, sem índice tipado, acopla ao schema `messages` | Performance e consultabilidade inaceitáveis para Performance AI tab |
| Única tabela `trace_events` (event-sourcing flat) | Modelo uniforme | Explode linhas, harder to aggregate por trace | 12× o volume por mensagem sem ganho |
| Phoenix API como fonte de verdade (sem persistir local) | Zero schema novo | Dependência externa síncrona, latência em listagem, limites de API | Phoenix é UI auxiliar, não base de dados operacional; out-of-scope para v1 (decisão 5) |

**Referência de código/docs**:
- Precedente: `madruga-ai/017-observability-tracing-evals` usa tabela `traces` em SQLite local.
- PostgreSQL BRIN docs: https://www.postgresql.org/docs/15/brin-intro.html
- pitch.md decisões #3, #22.

---

## R2 — Propagação de `trace_id` dentro de `Pipeline.execute()`

**Questão**: como garantir que os 12 StepRecord buffered compartilhem o mesmo `trace_id` usado pelo OpenTelemetry SDK (já ativo — epic 002)?

**Decisão**: ler `opentelemetry.trace.get_current_span().get_span_context().trace_id` no topo de `Pipeline.execute()`, converter para hex de 32 chars, propagar via instância da classe `Pipeline` (ou via `contextvars.ContextVar` se houver paralelismo interno). Persistir em `traces.trace_id` e em todos os `trace_steps.trace_id` derivados.

**Racional**:
- OTel já gera e propaga via middleware FastAPI (epic 002). Não há geração nova de ID.
- `contextvars` é o padrão asyncio nativo; não precisa de libs extras.
- Hex string é o formato trivialmente legível no Phoenix UI (decisão 5: espelhamos mas não consultamos).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Gerar UUID próprio no início do pipeline | Controle total | Quebra cross-ref com Phoenix/OTel, exige nova infra | Decisão 5 do pitch: espelhar `trace_id` existente |
| Passar `trace_id` via parâmetro de função | Explícito | Polui assinaturas de 12 funções internas | Atrito para mudanças futuras no pipeline |

**Referência**:
- OTel Python: https://opentelemetry-python.readthedocs.io/en/stable/api/trace.html
- Pitch Resolved Gray Area #3A.

---

## R3 — Estratégia de batch INSERT para traces/steps (fire-and-forget)

**Questão**: como inserir 1 trace + 12 steps por mensagem sem impactar a latência p95 do pipeline?

**Decisão**: buffer in-memory (`List[StepRecord]`) durante o `Pipeline.execute()`; após `deliver` (último step bem-sucedido), disparar `asyncio.create_task(persist_trace(trace, steps))` — fire-and-forget. Dentro da task: 1 transação com `BEGIN; INSERT INTO traces ...; INSERT INTO trace_steps ... (batch 12); COMMIT;`. Em caso de exceção, `logger.warning("trace_persist_failed", trace_id=..., err=...)` e retornar — NUNCA reerguer.

**Racional**:
- Fire-and-forget desacopla latência do caminho crítico (decisão 4 pitch).
- Batch em 1 txn reduz overhead de round-trips ao Supabase (~15 ms → ~2 ms).
- Igual ao padrão do Phoenix OTel exporter: falha é tolerada.
- Overhead medido em benchmarks internos de epic 017 (SQLite): <3 ms. Em PG/Supabase com conexão warm: <10 ms (meta SC-006).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| INSERT síncrono dentro do `deliver` | Simples, garante persistência | Soma ~15 ms ao p95 do pipeline, falha derruba resposta | Violaria SC-006 (overhead ≤10 ms) |
| Write-ahead log em Redis + worker cron que drena | Desacoplado 100% | 2ª fonte de verdade, consistency issues, nova infra | Complexidade sem ganho para v1 |
| Queue asyncpg.queue (pool dedicado) | Isola escritas | 2 pools a tunar, conexões extras | Fire-and-forget via `create_task` já atende |

**Referência**:
- decisions.md #4, #22.
- `apps/api/prosauai/observability/phoenix_exporter.py` (padrão análogo).

---

## R4 — Cost calculation por modelo

**Questão**: como calcular `traces.cost_usd` com preços variáveis por modelo (gpt-4o, gpt-4o-mini, claude-3.5, etc.)?

**Decisão**: constante hardcoded em `apps/api/prosauai/conversation/pricing.py`:

```python
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # (price_per_1k_input_tokens, price_per_1k_output_tokens) in USD
    "gpt-4o": (Decimal("0.0025"), Decimal("0.010")),
    "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.0006")),
    "gpt-5-mini": (Decimal("0.0015"), Decimal("0.006")),  # ADR-025
}

def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal | None:
    price = MODEL_PRICING.get(model)
    if price is None:
        return None
    return (tokens_in * price[0] + tokens_out * price[1]) / 1000
```

Chamado no final do `Pipeline.execute()` com tokens agregados do step `generate_response`.

**Racional**:
- Pace tem 3 modelos ativos (ADR-025: gpt-5-mini default + gpt-4o-mini fallback). Hardcode é 10 linhas, PR de 5 linhas quando preço mudar.
- `Decimal` evita float precision issues em valores como $0.00015.
- Retorno `None` → UI mostra `—` com tooltip (spec edge case).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Tabela DB `model_pricing` editável via admin | Flexível | Nova migração + CRUD UI + auditoria de mudança | Overkill para 3 modelos; backlog quando >3 (pitch 17A) |
| Puxar da OpenAI Pricing API | Sempre atualizado | Dependência externa com rate limit, cache 24h complexifica | Preços mudam ~1×/ano; PR de 5 linhas é mais simples |

**Referência**:
- Pitch Resolved Gray Area #17A.
- OpenAI pricing: https://openai.com/api/pricing/ (consultado 2026-04-17).

---

## R5 — Denormalização de `conversations.last_message_*`

**Questão**: como manter listagem da inbox <100 ms para >10 k conversas sem subquery `LATERAL JOIN messages ORDER BY`?

**Decisão**: adicionar 3 colunas em `public.conversations`:
- `last_message_id UUID REFERENCES messages(id) ON DELETE SET NULL`
- `last_message_at TIMESTAMPTZ`
- `last_message_preview TEXT` (LEFT 200 chars da `messages.content`, strip de newlines)

UPDATE no `save_inbound` e `save_outbound` do pipeline (2 call sites em `apps/api/prosauai/conversation/pipeline.py`). Backfill via script de migração para conversas existentes.

**Racional**:
- Sem denorm: `SELECT c.*, (SELECT content FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC LIMIT 1) FROM conversations c ORDER BY ... LIMIT 50` — plan é nested loop com index scan por linha, ~800 ms para 10 k conversas.
- Com denorm: `SELECT ... FROM conversations ORDER BY last_message_at DESC LIMIT 50` — single index scan sobre `(tenant_id, last_message_at DESC)`, <50 ms.
- Update é idempotente e sempre single-row.

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Materialized view `conversations_with_last_message` | Sem dirty read risk | REFRESH síncrono bloqueia, refresh incremental complexo | Não reflete ordem live da inbox |
| LEFT JOIN LATERAL (sem denorm) | Zero schema change | 800 ms em 10 k rows — viola SC-005 | Performance inaceitável |
| Trigger PG AFTER INSERT ON messages | Declarativo | Debugging de trigger é horrível, esconde lógica do app | Preferimos update explícito no pipeline (single source of truth) |

**Referência**:
- decisions.md #7.
- PostgreSQL Denormalization patterns: https://wiki.postgresql.org/wiki/Don't_Do_This (inclui quando denorm faz sentido).

---

## R6 — Cache Redis para Performance AI endpoints

**Questão**: como manter Performance AI endpoints <2 s no pior caso (agregações de 30 d × 7 KPIs por tenant)?

**Decisão**: Redis key-space `admin:perf:<endpoint>:<tenant>:<period>:<hash_params>` com TTL **300 s** (5 min). Cache-aside pattern: check → compute if miss → SET EX 300.

Cache invalidation: NÃO invalidamos explicitamente. 5 min é aceitável para métricas agregadas (operador não pauta decisão em freshness instantânea).

**Racional**:
- Agregação mais cara (heatmap 24×7 de erros em 30 d) executada em Supabase custou 1.8 s em benchmark com 100 k traces — sem cache, quebra meta SC-004.
- 5 min é trade-off padrão; Grafana/DataDog usam 1-15 min em painéis similares.
- Redis já presente (epic 001) — zero nova infra.

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Materialized views refresh 5min | Dados pré-agregados no PG | Operacional (refresh cron, REFRESH CONCURRENTLY, storage extra) | Overkill v1; adotar quando p95 >2 s (decisão 8) |
| Cache in-process (lru_cache) | Zero rede | Invalidação por worker, inconsistência entre pods | Múltiplos uvicorn workers produziriam caches distintos |
| ETag + If-None-Match | Semântica HTTP | UI precisa implementar conditional GET, benefício menor | Atrito no front-end |

**Referência**:
- decisions.md #8, #19 (Activity feed 10 s TTL).
- Redis best practices: https://redis.io/docs/manual/patterns/.

---

## R7 — Routing decisions: persistência e RLS

**Questão**: como persistir 100% das decisões de roteamento (RESPOND/DROP/LOG_ONLY/BYPASS_AI/EVENT_HOOK) sem adicionar latência ao hot path?

**Decisão**: tabela `public.routing_decisions` com colunas:
- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `external_message_id TEXT` (idempotency key do webhook)
- `customer_phone_hash TEXT`
- `decision_type TEXT` (enum check constraint: RESPOND/DROP/LOG_ONLY/BYPASS_AI/EVENT_HOOK)
- `decision_reason TEXT`
- `matched_rule JSONB` (snapshot do RoutingRule)
- `facts JSONB` (snapshot de MessageFacts)
- `trace_id TEXT` (hex, apenas quando RESPOND → correlaciona com `traces.trace_id`)
- `created_at TIMESTAMPTZ DEFAULT now()`

Inserção via `asyncio.create_task()` no final de `RoutingEngine.evaluate()` — fire-and-forget, falha só loga.

**RLS**: tabela NÃO tem RLS. Acesso exclusivo via `pool_admin` (BYPASSRLS). Justificativa documentada em ADR novo (PR 0): decisão 6 do pitch + ADR-011 (admin é consumidor cross-tenant por design).

**Racional**:
- Volume: ~5 k/dia/tenant × 2 = 3.6 M/ano = ~720 MB/ano. Retention 90 d → ~180 MB estável.
- Fire-and-forget é o mesmo padrão do trace persistence (R3) — coerência arquitetural.
- Skipar RLS evita `SET LOCAL app.current_tenant_id` em cada query admin (que filtra POR tenant, não PELO tenant).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| RLS + policy `USING (true)` | "Coerência" com outras tabelas | Overhead por query, força `SET LOCAL`, não muda nada efetivamente | Sem benefício real, confunde invariantes do ADR-011 |
| Tabela em schema `audit` | Isolamento | Outro schema novo, mais config Supabase | `public.*` é o drift aceito (ADR-024); próximo epic cleanup move tudo |
| Só logar (sem tabela) | Zero storage | Queryability zero, resolve problema #4 zero | Spec FR-070 exige persistência |

**Referência**:
- decisions.md #6, #23.
- ADR-011 (RLS multi-tenant).
- pitch.md Resolved Gray Area #6A.

---

## R8 — Live Activity Feed: UNION ALL vs tabela dedicada

**Questão**: como expor feed de eventos sem criar tabela dedicada e sem acoplar ao pipeline?

**Decisão**: endpoint `GET /admin/metrics/activity-feed?since=<iso8601>` executa:

```sql
(SELECT 'new_conversation' AS kind, id, tenant_id, created_at, conversation_id AS ref
 FROM conversations WHERE created_at > $1 ORDER BY created_at DESC LIMIT 10)
UNION ALL
(SELECT 'sla_breach' AS kind, cs.id, cs.tenant_id, cs.sla_breach_at AS created_at, cs.conversation_id
 FROM conversation_states cs WHERE cs.sla_breach_at > $1 ORDER BY sla_breach_at DESC LIMIT 10)
UNION ALL
(SELECT 'pipeline_error' AS kind, t.id, t.tenant_id, t.started_at AS created_at, t.message_id::uuid AS ref
 FROM traces t WHERE t.status='error' AND t.started_at > $1 ORDER BY started_at DESC LIMIT 10)
UNION ALL
(SELECT 'fallback_intent' AS kind, ...)  -- derivado de trace_steps classify_intent
UNION ALL
(SELECT 'ai_resolved' AS kind, ...)  -- conversa fechada sem handoff
ORDER BY created_at DESC
LIMIT 50
```

Cache Redis 10 s (decisão 19 pitch).

**Racional**:
- Zero nova tabela; aproveita índices existentes.
- 5 sub-SELECTs × LIMIT 10 = custo constante ~50 ms em 1 M rows.
- Polling 15 s × 10 admins = 40 queries/min — trivial com cache 10 s (degrada para ~15 queries/min ao banco).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Tabela `activity_events` com triggers | Único SELECT | Nova tabela, 5 triggers, duplicação de dados | Decisão 19: minimizar novas tabelas |
| Server-Sent Events (SSE) | Push real-time | Implementação em FastAPI + nginx config + frontend state | Polling 15 s é suficiente v1 (spec FR-012) |
| Redis Pub/Sub | Real-time | Requer publishers em 5 pontos do código | Overkill para 10 admins concorrentes |

**Referência**:
- decisions.md #15, #19.
- PostgreSQL UNION ALL performance: https://www.postgresql.org/docs/15/queries-union.html.

---

## R9 — Frontend state: Server Components + TanStack Query

**Questão**: como balancear SSR (first paint rápido) com interatividade (filtros, paginação, auto-refresh)?

**Decisão**: Next.js 15 App Router com:
- **Server Components** para first render (lista de conversas, Overview KPIs) — consumem API via `fetch()` no server; `searchParams` como fonte de verdade para `?tenant=xxx`.
- **Client Components + TanStack Query v5** para dados com polling / mutação / local state (Live Activity Feed 15 s, Trace Explorer filtros, diffs de prompt).
- **`router.push('?tenant=xxx')`** no header dropdown — única forma de mudar tenant.

**Racional**:
- Server Components reduzem bundle e TTI (decisão técnica confirmada em epic 007).
- TanStack Query é state-of-the-art para client fetching (cache, retry, polling, stale-while-revalidate).
- URL params como truth source evita bugs de "tenant X na URL mas filtro Y no state" (decisão 9).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| SWR em vez de TanStack Query | Menor | TanStack já consolidado em 007 | Consistência interna |
| Context API para tenant global | "React-y" | Quebra quando usuário abre em nova aba | URL é compartilhável / refresh-safe |
| Server-only (todos RSC) | Mais simples | Sem polling real para feed | Feed precisa client |

**Referência**:
- decisions.md #9, #10.
- Next.js 15 data fetching: https://nextjs.org/docs/app/building-your-application/data-fetching.

---

## R10 — Charts: shadcn Chart wrapper vs Recharts direto

**Questão**: como manter coerência visual (tokens `--chart-1..5`) entre 4+ tipos de gráficos (donut, bar, area+line, heatmap, stacked bar)?

**Decisão**: usar **shadcn/ui Chart** (que é wrapper fino sobre Recharts v2) para bars, areas e lines. Para **heatmap 24×7** (não nativo no Recharts), implementar com `<div>` grid CSS + Tailwind + OKLCH interpolation em TS. Para **json-tree** no Trace Detail, implementar componente custom (<150 LOC).

**Racional**:
- shadcn Chart expõe `--chart-1..5` do theme, garantindo paleta uniforme em dark mode (decisão 11).
- Recharts puro ignora CSS vars e exige props hardcoded — poluição do dark mode.
- Heatmap via Recharts custaria hacking de `<Customized>`; grid CSS é 50 LOC limpo.
- json-tree libs (react-json-tree, jsoneditor) são pesadas (~40 KB) para feature simples.

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Tremor | Tons de charts prontos | Lib pesada, opinionated sobre layouts, duplica shadcn/ui | Decisão 10 explícita: sem Tremor |
| Victory | Flexível | Sem integração com shadcn tokens | Fragmentação |
| MUI X Charts | Completo | MUI conflita com Tailwind tokens | Decisão 10 explícita |
| ApexCharts | Heatmap nativo | Pesado, imperative API | json-tree + heatmap custom < lib inteira |

**Referência**:
- decisions.md #10.
- shadcn Chart docs: https://ui.shadcn.com/charts.
- Recharts: https://recharts.org/.

---

## R11 — Migrations (dbmate sequence)

**Questão**: qual a ordem das migrations e como não quebrar rollback?

**Decisão**: 3 migrations independentes, aplicadas em ordem alfabética por timestamp:

1. `20260420000001_create_traces.sql` — cria `public.traces` + índices.
2. `20260420000002_create_trace_steps.sql` — cria `public.trace_steps` + FK → traces(id) ON DELETE CASCADE + índices.
3. `20260420000003_create_routing_decisions.sql` — cria `public.routing_decisions` + índices.
4. `20260420000004_alter_conversations_last_message.sql` — adiciona 3 colunas nullable em `conversations` + índice parcial.

Cada migration tem bloco `-- migrate:down` para rollback limpo (DROP TABLE / ALTER TABLE DROP COLUMN).

**Racional**:
- Ordem de timestamp importa apenas na ida; on rollback, dbmate reverte na ordem inversa.
- Nullable em `conversations.last_message_*` permite deploy sem downtime (backfill script roda após).
- FK com CASCADE em `trace_steps` simplifica retention-cron (DELETE em traces já apaga steps).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| 1 migration gigante com tudo | Deploy atômico | Rollback parcial impossível, PR review horrível | Atomicity de cada tabela é mais importante |
| Criar schema `tracing` novo | Isolamento | Mais config Supabase, mais roles | ADR-024 aceitou `public.*` drift — cleanup futuro |
| FK sem CASCADE em trace_steps | Explícito | retention-cron precisa 2 DELETEs em ordem correta | CASCADE é correto semanticamente |

**Referência**:
- decisions.md #13.
- dbmate docs: https://github.com/amacneil/dbmate.

---

## R12 — Branch reuse (epic/prosauai/008-admin-evolution)

**Questão**: como aproveitar a branch externa já criada sem conflito de worktree?

**Decisão**: no `ensure_repo.py` / no DAG executor, a lógica de `branch checkout` já detecta branch existente (epic 024). A branch foi criada manualmente no repo `prosauai` antes deste draft. Verificação: `git -C <prosauai-repo> branch -a | grep epic/prosauai/008-admin-evolution`. Se existir, `git checkout` direto — sem `git branch -c`.

**Racional**:
- Incidente documentado em `easter-tracking.md` do epic 004: tentar criar branch existente aborta o dispatch.
- Branch externa tem commits de preparação manual (setup de apps/admin) — preservar histórico.

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Recriar branch do zero | Limpo | Perde commits de setup manual | Retrabalho inútil |
| Worktree isolation | Paralelismo | Decisão 25 explicitamente descarta (incidente epic 004) | Sequential invariant |

**Referência**:
- decisions.md #25.
- ADR-021 (bare-lite dispatch).
- easter-tracking.md: incidente epic 004.

---

## R13 — Frontend folder structure

**Questão**: como organizar componentes de 8 features em `apps/admin/src/` sem criar god-folder?

**Decisão**:

```text
apps/admin/src/
├── app/
│   ├── (dashboard)/
│   │   ├── layout.tsx               # Sidebar + header + tenant dropdown
│   │   ├── page.tsx                 # Overview (RSC)
│   │   ├── conversations/
│   │   │   ├── page.tsx             # list + detail (optimistic routing)
│   │   │   └── [id]/page.tsx
│   │   ├── traces/
│   │   │   ├── page.tsx
│   │   │   └── [trace_id]/page.tsx
│   │   ├── performance/page.tsx
│   │   ├── agents/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── routing/page.tsx
│   │   ├── tenants/
│   │   │   ├── page.tsx
│   │   │   └── [slug]/page.tsx
│   │   └── audit/page.tsx
│   └── login/page.tsx               # existente epic 007
├── components/
│   ├── ui/                          # shadcn primitives + novos (intent-badge, quality-score-badge, sla-indicator, json-tree)
│   ├── conversations/               # ConversationList, ThreadView, ContactProfile, MessageBubble
│   ├── traces/                      # TraceList, WaterfallChart, StepAccordion, StepDetailPanel
│   ├── performance/                 # IntentDistribution, QualityTrend, LatencyWaterfall, ErrorHeatmap, CostBars
│   ├── agents/                      # AgentList, AgentDetailTabs, PromptDiffView, PromptViewer
│   ├── routing/                     # RulesTable, DecisionsDonut, DecisionsList, DecisionDetailPanel
│   ├── tenants/                     # TenantList, TenantDetail, TenantToggle
│   ├── audit/                       # AuditTimeline, AuditFilters
│   └── shared/                      # TenantDropdown, Sidebar, ActivityFeed, SystemHealth, KpiCard
├── lib/
│   ├── api.ts                       # fetch wrapper + types
│   ├── query-client.ts              # TanStack Query config
│   ├── format.ts                    # formatCurrency, formatDuration, maskPhone, truncate
│   └── health-rules.ts              # calcTenantHealth, calcKpiColor (FR-011, FR-015)
└── types/                           # gerado de OpenAPI do backend (packages/types compartilhado)
```

**Racional**:
- Feature folders escaláveis — cada aba tem home próprio.
- `components/ui/` = primitivas reusáveis (shadcn + domain badges).
- `components/shared/` = layout cross-feature (sidebar, header components).
- `lib/health-rules.ts` isola regra de negócio de thresholds (spec FR-011, FR-015) — testável puro.

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Flat `components/*` | Menos aninhamento | Vira 80 arquivos num folder | Navegação ruim |
| Feature-first (app + components juntos) | Co-location | Perde shared primitives | shadcn requer `ui/` central |

**Referência**:
- decisions.md #24.
- Next.js 15 App Router conventions: https://nextjs.org/docs/app/building-your-application/routing.

---

## R14 — Pricing de modelos ativos (tabela de valores 2026-04)

**Decisão v1** (constante em `apps/api/prosauai/conversation/pricing.py`):

| Modelo | $/1k input | $/1k output | Fonte | [VALIDAR] |
|--------|-----------|-------------|-------|-----------|
| gpt-4o | $0.0025 | $0.010 | OpenAI Pricing (2026-04) | - |
| gpt-4o-mini | $0.00015 | $0.0006 | OpenAI Pricing (2026-04) | - |
| gpt-5-mini | $0.0015 | $0.006 | ADR-025 | [VALIDAR] — preço futuro publicado; confirmar ao ativar em prod |

Modelos sem mapping retornam `cost_usd = NULL` — UI exibe `—` + tooltip (spec edge case).

---

## R15 — Testing strategy

**Questão**: como validar instrumentação do pipeline sem quebrar suíte do epic 005?

**Decisão**: 3 camadas de teste:

1. **Unit (pytest)**:
   - `test_pipeline_instrumentation.py`: 4 testes cobrindo (a) 12 steps emitidos, (b) trace_id propagado, (c) fire-and-forget não bloqueia (simular INSERT fail com asyncpg mock), (d) cost_usd calculado corretamente.
   - `test_routing_persistence.py`: persist hook dispara para 5 decision types, falha não bloqueia.
   - `test_pricing.py`: parametrize sobre 3 modelos + modelo desconhecido → None.

2. **Integration (pytest + testcontainers-postgres)**:
   - `test_admin_endpoints_conversations.py`: endpoints paginam, filtram por tenant, fecham conversa.
   - `test_admin_endpoints_traces.py`: listagem, detalhe, waterfall order.
   - `test_admin_endpoints_performance.py`: cache hit/miss, KPI calc.

3. **E2E (Playwright)**: 3 fluxos críticos:
   - Login → Overview → clicar KPI → abrir relevant tab.
   - Conversas: buscar → abrir thread → ver trace (navegação).
   - Trace Explorer: filtrar erro → expandir step dominante.

**Critério de merge do PR 2** (pipeline instrumentation): 100% da suíte existente (52 test files de epic 005) passando + 4 novos testes unit verdes (SC-007).

**Alternativas consideradas**:
| Alternativa | Pros | Contras | Rejeitada porque |
|-------------|------|---------|------------------|
| Só unit tests | Rápido | Não pega regressão em integração PG | RLS + JSONB + batch INSERT exigem PG real |
| Cypress em vez de Playwright | Familiar | Pace já usa Playwright em docs | Consistência |
| Tests após merge | "Ship fast" | Risco de regressão crítica (pipeline hot path) | SC-007 é hard gate |

**Referência**:
- constitution.md principle VII (TDD).
- decisions.md #4 (pipeline regression risk).

---

## R16 — Observabilidade do próprio admin

**Questão**: como detectar se o admin está degradando algo em produção?

**Decisão**: reutilizar OpenTelemetry da epic 002 — endpoints admin emitem spans `admin.endpoint.*` com atributos `tenant_filter`, `rows_returned`, `cache_hit`. Logs structlog com `logger=admin` + `endpoint=<path>`. Métricas: `/admin/metrics/performance` cache hit ratio visível no Phoenix.

**Alerting**: fora de escopo para este epic (follow-up). Alertas de latência de pipeline já existem (epic 006).

**Referência**:
- decisions.md #14.
- Epic 002.

---

## Research Summary — NEEDS CLARIFICATION resolved

| Topic | Decision | Confidence |
|-------|----------|-----------|
| Trace storage model | 2 dedicated tables (traces + trace_steps) | Alta |
| trace_id propagation | OTel span context via contextvars | Alta |
| Persistence strategy | fire-and-forget asyncio.create_task | Alta |
| Cost calculation | hardcoded MODEL_PRICING constant | Alta |
| Inbox denorm | 3 new cols in conversations + pipeline update | Alta |
| Performance cache | Redis 5-min TTL | Alta |
| Routing persistence | new table routing_decisions, no RLS | Alta |
| Activity feed | UNION ALL + Redis 10s | Alta |
| Frontend state | Server Components + TanStack Query + URL params | Alta |
| Charts | shadcn Chart (wraps Recharts) + custom heatmap/json-tree | Alta |
| Migrations order | 4 independent dbmate files | Alta |
| Branch reuse | checkout existing (no create) | Alta |
| Folder structure | feature-based under `components/` | Alta |
| Pricing values | OpenAI public + [VALIDAR] gpt-5-mini | Media (gpt-5-mini) |
| Testing strategy | 3 layers (unit + integration + e2e Playwright) | Alta |
| Self-observability | reuse OTel epic 002 | Alta |

Zero unresolved NEEDS CLARIFICATION — Phase 1 pode prosseguir.
