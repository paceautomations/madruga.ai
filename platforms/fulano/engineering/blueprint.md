---
title: "Blueprint"
---
# Blueprint de Engenharia

Referencia tecnica consolidada da plataforma **Fulano — Agentes WhatsApp**: concerns transversais, requisitos de qualidade, topologia de deploy, mapa de dados e glossario.

> **Convencao**: esta pagina consolida o **O QUE** e **COMO**. Para o **POR QUE** de cada decisao, consulte os [ADRs](../decisions/).

---

## 1. Concerns Transversais

### 1.1 Autenticacao & Autorizacao

| Aspecto | Mecanismo | ADR |
|---------|-----------|-----|
| Autenticacao tenant admin | Supabase Auth (JWT) — login email/password | — |
| Isolamento de dados | Pool + RLS com `SET LOCAL` por transacao | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Wrapper RLS | `auth.tenant_id()` STABLE SECURITY DEFINER — todas as policies usam | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Indexes obrigatorios | `tenant_id` em toda tabela de dados, sem excecao | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Service role key | Nunca exposta no frontend; apenas server-side | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Tenant context | Sempre `SET LOCAL` (transaction-scoped), nunca `SET` global | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |

### 1.2 Seguranca & Safety

| Camada | Mecanismo | Latencia | ADR |
|--------|-----------|----------|-----|
| Hard limits | 20 tool calls/conversa, 60s timeout, 8K context tokens, 3 max retries | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Layer A — Regex | Blocklist, PII patterns (CPF, telefone, email), length checks | <5ms | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Layer B — ML classifier | DistilBERT injection detection + toxicity | ~50ms | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Layer C — LLM-as-judge | Semantic check em acoes destrutivas (tools high-risk only) | ~200ms | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Loop detection | Similaridade de pattern + semantic entre ultimas N respostas | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Prompt injection defense | Sandwich pattern (system → user → system), input sanitization, output scan | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Tool safety | Pydantic strict schema, whitelist enforcement, server-side tenant_id injection | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Webhook validation | HMAC-SHA256 por tenant na Evolution API | — | [ADR-017](../decisions/ADR-017-secrets-management/) |

### 1.3 Secrets & Encryption

| Aspecto | Mecanismo | ADR |
|---------|-----------|-----|
| Vault | Infisical self-hosted (MIT license) | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Modelo de encryption | Envelope — KEK master + DEK por tenant | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao Evolution API keys | A cada 30 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao LLM keys | A cada 30 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao webhook secrets | A cada 90 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao DEK | A cada 180 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao JWT | A cada 90 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Runtime injection | Via pydantic-ai dependency injection — worker nunca ve raw keys | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Audit trail | Toda operacao (read/rotate/create/delete) com tenant_id, agent_id, IP, timestamp | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Retencao audit | 365 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |

### 1.4 Observabilidade

| Ferramenta | Papel | Integracao |
|------------|-------|------------|
| LangFuse v3 (self-hosted) | Tracing LLM, prompt versioning, sessoes | SDK Python; `trace_id` = `conversation_id` |
| DeepEval | Eval offline: faithfulness, relevance, toxicity, coherence | Batch jobs no worker; resultados em `eval_results` |
| Promptfoo | Regressao de prompts, red-teaming automatizado | CI/CD pipeline; roda contra prompt snapshots |
| `usage_events` | Metricas de consumo, latencia, custo por tenant | Supabase; particao mensal por `event_month` |
| LangFuse traces | Latencia p50/p95/p99 por modulo do pipeline | Fire-and-forget; buffer local em Redis se LangFuse indisponivel |

> Detalhes: [ADR-007](../decisions/ADR-007-langfuse-observability/) | [ADR-008](../decisions/ADR-008-eval-stack/)

### 1.5 Multi-Tenancy

| Mecanismo | Descricao | ADR |
|-----------|-----------|-----|
| Rate limiting | Sliding window Redis por tenant por tier (Free=20, Starter=100, Growth=200, Business=500 RPM) | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| LLM spend caps | Bifrost daily cap por tier; fallback automatico Sonnet → Haiku ao atingir cap | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Queue priority | 3 niveis Redis Streams (high/normal/low) por tier; ratio 1:10 anti-starvation | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Circuit breaker | Por tenant; threshold 50 erros/5min abre por 5min; half-open testing; DLQ para falhas | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Concurrency limits | Free=5, Starter=20, Growth=50, Business=100 requests simultaneos | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Data isolation | RLS policies + `SET LOCAL` em toda query | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Billing metering | `usage_events` com particao mensal; Stripe Metered Billing sync | [ADR-012](../decisions/ADR-012-consumption-billing/) |

### 1.6 Error Handling

| Cenario | Estrategia | Fallback |
|---------|------------|----------|
| LLM timeout/falha | 3 retries com backoff exponencial via Bifrost | Sonnet → Haiku; se ambos falham: mensagem amigavel + handoff |
| Evolution API fora | 3 retries exponential backoff (1s → 4s → 16s) | Mensagem reenfileirada no Redis Stream; alerta admin |
| Redis desconectado | Reconnect automatico com exponential backoff | — |
| PG LISTEN/NOTIFY drop | Polling fallback a cada 5s | ARQ cron a cada 30min catch-up de eventos perdidos |
| Rate limit excedido | HTTP 429 + mensagem amigavel ao usuario WhatsApp | Fila de espera; mensagem processada quando slot disponivel |
| Circuit breaker aberto | Requests do tenant vao para DLQ | Half-open apos 5min; 1 request teste; sucesso = fecha |
| Tool execution falha | Retry 1x; se falha novamente, resposta sem tool + log | Alerta no LangFuse trace |
| Webhook HMAC invalido | Request rejeitado com 401 | Log de tentativa + alerta seguranca |

---

## 2. Qualidade & NFRs

| # | Cenario | Metrica | Target | Mecanismo | Prioridade |
|---|---------|---------|--------|-----------|------------|
| Q1 | Latencia resposta bot | p95 end-to-end (msg recebida → resposta enviada) | <3s | Debounce 3s + LLM streaming + Redis pipeline | Must |
| Q2 | Disponibilidade pipeline | Uptime mensal | 99.5% | Health checks, auto-restart, fallback LLM, DLQ | Must |
| Q3 | Isolamento tenant | Cross-tenant data leak | Zero | RLS + SET LOCAL + integration tests automatizados | Must |
| Q4 | Safety — injection bypass | Taxa de bypass das guardrails | <1% | 3-layer guardrails (regex + ML + LLM-as-judge) | Must |
| Q5 | Throughput Starter | Mensagens/min por tenant | 100 RPM | Redis sliding window rate limiting | Must |
| Q6 | Throughput Business | Mensagens/min por tenant | 500 RPM | Redis sliding window rate limiting | Must |
| Q7 | Custo LLM Starter | Cap diario por tenant | $5/dia | Bifrost spend tracking + Sonnet → Haiku fallback | Should |
| Q8 | Retencao automatica | Purge de dados expirados | <=90d default (config 30-365d) | Cron diario com cascade delete | Must |
| Q9 | SAR response (LGPD) | Tempo de resposta a requisicao do titular | <=15 dias | Endpoint dedicado `/api/v1/sar/{customer_id}` | Must |
| Q10 | Eval quality | Faithfulness score medio | >0.8 | DeepEval batch offline + alerta se cai abaixo | Should |
| Q11 | Guardrail latencia | Overhead de seguranca no pipeline | <260ms total (3 layers) | Layer A <5ms, B ~50ms, C ~200ms (so high-risk) | Should |
| Q12 | Secret rotation | Compliance de rotacao | 100% no prazo | Infisical rotation schedules automatizados | Must |

---

## 3. Deploy & Infraestrutura

### 3.1 Topologia

| Componente | Runtime | Porta/Protocolo | Scaling |
|------------|---------|-----------------|---------|
| fulano-api | Python 3.12, FastAPI + uvicorn | 8040/HTTP | Horizontal (stateless) |
| fulano-worker | Python 3.12, ARQ (async task queue) | — (consumer) | Horizontal (Redis consumer groups) |
| fulano-admin | Next.js 15, shadcn/ui | 3000/HTTP | Horizontal (stateless) |
| Redis 7 | Managed ou self-hosted | 6379/TCP | Single instance + Sentinel (HA) |
| Supabase (PG 15 + pgvector + RLS) | Managed (Supabase Cloud) | 5432/TCP | Vertical (managed) |
| Bifrost | Go binary (LLM proxy) | 8080/HTTP | Horizontal (stateless) |
| LangFuse v3 | Docker Compose (self-hosted) | 3000/HTTP | Single instance |
| Infisical | Docker Compose (self-hosted) | 8080/HTTP | Single instance |
| Evolution API | Cloud mode (managed) | — (webhook) | Managed pelo provider |

#### Deploy Topology (L1)

> Visao geral de todos os componentes, atores e conexoes da plataforma. [→ Ver containers em detalhe](#containers)

```mermaid
graph LR
    %% Actors
    agent(("Agente WhatsApp"))
    admin_user(("Admin / Operador"))

    %% Platform
    subgraph fulano ["Fulano Platform"]
        fulano-api["fulano-api<br/><small>Python 3.12 + FastAPI</small>"]
        fulano-worker["fulano-worker<br/><small>Python 3.12 + ARQ</small>"]
        fulano-admin["fulano-admin<br/><small>Next.js 15 + shadcn/ui</small>"]
    end

    %% Infrastructure
    subgraph infra ["Infrastructure"]
        redis["Redis 7"]
        supabase-fulano[("Supabase Fulano<br/><small>PG 15 + pgvector</small>")]
        bifrost["Bifrost<br/><small>Go LLM Proxy</small>"]
    end

    %% External Services
    subgraph external ["External"]
        evolution-api["Evolution API<br/><small>WhatsApp Gateway</small>"]
        supabase-resenhai[("Supabase ResenhAI<br/><small>PG 15 read-only</small>")]
        claude-sonnet["Claude Sonnet"]
        claude-haiku["Claude Haiku"]
        langfuse["LangFuse v3"]
        infisical["Infisical"]
    end

    %% Actor connections
    agent -- "HTTPS webhook" --> fulano-api
    admin_user -- "HTTPS + JWT" --> fulano-admin
    evolution-api -- "webhook POST<br/>HMAC-SHA256" --> fulano-api

    %% Internal platform flows
    fulano-api -- "XADD Redis Streams" --> redis
    fulano-api -- "GET/SET cache" --> redis
    fulano-api -- "Socket.io WebSocket" --> fulano-admin
    fulano-admin -- "REST API /api/v1/*" --> fulano-api
    fulano-admin -- "Supabase JS client" --> supabase-fulano
    redis -- "XREADGROUP" --> fulano-worker
    fulano-worker -- "PUBLISH events" --> redis

    %% Worker → Infrastructure
    fulano-worker -- "asyncpg SQL" --> supabase-fulano
    supabase-fulano -. "PG LISTEN/NOTIFY" .-> fulano-worker
    fulano-worker -- "POST /v1/chat/completions" --> bifrost

    %% Worker → External
    fulano-worker -- "POST sendText" --> evolution-api
    fulano-worker -- "asyncpg read-only" --> supabase-resenhai
    fulano-worker -. "HTTPS SDK traces" .-> langfuse
    fulano-worker -- "SDK secret read" --> infisical

    %% Bifrost → LLMs
    bifrost -- "Anthropic API" --> claude-sonnet
    bifrost -- "Anthropic API<br/>fallback" --> claude-haiku
```

#### Containers (L2)

> Detalhe dos containers deployaveis, seus componentes internos e protocolos de comunicacao. [→ Ver domain model](../domain-model/) | [→ Ver fluxo de negocio](../business/process/)

```mermaid
graph LR
    %% Actors
    agent(("Agente WhatsApp"))
    admin_user(("Admin / Operador"))

    subgraph fulano ["Fulano Platform"]
        subgraph fulano_api ["fulano-api :8040"]
            api_webhook["Webhook receiver<br/><small>HMAC-SHA256 validation</small>"]
            api_rest["REST endpoints<br/><small>/api/v1/*</small>"]
            api_socketio["Socket.io gateway<br/><small>realtime push</small>"]
        end

        subgraph fulano_worker ["fulano-worker"]
            wk_debounce["Debounce flush<br/><small>Redis Lua 3s window</small>"]
            wk_llm["LLM orchestration<br/><small>via Bifrost proxy</small>"]
            wk_delivery["Delivery + retry<br/><small>3x backoff</small>"]
            wk_eval["Eval batch jobs<br/><small>DeepEval offline</small>"]
            wk_trigger["Trigger evaluator<br/><small>PG LISTEN/NOTIFY</small>"]
        end

        subgraph fulano_admin ["fulano-admin :3000"]
            adm_dash["Dashboard<br/><small>metricas por tenant</small>"]
            adm_conv["Conversation viewer<br/><small>realtime via Socket.io</small>"]
            adm_prompt["Prompt manager<br/><small>versionamento</small>"]
            adm_handoff["Handoff queue<br/><small>fila de atendimento</small>"]
        end
    end

    subgraph storage ["Storage"]
        redis["Redis 7<br/><small>arq: buf: cache: ps:</small>"]
        supabase-fulano[("Supabase Fulano<br/><small>PG 15 + pgvector + RLS</small>")]
    end

    subgraph llm_proxy ["LLM Proxy"]
        bifrost["Bifrost :8050<br/><small>Go — rate limit + fallback</small>"]
    end

    subgraph external ["External Services"]
        evolution-api["Evolution API<br/><small>WhatsApp gateway</small>"]
        supabase-resenhai[("Supabase ResenhAI<br/><small>PG 15 read-only</small>")]
        claude-sonnet["Claude Sonnet<br/><small>primary LLM</small>"]
        claude-haiku["Claude Haiku<br/><small>classification + fallback</small>"]
        langfuse["LangFuse v3<br/><small>tracing + eval</small>"]
        infisical["Infisical<br/><small>secrets vault</small>"]
    end

    %% Actor → Platform
    agent -- "HTTPS" --> api_webhook
    evolution-api -- "webhook POST<br/>HMAC-SHA256" --> api_webhook
    admin_user -- "HTTPS + JWT" --> fulano_admin

    %% API internal
    api_webhook -- "XADD stream:messages" --> redis
    api_webhook -- "SET dedup message_id<br/>TTL 24h" --> redis
    api_rest -- "asyncpg SQL" --> supabase-fulano
    api_socketio -- "WebSocket" --> adm_conv

    %% Admin → API
    fulano_admin -- "REST /api/v1/*" --> api_rest
    fulano_admin -- "Supabase JS client<br/>Auth + queries" --> supabase-fulano

    %% Redis → Worker
    redis -- "XREADGROUP<br/>BLOCK 5000ms" --> wk_debounce

    %% Worker processing
    wk_debounce -- "BufferedBatch" --> wk_llm
    wk_llm -- "POST /v1/chat/completions" --> bifrost
    wk_llm -- "asyncpg SQL" --> supabase-fulano
    wk_llm -- "asyncpg read-only" --> supabase-resenhai
    wk_delivery -- "POST sendText" --> evolution-api
    wk_delivery -- "PUBLISH ps:events" --> redis
    wk_eval -. "HTTPS SDK<br/>fire-and-forget" .-> langfuse
    wk_trigger -- "SDK secret read<br/>cached 5min" --> infisical

    %% PG events → Worker
    supabase-fulano -. "PG LISTEN/NOTIFY<br/>games, group_members" .-> wk_trigger

    %% Bifrost → LLMs
    bifrost -- "Anthropic API" --> claude-sonnet
    bifrost -- "Anthropic API<br/>fallback chain" --> claude-haiku
```

### 3.2 Ambientes

| Ambiente | Finalidade | Infra |
|----------|------------|-------|
| local | Desenvolvimento e testes | Docker Compose completo (todos servicos) |
| staging | QA, red-teaming, testes de integracao | Subset producao; tenants de teste |
| production | Tenants reais | Full stack; monitoring ativo |

### 3.3 CI/CD

> **Nota**: pipeline em definicao. Estrutura planejada abaixo.

| Etapa | Ferramenta | Gate |
|-------|------------|------|
| Lint + type check | ruff, mypy | Blocking |
| Unit tests | pytest | Blocking |
| RLS isolation tests | pytest + Supabase test DB | Blocking |
| Prompt regression | Promptfoo | Warning |
| Security scan | — (a definir) | Blocking |
| Deploy staging | — (a definir) | Automatico |
| Deploy production | — (a definir) | Manual approval |

---

## 4. Mapa de Dados & Privacidade

### 4.1 Fluxo de Dados Pessoais

| Dado | Origem | Storage | Retention | PII? | Base Legal LGPD |
|------|--------|---------|-----------|------|-----------------|
| Mensagens (texto, audio, imagem) | Usuario WhatsApp | Supabase `messages` | 90d (config 30-365d) | Sim | Consentimento no 1o contato |
| Numero WhatsApp | Usuario WhatsApp | Supabase `customers.phone` | Vida do registro | Sim | Execucao de contrato |
| Phone hash | Pipeline | Supabase `customers.phone_hash` (SHA-256) | Vida do registro | Pseudonimizado | Legitimo interesse |
| Sessoes ativas | Pipeline processing | Redis (TTL 24h) | 24h auto-expire | Sim | Legitimo interesse |
| Embeddings knowledge base | Admin upload | Supabase pgvector `knowledge_chunks` | Permanente (ate delete manual) | Possivel | Consentimento do tenant |
| LangFuse traces | Pipeline observability | ClickHouse (LangFuse) | 90d | Sim (referencia) | Legitimo interesse |
| Application logs | Todos os servicos | Log rotation local | 30d | Hash only | Legitimo interesse |
| Audit trail (seguranca) | Auth, admin actions, secret ops | Supabase `audit_log` | 365d | Sim | Obrigacao legal |
| Consent records | 1o contato WhatsApp | Supabase `user_consents` | Permanente | Sim | Obrigacao legal |

> PII em logs e traces: sempre SHA-256 hash do phone. Nunca plain text fora do BD principal. ([ADR-018](../decisions/ADR-018-data-retention-lgpd/))

### 4.2 Direitos do Titular (LGPD)

| Direito | Mecanismo | SLA | ADR |
|---------|-----------|-----|-----|
| Acesso (SAR) | Endpoint `/api/v1/sar/{customer_id}` — retorna metadata, conversas, knowledge_mentions, consents, metricas | 15 dias | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Exclusao | Cascade delete por `phone_hash`: mensagens → embeddings → traces (redact, nao delete) → cache Redis | 15 dias | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Consentimento | Mensagem de disclosure no 1o contato WhatsApp; opt-in explicito; re-consent se politica muda | Imediato | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Portabilidade | JSON export via mesmo SAR endpoint | 15 dias | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Revogacao | Sem consentimento = apenas respostas genericas, sem armazenamento | Imediato | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |

### 4.3 Compliance Checklist

| Item | Status | Nota |
|------|--------|------|
| Consent flow no 1o contato | Desenhado | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Retention cron automatico (diario) | Desenhado | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) — cascade delete |
| SAR endpoint | Desenhado | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) — 15 dias SLA |
| PII detection pre-LLM | Desenhado | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) — Layer A regex |
| Encryption at rest | Supabase managed | Transparente via provider |
| Encryption in transit (TLS) | Todas conexoes HTTPS/TLS | Inclui Redis TLS em producao |
| HMAC webhook validation | Desenhado | [ADR-017](../decisions/ADR-017-secrets-management/) — SHA-256 por tenant |
| Envelope encryption secrets | Desenhado | [ADR-017](../decisions/ADR-017-secrets-management/) — KEK + DEK |
| Proibicao fine-tuning sem consent | Politica | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Proibicao cross-tenant embedding | Politica | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |

---

## 5. Glossario

| Termo | Definicao | Dominio |
|-------|-----------|---------|
| **Tenant** | Empresa/negocio que usa Fulano. Isolamento completo de dados, config e billing | Plataforma |
| **Pipeline** | Sequencia de 14 modulos (M1-M14) que processa cada mensagem recebida | Core |
| **Handoff** | Transferencia de conversa do agente IA para atendente humano, com maquina de estados | Atendimento |
| **Guardrails** | Filtros de seguranca pre/pos-LLM que bloqueiam conteudo indesejado (3 layers) | Seguranca |
| **Debounce** | Agrupamento de mensagens rapidas (janela 3s via Redis Lua) numa unica request | Core |
| **Cooldown** | Tempo minimo entre mensagens proativas para o mesmo cliente (evitar spam) | Triggers |
| **Bounded Context** | Area logica do sistema com fronteiras definidas (DDD). 7 contextos no Fulano | Arquitetura |
| **ACL** | Anti-Corruption Layer — isola integracao com sistemas externos, traduzindo formatos | Arquitetura |
| **Bifrost** | Proxy LLM em Go — centraliza rate limiting, fallback Sonnet/Haiku, cost tracking | Infra |
| **Evolution API** | Gateway WhatsApp self-hosted (cloud mode) — conecta Fulano ao WhatsApp sem BSP | Integracao |
| **LangFuse** | Observabilidade LLM: tracing, eval, prompt versioning. Self-hosted v3 | Observabilidade |
| **CSAT** | Customer Satisfaction Score (1-5) coletado apos atendimento humano | Metricas |
| **Channel Adapter** | Interface padrao que abstrai canal de mensageria. Novo canal = novo adapter, zero mudanca no core | Arquitetura |
| **Tool Registry** | Catalogo central de tools com metadata (nome, params, categoria). Alimenta admin e valida configs | Arquitetura |
| **Infisical** | Secret manager open-source (MIT). Envelope encryption (KEK + DEK por tenant) | Seguranca |
| **DLQ** | Dead Letter Queue — fila de mensagens que falharam apos max retries, para reprocessamento manual | Infra |
| **Circuit Breaker** | Padrao que isola tenant com alta taxa de erro, evitando cascata para outros tenants | Resiliencia |
| **Sandwich Pattern** | Defesa contra prompt injection: system prompt antes e depois do input do usuario | Seguranca |
| **SAR** | Subject Access Request — requisicao do titular de dados (LGPD Art. 18) | Compliance |
| **RPM** | Requests Per Minute — metrica primaria de rate limiting por tenant | Metricas |
