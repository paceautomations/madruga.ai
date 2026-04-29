---
title: "Context Map"
updated: 2026-04-17
sidebar:
  order: 3
---
# ProsaUAI — Context Map

> Relacionamentos entre bounded contexts com padroes DDD explicitos.
>
> Definicoes dos BCs → ver [domain-model.md](../domain-model/) · NFRs e stack → ver [blueprint.md](../blueprint/)

---

## Context Diagram

```mermaid
flowchart LR
    subgraph Channel ["Channel<br/><small>#supporting</small>"]
        M1["M1 Recepcao"]
        M2["M2 Debounce"]
        M3["M3 Router"]
        M11["M11 Entrega"]
    end

    subgraph Conversation ["Conversation<br/><small>#core</small>"]
        M4["M4 Clientes"]
        M5["M5 Contexto"]
        M7["M7 Classificador"]
        M8["M8 Agente IA"]
        M9["M9 Avaliador"]
    end

    subgraph Safety ["Safety<br/><small>#supporting</small>"]
        M6["M6 Guardrails Entrada"]
        M10["M10 Guardrails Saida"]
    end

    subgraph Operations ["Operations<br/><small>#supporting</small>"]
        M12["M12 Handoff"]
        M13["M13 Triggers"]
    end

    subgraph Observability ["Observability<br/><small>#generic</small>"]
        M14["M14 Observabilidade"]
    end

    subgraph Admin ["Admin<br/><small>#supporting (cross-tenant)</small>"]
        M15["M15 Admin API (/admin/*)"]
        M16["M16 prosauai-admin :3000"]
    end

    %% External
    evolution-api["Evolution API"]
    redis["Redis"]
    bifrost["Bifrost"]
    supabase-prosauai[("Supabase ProsaUAI")]
    supabase-resenhai[("Supabase ResenhAI")]
    phoenix["Phoenix (Arize)"]

    %% === Pipeline Flow (intra-BC: sem label) ===
    M1 --> M2
    M2 --> M3
    M4 --> M5
    M7 --> M8
    M8 --> M9
    M9 -.->|"RETRY"| M8

    %% === Cross-BC Flow (com label DDD) ===
    evolution-api -- "Conformist" --> M1
    M3 -- "ACL" --> M4
    M3 -- "ACL" --> M12
    M5 -- "Customer-Supplier" --> M6
    M6 -- "Customer-Supplier" --> M7
    M9 -- "Customer-Supplier" --> M10
    M9 -- "Customer-Supplier" --> M12
    M10 -- "Customer-Supplier" --> M11
    M12 --> M11
    M13 -- "Customer-Supplier" --> M11
    M11 -- "Conformist" --> evolution-api

    %% === ACL (external systems) ===
    M2 -- "ACL" --> redis
    M8 -- "ACL" --> bifrost
    M8 -- "ACL" --> supabase-resenhai
    M4 -- "ACL" --> supabase-prosauai

    %% === Pub-Sub (observability) ===
    M1 -. "Pub-Sub" .-> M14
    M5 -. "Pub-Sub" .-> M14
    M8 -. "Pub-Sub" .-> M14
    M9 -. "Pub-Sub" .-> M14
    M12 -. "Pub-Sub" .-> M14
    M13 -. "Pub-Sub" .-> M14

    %% === Observability → External ===
    M14 -- "Conformist" --> phoenix

    %% === Pipeline → Admin (fire-and-forget, epic 008 / ADR-028) ===
    M1 -. "fire-and-forget" .-> M15
    M3 -. "fire-and-forget" .-> M15
    M9 -. "fire-and-forget" .-> M15

    %% === Admin API → UI ===
    M15 -- "REST /admin/*" --> M16

    %% === Admin → Supabase (pool_admin BYPASSRLS, ADR-027) ===
    M15 -- "ACL (pool_admin)" --> supabase-prosauai
```

---

## Relacoes entre Contextos

| # | De | Para | Padrao | Justificativa |
|---|-----|------|--------|---------------|
| 1 | Evolution API → Channel (M1) | Conformist | Channel aceita o schema de webhooks sem traducao |
| 2 | Channel (M1) → Channel (M2) | Intra-BC | Mensagem normalizada segue para debounce |
| 3 | Channel (M2) → Channel (M3) | Intra-BC | Batch debounced segue para roteamento |
| 4 | Channel (M3) → Conversation (M4) | ACL | Traduz InboundMessage → ConversationRequest |
| 5 | Channel (M3) → Operations (M12) | ACL | Bypass IA — acao BYPASS_AI direto para handoff |
| 6 | Conversation (M4) → Conversation (M5) | Intra-BC | CustomerContext alimenta montagem de contexto |
| 7 | Conversation (M5) → Safety (M6) | Customer-Supplier | AgentContext validado por guardrails de entrada |
| 8 | Safety (M6) → Conversation (M7) | Customer-Supplier | Mensagem sanitizada segue para classificacao |
| 9 | Conversation (M7) → Conversation (M8) | Intra-BC | IntentClassification alimenta agente IA |
| 10 | Conversation (M8) → Conversation (M9) | Intra-BC | AgentResponse avaliada por quality check |
| 11 | Conversation (M9) → Conversation (M8) | Intra-BC | RETRY — score 0.5-0.8, max 2 tentativas |
| 12 | Conversation (M9) → Safety (M10) | Customer-Supplier | APPROVE — resposta segue para guardrails de saida |
| 13 | Conversation (M9) → Operations (M12) | Customer-Supplier | ESCALATE — handoff quando score < 0.5 |
| 14 | Safety (M10) → Channel (M11) | Customer-Supplier | Payload formatado segue para entrega |
| 15 | Operations (M12) → Channel (M11) | Intra-flow | Resposta humana entregue via bot |
| 16 | Operations (M13) → Channel (M11) | Customer-Supplier | Trigger Engine (cron 15s) identifica clientes elegíveis via SQL matchers → verifica cooldown/daily-cap Redis → renderiza template (Jinja2 sandbox) → `EvolutionProvider.send_template()` → persiste `trigger_events`. Anti-spam: cooldown per `(tenant,customer,trigger_id)` + daily cap `(tenant,customer,date)` (FR-012/013). ADR-049. |
| 17 | Channel (M11) → Evolution API | Conformist | Entrega outbound via WhatsApp gateway |
| 18 | Conversation (M8) → Bifrost | ACL | Traduz para formato OpenAI-compatible |
| 19 | Conversation (M8) → Supabase ResenhAI | ACL | Acesso read-only com ACL isolando schema externo |
| 20 | Conversation (M4) → Supabase ProsaUAI | ACL | Repositories com ACL isolam domain models do schema SQL |
| 21 | Channel (M2) → Redis | ACL | Debounce via Lua scripts com ACL isolando detalhes |
| 22 | M1, M5, M8, M9, M12, M13 → Observability (M14) | Pub-Sub | Eventos de todos os modulos para tracing passivo |
| 23 | Observability (M14) → Phoenix (Arize) | Conformist | Conforma-se ao OTel SDK/OTLP gRPC do Phoenix |
| 24 | Pipeline (M1, M3, M9) → Admin API (M15) | Pub-Sub (fire-and-forget) | [ADR-028](../decisions/ADR-028-pipeline-fire-and-forget-persistence/) — escrita assincrona de `traces`/`trace_steps`/`routing_decisions` sem acoplar caminho critico (epic 008) |
| 25 | Admin API (M15) → prosauai-admin (M16) | Customer-Supplier | Endpoints REST `/admin/*` consumidos pela UI Next.js 15 (TanStack Query + tipos gerados via openapi-typescript) |
| 26 | Admin API (M15) → Supabase ProsaUAI | ACL (pool_admin) | Leituras cross-tenant via `pool_admin` com BYPASSRLS — sem `SET LOCAL app.current_tenant_id` ([ADR-027](../decisions/ADR-027-admin-tables-no-rls/)) |

---

## Classificacao de Dominios

| Tipo | Bounded Context | Justificativa |
|------|----------------|---------------|
| **Core** | Conversation | Pipeline IA — diferencial competitivo |
| **Supporting** | Channel | Ingestao/entrega — necessario mas substituivel |
| **Supporting** | Safety | Guardrails — critico mas nao diferenciador |
| **Supporting** | Operations | Handoff/triggers — regras de negocio mas nao core |
| **Generic** | Observability | Tracing — poderia ser ferramenta externa |
| **Supporting (cross-tenant)** | Admin | Plataforma operacional — 8 abas consultam dados cross-tenant via `pool_admin`; necessario para ops mas nao diferenciador (epic 008) |

---

## Padroes Utilizados

| Padrao | Descricao | Quando Usar | Usado Em |
|--------|-----------|-------------|----------|
| **Conformist** | Downstream adota modelo do upstream sem traducao | Upstream estavel e confiavel | Evolution API → Channel, Channel → Evolution API, Observability → Phoenix |
| **ACL** | Traduz modelo externo para modelo interno | Upstream tem modelo diferente | Channel → Conversation, Channel → Operations, Conversation → Bifrost/Supabase, Channel → Redis, Admin API → Supabase (pool_admin) |
| **Customer-Supplier** | Upstream adapta-se ao que downstream precisa | Downstream tem poder de negociacao | Conversation → Safety, Safety → Conversation, Conversation → Operations, Safety → Channel, Operations → Channel, Admin API → prosauai-admin UI |
| **Pub-Sub** | Publicacao de eventos sem acoplamento direto | Observabilidade passiva | Todos os modulos → Observability; Pipeline (M1/M3/M9) → Admin (fire-and-forget, ADR-028) |
| **Intra-BC** | Fluxo interno dentro do mesmo bounded context | Modulos do mesmo BC | M1→M2→M3 (Channel), M4→M5 / M7→M8→M9 (Conversation) |

---

## Anti-Padroes Monitorados

| Anti-Padrao | Risco | Status |
|------------|-------|--------|
| Big Ball of Mud | Sem boundaries claros | OK — 5 BCs com fronteiras definidas |
| Shared Kernel excessivo | Acoplamento forte | OK — zero shared kernels |
| God Context | 1 contexto faz tudo | ATENCAO — Conversation tem 5 modulos (M4-M9) |
| Contexto isolado | Contexto sem relacoes | OK — todos os BCs tem relacoes |

---

> **Proximo passo:** `/madruga:epic-breakdown prosauai` — quebrar o projeto em epics Shape Up.
