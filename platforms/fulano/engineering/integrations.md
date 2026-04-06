---
title: "Integrations"
sidebar:
  order: 5
---
# Fulano — Integrations

> Pontos de integracao externa: APIs, webhooks, filas, bancos de dados externos.
> Topologia de deploy → ver [blueprint.md](../blueprint/) · Containers → ver [containers.md](../containers/)

---

## Tabela de Integracoes

<!-- AUTO:integrations -->
| # | Sistema | Protocolo | Direcao | Frequencia | Dados | Fallback |
|---|---------|-----------|---------|-----------|-------|----------|
| 1 | **HTTPS webhook** | HTTPS | Agente WhatsApp → fulano-api | per-message | Mensagens WhatsApp (texto, audio, imagem, video, documento) | — |
| 2 | **webhook POST** | HTTPS | Evolution API → fulano-api | — | — | — |
| 3 | **XADD stream:messages** | Redis protocol | fulano-api → Redis | per-message | — | — |
| 4 | **GET/SET cache** | Redis protocol | fulano-api → Redis | per-request | Cache de sessao, debounce state, dedup message_id | — |
| 5 | **XREADGROUP** | Redis Streams | Redis → fulano-worker | per-message | — | — |
| 6 | **POST /v1/chat/completions** | HTTP POST | fulano-worker → Bifrost | per-message | — | retry 3x |
| 7 | **Anthropic API** | Anthropic API | Bifrost → Claude Sonnet | — | — | — |
| 8 | **Anthropic API (fallback)** | Anthropic API | Bifrost → Claude Haiku | per-classification | — | — |
| 9 | **POST sendText/{instance}** | HTTP POST | fulano-worker → Evolution API | per-response | — | 3 retries com backoff exponencial |
| 10 | **asyncpg SQL** | asyncpg | fulano-worker → Supabase Fulano | per-message | Mensagens, conversas, clientes, prompts, evals | — |
| 11 | **asyncpg read-only** | asyncpg | fulano-worker → Supabase ResenhAI | per-tool-call | Dados de jogos, estatisticas, ranking | — |
| 12 | **HTTPS SDK traces** | HTTPS SDK | fulano-worker → LangFuse | per-message | — | Fire-and-forget; buffer local em Redis |
| 13 | **PG LISTEN/NOTIFY** | PostgreSQL | Supabase Fulano → fulano-worker | event-driven | — | Polling fallback a cada 5s se LISTEN desconectar |
| 14 | **Socket.io WebSocket** | Socket.io | fulano-api → fulano-admin | per-event | Novas mensagens, status conversas, alertas handoff | Long-polling automatico (fallback nativo Socket.io) |
| 15 | **HTTPS + JWT** | HTTPS | Admin / Operador → fulano-admin | per-session | Autenticacao Supabase Auth, gerenciamento via dashboard | — |
| 16 | **REST API calls** | HTTPS REST | fulano-admin → fulano-api | — | CRUD prompts, handoff actions, conversation queries | — |
| 17 | **Supabase Auth + queries** | Supabase JS client | fulano-admin → Supabase Fulano | — | JWT tokens, dashboard queries, realtime subscriptions | — |
| 18 | **PUBLISH events** | Redis PubSub | fulano-worker → Redis | — | Notificacoes: nova resposta, handoff status, eval scores | — |
| 19 | **SDK secret read** | HTTPS REST (SDK) | fulano-worker → Infisical | per-request (cached 5min) | Tenant credentials, API keys, webhook secrets | — |
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
