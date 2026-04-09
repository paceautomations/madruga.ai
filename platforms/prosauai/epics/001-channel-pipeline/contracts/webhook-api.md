# Contract: Webhook API

**Epic**: 001-channel-pipeline  
**Date**: 2026-04-09  
**Type**: HTTP REST API

---

## Endpoints

### POST /webhook/whatsapp/{instance_name}

Recebe webhooks da Evolution API com payload de mensagem.

**Headers obrigatórios**:
| Header | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `x-webhook-signature` | string | Sim | HMAC-SHA256 hex digest do raw body usando webhook_secret |
| `Content-Type` | string | Sim | `application/json` |

**Path Parameters**:
| Param | Tipo | Descrição |
|-------|------|-----------|
| `instance_name` | string | Nome da instância Evolution API |

**Request Body**: Payload JSON da Evolution API (formato variável por versão — tratado pelo adapter).

**Response** (200 OK):
```json
{
  "status": "queued",
  "route": "support",
  "message_id": "3EB0A1B2C3D4E5F6"
}
```

| Campo | Tipo | Valores possíveis |
|-------|------|-------------------|
| `status` | string | `"queued"` (será processado) ou `"ignored"` (descartado) |
| `route` | string | `"support"`, `"group_respond"`, `"group_save"`, `"group_event"`, `"handoff_ativo"`, `"ignore"` |
| `message_id` | string | ID da mensagem da Evolution API |

**Error Responses**:

| Status | Condição | Body |
|--------|----------|------|
| 401 | Assinatura HMAC ausente ou inválida | `{"detail": "Invalid webhook signature"}` |
| 400 | Payload malformado ou impossível de parsear | `{"detail": "Invalid payload: {reason}"}` |
| 500 | Erro interno inesperado | `{"detail": "Internal server error"}` |

**Computação da assinatura**:
```python
import hmac, hashlib
signature = hmac.new(
    webhook_secret.encode("utf-8"),
    raw_request_body,  # bytes, não JSON re-serializado
    hashlib.sha256
).hexdigest()
# Enviar como: x-webhook-signature: {signature}
```

---

### GET /health

Health check da aplicação.

**Response** (200 OK):
```json
{
  "status": "ok",
  "redis": true
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | string | `"ok"` ou `"degraded"` |
| `redis` | boolean | `true` se Redis está acessível, `false` caso contrário |

---

## Contract: Evolution API Client

Interface para envio de mensagens via Evolution API.

### POST /message/sendText/{instance}

**Headers**:
| Header | Valor |
|--------|-------|
| `apikey` | `{evolution_api_key}` |
| `Content-Type` | `application/json` |

**Request Body**:
```json
{
  "number": "5511999998888@s.whatsapp.net",
  "text": "Echo: mensagem recebida"
}
```

**Response** (200/201):
```json
{
  "key": {
    "remoteJid": "5511999998888@s.whatsapp.net",
    "fromMe": true,
    "id": "3EB0A1B2C3D4E5F6"
  },
  "status": "PENDING"
}
```

### POST /message/sendMedia/{instance}

**Headers**: Mesmos de sendText.

**Request Body**:
```json
{
  "number": "5511999998888@s.whatsapp.net",
  "mediatype": "image",
  "media": "https://example.com/image.jpg",
  "caption": "Legenda opcional"
}
```

---

## Contract: MessagingProvider (Abstract)

Interface Python que os providers devem implementar.

```python
from abc import ABC, abstractmethod

class MessagingProvider(ABC):
    @abstractmethod
    async def send_text(self, instance: str, number: str, text: str) -> str:
        """Envia texto. Retorna message_id."""
        ...

    @abstractmethod
    async def send_media(
        self, instance: str, number: str,
        media_type: str, media: str, caption: str | None = None
    ) -> str:
        """Envia mídia. Retorna message_id."""
        ...
```

**Implementações**:
- `EvolutionProvider`: Produção — chama Evolution API via httpx
- Mock em testes: Retorna message_id fixo, registra chamadas

---

handoff:
  from: speckit.plan (Phase 1 - contracts)
  to: speckit.plan (Phase 1 - quickstart)
  context: "Contracts definidos: webhook API (POST /webhook + GET /health), Evolution API client (sendText + sendMedia), MessagingProvider ABC. HMAC validation via raw body bytes."
