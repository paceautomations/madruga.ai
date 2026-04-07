---
title: "Containers"
updated: 2026-04-07
sidebar:
  order: 4
---
# ProsaUAI — Container Architecture (C4 Level 2)

> C4 Level 2: containers, responsabilidades e comunicacao entre componentes.
>
> BCs e aggregates → ver [domain-model.md](../domain-model/) · Integracoes externas → ver [integrations.md](../integrations/)

---

## Container Diagram

```mermaid
graph LR
    %% Actors
    agent(("Agente WhatsApp"))
    admin_user(("Admin / Operador"))

    subgraph prosauai ["ProsaUAI Platform"]
        subgraph prosauai_api ["prosauai-api :8040"]
            api_webhook["Webhook receiver<br/><small>HMAC-SHA256 validation</small>"]
            api_rest["REST endpoints<br/><small>/api/v1/*</small>"]
            api_socketio["Socket.io gateway<br/><small>realtime push</small>"]
        end

        subgraph prosauai_worker ["prosauai-worker"]
            wk_debounce["Debounce flush<br/><small>Redis Lua 3s + jitter</small>"]
            wk_llm["LLM orchestration<br/><small>via Bifrost proxy</small>"]
            wk_delivery["Delivery + retry<br/><small>3x backoff</small>"]
            wk_eval["Eval batch jobs<br/><small>DeepEval offline</small>"]
            wk_trigger["Trigger evaluator<br/><small>PG LISTEN/NOTIFY</small>"]
        end

        subgraph prosauai_admin ["prosauai-admin :3000"]
            adm_dash["Dashboard<br/><small>metricas por tenant</small>"]
            adm_conv["Conversation viewer<br/><small>realtime via Socket.io</small>"]
            adm_prompt["Prompt manager<br/><small>versionamento</small>"]
            adm_handoff["Handoff queue<br/><small>fila de atendimento</small>"]
        end
    end

    subgraph storage ["Storage"]
        redis["Redis 7<br/><small>arq: buf: cache: ps:</small>"]
        supabase-prosauai[("Supabase ProsaUAI<br/><small>PG 15 + pgvector + RLS</small>")]
    end

    subgraph llm_proxy ["LLM Proxy"]
        bifrost["Bifrost :8050<br/><small>Go — rate limit + fallback</small>"]
    end

    subgraph external ["External Services"]
        evolution-api["Evolution API<br/><small>WhatsApp gateway</small>"]
        supabase-resenhai[("Supabase ResenhAI<br/><small>PG 15 read-only</small>")]
        openai-gpt-mini["OpenAI GPT mini<br/><small>classification + generation</small>"]
        langfuse["LangFuse v3<br/><small>tracing + eval</small>"]
        infisical["Infisical<br/><small>secrets vault</small>"]
    end

    %% Actor → Platform
    agent -- "HTTPS" --> api_webhook
    evolution-api -- "webhook POST<br/>HMAC-SHA256" --> api_webhook
    admin_user -- "HTTPS + JWT" --> prosauai_admin

    %% API internal
    api_webhook -- "XADD stream:messages" --> redis
    api_webhook -- "SET dedup message_id<br/>TTL 24h" --> redis
    api_rest -- "asyncpg SQL" --> supabase-prosauai
    api_socketio -- "WebSocket" --> adm_conv

    %% Admin → API
    prosauai_admin -- "REST /api/v1/*" --> api_rest
    prosauai_admin -- "Supabase JS client<br/>Auth + queries" --> supabase-prosauai

    %% Redis → Worker
    redis -- "XREADGROUP<br/>BLOCK 5000ms" --> wk_debounce

    %% Worker processing
    wk_debounce -- "BufferedBatch" --> wk_llm
    wk_llm -- "POST /v1/chat/completions" --> bifrost
    wk_llm -- "asyncpg SQL" --> supabase-prosauai
    wk_llm -- "asyncpg read-only" --> supabase-resenhai
    wk_delivery -- "POST sendText" --> evolution-api
    wk_delivery -- "PUBLISH ps:events" --> redis
    wk_eval -. "HTTPS SDK<br/>fire-and-forget" .-> langfuse
    wk_trigger -- "SDK secret read<br/>cached 5min" --> infisical

    %% PG events → Worker
    supabase-prosauai -. "PG LISTEN/NOTIFY<br/>games, group_members" .-> wk_trigger

    %% Bifrost → LLMs
    bifrost -- "OpenAI API" --> openai-gpt-mini
```

---

## Container Matrix

<!-- Tech choices justified in Blueprint — list technology here without justification -->

| # | Container | Bounded Context | Tecnologia | Responsabilidade | Protocol In | Protocol Out |
|---|-----------|----------------|------------|------------------|-------------|-------------|
| 1 | prosauai-api | Channel | Python 3.12 + FastAPI | Webhook receiver, REST endpoints, Socket.io gateway | HTTPS (webhook, REST) | Redis Streams, Socket.io, asyncpg |
| 2 | prosauai-worker | Conversation, Safety, Operations, Observability | Python 3.12 + ARQ | Debounce (Lua 3s + jitter), LLM orchestration (semaphore cap), delivery, eval, triggers. Concurrency: `max_jobs=20`, `llm_semaphore=10`, backpressure at queue depth > 100 | Redis Streams (XREADGROUP) | asyncpg, HTTP (Bifrost, Evolution), HTTPS (LangFuse) |
| 3 | prosauai-admin | — (apresentacao) | Next.js 15 + shadcn/ui | Dashboard, conversation viewer, prompt manager, handoff queue | HTTPS + JWT | REST API, Supabase JS |
| 4 | Redis 7 | — (infra) | Redis | Message streams, cache, PubSub, debounce state | Redis protocol | Redis protocol |
| 5 | Supabase ProsaUAI | — (infra) | PG 15 + pgvector + RLS | Persistent state multi-tenant | asyncpg SQL, Supabase JS | PG LISTEN/NOTIFY |
| 6 | Bifrost | — (proxy) | Go binary | LLM proxy: rate limit, cost tracking | HTTP POST | OpenAI API |
| 7 | LangFuse v3 | Observability | Docker (self-hosted) | Tracing LLM, eval, prompt versioning | HTTPS SDK | — |
| 8 | Infisical | — (infra) | Docker (self-hosted) | Secrets vault: envelope encryption, rotation | HTTPS REST SDK | — |
| 9 | Evolution API | Channel | Cloud mode (managed) | WhatsApp gateway: send/receive messages | HTTP POST (sendText) | Webhook POST |

---

## Communication Protocols

| De | Para | Protocolo | Padrao | Justificativa |
|----|------|-----------|--------|---------------|
| Evolution API | prosauai-api | HTTPS webhook (HMAC-SHA256) | async | WhatsApp messages inbound |
| prosauai-api | Redis | XADD stream:messages | async | Desacoplamento intake → processing |
| prosauai-api | prosauai-admin | Socket.io WebSocket | async (push) | Realtime updates (new messages, handoff alerts) |
| Redis | prosauai-worker | XREADGROUP (BLOCK 5000ms) | async (pull) | Consumer group permite horizontal scaling |
| prosauai-worker | Bifrost | POST /v1/chat/completions | sync | LLM request-response |
| prosauai-worker | Supabase ProsaUAI | asyncpg SQL | sync | CRUD + RLS per transaction |
| prosauai-worker | Evolution API | POST sendText/{instance} | sync | Envio de resposta ao WhatsApp |
| prosauai-worker | LangFuse | HTTPS SDK | async (fire-and-forget) | Tracing sem bloquear pipeline |
| prosauai-worker | Infisical | HTTPS REST SDK (cached 5min) | sync | Secret retrieval |
| Supabase ProsaUAI | prosauai-worker | PG LISTEN/NOTIFY | async (event-driven) | Triggers proativos (games, group_members) |
| prosauai-admin | prosauai-api | REST /api/v1/* | sync | CRUD operations |
| Bifrost | OpenAI GPT mini | OpenAI API | sync | LLM inference |

---

## Scaling Strategy

| Container | Estrategia | Trigger | Notas |
|-----------|-----------|---------|-------|
| prosauai-api | Horizontal | CPU > 70% ou latencia p95 > 500ms | Stateless — qualquer instancia serve |
| prosauai-worker | Horizontal | Queue depth > 100 msgs | Redis consumer groups distribui carga. Cada instancia: `max_jobs=20` (ARQ), `llm_semaphore=10` (asyncio), backpressure se fila > 100. Jitter 0-1s no Lua TTL previne avalanche de flushes |
| prosauai-admin | Horizontal | Usuarios concorrentes > 100 | Stateless Next.js |
| Redis | Single + Sentinel | — | HA via Sentinel; vertical para throughput |
| Supabase | Vertical (managed) | Conexoes > 80% pool | Managed pelo provider |
| Bifrost | Horizontal | RPM > 1000 | Stateless Go proxy |
| LangFuse | Single instance | — | Tracing nao e critico para pipeline |
| Infisical | Single instance | — | Cache 5min no client reduz load |

> NFRs globais e targets mensuraveis → ver [blueprint.md](../blueprint/)

---

## Premissas e Decisoes

| # | Decisao | Alternativas Consideradas | Justificativa |
|---|---------|---------------------------|---------------|
| 1 | Separar API e Worker em containers distintos | Monolito com threads — rejeitado: scaling independente necessario | Worker processa LLM (lento), API precisa ser rapida para webhooks |
| 2 | Redis como message broker (nao RabbitMQ/Kafka) | RabbitMQ — rejeitado: overhead operacional. Kafka — overkill para ~500 RPM | Redis Streams cobre consumer groups + DLQ + backpressure |
| 3 | Bifrost como proxy LLM separado | SDK direto no worker — rejeitado: rate limiting centralizado + fallback chain | Go binary leve, stateless, horizontal |
| 4 | Next.js para admin (nao React SPA) | SPA puro — rejeitado: SSR melhora SEO/perf para dashboards | Next.js 15 + shadcn/ui — produtividade alta |

---

> **Proximo passo:** `/madruga:context-map prosauai` — mapear relacionamentos DDD entre bounded contexts.
