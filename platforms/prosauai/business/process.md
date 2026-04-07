---
title: "Business Process"
description: 'Fluxo de negocio da plataforma ProsaUAI: mensagem individual (1:1), grupo (@mention), handoff humano, triggers proativos.'
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

### Fase 2: Decision Point #1 — Smart Router

<details>
<summary>5 caminhos possiveis de roteamento</summary>

```mermaid
flowchart LR
    M3{"M3 Smart Router"}

    M3 -->|"1. SUPPORT"| P1["Pipeline completo (1:1)"]
    M3 -->|"2. GROUP_RESPOND"| P2["Pipeline com contexto de grupo"]
    M3 -->|"3. GROUP_SAVE_ONLY"| P3["Salva sem LLM<br/>(zero custo)"]
    M3 -->|"4. GROUP_EVENT"| P6["Evento de membership<br/>(welcome/saida)"]
    M3 -->|"5. HANDOFF_ATIVO"| P4["Bypass IA<br/>→ M12 Handoff"]
    M3 -->|"6. IGNORE"| P5["Duplicata ou<br/>evento interno"]

    P1 --> M4["→ M4 Clientes"]
    P2 --> M4

    style M3 fill:#f9f,stroke:#333
    style P3 fill:#eee,stroke:#999
    style P6 fill:#eee,stroke:#999
    style P5 fill:#eee,stroke:#999
```

**Caminhos:**
- **SUPPORT** → Pipeline completo para mensagem individual (1:1)
- **GROUP_RESPOND** → Mesmo pipeline, com contexto de grupo (@mention)
- **GROUP_SAVE_ONLY** → Salva mensagem no historico sem acionar LLM (zero custo)
- **GROUP_EVENT** → Evento de membership (welcome, saida de membro) — aciona trigger template sem LLM
- **HANDOFF_ATIVO** → Conversa ja escalada — bypass completo da IA, direto para atendente humano
- **IGNORE** → Duplicata detectada ou evento interno — descarta

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
    Note over M5: Montagem de contexto em 3 camadas:<br/>1. Perfil do cliente (longo prazo)<br/>2. Estado da conversa (sessao)<br/>3. Working memory (ultimas interacoes)<br/>+ RAG results quando disponivel

    M5->>M6: AgentContext (3 camadas)
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
    M8->>Bifrost: POST /v1/chat/completions
    Bifrost->>GPTmini: OpenAI API
    GPTmini-->>Bifrost: Resposta + tool calls
    Bifrost-->>M8: AgentResponse

    opt Tool calls (ResenhAI data)
        M8->>ResenhAI: asyncpg read-only
        ResenhAI-->>M8: Dados jogos/stats/ranking
    end

    Note over M8: ~2-5 LLM calls por conversa ativa<br/>Tools: get_ranking, get_stats,<br/>get_player, handoff
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
