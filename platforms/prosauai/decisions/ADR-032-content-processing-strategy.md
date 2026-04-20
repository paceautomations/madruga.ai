---
title: 'ADR-032: Content processing strategy (per-kind processor via Strategy pattern)'
status: Accepted
decision: Introduce a formal ``Content Processing`` module in
  ``apps/api/prosauai/processors/`` where each ``ContentKind`` (text, audio,
  image, document, sticker, location, contact, reaction, unsupported) has a
  dedicated processor implementing a ``ContentProcessor`` Protocol. Processors
  receive dependencies via a ``ProcessorContext`` (cache, budget tracker,
  providers) and are looked up by a process-local registry. Pipeline step 6
  (``content_process``) delegates to ``registry.get(kind).process(block, ctx)``
  without knowing the concrete implementation.
alternatives: Monolithic ContentProcessor with if/elif per kind; Pydantic
  discriminated-union dispatch using the Pydantic engine (Annotated + Field
  discriminator) to auto-route; Chain-of-responsibility with processors
  declaring can_handle(block); OpenAI Agent/Tool invocation per kind inside
  the existing LLM agent; External microservice for media processing; Runtime
  class-based dispatch via ``singledispatch``.
rationale: Strategy + Registry is the simplest pattern that (a) keeps new
  ContentKinds aditivos without editing pipeline.py, (b) lets providers be
  swapped in tests (AsyncMock) and in prod (Deepgram in place of Whisper)
  without touching processor code, (c) allows per-kind budget, cache and
  circuit-breaker policies to be expressed as attributes, and (d) pins a
  single OTel span name per kind (``processor.audio``, …) for audit. The
  Protocol is ~20 LOC; the overhead is trivial compared to a hand-rolled
  if/elif that already tops 200 LOC in the spike.
---

# ADR-032: Content processing strategy (per-kind processor via Strategy pattern)

**Status:** Accepted | **Data:** 2026-04-19 | **Supersede:** — | **Relaciona:** [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md), [ADR-030](ADR-030-canonical-inbound-message.md), [ADR-031](ADR-031-multi-source-channel-adapter.md), [ADR-033](ADR-033-openai-stt-vision-provider.md), [ADR-034](ADR-034-media-retention-policy.md)

> **Escopo:** Epic 009 (Channel Ingestion + Content Processing). Esta ADR formaliza a arquitetura da **camada de processamento de conteúdo** — o passo novo do pipeline introduzido pelo PR-A (step 6 `content_process`), que carrega as implementações reais (Whisper, gpt-4o-mini vision, pypdf, python-docx) no PR-B.

## Contexto

O epic 009 precisa transformar cada `ContentBlock` de uma `CanonicalInboundMessage` (ADR-030) em uma representação textual que o LLM de resposta consegue consumir. Os 9 `ContentKind` definidos pelo canonical (text, audio, image, document, sticker, location, contact, reaction, unsupported) têm comportamentos **muito heterogêneos**:

| Kind | Provider externo? | Cacheável? | Budget-tracked? | Determinístico? |
|------|-------------------|------------|-----------------|-----------------|
| text | Não | Não | Não | Sim (passthrough) |
| audio | Sim (Whisper) | Sim (14d) | Sim | Não |
| image | Sim (gpt-4o-mini vision) | Sim (14d) | Sim | Não |
| document | Não (pypdf/python-docx local) | Sim (14d) | Não | Sim |
| sticker | Não | Não | Não | Sim |
| location | Não | Não | Não | Sim |
| contact | Não | Não | Não | Sim |
| reaction | Não | Não | Não | Sim |
| unsupported | Não | Não | Não | Sim (marker) |

A primeira tentativa interna (spike em 2026-04-15) foi um `content_dispatch.py` de ~220 LOC com `if/elif` por kind. Os problemas emergiram rápido:

1. **Escalabilidade horizontal de gente**: qualquer mudança em áudio (ex.: invalidar cache após bump de prompt) exigia PR que tocava o módulo central — conflitos de merge ao tentar paralelizar trabalho entre PR-B (audio/image) e PR-C (Meta Cloud).
2. **Teste acoplado**: `test_content_dispatch.py` virava um fixture zoo (13 mocks por teste). Para testar só `audio`, era preciso carregar fakes de `image`, `document`, `sticker`, etc.
3. **Sem boundary para telemetria**: emitir 1 OTel span por kind ficava em `pipeline/steps/content_process.py`, misturando concerns (orquestração + instrumentação + lógica de cada provider).
4. **Providers "engavetados"**: trocar Whisper por Deepgram no futuro (veja ADR-033 alternativas) exigiria grep por `whisper` em 5 lugares.

O spec do epic 009 (FR-010..FR-022) pede que cada kind seja tratado isoladamente com políticas próprias (budget, cache, retry, fallback). O plan.md descreve o módulo `processors/` com um Protocol + registry — esta ADR formaliza essa decisão.

## Decisão

**Adotamos o padrão Strategy com registry in-process para a camada de processamento de conteúdo**.

### Shape do Protocol

```python
# apps/api/prosauai/processors/base.py
from typing import Protocol, runtime_checkable

from prosauai.channels.canonical import ContentBlock, ContentKind
from prosauai.processors.result import ProcessedContent


@runtime_checkable
class ContentProcessor(Protocol):
    """Strategy especializada por ContentKind.

    Contrato (ver contracts/content-processor.md):
      - NÃO instancia SDK de provider externo — dependências via ProcessorContext.providers.
      - NÃO persiste em DB — persistência é fire-and-forget pelo pipeline após retornar.
      - Retorna SEMPRE um ProcessedContent, mesmo em erro (com marker em bracket notation).
      - Respeita cache, budget e feature flags antes de chamar provider.
      - Emite OTel span `processor.{kind}` com atributos padronizados.
    """

    kind: ContentKind
    version: str            # versão interna (ex: "1.0.0") — invalida cache se mudada
    prompt_version: str     # parte da chave Redis proc:{kind}:v{prompt_version}:{sha}

    async def process(
        self,
        block: ContentBlock,
        ctx: "ProcessorContext",
    ) -> ProcessedContent:
        ...
```

### ProcessorContext (injeção de dependência)

```python
class ProcessorContext(BaseModel):
    tenant_id: UUID
    tenant_config: TenantConfig      # content_processing.* per tenant (yaml-backed)
    cache: ProcessorCache            # Redis proc:* wrapper
    budget_tracker: BudgetTracker    # processor_usage_daily wrapper
    providers: ProcessorProviders    # STTProvider + VisionProvider + DocumentExtractor
    tracer: Tracer                   # OTel
    correlation_id: str
```

### Registry

```python
# apps/api/prosauai/processors/registry.py
_REGISTRY: dict[ContentKind, ContentProcessor] = {}

def register(processor: ContentProcessor) -> None:
    if processor.kind in _REGISTRY:
        raise ValueError(f"Duplicate processor for kind={processor.kind!r}")
    _REGISTRY[processor.kind] = processor

def get(kind: ContentKind) -> ContentProcessor:
    return _REGISTRY[kind]  # KeyError se unregistered → bug, não runtime error
```

Bootstrap único em `main.py`:

```python
from prosauai.processors.text import TextProcessor
from prosauai.processors.audio import AudioProcessor
# …
register(TextProcessor())
register(AudioProcessor(providers=cfg.providers))
# …
```

### Pipeline integration

O step 6 `content_process` (`apps/api/prosauai/pipeline/steps/content_process.py`) vira um *orquestrador puro*:

```python
async def run_content_process(req: ConversationRequest, ctx: PipelineContext) -> ConversationRequest:
    for msg in req.canonical_messages:
        for block in msg.content:
            processor = processors.registry.get(block.kind)
            processed = await processor.process(block, ctx.processor_ctx)
            # ... store processed.text_representation into ConversationRequest; persist via fire-and-forget
```

Zero `if/elif` por kind. Zero acoplamento com `openai`/`pypdf`/`python-docx`.

### Pattern scope (o que estrategia cobre e o que não cobre)

| Concern | Dono | Onde vive |
|---------|------|-----------|
| Lookup do processor certo | Registry | `processors/registry.py` |
| Chamada ao provider externo | Processor + `ProcessorProviders` | `processors/audio.py` + `processors/providers/openai_stt.py` |
| Cache hit/miss + sha256 keying | Processor consulta `ProcessorCache` | `processors/cache.py` (shared) |
| Budget check antes da chamada | Processor consulta `BudgetTracker` | `processors/budget.py` (shared) |
| Circuit breaker por (tenant, provider) | Processor consulta `CircuitBreaker` | `processors/breaker.py` (shared, memória local) |
| Fallback (marker bracket notation) | Processor retorna `ProcessedContent` com `marker` | `processors/result.py` (ProcessorStatus enum) |
| Retenção de transcript/URL | Pipeline (fire-and-forget) | `pipeline/steps/content_process.py` + `media_analyses` SQL |
| Agregação diária de custo | BudgetTracker.record_usage | `processor_usage_daily` SQL |

## Alternativas consideradas

### A. Monolithic ContentProcessor com if/elif

O spike descrito no Contexto (~220 LOC). Rejeitado por escalar linearmente com kinds novos, não ter boundary testável e violar SRP.

### B. Pydantic discriminated-union dispatch

Registrar processors como `Annotated[Union[AudioProcessor, ImageProcessor, ...], Field(discriminator="kind")]` e deixar o Pydantic engine rotear. Rejeitado porque:

- ContentKind já é uma StrEnum no `ContentBlock` (ADR-030). Union em outro lugar duplica a discriminação.
- O engine Pydantic não lida com async bem — seria necessário wrapping.
- Registry explícito é trivial (~15 LOC) e mantém stack mínima (stdlib only).

### C. Chain of Responsibility com `can_handle(block)`

Cada processor declara se atende um bloco. Rejeitado porque:

- O match é por `ContentKind`, não por semântica complexa — `can_handle` seria sempre `return block.kind == self.kind`, mero wrap.
- Ordenação da cadeia vira problema (quem resolve primeiro se dois processadores respondem "sim"?).
- Registry O(1) é mais claro que iteração O(n).

### D. OpenAI Agent/Tool invocation per kind dentro do LLM agent existente

Cada kind vira uma tool definida no agente pydantic-ai; o modelo decide qual chamar. Rejeitado porque:

- Coloca lógica determinística (passthrough de texto, marker de unsupported) atrás de uma LLM call — custo + latência injustificados.
- Cache Redis deixa de fazer sentido (tool call decisions não cacheáveis no nível Redis sem hacks).
- Budget tracking fica opaco (LLM decide quando invocar — sem backpressure previsível).
- Violaria [ADR-001](ADR-001-pydantic-ai.md) ao misturar orquestração de I/O com raciocínio do modelo.

### E. Microservice externo para media processing

Um serviço separado (Python ou Go) que recebe `ContentBlock`, processa e retorna `ProcessedContent`. Rejeitado porque:

- Adiciona hop de rede (overhead latência + network failure modes) para o cenário síncrono da pipeline.
- Duplica infra (deploy, observabilidade, health checks).
- Viola princípio *Pragmatismo > elegância*. Escopo v1 é 2 tenants e 10k mídias/mês — não justifica.
- Revisitar quando volume > 100k/mês/tenant OR quando GPU-backed local inference entrar (epic futuro).

### F. `functools.singledispatch` baseado em ContentKind

Rejeitado porque `singledispatch` opera em tipo do primeiro argumento; `ContentKind` é um valor (enum), não um tipo. Precisaria de `singledispatchmethod` com adaptação — menos claro que registry dict.

## Consequências

### Positivas

- **Zero toque em pipeline para kinds novos**: adicionar `VideoProcessor` no epic 010 é *somente* (a) criar classe, (b) `register()` no bootstrap. Nenhum outro arquivo muda.
- **Testabilidade granular**: `test_audio_processor.py` injeta `STTProvider` mockado sem carregar vision/document. Cada arquivo de teste tem < 5 fixtures.
- **OTel spans padronizados**: 1 span por kind (`processor.audio`, `processor.image`, …) com atributos iguais (cache_hit, cost_usd, latency_ms). Facilita dashboards admin do epic 008.
- **Swap de provider é trivial**: trocar Whisper por Deepgram no futuro é reescrever `providers/openai_stt.py` como `providers/deepgram_stt.py` e apontar `ProcessorProviders.stt` no bootstrap. Processor não muda.
- **Per-kind policy natural**: `AudioProcessor.prompt_version = "v1"`; bump para `"v2"` invalida cache só para áudio — image/document intocados.
- **Circuit breaker por (tenant, provider)** vive no próprio processor — incidente OpenAI-STT não cascateia para vision.

### Negativas

- **Overhead de arquivos**: 9 kinds × 1 arquivo = 9 arquivos em `processors/`. Mitigado pela naturalidade (cada arquivo < 150 LOC, focado).
- **Bootstrap lista longa**: `main.py` ganha 9 linhas `register(...)`. Aceitável — torna dependências explícitas.
- **Learning curve para novos processors**: contribuintes devem entender o Protocol + registry. Mitigado pelo `contracts/content-processor.md` e README.
- **Registry global (module-level)**: testes que querem isolamento devem usar fixture de `pytest` para limpar/repovoar. Mitigado — padrão testado em `tests/fixtures/processor_registry.py`.

### Neutras

- **Performance**: lookup `_REGISTRY[kind]` é O(1) dict access (~100ns). Insignificante no budget de 8s p95.
- **Memory**: cada processor é singleton instanciado no bootstrap — custo desprezível.

## Escopo por PR

| PR | Entregas |
|----|----------|
| **PR-A** | Protocol + Registry + `TextProcessor` (identity passthrough). `UnsupportedProcessor` emite marker. Mídia retorna fallback textual (marker). |
| **PR-B** | `AudioProcessor`, `ImageProcessor`, `DocumentProcessor`, `StickerProcessor`, `LocationProcessor`, `ContactProcessor`, `ReactionProcessor` reais. Cache + BudgetTracker + CircuitBreaker. Admin gráfico de custo diário. |
| **PR-C** | Nenhuma mudança em processors/. Valida via SC-013 (diff zero) que a arquitetura suporta novo canal. |

## Kill criteria

Esta ADR é invalidada se:

1. **Contract test `test_content_processor_contract.py` precisar ampliar o Protocol para cada processor novo** (ex.: adicionar método `post_validate()` só para audio) — sinal de que abstração não é coesa e deveríamos quebrar em Protocols específicos por família.
2. **Latência do step 6 com `kind=text` for > 2ms p95** — o Registry lookup + instanciação de `ProcessedContent` estaria penalizando o happy path. Força inlinear o caso text.
3. **Mais de 3 processors precisarem compartilhar > 30% do código** via herança — força introduzir classes base (AudioProcessor e ImageProcessor hoje compartilham ~40% via helpers compostos, não herança).

## Links

- Implementação: [apps/api/prosauai/processors/](https://github.com/paceautomations/prosauai/tree/develop/apps/api/prosauai/processors)
- Contract: [epics/009-channel-ingestion-and-content-processing/contracts/content-processor.md](../epics/009-channel-ingestion-and-content-processing/contracts/content-processor.md)
- Registry tests: [apps/api/tests/contract/test_content_processor_contract.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/tests/contract/test_content_processor_contract.py)
- Data model: [epics/009-channel-ingestion-and-content-processing/data-model.md §2.2 (ProcessedContent) + §2.3 (ProcessorContext)](../epics/009-channel-ingestion-and-content-processing/data-model.md)
- Alternativa B (discriminated union) — ver ADR-030 §Alternativas B, mesma razão rejeitada aqui.
