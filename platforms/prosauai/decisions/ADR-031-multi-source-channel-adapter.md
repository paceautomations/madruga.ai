---
title: 'ADR-031: Multi-source channel adapter pattern (pure translator + registry)'
status: Accepted
decision: Every inbound channel (Evolution v2.3.0, Meta Cloud API, and any
  future Telegram/Instagram adapter) implements the ``ChannelAdapter``
  Protocol defined in ``prosauai.channels.base``. Adapters are **pure
  translators** — they MUST NOT access PostgreSQL, Redis, LLM providers or
  emit OpenTelemetry spans. Registration is done via a module-level
  registry (``prosauai.channels.registry``) at application startup and
  looked up by ``source`` (path-derived) in the webhook handler layer.
alternatives: Abstract base class (ABC) with inheritance; FastAPI sub-apps
  per channel; generic Starlette middleware decoding payloads into
  kwargs; protobuf gateway service with gRPC.
rationale: Protocol + runtime_checkable keeps adapters duck-typed (testable
  with lightweight stubs) while still exposing a conformance contract.
  "Pure translator" rule isolates the pipeline from channel-specific
  side-effects and is the validation gate (SC-013) for PR-C — merging
  MetaCloudAdapter without touching pipeline.py / processors/ /
  core/router/ proves the abstraction holds.
---

# ADR-031: Multi-source channel adapter pattern (pure translator + registry)

**Status:** Accepted | **Data:** 2026-04-19 | **Supersede:** — | **Relaciona:** [ADR-030](ADR-030-canonical-inbound-message.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md), [ADR-032](ADR-032-content-processing-strategy.md)

> **Escopo:** Epic 009 (Channel Ingestion + Content Processing). Esta ADR formaliza o pattern arquitetural que permite plugar canais novos — WhatsApp via Evolution (PR-A), WhatsApp via Meta Cloud API (PR-C), e futuros Telegram/Instagram/Threads — sem tocar o pipeline central do prosauai.

## Contexto

Dois fatos convergem na entrada do epic 009:

1. **Epic 005 já provou o pipeline de IA**: 12 steps, MECE router, fire-and-forget trace persist (ADR-028). O caminho crítico é sensível a latência (SC-006 do epic 008 = overhead ≤10ms) e NÃO deve ficar conhecendo *de que canal veio* cada mensagem.
2. **O prosauai precisa de Meta Cloud como "canal 2"**. Motivos: (a) redundância quando Evolution cai, (b) uma conta do ResenhAI testando integração oficial WhatsApp Business Platform, (c) validar que o novo ``CanonicalInboundMessage`` (ADR-030) realmente é agnóstico — não uma abstração Evolution-em-roupagem-nova.

Sem uma disciplina formal, cada novo canal tende a crescer assim:
- ``webhooks.py`` com 5 branches (``if source == "evolution": ... elif "meta_cloud": ...``).
- ``DebounceManager.append`` aceitando ``text`` OU ``audio`` OU ``caption`` para não quebrar callers antigos.
- ``facts.py::_derive_content_kind`` com 40 linhas de ``isinstance`` / ``hasattr``.

A discussão interna (spec §Clarifications + [SC-013 do epic 009](../epics/009-channel-ingestion-and-content-processing/spec.md)) travou que a **validação arquitetural** do epic é justamente: *"merge do PR-C (MetaCloudAdapter) tem diff zero em ``pipeline.py`` / ``processors/`` / ``core/router/``"*.

## Decisão

Formalizamos o **ChannelAdapter Protocol** em ``prosauai.channels.base``:

```python
@runtime_checkable
class ChannelAdapter(Protocol):
    source: str               # "evolution" | "meta_cloud" | ...
    source_version: str       # "1.0.0" — visível em trace attributes

    async def verify_webhook(self, request: Request) -> None: ...
    async def normalize(
        self,
        payload: dict,
        source_instance: str,
    ) -> list[CanonicalInboundMessage]: ...
```

### Invariantes de implementação (regra dos "6 NOT")

Todo adapter que implementar ``ChannelAdapter``:

1. **NÃO** acessa PostgreSQL (nenhum import de ``asyncpg`` / ``db.*``).
2. **NÃO** acessa Redis (nenhum import de ``redis`` / ``debounce``).
3. **NÃO** chama LLM, STT, vision, TTS ou qualquer provider externo.
4. **NÃO** emite spans OpenTelemetry (o pipeline/handler emite).
5. **NÃO** muta estado global (registry é só leitura após startup).
6. **NÃO** tenta reparar payloads malformados — prefere ``InvalidPayloadError`` para forçar correção upstream.

Essas regras são validadas por:

- **Ruff lint rule custom** (a adicionar no PR-B) que falha se ``channels/**/*.py`` importar ``asyncpg``, ``redis``, ``openai``, ``opentelemetry.trace``.
- **Test de contrato** ``test_adapter_does_not_touch_db_or_providers`` (contracts/channel-adapter.md §4) que mocka DB/providers e assert 0 chamadas.

### Registry

```python
# prosauai/channels/registry.py — módulo único
_REGISTRY: dict[str, ChannelAdapter] = {}

def register(adapter: ChannelAdapter) -> None: ...
def get(source: str) -> ChannelAdapter: ...           # KeyError if missing
def registered_sources() -> list[str]: ...            # introspecção
def _clear_for_tests() -> None: ...                   # apenas tests
```

- **Bootstrap**: ``main.py`` (ou lifespan) chama ``register(EvolutionAdapter(tenant_store=...))``. PR-C adiciona ``register(MetaCloudAdapter(config=...))``.
- **Lookup**: ``webhooks/evolution.py`` faz ``channel_registry.get("evolution")`` — se não encontrar, instancia um ``EvolutionAdapter`` default (fallback p/ test harness).

### Webhook layering

Cada canal **tem seu próprio handler** em ``prosauai/api/webhooks/``:

```
prosauai/api/webhooks/
  ├── __init__.py            # alias /webhook/whatsapp/{instance} (retrocompat)
  ├── dispatch.py            # lógica comum: tenant resolve, auth, debounce
  ├── evolution.py           # POST /webhook/evolution/{instance_name}
  └── meta_cloud.py          # PR-C — GET/POST /webhook/meta_cloud/{tenant_slug}
```

Handler sequência:
1. Validate auth via FastAPI dependency (``resolve_tenant_and_authenticate`` ou HMAC Meta).
2. Resolve adapter via ``channel_registry.get(source)``.
3. Call ``adapter.verify_webhook(request)`` (no-op se auth já foi pelo FastAPI).
4. Parse body (``json.loads(raw_body)``).
5. ``messages = await adapter.normalize(payload, source_instance=path_param)``.
6. Forward list para ``dispatch.dispatch(messages, tenant)`` (comum a todos os canais).

## Alternativas consideradas

### A. Abstract Base Class (ABC) com herança

```python
from abc import ABC, abstractmethod

class ChannelAdapter(ABC):
    source: str
    @abstractmethod
    async def normalize(self, payload, source_instance) -> list[CanonicalInboundMessage]: ...
```

**Rejeitada por**:
- Força herança, enquanto Protocol permite qualquer objeto com shape compatível (útil para mocks e test stubs).
- Menos idiomático em Python 3.12 com ``@runtime_checkable``.
- Runtime check via ``isinstance(obj, ChannelAdapter)`` funciona em ambos; Protocol é mais leve.

### B. FastAPI sub-apps por canal

Montar um ``FastAPI`` filho por canal em ``main.py`` via ``app.mount("/webhook/evolution", evo_app)``.

**Rejeitada por**:
- Complicação de middleware compartilhado (auth, tracing, debounce) que passaria a viver em 2 árvores.
- Tests precisariam subir N apps ou reconfigurar transport a cada caso.
- Endpoints de alias (retrocompat ``/webhook/whatsapp/{instance}``) viram forwarders externos ao sub-app — quebra isolation.

### C. Starlette middleware genérico

Middleware intercepta ``/webhook/*`` e extrai ``source`` da URL, decodifica payload, injeta ``CanonicalInboundMessage`` como kwarg.

**Rejeitada por**:
- Auth é fundamentalmente diferente por canal (header ``X-Webhook-Secret`` constant-time vs. HMAC Meta vs. verify_token Meta). Um middleware genérico vira um pseudocódigo com branches tão feio quanto o que estamos evitando.
- Debug fica opaco — pipeline não mostra "entrou no EvolutionAdapter, deu X" em stack traces.

### D. Serviço gateway protobuf/gRPC

Rodar um binário Go dedicado que recebe webhooks, traduz para protobuf, e chama o prosauai via gRPC com ``CanonicalInboundMessage``.

**Rejeitada por**:
- Stack separada → 1 linguagem a mais, 1 deploy a mais, 1 observabilidade a mais.
- Overhead operacional enorme para 2 canais ativos.
- Conflita com ADR-011 (simplicidade pragmática).

## Consequências

### Positivas

- **PR-C é quase trivial**: MetaCloudAdapter implementa 2 métodos, 1 FastAPI handler (``webhooks/meta_cloud.py``), 1 registrador no lifespan, 4 fixtures. Zero toque no core.
- **Test de regressão arquitetural**: SC-013 gate (merge PR-C ⇒ diff zero em pipeline/processors/router) é uma prova automatizada que a abstração aguenta canais heterogêneos.
- **Onboarding de contribuintes**: "o que um adapter faz?" tem resposta única de 2 linhas.
- **Debug linear**: pilha de chamadas segue ``webhook_handler → adapter.normalize → dispatch → pipeline`` sem inversões de controle.
- **Shim de retrocompat simples**: ``/webhook/whatsapp/{instance}`` (legado) é apenas um forwarder HTTP → ``/webhook/evolution/{instance}`` (T042). Zero lógica duplicada.

### Negativas

- **Regra dos "6 NOT" é disciplina social** até o lint rule entrar em vigor. Risco de adapter futuro "só dar um quick check no Redis" — mitigado via code review obrigatório em PRs que toquem ``channels/``.
- **Registry é estado global** (módulo-level dict) — cuidado em testes paralelos. Mitigação: fixture ``_clear_for_tests()`` + snapshot/restore pattern já em uso nos contract tests.
- **Protocol não valida shape em build-time**: erro só surge em ``isinstance(adapter, ChannelAdapter)`` no test de contrato. Aceitável porque o test roda em todo PR.

### Neutras

- **Performance**: overhead de ``channel_registry.get(source)`` = 1 dict lookup (~50ns). Inivel.
- **Scale**: registry cresce O(N_canais); esperamos ≤5 canais no horizonte de 2 anos.

## Kill criteria

Esta ADR é invalidada se:

1. **PR-C precisar tocar ``pipeline.py``, ``processors/`` ou ``core/router/``** para acomodar Meta Cloud → força rearquitetar o Protocol antes do merge do PR-A (SC-013 fail).
2. **Adapter precisar de estado compartilhado cross-request** (ex.: session token Meta Cloud que expira a cada hora) → ADR precisa ser estendida para cobrir lifecycle de credential refresh.
3. **Registry virar gargalo em multi-tenant** (muito improvável: dict lookup é constant-time) — revisar pattern de lookup por tenant.

## Links

- Implementação base: [apps/api/prosauai/channels/base.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/channels/base.py)
- Registry: [apps/api/prosauai/channels/registry.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/channels/registry.py)
- EvolutionAdapter: [apps/api/prosauai/channels/inbound/evolution/adapter.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/channels/inbound/evolution/adapter.py)
- Contract test: [apps/api/tests/contract/test_channel_adapter_contract.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/tests/contract/test_channel_adapter_contract.py)
- Contrato detalhado: [epics/009-channel-ingestion-and-content-processing/contracts/channel-adapter.md](../epics/009-channel-ingestion-and-content-processing/contracts/channel-adapter.md)
- SC-013 (gate de validação arquitetural): [spec.md SC-013](../epics/009-channel-ingestion-and-content-processing/spec.md)
