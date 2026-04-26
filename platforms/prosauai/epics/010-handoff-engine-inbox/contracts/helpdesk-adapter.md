# Contract — `HelpdeskAdapter` Protocol

**File location**: `apps/api/prosauai/handoff/base.py` (Protocol) + registry em `apps/api/prosauai/handoff/registry.py`.

**Stability**: STABLE apos merge do PR-A. Mudancas no Protocol pos-PR-A sao breaking e exigem revisao dos 2 adapters v1 + qualquer adapter em flight (epic 010.1).

**Pattern reference**: espelha [ADR-031 ChannelAdapter](../../../decisions/ADR-031-multi-source-channel-adapter.md) do epic 009. Mesmo estilo Protocol + registry + error hierarchy.

---

## 1. Definicao

```python
from typing import Protocol, runtime_checkable
from uuid import UUID

from fastapi import Request


class HelpdeskAdapterError(Exception):
    """Base para falhas de adapter."""


class InvalidPayloadError(HelpdeskAdapterError):
    """Webhook payload nao pode ser parseado ou esta em formato desconhecido."""


class AuthError(HelpdeskAdapterError):
    """HMAC invalido ou credenciais ausentes."""


class HelpdeskNotConfigured(HelpdeskAdapterError):
    """Operacao outbound tentada em tenant sem helpdesk (ex: NoneAdapter.send_operator_reply).
    Mapeada para HTTP 409 Conflict no caller admin."""


class HelpdeskAPIError(HelpdeskAdapterError):
    """Falha na chamada outbound ao helpdesk (rede, 5xx, rate limit)."""
    http_status: int | None = None


@runtime_checkable
class HelpdeskAdapter(Protocol):
    """Contrato para integracao bidirecional com helpdesks externos.

    Contrato:
      - NAO acessa PostgreSQL diretamente (chama state.mute/resume via injection).
      - NAO muta estado global.
      - NAO emite OTel spans (pipeline/webhook o fazem).
      - Side effects outbound (Chatwoot API) sao os UNICOS efeitos colaterais permitidos.
      - E idempotente para webhooks inbound: mesmo payload → mesma acao (dedup via Redis SETNX
        no handler, antes de chegar ao adapter).
      - Para NoneAdapter: todos os metodos outbound sao no-ops OU levantam HelpdeskNotConfigured.
    """

    helpdesk_type: str
    """Identificador unico usado no registry. Ex: 'chatwoot', 'none'."""

    async def verify_webhook_signature(self, request: Request, secret: str) -> None:
        """Valida assinatura HMAC do webhook inbound.
        
        Args:
            request: FastAPI Request (body ja consumido pelo handler antes da chamada).
            secret: webhook_secret per-tenant extraido de tenants.yaml.
        
        Raises:
            AuthError: se signature invalida ou ausente.
            NotImplementedError: se adapter nao recebe webhooks (ex: NoneAdapter).
        """

    async def parse_webhook_event(self, payload: dict) -> "HelpdeskWebhookEvent":
        """Parseia payload raw em evento canonico.
        
        Retorna shape:
            HelpdeskWebhookEvent(
                event_type: Literal["assigned", "resolved", "unhandled"],
                external_conversation_id: str,
                assignee_id: str | None,
                metadata: dict,
            )
        
        Payloads desconhecidos retornam event_type='unhandled' (handler responde 200 OK + log).
        
        Raises:
            InvalidPayloadError: se payload estruturalmente invalido (JSON malformado,
                campos obrigatorios ausentes).
        """

    async def on_conversation_assigned(
        self,
        tenant_id: UUID,
        external_conversation_id: str,
        assignee_id: str,
        metadata: dict,
    ) -> None:
        """Callback chamado quando helpdesk sinaliza 'atendente assumiu'.
        
        Implementacao tipica (ChatwootAdapter): no-op — a acao real (mute) e feita pelo
        handler do webhook que chama state.mute_conversation diretamente. Este metodo
        existe para adapters que precisam de logica custom (ex: filtrar assignees internos).
        """

    async def on_conversation_resolved(
        self,
        tenant_id: UUID,
        external_conversation_id: str,
        metadata: dict,
    ) -> None:
        """Callback chamado quando helpdesk sinaliza 'conversa resolvida'.
        
        Simetrico a on_conversation_assigned.
        """

    async def push_private_note(
        self,
        tenant_id: UUID,
        external_conversation_id: str,
        text: str,
    ) -> None:
        """Envia anotacao privada ao helpdesk (visivel apenas ao atendente, nao ao cliente).
        
        Usado para empurrar transcripts (epic 009 content_process) durante handoff —
        atendente precisa ver o que o cliente enviou (audio transcrito, imagem descrita).
        
        Fire-and-forget do caller: falha NUNCA bloqueia pipeline (ADR-028).
        Se adapter nao suporta private note (NoneAdapter) → no-op silencioso.
        
        Raises:
            HelpdeskAPIError: falha de rede ou 5xx; caller circuit breaker trata.
        """

    async def send_operator_reply(
        self,
        tenant_id: UUID,
        external_conversation_id: str,
        text: str,
        sender_name: str,
    ) -> "OperatorReplyResult":
        """Envia mensagem ao cliente via helpdesk (composer admin emergencia).
        
        Args:
            sender_name: exibido ao atendente do tenant. Por padrao admin_user.email (Q4-A).
        
        Retorna:
            OperatorReplyResult(helpdesk_message_id: str, delivered_at: datetime)
        
        Raises:
            HelpdeskNotConfigured: adapter nao suporta operator reply (NoneAdapter).
                Caller (endpoint admin) mapeia para 409 Conflict.
            HelpdeskAPIError: falha de rede ou 5xx.
        """
```

---

## 2. Behaviors — `ChatwootAdapter`

**File**: `apps/api/prosauai/handoff/chatwoot.py`.

**Configuracao**: le `tenant.helpdesk.{base_url, account_id, inbox_id, api_token, webhook_secret}` do TenantConfig.

### 2.1 `verify_webhook_signature`

Chatwoot envia header `X-Webhook-Signature` com HMAC-SHA256 do body raw usando `webhook_secret`.

```python
async def verify_webhook_signature(self, request: Request, secret: str) -> None:
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        raise AuthError("Missing X-Webhook-Signature header")
    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise AuthError("Invalid HMAC signature")
```

### 2.2 `parse_webhook_event`

Processa apenas 2 tipos de evento (spec Clarify Q2):

| Chatwoot event | Condicao | Mapeia para |
|----------------|----------|-------------|
| `conversation_updated` | `changed_attributes.assignee_id.previous_value = null AND current_value != null` | `assigned` |
| `conversation_updated` | `changed_attributes.assignee_id.previous_value != null AND current_value = null` | `resolved` |
| `conversation_status_changed` | `status = 'resolved'` | `resolved` |
| qualquer outro | — | `unhandled` |

```python
async def parse_webhook_event(self, payload: dict) -> HelpdeskWebhookEvent:
    event = payload.get("event")
    conv = payload.get("conversation", {})
    external_id = str(conv.get("id", ""))

    if event == "conversation_updated":
        changed = payload.get("changed_attributes") or []
        assignee_delta = next(
            (c.get("assignee_id") for c in changed if "assignee_id" in c), None
        )
        if assignee_delta is not None:
            prev = assignee_delta.get("previous_value")
            curr = assignee_delta.get("current_value")
            if prev is None and curr is not None:
                return HelpdeskWebhookEvent(
                    event_type="assigned",
                    external_conversation_id=external_id,
                    assignee_id=str(curr),
                    metadata={"chatwoot_event_id": payload.get("id")},
                )
            if prev is not None and curr is None:
                return HelpdeskWebhookEvent(
                    event_type="resolved",
                    external_conversation_id=external_id,
                    assignee_id=None,
                    metadata={"chatwoot_event_id": payload.get("id"), "unassigned_from": prev},
                )
    elif event == "conversation_status_changed":
        if conv.get("status") == "resolved":
            return HelpdeskWebhookEvent(
                event_type="resolved",
                external_conversation_id=external_id,
                assignee_id=None,
                metadata={"chatwoot_event_id": payload.get("id")},
            )
    return HelpdeskWebhookEvent(event_type="unhandled", external_conversation_id=external_id, assignee_id=None, metadata={})
```

### 2.3 `push_private_note`

Chatwoot API v1:
```
POST {base_url}/api/v1/accounts/{account_id}/conversations/{external_conversation_id}/messages
Headers: api_access_token={api_token}
Body: {"content": "<text>", "message_type": "outgoing", "private": true}
```

```python
async def push_private_note(self, tenant_id, external_conversation_id, text):
    cfg = self._cfg_for(tenant_id)
    url = f"{cfg.base_url}/api/v1/accounts/{cfg.account_id}/conversations/{external_conversation_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"content": text, "message_type": "outgoing", "private": True},
                headers={"api_access_token": cfg.api_token.get_secret_value()},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HelpdeskAPIError(f"chatwoot push_private_note failed: {exc}") from exc
```

### 2.4 `send_operator_reply`

```
POST {base_url}/api/v1/accounts/{account_id}/conversations/{external_conversation_id}/messages
Body: {"content": "<text>", "message_type": "outgoing", "sender_type": "AgentBot", "sender_name": "<sender_name>"}
```

> Chatwoot API aceita `sender_name` via custom attribute ou metadata dependendo do deployment. Se Chatwoot Pace nao suportar custom sender_name nativamente, alternativa e prefix no texto: `[Pace ops: admin@pace.ai] <text>`. Decisao final fica na implementacao PR-C apos confirmar Chatwoot version installed.

---

## 3. Behaviors — `NoneAdapter`

**File**: `apps/api/prosauai/handoff/none.py`.

**Configuracao**: `tenant.helpdesk.type == 'none'`. Nao le credenciais (nenhum helpdesk externo).

### 3.1 Comportamentos

| Metodo | Comportamento |
|--------|---------------|
| `verify_webhook_signature` | Raises `NotImplementedError` — NoneAdapter nao expoe webhook |
| `parse_webhook_event` | Raises `NotImplementedError` |
| `on_conversation_assigned` | No-op (nao faz sentido sem helpdesk) |
| `on_conversation_resolved` | No-op |
| `push_private_note` | No-op silencioso (skip + log `noneadapter_push_skip`) |
| `send_operator_reply` | **Raises `HelpdeskNotConfigured`** — caller admin mapeia para 409 |

### 3.2 fromMe detection (hook no webhook Evolution)

NoneAdapter nao recebe webhook proprio — em vez disso, hook no handler Evolution existente chama:

```python
# apps/api/prosauai/api/webhooks/evolution.py (EXTEND, PR-B)
async def handle_evolution_webhook(tenant_id, payload):
    ...
    tenant_cfg = await load_tenant_handoff_config(tenant_id)
    if tenant_cfg.helpdesk.type == "none" and payload.fromMe is True:
        await _none_adapter_fromme_hook(tenant_id, payload, tenant_cfg)
    ...


async def _none_adapter_fromme_hook(tenant_id, payload, tenant_cfg):
    canonical = parse_evolution_canonical(payload)
    if canonical.conversation_ref.kind == "group":
        logger.info("noneadapter_group_skip", message_id=payload.message_id, tenant_id=str(tenant_id))
        return
    is_echo = await lookup_bot_echo(pool, tenant_id, payload.message_id)
    if is_echo:
        logger.info("noneadapter_bot_echo", message_id=payload.message_id, tenant_id=str(tenant_id))
        return
    conversation_id = await resolve_conversation(canonical)
    await state.mute_conversation(MuteRequest(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        reason=MuteReason.FROM_ME_DETECTED,
        source="fromMe_detected",
        auto_resume_at=datetime.now(UTC) + timedelta(minutes=tenant_cfg.handoff.human_pause_minutes),
        metadata={"message_id": payload.message_id, "evolution_timestamp": payload.timestamp},
    ))
```

---

## 4. Registry

```python
# apps/api/prosauai/handoff/registry.py
from typing import Dict, Type
from .base import HelpdeskAdapter


_REGISTRY: Dict[str, HelpdeskAdapter] = {}


def register(adapter: HelpdeskAdapter) -> None:
    _REGISTRY[adapter.helpdesk_type] = adapter


def get_adapter(helpdesk_type: str) -> HelpdeskAdapter:
    if helpdesk_type not in _REGISTRY:
        raise ValueError(f"Unknown helpdesk type: {helpdesk_type}")
    return _REGISTRY[helpdesk_type]


def registered_helpdesks() -> list[str]:
    return sorted(_REGISTRY.keys())


# Bootstrap em main.py:
#   from prosauai.handoff.chatwoot import ChatwootAdapter
#   from prosauai.handoff.none import NoneAdapter
#   register(ChatwootAdapter())
#   register(NoneAdapter())
```

---

## 5. Contract Tests

`tests/contract/test_helpdesk_adapter_contract.py`:

```python
import pytest
from prosauai.handoff.base import HelpdeskAdapter, HelpdeskAdapterError
from prosauai.handoff.chatwoot import ChatwootAdapter
from prosauai.handoff.none import NoneAdapter


@pytest.mark.parametrize("adapter_cls", [ChatwootAdapter, NoneAdapter])
def test_implements_protocol(adapter_cls):
    adapter = adapter_cls()
    assert isinstance(adapter, HelpdeskAdapter)
    assert adapter.helpdesk_type in {"chatwoot", "none"}


@pytest.mark.parametrize("adapter_cls,method_name", [
    (ChatwootAdapter, "verify_webhook_signature"),
    (ChatwootAdapter, "parse_webhook_event"),
    (ChatwootAdapter, "on_conversation_assigned"),
    (ChatwootAdapter, "on_conversation_resolved"),
    (ChatwootAdapter, "push_private_note"),
    (ChatwootAdapter, "send_operator_reply"),
    (NoneAdapter, "push_private_note"),
    (NoneAdapter, "send_operator_reply"),
])
def test_method_exists(adapter_cls, method_name):
    adapter = adapter_cls()
    assert hasattr(adapter, method_name)
    assert callable(getattr(adapter, method_name))


@pytest.mark.asyncio
async def test_none_adapter_send_reply_raises():
    adapter = NoneAdapter()
    with pytest.raises(HelpdeskAdapterError):
        await adapter.send_operator_reply(
            tenant_id=UUID("..."),
            external_conversation_id="ignored",
            text="hi",
            sender_name="ops@pace.ai",
        )
```

Fixtures de webhook Chatwoot reais (task T000 PR-A):

```python
@pytest.fixture
def chatwoot_assigned_payload():
    with open("tests/fixtures/captured/chatwoot_conversation_updated_assignee.input.json") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_chatwoot_parse_assigned(chatwoot_assigned_payload):
    adapter = ChatwootAdapter()
    event = await adapter.parse_webhook_event(chatwoot_assigned_payload)
    assert event.event_type == "assigned"
    assert event.external_conversation_id == "123"
    assert event.assignee_id == "42"
```

---

## 6. Error handling matrix

| Error class | HTTP status mapeado | Retry? |
|-------------|--------------------|--------|
| `AuthError` | 401 Unauthorized | No |
| `InvalidPayloadError` | 200 OK + log (evita retry storm Chatwoot) | No |
| `HelpdeskNotConfigured` | 409 Conflict | No |
| `HelpdeskAPIError` (5xx) | Circuit breaker increment + log | Yes (caller-level, fire-and-forget) |
| `HelpdeskAPIError` (429 rate limit) | Retry com backoff exponencial | Yes |
| `ValueError` (pydantic validation) | 500 Internal Server Error (bug) | No |

---

## 7. Future adapters (epic 010.1+)

Shape para futuros adapters (quando houver cliente demandando):

- **BlipAdapter** — Blip Marketplace bot integration. Webhook padrao Blip: `POST {blip_endpoint}`. Auth via Basic Auth ou OAuth2.
- **ZendeskAdapter** — Zendesk Chat/Messaging. Webhook Zendesk Sunshine Conversations API.
- **FreshdeskAdapter** — Freshchat. Webhook Freshchat native events.
- **FrontAdapter** — Front API webhooks.

Cada adapter novo:
1. Subclass de Protocol `HelpdeskAdapter`.
2. Registro em `main.py` via `register(...)`.
3. Fixtures de webhook reais em `tests/fixtures/captured/`.
4. Novo caso em `tenants.yaml` (`helpdesk.type: blip|zendesk|...`).
5. Nova key em `conversations.external_refs` (`{"blip": {...}}`).
6. Contract tests re-rodam parametrizados no adapter novo.

Nenhuma mudanca em `handoff/state.py`, `handoff/registry.py`, `handoff/events.py`, ou pipeline. Gate de SC-013-like (diff zero em core) aplicavel a cada adapter novo.
