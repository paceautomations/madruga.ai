---
title: "Business Process"
description: 'Fluxo de negocio da plataforma ProsaUAI: mensagem individual (1:1), grupo (@mention), handoff humano, triggers proativos, multi-tenant.'
updated: 2026-04-10
sidebar:
  order: 3
---

# Business Process — Pipeline Completo

Todos os caminhos da plataforma ProsaUAI: mensagem individual (1:1), grupo (@mention), handoff humano, triggers proativos. **14 modulos, 6 paths de roteamento, 3 decision points.**

> [→ Ver arquitetura de containers](../engineering/blueprint/#containers) | [→ Ver domain model](../engineering/domain-model/)

---

## Visao Geral do Pipeline

```mermaid
flowchart TD
    A[/"👤 Agente WhatsApp"/] -->|Mensagem| M1["M1 Recepcao<br/>(Channel)"]
    M1 -->|InboundMessage| M2["M2 Debounce<br/>(Channel)"]
    M2 -->|BufferedBatch| M3{"M3 Smart Router<br/>Decision Point #1"}

    M3 -->|SUPPORT / GROUP| M4["M4 Clientes<br/>(Conversation)"]
    M3 -->|HANDOFF_ATIVO| M12["M12 Handoff<br/>(Operations)"]

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

    M14["M14 Observabilidade"] -.->|Traces| LF[/"LangFuse"/]

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
    Note over M1: Validacao HMAC-SHA256 obrigatoria
    Note over M1: Tipos: texto, audio, imagem,<br/>video, documento, sticker,<br/>contato, localizacao

    M1->>M2: InboundMessage normalizado
    M2->>Redis: Lua script atomico (buffer 3s + jitter 0-1s)
    Note over M2,Redis: Agrupa mensagens rapidas<br/>do mesmo usuario.<br/>Jitter aleatorio no TTL<br/>evita avalanche de flushes.<br/>Worker: max_jobs=20,<br/>semaforo LLM=10.
    Redis-->>M2: BufferedBatch pronto (apos 3-4s)
    M2->>M2: Emite BufferedBatch
```

</details>

### Fase 2: Decision Point #1 — Smart Router (Two-Phase)

<details>
<summary>6 caminhos de roteamento + resolucao de agente configuravel por numero</summary>

O Smart Router opera em **duas fases**:

**Fase A — Route Classification** (o que acontece): classifica a mensagem em 1 dos 6 paths com base em atributos da mensagem (is_group, @mention, from_me, handoff state). Os 6 paths sao fixos e iguais para todos os tenants.

**Fase B — Agent Resolution** (quem atende): para routes que precisam de agente (SUPPORT, GROUP_RESPOND), avalia as `routing_rules` configuradas para o tenant + phone_number. Avaliacao por priority ASC, first-match wins. Sem regra = `tenants.settings.default_agent_id`.

```mermaid
flowchart LR
    M3{"M3 Smart Router"}

    subgraph "Fase A: Route Classification"
        M3 -->|"1. SUPPORT"| P1["Pipeline completo (1:1)"]
        M3 -->|"2. GROUP_RESPOND"| P2["Pipeline com contexto de grupo"]
        M3 -->|"3. GROUP_SAVE_ONLY"| P3["Salva sem LLM<br/>(zero custo)"]
        M3 -->|"4. GROUP_EVENT"| P6["Evento de membership<br/>(welcome/saida)"]
        M3 -->|"5. HANDOFF_ATIVO"| P4["Bypass IA<br/>→ M12 Handoff"]
        M3 -->|"6. IGNORE"| P5["Duplicata ou<br/>evento interno"]
    end

    subgraph "Fase B: Agent Resolution"
        P1 --> RR{"routing_rules<br/>(priority ASC)"}
        P2 --> RR
        RR -->|"Match"| AG["agent_id resolvido"]
        RR -->|"No match"| DF["default_agent_id<br/>(tenant settings)"]
        AG --> M4["→ M4 Clientes"]
        DF --> M4
    end

    style M3 fill:#f9f,stroke:#333
    style RR fill:#ffd,stroke:#333
    style P3 fill:#eee,stroke:#999
    style P6 fill:#eee,stroke:#999
    style P5 fill:#eee,stroke:#999
```

**Caminhos (Fase A):**
- **SUPPORT** → Pipeline completo para mensagem individual (1:1)
- **GROUP_RESPOND** → Mesmo pipeline, com contexto de grupo (@mention)
- **GROUP_SAVE_ONLY** → Salva mensagem no historico sem acionar LLM (zero custo)
- **GROUP_EVENT** → Evento de membership (welcome, saida de membro) — aciona trigger template sem LLM
- **HANDOFF_ATIVO** → Conversa ja escalada — bypass completo da IA, direto para atendente humano
- **IGNORE** → Duplicata detectada ou evento interno — descarta

**Resolucao de agente (Fase B):**
- Cada numero WhatsApp do tenant pode ter `routing_rules` diferentes (ex: individual → vendas, grupo → suporte)
- Regras armazenadas em `routing_rules` table com `match_conditions` JSONB (ex: `{"channel_type": "individual"}`)
- Avaliacao por priority (menor = maior prioridade), first-match wins
- Sem regras configuradas → usa `tenants.settings.default_agent_id`
- Config via admin panel, sem deploy — ver [ADR-006](../decisions/ADR-006-agent-as-data/) e [domain-model](../engineering/domain-model/)

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
    participant Bifrost
    participant GPTmini as OpenAI GPT mini
    participant ResenhAI as Supabase ResenhAI

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

    alt Agent SEM pipeline steps (default)
        M8->>Bifrost: POST /v1/chat/completions (single LLM call)
        Bifrost->>GPTmini: OpenAI API
        GPTmini-->>Bifrost: Resposta + tool calls
        Bifrost-->>M8: AgentResponse
    else Agent COM pipeline steps (configuravel)
        Note over M8: Pipeline: classifier → clarifier → resolver → specialist<br/>Cada step configurado em agent_pipeline_steps<br/>(model, prompt, tools, conditions por step)
        loop Para cada step em agent_pipeline_steps (step_order ASC)
            M8->>Bifrost: POST /v1/chat/completions (step N)
            Bifrost-->>M8: StepOutput
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

    M14["M14 Observabilidade"] -->|"Traces + scores<br/>(fire-and-forget)"| LF[/"LangFuse"/]

    style M14 fill:#eee,stroke:#999,stroke-dasharray: 5 5
    style LF fill:#eee,stroke:#999,stroke-dasharray: 5 5
```

**Stack de observabilidade:**
- **LangFuse**: Traces com spans por modulo (M1-M13)
- **DeepEval + Promptfoo**: Scores de eval (online + offline)
- **trace_id** = conversation_id (correlacao end-to-end)
- **Fire-and-forget**: falha na observabilidade NAO bloqueia o pipeline
- **Prompt versions**: source of truth no LangFuse

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
- Rate limit per-tenant aplicado (Bifrost spend cap + Redis sliding window)
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
