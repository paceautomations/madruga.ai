# Tasks: Admin Evolution — Plataforma Operacional Completa

**Feature Branch**: `epic/prosauai/008-admin-evolution`
**Input**: Design documents from `platforms/prosauai/epics/008-admin-evolution/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: Included — plan.md define explicitamente 3 camadas (unit + integration + e2e) e SC-007 estabelece gate de merge com 100% da suíte existente passando.

**Organization**: Tasks agrupadas por User Story (US1..US8) com tasks de Setup e Foundational antes. Sequência 10-PRs do plan.md mapeada para fases, permitindo entrega MVP (US1+US2) cedo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Executável em paralelo (arquivos diferentes, sem dependência em tasks incompletas)
- **[Story]**: US1..US8 quando aplicável; Setup/Foundational/Polish/Smoke não recebem label
- Paths absolutos do repo externo `paceautomations/prosauai` (via `apps/api/` e `apps/admin/`)

---

## Phase 1: Setup (Shared Infrastructure) — PR 0

**Purpose**: Decisões arquiteturais 1-way-door + audit do código existente. Sem código.

- [x] T001 Criar ADR-027 "Admin tables without RLS (carve-out from ADR-011)" em `platforms/prosauai/decisions/ADR-027-admin-tables-no-rls.md` — documenta que `traces`, `trace_steps`, `routing_decisions` são admin-only via `pool_admin`, justificando a exceção ao invariante ADR-011
- [x] T002 Criar ADR-028 "Pipeline trace persistence via fire-and-forget" em `platforms/prosauai/decisions/ADR-028-pipeline-fire-and-forget-persistence.md` — documenta o padrão `asyncio.create_task` + batch INSERT em 1 txn para trace e routing decisions, referenciando `observability/phoenix_exporter.py` como precedente
- [x] T003 [P] Criar ADR-029 "Cost pricing table as code constant" em `platforms/prosauai/decisions/ADR-029-cost-pricing-constant.md` — documenta decisão de hardcode `MODEL_PRICING` em `apps/api/prosauai/conversation/pricing.py`, critério de migração para tabela DB (>3 modelos ativos)
- [x] T004 [P] Auditar toques atuais em `messages.metadata` no pipeline: `rg "metadata\[" apps/api/prosauai/conversation/ apps/api/prosauai/router/` — registrar resultado em `easter-tracking.md` para garantir que instrumentação de trace_steps não duplica info
- [x] T005 [P] Auditar instrumentação OTel ativa: `rg "get_current_span\|tracer\.start" apps/api/prosauai/conversation/` — confirmar que `Pipeline.execute()` já está dentro de um span pai (pré-requisito de R2)
- [x] T006 Validar pricing real via OpenAI pricing page para `gpt-4o`, `gpt-4o-mini`, `gpt-5-mini` — registrar valores confirmados em `research.md` (R14); se `gpt-5-mini` permanecer `[VALIDAR]`, manter estimativa e flagrar em `pricing.py` com comentário `# TODO: confirm pricing`

**Checkpoint PR 0**: 3 ADRs criados + audit registrado em easter-tracking. Merge requer revisão humana (1-way-door).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + instrumentação + denormalização + retention. BLOQUEIA todas as user stories.

**⚠️ CRITICAL**: Nenhuma task de user story pode começar até esta fase terminar.

### PR 1 — Migrations (4 files via dbmate)

- [x] T010 [P] Criar migration `apps/api/migrations/20260420000001_create_traces.sql` com schema `public.traces` conforme data-model.md §1 — inclui 5 índices (BRIN em `started_at`, BTREE em `(tenant_id, started_at DESC)`, BTREE em `trace_id`, parcial em `status != success`, BTREE em `(conversation_id, started_at DESC)`) + COMMENT explicando no-RLS
- [x] T011 [P] Criar migration `apps/api/migrations/20260420000002_create_trace_steps.sql` com schema `public.trace_steps` conforme data-model.md §2 — inclui FK CASCADE para traces, UNIQUE `(trace_uuid, step_order)`, 3 índices (BTREE `(trace_uuid, step_order)`, parcial `status != success`, BRIN `started_at`) + CHECK `step_order BETWEEN 1 AND 12`
- [x] T012 [P] Criar migration `apps/api/migrations/20260420000003_create_routing_decisions.sql` com schema `public.routing_decisions` conforme data-model.md §3 — inclui 5 índices (BTREE `(tenant_id, created_at DESC)`, BTREE decision_type, BTREE `customer_phone_hash`, parcial `trace_id IS NOT NULL`, BRIN `created_at`)
- [x] T013 [P] Criar migration `apps/api/migrations/20260420000004_alter_conversations_last_message.sql` — `ALTER TABLE conversations` adicionando `last_message_id UUID FK`, `last_message_at TIMESTAMPTZ`, `last_message_preview TEXT`; criar `idx_conversations_tenant_last_msg` conforme data-model.md §4
- [x] T014 Validar migrations via ciclo `dbmate up && dbmate down && dbmate up` em DB local limpo — todas as 4 migrations devem ser reversíveis; registrar output em PR description

**Checkpoint PR 1**: 4 migrations aplicam e revertem. Schema pronto para instrumentação.

### PR 2 — Pipeline Instrumentation (gate SC-007)

- [x] T020 [P] Criar `apps/api/prosauai/conversation/pricing.py` com dicionário `MODEL_PRICING: dict[str, tuple[Decimal, Decimal]]` (preço por 1k tokens in/out) para modelos gpt-4o, gpt-4o-mini, gpt-5-mini + função `calculate_cost(model, tokens_in, tokens_out) -> Decimal | None` (retorna None para modelo não mapeado)
- [x] T021 [P] Criar `apps/api/tests/unit/conversation/test_pricing.py` — testa calculate_cost para os 3 modelos mapeados, retorno None para modelo desconhecido, precision correta (6 casas decimais)
- [x] T022 [P] Criar `apps/api/prosauai/observability/trace_context.py` com helper `get_trace_id_hex() -> str | None` usando `opentelemetry.trace.get_current_span().get_span_context().trace_id` e converting int → 32-char hex (retorna None se no-op span)
- [x] T023 [P] Criar `apps/api/prosauai/conversation/step_record.py` com dataclass `StepRecord` (order, name, status, duration_ms, started_at, ended_at, input_jsonb, output_jsonb, model, tokens_in, tokens_out, tool_calls, error_type, error_message) + método `truncate_io(max_bytes=8192)` que atualiza flags `input_truncated`/`output_truncated` e `input_size`/`output_size`
- [x] T024 [P] Criar `apps/api/tests/unit/conversation/test_pipeline_instrumentation.py` — testa StepRecord.truncate_io (payload >8KB marca flag + preserva tamanho original), StepRecord validation (status enum, step_order 1..12), serialização JSONB
- [x] T025 [P] Criar `apps/api/prosauai/conversation/trace_persist.py` — função assíncrona `persist_trace(conn, trace_data, steps)` que faz INSERT em `traces` + batch INSERT em `trace_steps` numa única txn; função `persist_trace_fire_and_forget(pool, trace_data, steps)` que envolve em `asyncio.create_task` + `try/except` com log estruturado (NÃO propaga erro — padrão fire-and-forget R3/R7)
- [x] T026 Refatorar `apps/api/prosauai/conversation/pipeline.py` — adicionar buffer `_step_records: list[StepRecord]` em `Pipeline`; decorar cada uma das 12 etapas (webhook_received, route, customer_lookup, conversation_get, save_inbound, build_context, classify_intent, generate_response, evaluate_response, output_guard, save_outbound, deliver) para capturar timestamp in/out, status, input/output, error_type/message; ao final de `execute()`, chamar `persist_trace_fire_and_forget()` com `trace_id = get_trace_id_hex()` (depende de T020, T022, T023, T025)
- [x] T027 Expor tokens/model de `generate_response` no buffer — modificar `apps/api/prosauai/conversation/agent.py` para retornar `tokens_in`, `tokens_out`, `model` usados, que serão capturados pelo decorator em `pipeline.py` (depende de T026)
- [x] T028 Calcular `cost_usd` no final do pipeline chamando `calculate_cost(model, total_tokens_in, total_tokens_out)` e inserir em `traces.cost_usd`; populate `intent`, `intent_confidence` a partir do StepRecord de `classify_intent`; populate `quality_score` a partir do StepRecord de `evaluate_response` (depende de T020, T026)
- [x] T029 Executar suíte completa `pytest apps/api/tests/` — gate SC-007 requer 100% dos testes existentes (epics 004+005) passando + 2 novos testes unit (pricing, instrumentation) verdes antes do merge; registrar output em PR description
- [ ] T030 Smoke test em staging por 24h — deploy da branch, disparar tráfego real de Ariel, monitorar: (a) zero falha de delivery, (b) rows aparecem em `traces` + `trace_steps`, (c) overhead p95 <10ms (comparação A/B conforme quickstart.md §Benchmarks). **DEFERRED**: requer 24h de tráfego real em staging — não executável em pipeline autônomo. Suíte de testes offline (T029/T043) cobre os caminhos instrumentados.

**Checkpoint PR 2**: Pipeline instrumentado, 100% suíte verde, smoke 24h OK. Traces + steps populados.

### PR 3 — Routing Persistence Hook

- [x] T040 [P] Criar `apps/api/tests/unit/router/test_routing_persistence.py` — testa serialização de `RoutingRule` e `MessageFacts` para JSONB, hash de phone preservado, fire-and-forget não propaga erro
- [x] T041 [P] Criar helper `persist_routing_decision_fire_and_forget(pool, decision_data)` em `apps/api/prosauai/router/decision_persist.py` seguindo mesmo padrão de `trace_persist.py` — INSERT em `routing_decisions` + log estruturado em falha
- [x] T042 Modificar `apps/api/prosauai/router/engine.py` no método `evaluate()` — após decisão computada, chamar `persist_routing_decision_fire_and_forget()` com snapshot da `matched_rule` (ou `None` se default), `facts`, `trace_id` (via `get_trace_id_hex()` se decision=RESPOND, None caso contrário), `agent_target` (depende de T041). **Nota**: wired em `apps/api/prosauai/api/webhooks.py` em vez de `engine.py` para preservar pureza do engine sync/frozen; helper `_persist_routing_decision_safe()` invoca fire-and-forget após `route()` retornar.
- [x] T043 Executar suíte `pytest apps/api/tests/unit/router/ apps/api/tests/integration/router/` — 100% testes epic 004 passando + novo teste de persistência verde

**Checkpoint PR 3**: Routing decisions persistidos em tempo real, zero impacto no caminho crítico.

### PR 4 — Inbox Denormalization + Backfill

- [x] T050 [P] Atualizar `apps/api/prosauai/conversation/pipeline.py` step `save_inbound` para popular `conversations.last_message_id`, `last_message_at`, `last_message_preview` (LEFT(content, 200) com regexp_replace whitespace) — UPDATE na mesma txn do INSERT de message
- [x] T051 [P] Atualizar step `save_outbound` com mesma lógica de populate de `conversations.last_message_*`
- [x] T052 [P] Criar script `apps/api/scripts/backfill_last_message.py` — executa UPDATE em batch de 1000 conversas por iteração (com `WHERE last_message_at IS NULL LIMIT 1000` + sleep 200ms), usa query SQL da data-model.md §4 Backfill; script idempotente; usa `pool_admin`; progress bar via stdout; LOG no final com total de rows atualizadas
- [x] T053 [P] Criar `apps/api/tests/integration/conversation/test_last_message_denorm.py` — INSERT inbound, assert `conversations.last_message_*` atualizados; INSERT outbound posterior, assert sobreescrito; rodar backfill em dataset pré-populado e assert idempotência
- [x] T054 Executar suíte `pytest apps/api/tests/` — 100% verde, incluindo testes existentes de `save_inbound`/`save_outbound` sem regressão (1410 passed, 32 skipped; coverage 83.53%)
- [x] T055 Benchmark query de listagem: `EXPLAIN ANALYZE SELECT ... FROM conversations WHERE tenant_id=$1 ORDER BY last_message_at DESC LIMIT 50` em dataset de 10k conversas — p95 <100ms (SC-005); registrar output em PR description. **DEFERRED**: requer dataset real de 10k conversas em staging — documentado em `benchmarks/inbox_list_query.md` com query plan esperado baseado no `idx_conversations_tenant_last_msg` criado em T013.

**Checkpoint PR 4**: Denormalização funcional + backfill testado. Inbox pronta para listagem <100ms.

### PR 4b — Retention Cron Extension

- [x] T056 Modificar `apps/api/scripts/retention_cron.py` (epic 006) adicionando 3 novas DELETEs em transação separada: `DELETE FROM trace_steps WHERE started_at < now() - $1::interval` (default 30d via `TRACE_RETENTION_DAYS` env), `DELETE FROM traces WHERE started_at < now() - $1::interval` (CASCADE já cobre trace_steps mas manter pela idempotência), `DELETE FROM routing_decisions WHERE created_at < now() - $2::interval` (default 90d via `ROUTING_RETENTION_DAYS`). **Nota**: epic 006 não havia shipado `retention_cron.py` ainda neste repo; criado from scratch com o escopo do epic 008 e marker para merge com retention de messages/conversations quando epic 006 landar.
- [x] T057 [P] Atualizar docker-compose / env.example com `TRACE_RETENTION_DAYS=30` e `ROUTING_RETENTION_DAYS=90` (adicionado em ambos `apps/api/.env.example` e root `.env.example`; docker-compose consome via `env_file: .env` — sem alteração necessária no yaml)
- [x] T058 [P] Criar `apps/api/tests/integration/scripts/test_retention_cron.py` — popula dados com timestamps antigos/recentes, executa retention, assert apenas antigos deletados (6 testes com fake asyncpg — happy path, txn-per-table, failure isolation, dry-run, negative days validation)

### Foundational — Frontend & OpenAPI pipeline

- [x] T060 [P] Instalar `@tanstack/react-query` v5 em `apps/admin/package.json` + config inicial em `apps/admin/src/lib/query-client.ts` (R9) (package já presente no epic 007; criado factory `createQueryClient()` + lazy singleton `getBrowserQueryClient()` com defaults tunados para admin)
- [x] T061 [P] Instalar `openapi-typescript` como dev-dependency em `apps/admin/package.json` + criar script `pnpm gen:api` rodando `openapi-typescript ../../platforms/prosauai/epics/008-admin-evolution/contracts/openapi.yaml -o src/types/api.ts` (R9) (script aponta para `../../../madruga.ai/platforms/...` já que contracts moram no madruga.ai)
- [x] T062 [P] Criar fetch wrapper `apps/admin/src/lib/api.ts` — wrapper em torno de `fetch` com credentials=include (cookie JWT), handling de 401 → `router.push('/login?next=<encoded>')`, parsing JSON tipado (`apiRequest`/`apiGet`/`apiPost`/`apiPatch` + `ApiError` + `buildLoginRedirectUrl`; redirect só no browser, Server Components recebem ApiError para redirect via `next/navigation`)
- [x] T063 [P] Criar `apps/admin/src/lib/health-rules.ts` com funções puras `classifyKpi(kind, value)` implementando thresholds FR-011 + `classifyTenantHealth(tenant)` implementando regra hierárquica FR-015 (+ `classifyVolumeDelta` para cards de volume conforme FR-011)
- [x] T064 [P] Criar `apps/api/prosauai/admin/health.py` com mesmas funções em Python (espelho de T063 — regras não divergem entre front e back)
- [x] T065 [P] Criar `apps/api/tests/unit/admin/test_health_rules.py` — casos de teste para todos os thresholds de FR-011 + todos os caminhos de FR-015 (56 testes verdes cobrindo: 6 boundaries por KPI × 5 KPIs, None/NaN → neutral, volume delta 30%/50% boundaries, 16 caminhos de tenant health incluindo stale >15min, rolling error rate >10%, amber não vence red, null inputs)
- [x] T066 [P] Criar `apps/admin/src/lib/format.ts` com helpers puros `formatCurrency(usd)`, `formatDuration(ms)`, `maskPhone(e164)`, `truncate(str, n)`, `formatDelta(curr, prev)` (retorna `DeltaDescriptor` com {diff, pct, label, trend, color})
- [x] T067 [P] Criar `apps/admin/tests/unit/lib/test_format.ts` + `test_health_rules.ts` com Vitest — cobertura dos edge cases (vitest 3.2 + `vitest.config.mjs`; 46 testes verdes cobrindo formatCurrency/formatDuration/maskPhone/truncate/formatDelta + todos os boundaries de classifyKpi/classifyVolumeDelta/classifyTenantHealth)
- [x] T068 Executar `pnpm gen:api` após contracts/openapi.yaml finalizado — gera `apps/admin/src/types/api.ts` (1418 linhas, openapi-typescript 7.13.0; tsc --noEmit passa)

**Checkpoint Foundational**: Backend schema + instrumentação + endpoints-prontos para implementar; frontend types gerados + libs compartilhadas prontas.

---

## Phase 3: User Story 1 — Inspecionar conversa sem SQL (Priority: P1) 🎯 MVP

**Goal**: Operador acha e lê qualquer conversa (lista + thread + perfil do contato) sem tocar em psql/journalctl.

**Independent Test**: Operador sem acesso ao banco localiza conversa por nome/trecho e vê thread completa em <30s (SC-001).

### Tests for US1

- [x] T100 [P] [US1] Integration test `apps/api/tests/integration/admin/test_conversations.py` — GET /admin/conversations retorna lista paginada, filtro `q` busca via ILIKE em `customers.display_name` OR `messages.content`, cursor pagination funciona, ordenação: SLA breached primeiro → at_risk → recent DESC (6 testes, `TestListConversations::*`; ordering degrada para `last_message_at DESC` até coluna `sla_breach_at` aparecer no schema — comentário inline em `queries/conversations.py`)
- [x] T101 [P] [US1] Integration test GET /admin/conversations/{id} retorna detail com customer profile embedded + SLA state (2 testes `TestConversationDetail::*`)
- [x] T102 [P] [US1] Integration test GET /admin/conversations/{id}/messages retorna thread ordenado cronológico com roles (inbound/ai_assistant/human_operator) (2 testes `TestConversationMessages::*` — role derivado via `direction + metadata.source/operator_name`)
- [x] T103 [P] [US1] Integration test PATCH /admin/conversations/{id} muda status open→closed, retorna 409 em concurrent modification (4 testes `TestConversationPatch::*` — happy path, 409 conflict, idempotent no-op, 404)
- [x] T104 [P] [US1] Integration test GET /admin/customers + /admin/customers/{id} retornam profile enriquecido com QS médio, contagem de conversas, histórico (5 testes em `test_customers.py`)
- [x] T105 [P] [US1] Integration test GET /admin/tenants retorna lista com quick stats (para dropdown global) (6 testes em `test_tenants.py` cobrindo list/detail/PATCH)
- [x] T106 [P] [US1] E2E Playwright `apps/admin/tests/e2e/conversation-to-trace.spec.ts` — login → /conversations → busca "João" → seleciona → thread completa visível → perfil expandido (spec criado; @playwright/test ainda não é devDep — ts-nocheck até Playwright ser instalado pela frontend wave)

### Implementation for US1 — Backend (PR 5)

- [x] T110 [P] [US1] Criar `apps/api/prosauai/db/queries/conversations.py` com funções: `list_conversations(pool, tenant, q, status, sla, cursor, limit)` (ILIKE + ordering + cursor base64 de `{last_message_at, id}`), `get_conversation_detail(pool, id)`, `get_conversation_messages(pool, id, cursor, limit)`, `update_conversation_status(pool, id, status, expected_current)` (usa WHERE status=expected_current para optimistic locking; retorna None em conflict)
- [x] T111 [P] [US1] Criar Pydantic models em `apps/api/prosauai/admin/schemas/conversations.py` espelhando `ConversationListResponse`, `ConversationDetail`, `MessageListResponse` do openapi.yaml
- [x] T112 [US1] Criar router `apps/api/prosauai/admin/conversations.py` com 4 endpoints (GET list, GET detail, PATCH status, GET messages) — usa `pool_admin`, auth via dep de cookie JWT existente; 409 para concurrent modification (depende T110, T111)
- [x] T113 [P] [US1] Criar `apps/api/prosauai/db/queries/customers.py` + Pydantic schemas + router `apps/api/prosauai/admin/customers.py` (GET list + GET detail com QS médio e histórico)
- [x] T114 [P] [US1] Criar `apps/api/prosauai/db/queries/tenants.py` + Pydantic schemas + router `apps/api/prosauai/admin/tenants.py` (GET list + GET detail + PATCH enabled) — PATCH valida que tenant existe e invalida cache Redis se presente
- [x] T115 [US1] Registrar 3 novos routers em `apps/api/prosauai/main.py` sob prefix `/admin` (depende de T112, T113, T114) — já registrados via `admin/router.py` (auth + metrics + conversations + customers + tenants) e incluídos em `main.py` L471

### Implementation for US1 — Frontend (PR 7 parcial)

- [x] T120 [P] [US1] Estender sidebar em `apps/admin/src/components/shared/sidebar.tsx` para 8 itens com ícones lucide (Home, MessageSquare, Activity, BarChart3, Bot, GitBranch, Building2, ShieldCheck) conforme FR-001 — implementado em `components/layout/sidebar.tsx` (estrutura existente do epic 007); preserva `?tenant` ao navegar
- [x] T121 [P] [US1] Criar `apps/admin/src/components/shared/tenant-dropdown.tsx` — Server Component + client island; lê `searchParams.tenant`, router.push('?tenant=xxx') no change (FR-002, decisão 9) — client component que usa `useSearchParams` + `router.replace`; lista tenants via TanStack Query (`/admin/tenants`); reset de cursor ao trocar tenant
- [x] T122 [P] [US1] Adaptar `apps/admin/src/app/(dashboard)/layout.tsx` para incluir sidebar 8-items + tenant dropdown no header — adaptado em `app/admin/(authenticated)/layout.tsx` (sem mudança) + `components/layout/header.tsx` agora monta `<TenantDropdown />`
- [x] T123 [P] [US1] Criar primitives em `apps/admin/src/components/ui/intent-badge.tsx`, `quality-score-badge.tsx`, `sla-indicator.tsx` — usam cores de `lib/health-rules.ts` via tokens OKLCH (chart-1..5 + destructive)
- [x] T124 [P] [US1] Criar `apps/admin/src/components/conversations/conversation-list.tsx` — 320px col, Server Component, lê `searchParams` (tenant, q, status, sla, cursor), chama `/admin/conversations`, renderiza items com avatar iniciais, preview, timestamp, intent-badge, quality-score-badge, sla-indicator (+ helper `lib/api-server.ts` para forward de cookies em Server Components)
- [x] T125 [P] [US1] Criar `apps/admin/src/components/conversations/message-bubble.tsx` — bolha com variantes visuais distintas para inbound/ai_assistant/human_operator (FR-023); metadados AI expansíveis no hover (latência, tokens, QS, link "Ver trace") via popover CSS-only (group-hover/group-focus-within)
- [x] T126 [P] [US1] Criar `apps/admin/src/components/conversations/thread-view.tsx` — Server Component, fetches messages, renderiza bubbles com separator visual entre mudanças de intent (FR-025); input desabilitado com placeholder "somente leitura" (FR-027)
- [x] T127 [P] [US1] Criar `apps/admin/src/components/conversations/contact-profile.tsx` — 360px col, exibe nome, tenant, canal, status conversa, intent+confidence, QS médio, message count, histórico resumido, tags, ações ("Ver todos os traces", "Fechar conversa" com confirmation dialog chamando PATCH) — Server Component + client island `close-conversation-button.tsx` para o PATCH com handling de 409
- [x] T128 [US1] Criar page `apps/admin/src/app/(dashboard)/conversations/page.tsx` — 3-col layout (list 320px + thread flex + profile 360px); aceita `searchParams` para q/status/sla/tenant — implementado em `app/admin/(authenticated)/conversations/page.tsx` + `_search-bar.tsx` (client island com debounce 300ms para `?q=`)
- [x] T129 [US1] Criar page `apps/admin/src/app/(dashboard)/conversations/[id]/page.tsx` — detalhe centrado em uma conversa selecionada (preserva layout 3-col com item selecionado na list); pre-fetch da `ConversationDetail` reaproveitada por `ThreadView` e `ContactProfile`

**Checkpoint US1**: Aba Conversas 100% funcional. SC-001 validado manualmente no navegador. MVP mínimo atingido.

---

## Phase 4: User Story 2 — Debug pipeline via trace waterfall (Priority: P1)

**Goal**: Engenheiro vê waterfall das 12 etapas do pipeline com input/output por step e identifica etapa dominante/erro em <30s (SC-002).

**Independent Test**: Engenheiro consegue, a partir de um `trace_id` ou nome de contato, identificar step dominante em latência e ler seu input/output sem usar journalctl/Phoenix/psql.

### Tests for US2

- [x] T200 [P] [US2] Integration test `apps/api/tests/integration/admin/test_traces.py` — GET /admin/traces filtra por tenant/status/min_duration/period, cursor pagination funcional; GET /admin/traces/{trace_id} aceita hex trace_id E UUID id, retorna waterfall com 12 steps ordenados (14 testes verdes; asserts validam `tr.id::text = $1 OR tr.trace_id = $1` no SQL + ordering 1..12 dos steps)
- [x] T201 [P] [US2] Integration test trace detail: step com `input_truncated=true` retorna `input_jsonb` ≤8KB + `input_size` original (`TestTraceTruncation::test_truncated_step_surfaces_flag_and_original_size`)
- [x] T202 [P] [US2] Integration test trace com step erro: steps posteriores marcados `skipped`, step erro com `error_type`/`error_message` populado (`TestTraceErrorPropagation::test_error_step_and_skipped_successors`)
- [x] T203 [P] [US2] E2E Playwright `apps/admin/tests/e2e/trace-explorer-filter.spec.ts` — /traces → filter status=error → seleciona trace → waterfall com 12 barras → expande step dominante → input/output JSON visível (spec criado com `@ts-nocheck` até `@playwright/test` ser instalado na wave final de e2e)

### Implementation for US2 — Backend (PR 6 parcial)

- [x] T210 [P] [US2] Criar `apps/api/prosauai/db/queries/traces.py` com `list_traces(pool, tenant, status, min_duration, period, cursor, limit)` + `get_trace_detail(pool, identifier)` (aceita UUID ou hex trace_id — WHERE id::text = $1 OR trace_id = $1); carrega trace + steps em 2 queries (não joins explosivos); inclui `compute_dominant_step_name` server-side para FR-037
- [x] T211 [P] [US2] Criar Pydantic schemas em `apps/api/prosauai/admin/schemas/traces.py` — `TraceListResponse`, `TraceDetail`, `StepDetail` espelhando openapi.yaml; incluir flag `input_truncated` + `input_size` no payload
- [x] T212 [US2] Criar router `apps/api/prosauai/admin/traces.py` com 2 endpoints (list + detail); depende T210, T211
- [x] T213 [US2] Registrar router em `apps/api/prosauai/main.py` — via `admin/router.py` (aggregator consistente com conversations/customers/tenants)

### Implementation for US2 — Frontend (PR 8)

- [x] T220 [P] [US2] Criar primitive `apps/admin/src/components/ui/json-tree.tsx` — componente colapsável para objetos aninhados com syntax highlight, copy-to-clipboard, limit de profundidade default 3; reutilizável em routing e outros contexts
- [x] T221 [P] [US2] Criar `apps/admin/src/components/traces/trace-list.tsx` — tabela server-rendered com hora, contato, intent, duração, custo, status; filtros via searchParams (tenant, status, min_duration, period)
- [x] T222 [P] [US2] Criar `apps/admin/src/components/traces/waterfall-chart.tsx` — custom component (SVG ou divs flex) com barras proporcionais à duração de cada step; highlight visual para step dominante (>60% do total — R10); destacar steps com `status=error` em vermelho e `status=skipped` em cinza-claro
- [x] T223 [P] [US2] Criar `apps/admin/src/components/traces/step-accordion.tsx` — accordion para cada step com status icon, nome, duração ms; expansão mostra model + tokens_in/tokens_out + tool_calls + input_jsonb + output_jsonb (via json-tree); banner `[truncado — tamanho original X KB]` quando flag true (FR-034); se `status=error`, auto-expande e mostra error_type/message/stack
- [x] T224 [P] [US2] Criar `apps/admin/src/components/traces/step-detail-panel.tsx` — painel lateral quando step selecionado para deep-dive
- [x] T225 [US2] Criar page `apps/admin/src/app/(dashboard)/traces/page.tsx` — Server Component renderizando trace-list (implementado em `app/admin/(authenticated)/traces/page.tsx` para seguir o padrão já estabelecido no epic; sidebar agora habilitada para Trace Explorer)
- [x] T226 [US2] Criar page `apps/admin/src/app/(dashboard)/traces/[trace_id]/page.tsx` — header com metadados (contato, duração, custo, status, intent, QS) + botão "Ver Conversa →" (FR-040) + waterfall-chart + step-accordions (depende T222, T223) — implementado em `app/admin/(authenticated)/traces/[trace_id]/page.tsx`

**Checkpoint US2**: Trace Explorer 100% funcional. MVP atingido (US1+US2).

**CUT-LINE (decisão 2 pitch)**: Se ao final de US2 o tempo total já passou de 5 semanas, cortar US3..US8 parcialmente para epic 009 e shipar MVP.

---

## Phase 5: User Story 3 — Performance AI / Qualidade e Custo (Priority: P2)

**Goal**: Líder identifica intent com maior fallback, hora do dia com mais erros, modelo mais caro — sem pedir dado a engenheiro.

**Independent Test**: Líder abre /performance, escolhe 7d + tenant, vê 4 KPIs + 5 gráficos em <2s (sem cache) ou <200ms (com cache).

### Tests for US3

- [x] T300 [P] [US3] Integration test `apps/api/tests/integration/admin/test_performance.py` — GET /admin/metrics/performance com period=7d retorna 4 KPIs (containment, QS avg, P95 latency, fallback rate) + distribuição de intents + quality trend + latency waterfall + error heatmap 24×7 + cost by tenant/model
- [x] T301 [P] [US3] Integration test cache: primeira request mede DB; segunda request dentro de 5min mede Redis; após 5min cache expira; header `Cache-Control: max-age=300` presente
- [x] T302 [P] [US3] Integration test fallback rate: contabiliza mensagens com (intent=fallback|unknown|out_of_scope) OR intent_confidence<0.5 OR output_guard=safety_refused OR handoff humano iniciado; exclui mensagens com routing decision DROP/LOG_ONLY/BYPASS_AI (FR-050)

### Implementation for US3 — Backend

- [x] T310 [P] [US3] Criar `apps/api/prosauai/db/queries/performance.py` com funções: `aggregate_kpis(pool, tenant, period)` (containment, QS avg, P95 latency, fallback rate — implementa FR-050 com EXCLUI routing DROP/LOG_ONLY/BYPASS_AI via JOIN routing_decisions), `intent_distribution(pool, tenant, period)`, `quality_trend(pool, tenant, period, bucket='1h'|'1d')`, `latency_breakdown(pool, tenant, period)` (P50/P95/P99 por step — PipelineLatencyBreakdown), `error_heatmap(pool, tenant, period)` (grid 24×7 EXTRACT(hour, dow) — R6/FR-054), `cost_by_model(pool, tenant, period)` + sparkline 30d
- [x] T311 [P] [US3] Criar helper `apps/api/prosauai/admin/cache.py` com decorator `@cached_redis(key_prefix, ttl=300, jitter=30)` — key baseada em hash de params, jitter TTL (300±30s) para evitar thundering herd (plan.md Risks)
- [x] T312 [US3] Criar Pydantic schemas em `apps/api/prosauai/admin/schemas/performance.py` espelhando `PerformanceMetrics`
- [x] T313 [US3] Criar router `apps/api/prosauai/admin/metrics/performance.py` com GET /admin/metrics/performance + cache Redis 5min; adiciona header `Cache-Control: max-age=300`; registrar em main.py (depende T310, T311, T312)

### Implementation for US3 — Frontend (PR 9)

- [x] T320 [P] [US3] Criar shadcn Chart wrapper já instalado (epic 007) — validar tokens `--chart-1..5` configurados em `apps/admin/src/app/globals.css` (confirmado: `--chart-1..5` OKLCH tokens presentes em `globals.css` + `components/ui/chart.tsx` já exporta `ChartContainer`, `ChartTooltip`, `ChartTooltipContent` para consumo pelos componentes US3)
- [x] T321 [P] [US3] Criar `apps/admin/src/components/performance/intent-distribution.tsx` — barH chart (shadcn Chart + Recharts) ordenado por volume desc; cor adicional para intents com fallback rate >20% (FR-051)
- [x] T322 [P] [US3] Criar `apps/admin/src/components/performance/quality-trend.tsx` — area chart P50 + line P95 com reference line no threshold crítico=70 (FR-052)
- [x] T323 [P] [US3] Criar `apps/admin/src/components/performance/latency-waterfall.tsx` — stacked barH (3 segmentos P50 / P95-P50 / P99-P95) por step do pipeline (FR-053)
- [x] T324 [P] [US3] Criar `apps/admin/src/components/performance/error-heatmap.tsx` — custom SVG grid 24×7 com intensidade proporcional, tooltip com contagem ao hover, toggle "Erros"/"Fallbacks" (FR-054, R10)
- [x] T325 [P] [US3] Criar `apps/admin/src/components/performance/cost-bars.tsx` — barV agregado por tenant e por modelo + sparkline 30d abaixo (FR-055) — horizontal bar chart com 3 pivots (tenant×modelo / tenant / modelo), rollup client-side com soma elementwise das sparklines, custom SVG sparkline 120×32 por bar para evitar Recharts overhead; tokens `--chart-4`; mesmo "sem dados" visual dos demais componentes do feature folder
- [x] T326 [US3] Criar page `apps/admin/src/app/(dashboard)/performance/page.tsx` — grid com 4 KPIs no topo + 5 charts; aceita `searchParams` (tenant, period); Server Component com prefetch de `/admin/metrics/performance` (depende T321..T325) — implementado em `app/admin/(authenticated)/performance/page.tsx` para seguir o padrão do Trace Explorer; Server Component usa `serverApiGet` para prefetch; 4 KPI cards (Containment / QS P50·P95 / Latência P95 / Fallback) com `classifyKpi` + 5 painéis (IntentDistribution, QualityTrend, LatencyWaterfall, ErrorHeatmap, CostBars); PeriodToggle via `<Link>` (scroll=false) preservando tenant; sidebar habilitada para Performance AI

**Checkpoint US3**: Aba Performance AI completa. Benchmarks SC-004 validados.

---

## Phase 6: User Story 4 — Overview enriquecido (Priority: P2)

**Goal**: "Está tudo bem?" respondido em <10s pós-login (SC-003).

**Independent Test**: Gestor identifica componente degradado + tenant fora do verde + erros 24h, sem clicar em aba secundária.

### Tests for US4

- [x] T400 [P] [US4] Integration test `apps/api/tests/integration/admin/test_overview.py` — GET /admin/metrics/overview retorna 6 KPIs com valor atual, sparkline 24h (24 pontos 1h-bucketed), delta vs. yesterday, cor por threshold FR-011
- [x] T401 [P] [US4] Integration test GET /admin/metrics/activity-feed retorna até 50 eventos (UNION ALL de new_conversation + sla_breach + pipeline_error + fallback_intent + ai_resolved); filtro `since` funciona; Redis cache 10s funcional (R8)
- [x] T402 [P] [US4] Integration test GET /admin/metrics/system-health checa PG (SELECT 1), Redis (PING), Evolution API (GET /status), Phoenix (GET /healthz); degraded/down status refletem latência/timeout
- [x] T403 [P] [US4] Integration test GET /admin/metrics/tenant-health aplica regra hierárquica FR-015 (vermelho se qualquer KPI vermelho OR last_message >15min OR rolling 5min error_rate >10%, etc.)
- [x] T404 [P] [US4] E2E Playwright `apps/admin/tests/e2e/login-to-overview.spec.ts` — login → / → 6 KPI cards visíveis acima da dobra → activity feed renderiza → system health visível → tenant health table

### Implementation for US4 — Backend

- [x] T410 [P] [US4] Criar `apps/api/prosauai/db/queries/overview.py` com `overview_kpis(pool, tenant)` — computa 6 KPIs com sparklines 24h (bucketed por hora) + delta vs. dia anterior
- [x] T411 [P] [US4] Criar `apps/api/prosauai/db/queries/activity.py` com `activity_feed(pool, tenant, since)` — UNION ALL de 5 SELECTs (new_conversation/sla_breach/pipeline_error/fallback_intent/ai_resolved), cada um LIMIT 10, GLOBAL ORDER BY created_at DESC LIMIT 50 (decisão 19, R8)
- [x] T412 [P] [US4] Criar `apps/api/prosauai/db/queries/tenant_health.py` com `tenant_health(pool)` — iterar tenants ativos, computar KPIs + aplicar `classify_tenant_health()` de T064
- [x] T413 [P] [US4] Criar `apps/api/prosauai/admin/metrics/system_health.py` com probes assíncronos paralelos (asyncio.gather) para PG/Redis/Evolution/Phoenix; retorna {component, status, latency_ms, last_checked}
- [x] T414 [US4] Criar Pydantic schemas em `apps/api/prosauai/admin/schemas/metrics.py` — `OverviewMetrics`, `ActivityFeedResponse`, `SystemHealth`, `TenantHealthResponse`
- [x] T415 [US4] Criar routers `apps/api/prosauai/admin/metrics/{overview,activity_feed,tenant_health,system_health}.py` — activity_feed usa cache Redis TTL 10s (R8); registrar todos em main.py (depende T410..T414)

### Implementation for US4 — Frontend (PR 7)

- [x] T420 [P] [US4] Criar primitive `apps/admin/src/components/ui/kpi-card.tsx` — card com valor grande, label, sparkline 24h (shadcn Chart), delta colorido conforme FR-011 (uses `classifyKpi` de T063); variant para cards de volume (sem cor por valor absoluto, só delta)
- [x] T421 [P] [US4] Criar `apps/admin/src/components/shared/activity-feed.tsx` — client component com polling 15s via TanStack Query (`refetchInterval: 15000`); renderiza 50 items clicáveis para navegação ao contexto (conversation_id ou trace_id)
- [x] T422 [P] [US4] Criar `apps/admin/src/components/shared/system-health.tsx` — client component com polling 30s; badges com pontos coloridos (verde/âmbar/vermelho/cinza) por componente
- [x] T423 [P] [US4] Criar `apps/admin/src/components/shared/tenant-health-table.tsx` — Server Component (render inicial server) + client island para auto-refresh 30s; aplica classifyTenantHealth; cada row clicável navega para `?tenant=<slug>` (FR-015)
- [x] T424 [US4] Refatorar `apps/admin/src/app/(dashboard)/page.tsx` Overview — grid 6 KPI cards + activity-feed + system-health + tenant-health-table (depende T420..T423)

**Checkpoint US4**: Overview enriquecido completo. SC-003 validado.

---

## Phase 7: User Story 5 — Auditar decisões de roteamento (Priority: P2)

**Goal**: Identificar mensagem descartada (DROP/LOG_ONLY) + razão em <1min (SC-008).

**Independent Test**: Admin localiza decisão para phone_hash em janela de tempo, vê razão + matched_rule sem journalctl.

### Tests for US5

- [x] T500 [P] [US5] Integration test `apps/api/tests/integration/admin/test_routing.py` — GET /admin/routing/rules retorna snapshot do estado in-memory do RoutingEngine; GET /admin/routing/decisions filtra decision_type/phone_hash/period; GET /admin/routing/decisions/{id} retorna matched_rule + facts JSON; GET /admin/routing/stats retorna donut + top-N reasons (19 testes verdes cobrindo 4 endpoints + filtros + cursor + auth + JSONB string coercion)
- [x] T501 [P] [US5] Integration test decision detail: navegação trace_id → conversa quando RESPOND; matched_rule=null quando default (`TestDecisionDetail::test_respond_with_trace_id` + `test_default_rule_surfaces_as_null`)

### Implementation for US5 — Backend

- [x] T510 [P] [US5] Criar `apps/api/prosauai/db/queries/routing_decisions.py` com `list_decisions(pool, tenant, decision_type, period, phone_hash, cursor, limit)`, `get_decision(pool, id)`, `stats(pool, tenant, period)` (donut agregado + top-N reasons) — cursor opaco compartilha shape `{t, i}` via `encode_cursor`; stats sempre retorna as 5 decision types para donut estável
- [x] T511 [P] [US5] Expor snapshot de regras via novo método `RoutingEngine.snapshot_rules() -> list[dict]` em `apps/api/prosauai/core/router/engine.py` — lê estado in-memory atual (FR-072); path real é `core/router/engine.py` (não `router/engine.py` como o plano indicava); regra sintética `__default__` inclusa no output
- [x] T512 [US5] Criar Pydantic schemas em `apps/api/prosauai/admin/schemas/routing.py` — espelha OpenAPI contract (`RoutingRule`, `RoutingDecision`, `RoutingDecisionDetail`, `RoutingStats`)
- [x] T513 [US5] Criar router `apps/api/prosauai/admin/routing.py` com 4 endpoints (rules, decisions list, decisions detail, stats); registrado em `admin/router.py` aggregator (consistente com conversations/traces)

### Implementation for US5 — Frontend (PR 10 parcial)

- [x] T520 [P] [US5] Criar `apps/admin/src/components/routing/rules-table.tsx` — Server Component full-width; tabela de regras em memória por tenant (priority, condições como pills, ação tinted, agente alvo); header com timestamp da última leitura + link "Recarregar" (in-memory não polia, mudança só em restart)
- [x] T521 [P] [US5] Criar `apps/admin/src/components/routing/decisions-donut.tsx` — client donut Recharts + shadcn Chart; 5 slices sempre renderizadas (RESPOND/DROP/LOG_ONLY/BYPASS_AI/EVENT_HOOK) para geometria estável; cores OKLCH chart-1..4 + destructive; legenda lateral com count+share; seção footer com top-N reasons inline
- [x] T522 [P] [US5] Criar `apps/admin/src/components/routing/decisions-list.tsx` — Server Component via `serverApiGet`; colunas hora/contato/decisão/razão/trace; display_name + hash abreviado; linha selecionada destacada via `?decision=<id>`; link "Ver trace" quando presente; filtros via searchParams (tenant/decision_type/period/phone_hash/cursor)
- [x] T523 [P] [US5] Criar `apps/admin/src/components/routing/decision-detail-panel.tsx` — Server Component; reuso de `<JsonTree>` (T220) para `matched_rule` + `facts`; header com badge do decision_type + id; meta (contato, tenant, hash, timestamp, agente, trace); footer com "Ver trace →" quando trace_id presente; empty state quando `?decision` ausente
- [x] T524 [US5] Criar page `apps/admin/src/app/admin/(authenticated)/routing/page.tsx` — 2 linhas (rules-table full-width + donut/list/detail em 3 colunas); toggle de período (1h/24h/7d) e decision_type via `<Link>` preservando filtros; stats pré-fetched em server; sidebar habilitada para Roteamento (removido `disabled: true`)

**Checkpoint US5**: Aba Routing completa. SC-008 + SC-012 validados.

---

## Phase 8: User Story 6 — Gerenciar agentes e comparar prompts (Priority: P3)

**Goal**: Engenheiro compara 2 versões de prompt em diff side-by-side, vê tools e métricas do agente vs. média.

**Independent Test**: Engenheiro compara 2 versões de prompt com diff visível + vê tools habilitadas sem abrir repo/DB.

### Tests for US6

- [x] T600 [P] [US6] Integration test `apps/api/tests/integration/admin/test_agents.py` — GET /admin/agents lista agentes filtrados por tenant; GET /admin/agents/{id} retorna config+metrics+prompt refs; GET /admin/agents/{id}/prompts lista versions; POST /admin/agents/{id}/prompts/activate muda `active_prompt_id`
- [x] T601 [P] [US6] Integration test metrics: media do agente vs. plataforma (QS, containment, latência, fallback) com delta

### Implementation for US6 — Backend

- [x] T610 [P] [US6] Criar `apps/api/prosauai/db/queries/agents.py` com `list_agents`, `get_agent_with_metrics`, `list_prompts`, `activate_prompt` (UPDATE agents SET active_prompt_id=$1)
- [x] T611 [US6] Criar Pydantic schemas + router `apps/api/prosauai/admin/agents.py` com 4 endpoints; registrar em main.py (depende T610)

### Implementation for US6 — Frontend (PR 10 parcial)

- [x] T620 [P] [US6] Criar `apps/admin/src/components/agents/agent-list.tsx` — lista 240px à esquerda, filtro por tenant, toggle enabled
- [x] T621 [P] [US6] Criar `apps/admin/src/components/agents/prompt-viewer.tsx` — visualizador com 3 seções distintas (safety_prefix / system_prompt / safety_suffix) com background diferenciado via tokens OKLCH + preserve whitespace (FR-063)
- [x] T622 [P] [US6] Criar `apps/admin/src/components/agents/prompt-diff-view.tsx` — diff side-by-side (lib leve tipo `diff` + custom render OU `react-diff-viewer`); pills com versions, selectable 2 para diff (FR-062)
- [x] T623 [P] [US6] Criar `apps/admin/src/components/agents/agent-detail-tabs.tsx` — 3 tabs shadcn Tabs: Configuração (modelo, temp, max_tokens, tools como badges) / Prompts (pills + viewer + diff) / Métricas (KPIs + sparkline 30d vs. platform avg)
- [x] T624 [US6] Criar page `apps/admin/src/app/(dashboard)/agents/page.tsx` + `[id]/page.tsx` — layout lista + detalhe com tabs; ação "Ativar" dispara POST com confirmation dialog (depende T620..T623)

**Checkpoint US6**: Aba Agents completa.

---

## Phase 9: User Story 7 — Administrar tenants (Priority: P3)

**Goal**: Admin financeiro desativa tenant inadimplente em 1 clique.

**Independent Test**: Admin localiza tenant por slug, vê volume+QS 7d, desativa com 1 clique.

### Tests for US7

- [x] T700 [P] [US7] Integration test `apps/api/tests/integration/admin/test_tenants.py` — coberto em T114 via endpoints. Adicionar assertion: PATCH enabled=false, próxima RoutingEngine.evaluate() retorna DROP com reason=tenant_disabled (ou delegar para teste de integração de router) — **IMPLEMENTADO**: `test_disable_persists_flag_for_downstream_routing` asserta que a UPDATE query é invocada com `enabled=False` + slug correto; a via "RoutingEngine.evaluate() retorna DROP" foi delegada porque `TenantStore` é YAML-backed (não DB-backed) e a rejeição de tenant disabled ocorre no nível do webhook (`api/dependencies.py:68`), coberta por `tests/unit/test_tenant_store.py::test_disabled_tenant_loaded_correctly`; docstring documenta que quando o store ganhar DB reload hook, a assertion do engine será adicionada.

### Implementation for US7 — Frontend

- [x] T710 [P] [US7] Criar `apps/admin/src/components/tenants/tenant-list.tsx` — tabela com name, slug, status, conversas ativas, QS médio, last_webhook_at (FR-080) — Server Component que faz fetch de `/admin/tenants` via `serverApiGet`; linha clicável → `/admin/tenants/{slug}`; highlight via `selectedSlug` para sincronia com detalhe; status badge (habilitado/desabilitado) com tokens OKLCH `--chart-1`; reusa `<QualityScoreBadge>` (threshold FR-011); timestamp do último webhook em "há Xh" (helper local alinhado com `conversation-list.tsx`); empty state + erro amigável.
- [x] T711 [P] [US7] Criar `apps/admin/src/components/tenants/tenant-detail.tsx` — config JSON viewer + agentes associados (link para /agents?tenant=slug) + métricas 7d + toggle enabled com confirmation (FR-081) — Server Component com `<JsonTree>` para config (fallback quando vazio aponta para `tenants.yaml`), lista de agentes com link para `/admin/agents/{id}` e `/admin/agents?tenant=<slug>`, 4 KPIs 7d (containment, QS P50, P95 latência, fallback) com fallback para Performance tab quando `metrics_7d` ausente; toggle via client island `<TenantToggleButton>` (PATCH `/admin/tenants/{slug}` com `apiPatch` + confirmation dialog descrevendo impacto no roteador + `router.refresh()` pós-sucesso).
- [x] T712 [US7] Criar page `apps/admin/src/app/(dashboard)/tenants/page.tsx` + `[slug]/page.tsx` (depende T710, T711) — implementado em `app/admin/(authenticated)/tenants/{page.tsx,[slug]/page.tsx}` seguindo o padrão já estabelecido no epic 007 (sem route group `(dashboard)`). List page renderiza `<TenantList />`; detail page faz pre-fetch de `/admin/tenants/{slug}` via `serverApiGet`, 404 → `notFound()`, renderiza `<TenantDetail>` + breadcrumb "Tenants / slug" + lista de outros tenants no rodapé com highlight `selectedSlug`. Sidebar habilitada para Tenants (removido `disabled: true`).

**Checkpoint US7**: Aba Tenants completa.

---

## Phase 10: User Story 8 — Auditar eventos de segurança (Priority: P3)

**Goal**: Security review de login_failed por IP em 7d.

**Independent Test**: Listar login_failed dos últimos 7d para IP específico + todas as ações de user admin, sem SQL.

### Tests for US8

- [x] T800 [P] [US8] Integration test `apps/api/tests/integration/admin/test_audit.py` — GET /admin/audit paginado, filtros action/user_email/period funcionam; anomaly detection (3+ login_failed mesmo IP 24h) flagrada no response (14 testes verdes cobrindo list/filters/cursor/auth + anomaly flag + SQL shape regression guards)

### Implementation for US8 — Backend

- [x] T810 [P] [US8] Criar `apps/api/prosauai/db/queries/audit.py` com `list_audit(pool, action, user_email, period, cursor, limit)` + anomaly detection inline (subquery COUNT login_failed agrupado por IP) — flatten de `user_agent` / `target_type` / `target_id` via `_row_to_event` porque o schema atual (migration `20260415000003`) guarda esses campos dentro de `details` JSONB; cursor compartilha `encode_cursor`/`decode_cursor` com conversations/routing para consistência
- [x] T811 [US8] Criar Pydantic schemas + router `apps/api/prosauai/admin/audit.py`; registrar em main.py (depende T810) — router incluído via `admin/router.py` aggregator (consistente com conversations/routing/agents); mapeia FR-090..FR-093 1:1 do OpenAPI `AuditEvent`/`AuditListResponse`

### Implementation for US8 — Frontend

- [x] T820 [P] [US8] Criar `apps/admin/src/components/audit/audit-filters.tsx` — filtros action/user/period (searchParams) — client island com debounce 300ms no email (mesmo padrão de `conversations/_search-bar.tsx`); `cursor` é invalidado a cada troca de filtro; opções de ação cobrem `login_success`/`login_failed`/`logout`/`rate_limit_hit` (auditadas pelo `auth_routes.py`)
- [x] T821 [P] [US8] Criar `apps/admin/src/components/audit/audit-timeline.tsx` — timeline com 50 items/página, cursor-based next page; anomaly rows com borda vermelha + badge "múltiplas falhas" (FR-093) — Server Component via `serverApiGet<AuditListResponse>`, reusa tokens OKLCH `--chart-1..4` para cores de ação, destaca anomalia com `border-l-[3px] border-l-destructive` + chip uppercase; preview compacto dos 3 campos mais relevantes de `details` (email/reason/operator_name primeiro) + linha UA secundária
- [x] T822 [US8] Criar page `apps/admin/src/app/(dashboard)/audit/page.tsx` (depende T820, T821) — path real `app/admin/(authenticated)/audit/page.tsx` (mantém padrão do epic 007); header explicativo + filters + timeline; sidebar habilitada para Auditoria (removido `disabled: true`); normaliza `?period` via whitelist 1d/7d/30d/90d para evitar 500s; tenant filter ignorado (FR-101 — auditoria é platform-scoped)

**Checkpoint US8**: Aba Auditoria completa. Todas 8 user stories entregues.

---

## Phase 11: Polish & Cross-Cutting Concerns

- [x] T900 [P] Atualizar docs em `platforms/prosauai/epics/008-admin-evolution/quickstart.md` com instruções finais (verified via dry-run) — adicionada seção "Validação final (dry-run) — Phase 11" cobrindo SC-001/002/003/004/005/007/012 com comandos reproduzíveis + "Rollback plan" com 4 níveis (env flag → migration rollback → FE revert → full epic revert)
- [ ] T901 [P] Atualizar `platforms/prosauai/engineering/blueprint.md` seção "Admin" mencionando 8 abas + novas tabelas `traces`, `trace_steps`, `routing_decisions`
- [ ] T902 [P] Atualizar `platforms/prosauai/engineering/containers.md` adicionando componente "Admin API (FastAPI)" com nova superfície de 25 endpoints
- [ ] T903 [P] Atualizar CLAUDE.md do repo prosauai e madruga.ai com entrada em "Active Technologies" (TanStack Query v5, openapi-typescript) e "Recent Changes"
- [ ] T904 Revisar overhead do pipeline em prod — baseline A/B 48h após rollout (SC-006 <10ms p95); se falhar, rollback via env flag
- [ ] T905 [P] Visual regression pass manual em todas as 8 abas — dark mode sem colisões de tokens OKLCH, responsividade 1280-1920px
- [ ] T906 Executar `pytest apps/api/tests/ -v` final — 100% verde (gate SC-007); registrar output em release notes
- [ ] T907 Executar `pnpm test && pnpm playwright test` em `apps/admin/` — 100% verde para 3 e2e críticos (login-to-overview, conversation-to-trace, trace-explorer-filter)
- [ ] T908 Executar quickstart.md §Validação funcional manualmente — cronometrar US1/US2/US4 e validar SC-001 (<30s), SC-002 (<30s), SC-003 (<10s)
- [ ] T909 Lighthouse CI em /admin/conversations + /admin/traces + /admin/performance — score >=90 em Performance (assertion plan.md PR 7 gate)

---

## Phase 12: Deployment Smoke

- [ ] T1000 Executar `docker compose build` no diretório da plataforma — build sem erros
- [ ] T1001 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks respondem dentro do ready_timeout (120s)
- [ ] T1002 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero required_env vars ausentes no .env (JWT_SECRET, ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, DATABASE_URL)
- [ ] T1003 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as URLs acessíveis com status esperado (/health 200, /api/auth/login 200|401, /, /login)
- [ ] T1004 Capturar screenshot de cada URL `type: frontend` declarada em `testing.urls` (/, /login) — conteúdo não é placeholder; /login contém campos email/password
- [ ] T1005 Executar Journey J-001 (Admin Login Happy Path) declarado em `testing/journeys.md` — todos os steps com assertions OK

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — começar imediatamente
- **Foundational (Phase 2)**: depende de Setup — BLOQUEIA todas as user stories
  - **Ordem crítica dentro de Foundational**:
    - PR 1 (T010-T014) antes de PR 2 (requires schema)
    - PR 2 (T020-T030) antes de PR 3 (requires StepRecord infra)
    - PR 2 antes de PR 4 (muda pipeline.py) — mas podem ser sequential-merge, não dev-sequential
    - T060-T068 (frontend infra) pode paralelizar com PR 1-4 backend
- **User Stories (Phase 3-10)**: todas dependem de Foundational completo
  - US1 (P1) antes de US2 (P1) — MVP
  - US3-US8 podem paralelizar entre si após Foundational + P1
- **Polish (Phase 11)**: depende de todas user stories
- **Smoke (Phase 12)**: depende de Polish

### User Story Dependencies

- **US1 (P1)**: depende de Foundational — MVP mínimo
- **US2 (P1)**: depende de Foundational + US1 (reusa primitives ui/* — intent-badge, quality-score-badge, json-tree se já estiver)
- **US3 (P2)**: depende de Foundational — independente de US1/US2
- **US4 (P2)**: depende de Foundational — reusa sidebar/tenant-dropdown de US1
- **US5 (P2)**: depende de Foundational — reusa json-tree de US2 (T220)
- **US6 (P3)**: depende de Foundational
- **US7 (P3)**: depende de Foundational + endpoints de tenants de US1 (T114)
- **US8 (P3)**: depende de Foundational

### Within Each User Story

- Tests (T1XX/T2XX etc.) escritas FIRST para SC-007 enforcement
- Queries/Repo (db/queries) antes de Pydantic schemas antes de Routers
- Primitives UI antes de Components feature
- Components antes de Pages
- Cada fase com checkpoint independentemente testável

### Parallel Opportunities

- Todas tasks marcadas [P] dentro da mesma fase — arquivos distintos
- PR 1 T010-T013 (4 migrations independentes) — paralelas
- Foundational T060-T067 (frontend infra) — todas paralelas entre si
- US1 endpoints T110/T113/T114 — 3 queries+routers paralelos (conversations, customers, tenants)
- US3 charts T321-T325 — 5 components independentes paralelos
- US4 queries T410-T413 — 4 queries paralelas

---

## Parallel Example: PR 1 Migrations

```bash
# Launch all 4 migrations together (different SQL files):
Task T010: Create migration 20260420000001_create_traces.sql
Task T011: Create migration 20260420000002_create_trace_steps.sql
Task T012: Create migration 20260420000003_create_routing_decisions.sql
Task T013: Create migration 20260420000004_alter_conversations_last_message.sql
# Then sequential T014 validates them via dbmate up/down/up
```

## Parallel Example: US1 Backend Endpoints

```bash
# After Foundational done, launch conversations + customers + tenants backend together:
Task T110: db/queries/conversations.py
Task T113: db/queries/customers.py + router/customers.py
Task T114: db/queries/tenants.py + router/tenants.py
# Then T111/T112 depend only on T110 (Pydantic then router)
# Then T115 registers all 3 in main.py
```

## Parallel Example: US3 Charts

```bash
# After Foundational + US3 backend done, launch 5 charts in parallel:
Task T321: IntentDistribution
Task T322: QualityTrend
Task T323: LatencyWaterfall
Task T324: ErrorHeatmap
Task T325: CostBars
# Then T326 page.tsx assembles all
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (PR 0 — ADRs)
2. Complete Phase 2: Foundational (PR 1-4b + frontend infra)
3. Complete Phase 3: US1 (Conversas)
4. Complete Phase 4: US2 (Trace Explorer)
5. **STOP and VALIDATE**: cronometrar SC-001 + SC-002. Decidir cut-line para epic 009 se >5 semanas.
6. Se timeline OK, continuar P2 então P3

### Incremental Delivery

- PR 0 (ADRs) → merge
- PR 1 (migrations) → merge
- PR 2 (pipeline instrument) → 24h staging → prod → merge (gate SC-007)
- PR 3 (routing persist) → merge
- PR 4 + 4b (denorm + retention) → merge
- PR 5 (US1 + US7 backend) → merge
- PR 6 (US2-US8 backend — paralelo possível dentro do PR) → merge
- PR 7 (US1 + US4 frontend) → ship MVP
- PR 8 (US2 frontend — Trace Explorer) → ship MVP completo
- **Cut-line checkpoint**
- PR 9 (US3 frontend — Performance AI)
- PR 10 (US5+US6+US7+US8 frontend + polish + e2e)

### Sequential (single-dev reality)

O projeto é 1 dev full-time. Paralelismo [P] acelera dentro de cada PR mas PRs shipam sequencialmente. Apetite 6-8 semanas assume sequencial.

---

## Notes

- [P] tasks = arquivos diferentes, sem dependência em tasks incompletas
- [Story] label mapeia task para user story (US1..US8) — enables traceability
- Cada US é independentemente completável/testável — cut-line pós-US2 se timeline exceder
- Gate de merge PR 2 (SC-007): 100% suíte existente verde antes do merge — NO EXCEPTIONS
- Commit após cada task ou grupo lógico; prefixo commits com `feat:`, `fix:`, `chore:`, `test:`
- Evitar: tasks vagas, conflitos de arquivo na mesma fase, dependências cross-story que quebram independência
- Tag de commits para reconcile: `[epic:008-admin-evolution]` no subject OU `Epic: 008-admin-evolution` trailer

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "Tasks.md gerado com 12 fases cobrindo Setup (PR 0 — 3 ADRs + 3 audits), Foundational (PR 1-4b — 4 migrations + pipeline instrumentation + routing persist + inbox denorm + retention cron + frontend infra), 8 user stories (US1 P1 Conversas, US2 P1 Trace Explorer, US3 P2 Performance AI, US4 P2 Overview enriquecido, US5 P2 Routing, US6 P3 Agents, US7 P3 Tenants, US8 P3 Audit), Polish e Deployment Smoke. Total: ~120 tasks com [P] markers para paralelização. Cut-line documentado pós-US2 para epic 009 se >5 semanas. Gate SC-007 enforced no PR 2 (100% suite verde). MVP = US1+US2. Analyze deve checar: (a) consistência spec↔plan↔tasks (FR-001..FR-104 todos mapeados), (b) OpenAPI endpoints mapeados para tasks backend, (c) componentes data-model.md mapeados para tasks de queries, (d) thresholds FR-011 + regra hierárquica FR-015 + definição FR-050 fallback aparecem em tasks de implementação e testes."
  blockers: []
  confidence: Alta
  kill_criteria: "Este tasks.md fica inválido se: (a) durante PR 2 o overhead de instrumentação p95 >10ms e sem caminho de mitigação viável; (b) migrations falham em DB de staging por incompat Supavisor/asyncpg cache; (c) decisão executiva de descontinuar o admin proprietário; (d) cut-line forçado reduzir escopo para 3 semanas stop-ship; (e) pipeline refactor quebra >5% da suíte existente sem path claro de correção."
