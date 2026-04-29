---
title: "Roadmap"
updated: 2026-04-17
---
# ProsaUAI — Delivery Roadmap

> Sequenciamento de epics, milestones e definicao de MVP. Atualizado: 2026-04-13 (MVP completo — todos 6 epics shipped).

---

## Status

**Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin + Post-MVP implementados**.
**L1 Pipeline:** 12/13 nodes completos. Revisao completa realizada em 2026-04-07.
**L1 Pendente:** codebase-map (opcional — plataforma greenfield, sem valor agregado).
**L2 Status:** Epics 001–009 shipped. **Epics 010–012 implementados** (tasks.md completo, reconcile pendente). **Epic 015 shipped**. **Epic 016 shipped** (Trigger Engine — 3 trigger types, cooldown + daily cap, evolution send_template, 231 testes, judge 82%, QA pass).
**Proximo marco:** reconcile epics 010–012 + primeiro deploy de producao VPS.

---

## MVP

**MVP Epics:** 001-channel-pipeline + 002-observability + 003-multi-tenant-foundation + 004-router-mece + 005-conversation-core + 006-production-readiness
**MVP Criterion:** Agente recebe mensagem WhatsApp **multi-tenant** (>=2 instancias Evolution reais), parseia 100% dos payloads reais, responde com IA, persiste em BD, **com observabilidade total da jornada**, **router MECE provado em CI**, e **infra production-ready** (schema isolation, log persistence, data retention, host monitoring).
**Total MVP Estimate:** ~7-8 semanas (realizado)
**Progresso MVP:** **100%** (todos 6 epics shipped)

---

## Delivery Sequence

```mermaid
gantt
    title Roadmap ProsaUAI
    dateFormat YYYY-MM-DD
    section MVP
    001 Channel Pipeline (DONE)   :done, a1, 2026-04-08, 1d
    002 Observability (DONE)       :done, a2, after a1, 1w
    003 Multi-Tenant Foundation (DONE) :done, a3, after a2, 1w
    004 Router MECE (DONE)         :done, a4, after a3, 1w
    005 Conversation Core (DONE)    :done, a5, after a4, 2w
    006 Production Readiness (DONE) :done, a6, after a5, 1w
    section Admin
    007 Admin Front Foundation (DONE) :done, a7, after a6, 1w
    008 Admin Evolution (IN PROGRESS) :active, a8, after a7, 6w
    012 Admin Dashboard (absorvido por 008) :a12, after a8, 0d
    013 Admin Handoff Inbox :a13, after a10, 1w
    section Post-MVP
    009 Agent Tools         :a9, after a6, 2w
    010 Handoff Engine      :a10, after a6, 2w
    011 Trigger Engine      :a11, after a10, 1w
```

---

## Epic Table

> **Convencao:** apenas epics shipped/in-progress/drafted tem pitch file criado. Demais sao sugestoes — arquivos serao criados sob demanda quando o epic for iniciado via `/madruga:epic-context`.
>
> **Renumeracao 2026-04-10 (2a):** Slot 003 reservado para novo epic (escopo a definir pelo usuario). Router MECE movido de draft@003 para draft@004. Epics a partir do antigo 003 bumpados +2 (Conversation Core → 005, Configurable Routing → 006, etc.). Router MECE (004) reduz escopo do 006 drasticamente — engine declarativa ja entrega.
>
> **Definicao do slot 003 (2026-04-10):** epic 003 agora e **Multi-Tenant Foundation** (auth + parser reality fix + deploy isolado + tenant abstraction). Pre-requisito duro para 004+, baseado em [docs/prosauai/IMPLEMENTATION_PLAN.md](../../../docs/prosauai/IMPLEMENTATION_PLAN.md). Sequencia 003 + 004 e back-to-back, single prod deploy apos os dois mergerem. Fase 2 (Caddy + Admin API + rate limit) e Fase 3 (Postgres TenantStore + billing) **documentadas agora** em [ADR-021](../decisions/ADR-021-caddy-edge-proxy.md), [ADR-022](../decisions/ADR-022-admin-api.md), [ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md).
>
> **Renumeracao 2026-04-12 (3a):** Slot 006 inserido para **Production Readiness** (schema isolation, log persistence, data retention, particionamento, host monitoring, migration runner). Gaps identificados ao cruzar ADRs aprovados com estado real do codigo. Antigo 006 (Configurable Routing) → 007. Demais epics bumpados +1. Epics futuros re-referenciados.
>
> **Renumeracao 2026-04-17 (4a):** Slot 008 adotado para **Admin Evolution** (plataforma operacional completa — 8 abas). Antigo "008 Agent Tools" → 009, "009 Handoff Engine" → 010, "010 Trigger Engine" → 011. Slot 007 preenchido com "Admin Front Foundation" (shipped — sidebar+login+pool_admin+dbmate, substituiu o antigo "Configurable Routing DB" que foi absorvido pelo epic 004). Slot "011 Admin Dashboard" absorvido por 008 (8 abas supera o escopo original). "012 Admin Handoff Inbox" → 013 (depende de 010 Handoff Engine). Ref: [epics/008-admin-evolution/decisions.md](../epics/008-admin-evolution/decisions.md) decisao 1.

| Ordem | Epic | Deps | Risco | Milestone | Status |
|-------|------|------|-------|-----------|--------|
| 1 | 001: Channel Pipeline | — | baixo | MVP | **shipped** (52 tasks, 122 testes, judge 92%) |
| 2 | 002: Observability (Phoenix + OTel) | 001 | medio | MVP | **shipped** (Phoenix + OTel SDK + structlog bridge) |
| 3 | 003: Multi-Tenant Foundation (auth + parser reality + deploy) | 002 | medio | MVP | **shipped** (TenantStore YAML, X-Webhook-Secret auth, 26 fixtures, idempotency Redis) |
| 4 | 004: Router MECE | 003 | medio | MVP | **shipped** (classify() + RoutingEngine declarativa, MECE 4 camadas, config YAML per-tenant) |
| 5 | 005: Conversation Core | 004 | medio | MVP | **shipped** (conversation pipeline 12-step, LLM agent pydantic-ai, safety guards 3-layer, tool registry, 52 test files) |
| 6 | 006: Production Readiness | 005 | baixo | MVP | **shipped** (schema isolation, migration runner, data retention LGPD, log persistence, host monitoring Netdata — 34 tasks, 67 testes, judge 88%, QA 100%) |
| 7 | 007: Admin Front Foundation | 006 | baixo | Admin | **shipped** (sidebar+login Next.js 15, pool_admin BYPASSRLS, dbmate migrations, dashboard inicial) |
| 8 | **008: Admin Evolution** | 006, 007 | medio | Admin | **shipped** (8 abas, traces/trace_steps/routing_decisions, ~25 endpoints, pipeline instrumentation — judge pass, QA pass, reconcile 2026-04-28) |
| 9 | **009: Channel Ingestion + Content Processing** | 006 | medio | Post-MVP | **shipped** (multi-source channel adapter ADR-031, content processing pipeline ADR-032 — judge pass, QA pass, reconcile 2026-04-28) |
| 10 | **010: Handoff Engine + Inbox** | 006 | medio | Post-MVP | **implementado** (HelpdeskAdapter Protocol ADR-037, ChatwootAdapter + NoneAdapter ADR-038, ai_active unified state ADR-036, handoff_events + bot_sent_messages — reconcile pendente) |
| 11 | **011: Evals** | 006 | medio | Post-MVP | **implementado** (reconcile pendente) |
| 12 | **012: Tenant Knowledge Base RAG** | 006 | medio | Post-MVP | **implementado** (reconcile pendente) |
| 13 | 013: Admin Handoff Inbox | 010 | baixo | Admin | sugerido (depende de 010 Handoff Engine) |
| 15 | **015: Agent Pipeline Steps** | 008, 005 | medio | Post-MVP | **shipped** (agent pipeline steps configuravel, sub-steps — judge pass, QA pass, reconcile 2026-04-28) |
| 16 | **016: Trigger Engine** | 010 | baixo | Post-MVP | **shipped** (3 trigger types, YAML config, cooldown+daily cap Redis, send_template Evolution, 231 testes, judge 82%, QA pass — reconcile 2026-04-29) |

### Epics Futuros (criados conforme necessidade)

| Epic | Descricao | Deps Provavel | Prioridade |
|------|-----------|---------------|------------|
| 013: Multi-Tenant Public API (Fase 2) | Caddy edge proxy + admin API (CRUD tenants) + rate limiting per-tenant + onboarding externo. **Trigger: primeiro cliente externo pagante.** | 003, 012 | Later |
| 014: TenantStore Postgres + Ops (Fase 3) | Migracao YAML → Postgres com schema gerenciado; circuit breaker per-tenant; billing/usage tracking; alertas Prometheus. **Trigger: >=5 tenants reais ou dor operacional.** | 013, 018 | Later |
| 015: Evals Offline | Score automatico por conversa (faithfulness, relevance, toxicity) — **fundacao em 002** | 006, 002 | Next |
| 016: Evals Online | Guardrails pre/pos-LLM em tempo real — **traces em 002** | 006, 002 | Next |
| 017: Data Flywheel | Ciclo semanal de melhoria com revisao humana | 015, 016 | Later |
| 018: Multi-Tenant Self-Service | Cadastro self-service, onboarding autonomo (depende de Admin API do 013) | 013, 011 | Later |
| 019: RAG pgvector | Base de conhecimento com embeddings por tenant | 006 | Later |
| 020: Billing Stripe | Cobranca automatica com tiers e consumo medido | 014, 018 | Later |
| 021: WhatsApp Flows | Formularios estruturados dentro do WhatsApp | 006 | Later |
| 022: Agent Pipeline Steps | Pipeline de processamento configuravel por agente (classifier → clarifier → resolver → specialist) | 008 | Later |

---

## Dependencies

```mermaid
graph LR
  E001[001 Channel Pipeline] --> E002[002 Observability]
  E002 --> E003[003 Multi-Tenant Foundation]
  E003 --> E004[004 Router MECE]
  E004 --> E005[005 Conversation Core]
  E005 --> E006[006 Production Readiness]
  E006 --> E007[007 Admin Front Foundation - DONE]
  E007 --> E008[008 Admin Evolution - IN PROGRESS]
  E006 --> E009[009 Agent Tools]
  E006 --> E010[010 Handoff Engine]
  E010 --> E016[016 Trigger Engine - DONE]
  E010 --> E011[011 Evals]
  E010 --> E012[012 Knowledge Base RAG]
  E008 --> E015[015 Agent Pipeline Steps - DONE]
  E010 --> E013[013 Admin Handoff Inbox]
  E009 --> E022[022 Agent Pipeline Steps]
  E003 -.-> E013[013 Public API Fase 2]
  E013 -.-> E014[014 Postgres + Ops Fase 3]
  E002 -.-> E015[015 Evals Offline]
  E002 -.-> E016[016 Evals Online]
```

---

## Milestones

| Milestone | Epics | Criterio de Sucesso | Estimativa |
|-----------|-------|---------------------|------------|
| **MVP** | 001, 002, 003, 004, 005, 006 | ✅ **COMPLETO.** Agente responde mensagens WhatsApp **multi-tenant** com IA, parseia 100% dos payloads reais, persiste conversas, funciona em grupo, **com observabilidade total + router MECE provado em CI + infra production-ready** (schema isolation, logs, retention, monitoring) | realizado |
| **Admin** | 007, 008, 013 | 007 ✅ shipped (foundation) · **008 in-progress** (Admin Evolution — 8 abas operacionais, 152/158 tasks) · 013 sugerido (Handoff Inbox, depende de 010) | ~8 semanas (007+008 realizadas) |
| **Post-MVP** | 009, 010, 011, 012, 015, 016 | ✅ **Ciclo concluido**: Channel Ingestion (009), Handoff Engine (010), Evals (011), Knowledge Base RAG (012), Agent Pipeline Steps (015), Trigger Engine (016) — todos implementados ou shipped. | realizado |
| **Public API (Fase 2)** | 013 | Caddy + Admin API + onboarding de cliente externo. Trigger: primeiro cliente pagante. | ~2 semanas |
| **Ops (Fase 3)** | 014 | TenantStore Postgres + circuit breaker + billing + alertas. Trigger: >=5 tenants reais ou dor operacional | ~3 semanas |

---

## Riscos do Roadmap

| Risco | Status | Impacto | Probabilidade | Mitigacao |
|-------|--------|---------|---------------|-----------|
| Evolution API payload muda entre versoes | **Mitigado (epic 001)** | Baixo | Baixa | Adapter pattern + 122 testes com fixtures reais |
| Custo LLM acima do esperado no MVP | **Parcialmente mitigado (epic 005)** | Medio | Baixa | pydantic-ai com modelo configuravel por agente + semaforo concorrencia (10). Bifrost (rate limit + spend cap) planejado para Fase 3 |
| Complexidade de grupo subestimada | **Eliminado (epic 001)** | — | — | Smart Router 6 rotas funcional |
| Observability ops complexity | **Mitigado (epic 002)** | Baixo | Baixa | Phoenix (Arize) substitui LangFuse — single container, Postgres backend, sem ClickHouse ([ADR-020](../decisions/ADR-020-phoenix-observability.md)) |
| OTel overhead em hot path do webhook | **Mitigado (epic 002)** | Baixo | Baixa | Sampling configuravel + BatchSpanProcessor fire-and-forget |
| Reconcile pendente do epic 001 (12 propostas) | **Eliminado (epic 002)** | — | — | Aplicado durante epic 002 |
| Router nao-MECE hardcoded bloqueia agent resolution | **Eliminado (epic 004)** | — | — | `classify()` puro + `RoutingEngine` declarativa + MECE 4 camadas (tipo/schema/runtime/CI). Agent resolution implementada |
| **Servico rejeita 100% dos webhooks reais (HMAC imaginario)** | **Eliminado (epic 003)** | — | — | X-Webhook-Secret per-tenant validado empiricamente com 2 tenants reais |
| **Parser falha em 50% das mensagens reais (messageType errados)** | **Eliminado (epic 003)** | — | — | 12 correcoes contra 26 fixtures capturadas reais; 13 tipos de mensagem suportados |
| Refactor multi-tenant posterior seria doloroso | **Eliminado (epic 003)** | — | — | Multi-tenant estrutural desde dia 1; 2 tenants reais (Ariel + ResenhAI) operando em paralelo |
| Merge conflict entre 003 (router T7) e 004 (router rip-and-replace) | **Eliminado** | — | — | Sequencia back-to-back executada sem conflitos |
| **Schema collision com Supabase (auth + public)** | **Mitigado (epic 006)** | — | — | Schemas dedicados `prosauai` + `prosauai_ops`. `public.tenant_id()` SECURITY DEFINER. Migrations idempotentes com `gen_random_uuid()` (sem `uuid-ossp`). [ADR-024](../decisions/ADR-024-schema-isolation.md) |
| **Disco VPS cheio (logs + Phoenix SQLite + pgdata)** | **Mitigado (epic 006)** | — | — | Log rotation Docker json-file (max 1.25GB stack). Phoenix Postgres backend em prod. Netdata host monitoring (:19999) |
| **LGPD non-compliance (sem purge de dados)** | **Mitigado (epic 006)** | — | — | retention-cron diario: DROP PARTITION messages, batch DELETE conversations/eval_scores/traces. `--dry-run` default. 17 testes. [ADR-018](../decisions/ADR-018-data-retention-lgpd.md) |
| **`pool_admin.max_size=5` esgota com 2-3 admins simultaneos** | **ABERTO (epic 008 B5)** | Alto | Alta | Aumentar `admin_pool_max_size` para 20 em `config.py` antes do merge; patch no repo externo `paceautomations/prosauai` |
| **8KB truncation de `trace_steps` pode ultrapassar limite em UTF-8 multibyte** | **ABERTO (epic 008 B3)** | Medio | Baixa | Fix em `step_record._truncate_value` (`ensure_ascii=False` + revalidacao de bytes); patch no repo externo |
| **`INSTRUMENTATION_ENABLED` kill switch ausente** | **ABERTO (epic 008 B1)** | Alto | Baixa | Adicionar env flag em `.env.example` + guard em `pipeline.py` e `trace_persist.py`; patch no repo externo |
| **`activate_prompt` sem INSERT em `audit_log`** | **ABERTO (epic 008 B2)** | Alto | Media | Adicionar INSERT em `agents.py:427-454`; patch no repo externo |
| **Phase 12 smoke (epic 008) nunca executado em container real** | **ABERTO (epic 008 B4)** | Alto | Certeza | Executar runbook `benchmarks/pipeline_instrumentation_smoke.md` no primeiro deploy staging |
| **Cost sparkline O(N) round-trips em dashboard** | **Aberto (epic 008 W2)** | Medio | Alta (hit em qualquer dashboard view) | Consolidar em single JOIN ou VIEW materializada antes do epic 009 |
| **ILIKE sem trigram GIN index degrada inbox >10k conversas** | **Aberto (epic 008 W7)** | Medio | Media | Adicionar `pg_trgm` + GIN index antes de 10k conversas; SC-005 inbox <100ms nao garantido em escala |
| **`trigger_events ON DELETE CASCADE` sem DPO sign-off (epic 016 S1)** | **ABERTO** | Alto | Media | DPO/juridico deve validar que hard-delete e aceitavel antes de `mode: live` em Ariel. Alternativa (set NULL + redact) disponivel em 016.1+. |
| **Circuit breaker Evolution nao verificado sob 5xx storm (epic 016 W5)** | **A verificar em QA** | Medio | Baixa | Load sintetico com Evolution retornando 5xx consecutivos — confirmar se breaker abre apos N falhas antes de rollout live. |

---

*MVP completo: todos 6 epics shipped (001-006). Admin: 007 e 008 shipped. Post-MVP: 009 shipped; 010-012 implementados (reconcile pendente); 015 e 016 shipped. Proximo: reconcile 010-012 + primeiro deploy de producao VPS.*

---

> **Proximo passo:** Reconcile dos epics 010, 011, 012 (implementados sem reconcile formal). Primeiro deploy de producao VPS apos validacao Ariel shadow (epic 016 rollout). DPO sign-off para `trigger_events ON DELETE CASCADE` antes de `mode: live` (judge-report S1). ADRs 049 e 050 a promover de draft → reviewed.
>
> **Supabase deployment readiness (epic 006):** Migrations hardened (idempotent, `gen_random_uuid()`, sem `uuid-ossp`), tenants table (008) created, dual slug/UUID tenant identity implemented. Schema isolation (`prosauai` + `prosauai_ops`) pronto para Supabase managed.
