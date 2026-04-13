---
title: "Business Process"
description: 'Fluxo de negocio da plataforma ProsaUAI: mensagem individual (1:1), grupo (@mention), handoff humano, triggers proativos, multi-tenant.'
updated: 2026-04-13
sidebar:
  order: 3
---

# Business Process — Pipeline Completo

Todos os caminhos da plataforma ProsaUAI: mensagem individual (1:1), grupo (@mention), handoff humano, triggers proativos. **14 modulos, 5 tipos de acao de roteamento (RESPOND, LOG_ONLY, DROP, BYPASS_AI, EVENT_HOOK), 3 decision points.**

> [→ Ver arquitetura de containers](../engineering/blueprint/#containers) | [→ Ver domain model](../engineering/domain-model/)

---

## Visao Geral do Pipeline

```mermaid
flowchart TD
    A[/"👤 Agente WhatsApp"/] -->|Mensagem| M1["M1 Recepcao<br/>(Channel)"]
    M1 -->|InboundMessage| M2["M2 Debounce<br/>(Channel)"]
    M2 -->|BufferedBatch| M3{"M3 Smart Router<br/>Decision Point #1"}

    M3 -->|RESPOND| M4["M4 Clientes<br/>(Conversation)"]
    M3 -->|BYPASS_AI| M12["M12 Handoff<br/>(Operations)"]

    M4 -->|CustomerContext| M5["M5 Contexto<br/>(Conversation)"]
    M5 -->|AgentContext| M6["M6 Guardrails Entrada<br/>(Safety)"]
    M6 -->|Sanitizada| M7["M7 Classificador<br/>(Conversation)"]
    M7 -->|Intent| M8["M8 Agente IA<br/>(Conversation)"]
    M8 -->|AgentResponse| M9{"M9 Avaliador<br/>Decision Point #3"}

    M9 -->|"APPROVE (score > 0.8)"| M10["M10 Guardrails Saida<br/>(Safety)"]
    M9 -->|"ESCALATE (score < 0.5)"| M12

    M10 -->|Payload formatado| M11["M11 Entrega<br/>(Channel)"]
    M12 -->|Humano responde| M11

    DB[("Supabase")] -.->|PG LISTEN/NOTIFY| M13["M13 Trigger Engine<br/>(Operations)"]
    M13 -->|Mensagem proativa| M11

    M11 -->|POST sendText| EVO[/"Evolution API"/]

    M14["M14 Observabilidade"] -.->|"OTLP gRPC traces"| PH[/"Phoenix (Arize)"/]

    style M3 fill:#f9f,stroke:#333
    style M9 fill:#f9f,stroke:#333
    style M14 fill:#eee,stroke:#999,stroke-dasharray: 5 5
```

---

## Fases do Pipeline

### Fase 1: Entrada (Channel Inbound)

<details>
<summary>Recepcao, normalizacao e buffering de mensagens WhatsApp</summary>

```mermaid
sequenceDiagram
    participant Agent as 👤 Agente WhatsApp
    participant EVO as Evolution API
    participant M1 as M1 Recepcao
    participant M2 as M2 Debounce
    participant Redis

    Agent->>EVO: Mensagem WhatsApp
    EVO->>M1: Webhook POST (JSON)
    Note over M1: Validacao X-Webhook-Secret per-tenant<br/>(constant-time compare)
    Note over M1: 13 tipos: text, image, video,<br/>audio (PTT), document, sticker,<br/>contact, location, live_location,<br/>poll, reaction, event, group_metadata

    M1->>M2: InboundMessage normalizado
    M2->>Redis: Lua script atomico (buffer 3s + jitter 0-1s)
    Note over M2,Redis: Agrupa mensagens rapidas<br/>do mesmo usuario.<br/>Jitter aleatorio no TTL<br/>evita avalanche de flushes.<br/>Worker: max_jobs=20,<br/>semaforo LLM=10.
    Redis-->>M2: BufferedBatch pronto (apos 3-4s)
    M2->>M2: Emite BufferedBatch
```

</details>

### Fase 2: Decision Point #1 — MECE Router (Two-Layer)

<details>
<summary>5 acoes de roteamento declarativo + resolucao de agente per-tenant</summary>

O Router MECE opera em **duas camadas** (epic 004):

**Layer 1 — classify()** (funcao pura, sem I/O): deriva `MessageFacts` a partir da mensagem + estado pre-carregado. Classifica em enums tipados: `Channel` (individual/group), `EventKind` (message/group_membership/group_metadata/protocol/unknown), `ContentKind` (text/media/structured/reaction/empty).

**Layer 2 — RoutingEngine.decide()** (declarativo): avalia regras YAML per-tenant por prioridade (menor = maior), first-match wins. 5 tipos de acao: RESPOND, LOG_ONLY, DROP, BYPASS_AI, EVENT_HOOK.

```mermaid
flowchart LR
    M3{"M3 Router MECE"}

    subgraph "Layer 1: classify()"
        MSG["InboundMessage"] --> FACTS["MessageFacts<br/>(channel, event_kind,<br/>content_kind, has_mention,<br/>from_me, is_duplicate,<br/>conversation_in_handoff)"]
    end

    subgraph "Layer 2: RoutingEngine.decide()"
        FACTS --> RULES{"Rules YAML<br/>per-tenant<br/>(priority ASC)"}
        RULES -->|"RESPOND"| P1["Pipeline IA completo<br/>(agent_id resolvido)"]
        RULES -->|"LOG_ONLY"| P3["Log sem resposta<br/>(zero custo)"]
        RULES -->|"DROP"| P5["Descarta<br/>(echo, duplicata)"]
        RULES -->|"BYPASS_AI"| P4["Bypass IA<br/>→ M12 Handoff"]
        RULES -->|"EVENT_HOOK"| P6["Handler especializado<br/>(membership, metadata)"]
        RULES -->|"Sem match"| DEF["Default rule<br/>(per-tenant config)"]
    end

    P1 --> M4["→ M4 Clientes"]

    style M3 fill:#f9f,stroke:#333
    style RULES fill:#ffd,stroke:#333
    style P3 fill:#eee,stroke:#999
    style P5 fill:#eee,stroke:#999
```

**Acoes do router:**
- **RESPOND** → Pipeline IA completo. Agent resolution: `rule.agent` > `tenant.default_agent_id` > `AgentResolutionError`
- **LOG_ONLY** → Log estruturado sem resposta (grupo sem @mention, eventos de protocolo)
- **DROP** → Descarta silenciosamente (echo do bot = previne loop, duplicatas via idempotency)
- **BYPASS_AI** → Bypass completo da IA, direto para handler humano (conversa em handoff ativo)
- **EVENT_HOOK** → Dispatch para handler especializado (membership de grupo, metadata)

**Config YAML per-tenant** (`config/routing/{tenant}.yaml`):
- Cada tenant tem suas proprias regras com prioridades e condicoes
- Regras sao pares `when` (condicoes sobre MessageFacts) + `action` + `agent` (opcional)
- Condicoes avaliadas por igualdade (AND): `from_me`, `is_duplicate`, `channel`, `has_mention`, `event_kind`, `conversation_in_handoff`, `is_membership_event`
- MECE garantido em 4 camadas: (1) tipo (enums), (2) schema (pydantic valida overlaps), (3) runtime (discriminated union), (4) CI (property-based testing)

**MentionMatchers** (deteccao de @mention em grupo):
- 3 estrategias: opaque @lid, phone number, keywords configurados por tenant
- Carregados no startup a partir de `tenant.mention_lid_opaque`, `tenant.mention_phone`, `tenant.mention_keywords`

</details>

### Fase 3: Pipeline Core (IA)

<details>
<summary>Gestao de cliente, contexto, guardrails, classificacao e agente IA</summary>

```mermaid
sequenceDiagram
    participant M4 as M4 Clientes
    participant DB as Supabase ProsaUAI
    participant M5 as M5 Contexto
    participant M6 as M6 Guardrails Entrada
    participant M7 as M7 Classificador
    participant M8 as M8 Agente IA
    participant GPTmini as OpenAI GPT mini
    participant ResenhAI as Supabase ResenhAI
    Note right of GPTmini: Atualmente via pydantic-ai direto.<br/>Bifrost proxy planejado (Fase 3)

    M4->>DB: Busca/cria customer
    DB-->>M4: Perfil + preferencias + historico
    Note over M4: Persiste mensagens recebidas

    M4->>M5: CustomerContext
    Note over M5: Montagem de contexto em 4 camadas:<br/>1. Perfil (customers.preferences, metadata)<br/>2. Estado da conversa (session state machine)<br/>3. Working memory (ultimas 10 msgs + summary)<br/>4. RAG knowledge base (opcional, pgvector)
    Note over M5: Short-term memory: sliding window<br/>(default 10 msgs) + async summarization<br/>apos 20 exchanges.<br/>Cross-conversation: dados estruturados<br/>(preferences, metadata, ultimas N conversas),<br/>NAO vector-based long-term memory.

    M5->>M6: AgentContext (4 camadas)
    Note over M6: Decision Point #2<br/>PII: CPF, telefone, email<br/>Toxicidade: conteudo ofensivo<br/>Injection: prompt injection
    alt BLOCK
        M6-->>M6: Resposta padrao (rejeita)
    else PASS / FLAG
        M6->>M7: Mensagem sanitizada
    end

    M7->>GPTmini: Classifica intent
    GPTmini-->>M7: intent + confidence (0-1)
    Note over M7: Se confidence < 0.7<br/>→ fallback "general"

    M7->>M8: IntentClassification

    alt Agent SEM pipeline steps (default — implementado epic 005)
        M8->>GPTmini: pydantic-ai agent.run() (single LLM call)
        GPTmini-->>M8: Resposta + tool calls
        Note over M8: pydantic-ai v1.70+ com OpenAI SDK direto.<br/>Semaforo concorrencia=10, timeout=60s, 1 retry.<br/>Bifrost proxy planejado para rate limit + spend cap (Fase 3).
    else Agent COM pipeline steps (configuravel — planejado epic 022)
        Note over M8: Pipeline: classifier → clarifier → resolver → specialist<br/>Cada step configurado em agent_pipeline_steps<br/>(model, prompt, tools, conditions por step)
        loop Para cada step em agent_pipeline_steps (step_order ASC)
            M8->>GPTmini: pydantic-ai agent.run() (step N)
            GPTmini-->>M8: StepOutput
            Note over M8: Proximo step recebe output do anterior.<br/>Step com condition so executa se match.
        end
    end

    opt Tool calls (ResenhAI data)
        M8->>ResenhAI: asyncpg read-only
        ResenhAI-->>M8: Dados jogos/stats/ranking
    end

    Note over M8: ~2-5 LLM calls por conversa ativa<br/>Tools: get_ranking, get_stats,<br/>get_player, handoff<br/>Pipeline steps: opt-in per agent (ADR-006)
```

</details>

### Fase 4: Decision Point #3 — Avaliador de Qualidade

<details>
<summary>Aprovacao, retry ou escalacao para humano</summary>

```mermaid
flowchart LR
    M9{"M9 Avaliador<br/>score 0-1"}

    M9 -->|"APPROVE<br/>(score > 0.8)"| M10["M10 Guardrails Saida"]
    M9 -->|"RETRY<br/>(0.5-0.8, max 2x)"| M8["→ M8 Agente IA"]
    M9 -->|"ESCALATE<br/>(score < 0.5)"| M12["→ M12 Handoff"]

    M10 --> OK["Formata para WhatsApp:<br/>markdown, emojis,<br/>limites de caracteres"]

    style M9 fill:#f9f,stroke:#333
```

**Criterios de decisao:**
- **APPROVE** (score > 0.8) → Resposta aprovada, segue para formatacao e entrega
- **RETRY** (score 0.5-0.8) → Volta para M8 Agente IA (maximo 2 tentativas antes de escalar)
- **ESCALATE** (score < 0.5 ou topico critico ou request explicito do usuario) → Handoff para humano

</details>

### Fase 5: Saida (Channel Outbound)

<details>
<summary>Entrega da resposta via Evolution API</summary>

```mermaid
sequenceDiagram
    participant M10 as M10 Guardrails Saida
    participant M11 as M11 Entrega
    participant EVO as Evolution API
    participant Agent as 👤 Agente WhatsApp
    participant DB as Supabase ProsaUAI

    M10->>M11: Payload formatado
    Note over M10,M11: Markdown WhatsApp-compativel,<br/>emojis, limites de caracteres

    M11->>EVO: POST /message/sendText/{instance}
    Note over M11,EVO: Retry 3x com backoff<br/>(1s, 4s, 16s)
    EVO->>Agent: Mensagem entregue

    M11->>DB: Persiste mensagem (role=assistant)
    M11->>M11: Atualiza metricas de conversa

    Note over M11: Ponto de convergencia:<br/>Todos os caminhos terminam aqui<br/>(IA, handoff humano, trigger proativo)
```

</details>

### Fase 6: Handoff Humano

<details>
<summary>Maquina de estados para transferencia IA → humano</summary>

```mermaid
sequenceDiagram
    participant M9 as M9 Avaliador
    participant M12 as M12 Handoff
    participant Admin as prosauai-admin
    participant Operador as 🧑‍💼 Operador
    participant M11 as M11 Entrega

    M9->>M12: ESCALATE (score < 0.5)
    Note over M12: Gera resumo via GPT mini<br/>para contexto do atendente

    M12->>Admin: Notifica atendente (Socket.io)
    Admin->>Operador: Alerta na fila de handoff

    alt Atendente aceita (< 5min)
        Operador->>M12: Aceita handoff
        Note over M12: PENDING → ASSIGNED
        loop Atendimento humano
            Operador->>M12: Responde ao cliente
            M12->>M11: Humano responde via bot
        end
        Note over M12: HUMAN_ACTIVE (30min inatividade)<br/>→ COMPLETED → AGENT_ACTIVE
    else Timeout (> 5min)
        Note over M12: PENDING → AGENT_ACTIVE<br/>(retorna para IA)
    end
```

**State Machine do Handoff:**

```mermaid
stateDiagram-v2
    [*] --> AGENT_ACTIVE
    AGENT_ACTIVE --> PENDING: ESCALATE
    PENDING --> ASSIGNED: Atendente aceita (< 5min)
    PENDING --> AGENT_ACTIVE: Timeout (5min)
    ASSIGNED --> HUMAN_ACTIVE: Atendente responde (< 2min)
    HUMAN_ACTIVE --> COMPLETED: Encerra / Inatividade (30min)
    COMPLETED --> AGENT_ACTIVE: Cooldown (5min)
```

</details>

### Fase 7: Triggers Proativos

<details>
<summary>Mensagens proativas baseadas em eventos — sem LLM</summary>

```mermaid
sequenceDiagram
    participant DB as Supabase ProsaUAI
    participant M13 as M13 Trigger Engine
    participant M11 as M11 Entrega
    participant EVO as Evolution API
    participant Agent as 👤 Agente WhatsApp

    DB->>M13: PG LISTEN/NOTIFY
    Note over DB,M13: Eventos: INSERT em games,<br/>group_members

    M13->>M13: Match contra trigger rules do tenant
    alt Cooldown ativo
        M13-->>M13: Pula (anti-spam)
    else Fora do active_hours
        M13-->>M13: Enfileira para depois
    else Match + cooldown OK
        M13->>M13: Renderiza template Jinja2
        M13->>M11: Mensagem proativa renderizada
        M11->>EVO: POST sendText/{instance}
        EVO->>Agent: Mensagem proativa entregue
    end

    Note over M13: Sem LLM — templates estaticos<br/>Cooldown por cliente (anti-spam)
```

</details>

### Fase 8: Observabilidade (passiva)

<details>
<summary>Tracing distribuido e metricas de qualidade — fire-and-forget</summary>

```mermaid
flowchart LR
    M1["M1 Recepcao"] -.->|Trace recepcao| M14
    M5["M5 Contexto"] -.->|Trace contexto| M14
    M8["M8 Agente IA"] -.->|Trace agente + tokens| M14
    M9["M9 Avaliador"] -.->|Trace eval scores| M14
    M12["M12 Handoff"] -.->|Trace handoff events| M14
    M13["M13 Triggers"] -.->|Trace trigger events| M14

    M14["M14 Observabilidade"] -->|"OTLP gRPC traces<br/>(fire-and-forget)"| PH[/"Phoenix (Arize)"/]

    style M14 fill:#eee,stroke:#999,stroke-dasharray: 5 5
    style PH fill:#eee,stroke:#999,stroke-dasharray: 5 5
```

**Stack de observabilidade:**
- **Phoenix (Arize)**: Self-hosted (:6006 UI + :4317 gRPC). Substitui LangFuse — single container, Postgres backend, sem ClickHouse
- **OpenTelemetry SDK**: Auto-instrumentation (FastAPI, httpx, redis) + spans manuais de dominio (webhook, classify, decide)
- **structlog bridge**: `trace_id`/`span_id` injetados em todo log estruturado via processor `add_otel_context`
- **DeepEval + Promptfoo**: Scores de eval (online + offline) — planejado para epic 005+
- **Fire-and-forget**: falha na observabilidade NAO bloqueia o pipeline (BatchSpanProcessor com force_flush no shutdown)

</details>

---

## Multi-Tenant Lifecycle (Fase 1 → Fase 3)

A partir do epic 003 (Multi-Tenant Foundation), todo fluxo do pipeline acima e **per-tenant por construcao**: cada mensagem entra com `instance_name` no path, e o `TenantResolver` carrega o `Tenant` correto antes de qualquer outra etapa. Esta secao descreve os fluxos especificos de gestao de tenants — quem cria, quem desabilita, quem cobra.

### Fase 1 — Onboarding manual (interno Pace, epic 003)

**Atores:** dev/admin Pace.

```mermaid
sequenceDiagram
    participant Dev as Dev/Admin Pace
    participant Repo as Repo prosauai
    participant Evo as Evolution API
    participant API as ProsauAI API

    Dev->>Repo: Edita config/tenants.yaml<br/>(adiciona novo tenant)
    Dev->>Dev: Gera webhook_secret aleatorio
    Dev->>Repo: Adiciona ${ENV_VAR} no .env
    Dev->>Evo: POST /webhook/set/{instance}<br/>com headers.X-Webhook-Secret
    Dev->>API: Restart container (lifespan recarrega TenantStore)
    Dev->>Dev: Descobre mention_lid_opaque<br/>via capture tool + mention real
    Dev->>Repo: Atualiza tenants.yaml com lid
    Dev->>API: Restart novamente
    Note over Dev,API: Tenant pronto para receber webhooks reais
```

**Caracteristicas:**
- 100% manual
- Aceitavel para 2-5 tenants internos
- Sem rollback automatizado, sem auditoria, sem self-service

### Fase 2 — Onboarding via Admin API (cliente externo, epic 012)

**Atores:** cliente externo + admin Pace.

```mermaid
sequenceDiagram
    participant Client as Cliente Externo
    participant Sales as Vendas Pace
    participant AdminAPI as Admin API
    participant TenantStore as TenantStore (file)
    participant Caddy as Caddy
    participant Client_Evo as Evolution do Cliente
    participant API as ProsauAI API

    Client->>Sales: Quer testar/contratar
    Sales->>AdminAPI: POST /admin/tenants<br/>(master token)
    AdminAPI->>TenantStore: Adiciona tenant + persist em YAML
    AdminAPI->>AdminAPI: Gera webhook_secret aleatorio
    AdminAPI-->>Sales: {tenant_id, webhook_secret, instance_url}
    Sales->>Client: Envia onboarding doc:<br/>"configure webhook na sua Evolution"
    Client->>Client_Evo: POST /webhook/set/{instance}<br/>headers.X-Webhook-Secret
    Client->>Caddy: Mensagem real WhatsApp
    Caddy->>API: Reverse proxy + TLS
    API-->>Client: Echo (tenant validado)
    Note over Client,API: Tenant ativo, rate limit aplicado
```

**Caracteristicas:**
- Vendas/admin Pace cria tenant via API
- Cliente faz a integracao do lado dele (sem acesso ao codigo Pace)
- Caddy + Let's Encrypt fornece TLS publico
- Rate limit per-tenant aplicado (Redis sliding window). Bifrost spend cap planejado (Fase 3)
- Hot reload do TenantStore (sem restart) ou reload via admin API

### Fase 3 — Self-service onboarding + ops (epic 013)

**Atores:** cliente externo (sem intervencao Pace) + ops team.

```mermaid
sequenceDiagram
    participant Client as Cliente Externo
    participant Signup as Signup UI
    participant Stripe as Stripe
    participant AdminAPI as Admin API
    participant Postgres as TenantStore Postgres
    participant Ops as Ops Team
    participant Alerting as Prometheus + Grafana

    Client->>Signup: Cadastro self-service
    Signup->>Stripe: Cria customer + checkout
    Stripe-->>Signup: webhook payment_succeeded
    Signup->>AdminAPI: POST /admin/tenants (Stripe token)
    AdminAPI->>Postgres: INSERT tenant (RLS policies)
    AdminAPI-->>Signup: tenant credentials
    Signup-->>Client: Onboarding wizard:<br/>"configure webhook"
    Client->>Client: Configura webhook
    Note over Client: Operacao normal
    Client->>AdminAPI: Envia 1000 msgs/min (anomaly)
    AdminAPI->>AdminAPI: Circuit breaker abre
    AdminAPI->>Alerting: Metrica spike
    Alerting->>Ops: PagerDuty alert
    Ops->>AdminAPI: PATCH /admin/tenants/{id} disable=true
    Ops->>Client: Email + investigacao
```

**Caracteristicas:**
- Zero intervencao manual no happy path
- Postgres como source of truth (RLS, audit trail, backup)
- Circuit breaker per-tenant impede 1 cliente derrubar outros
- Billing automatizado via Stripe
- Alertas Prometheus quando tenant ultrapassa thresholds
- Migracao YAML → Postgres feita uma unica vez ([ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md))

---

> **Proximo passo:** `/madruga:tech-research prosauai` — pesquisar alternativas tecnologicas para implementar este pipeline.
