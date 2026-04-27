---
title: 'ADR-037: HelpdeskAdapter pattern (bidirectional multi-helpdesk integration)'
status: Accepted
decision: >-
  Every helpdesk integration (Chatwoot, NoneAdapter, future Blip/Zendesk)
  implements the ``HelpdeskAdapter`` ``@runtime_checkable`` Protocol defined in
  ``prosauai.handoff.base``. Adapters are registered via a module-level registry
  (``prosauai.handoff.registry``) at application startup and dispatched by
  ``helpdesk.type`` from ``tenants.yaml``. The Protocol exposes **5 methods**
  (vs. the 2-method shape of ADR-031's ChannelAdapter) because the helpdesk
  integration is bidirectional: inbound webhook parsing (3 methods) plus
  outbound messaging (2 methods).
alternatives: ABC inheritance; per-helpdesk FastAPI sub-apps; state-machine
  per-adapter; a single generic "helpdesk client" with feature-flags; adapter
  merging with ChannelAdapter (ADR-031)
rationale: Protocol + runtime_checkable mirrors ADR-031 (ChannelAdapter) and
  keeps adapters duck-typed, testable with lightweight stubs, and conformance-
  checked at test time via ``isinstance``. The 5-method shape is the minimal
  surface needed to cover the full contract — any merger with ChannelAdapter
  would mix inbound-channel semantics with helpdesk-side-effect semantics, which
  are orthogonal concerns. NoneAdapter as null-object ensures tenants without a
  real helpdesk share the same code-path with a safe default.
---

# ADR-037: `HelpdeskAdapter` pattern (bidirectional multi-helpdesk integration)

**Status:** Accepted | **Data:** 2026-04-23 | **Relaciona:** [ADR-031](ADR-031-multi-source-channel-adapter.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md), [ADR-036](ADR-036-ai-active-unified-mute-state.md), [ADR-027](ADR-027-admin-tables-no-rls.md)

> **Escopo:** Epic 010 (Handoff Engine + Multi-Helpdesk). Formaliza o padrão arquitetural para integrar o prosauai com helpdesks externos (Chatwoot v1, NoneAdapter, e futuros Blip/Zendesk/Freshdesk). Complementa o [ADR-031](ADR-031-multi-source-channel-adapter.md) que faz o mesmo para canais de entrada.

## Contexto

O epic 010 introduz dois lados de integração com helpdesks:

1. **Inbound** — o helpdesk notifica o prosauai via webhook (e.g. Chatwoot sinaliza que um atendente assumiu a conversa → bot deve silenciar).
2. **Outbound** — o painel admin do prosauai envia mensagens ao helpdesk (e.g. Pace ops usa o composer de emergência para falar com o cliente via Chatwoot).

Sem uma abstração formal, cada helpdesk novo tenderia a crescer assim:
- Handler do webhook com `if helpdesk_type == "chatwoot": ... elif helpdesk_type == "blip": ...`
- Endpoint de reply com 3 caminhos condicionais
- Fixtures de teste duplicadas
- Nenhuma proteção contra drift de contrato quando Chatwoot muda o formato de payload

O [ADR-031](ADR-031-multi-source-channel-adapter.md) (epic 009) provou o valor do Protocol + registry para canais de **entrada**. O epic 010 aplica o mesmo padrão para a camada de **helpdesk**, com a diferença de que o contrato agora é bidirecional (inbound + outbound).

### Tensão: 5 métodos vs. 2 métodos (ChannelAdapter)

O `ChannelAdapter` do ADR-031 expõe apenas 2 métodos (`verify_webhook` + `normalize`). Um shape mais compacto foi considerado para `HelpdeskAdapter`, mas a bidirecionalidade torna isso impraticável:

| Direção | Métodos necessários |
|---------|---------------------|
| Inbound | `verify_webhook_signature`, `parse_webhook_event`, `on_conversation_assigned`, `on_conversation_resolved` |
| Outbound | `push_private_note`, `send_operator_reply` |

Colapsar em 2 métodos forçaria callbacks genéricos com dispatch interno — equivalente a re-implementar o Protocol como uma máquina de estados interna ao adapter, sem ganho real de simplicidade.

## Decisão

We will formalizar o **`HelpdeskAdapter` Protocol** em `prosauai.handoff.base`:

```python
@runtime_checkable
class HelpdeskAdapter(Protocol):
    helpdesk_type: str

    # Inbound
    async def verify_webhook_signature(self, request: Request, secret: str) -> None: ...
    async def parse_webhook_event(self, payload: dict) -> HelpdeskWebhookEvent: ...
    async def on_conversation_assigned(self, tenant_id, external_conversation_id, assignee_id, metadata) -> None: ...
    async def on_conversation_resolved(self, tenant_id, external_conversation_id, metadata) -> None: ...

    # Outbound
    async def push_private_note(self, tenant_id, external_conversation_id, text) -> None: ...
    async def send_operator_reply(self, tenant_id, external_conversation_id, text, sender_name) -> OperatorReplyResult: ...
```

A decisão se decompõe em 5 partes:

### 1. Protocol + `@runtime_checkable`

`HelpdeskAdapter` usa `@runtime_checkable` para que contract tests possam verificar conformance via `isinstance(adapter, HelpdeskAdapter)`. Isso é idêntico ao ADR-031 e garante que:
- Novos adapters sem `helpdesk_type` falham no contract test antes do PR merge.
- Stubs de test não precisam herdar de nenhuma base — duck-typing puro.

### 2. Hierarquia de erros

```
HelpdeskAdapterError        ← base
├── InvalidPayloadError     ← payload malformado → HTTP 200 OK + log (evita retry storm)
├── AuthError               ← HMAC inválido → HTTP 401
├── HelpdeskNotConfigured   ← NoneAdapter.send_reply() → HTTP 409
├── HelpdeskAPIError        ← falha HTTP outbound → circuit breaker
└── UnknownHelpdesk         ← registry.get_adapter() miss → HTTP 500 (bug de config)
```

A separação de `InvalidPayloadError` (→ 200 OK) e `AuthError` (→ 401) é intencional: payloads desconhecidos de um helpdesk legítimo não devem causar retry-storm, mas payloads sem assinatura HMAC são sinais de ataque.

### 3. Registry (mesmo padrão ADR-031)

```python
# prosauai/handoff/registry.py
_REGISTRY: dict[str, HelpdeskAdapter] = {}

def register(adapter: HelpdeskAdapter) -> None: ...
def get_adapter(helpdesk_type: str) -> HelpdeskAdapter: ...
def registered_helpdesks() -> list[str]: ...
def _clear_for_tests() -> None: ...
```

Bootstrap em `main.py`:

```python
from prosauai.handoff.chatwoot import ChatwootAdapter
from prosauai.handoff.none import NoneAdapter
from prosauai.handoff import registry as helpdesk_registry

helpdesk_registry.register(ChatwootAdapter(get_helpdesk_config=...))
helpdesk_registry.register(NoneAdapter())
```

Registry armazena **uma instância por `helpdesk_type`**. Adapters são stateless (ou carregam apenas config imutável injetada no construtor), logo uma instância por tipo é thread-safe.

### 4. `NoneAdapter` como null-object

Tenants com `helpdesk.type: none` usam `NoneAdapter`. Isso garante que:
- O código do webhook handler e do pipeline **nunca verifica `if helpdesk_type == "none"`** — ele chama os métodos do adapter e eles se comportam de forma segura.
- `push_private_note` → no-op silencioso (log `noneadapter_push_skip`).
- `send_operator_reply` → `HelpdeskNotConfigured` → HTTP 409.
- `verify_webhook_signature` / `parse_webhook_event` → `HelpdeskNotConfigured` (o endpoint `/webhook/helpdesk/{tenant_slug}` só é registrado quando `helpdesk.type != "none"`).

### 5. Invariantes de implementação (regras dos adapters)

Todo adapter que implementar `HelpdeskAdapter`:

1. **NÃO** acessa PostgreSQL diretamente — transições de estado vão por `handoff.state.mute_conversation` / `resume_conversation`.
2. **NÃO** muta estado global.
3. **NÃO** emite spans OTel — o handler/pipeline emite.
4. **Chamadas HTTP outbound** ao helpdesk são os ÚNICOS efeitos colaterais permitidos.
5. **É idempotente** para webhooks inbound: mesmo payload → mesma ação (dedup via Redis SETNX no handler, antes de chamar o adapter).
6. **NoneAdapter** — todos os métodos outbound são no-ops ou `HelpdeskNotConfigured`.

Essas regras são validadas por:
- **Contract tests** em `tests/contract/test_helpdesk_adapter_contract.py` (T021-T022): verificam `isinstance` + existência de cada método em `ChatwootAdapter` e `NoneAdapter`.
- **Code review** obrigatório em PRs que tocam `handoff/*.py`.

## Alternativas consideradas

### A. Abstract Base Class (ABC) com herança

```python
from abc import ABC, abstractmethod

class HelpdeskAdapter(ABC):
    helpdesk_type: str

    @abstractmethod
    async def verify_webhook_signature(self, ...): ...
```

**Rejeitada por**:
- Força herança onde duck-typing basta. Protocol é mais idiomático em Python 3.12.
- Stubs de test precisariam herdar, tornando-os mais verbosos.
- `isinstance(stub, HelpdeskAdapter)` funciona em ambos; Protocol é mais leve.
- ADR-031 já estabeleceu o padrão Protocol — manter consistência tem valor intrínseco.

### B. Integração merged com `ChannelAdapter` (ADR-031)

Estender o `ChannelAdapter` com métodos outbound, unificando canais e helpdesks em um único Protocol.

**Rejeitada por**:
- **Semânticas ortogonais**: `ChannelAdapter` traduz payloads de **entrada** (Evolution, Meta Cloud) para `CanonicalInboundMessage`. `HelpdeskAdapter` integra com helpdesks externos (outbound + inbound webhook). Misturar as duas semânticas em um único Protocol viola o Single Responsibility Principle.
- `EvolutionAdapter` não tem `send_operator_reply` — adicioná-lo criaria 1 método no-op obrigatório em um adapter que não deveria saber de helpdesks.
- Regression gate SC-013 (ADR-031) exige diff zero em `pipeline/processors/router` ao adicionar novos canais. Um adapter merged quebraria esse gate ao adicionar métodos helpdesk ao `ChannelAdapter`.

### C. Per-helpdesk FastAPI sub-apps

Montar uma sub-app Starlette por helpdesk em `main.py` via `app.mount(...)`.

**Rejeitada por**:
- Middleware compartilhado (auth, OTel tracing, circuit breaker) ficaria em duas árvores.
- Tests precisariam subir N apps.
- O registry approach é O(1) lookup e zero overhead operacional.

### D. Adapter genérico com feature-flags

Um único `GenericHelpdeskAdapter` com `if self.config.type == "chatwoot": ...` interno.

**Rejeitada por**:
- Anula o benefício de isolamento: um bug no caminho Chatwoot pode vazar para o NoneAdapter path.
- Novos helpdesks em epic 010.1 exigiriam editar o adapter existente (OCP violation).
- Impossibilita tests paramétricos por adapter.

### E. State machine por adapter

Cada adapter carrega uma máquina de estados interna para orchestrar mute/resume.

**Rejeitada por**:
- Estado de mute é responsabilidade de `handoff/state.py` + `conversations.ai_active` (ADR-036). Adapters são side-effect executors, não orchestrators.
- Duplicaria a lógica de advisory lock em cada adapter.

## Consequências

### Positivas

- **Novos helpdesks em epic 010.1 são quase triviais**: implementar 6 métodos + 1 arquivo + 1 fixture real capturada + 1 registro no lifespan. Zero toque no `state.py` / `pipeline.py` / `router`.
- **Contract test é gate automático**: `isinstance(adapter, HelpdeskAdapter)` em `tests/contract/test_helpdesk_adapter_contract.py` roda em todo PR. Adapters incompletos falham antes do merge.
- **NoneAdapter garante onboarding zero-friction**: tenant sem helpdesk usa o mesmo código-path com comportamento seguro por padrão.
- **Hierarquia de erros clara**: cada falha mapeia para um HTTP status bem-definido. O circuit breaker incrementa somente em `HelpdeskAPIError` — não em `AuthError` ou `InvalidPayloadError`.
- **Debug linear**: `webhook_handler → adapter.verify → adapter.parse → state.mute` — sem inversões de controle.

### Negativas / Trade-offs

- **5 métodos vs. 2 do ADR-031**: maior superfície de contrato. Justificada pela bidirecionalidade necessária (inbound + outbound).
- **Regras de invariante são disciplina social** até lint rule customizado (a adicionar pós-PR-B). Risco de adapter futuro "dar um quick access no DB" — mitigado por code review obrigatório em `handoff/`.
- **Registry é estado global** (dict em módulo). Cuidado em testes paralelos. Mitigação: fixture `_clear_for_tests()` + snapshot/restore pattern (já em uso no contract test).
- **Adapter é singleton stateless por tipo**: se um helpdesk futuro precisar de credential refresh periódico (e.g. OAuth2 token), o lifecycle de refresh precisará ser externalizado (ver Kill criteria §3).

### Neutras

- **Performance**: `registry.get_adapter(type)` = 1 dict lookup (~50ns). Invisível no p95.
- **Scale**: registry cresce O(N_helpdesks); esperamos ≤5 helpdesks no horizonte de 2 anos.

## Kill criteria

Esta ADR é invalidada se:

1. **Um novo helpdesk (epic 010.1+) precisar tocar `handoff/state.py`, `pipeline.py` ou `core/router/`** para acomodar sua lógica específica → redesign do Protocol antes do merge (analogia ao SC-013 do ADR-031).
2. **O Protocol precisar de métodos síncronos** (e.g. adapter que usa um SDK síncrono de terceiro) → avaliar `asyncio.to_thread` wrapper vs. reabrir este ADR.
3. **Credential refresh periódico for necessário** (OAuth2 token helpdesk com TTL < 1h) → estender o Protocol com `async def refresh_credentials()` e lifespan background task.

## Links

| Arquivo | Descrição |
|---------|-----------|
| `apps/api/prosauai/handoff/base.py` | Definição do Protocol + hierarquia de erros + value objects |
| `apps/api/prosauai/handoff/registry.py` | Registry module-level |
| `apps/api/prosauai/handoff/chatwoot.py` | ChatwootAdapter (PR-A shell, PR-C completo) |
| `apps/api/prosauai/handoff/none.py` | NoneAdapter (null-object) |
| `apps/api/tests/contract/test_helpdesk_adapter_contract.py` | Contract tests (isinstance + method existence) |
| `epics/010-handoff-engine-inbox/contracts/helpdesk-adapter.md` | Contrato detalhado com behaviors por método |

---
handoff:
  from: speckit.implement
  to: speckit.implement
  context: "ADR-037 documenta o HelpdeskAdapter Protocol pattern (5 métodos,
    registry, NoneAdapter null-object, hierarquia de erros). Espelha ADR-031
    com bidirecionalidade adicional. Próximas tasks: T120 benchmark gate PR-A,
    T130-T131 merge gates."
  blockers: []
  confidence: Alta
  kill_criteria: "Se novo helpdesk em epic 010.1 precisar tocar state.py ou
    pipeline.py para funcionar, reabrir este ADR antes do merge."
