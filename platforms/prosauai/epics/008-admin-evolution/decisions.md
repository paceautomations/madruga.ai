---
epic: 008-admin-evolution
created: 2026-04-17
updated: 2026-04-17
---
# Registro de Decisoes — Epic 008

1. `[2026-04-17 epic-context]` Adotar slot 008 para "Admin Evolution"; bumpar 008→009 (Agent Tools), 009→010 (Handoff), 010→011 (Trigger), 011→012 (Admin Dashboard), 012→013 (Admin Handoff Inbox) no roadmap-reassess final (ref: planning/roadmap.md)
2. `[2026-04-17 epic-context]` Epico unico cobrindo 9 abas (sidebar + Overview + Conversations + Trace Explorer + Performance AI + Agents + Routing + Tenants + Audit) — decisao consciente de exceder appetite Shape Up (ref: reference-spec.md)
3. `[2026-04-17 epic-context]` Tabelas dedicadas public.traces + public.trace_steps (NAO usar messages.metadata JSONB) — schema enforced, queries 10x mais rapidas, espelha estrutura Phoenix sem dependencia de API (ref: precedente madruga-ai/017)
4. `[2026-04-17 epic-context]` Refactor de Pipeline.execute() em apps/api: buffer in-memory List[StepRecord], batch INSERT (1 transacao) no fim do pipeline. Falha do INSERT NAO bloqueia entrega da resposta — log + skip, mesmo padrao do Phoenix exporter (ref: apps/api/prosauai/conversation/pipeline.py)
5. `[2026-04-17 epic-context]` Phoenix coupling out-of-scope para v1. Espelhamos trace_id mas nao consumimos Phoenix API. Enrichment via Phoenix vira epico futuro (ref: epic 002)
6. `[2026-04-17 epic-context]` Nova tabela public.routing_decisions populada no hot path do RoutingEngine.evaluate(). Sem RLS — acesso pool_admin only (ref: apps/api/prosauai/router/)
7. `[2026-04-17 epic-context]` Adicionar colunas last_message_id, last_message_at, last_message_preview (TEXT 200 char) em conversations. Update no save_outbound/save_inbound do pipeline. Justificativa: lista 320px-column precisa ser <100ms para >10k conversas (ref: epic 005 pipeline)
8. `[2026-04-17 epic-context]` Redis 5-min TTL nos endpoints /admin/metrics/performance (heatmap + percentis + cost). Sem materialized views v1 — adotar quando P95 do endpoint >2s (ref: epic 005 — Redis ja presente)
9. `[2026-04-17 epic-context]` Tenant filter via URL query param ?tenant=xxx — fonte unica de verdade. Server Components leem via searchParams prop. Default = all. Header dropdown faz router.push (ref: Next.js 15 App Router pattern)
10. `[2026-04-17 epic-context]` Stack frontend: Next.js 15 App Router + shadcn/ui + Tailwind v4 + Recharts + TanStack Query + lucide-react (ja estabelecidos em 007). NAO introduzir Tremor, MUI ou outras libs UI (ref: epic 007 / ADR-010)
11. `[2026-04-17 epic-context]` Dark mode forcado (principio 5 da spec). Sem toggle light no v1 (ref: reference-spec.md)
12. `[2026-04-17 epic-context]` Todas queries via pool_admin (BYPASSRLS). Sem nova role (ref: ADR-011 / epic 007)
13. `[2026-04-17 epic-context]` dbmate como migration tool, proxima sequencia 20260420000001+ (ref: epic 007)
14. `[2026-04-17 epic-context]` JWT cookie admin_token existente — NAO migrar para httpOnly aqui (segue follow-up de 007) (ref: epic 007)
15. `[2026-04-17 epic-context]` Live activity feed: polling 15s contra UNION de queries SQL (novas conversas, fechadas sem handoff, SLA breach, fallback intent, errors em traces). Socket.io NAO entra (ref: docs spec)
16. `[2026-04-17 epic-context]` Inbox search ILIKE para v1. Migrar para tsvector + GIN quando >10k conversas ou P95 >500ms (ref: docs spec)
17. `[2026-04-17 epic-context]` traces.cost_usd calculado no fim do pipeline: tokens_in × $/1k_in + tokens_out × $/1k_out. Mapping de preco em apps/api/prosauai/conversation/pricing.py (constante hardcoded v1) (ref: apps/api/prosauai/conversation/agent.py)
18. `[2026-04-17 epic-context]` Novas tabelas em public.* (segue drift conhecido de ADR-024 — epic 007 documentou esse trade-off). Cleanup para schema prosauai continua em backlog (ref: ADR-024 known drift)
19. `[2026-04-17 epic-context]` Activity feed events derivados via UNION ALL de SELECTs (NAO criar tabela de eventos). Cada UNION limitado por LIMIT 10 + GLOBAL ORDER BY DESC LIMIT 50. Cache Redis 10s (ref: minimizacao de novas tabelas)
20. `[2026-04-17 epic-context]` Aba Routing inclui: tabela de regras ativas (in-memory state via /admin/routing/rules), distribuicao de decisoes (donut), tabela de decisoes recentes (incluindo DROPs), top-N reasons (ref: docs spec)
21. `[2026-04-17 epic-context]` Performance heatmap 24×7 de erros: query GROUP BY EXTRACT(hour) + EXTRACT(dow) FROM traces WHERE status='error'. Cache Redis 5min (ref: docs spec)
22. `[2026-04-17 epic-context]` trace_steps.input_jsonb e output_jsonb truncados em 8KB cada no insert (UI mostra [truncated] + link para Phoenix se passar) (ref: bound storage)
23. `[2026-04-17 epic-context]` retention-cron (epic 006) estendido: DELETE traces + trace_steps + routing_decisions WHERE started_at < now() - retention_days. Default 30d traces, 90d routing_decisions. Configuravel via env (ref: LGPD epic 006)
24. `[2026-04-17 epic-context]` Componentes frontend em apps/admin/src/components/<feature>/: conversations/, traces/, performance/, agents/, routing/, tenants/, audit/. UI primitives compartilhadas em components/ui/ (ref: docs spec layout)
25. `[2026-04-17 epic-context]` Branch externa epic/prosauai/008-admin-evolution criada manualmente no repo prosauai antes deste draft. Na promocao (Path B), reaproveitar a branch existente em vez de tentar criar — evita conflito de worktree (ref: easter-tracking.md incidente epic 004)
