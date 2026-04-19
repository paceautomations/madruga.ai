---
title: 'ADR-033: OpenAI (Whisper + gpt-4o-mini) as default STT & vision provider (v1)'
status: Accepted
decision: Use OpenAI ``whisper-1`` for PT-BR audio transcription and OpenAI
  ``gpt-4o-mini`` (Responses API) for image description as the default
  providers in epic 009 v1. Both are wired behind the ``STTProvider`` /
  ``VisionProvider`` protocols defined in ``prosauai.processors.base``,
  and are injected through ``ProcessorContext.providers``. Swapping to
  another vendor is a one-file change (provider wrapper) with zero impact
  on processors, pipeline, router or observability.
alternatives: Deepgram (STT — Nova-2 / Whisper hosted); Azure AI Speech
  (STT); Google Cloud Speech-to-Text (STT); OpenAI
  ``gpt-4o-mini-transcribe`` (newer unified audio endpoint); Anthropic
  Claude Haiku 3.5 (vision only — no STT); self-hosted faster-whisper
  on GPU.
rationale: The prosauai stack already consumes OpenAI via Bifrost for the
  conversation generator (ADR-002) and for gpt-5-mini pricing (ADR-025,
  ADR-029). Reusing the same vendor for STT/vision minimises ops cost
  (1 key, 1 dashboard, 1 invoice), gives strong PT-BR quality out of the
  box, ships with an official Python SDK that is OTel-friendly via
  ``opentelemetry-instrumentation-httpx``, and keeps the v1 surface
  small enough that we can validate the ``ContentProcessor`` Protocol
  abstraction (SC-013 gate). Swap is planned to be trivial: every
  processor only depends on the Protocol, not on ``openai.AsyncClient``
  directly.
---

# ADR-033: OpenAI (Whisper + gpt-4o-mini) as default STT & vision provider (v1)

**Status:** Accepted | **Data:** 2026-04-19 | **Supersede:** — | **Relaciona:** [ADR-029](ADR-029-cost-pricing-constant.md), [ADR-032](ADR-032-content-processing-strategy.md), [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md)

> **Escopo:** Epic 009 (Channel Ingestion + Content Processing) PR-B. Esta ADR formaliza **qual provider externo** o ``AudioProcessor`` e o ``ImageProcessor`` usam em v1, e **por que** a escolha é reversível sem reescrever nada além do arquivo do wrapper.

## Contexto

O epic 009 introduz dois processors que, diferente do ``TextProcessor`` (passthrough) e dos processors determinísticos (``sticker``, ``location``, ``contact``, ``reaction``, ``unsupported``), dependem de um provider externo:

| Processor | Função v1 | Protocolo | SLO (spec) |
|-----------|-----------|-----------|------------|
| ``AudioProcessor`` | Transcrever PTT/áudio em PT-BR para texto utilizável pelo gerador | ``STTProvider.transcribe(audio_bytes, mime_type, language) -> (transcript, raw)`` | p95 áudio 10s end-to-end < 8s (SC-001) |
| ``ImageProcessor`` | Gerar descrição textual da imagem (com ou sem legenda), opcional leitura de texto (``detail="high"``) | ``VisionProvider.describe(image_bytes, mime_type, detail, prompt) -> (description, raw)`` | p95 imagem end-to-end < 9s (SC-002) |

Ambos carregam custo por mensagem (FR-008, FR-009 spec), precisam de **cache de sha256** (FR-022), **budget enforcement** (FR-018), **circuit breaker por tenant+provider** (FR-023) e **retry com jitter** (FR-024). Toda essa orquestração é de responsabilidade do **processor**, não do provider — o provider é só um wrapper de I/O ([ADR-032 §"Provider vs Processor"](ADR-032-content-processing-strategy.md)).

A pergunta travada em [decisions.md D6 do epic 009](../epics/009-channel-ingestion-and-content-processing/decisions.md): *"qual provider de STT e vision para v1?"*.

Duas forças empurram a escolha:

1. **Ops simples**. Já temos ``OPENAI_API_KEY`` em env, faturamento consolidado, a instrumentação ``opentelemetry-instrumentation-httpx`` do epic 002 já captura chamadas ao endpoint ``api.openai.com``. Adicionar um segundo vendor (Deepgram, Azure) significa: +1 secret, +1 conta, +1 pricing table em ``pricing.py`` (ADR-029), +1 painel de billing para o operador monitorar.
2. **Qualidade PT-BR**. Whisper v3 (acessível via ``whisper-1``) é benchmark-vencedor para PT-BR em áudios curtos de WhatsApp (PTT 2–30s, alto ruído de fundo, sotaques variados). Concorrentes (Deepgram Nova-2, Azure Speech PT-BR) empatam em corpora controlados mas perdem em PTT curto com *filler words* ("é... tipo...").

O epic 009 **não** é o momento certo para comparar 4 vendors em produção — isto seria um epic à parte com corpus controlado. Em vez disso, adotamos OpenAI para v1 e **investimos o esforço em tornar o swap trivial** (Protocol + ``ProcessorContext.providers`` injection).

## Decisão

### STT: ``whisper-1`` (OpenAI Audio API)

**Chamada via** [``openai.AsyncOpenAI.audio.transcriptions.create``](https://platform.openai.com/docs/api-reference/audio/createTranscription):

```python
# apps/api/prosauai/processors/providers/openai_stt.py

class OpenAISTTProvider:
    """Implementation of STTProvider backed by OpenAI Whisper-1."""

    def __init__(self, client: "openai.AsyncOpenAI", *, timeout_s: float = 15.0):
        self._client = client
        self._timeout_s = timeout_s

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language: str = "pt",
    ) -> tuple[str, dict]:
        response = await self._client.audio.transcriptions.create(
            model="whisper-1",
            language=language,
            file=(f"audio.{_ext(mime_type)}", audio_bytes, mime_type),
            response_format="verbose_json",
            timeout=self._timeout_s,
        )
        return response.text, response.model_dump()
```

**Parâmetros fixos**:

- ``language="pt"`` — forçamos o idioma (FR-008) em vez de deixar Whisper auto-detectar. Reduz drift em áudios curtos.
- ``response_format="verbose_json"`` — devolve segments + duração para o filtro de alucinação (FR-025 / ``hallucination_filter.py``).
- Sem ``prompt=`` — prompting de Whisper é *finicky* e costuma piorar a qualidade sem um corpus de calibração por tenant.

**Pricing (ADR-029 extensão, PR-B)**:

- ``whisper-1``: USD 0.006 / minuto de áudio.
- Registrado como ``PRICING_TABLE["openai/whisper-1"] = AudioPrice(per_minute_usd=Decimal("0.006"))`` em ``conversation/pricing.py``.

### Vision: ``gpt-4o-mini`` (OpenAI Responses API)

**Chamada via** [``openai.AsyncOpenAI.responses.create``](https://platform.openai.com/docs/api-reference/responses):

```python
# apps/api/prosauai/processors/providers/openai_vision.py

DEFAULT_PROMPT = (
    "Describe this image concisely in Portuguese (Brazil), focusing on "
    "objects, people, text content (if any) and anything that helps a "
    "customer service agent understand what the customer is sharing. "
    "Do not invent details that are not visible. Max 120 words."
)


class OpenAIVisionProvider:
    """Implementation of VisionProvider backed by gpt-4o-mini via Responses API."""

    def __init__(self, client: "openai.AsyncOpenAI", *, timeout_s: float = 12.0):
        self._client = client
        self._timeout_s = timeout_s

    async def describe(
        self,
        image_bytes: bytes,
        mime_type: str,
        detail: str = "low",
        prompt: str = DEFAULT_PROMPT,
    ) -> tuple[str, dict]:
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
        response = await self._client.responses.create(
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": detail},
                ],
            }],
            timeout=self._timeout_s,
        )
        return response.output_text, response.model_dump()
```

**Parâmetros por-tenant** (``tenants.yaml::content_processing.image.detail``):

- ``"low"`` (default) — overhead 85 tokens, ~0.5s, suficiente para "o cliente mandou foto de produto X".
- ``"high"`` — overhead 170–765 tokens (depende do tamanho), ~1.5s, lê texto em cardápios/notas fiscais. Habilitado caso-a-caso (SC-002 gate: p95 continua < 9s).

**Pricing (ADR-029 extensão, PR-B)**:

- ``gpt-4o-mini``: USD 0.150 / 1M tokens input, USD 0.600 / 1M tokens output.
- Custo típico imagem ``detail="low"``: ~85 tokens input + ~80 tokens output ≈ **USD 0.00006 por imagem** (cache hit = zero).

### Injeção via ``ProcessorContext.providers``

Nenhum processor toca ``openai.*`` diretamente. A dependência é declarada como **Protocol** (``STTProvider``, ``VisionProvider`` em ``prosauai.processors.base``) e injetada pelo lifespan do FastAPI:

```python
# apps/api/prosauai/main.py (lifespan)

openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

processor_providers = ProcessorProviders(
    stt=OpenAISTTProvider(client=openai_client),
    vision=OpenAIVisionProvider(client=openai_client),
    document_extractor=LocalDocumentExtractor(),
)

registry.register(AudioProcessor(providers=processor_providers, ...))
registry.register(ImageProcessor(providers=processor_providers, ...))
```

Em testes, o mesmo ``ProcessorProviders`` é construído com ``AsyncMock`` / dublés — o processor não sabe que não é OpenAI real.

## Alternativas consideradas

### A. Deepgram (STT — Nova-2)

**Prós**:
- Latência ~30–40% menor que Whisper em áudios curtos (streaming-first).
- Suporta PT-BR em Nova-2 desde 2024Q3.
- Preço competitivo (USD 0.0043 / min).

**Rejeitada por**:
- +1 vendor, +1 secret, +1 dashboard (conflita com princípio I — Pragmatismo).
- Quality em PT-BR PTT com ruído de fundo é marginalmente inferior a Whisper em benchmarks internos (spec Assumptions §"Transcrições em PT-BR").
- SDK oficial tem histórico de breaking changes mais frequentes que OpenAI SDK.

### B. Azure AI Speech (STT)

**Prós**:
- Integração nativa com Azure AD (caso prosauai vá para Azure no futuro).
- Custom speech models por tenant possível.

**Rejeitada por**:
- Tooling assíncrono em Python (``azure-cognitiveservices-speech``) é pior que OpenAI SDK.
- Nenhum dos 2 tenants ativos tem vínculo com Azure.
- Configuração de região força decisão de data residency — fora de escopo v1.

### C. Google Cloud Speech-to-Text (STT)

**Prós**:
- PT-BR de alta qualidade (uso em Google Assistant).
- Word-level timestamps detalhados.

**Rejeitada por**:
- Auth via service account JSON (pior UX que API key OpenAI).
- Custo mais alto para áudio curto sem *pre-commit pricing*.

### D. OpenAI ``gpt-4o-mini-transcribe`` (endpoint unificado)

**Prós**:
- API single-call (``responses.create`` com input áudio), mesma SDK do ``gpt-4o-mini``.
- Potencial redução de latência por evitar duas round-trips (STT + resposta).

**Rejeitada por** (mas reavaliável em epic 010):
- Ainda em **GA parcial** — sem SLA sobre latência em 2026-04.
- Transcript separado (retornável via ``response.text``) não é formatado como Whisper (sem ``verbose_json.segments``) — quebra nosso filtro de alucinação (FR-025) que depende de ``segments.avg_logprob``.
- Preço ainda não estabilizado (pricing 2026-04 é preview).

**Migration path**: quando estabilizar, trocar ``OpenAISTTProvider.transcribe`` para usar ``responses.create`` com ``input_audio`` — zero mudança em ``AudioProcessor``, cache, budget ou pipeline. É exatamente 1 arquivo (~60 LOC).

### E. Anthropic Claude Haiku 3.5 (vision only)

**Prós**:
- Qualidade de OCR em imagens muito próxima ou superior ao ``gpt-4o-mini`` em benchmarks comunitários 2025-Q4.
- Preço competitivo (USD 0.25 / 1M input tokens).

**Rejeitada por**:
- +1 vendor para cobrir apenas vision — STT fica em OpenAI, dobraria complexidade ops.
- SDK Anthropic para Python (``anthropic``) é bom mas requer sua própria instrumentação OTel.
- Latência p95 ligeiramente pior que gpt-4o-mini em 2026-04 (fonte: `ML Ops Weekly` comparative benchmark 2026-03) `[VALIDAR]`.

**Migration path**: swap ``OpenAIVisionProvider`` por ``AnthropicVisionProvider`` — 1 arquivo, ~80 LOC. Pricing table ganha linha nova.

### F. Self-hosted faster-whisper (GPU)

**Prós**:
- Custo marginal zero por minuto de áudio (só custo de hardware).
- Controle total sobre latência (sem rede pública).

**Rejeitada por**:
- Complexidade ops absurda para 2 tenants ativos: GPU instance sempre quente, modelo carregado em RAM, rolling deploys sem downtime, degradation quando GPU quebra.
- Não há equipe dedicada a ML ops em 2026-04.
- Conflita com ADR-011 (simplicidade pragmática).

**Reavaliável** quando volume >100k áudios/mês/tenant OU regulação obrigar data residency on-prem.

## Swap migration path (quando)

A ADR-032 define o ``ContentProcessor`` Protocol. Esta ADR-033 define as implementações concretas de ``STTProvider`` e ``VisionProvider``. **Trocar de provider não requer aprovar uma ADR nova** — apenas *registrar* a troca como decisão menor em ``decisions.md`` do epic ativo e anexar os benchmarks que justificaram.

### Quando trocar de STT

Critérios disparadores (qualquer 1 gatilha a investigação; 2+ justificam a troca):

1. **Custo mensal OpenAI STT excede USD 500/tenant/mês** em produção (kill criteria do plan.md).
2. **p95 áudio > 8s em produção por 14 dias consecutivos** apesar de cache ≥30% (SC-001 fail).
3. **Taxa de alucinação > 2% em amostra mensal** (SC-011) mesmo após tuning do ``hallucination_filter.py``.
4. **Incidente sustentado OpenAI > 4h** em que o circuit breaker ficou aberto e impactou >10% das mensagens — força considerar failover para 2º provider.

### Quando trocar de vision

1. **Imagens com texto (cardápio, nota) consistentemente erram** em ``detail="high"`` — considerar Claude Haiku ou Gemini 1.5 Flash.
2. **Rate limit OpenAI vision** bater o teto de organização → distribuição entre 2 providers vira obrigatória (arquitetura: multi-provider round-robin via ``ProcessorContext.providers``).
3. **Custo > USD 200/tenant/mês** puramente em vision.

### Mecânica de swap (1 dia de trabalho, sem mudança de schema)

1. Criar ``apps/api/prosauai/processors/providers/<newvendor>_stt.py`` implementando ``STTProvider``.
2. Adicionar linha em ``MODEL_PRICING`` (``pricing.py``) — ADR-029.
3. Trocar a instância em ``main.py`` (lifespan) de ``OpenAISTTProvider(...)`` para ``<NewVendor>STTProvider(...)``.
4. Atualizar ``tenants.yaml`` opcional (feature flag ``content_processing.audio.provider`` se convivemos com 2 providers durante rollout).
5. Registrar decisão em ``decisions.md`` com link para benchmark.
6. Deploy canário (1 tenant, 7 dias) antes de cutover global.

Nenhuma tabela Postgres muda. Nenhum processor muda. Nenhum teste de contrato muda (``AsyncMock`` continua mockando o Protocol, não o SDK).

## Consequências

### Positivas

- **Ops mínima em v1**: 1 secret (``OPENAI_API_KEY``), 1 billing dashboard, 1 SDK já instrumentado via httpx auto-instrumentation (epic 002).
- **Swap trivial documentado**: o caminho para trocar de provider cabe em 6 passos (acima), fecha em 1 dia, sem mudança de schema ou contrato.
- **Qualidade PT-BR out-of-box**: Whisper ``whisper-1`` e ``gpt-4o-mini`` vision são benchmarks fortes em PT-BR para a faixa de casos do WhatsApp (PTT curto, foto de produto, nota fiscal).
- **Testabilidade**: ``ProcessorContext.providers`` é injeção pura → ``AsyncMock`` testa sem bater rede em CI.
- **Pricing reutiliza ADR-029**: 2 linhas novas em ``MODEL_PRICING``, sem criar tabela nova.

### Negativas

- **Single-vendor risk**: uma interrupção prolongada da OpenAI (>4h) impacta tanto o gerador de conversa (já em produção via ADR-002) quanto os processors novos. Mitigação: circuit breaker por ``(tenant, provider)`` (FR-023) entrega fallback gracioso via marker (``[provider_unavailable]``) enquanto o operador decide failover manual.
- **Pricing lock-in**: aumentos de preço unilaterais da OpenAI impactam diretamente o P&L dos tenants. Mitigação: revisão trimestral de custo e os gatilhos acima.
- **``gpt-4o-mini-transcribe`` não adotado em v1**: potencial ganho de latência deixado na mesa até o endpoint estabilizar. Aceitável — rework é 1 arquivo quando chegar a hora.
- **``whisper-1`` é modelo legado**: OpenAI pode deprecar em favor do novo endpoint unificado. Mitigação: SDK suporta as duas chamadas; swap é 1 arquivo (``openai_stt.py``).

### Neutras

- **Performance**: OpenAI STT/vision latency é dominada por rede + inferência (~1.5s–3s), não pelo SDK. Overhead do nosso wrapper é negligível (~200µs).
- **OTel**: ``opentelemetry-instrumentation-httpx`` (já instalado) já captura chamadas ``api.openai.com`` com atributos ``http.url`` / ``http.status_code``. Emitimos span ``openai.whisper.create`` / ``openai.vision.responses.create`` manualmente (T106) para poder anotar ``processor.cost_usd`` e ``processor.prompt_version``.

## Kill criteria

Esta ADR é invalidada se:

1. **Custo mensal OpenAI STT+vision ultrapassa USD 500/tenant/mês** em benchmark real com volume de 10k+ mídias/tenant (plan.md kill criteria). Força migrar para provider alternativo OU self-hosted.
2. **Compliance / LGPD reviewer veta** OpenAI como processador de áudio de cliente (ex.: exigência de data residency BR). Força Azure (BR region) ou self-hosted.
3. **SDK OpenAI quebra compatibilidade** em upgrade major de forma a impossibilitar fix de <1 dia. Força pin de versão estrito + planning de swap.
4. **Incidente recorrente OpenAI** (>1 incidente/mês sustentado >1h por 3 meses consecutivos). Força arquitetura multi-provider com failover automático (scope de epic futuro).

## Links

- Contrato: [contracts/content-processor.md §2](../epics/009-channel-ingestion-and-content-processing/contracts/content-processor.md)
- Provider wrapper (STT): [apps/api/prosauai/processors/providers/openai_stt.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/processors/providers/openai_stt.py)
- Provider wrapper (vision): [apps/api/prosauai/processors/providers/openai_vision.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/processors/providers/openai_vision.py) (PR-B, US2)
- AudioProcessor: [apps/api/prosauai/processors/audio.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/processors/audio.py)
- Pricing table: [apps/api/prosauai/observability/pricing.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/observability/pricing.py) (ADR-029)
- Circuit breaker: [apps/api/prosauai/processors/breaker.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/processors/breaker.py)
- SC-001 / SC-002 (performance gates): [spec.md](../epics/009-channel-ingestion-and-content-processing/spec.md)
- Decisão original (D6): [decisions.md](../epics/009-channel-ingestion-and-content-processing/decisions.md)
