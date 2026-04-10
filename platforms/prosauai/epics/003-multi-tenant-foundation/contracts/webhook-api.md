# Contract: Webhook API — Multi-Tenant

**Date**: 2026-04-10  
**Epic**: `003-multi-tenant-foundation`  
**Type**: HTTP REST Endpoint

---

## Endpoint

```
POST /webhook/whatsapp/{instance_name}
```

## Authentication

| Header | Required | Description |
|--------|----------|-------------|
| `X-Webhook-Secret` | Yes | Per-tenant shared secret, validated via constant-time comparison |

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `instance_name` | string | Evolution API instance name (maps to `Tenant.instance_name`) |

## Request Body

Raw JSON payload from Evolution API v2.3.0. Three event types supported:

### messages.upsert

```json
{
  "event": "messages.upsert",
  "instance": "Ariel",
  "data": {
    "key": {
      "remoteJid": "5511999998888@lid",
      "id": "BAE5F3B4C1E2D",
      "fromMe": false,
      "participant": "5511999998888@s.whatsapp.net",
      "senderPn": "5511999998888"
    },
    "messageType": "imageMessage",
    "message": {
      "imageMessage": {
        "url": "https://...",
        "caption": "Olha essa foto",
        "mimetype": "image/jpeg"
      }
    },
    "messageTimestamp": 1712764800,
    "pushName": "Gabriel",
    "contextInfo": {
      "mentionedJid": ["146102623948863@lid"],
      "quotedMessage": { ... }
    }
  }
}
```

### groups.upsert

```json
{
  "event": "groups.upsert",
  "instance": "Ariel",
  "data": [
    {
      "id": "120363123456789@g.us",
      "subject": "Grupo Teste",
      "size": 5,
      "creation": 1712764800
    }
  ]
}
```

### group-participants.update

```json
{
  "event": "group-participants.update",
  "instance": "Ariel",
  "data": {
    "id": "120363123456789@g.us",
    "action": "add",
    "author": "146102623948863@lid",
    "participants": ["5511999998888@s.whatsapp.net"]
  }
}
```

## Response

### Success — New Message

```json
HTTP 200
{
  "status": "processed"
}
```

### Success — Duplicate

```json
HTTP 200
{
  "status": "duplicate"
}
```

### Error — Unknown Tenant

```json
HTTP 404
{
  "detail": "Unknown instance"
}
```

### Error — Invalid Secret

```json
HTTP 401
{
  "detail": "Invalid webhook secret"
}
```

### Error — Malformed Payload

```json
HTTP 400
{
  "detail": "Invalid payload: <reason>"
}
```

## Idempotency

- Key: `seen:{tenant_id}:{message_id}` in Redis
- TTL: 24h (86400 seconds)
- Duplicate detection via atomic `SET NX EX`
- Fail-open: if Redis unavailable, message is processed (may duplicate)

## Rate Limits

Nenhum rate limit implementado na Fase 1. Planejado para Fase 2 (ADR-015).

## Cross-Tenant Isolation

- Cada tenant tem seu próprio `webhook_secret`
- Chaves Redis são prefixadas por `tenant_id`
- Um webhook para tenant A nunca afeta tenant B
- Lookup por `instance_name` é O(1) e retorna apenas o tenant correspondente

---

handoff:
  from: speckit.plan (contracts)
  to: speckit.plan (quickstart)
  context: "Contrato da webhook API documentado com os 3 event types, responses, e comportamento de idempotência."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Evolution API adicionar novos event types ou mudar formato de resposta esperado."
