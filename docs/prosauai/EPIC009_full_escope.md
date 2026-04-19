---
epic: 009-channel-ingestion-and-content-processing
title: "Channel Ingestion Normalization + Content Processing"
appetite: 5 semanas
status: drafted
created: 2026-04-19
depends_on: [008-admin-evolution]
deliverable_branch: epic/prosauai/009-channel-ingestion-and-content-processing
---

# Epic 009 — Channel Ingestion Normalization + Content Processing

> **Executar na ordem**: PR-A (Canonical + Adapter) → PR-B (Content Processors) → PR-C (Meta Cloud Adapter de validação). Cada PR é mergeável isoladamente em `develop`; reversível via feature flag por tenant.

---

## 0. Sumário executivo

**O quê**: Refatorar a camada de entrada em 2 módulos formais (`Channel Ingestion` + `Content Processing`) com pattern adapter/strategy, habilitar tratamento real de áudio e imagem via OpenAI (Whisper + GPT-4o vision), e validar a abstração com um segundo adapter (Meta Cloud API).

**Por quê**: Hoje mensagens não-texto (áudio, sticker, imagem sem caption) são **descartadas silenciosamente** em [apps/api/prosauai/api/webhooks.py:258](apps/api/prosauai/api/webhooks.py#L258) (cláusula `if message.text:`). O parser extrai metadata mas o debounce e o `ConversationRequest` carregam apenas `text`. Além disso, toda a lógica de entrada é Evolution-específica — impossível plugar Meta Cloud / Instagram / Telegram sem reescrever webhooks + formatter + debounce + pipeline.

**Como, em uma linha**: introduzir `CanonicalInboundMessage` como contrato source-agnostic preenchido por adapters plugáveis, e adicionar um step `content_process` no pipeline que delega a processors especializados por `ContentBlock.kind`.

**Entregáveis visíveis ao usuário final**:
- Áudio PTT do WhatsApp é transcrito via Whisper e respondido em contexto (sem mais silêncio)
- Imagem com ou sem caption é descrita via GPT-4o vision e respondida em contexto
- Documentos PDF/docx têm texto extraído e respondido
- Trace Explorer mostra transcrição/descrição de cada mídia como step próprio com custo + latência

**Entregáveis visíveis ao operador (admin)**:
- Novo step "content_process" no waterfall com input (URL mídia, mime, duration) e output (transcript/description + cost_usd + cache_hit)
- Tabela nova `media_analyses` auditável em retenção de 14 dias
- Deep-link da mídia original (URL WhatsApp enquanto válida)

---

## 1. Decisões travadas (usuário confirmou 2026-04-19)

| # | Decisão | Valor | Impacto |
|---|---------|-------|---------|
| D1 | Canonical rename | `InboundMessage` → `CanonicalInboundMessage` + split `media_*` em `ContentBlock` discriminada | Quebra tipos em ~6 arquivos (formatter, webhooks, router, facts, debounce, pipeline). Vale pela clareza |
| D2 | UX de transcrição | **Inline** — usuário espera +2-5s (áudio) ou +3-6s (imagem). Sem follow-up async | Simplifica arquitetura; evita dobra de mensagens de saída |
| D3 | Provider STT | **OpenAI `whisper-1`** como default | Preço estável $0.006/min, qualidade PT-BR ok. Upgrade path a `gpt-4o-mini-transcribe` documentado (metade do custo) mas fora de escopo v1 |
| D4 | Retenção mídia | Transcript salvo conforme retenção messages (90d). URL WhatsApp salva 14 dias (alinha com expiração natural do signed URL do Meta) | Cache dedup por sha256 do conteúdo; economiza custos em retries |
| D5 | Volume esperado | **Alto** (não quantificado hoje, planejar para 10k+ mídias/mês por tenant) | Força: cache obrigatório, budget per-tenant, circuit breaker, retry com jitter |
| D6 | Scope-out | Instagram, Telegram, video frames, PDF tabular, streaming transcription → epics 010-012 | Evita escopo creep |

Decisões derivadas (minhas, validáveis no review):

| # | Decisão | Valor | Justificativa |
|---|---------|-------|---------------|
| D7 | Provider vision | **OpenAI `gpt-4o-mini`** via Responses API | 16× mais barato que `gpt-4o`, cobre 99% de descrição simples conforme pedido no n8n ("Descreva de forma simples, objetiva e direta") |
| D8 | Download binário | Baixar com `httpx` + stream para memória (áudio WhatsApp tipicamente ≤1MB) | Whisper max 25MB; rejeitar antes de gastar banda se `content-length > 25MB` |
| D9 | Base64 inline | Quando Evolution envia `data.message.base64`, pular download | Reduz latência ~100-300ms; disponível em alguns builds da Evolution |
| D10 | Idempotency key canônico | `sha256(source + source_instance + external_message_id)` | Evita colisão cross-source (Meta e Evolution podem ter IDs iguais) |
| D11 | Feature flag granular | `content_processing.audio_enabled`, `content_processing.image_enabled` por tenant | Rollback sem deploy; permite ligar Ariel primeiro, ResenhAI depois |
| D12 | Pricing register | Estender `pricing.py` (ADR-029) com linhas `whisper-1` e `gpt-4o-mini-vision` | Admin Performance tab mostra custo por processor |

---

## 2. Problem deep-dive

### 2.1 Mídia descartada silenciosamente — código-fonte do bug

Atual em [apps/api/prosauai/api/webhooks.py:252](apps/api/prosauai/api/webhooks.py#L252):

```python
case RespondDecision(agent_id=agent_id, matched_rule=matched_rule):
    if message.text:          # ← áudio sem caption: text is None → Falsy
        debounce = getattr(request.app.state, "debounce_manager", None)
        if debounce is not None:
            await debounce.append(
                tenant.slug, sender_key,
                group_id=message.group_id,
                text=message.text,    # ← só text entra no buffer
                agent_id=str(agent_id) if agent_id else None,
                recipient_key=message.recipient_key,
            )
```

E em [apps/api/prosauai/core/debounce.py:302](apps/api/prosauai/core/debounce.py#L302):

```python
payload: dict[str, object] = {
    "text": text,
    "trace_context": carrier,
}
if agent_id is not None:
    payload["agent_id"] = agent_id
if recipient_key is not None:
    payload["recipient_key"] = recipient_key
# ← Nenhum campo de mídia. Metadata extraída pelo parser é jogada fora.
```

E em [apps/api/prosauai/conversation/models.py:175](apps/api/prosauai/conversation/models.py#L175):

```python
class ConversationRequest(BaseModel):
    tenant_id: str
    sender_key: str
    group_id: str | None = None
    text: str                 # ← string obrigatória; sem campo media
    agent_id: str | None = None
    trace_context: dict[str, Any] = Field(default_factory=dict)
```

Resultado: áudio/sticker/imagem sem caption → webhook retorna 200 OK → nenhum trace é persistido → operador vê "mensagem recebida" no Chatwoot mas sem resposta. Cliente silenciado.

### 2.2 Acoplamento Evolution

`parse_evolution_message` em [apps/api/prosauai/core/formatter.py](apps/api/prosauai/core/formatter.py) retorna um `InboundMessage` cuja estrutura carrega strings Evolution-específicas:

- `messageType: "audioMessage" | "imageMessage" | "conversation" | ...` — nomes Evolution
- `media_is_ptt: bool` — push-to-talk é conceito WhatsApp
- `media_duration_seconds` — campo achatado em vez de union type

Qualquer adapter novo (Meta Cloud, Instagram) teria que emitir os mesmos strings Evolution para funcionar, o que é acoplamento ruim. Meta Cloud usa `type: "audio" | "image" | "text"` (diferente). Instagram usa `attachments[].type: "image" | "video" | "audio" | "file"`.

### 2.3 Ingestão monolítica no handler HTTP

[apps/api/prosauai/api/webhooks.py:73-343](apps/api/prosauai/api/webhooks.py#L73) — função `webhook_whatsapp` faz 7 responsabilidades num só fluxo: autenticação, parse JSON, normalização, idempotência, handoff check, roteamento MECE, persistência da decisão, dispatch. Adicionar um segundo canal significa duplicar quase tudo ou enfiar branches.

### 2.4 Nenhuma análise de mídia ocorre

Grep exaustivo em `apps/api/` e `platforms/` confirma: zero código para Whisper, OCR, vision, ou qualquer provedor de STT. O único ponto onde `media_type` é consultado é em [core/router/facts.py:148](apps/api/prosauai/core/router/facts.py#L148) para derivar `ContentKind.MEDIA` (para o roteador), mas não para processar.

---

## 3. Architecture overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  L1 — CHANNEL INGESTION (Adapter Pattern)                          │
│                                                                     │
│   POST /webhook/evolution/{instance}   ──┐                         │
│   POST /webhook/meta/{phone_number_id}  ──┼─► ChannelAdapter       │
│   POST /webhook/instagram/{ig_id}       ──┼────verify_webhook()    │
│   POST /webhook/telegram/{bot}           ──┘    normalize()        │
│                                                     │               │
│                                          CanonicalInboundMessage    │
│                                                     │               │
│                             ┌───────────────────────┘               │
│                             ▼                                       │
│                     Idempotency (Redis SETNX)                       │
│                             │                                       │
│                             ▼                                       │
│                        Router MECE (unchanged)                      │
│                             │                                       │
│                             ▼                                       │
│                     Debounce (payload = Canonical)                  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ flush
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PIPELINE (14 steps agora em vez de 12)                             │
│                                                                     │
│   1. webhook_received   (registra Canonical completo)              │
│   2. route              (reuso)                                    │
│   3. customer_lookup    (reuso)                                    │
│   4. conversation_get   (reuso)                                    │
│   5. save_inbound       (reuso — mas salva Canonical + raw)        │
│  ➤6. content_process    ◄────── NOVO STEP                          │
│   7. build_context      (recebe text_representation)               │
│   8. input_guard                                                    │
│   9. classify_intent                                                │
│  10. generate_response                                              │
│  11. evaluate_response                                              │
│  12. output_guard                                                   │
│  13. save_outbound                                                  │
│  14. deliver                                                        │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  L2 — CONTENT PROCESSING (Strategy Pattern)                        │
│                                                                     │
│   ContentBlock.kind ─► registry ─► Processor.process(block, ctx)    │
│                                                                     │
│     "text"         → TextProcessor          (identity)              │
│     "audio"        → AudioProcessor         (OpenAI Whisper)        │
│     "image"        → ImageProcessor         (GPT-4o-mini vision)    │
│     "document"     → DocumentProcessor      (PDF/docx text extract) │
│     "location"     → LocationProcessor      (format lat/lng)        │
│     "contact"      → ContactProcessor       (format vcard resume)   │
│     "reaction"     → ReactionProcessor      (fmt "👍 a msg X")      │
│     "sticker"      → UnsupportedProcessor   (polite fallback)       │
│     "video"        → UnsupportedProcessor   (epic 011)              │
│                                                                     │
│   Saída: ProcessedContent com .text_representation (string única   │
│   pronta para o LLM agent ver) + cost_usd + cache_hit + duration   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Canonical schema

### 4.1 `CanonicalInboundMessage`

```python
# apps/api/prosauai/messaging/canonical.py (novo)

from __future__ import annotations
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field


Source = Literal["whatsapp_evolution", "whatsapp_meta", "instagram", "telegram"]

ContentKind = Literal[
    "text", "audio", "image", "video", "document",
    "location", "contact", "reaction", "sticker", "system",
]


class SenderIdentity(BaseModel):
    """Stable identity of the message sender across channels.

    `external_id` is the most stable identifier available in the source
    system — WhatsApp LID, Instagram IGSID, Telegram user_id. `phone` is
    populated only when the source exposes it (always for WhatsApp,
    optional for others).
    """

    external_id: str
    phone: str | None = None
    display_name: str | None = None
    source: Source


class ConversationContext(BaseModel):
    """Where the message lives in the source system.

    `external_thread_id` is the source-native conversation/chat ID
    (remoteJid for WhatsApp, conversation_id for Meta, thread_id for
    Instagram). Pipeline resolves it to an internal `conversations.id`
    via `get_or_create_conversation`.
    """

    channel: Literal["individual", "group"]
    external_thread_id: str
    group_id: str | None = None
    reply_to_external_id: str | None = None
    mentioned_external_ids: list[str] = Field(default_factory=list)


# -- Content blocks (discriminated union) ----------------------------------

class TextContent(BaseModel):
    kind: Literal["text"] = "text"
    body: str


class MediaContent(BaseModel):
    """Audio, image, video, document — anything with a downloadable URL."""

    kind: Literal["audio", "image", "video", "document"]
    url: str | None = None              # signed URL; expira em ~14d no WhatsApp
    mime_type: str | None = None
    size_bytes: int | None = None
    duration_seconds: int | None = None  # audio/video
    is_ptt: bool = False                 # push-to-talk (WhatsApp audio)
    caption: str | None = None
    base64_inline: str | None = None     # quando source já manda inline
    filename: str | None = None          # document


class LocationContent(BaseModel):
    kind: Literal["location"] = "location"
    latitude: float
    longitude: float
    place_name: str | None = None


class ContactContent(BaseModel):
    kind: Literal["contact"] = "contact"
    display_name: str
    phones: list[str] = Field(default_factory=list)
    vcard: str | None = None


class ReactionContent(BaseModel):
    kind: Literal["reaction"] = "reaction"
    emoji: str
    target_external_id: str


class StickerContent(BaseModel):
    kind: Literal["sticker"] = "sticker"
    url: str | None = None
    mime_type: str | None = None


class SystemContent(BaseModel):
    """Group join/leave, protocol messages, typing indicators."""
    kind: Literal["system"] = "system"
    event: str
    metadata: dict[str, Any] = Field(default_factory=dict)


ContentBlock = Annotated[
    TextContent | MediaContent | LocationContent | ContactContent
    | ReactionContent | StickerContent | SystemContent,
    Field(discriminator="kind"),
]


# -- Top-level canonical message -------------------------------------------

class CanonicalInboundMessage(BaseModel):
    """Source-agnostic representation of an inbound message.

    Produced by ChannelAdapter.normalize() at the webhook boundary and
    consumed by the full pipeline downstream. Never mutated in place —
    enriched copies are produced at content_process step.
    """

    # Provenance
    source: Source
    source_instance: str          # "Ariel", phone_number_id, ig_account_id
    external_message_id: str
    received_at: datetime
    tenant_id: UUID

    # Parties
    sender: SenderIdentity
    conversation: ConversationContext

    # Content (single block — compound messages with text+media are rare
    # in WhatsApp; when they occur the caption lives inside MediaContent)
    content: ContentBlock

    # Audit / replay — full source payload for 30d retention
    raw_payload: dict[str, Any]

    # Derived — filled by webhook handler post-normalization
    from_me: bool = False
    is_duplicate: bool = False

    @property
    def idempotency_key(self) -> str:
        """Stable key used by Redis SETNX.

        Includes source + instance to prevent collision between Evolution
        and Meta Cloud IDs that happen to match.
        """
        return f"{self.source}:{self.source_instance}:{self.external_message_id}"

    @property
    def sender_key(self) -> str:
        """Stable identity for debounce buffer / idempotency.

        Delegates to `SenderIdentity.external_id` which each adapter fills
        with the most stable available ID in its source (LID > phone
        > push_name-hash).
        """
        return self.sender.external_id
```

### 4.2 Compatibility strategy (refactor seguro)

`InboundMessage` atual em [core/formatter.py:63](apps/api/prosauai/core/formatter.py#L63) não vai ser apagado de cara. Plan:

- **Fase 1 (PR-A1)**: criar `CanonicalInboundMessage` como novo tipo separado; `EvolutionAdapter` produz ele; webhook e debounce passam a trabalhar com o canônico. `InboundMessage` antigo permanece usado apenas por `parse_evolution_message` internamente (que agora vira implementação interna do `EvolutionAdapter`).
- **Fase 2 (PR-A2)**: roteador, facts, pipeline lêem `CanonicalInboundMessage` direto. `InboundMessage` fica legacy.
- **Fase 3 (PR-A3)**: deleta `InboundMessage` antigo após grepar zero uso.

Isso evita PR gigante quebrando tudo de uma vez.

---

## 5. Channel Ingestion Layer (L1) — detalhe

### 5.1 Estrutura de diretórios

```
apps/api/prosauai/
├── channels/
│   ├── __init__.py
│   ├── canonical.py              # CanonicalInboundMessage + ContentBlock (§4)
│   ├── base.py                   # ChannelAdapter protocol
│   ├── registry.py               # get_adapter(source) → ChannelAdapter
│   ├── inbound/
│   │   ├── __init__.py
│   │   ├── evolution/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # X-Webhook-Secret validator
│   │   │   ├── adapter.py        # EvolutionAdapter.normalize()
│   │   │   └── types.py          # Evolution payload TypedDicts (opt)
│   │   ├── meta_cloud/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # X-Hub-Signature-256 verifier
│   │   │   └── adapter.py        # MetaCloudAdapter.normalize()
│   │   └── instagram/            # placeholder — epic 010
│   └── outbound/                 # renomeado de channels/evolution.py
│       ├── __init__.py
│       ├── base.py               # MessagingProvider (send_text/send_media)
│       └── evolution.py
├── api/
│   ├── webhooks/                 # quebrar webhooks.py em 1 arquivo/source
│   │   ├── __init__.py
│   │   ├── dispatch.py           # dispatch_canonical() helper compartilhado
│   │   ├── evolution.py          # router /webhook/evolution/{instance}
│   │   └── meta_cloud.py         # router /webhook/meta/{phone_number_id}
```

### 5.2 `ChannelAdapter` protocol

```python
# apps/api/prosauai/channels/base.py

from typing import Protocol, runtime_checkable
from fastapi import Request
from prosauai.channels.canonical import CanonicalInboundMessage
from prosauai.core.tenant import Tenant


@runtime_checkable
class ChannelAdapter(Protocol):
    """Contract for ingesting messages from a specific source system.

    Adapters are thin translators — they MUST NOT access the database
    or call LLMs. All business logic lives in the pipeline.
    """

    source: str  # Literal value of Source

    async def verify_webhook(
        self, request: Request, raw_body: bytes, instance_ref: str,
    ) -> Tenant:
        """Authenticate and resolve tenant from the incoming request.

        Raises HTTPException(401/403/404) on auth or tenant mismatch.
        """
        ...

    def normalize(
        self, payload: dict, tenant: Tenant,
    ) -> CanonicalInboundMessage | None:
        """Translate the source payload into the canonical model.

        Returns None when the event is purely informational (delivery
        receipt, read receipt) and should not traverse the pipeline.
        Raises MalformedPayloadError on structural issues.
        """
        ...
```

### 5.3 `EvolutionAdapter` — mapping table

Mapping EXAUSTIVO entre campos Evolution e canonical:

| Source field (Evolution) | Canonical field | Transformação |
|--------------------------|-----------------|---------------|
| `data.key.id` | `external_message_id` | Direto |
| `instance` (URL path) | `source_instance` | Direto |
| `data.messageTimestamp` | `received_at` | `datetime.fromtimestamp(int(v), UTC)` |
| `data.key.senderPn` → `split('@')[0]` | `sender.phone` | Dígitos E.164 |
| `data.key.remoteJid` (se `@lid`) | `sender.external_id` | Prefer LID |
| `data.pushName` | `sender.display_name` | Direto |
| `data.key.remoteJid` (se `@g.us`) | `conversation.external_thread_id` | Direto |
| `data.key.remoteJid.includes('@g.us')` | `conversation.channel` | `"group"` senão `"individual"` |
| `data.key.remoteJid` (se group) | `conversation.group_id` | Strip `@g.us` |
| `data.message.messageContextInfo.stanzaId` | `conversation.reply_to_external_id` | Direto |
| `data.contextInfo.mentionedJid[]` | `conversation.mentioned_external_ids` | Strip `@s.whatsapp.net` |
| `data.messageType` | discrimina `ContentBlock.kind` | Switch: `conversation`/`extendedTextMessage` → text; `audioMessage` → audio; etc. |
| `data.message.conversation` OR `extendedTextMessage.text` OR `*Message.caption` | `TextContent.body` ou `MediaContent.caption` | Fallback chain |
| `data.message.audioMessage.url` | `MediaContent.url` | Direto |
| `data.message.audioMessage.mimetype` | `MediaContent.mime_type` | Direto |
| `data.message.audioMessage.seconds` | `MediaContent.duration_seconds` | `int` |
| `data.message.audioMessage.ptt` | `MediaContent.is_ptt` | `bool` |
| `data.message.audioMessage.fileLength` | `MediaContent.size_bytes` | `int` |
| `data.message.base64` | `MediaContent.base64_inline` | Quando presente |
| `data.key.fromMe` | `from_me` | `bool` |
| Full payload | `raw_payload` | `payload.copy()` |

Fallback para `messageType` desconhecido → `SystemContent(event=messageType, metadata=payload)` + log structlog `unknown_message_type`. Não raise.

### 5.4 `MetaCloudAdapter` (validação)

Referência oficial: [WhatsApp Cloud API Webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples).

Mapping table para payload Meta Cloud (`entry[0].changes[0].value.messages[0]`):

| Meta field | Canonical field |
|------------|-----------------|
| `id` | `external_message_id` |
| `from` | `sender.phone` |
| `contacts[0].profile.name` | `sender.display_name` |
| `type` | discrimina `ContentBlock.kind` (`text`/`audio`/`image`/...) |
| `text.body` | `TextContent.body` |
| `audio.id` | `MediaContent.url` (via `/v19.0/{media_id}` resolve em tempo-real) |
| `image.id` | `MediaContent.url` (idem) |
| `audio.mime_type` | `MediaContent.mime_type` |
| `audio.voice` | `MediaContent.is_ptt` |
| `context.id` | `conversation.reply_to_external_id` |
| `context.from` | infer `reply_to` |

Auth: `X-Hub-Signature-256` verificado com `hmac.compare_digest(hmac.new(app_secret, raw_body, sha256).hexdigest(), header.split('sha256=')[1])`.

Handler route: `POST /webhook/meta/{phone_number_id}`. Também lida com `GET` webhook verification Meta exige no setup (`hub.mode=subscribe`).

### 5.5 Shared dispatch

```python
# apps/api/prosauai/api/webhooks/dispatch.py

async def dispatch_canonical(
    canonical: CanonicalInboundMessage,
    request: Request,
) -> WebhookResponse:
    """Common path for all adapters after normalize(). Extracted from
    the current webhook_whatsapp() function."""

    # 1. Idempotency
    # 2. Handoff check
    # 3. Route (MECE)
    # 4. Persist routing decision (fire-and-forget)
    # 5. Dispatch by Decision type → debounce (se RESPOND)
    # 6. Return WebhookResponse
    ...
```

Idempotency key agora usa `canonical.idempotency_key` (inclui source).

Roteador recebe o canonical direto. `_derive_content_kind` em [core/router/facts.py:138](apps/api/prosauai/core/router/facts.py#L138) passa a casar em `canonical.content.kind` em vez de `message.media_type`. Lógica idêntica, só o campo muda.

Debounce append passa a serializar o canonical completo no payload Redis:

```python
payload = {
    "canonical": canonical.model_dump(mode="json"),
    "trace_context": carrier,
    "agent_id": str(agent_id) if agent_id else None,
    "recipient_key": recipient_key,
}
```

`_parse_flush_items` desserializa e reconstrói `CanonicalInboundMessage.model_validate(json.canonical)`. Mensagens múltiplas buferizadas → envia **lista de Canonicals** para o pipeline em vez de text concatenado (mudança semântica — pipeline precisa iterar ou mergear).

**Decisão crítica sobre merge**: quando 3 mensagens chegam em 3 segundos (cliente manda "oi", "queria saber", "o horário"), hoje o debounce concatena por `\n`. Com canonical, 3 opções:

1. **Concatenar só texto**: mesma semântica de hoje, mídia fica perdida se misturada. Simples mas frágil.
2. **Lista de canonicals**: pipeline recebe `list[CanonicalInboundMessage]`, processa cada uma no step content_process, e gera um único "prompt combinado" antes do LLM. Correto mas reescreve pipeline.
3. **First-wins**: só a primeira mensagem do buffer vai. Perde mensagens intermediárias.

**Escolho (2)** porque é o único que suporta "cliente manda áudio seguido de texto complementar" sem bug. Pipeline passa a processar lista → content_process gera uma `text_representation` concatenada → resto do pipeline vê string única.

### 5.6 Auth + tenant resolution unificados

`resolve_tenant_and_authenticate` em [api/dependencies.py](apps/api/prosauai/api/dependencies.py) vira Evolution-específico e é movido para `channels/inbound/evolution/auth.py`. Meta Cloud tem auth próprio em `channels/inbound/meta_cloud/auth.py`. Cada webhook router (`/webhook/evolution/*`, `/webhook/meta/*`) chama seu auth.

---

## 6. Content Processing Layer (L2) — detalhe

### 6.1 Estrutura

```
apps/api/prosauai/processors/
├── __init__.py
├── base.py                  # ContentProcessor protocol + ProcessedContent
├── context.py               # ProcessorContext (http, redis, openai, config, tracer)
├── registry.py              # processor_for(kind) → ContentProcessor
├── cache.py                 # ProcessorCache (sha256 → ProcessedContent)
├── budget.py                # BudgetGuard per-tenant
├── text.py                  # TextProcessor (identity)
├── audio.py                 # AudioProcessor (Whisper)
├── image.py                 # ImageProcessor (GPT-4o-mini vision)
├── document.py              # DocumentProcessor (PDF/docx extract)
├── location.py              # LocationProcessor
├── contact.py               # ContactProcessor
├── reaction.py              # ReactionProcessor
├── sticker.py               # StickerProcessor (UnsupportedProcessor wrapper)
├── unsupported.py           # UnsupportedProcessor (polite fallback)
└── errors.py                # ProcessorError, BudgetExceededError, etc.
```

### 6.2 Contract

```python
# apps/api/prosauai/processors/base.py

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable
from prosauai.channels.canonical import ContentBlock


@dataclass(frozen=True)
class ProcessedContent:
    """Output of a Processor — what the LLM will see downstream.

    `text_representation` is the string that gets folded into the user
    message the LLM consumes. For text, it's the body verbatim. For
    audio/image/document, it's the model's interpretation wrapped in
    tags that help the LLM know it's derived from media (e.g.
    "[áudio transcrito]: ..." or "<imagem>Pessoa sorrindo.</imagem>").
    """

    text_representation: str
    original_kind: str                    # "text" | "audio" | ...
    provider: str | None = None           # "openai:whisper-1"
    tokens_used: int = 0
    cost_usd: Decimal | None = None
    cache_hit: bool = False
    duration_ms: int = 0
    error: str | None = None              # populated on graceful failure
    metadata: dict = None                 # provider-specific (e.g. language detected)


@runtime_checkable
class ContentProcessor(Protocol):
    kind: str  # content kind this processor handles

    async def process(
        self, content: ContentBlock, ctx: "ProcessorContext",
    ) -> ProcessedContent:
        ...
```

### 6.3 `ProcessorContext`

```python
# apps/api/prosauai/processors/context.py

from dataclasses import dataclass
import httpx
import redis.asyncio as redis_async
from openai import AsyncOpenAI
from opentelemetry.trace import Tracer
from prosauai.config import Settings


@dataclass(frozen=True)
class ProcessorContext:
    http: httpx.AsyncClient
    redis: redis_async.Redis
    openai: AsyncOpenAI
    tracer: Tracer
    settings: Settings
    tenant_id: str
    budget_remaining_usd: Decimal | None   # None = no budget enforcement
```

Construído no pipeline antes de chamar `content_process` step. Single shared context para todos os processors de uma mensagem.

### 6.4 Processadores — specs detalhadas

#### TextProcessor (passthrough)

```python
class TextProcessor:
    kind = "text"

    async def process(self, content: TextContent, ctx):
        return ProcessedContent(
            text_representation=content.body,
            original_kind="text",
        )
```

Nunca erra. Zero custo. 0ms overhead.

#### AudioProcessor (Whisper)

Algoritmo:

```
1. Check cache: key = "proc:audio:sha256:" + sha256(url or base64_inline)
   - Hit → return cached ProcessedContent(cache_hit=True)

2. Check budget: if BudgetGuard.exceeded(tenant) → return fallback

3. Check size: if size_bytes > 25MB → return fallback "áudio muito longo"
   (Whisper hard limit)

4. Obtain audio bytes:
   - If base64_inline: decode
   - Else: GET url via httpx (timeout 10s, max 25MB stream)
   - On 410/404: WhatsApp URL expired → return fallback "áudio não
     mais disponível, reenvie por favor"

5. Call Whisper:
   transcription = await ctx.openai.audio.transcriptions.create(
       model="whisper-1",
       file=("audio.ogg", audio_bytes, content.mime_type or "audio/ogg"),
       language="pt",         # hint para PT-BR
       temperature=0.0,       # determinismo
       response_format="verbose_json",  # inclui duration + segments
   )

6. Compute cost: duration_sec * (0.006 / 60)

7. Cache with TTL = 14 days (D4):
   await ctx.redis.setex(key, 1209600, JSON(ProcessedContent))

8. Return:
   ProcessedContent(
       text_representation=f"[ÁUDIO {duration}s]: {transcription.text}",
       original_kind="audio",
       provider="openai:whisper-1",
       cost_usd=cost,
       duration_ms=elapsed,
       metadata={"language": transcription.language, "duration": duration},
   )

9. Errors: timeout/500/429 → retry once with backoff 500ms → fallback
   "não consegui processar o áudio agora, tente novamente em instantes"
```

Retry: 1 retry com jitter 250-750ms em caso de 429/5xx. 0 retries em 4xx (payload inválido).

Timeout total: 15s (budget apertado porque UX é inline).

#### ImageProcessor (GPT-4o-mini vision)

Algoritmo:

```
1. Cache check idêntico ao audio, com prompt_version na key:
   key = "proc:image:sha256:v1:" + sha256(url/base64)

2. Budget check

3. Size: reject > 20MB (OpenAI vision limit)

4. Build prompt (versionado para permitir A/B testing de prompt):
   SYSTEM_PROMPT_V1 = (
       "Descreva a imagem em português, de forma objetiva e direta. "
       "Máximo 200 caracteres. Não interprete, apenas descreva o que "
       "está visível. Se houver texto na imagem, transcreva-o em "
       "seguida em formato: 'Texto visível: \"...\"'."
   )

5. Call Responses API:
   response = await ctx.openai.responses.create(
       model="gpt-4o-mini",
       input=[{
           "role": "user",
           "content": [
               {"type": "input_text", "text": SYSTEM_PROMPT_V1},
               {"type": "input_image", "image_url": image_url_or_b64,
                "detail": "low"},   # "low" = 85 tokens, economiza 10×
           ],
       }],
   )
   description = response.output_text.strip()

6. Combine with caption if present:
   if content.caption:
       text_rep = f"<imagem>{description}</imagem>\n<caption>{content.caption}</caption>"
   else:
       text_rep = f"<imagem>{description}</imagem>"

7. Compute cost: input_tokens * $0.15/MT + output_tokens * $0.60/MT
   + image-specific tokens (85 for "low" detail)

8. Cache 14d, return
```

Prompt gira em função de caption/sem caption: quando há caption, o prompt pede descrição mais curta (caption provavelmente tem o contexto).

Detail `"low"` é **decisão importante**: 85 tokens fixos ≈ $0.013 por imagem, bom trade-off para descrição simples. Se quisermos ler texto em imagens (cardápio, nota fiscal), mudamos pra `"high"` (~765 tokens, $0.11/imagem). Fica configurável via `processor_config.image.detail`.

#### DocumentProcessor

Para PDF/docx — extração textual local sem LLM (barato):

```
1. Download stream (timeout 30s, max 20MB)
2. mime-type switch:
   - application/pdf → pypdf.PdfReader → join pages text
   - application/msword | vnd.openxml...wordprocessing → python-docx
   - text/plain → decode utf-8 directly
   - else → fallback "tipo não suportado"
3. Truncate to 8000 chars (cabe em contexto, alinha com trace_steps limit)
4. text_rep = f"<documento filename='{filename}'>{text}</documento>"
5. Cost: 0 (só parsing local)
```

Dependências novas: `pypdf>=4.0`, `python-docx>=1.1`. Leves.

#### LocationProcessor

```
text_rep = f"<localização>{place_name or 'sem nome'} ({lat},{lng})</localização>"
```

Zero cost. Reverse geocoding opcional em epic futuro.

#### ContactProcessor

```
text_rep = f"<contato>{display_name} ({', '.join(phones)})</contato>"
```

#### ReactionProcessor

```
# Lookup do texto da msg alvo para dar contexto
target = await lookup_message(target_external_id)
text_rep = f"{emoji} — reagiu a: \"{target.content[:100]}\""
```

#### UnsupportedProcessor (sticker, system, video na v1)

```python
class UnsupportedProcessor:
    FALLBACK_TEMPLATES = {
        "sticker": "[figurinha recebida]",
        "video":   "[vídeo recebido — ainda não processo vídeos]",
        "system":  "[evento do sistema]",
    }

    async def process(self, content, ctx):
        kind = content.kind
        text_rep = self.FALLBACK_TEMPLATES.get(kind, f"[{kind} recebido]")
        return ProcessedContent(
            text_representation=text_rep,
            original_kind=kind,
            error=None,
        )
```

Downstream o LLM vê `[figurinha recebida]` no histórico e decide responder de forma contextual ou ignorar. Não bloqueia o pipeline.

### 6.5 Cache strategy

**Chave**: `proc:{kind}:v{prompt_version}:{sha256}`.
- `sha256` do `url` se disponível (audio e image), senão do base64 inline.
- Versão do prompt na chave → bump da versão invalida todo o cache quando prompt muda.

**TTL**: 14 dias (igual retenção da URL WhatsApp). Alinha: cache expira junto com a fonte do dado original.

**Storage**: Redis key value JSON com `ProcessedContent.model_dump()`. Compressão não necessária (tipicamente < 2KB).

**Invalidação manual**: endpoint admin `DELETE /admin/processors/cache/{kind}/{sha256}` (opcional v2).

### 6.6 Budget per-tenant

Tabela nova `processor_usage_daily`:

```sql
CREATE TABLE prosauai_ops.processor_usage_daily (
    tenant_id UUID NOT NULL,
    date DATE NOT NULL,
    kind TEXT NOT NULL,
    provider TEXT NOT NULL,
    cost_usd_total NUMERIC(10, 6) NOT NULL DEFAULT 0,
    invocations INTEGER NOT NULL DEFAULT 0,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, date, kind, provider)
);
```

Incrementado via `BudgetGuard.record(tenant_id, kind, provider, cost)` após cada processor run. Leitura antes do processor check: `SELECT cost_usd_total FROM processor_usage_daily WHERE tenant_id=X AND date=CURRENT_DATE`.

Config por tenant em `tenants.yaml`:

```yaml
tenants:
  - id: pace-internal
    ...
    content_processing:
      enabled: true
      audio_enabled: true
      image_enabled: true
      document_enabled: true
      daily_budget_usd: 10.00     # None = unlimited
```

Quando estourado: processor retorna `ProcessedContent(error="budget_exceeded", text_representation="[áudio recebido — limite diário de transcrição atingido, responderei manualmente]")`. LLM consegue contornar na resposta.

### 6.7 Pipeline step `content_process`

Posição: entre `save_inbound` (5) e `build_context` (7), tornando-se step #6.

```python
# em apps/api/prosauai/conversation/pipeline.py, após step 5

async def _run_content_process_step(
    trace_buffer, canonical_messages, app_state, span
) -> str:
    """Returns concatenated text_representation ready for build_context."""

    with _record_step(
        trace_buffer,
        order=6,
        name="content_process",
        input_jsonb={
            "messages_count": len(canonical_messages),
            "kinds": [m.content.kind for m in canonical_messages],
        },
    ) as step:
        ctx = build_processor_context(app_state, canonical_messages[0].tenant_id)
        results: list[ProcessedContent] = []
        total_cost = Decimal("0")

        for canonical in canonical_messages:
            processor = processor_for(canonical.content.kind)
            result = await processor.process(canonical.content, ctx)
            results.append(result)
            if result.cost_usd:
                total_cost += result.cost_usd

        text_rep = "\n".join(r.text_representation for r in results)

        step.output = {
            "text_representation": text_rep[:2000],  # preview até 2KB
            "total_cost_usd": float(total_cost),
            "cache_hits": sum(1 for r in results if r.cache_hit),
            "providers": list({r.provider for r in results if r.provider}),
            "per_message": [
                {
                    "kind": r.original_kind,
                    "provider": r.provider,
                    "cost_usd": float(r.cost_usd) if r.cost_usd else 0,
                    "cache_hit": r.cache_hit,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in results
            ],
        }

    return text_rep
```

`build_context`, `classify_intent`, `generate_response` passam a receber `text_rep` em vez de `request.text`. `ConversationRequest` é renomeado/ajustado para carregar `canonical_messages: list[CanonicalInboundMessage]`.

### 6.8 `media_analyses` table (auditoria)

Tabela nova para persistir cada análise de mídia (não apenas no trace_steps que é truncado em 8KB):

```sql
-- apps/api/db/migrations/20260420_create_media_analyses.sql

CREATE TABLE IF NOT EXISTS public.media_analyses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_uuid    UUID REFERENCES public.traces(id) ON DELETE CASCADE,
    tenant_id     UUID NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('audio','image','video','document')),
    provider      TEXT NOT NULL,
    source_url    TEXT,          -- URL WhatsApp (expira em 14d)
    source_sha256 TEXT NOT NULL, -- cache key
    mime_type     TEXT,
    size_bytes    INTEGER,
    duration_seconds INTEGER,
    text_result   TEXT,          -- transcription / description (full, não truncado)
    cost_usd      NUMERIC(10, 6),
    cache_hit     BOOLEAN NOT NULL DEFAULT false,
    duration_ms   INTEGER,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_media_analyses_tenant_created
    ON public.media_analyses (tenant_id, created_at DESC);
CREATE INDEX idx_media_analyses_sha256
    ON public.media_analyses (source_sha256);  -- lookup de cache
CREATE INDEX idx_media_analyses_trace
    ON public.media_analyses (trace_uuid);

-- Retention: URL apagada após 14d, row completa apagada após 90d
ALTER TABLE public.media_analyses OWNER TO app_owner;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.media_analyses TO service_role;
```

ADR carve-out: igual `traces` e `trace_steps` (admin-only, sem RLS, accessado só via `pool_admin`). Reutiliza ADR-027.

Retention cron estendido para:
1. `UPDATE media_analyses SET source_url = NULL WHERE created_at < now() - interval '14 days'` (mantém transcript, remove URL expirada)
2. `DELETE FROM media_analyses WHERE created_at < now() - interval '90 days'`

---

## 7. Pipeline changes — 14 steps

### 7.1 Step list atualizada

```
 1. webhook_received    — grava Canonical completo (text_preview OU media metadata)
 2. route               — unchanged
 3. customer_lookup     — unchanged
 4. conversation_get    — unchanged
 5. save_inbound        — salva Canonical + raw_payload; text_preview se texto, media_url/mime se mídia
 6. content_process     — NOVO: chama processor por kind
 7. build_context       — recebe text_representation ∈ concat de ProcessedContent
 8. input_guard         — guard aplica sobre text_representation
 9. classify_intent
10. generate_response
11. evaluate_response
12. output_guard
13. save_outbound
14. deliver
```

### 7.2 `StepRecord.STEP_NAMES` update

[apps/api/prosauai/conversation/step_record.py:46](apps/api/prosauai/conversation/step_record.py#L46) passa a ter 14 entries. Validação `order 1..12` vira `1..14`. Migração de dados não necessária (novos traces têm 14 steps, antigos continuam com 12).

### 7.3 `ConversationRequest` change

```python
class ConversationRequest(BaseModel):
    tenant_id: str
    canonical_messages: list[CanonicalInboundMessage]
    trace_context: dict[str, Any] = Field(default_factory=dict)

    # derived helpers
    @property
    def sender_key(self) -> str:
        return self.canonical_messages[0].sender_key

    @property
    def group_id(self) -> str | None:
        return self.canonical_messages[0].conversation.group_id

    @property
    def agent_id(self) -> str | None:
        # carried through debounce item (unchanged semantics)
        ...
```

Remove `text: str` — não tem mais sentido. `agent_id`/`recipient_key` ficam onde estão.

### 7.4 Pipeline step 5 (save_inbound) update

Hoje salva só `messages.content = request.text`. Com Canonical, precisa salvar:

```python
await save_message(
    pool, conversation.id, request.tenant_id, "inbound",
    content=extract_display_text(canonical),  # caption OR "[áudio 7s]"
    metadata={
        "canonical": canonical.model_dump(mode="json"),
        "source": canonical.source,
        "kind": canonical.content.kind,
        # media URL/mime só se mídia
        "media_url": getattr(canonical.content, "url", None),
        "media_mime": getattr(canonical.content, "mime_type", None),
    },
)
```

Inbox do admin continua mostrando `content` como antes; novo campo `metadata.kind` permite UI mostrar ícone de áudio/imagem ao lado.

---

## 8. Observability changes

### 8.1 Trace step inputs/outputs enriquecidos

`content_process` step output inclui:

```json
{
  "text_representation": "<imagem>Uma pessoa sorrindo em praia...</imagem>",
  "total_cost_usd": 0.013,
  "cache_hits": 0,
  "providers": ["openai:gpt-4o-mini"],
  "per_message": [
    {
      "kind": "image",
      "provider": "openai:gpt-4o-mini",
      "cost_usd": 0.013,
      "cache_hit": false,
      "duration_ms": 2847,
      "error": null
    }
  ]
}
```

### 8.2 OTel spans novos

```
- processor.audio.transcribe
- processor.image.describe
- processor.document.extract
- openai.whisper.create
- openai.vision.responses.create
```

Atributos nos spans: `processor.kind`, `processor.provider`, `processor.cache_hit`, `processor.cost_usd`, `tenant.id`, `trace_steps.span_id`.

### 8.3 Admin UI (trace explorer)

Step novo `content_process` aparece no waterfall. Accordion expandido mostra:
- Preview da transcrição/descrição
- Botão "Ouvir áudio" (só enquanto URL WhatsApp válida — 14d)
- Cost + provider badge
- Cache hit badge (verde quando hit)

Mudança é só de dados — o StepAccordion genérico do epic 008 já renderiza qualquer `input_jsonb`/`output_jsonb`.

### 8.4 Performance AI tab

Extensão de queries em [db/queries/performance.py]: adicionar `cost_usd` agrupado por `provider` e `kind` via `media_analyses`. Novo gráfico "Custo de mídia por dia" (stacked bar: audio/image/document).

---

## 9. Cost analysis

### 9.1 Pricing unitário (valores públicos OpenAI, abril/2026)

| Recurso | Preço | Como cobra |
|---------|-------|------------|
| `whisper-1` | $0.006 / min | Por segundo de áudio, arredondado |
| `gpt-4o-mini` input tokens | $0.15 / M tokens | Prompt + imagem em tokens |
| `gpt-4o-mini` output tokens | $0.60 / M tokens | Descrição gerada |
| `gpt-4o-mini` image "low" | 85 tokens fixos | Incluído em input tokens |
| `gpt-4o-mini` image "high" | 85 base + 170/tile | ≈765 tokens imagem média |

### 9.2 Estimativa mensal para "volume alto" (D5)

Premissa: 10k mídias/mês/tenant, 2 tenants ativos = 20k mídias/mês total.

| Cenário | Volume mensal | Custo mensal |
|---------|---------------|--------------|
| Áudio médio 20s | 10k × 20s × $0.0001/s | **$20/tenant** |
| Imagem "low" detail | 10k × 85 tokens × $0.15/M + 10k × 100 tokens out × $0.60/M | **$0.13 + $0.60 = $0.73/tenant** (sic — vision é barato) |
| Imagem "high" detail | 10k × 765 tokens × $0.15/M + 10k × 150 × $0.60/M | **$1.15 + $0.90 = $2.05/tenant** |

Total baseline: **~$21/tenant/mês** com volume "alto" na estimativa inicial. Cache hit rate esperado >30% (retries + reenvios) → **~$15/tenant/mês**. Orçamento default recomendado: `daily_budget_usd: 5.00` (margem de 10×).

Nota: áudios longos (voice note de 2min) custam $0.72 cada — são os outliers a monitorar.

### 9.3 Upgrade path a `gpt-4o-mini-transcribe`

Quando estabilizar: migrar de `whisper-1` ($0.006/min) para `gpt-4o-mini-transcribe` ($0.003/min + response_format mais restrito mas melhor qualidade PT-BR). Corte de 50% no custo de áudio. Fora de escopo v1.

---

## 10. LGPD & security

### 10.1 Dados sensíveis introduzidos

- **Áudio raw**: URL do WhatsApp (signed, expira 14d). **Não baixamos** o arquivo para storage nosso (D4).
- **Transcrição PT-BR**: pode conter PII (nome, CPF, endereço falado). Tratado como `messages.content` — retenção 90d, sujeito ao retention cron existente.
- **Descrição de imagem**: pode descrever pessoas, documentos. Mesmo tratamento.

### 10.2 ADR a escrever — `ADR-030-content-processing-pii.md`

Deliverable do PR-B. Conteúdo:
- **Decisão**: Transcrições e descrições de mídia são armazenadas em plaintext em `media_analyses.text_result` com retenção 90d. URLs de mídia originais retidas 14d (alinha com expiração natural WhatsApp).
- **Razão**: Observabilidade e troubleshooting; LGPD base legal "execução de contrato" (atendimento automatizado) + "legítimo interesse" (debug).
- **Alternativas rejeitadas**: (a) Hash-only (perde utilidade debug); (b) Storage próprio dos bytes (explode volume, sem ganho); (c) Purge imediato pós-processamento (impossibilita replay em investigação de bug).
- **Mitigação**: retention cron; content_processing.enabled por tenant; futuras classes de dado sensível reconhecidas (CPF, cartão) ganham masking via output_guard existente.

### 10.3 Provider contract

OpenAI Enterprise terms (ou API standard): dados enviados ao endpoint não são usados para treinamento por default desde março/2023. Documentar em ADR-030 linkando [OpenAI data usage policy](https://openai.com/enterprise-privacy/).

### 10.4 Signed URLs do WhatsApp — segurança

URL do `data.message.audioMessage.url` no payload Evolution é tecnicamente um URL autenticado por `mediaKey` — apenas clientes com a chave podem descriptografar o conteúdo completo. Para nossa transcrição via Whisper, precisamos do bytes plaintext, então Evolution já descriptografa internamente e expõe a URL que serve o arquivo descriptografado pela duração do token. Armazenar essa URL 14d é seguro (ninguém sem o mediaKey original consegue decifrar conteúdos futuros, e a URL expira).

Se futuramente usarmos Meta Cloud API direto: aí precisamos chamar `GET /v19.0/{media_id}` para obter URL temporária, em vez de receber URL direta no webhook. Adapter trata a diferença.

---

## 11. Testing strategy

### 11.1 Unit tests (por módulo)

| Módulo | Test files | Coverage alvo |
|--------|-----------|---------------|
| `channels/canonical.py` | `test_canonical_validation.py` | 100% (schemas) |
| `channels/inbound/evolution/adapter.py` | `test_evolution_adapter.py` | ≥95% — uma fixture Evolution real por `messageType` (13 fixtures em `tests/fixtures/captured/`) |
| `channels/inbound/meta_cloud/adapter.py` | `test_meta_cloud_adapter.py` | ≥95% — fixtures das 4 modalidades (text/audio/image/interactive) |
| `channels/inbound/evolution/auth.py` | `test_evolution_auth.py` | ≥95% — HMAC válido/inválido/ausente |
| `channels/inbound/meta_cloud/auth.py` | `test_meta_cloud_auth.py` | ≥95% — signature válida/inválida/GET verification |
| `processors/audio.py` | `test_audio_processor.py` | ≥90% — cache hit/miss, budget exceeded, 25MB reject, WhatsApp URL expired |
| `processors/image.py` | `test_image_processor.py` | ≥90% — caption/sem caption, low/high detail, cache |
| `processors/document.py` | `test_document_processor.py` | ≥85% — PDF, docx, txt, unsupported mime |
| `processors/cache.py` | `test_processor_cache.py` | 100% |
| `processors/budget.py` | `test_budget_guard.py` | ≥90% |

OpenAI calls mockados via `respx` (para httpx) + `AsyncMock` no `AsyncOpenAI` client.

### 11.2 Integration tests

```
tests/integration/webhooks/
├── test_evolution_full_flow.py     # audio PTT + image + text
├── test_meta_cloud_full_flow.py    # equivalente
├── test_canonical_through_pipeline.py
```

Fluxo completo com testcontainers-postgres + fakeredis + OpenAI mocado.

### 11.3 E2E tests

Playwright: abrir admin → Trace Explorer → ver um trace com `content_process` expandido → confirma transcrição visível.

### 11.4 Fixtures reais

Reutilizar `tests/fixtures/captured/ariel_msg_individual_lid_audio_ptt.input.json` já existente + adicionar:
- `ariel_msg_image_with_caption.input.json`
- `ariel_msg_document_pdf.input.json`
- `meta_cloud_audio.input.json` (criar manualmente com payload Meta real)
- `meta_cloud_image.input.json`

---

## 12. Risks & mitigations

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Latência inline > 5s degrada UX | Alto | Média | Budget de 15s total no AudioProcessor; cache agressivo; se p95 > 5s após 1 mês, migrar para async (D2 revisitada em retro) |
| OpenAI indisponível (outage) | Alto | Baixa | Circuit breaker; fallback "estou com dificuldade técnica, responda em texto por favor"; degradação graciosa, pipeline nunca trava |
| Cost explosion (runaway audio loop) | Alto | Média | Budget per-tenant daily; alerta structlog quando 80% budget atingido; rejeito com fallback gracioso quando 100% |
| Cache lotando Redis | Médio | Baixa | TTL 14d; keys prefixadas `proc:*`; monitorar memory via Netdata; eviction policy LRU já configurada |
| MetaCloudAdapter descobre que abstração ficou muito Evolution-shaped | Médio | Média | Test-first: escrever MetaCloudAdapter.normalize() contra fixtures ANTES de terminar EvolutionAdapter; se não couber, revisitar Canonical |
| `ConversationRequest` refactor quebra epic 005 tests | Alto | Alta | Gate de merge: 100% dos 173 testes epic 005 passando. Deprecation shim: aceitar `text` legacy por 1 release, deprecation warning no log |
| Debounce multi-message merge tem bug semântico (ordem, dedup) | Alto | Média | Test matrix: (3 texts), (text + audio), (audio + text + image) — assert ordem cronológica preservada em `text_representation` |
| PDF malformado trava DocumentProcessor | Médio | Média | `pypdf` timeout 10s; try/except ampla → fallback "documento não processável" |
| GPT-4o-mini não entende texto em imagens em PT-BR | Baixo | Média | Prompt explícito pedindo transcrição de texto visível; fallback gracioso (LLM principal decide) |
| Whisper transcreve ruído como palavras estranhas ("alucinação de silêncio") | Médio | Média | Filtro: se duration < 2s OU resultado é match com lista conhecida de alucinações ("legendas em português" etc), retornar `[áudio curto sem fala clara]` |

---

## 13. ADRs a escrever

PR-A:
- **ADR-030**: Canonical inbound message model — replace Evolution-specific InboundMessage
- **ADR-031**: Multi-source channel ingestion via adapter pattern

PR-B:
- **ADR-032**: Content processing layer — strategy pattern with per-kind processors
- **ADR-033**: OpenAI as default provider for STT (Whisper) and vision (GPT-4o-mini)
- **ADR-034**: Media content retention — 14d URL, 90d transcript, LGPD alignment

PR-C:
- **ADR-035**: Meta Cloud API adapter — second-source validation

---

## 14. PR breakdown

### PR-A — Channel Ingestion Normalization (2 semanas)

**Escopo**: Canonical schema, EvolutionAdapter, debounce carrega Canonical, pipeline step_names atualizado mas **sem processors ainda** — usa `TextProcessor` identity para texto e fallback para mídia (comportamento equivalente ao atual em termos de resposta, mas com código arrumado).

**Entregáveis**:
- `channels/canonical.py`, `channels/base.py`, `channels/registry.py`
- `channels/inbound/evolution/{auth,adapter}.py`
- `api/webhooks/evolution.py` + `api/webhooks/dispatch.py`
- Migration `20260420_create_media_analyses.sql`
- `StepRecord.STEP_NAMES` 14 entries, step 6 é placeholder (TextProcessor)
- `ConversationRequest` carrega `canonical_messages: list[CanonicalInboundMessage]`
- Debounce payload é Canonical serialized
- Tests: 100% evolution adapter + canonical validation

**Gate de merge**:
- Todos os 173 tests epic 005 passam
- Todos os 191 tests epic 008 (traces) passam
- SC-PR-A: payload de mídia sem caption ainda não é processado, mas aparece no trace com `content_process.output = {"providers": ["text-placeholder"]}`
- Mensagens de texto têm latência idêntica ou ≤5ms pior que baseline

### PR-B — Content Processing Layer (3 semanas)

**Escopo**: Processors reais (audio/image/document/...), cache, budget, UI admin.

**Entregáveis**:
- `processors/*.py` (10 arquivos)
- Migration `20260505_create_processor_usage_daily.sql`
- Extensão `tenants.yaml` schema (`content_processing: {...}`)
- Extensão `config.py` (`OPENAI_API_KEY`, processor defaults)
- `pricing.py` adiciona whisper-1 + gpt-4o-mini vision
- Retention cron estendido
- Admin UI: `content_process` step no Trace Explorer renderiza preview
- ADR-030 a ADR-034
- Tests: 90%+ em cada processor

**Gate de merge**:
- Fixture test: áudio PTT real chega → Whisper mocado responde → trace mostra transcrição → LLM responde em contexto
- Budget test: exceder budget → fallback gracioso, não bloqueio
- Latência inline áudio 10s: p95 < 8s end-to-end

### PR-C — Meta Cloud API Adapter (1 semana)

**Escopo**: Segundo adapter real para validar que a abstração não é EvolutionShim.

**Entregáveis**:
- `channels/inbound/meta_cloud/{auth,adapter}.py`
- `api/webhooks/meta_cloud.py`
- Fixtures `tests/fixtures/captured/meta_cloud_*.input.json`
- ADR-035
- Docs em `channels/README.md` — como adicionar um novo source (playbook de 4 etapas)

**Gate de merge**:
- Meta Cloud webhook test: payload realista → Canonical válido → pipeline processa sem alteração
- Cross-source idempotency: Evolution ID == Meta ID não colidem
- Zero mudança em código core (pipeline, processors, router) — se houver, revisitar design

---

## 15. Task list

### Phase 0 — Foundation (2 dias)

- [ ] T001 Escrever ADR-030 (Canonical) + ADR-031 (Multi-source adapter) — revisar antes de codar
- [ ] T002 Criar branch `epic/prosauai/009-channel-ingestion-and-content-processing` a partir de develop
- [ ] T003 Pitch.md + spec.md + plan.md em `platforms/epics/009-*/` seguindo template epic 008

### Phase 1 — Canonical schema + EvolutionAdapter (PR-A) (5 dias)

- [ ] T010 [P] Criar `channels/canonical.py` com `CanonicalInboundMessage` + todos os `ContentBlock` types + Pydantic validators
- [ ] T011 [P] Unit tests `test_canonical_validation.py` — cada ContentBlock, idempotency_key uniqueness, sender_key derivation
- [ ] T012 Criar `channels/base.py` com `ChannelAdapter` Protocol + `MalformedPayloadError`
- [ ] T013 Criar `channels/registry.py` — registra EvolutionAdapter; `get_adapter(source)`
- [ ] T014 Mover `channels/evolution.py` → `channels/outbound/evolution.py` (sem mudança de lógica)
- [ ] T015 Criar `channels/inbound/evolution/auth.py` — extrai lógica de `api/dependencies.py::resolve_tenant_and_authenticate`
- [ ] T016 Criar `channels/inbound/evolution/adapter.py` — `EvolutionAdapter.normalize()` usando lógica de `parse_evolution_message`
- [ ] T017 [P] Unit tests `test_evolution_adapter.py` — 1 teste por fixture em `tests/fixtures/captured/ariel_msg_*.input.json` (13 fixtures); assertions sobre campos canonical
- [ ] T018 Criar `api/webhooks/dispatch.py` — `dispatch_canonical()` (extração de `webhook_whatsapp` atual, sem mudança de lógica)
- [ ] T019 Criar `api/webhooks/evolution.py` — router `POST /webhook/evolution/{instance}` usando EvolutionAdapter + dispatch
- [ ] T020 Criar alias de retrocompatibilidade `/webhook/whatsapp/{instance_name}` → chama evolution.py (zero-break deploy)
- [ ] T021 Atualizar `core/router/facts.py` para receber `CanonicalInboundMessage` e derivar ContentKind/EventKind
- [ ] T022 Atualizar `core/debounce.py::append` para carregar Canonical JSON no payload
- [ ] T023 Atualizar `core/debounce.py::_parse_flush_items` para retornar `list[CanonicalInboundMessage]`
- [ ] T024 Atualizar `conversation/models.py::ConversationRequest` — `canonical_messages: list[CanonicalInboundMessage]` (remove `text: str`)
- [ ] T025 [P] Atualizar `pipeline.py::_run_pipeline` para iterar canonical_messages (modo stub: usa TextContent.body se text, senão `[{kind} recebido]`)
- [ ] T026 Atualizar `step_record.STEP_NAMES` para 14 entries (insere `content_process` como #6)
- [ ] T027 Adicionar step 6 stub em `pipeline.py` — chama `TextProcessor` identity e loga no trace
- [ ] T028 Migração 20260420: `media_analyses` table + grants + index

### Phase 2 — Tests + validate PR-A (2 dias)

- [ ] T030 Rodar suíte completa: `uv run pytest` — 0 regression
- [ ] T031 Integration test `test_canonical_through_pipeline.py` — webhook audio PTT chega, trace mostra `content_process.output.kinds=["audio"]` mas text_representation é fallback (`[áudio recebido]`)
- [ ] T032 Testar manualmente via curl 3 webhooks reais (text, audio PTT, image) — comparar com admin Trace Explorer
- [ ] T033 Merge PR-A em `develop` + smoke em staging

### Phase 3 — Processors MVP (PR-B, semana 1) (5 dias)

- [ ] T040 [P] ADR-030 Canonical (já feito) ✓
- [ ] T041 ADR-032 Content processing layer
- [ ] T042 ADR-033 OpenAI as default provider STT + vision
- [ ] T043 ADR-034 Content retention 14d/90d
- [ ] T050 Criar `processors/base.py` — Protocol + `ProcessedContent` dataclass
- [ ] T051 Criar `processors/context.py` — `ProcessorContext` com http, redis, openai, settings
- [ ] T052 Criar `processors/errors.py` — `ProcessorError`, `BudgetExceededError`, `MediaTooLargeError`, `UnsupportedMediaError`
- [ ] T053 Criar `processors/cache.py` — get/set com prefixo `proc:{kind}:v{prompt_version}:{sha256}` + TTL 14d
- [ ] T054 [P] Unit tests `test_processor_cache.py`
- [ ] T055 Criar `processors/budget.py` — `BudgetGuard.check/record` com `processor_usage_daily` table
- [ ] T056 Migration `20260505_create_processor_usage_daily.sql`
- [ ] T057 [P] Unit tests `test_budget_guard.py`
- [ ] T058 Criar `processors/text.py` — TextProcessor identity
- [ ] T059 Criar `processors/registry.py` — `processor_for(kind)` lookup
- [ ] T060 [P] Unit tests `test_text_processor.py`

### Phase 4 — Audio + Image processors (PR-B, semana 2) (5 dias)

- [ ] T070 Adicionar `openai>=1.50` em `apps/api/pyproject.toml`
- [ ] T071 Adicionar `OPENAI_API_KEY` em `config.py` + `.env.example` + `tenants.yaml` schema
- [ ] T072 Criar `processors/audio.py` — `AudioProcessor` conforme §6.4
- [ ] T073 [P] Unit tests `test_audio_processor.py` — mock openai.audio.transcriptions.create; cases: cache miss+hit, budget exceeded, 25MB reject, URL 410, WhatsApp url decode, base64 inline, timeout, retry 429
- [ ] T074 Criar `processors/image.py` — `ImageProcessor` conforme §6.4 (Responses API)
- [ ] T075 [P] Unit tests `test_image_processor.py` — mock openai.responses.create; cases: caption/sem caption, detail low/high, cache, 20MB reject
- [ ] T076 Extender `pricing.py` (ADR-029) — `whisper-1` $0.006/min, `gpt-4o-mini` vision rates
- [ ] T077 Substituir TextProcessor stub em pipeline.py step 6 pelo registry real (usa processor_for(kind))
- [ ] T078 Integrar pricing no `ProcessedContent.cost_usd` — cada processor calcula via pricing.calculate_*
- [ ] T079 Integration test: `test_audio_end_to_end.py` — fixture áudio PTT → Whisper mocado retorna "oi, tudo bem" → trace mostra transcrição → LLM recebe text_rep e responde em contexto

### Phase 5 — Document + remaining processors (PR-B, semana 3) (3 dias)

- [ ] T090 Adicionar `pypdf>=4.0` + `python-docx>=1.1` em pyproject
- [ ] T091 Criar `processors/document.py`
- [ ] T092 [P] Unit tests `test_document_processor.py` — PDF normal, PDF encrypted (reject), docx, txt
- [ ] T093 Criar `processors/location.py` + test
- [ ] T094 Criar `processors/contact.py` + test
- [ ] T095 Criar `processors/reaction.py` + test
- [ ] T096 Criar `processors/unsupported.py` + `processors/sticker.py` (usa unsupported)
- [ ] T097 Registry atualizado com todos os processors

### Phase 6 — Admin UI (PR-B, semana 3 cont) (3 dias)

- [ ] T100 Admin: step `content_process` renderiza em StepAccordion (sem mudança — o componente já é genérico)
- [ ] T101 Admin: no detail de um trace step audio/image, mostrar botão "Ver mídia" se `output.per_message[i].media_url` ainda válida (< 14d)
- [ ] T102 Admin: Performance AI tab — novo gráfico "Custo de mídia/dia" (Recharts stacked bar)
- [ ] T103 Admin: indicador de `kind` nas bolhas de mensagem da inbox (ícone de microfone/imagem/doc)
- [ ] T104 E2E Playwright: abrir trace com `content_process`, confirmar transcrição visível

### Phase 7 — Budget + retention + observability (PR-B, semana 3 cont) (2 dias)

- [ ] T110 Retention cron: adicionar `UPDATE media_analyses SET source_url=NULL WHERE created_at < 14d` + `DELETE WHERE created_at < 90d`
- [ ] T111 Tests retention cron — `test_retention_cron::test_purges_old_media_analyses`
- [ ] T112 Feature flag em tenants.yaml — `content_processing.{enabled, audio_enabled, image_enabled, document_enabled, daily_budget_usd}`; ResenhAI com `enabled: false` default
- [ ] T113 Test: tenant com audio_enabled=false → áudio cai em UnsupportedProcessor
- [ ] T114 Config OTel exporter para novos spans — já automático via instrumentação httpx + openai

### Phase 8 — PR-B smoke + merge (1 dia)

- [ ] T120 Rodar suíte completa: `uv run pytest` — 0 regression + 95%+ coverage nos módulos novos
- [ ] T121 Docker compose up + curl 3 webhooks reais (audio PTT, image, pdf) → verificar resposta contextual no WhatsApp
- [ ] T122 Benchmark: p95 latência áudio 10s end-to-end < 8s (critério SC-B)
- [ ] T123 Merge PR-B em `develop`

### Phase 9 — Meta Cloud Adapter (PR-C) (5 dias)

- [ ] T130 ADR-035 Meta Cloud API adapter
- [ ] T140 Criar `channels/inbound/meta_cloud/auth.py` — X-Hub-Signature-256 + GET verification handler
- [ ] T141 [P] Unit tests `test_meta_cloud_auth.py`
- [ ] T142 Criar `channels/inbound/meta_cloud/adapter.py` — `MetaCloudAdapter.normalize()` conforme §5.4 mapping
- [ ] T143 Criar fixtures `tests/fixtures/captured/meta_cloud_{text,audio,image,interactive}.input.json` com payloads do docs oficial Meta
- [ ] T144 [P] Unit tests `test_meta_cloud_adapter.py` — 1 teste por fixture
- [ ] T145 Criar `api/webhooks/meta_cloud.py` — router POST + GET (verification)
- [ ] T146 Registrar `MetaCloudAdapter` no registry
- [ ] T147 Extender `tenants.yaml` — campo opcional `meta_cloud: {phone_number_id, app_secret, webhook_verify_token}`
- [ ] T148 Integration test `test_meta_cloud_full_flow.py` — payload Meta chega, pipeline processa idêntico, trace mostra `source: whatsapp_meta`
- [ ] T149 Docs `apps/api/prosauai/channels/README.md` — playbook "Como adicionar um novo source" em 4 etapas

### Phase 10 — PR-C merge + epic close (1 dia)

- [ ] T160 Merge PR-C em develop
- [ ] T161 Smoke produção — Ariel continua funcionando idêntico; zero regression
- [ ] T162 Update roadmap.md: epic 009 → shipped
- [ ] T163 Update CLAUDE.md — listar novos módulos channels/ e processors/

---

## 16. Success criteria

- **SC-001**: Áudio PTT do WhatsApp é transcrito e respondido contextualmente pelo bot (não mais silêncio).
- **SC-002**: Imagem (com ou sem caption) é descrita e respondida contextualmente.
- **SC-003**: `p95` latência mensagem texto idêntica ou ≤5ms pior que baseline epic 008.
- **SC-004**: `p95` latência mensagem áudio 10s end-to-end ≤ 8s.
- **SC-005**: Meta Cloud API adapter processa payload real sem alteração em código core (pipeline/processors/router) — validação estrutural da abstração.
- **SC-006**: Trace Explorer mostra step `content_process` com transcript/description completos + cost_usd + cache_hit.
- **SC-007**: Cache hit rate ≥ 30% após 7 dias produção (retries + reenvios).
- **SC-008**: Budget per-tenant enforceado: tenant que excede daily_budget vê fallback educado, não timeout/crash.
- **SC-009**: Retention cron purga URLs expiradas (14d) e rows completas (90d) automaticamente.
- **SC-010**: 100% dos 173 tests epic 005 + 191 tests epic 008 passam após merge.

---

## 17. Open questions (para o review)

Nenhuma — todas as decisões-chave travadas em §1. Se algo aparecer durante a execução, documentar como clarification no spec.md antes de codar.

---

## 18. References (docs oficiais, verificadas via context7 em 2026-04-19)

- **OpenAI Whisper API**: `POST /v1/audio/transcriptions`, modelo `whisper-1`, response_format `verbose_json` inclui `duration` + `language` + `segments`. Max file 25MB. Formats: mp3/mp4/mpeg/mpga/m4a/wav/webm/ogg. [developers.openai.com/api/docs/api-reference/audio](https://developers.openai.com/api/docs/api-reference/audio).
- **OpenAI GPT-4o Vision (Responses API)**: `client.responses.create(model="gpt-4o-mini", input=[{role:"user", content:[{type:"input_text",...}, {type:"input_image", image_url:"..."}]}])`. Suporta URL direta ou base64 data URL. `detail: "low"` = 85 tokens fixos, `"high"` = 85 + ~170/tile. [github.com/openai/openai-python README](https://github.com/openai/openai-python/blob/main/README.md).
- **OpenAI Python SDK**: `AsyncOpenAI` client (async/await). File upload aceita `bytes | PathLike | (filename, contents, mime) tuple`. [context7 `/openai/openai-python`].
- **Meta Cloud API Webhook**: payload schema em [developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples). Auth: `X-Hub-Signature-256` HMAC-SHA256 com app_secret.
- **Platform constraints**:
  - [ADR-011 RLS](platforms/decisions/ADR-011-rls-supabase.md) — carve-out ADR-027 aplicado a `media_analyses`.
  - [ADR-018 LGPD retention](platforms/decisions/ADR-018-data-retention-lgpd.md) — estendido por ADR-034.
  - [ADR-027 admin-tables-no-rls](platforms/decisions/ADR-027-admin-tables-no-rls.md).
  - [ADR-028 pipeline fire-and-forget](platforms/decisions/ADR-028-pipeline-fire-and-forget-persistence.md) — aplica-se a `media_analyses` persist.
  - [ADR-029 pricing constant](platforms/decisions/ADR-029-cost-pricing-constant.md) — estendido com `whisper-1` + `gpt-4o-mini` vision.

---

## 19. Dependencies

**Prerequisite epics** (shipped):
- 001 Channel Pipeline, 002 Observability, 003 Multi-Tenant, 004 Router MECE, 005 Conversation Core, 006 Production Readiness, 007 Admin Foundation, **008 Admin Evolution ✓**

**External**:
- OpenAI API key (provisionar via env `OPENAI_API_KEY`)
- Evolution API continua operacional (sem mudança)
- Meta Business App (opcional, só para PR-C test — pode usar app de sandbox)

**Blockers**:
- Nenhum. Epic 008 closed 2026-04-19.

---

## 20. Delivery shape & checkpoints

**Semana 1**: Foundation + PR-A coding → PR-A review
**Semana 2**: PR-A merge staging + PR-B coding audio/image
**Semana 3**: PR-B coding document + admin UI + budget
**Semana 4**: PR-B integration + PR-B merge staging
**Semana 5**: PR-C coding + merge + epic close

Daily checkpoint em `easter-tracking.md` igual epic 008.

Cut-line: se semana 4 PR-B ainda não mergeou, cortar PR-C e shipar sem Meta Cloud (documenta como follow-up epic 010). Aceitável: a abstração fica validada só parcialmente mas o valor user-facing (mídia funcionando) está entregue.

---

**Fim do documento.** Pronto para execução.
