# Contract — `ChannelAdapter` Protocol

**File location**: `apps/api/prosauai/channels/base.py` (Protocol) + registry em `apps/api/prosauai/channels/registry.py`.

**Stability**: STABLE após merge do PR-A. Mudanças no Protocol pós-PR-A são breaking e exigem revisão de todos os adapters + PR-C re-run.

---

## 1. Definição

```python
from typing import Protocol, runtime_checkable
from fastapi import Request

from prosauai.channels.canonical import CanonicalInboundMessage


class ChannelAdapterError(Exception):
    """Base para falhas de adapter. Mapeadas para HTTP 400 (payload inválido) ou 401 (auth)."""


class InvalidPayloadError(ChannelAdapterError):
    pass


class AuthError(ChannelAdapterError):
    pass


@runtime_checkable
class ChannelAdapter(Protocol):
    """Tradutor puro entre payload canal-específico e CanonicalInboundMessage.

    Contrato:
      - NÃO acessa PostgreSQL nem Redis.
      - NÃO chama LLM, STT, vision ou qualquer provider externo.
      - NÃO emite OTel spans (pipeline o faz).
      - NÃO muta estado global.
      - É idempotente: mesmo payload → mesma(s) CanonicalInboundMessage(s).
      - Retorna LISTA (um payload pode conter múltiplas mensagens — ex: Meta Cloud
        entrega batch, Evolution entrega uma de cada vez).

    Atributos obrigatórios da instância:
      source: str       — identificador único do canal (ex: "evolution", "meta_cloud")
      source_version: str — versão do adapter (ex: "1.0.0") p/ observability
    """

    source: str
    source_version: str

    async def verify_webhook(self, request: Request) -> None:
        """Valida autenticação do webhook. Raises AuthError se inválido.

        Exemplos de verificação (implementação-específica):
          - EvolutionAdapter: header X-Webhook-Secret === tenants[instance].secret
          - MetaCloudAdapter: header X-Hub-Signature-256 === HMAC-SHA256(body, app_secret)

        MUST ser chamado ANTES de parse_body para evitar parsing de payload malicioso.
        """
        ...

    async def normalize(
        self,
        payload: dict,
        source_instance: str,
    ) -> list[CanonicalInboundMessage]:
        """Converte payload bruto para lista de CanonicalInboundMessage.

        Parameters:
            payload: dict JSON cru do webhook (já parsed por FastAPI).
            source_instance: identificador da instância do canal (ex: "ariel" no path
                             /webhook/evolution/ariel, ou phone_number_id no Meta Cloud).

        Returns:
            Lista (ordem determinística) de CanonicalInboundMessage.
            Vazio se payload é um evento sem mensagem (ex: status update, read receipt).

        Raises:
            InvalidPayloadError: payload não corresponde ao schema esperado.

        Invariantes:
            - Cada msg retornada tem `msg.source == self.source`.
            - Cada msg retornada tem `msg.source_instance == source_instance`.
            - Cada msg retornada tem `msg.idempotency_key == sha256(source + instance + external_id)`.
            - `msg.raw_payload` preserva o JSON original (para audit).
            - Adapter preserva ordem cronológica das mensagens (timestamp asc).
        """
        ...
```

---

## 2. Implementações iniciais

### 2.1 `EvolutionAdapter` (PR-A)

**Arquivo**: `apps/api/prosauai/channels/inbound/evolution/adapter.py`

Comportamento:
- `verify_webhook`: valida `X-Webhook-Secret` contra `tenants.yaml::tenants[source_instance].webhook_secret`. Rejeita com `AuthError` se ausente/inválido.
- `normalize`:
  - Extrai `data.key.id` → `external_message_id`.
  - Mapeia `data.messageType` → `ContentKind`:
    - `"conversation" | "extendedTextMessage"` → `TEXT`
    - `"audioMessage"` → `AUDIO` (preserva `media_is_ptt` em `attrs`)
    - `"imageMessage"` → `IMAGE` (caption em `content_block.caption`)
    - `"documentMessage"` → `DOCUMENT`
    - `"stickerMessage"` → `STICKER`
    - `"locationMessage"` → `LOCATION`
    - `"contactMessage" | "contactsArrayMessage"` → `CONTACT`
    - `"reactionMessage"` → `REACTION`
    - Demais (`"videoMessage"`, `"pollMessage"`, `"protocolMessage"`, ...) → `UNSUPPORTED` com `sub_type` preservado.
  - Computa `idempotency_key = sha256(f"evolution:{source_instance}:{external_id}")`.
  - `conversation_ref.kind` = `"group"` se `data.key.remoteJid.endswith("@g.us")` else `"direct"`.
  - Usa `data.message.base64` se disponível (skip download futuro).

### 2.2 `MetaCloudAdapter` (PR-C)

**Arquivo**: `apps/api/prosauai/channels/inbound/meta_cloud/adapter.py`

Comportamento:
- `verify_webhook`:
  - `GET`: responde `hub.challenge` se `hub.verify_token == config.meta_cloud.verify_token`.
  - `POST`: valida `X-Hub-Signature-256 == 'sha256=' + HMAC(body, app_secret)` em constant-time compare.
- `normalize`:
  - Itera `entry[*].changes[*].value.messages[*]`.
  - Mapeia `message.type`:
    - `"text"` → `TEXT`
    - `"audio"` → `AUDIO` (Meta Cloud não tem PTT flag — deixa `attrs["media_is_ptt"] = None`)
    - `"image"` → `IMAGE`
    - `"document"` → `DOCUMENT`
    - `"sticker"` → `STICKER`
    - `"location"` → `LOCATION`
    - `"contacts"` → `CONTACT`
    - `"reaction"` → `REACTION` (preserva `reaction.emoji` + `reaction.message_id`)
    - `"interactive"` (button_reply, list_reply) → normaliza para `TEXT` com o `title` do botão como `text`.
    - `"video" | "order" | "system" | "unsupported"` → `UNSUPPORTED` com `sub_type`.
  - `idempotency_key = sha256(f"meta_cloud:{source_instance}:{message.id}")`.
  - `source_instance` = `phone_number_id` do Meta Cloud.

---

## 3. Registry

```python
# apps/api/prosauai/channels/registry.py

from prosauai.channels.base import ChannelAdapter

_REGISTRY: dict[str, ChannelAdapter] = {}


def register(adapter: ChannelAdapter) -> None:
    if adapter.source in _REGISTRY:
        raise ValueError(f"Duplicate adapter for source={adapter.source!r}")
    _REGISTRY[adapter.source] = adapter


def get(source: str) -> ChannelAdapter:
    if source not in _REGISTRY:
        raise KeyError(f"No adapter registered for source={source!r}")
    return _REGISTRY[source]


def registered_sources() -> list[str]:
    return sorted(_REGISTRY.keys())


# Bootstrap em main.py:
#   from prosauai.channels.inbound.evolution.adapter import EvolutionAdapter
#   register(EvolutionAdapter(config=...))
```

---

## 4. Tests de contrato (obrigatórios)

Arquivo: `tests/contract/test_channel_adapter_contract.py` (pytest).

```python
import pytest
from prosauai.channels.base import ChannelAdapter
from prosauai.channels.inbound.evolution.adapter import EvolutionAdapter
from prosauai.channels.inbound.meta_cloud.adapter import MetaCloudAdapter


@pytest.mark.parametrize("adapter_cls", [EvolutionAdapter, MetaCloudAdapter])
def test_implements_protocol(adapter_cls):
    adapter = adapter_cls(config=...)
    assert isinstance(adapter, ChannelAdapter)


@pytest.mark.parametrize("fixture,adapter_cls", [
    ("evolution_audio_ptt.input.json", EvolutionAdapter),
    ("evolution_image_with_caption.input.json", EvolutionAdapter),
    ("meta_cloud_audio.input.json", MetaCloudAdapter),
    # ... 17 fixtures total
])
def test_normalize_produces_valid_canonical(fixture, adapter_cls):
    """Toda fixture real produz CanonicalInboundMessage válido (schema Pydantic)."""
    payload = load_fixture(fixture)
    adapter = adapter_cls(config=...)
    msgs = await adapter.normalize(payload, source_instance="test")
    assert len(msgs) >= 1
    for m in msgs:
        # Frozen model validado pelo Pydantic ao construir; este teste garante
        # que o shape do payload real não quebra o schema.
        assert m.source == adapter.source


def test_idempotency_key_is_deterministic():
    """Chamar normalize 2x com mesmo payload produz mesmo idempotency_key."""
    ...


def test_adapter_does_not_touch_db_or_providers(mock_db, mock_openai):
    """Mock DB/providers e garante que adapter.normalize() nunca os chama."""
    ...
```

---

## 5. Garantias NÃO-cobertas pelo Protocol

Itens que são **policy**, não contrato:

- Rate limiting do webhook (responsabilidade do FastAPI middleware).
- Idempotency deduplication (responsabilidade do step `idempotency` em core/idempotency.py).
- Debounce (step `debounce`).
- Tenant resolution (step `auth` lookup via `source_instance`).

Estes passos consumem `CanonicalInboundMessage` mas não fazem parte do adapter.
