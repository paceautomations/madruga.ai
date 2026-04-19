# Contract — `ContentProcessor` Protocol + `ProcessorContext`

**File location**: `apps/api/prosauai/processors/base.py` (Protocol + Context) + registry em `apps/api/prosauai/processors/registry.py`.

**Stability**: STABLE após merge do PR-B. Novos processors (futuros) implementam o mesmo Protocol sem tocar pipeline.

---

## 1. `ContentProcessor` Protocol

```python
from typing import Protocol, runtime_checkable

from prosauai.channels.canonical import ContentBlock, ContentKind
from prosauai.processors.result import ProcessedContent


@runtime_checkable
class ContentProcessor(Protocol):
    """Processor especializado por ContentKind.

    Contrato:
      - Registra-se globalmente via `registry.register(processor)`.
      - Pipeline NUNCA instancia SDK de provider externo — toda dependência via ProcessorContext.providers.
      - Retorna SEMPRE um ProcessedContent (mesmo em erro — usa marker).
      - Respeita cache antes de chamar provider.
      - Respeita budget antes de chamar provider (consulta ProcessorContext.budget_tracker).
      - Respeita feature flags antes de chamar provider (consulta ProcessorContext.tenant_config).
      - Emite OTel spans via ProcessorContext.tracer (nome: f"processor.{kind}").
      - Não persiste em DB — persistência é fire-and-forget pelo pipeline após retornar.

    Atributos:
      kind: ContentKind — o kind que este processor atende.
      version: str       — versão interna (ex: "1.0.0") para invalidação de cache.
      prompt_version: str — versão do prompt (ex: "v1"); bump invalida cache via key change.
    """

    kind: ContentKind
    version: str
    prompt_version: str

    async def process(
        self,
        block: ContentBlock,
        ctx: "ProcessorContext",
    ) -> ProcessedContent:
        """Processa um bloco. Retorno SEMPRE válido (incluindo erros com marker)."""
        ...
```

---

## 2. `ProcessorContext`

```python
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from prosauai.config import TenantConfig  # existente, estendida
from prosauai.processors.cache import ProcessorCache  # novo
from prosauai.processors.budget import BudgetTracker  # novo
from prosauai.observability.tracer import Tracer  # existente


class STTProvider(Protocol):
    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language: str = "pt",
    ) -> tuple[str, dict]:
        """Retorna (transcript, raw_response_dict)."""
        ...


class VisionProvider(Protocol):
    async def describe(
        self,
        image_bytes: bytes,
        mime_type: str,
        detail: str = "low",
        prompt: str = ...,
    ) -> tuple[str, dict]:
        ...


class DocumentExtractor(Protocol):
    async def extract(
        self,
        doc_bytes: bytes,
        mime_type: str,
        max_pages: int,
    ) -> tuple[str, dict]:
        ...


class ProcessorProviders(BaseModel):
    stt: STTProvider
    vision: VisionProvider
    document_extractor: DocumentExtractor

    model_config = {"arbitrary_types_allowed": True, "frozen": True}


class ProcessorContext(BaseModel):
    tenant_id: UUID
    tenant_config: TenantConfig
    cache: ProcessorCache
    budget_tracker: BudgetTracker
    providers: ProcessorProviders
    tracer: Tracer
    correlation_id: str

    model_config = {"arbitrary_types_allowed": True, "frozen": True}
```

---

## 3. `ProcessorCache` contrato

```python
from typing import Protocol


class ProcessorCache(Protocol):
    """Redis-backed cache com key pattern proc:{kind}:v{prompt_version}:{sha256}."""

    async def get(self, kind: str, prompt_version: str, content_sha256: str) -> ProcessedContent | None:
        """Retorna ProcessedContent cached ou None. cache_hit=True set pelo caller."""
        ...

    async def set(self, kind: str, prompt_version: str, content_sha256: str, value: ProcessedContent) -> None:
        """TTL 14 dias. raw_response é stripped antes de serializar (economia Redis)."""
        ...
```

---

## 4. `BudgetTracker` contrato

```python
from decimal import Decimal
from typing import Protocol


class BudgetTracker(Protocol):
    """Wrapper em torno de processor_usage_daily. Single-row query por chamada."""

    async def check_allowed(
        self,
        tenant_id: UUID,
        daily_budget_usd: Decimal,
    ) -> bool:
        """True se spent_today + estimated_cost <= daily_budget_usd.

        Nota: race window aceita (≤1 chamada acima do limite por minuto, §Assumptions spec).
        """
        ...

    async def record_usage(
        self,
        tenant_id: UUID,
        kind: str,
        provider: str,
        cost_usd: Decimal,
        cache_hit: bool,
    ) -> None:
        """Fire-and-forget UPSERT em processor_usage_daily."""
        ...
```

---

## 5. Implementações

| Processor | Provider | Cache | Budget check | Marker em erro |
|-----------|----------|-------|--------------|----------------|
| `TextProcessor` | n/a (passthrough) | **Não** | **Não** | — (nunca erra) |
| `AudioProcessor` | `openai/whisper-1` via `STTProvider` | Sim | Sim | `[audio_silent]`, `[media_too_large: {mb}]`, `[timeout]`, `[provider_unavailable]`, `[budget_exceeded]` |
| `ImageProcessor` | `openai/gpt-4o-mini` via `VisionProvider` | Sim | Sim | `[timeout]`, `[provider_unavailable]`, `[budget_exceeded]` |
| `DocumentProcessor` | `pypdf`, `python-docx` (local) via `DocumentExtractor` | Sim | **Não** (local, custo trivial) | `[pdf_scanned]`, `[pdf_encrypted]`, `[timeout]` |
| `StickerProcessor` | n/a | Não | Não | — (sempre `[sticker: {descrição trivial}]`) |
| `LocationProcessor` | n/a | Não | Não | — (text_representation determinístico) |
| `ContactProcessor` | n/a | Não | Não | — (text_representation determinístico) |
| `ReactionProcessor` | n/a | Não | Não | — (text_representation determinístico) |
| `UnsupportedProcessor` | n/a | Não | Não | `[content_unsupported: {sub_type}]` |

---

## 6. Algoritmo genérico (pseudocódigo)

```python
async def process(self, block: ContentBlock, ctx: ProcessorContext) -> ProcessedContent:
    with ctx.tracer.start_as_current_span(f"processor.{self.kind}") as span:
        span.set_attribute("tenant.id", str(ctx.tenant_id))
        span.set_attribute("processor.kind", self.kind)
        span.set_attribute("processor.prompt_version", self.prompt_version)

        # 1. Feature flag
        if not self._is_enabled(ctx.tenant_config):
            return ProcessedContent(
                kind=self.kind,
                provider="internal/disabled",
                text_representation=f"[feature_disabled: {self.kind}]",
                status=ProcessorStatus.ERROR,
                marker=f"[feature_disabled: {self.kind}]",
            )

        # 2. Content sha256 para cache + dedup
        content_sha256 = await self._compute_sha256(block, ctx)

        # 3. Cache lookup
        cached = await ctx.cache.get(self.kind, self.prompt_version, content_sha256)
        if cached:
            span.set_attribute("processor.cache_hit", True)
            return cached.model_copy(update={"cache_hit": True})

        # 4. Budget check
        estimated_cost = self._estimate_cost(block)
        if not await ctx.budget_tracker.check_allowed(ctx.tenant_id, ctx.tenant_config.daily_budget_usd):
            return ProcessedContent(
                kind=self.kind,
                provider="internal/budget_guard",
                text_representation="[budget_exceeded]",
                status=ProcessorStatus.BUDGET_EXCEEDED,
                marker="[budget_exceeded]",
            )

        # 5. Circuit breaker check (abstrai provider ou camada externa)
        if self._breaker_is_open(ctx):
            return ProcessedContent(
                kind=self.kind,
                provider=self._provider_name(ctx),
                text_representation="[provider_unavailable]",
                status=ProcessorStatus.ERROR,
                marker="[provider_unavailable]",
            )

        # 6. Download (se não tem data_base64 inline)
        try:
            content_bytes = await self._fetch_bytes(block, ctx)
        except MediaTooLargeError as e:
            return ProcessedContent(... marker=f"[media_too_large: {e.size_mb}]" ...)
        except DownloadError:
            return ProcessedContent(... marker="[download_failed]" ...)

        # 7. Provider call (with retry)
        try:
            text_result, raw = await self._call_provider_with_retry(content_bytes, ctx)
        except TimeoutError:
            return ProcessedContent(... marker="[timeout]" ...)
        except ProviderError as e:
            self._record_breaker_failure(ctx)
            return ProcessedContent(... marker="[provider_unavailable]" ...)

        # 8. Post-process (hallucination filter, PII mask, etc)
        text_result = self._post_process(text_result, block, ctx)

        # 9. Build + cache + return
        result = ProcessedContent(
            kind=self.kind,
            provider=self._provider_name(ctx),
            text_representation=text_result,
            cost_usd=self._actual_cost(raw),
            latency_ms=...,
            cache_hit=False,
            status=ProcessorStatus.OK,
            raw_response=raw,
        )
        await ctx.cache.set(self.kind, self.prompt_version, content_sha256, result)
        await ctx.budget_tracker.record_usage(ctx.tenant_id, self.kind, result.provider, result.cost_usd, False)
        return result
```

---

## 7. Registry

```python
# apps/api/prosauai/processors/registry.py

_REGISTRY: dict[ContentKind, ContentProcessor] = {}


def register(processor: ContentProcessor) -> None:
    if processor.kind in _REGISTRY:
        raise ValueError(f"Duplicate processor for kind={processor.kind!r}")
    _REGISTRY[processor.kind] = processor


def get(kind: ContentKind) -> ContentProcessor:
    return _REGISTRY[kind]  # KeyError se unregistered


def registered_kinds() -> list[ContentKind]:
    return sorted(_REGISTRY.keys())
```

---

## 8. Circuit breaker (policy embutida)

Ver spec FR-023 para parâmetros:
- 5 falhas consecutivas em 60s → abre.
- 30s open → 1 half-open probe → fecha (sucesso) ou reabre com backoff 30→60→120→300s (cap).
- Reset: 10 min sem falhas → volta ao estado inicial.

Implementação: `prosauai.processors.breaker.CircuitBreaker` por `(tenant_id, provider)`. Estado em memória do worker (não compartilhado) — aceito porque falha em 1 worker não esconde incidente real; N workers independentes convergem ao fallback via gradient.

---

## 9. Tests de contrato (obrigatórios)

```python
# tests/contract/test_content_processor_contract.py

@pytest.mark.parametrize("processor_cls", [
    TextProcessor, AudioProcessor, ImageProcessor, DocumentProcessor,
    StickerProcessor, LocationProcessor, ContactProcessor, ReactionProcessor,
    UnsupportedProcessor,
])
def test_implements_protocol(processor_cls):
    p = processor_cls(...)
    assert isinstance(p, ContentProcessor)


@pytest.mark.asyncio
async def test_always_returns_processed_content(processor_cls, provider_mock_raises_5xx):
    """Mesmo quando provider explode, retorna ProcessedContent com marker."""
    p = processor_cls(...)
    result = await p.process(block, ctx)
    assert isinstance(result, ProcessedContent)
    assert result.status != ProcessorStatus.OK
    assert result.marker is not None


@pytest.mark.asyncio
async def test_cache_hit_second_call(audio_processor, redis_mock):
    """Segunda chamada com mesmo sha256 → cache_hit=True, zero chamadas ao provider."""
    ...


@pytest.mark.asyncio
async def test_budget_exceeded_fallback(audio_processor, budget_tracker_saturated):
    """Budget estourado → marker=[budget_exceeded], zero chamadas ao provider."""
    ...
```

---

## 10. Garantias NÃO-cobertas

- **Persistência em `media_analyses`**: responsabilidade do pipeline step `content_process` via fire-and-forget. Processor retorna resultado e esquece.
- **Instrumentação OTel**: processor emite span próprio, mas pipeline decora com atributos (tenant_id, correlation_id etc) antes de chamar.
- **Retry policy**: implementada dentro do processor (step 7 do algoritmo) — não é contrato público.
