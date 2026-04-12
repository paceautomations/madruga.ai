---
title: "Integrations"
sidebar:
  order: 5
---
# ProsaUAI — Integrations

> Pontos de integracao externa: APIs, webhooks, filas, bancos de dados externos.
> Topologia de deploy → ver [blueprint.md](../blueprint/) · Containers → ver [containers.md](../containers/)

---

## Tabela de Integracoes

<!-- AUTO:integrations -->
| # | Sistema | Protocolo | Direcao | Frequencia | Dados | Fallback |
|---|---------|-----------|---------|-----------|-------|----------|
| 1 | **HTTPS webhook** | HTTPS | Agente WhatsApp → prosauai-api | per-message | Mensagens WhatsApp (13 tipos: text, image, video, audio, document, sticker, contact, location, live_location, poll, reaction, event, group_metadata) | — |
| 2 | **webhook POST** | HTTPS | Evolution API → prosauai-api | — | — | — |
| 3 | **XADD stream:messages** | Redis protocol | prosauai-api → Redis | per-message | — | — |
| 4 | **GET/SET cache** | Redis protocol | prosauai-api → Redis | per-request | Cache de sessao, debounce state, dedup message_id | — |
| 5 | **XREADGROUP** | Redis Streams | Redis → prosauai-worker | per-message | — | — |
| 6 | **POST /v1/chat/completions** | HTTP POST | prosauai-worker → Bifrost | per-message | — | retry 3x |
| 7 | **OpenAI API** | OpenAI API | Bifrost → OpenAI GPT mini | per-message | Classificacao + geracao + eval | retry 3x via Bifrost |
| 9 | **POST sendText/{instance}** | HTTP POST | prosauai-worker → Evolution API | per-response | — | 3 retries com backoff exponencial |
| 10 | **asyncpg SQL** | asyncpg | prosauai-worker → Supabase ProsaUAI | per-message | Mensagens, conversas, clientes, prompts, evals | — |
| 11 | **asyncpg read-only** | asyncpg | prosauai-worker → Supabase ResenhAI | per-tool-call | Dados de jogos, estatisticas, ranking | — |
| 12 | **OTLP gRPC traces** | OTLP gRPC :4317 | prosauai-api → Phoenix (Arize) | per-message | OTel spans (webhook, classify, decide) | Fire-and-forget; BatchSpanProcessor com force_flush no shutdown |
| 13 | **PG LISTEN/NOTIFY** | PostgreSQL | Supabase ProsaUAI → prosauai-worker | event-driven | — | Polling fallback a cada 5s se LISTEN desconectar |
| 14 | **Socket.io WebSocket** | Socket.io | prosauai-api → prosauai-admin | per-event | Novas mensagens, status conversas, alertas handoff | Long-polling automatico (fallback nativo Socket.io) |
| 15 | **HTTPS + JWT** | HTTPS | Admin / Operador → prosauai-admin | per-session | Autenticacao Supabase Auth, gerenciamento via dashboard | — |
| 16 | **REST API calls** | HTTPS REST | prosauai-admin → prosauai-api | — | CRUD prompts, handoff actions, conversation queries | — |
| 17 | **Supabase Auth + queries** | Supabase JS client | prosauai-admin → Supabase ProsaUAI | — | JWT tokens, dashboard queries, realtime subscriptions | — |
| 18 | **PUBLISH events** | Redis PubSub | prosauai-worker → Redis | — | Notificacoes: nova resposta, handoff status, eval scores | — |
| 19 | **SDK secret read** | HTTPS REST (SDK) | prosauai-worker → Infisical | per-request (cached 5min) | Tenant credentials, API keys, webhook secrets | — |
<!-- /AUTO:integrations -->

## Implementation Details

### Evolution API — Endpoints

| Endpoint | Metodo | Descricao |
|---|---|---|
| `/message/sendText/{instance}` | POST | Envia mensagem texto |
| `/message/sendMedia/{instance}` | POST | Envia imagem/audio/documento |

**Headers**: `apikey: {evolution_api_key}` | `Content-Type: application/json`

**Payload sendText**:
```json
{
  "number": "5511999999999",
  "text": "Resposta do agente",
  "delay": 1000
}
```

**Payload sendMedia**:
```json
{
  "number": "5511999999999",
  "mediatype": "image",
  "media": "https://...",
  "caption": "Descricao da imagem",
  "fileName": "ranking.png"
}
```

### PostgreSQL LISTEN/NOTIFY — Channels

| Channel | Tabela | Eventos | Uso |
|---|---|---|---|
| `games` | games | INSERT, UPDATE | Triggers proativos (ranking, primeiro jogo) |
| `group_members` | group_members | INSERT, DELETE | Welcome message, membership changes |

**Payload NOTIFY**:
```json
{
  "event": "INSERT",
  "table": "games",
  "record": { "id": "...", "group_id": "...", "player_id": "..." },
  "timestamp": "2026-03-25T14:23:45Z"
}
```

**Fallback**: ARQ cron a cada 30min executa query para capturar eventos perdidos (proteção contra connection drops).

### Redis Streams — Consumer Groups

| Stream | Consumer Group | Consumer | Uso |
|---|---|---|---|
| `stream:messages:{tenant_id}` | `{tenant_id}:chat-processing` | `worker-{instance_id}` | Pipeline de mensagens |

- **Pull-based**: XREADGROUP com BLOCK 5000ms
- **DLQ**: XCLAIM apos 5min sem ACK, max 3 retries
- **Backoff**: 1s → 4s → 16s entre retries
