---
title: 'ADR-030: Canonical inbound message model (source-agnostic pipeline entry point)'
status: Accepted
decision: Replace the Evolution-specific ``InboundMessage`` with a frozen,
  source-agnostic ``CanonicalInboundMessage`` (Pydantic v2) composed of
  ``SenderRef``, ``ConversationRef`` and a list of attribute-flattened
  ``ContentBlock`` entries discriminated by ``ContentKind``. Every inbound
  channel adapter (EvolutionAdapter at PR-A, MetaCloudAdapter at PR-C)
  produces this shape; the pipeline (debounce → router → generator →
  processors) consumes only this shape.
alternatives: Keep InboundMessage Evolution-coupled and add
  media_type/media_url optional fields; Pydantic discriminated union with
  one class per ContentKind (AudioContent, ImageContent, …); dataclasses
  (no validation) for minimum overhead; protobuf/msgpack binary schema for
  multi-service reuse.
rationale: Canonical model is a pure Pydantic object — no runtime
  dependencies, no network hop, no schema registry. Attribute flattening
  keeps (de)serialization ergonomic for the Redis debounce buffer and for
  Trace Explorer snapshots. ``frozen=True`` prevents accidental mutation
  downstream. Discriminator-by-kind + conditional validators cover the v1
  domain without paying the discriminated-union complexity tax.
---

# ADR-030: Canonical inbound message model (source-agnostic pipeline entry point)

**Status:** Accepted | **Data:** 2026-04-19 | **Supersede:** — | **Relaciona:** [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md), [ADR-031](ADR-031-multi-source-channel-adapter.md), [ADR-032](ADR-032-content-processing-strategy.md)

> **Escopo:** Epic 009 (Channel Ingestion + Content Processing). Esta ADR formaliza o *shape* único que todo pipeline a partir do PR-A consome — ``CanonicalInboundMessage`` — e substitui o antigo ``core.InboundMessage`` que carregava estrutura Evolution-first.

## Contexto

Até o epic 008 inclusive, o pipeline do prosauai recebia instâncias de ``prosauai.core.formatter.InboundMessage`` — um dataclass com campos como ``jid``, ``push_name``, ``media_type``, ``media_url`` e métodos ``parse_evolution_message`` que assumiam shape Evolution v2.3.0 na origem. O design atendeu bem ao MVP (epics 001–005), mas acumulou duas dívidas estruturais evidentes:

1. **Acoplamento cross-provider**: qualquer canal novo (Meta Cloud API, Telegram, Instagram, …) exigiria campos opcionais no mesmo dataclass ou uma cadeia de ``if/else`` nos 12 steps do pipeline. A primeira tentativa de integrar Meta Cloud em spike interno (2026-04-10) produziu PR com 11 arquivos tocados só para adicionar um novo tipo de mensagem.
2. **Ausência de tipagem por conteúdo**: ``media_type: str`` (ex: ``"audio"``, ``"image"``, ``"location"``) era uma string livre. O router usava ``==`` e não havia como o pipeline, ao ver uma mensagem, derivar automaticamente *qual* processor aplicar — o epic 009 precisa plugar novos processors sem tocar o core.

O spec do epic 009 (US1..US7) pede que cada tipo de conteúdo (texto, áudio, imagem, documento, sticker, localização, contato, reação e "unsupported") seja tratado por um processor dedicado (ADR-032). O pipeline precisa carregar a lista de blocos de conteúdo com o tipo explícito, preservando o payload original para auditoria.

## Decisão

**Adotamos ``prosauai.channels.canonical.CanonicalInboundMessage`` como único ponto de entrada tipado do pipeline** a partir do PR-A do epic 009.

### Shape

```python
class CanonicalInboundMessage(BaseModel):
    source: str                                 # "evolution" | "meta_cloud" | ...
    source_instance: str                        # "ariel" | phone_number_id | ...
    external_message_id: str                    # id cru do provider
    idempotency_key: str                        # sha256(source:instance:id) em hex
    tenant_id: UUID
    sender: SenderRef
    conversation_ref: ConversationRef           # direct | group
    content: list[ContentBlock]                 # ≥1 item
    received_at: AwareDatetime
    raw_payload: dict                           # auditoria — pipeline não lê

    model_config = {"frozen": True}
```

Componentes:

* **``SenderRef``**: ``external_id``, ``display_name``, ``is_group_admin`` — sem dependência Evolution-shaped (LID/JID ficam dentro de ``external_id``).
* **``ConversationRef``**: ``external_id`` + ``kind: Literal["direct", "group"]`` + ``group_subject`` opcional. Substitui o par ``remoteJid`` / ``participant`` do Evolution.
* **``ContentBlock``**: campos **achatados** (``kind``, ``mime_type``, ``url``, ``data_base64``, ``caption``, ``duration_seconds``, ``latitude``, ``longitude``, ``reaction_emoji``, ``file_name``, ``size_bytes``, ``text``, …). Validator condicional (``_sub_type_only_for_unsupported``) garante consistência sem exigir discriminated union.
* **``ContentKind``** (``StrEnum``): ``TEXT | AUDIO | IMAGE | DOCUMENT | STICKER | LOCATION | CONTACT | REACTION | UNSUPPORTED``. Discriminador **semântico** (não Pydantic-runtime).

### Invariantes (aplicadas pelo adapter + validators)

1. ``idempotency_key == sha256(f"{source}:{source_instance}:{external_message_id}").hexdigest()`` — previne colisão cross-source (D11 em decisions.md).
2. ``content`` nunca vazio — adapters que recebem shape desconhecido emitem um ``ContentBlock(kind=UNSUPPORTED, sub_type=<provider_type>)``.
3. ``frozen=True`` — todo enriquecimento downstream (tenant resolve, agent_id) cria cópia via ``model_copy(update=...)``.
4. ``raw_payload`` preserva o webhook cru — pipeline nunca lê, apenas auditoria/trace_steps armazenam.

### Migração faseada (PR-A1 → PR-A3)

* **PR-A1**: adiciona ``canonical.py`` + ``ChannelAdapter`` Protocol + ``EvolutionAdapter.normalize()`` em paralelo com ``InboundMessage``/``parse_evolution_message``. Zero consumidor novo.
* **PR-A2**: ``ConversationRequest`` passa a carregar ``canonical_messages: list[CanonicalInboundMessage]`` (aditivo). Debounce ganha ``append_canonical()`` / ``flush_canonical()`` lado-a-lado com os antigos (T046). Shim ``request_compat.build_canonical_from_legacy`` converte buffers Redis in-flight durante o deploy.
* **PR-A3**: ``core.formatter.parse_evolution_message`` marcado ``DeprecationWarning``. 1 release depois (epic 010) removido definitivamente.

### Compat shim lifetime

``request_compat.build_canonical_from_legacy`` e ``parse_evolution_message`` vivem **exatamente 1 release** depois do merge do PR-A. Testes que importarem qualquer dos dois sobem ``DeprecationWarning``; no epic 010, rationale removido + deleção.

## Alternativas consideradas

### A. Manter ``InboundMessage`` + opcionais Evolution-first

Adicionar ``media_kind``, ``media_url``, ``media_caption`` ao dataclass atual.

**Rejeitada por**:
- Zero contenção: Meta Cloud, Telegram, Instagram exigiriam N campos opcionais novos, amplificando o débito.
- ``router/facts.py`` teria que crescer o mapping Evolution→kind sem mover a responsabilidade para o adapter.
- Persistência em ``trace_steps.input_jsonb`` continuaria sem tipagem por kind — dificulta queries admin por tipo de mídia.

### B. Pydantic discriminated union (uma classe por kind)

```python
class AudioContent(BaseModel):
    kind: Literal["audio"] = "audio"
    url: str
    duration_seconds: int
    ...
ContentBlock = Annotated[
    Union[TextContent, AudioContent, ImageContent, ...],
    Field(discriminator="kind"),
]
```

**Rejeitada por**:
- Aumenta significativamente o custo de (de)serialização no Redis debounce buffer (tag discriminator + extra type resolution) — benchmark interno mostrou +0.4ms p95 por mensagem com 5 blocks.
- Cada kind novo exige PR em ``canonical.py`` + em todos os adapters/processors — o epic 009 já introduz 9 kinds; a discriminated union amarraria o epic 010+ a mais complexidade.
- Flexibilidade real para campos por kind é **baixa**: ~90% dos campos se repetem (``mime_type``, ``url``, ``data_base64``). Achatamento com validator condicional (``_sub_type_only_for_unsupported``) cobre os contratos sem repetir atributos.

Migração futura para discriminated union **é aditiva** — não quebra nada: ADR pode ser revisitada no epic 012 se múltiplos processors ganharem lógica condicional pesada (veja data-model.md §9.2).

### C. Dataclasses sem Pydantic (só ``@dataclass``)

**Rejeitada por**:
- Perdemos validation runtime + JSON schema auto-gerado.
- Trace Explorer (epic 008) já depende de ``model_dump_json`` para armazenar snapshots em ``trace_steps``.
- O ganho de performance é marginal (~0.1ms p50) em comparação ao custo de reimplementar validators manualmente.

### D. Protobuf/msgpack binary schema

**Rejeitada por**:
- Requer schema registry externo e geração de código — entra em conflito com ADR-011 (stack mínima: stdlib + asyncpg + Pydantic).
- Debugging em Trace Explorer fica opaco (payload não é human-readable).
- Overhead desnecessário para um monolito de 1 linguagem (Python).

## Consequências

### Positivas

- **Zero acoplamento Evolution**: adicionar Meta Cloud no PR-C é *apenas* um novo adapter — ``pipeline.py``, ``core/router/``, ``processors/`` não mudam (SC-013).
- **Tipagem por kind**: ``router/facts.py::_derive_content_kind`` passa a casar em ``canonical.content[0].kind`` — pattern matching nativo (``match/case``).
- **Audit explícito**: ``raw_payload`` preservado; ``media_analyses.raw_response`` (ADR-032) pode guardar até 32KB sem truncar.
- **Testabilidade**: contract test único (``test_channel_adapter_contract.py``) varre TODAS as fixtures Evolution + Meta Cloud re-validando via ``model_validate``.
- **Frozen=True** elimina classes inteiras de bug (mutação acidental em enrichment downstream).

### Negativas

- **Migração custosa no PR-A**: 15+ arquivos tocados (webhooks, dispatch, debounce, conversation/request, router/facts). Mitigado via phased PR-A1..A3 + shim.
- **Duplicação temporária**: ``InboundMessage`` e ``CanonicalInboundMessage`` coexistem por 1 release. Logs/tests podem flagrar ``DeprecationWarning``.
- **Learning curve**: contribuintes acostumados com ``msg.media_type`` precisam aprender ``msg.content[0].kind``. Mitigado pelo README novo em ``channels/`` e pelo notebook ``quickstart.md``.

### Neutras

- **Performance**: overhead de validação Pydantic em ``CanonicalInboundMessage`` medido em 0.08ms p95 — bem dentro do budget SC-009 (+5ms).
- **Storage**: ``raw_payload`` é armazenado como parte do dict — não cria colunas novas em nenhuma tabela existente.

## Kill criteria

Esta ADR é invalidada se:

1. **Fixtures Evolution reais falharem ``model_validate`` em > 5% dos casos** — força relaxar o schema ou passar para discriminated union.
2. **``frozen=True`` causar falsos positivos de validation em enrichment downstream** (ex.: router tentando mutar ``sender.display_name``) que não possam ser corrigidos via ``model_copy``.
3. **Benchmark T051 regredir > +5ms p95** atribuível à (de)serialização do canonical — força rever o achatamento ou trocar de biblioteca.

## Links

- Implementação: [apps/api/prosauai/channels/canonical.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/channels/canonical.py)
- Fixtures canonicais: [apps/api/tests/fixtures/canonical/](https://github.com/paceautomations/prosauai/tree/develop/apps/api/tests/fixtures/canonical)
- Contract test: [apps/api/tests/contract/test_channel_adapter_contract.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/tests/contract/test_channel_adapter_contract.py)
- Data model detalhado: [epics/009-channel-ingestion-and-content-processing/data-model.md §2.1](../epics/009-channel-ingestion-and-content-processing/data-model.md)
- Alternativa B (discriminated union) detalhada: [data-model.md §9.2](../epics/009-channel-ingestion-and-content-processing/data-model.md)
