---
id: "004"
title: "Router MECE — Classificacao pura + regras externalizadas + agent resolution"
status: shipped
phase: now
features:
  - "Router em duas camadas: classify() puro + RoutingEngine declarativo"
  - "Regras de roteamento externas (YAML per-tenant), zero deploy para mudanca"
  - "Agent resolution funcional (epic 001 deixou agent_id sempre None)"
  - "Garantias MECE provadas em 4 camadas (tipo, schema, runtime, CI)"
owner: ""
created: 2026-04-10
updated: 2026-04-10
target: ""
outcome: ""
arch:
  modules: [M3]
  contexts: [channel]
  containers: [prosauai-api]
delivered_at: 2026-04-11
---

# 004 — Router MECE

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | M3 (Smart Router) | [Containers (Interactive)](../../engineering/containers/) |
| Contextos | Channel | [Context Map](../../engineering/context-map/) |
| Containers | prosauai-api | [Containers (Interactive)](../../engineering/containers/) |

## Problema

O epic 001 entregou o `Smart Router` funcional; o epic 003 (shipado 2026-04-10) corrigiu parser + auth + multi-tenant, mas **manteve intocada** a estrutura do router. Restam tres dividas estruturais que bloqueiam evolucao:

1. **Nao-MECE por construcao.** O enum `MessageRoute` conflata tres eixos ortogonais: tipo de mensagem (individual/grupo), estado de conversa (handoff/normal) e acao (respond/log/drop). O resultado e que `SUPPORT`, `GROUP_RESPOND`, `GROUP_SAVE_ONLY`, `GROUP_EVENT`, `HANDOFF_ATIVO` e `IGNORE` nao sao mutuamente exclusivos conceitualmente — o nome `SUPPORT` ja decide que "individual → suporte" esta hardcoded. Nao ha como expressar "individual em handoff ativo" sem criar constante nova.

2. **Regras de negocio cimentadas em codigo.** O `route_message()` em [prosauai/core/router.py](../../../../../prosauai-worktrees/003-multi-tenant-foundation/prosauai/core/router.py) tem regras dentro de if/elif: "from_me primeiro", "reaction → IGNORE" (fix do 003), "individual vira SUPPORT", "grupo com mention vira GROUP_RESPOND". Trocar "individual → vendas" para "individual → onboarding" exige mudar enum, codigo e testes. Admin panel (epic 009) nao tem o que editar. Pior: `_is_bot_mentioned()` esta hardcoded no mesmo arquivo, misturando detecao de fact com logica de rota.

3. **`agent_id` sempre None.** O `RouteResult.agent_id` existe desde o dia 1 por decisao 10 do epic 001 ("evita breaking change futuro"), mas **nenhum lugar do codigo escreve valor nele** — 003 mergeou sem tocar nesse ponto. A "Fase B — Agent Resolution" do diagrama em `business/process.md` e ficcao — existe so no Mermaid, nao no Python. Quando o epic 005 (Conversation Core + LLM) for implementado, ele vai ter que inventar `agent_id` do nada ou hardcodar um default do tenant bypassando qualquer conceito de regra. **E o `Tenant` dataclass shipado pelo 003 nao tem nem o campo `default_agent_id`** — o domain-model promete, o codigo nao entregou.

O deep-dive que originou este epic esta registrado na conversa [2026-04-10 — Router MECE deep-dive]. O pedido do usuario foi literal: "regras que sao fato ficam no codigo; links entre fatos e agentes ficam fora do codigo, sempre MECE". O problema (3) torna este refactor **bloqueio duro** para qualquer epic que invoque LLM — sem ele, o epic 005 herda o bug.

## Valor de Negocio

- [ ] Classificacao de mensagem e MECE por construcao — provado em CI via enumeracao exaustiva dos fatos possiveis
- [ ] Mudar regras de roteamento sem deploy — editar `config/routing/<tenant>.yaml` (epic 004) ou row em `routing_rules` (epic 006)
- [ ] `agent_id` resolvido de verdade pelo router — epic 005 (Conversation Core) consome `Decision.agent_id` em vez de hardcodar default
- [ ] Observabilidade total no Phoenix: cada mensagem tem spans `router.classify` + `router.decide` com `matched_rule`, `action`, `agent_id` atribuidos (integra com epic 002)
- [ ] Admin panel (epic 009) ganha modelo de dados pronto — cada regra = 1 row editavel
- [ ] Closeout de drift documental: `InboundMessage` passa a ser o nome real no codigo (o domain-model ja usa esse nome)

## Solucao

Arquitetura em duas camadas, separando **fatos** de **regras**:

**Layer 1 — `classify()`**: funcao pura `(message, state, matchers) → MessageFacts`, 100% deterministica, sem I/O, sem config hardcoded. Consome `InboundMessage` (renomeado de `ParsedMessage` — o parser do 003 ja e o anti-corruption layer; reparsear dict seria duplicar o trabalho). `MessageFacts` e um dataclass frozen com campos ortogonais (enums + bool): `channel`, `event_kind`, `content_kind`, `from_me`, `has_mention`, `is_membership_event`, `is_duplicate`, `conversation_in_handoff`. Estado externo (`is_duplicate`, `conversation_in_handoff`) e pre-carregado pelo caller num `StateSnapshot` via `MGET` unico no Redis. **Matchers de mention** (que sao dados tenant-specific, nao estado) sao passados como `MentionMatchers` frozen — um value object construido uma vez por tenant no lifespan, reutilizado em todas as requests. Isso preserva a pureza (Bernhardt FCIS: "configuration values gathered in the shell and passed as parameters to pure functions"). Invariantes cross-field sao validadas em `__post_init__` (ex: `has_mention ⟹ channel == GROUP`), impedindo a construcao de fatos impossiveis.

**Layer 2 — `RoutingEngine.decide(facts, tenant_ctx)`**: avalia rules ordenadas por `priority ASC`, primeira cujo `when` casa ganha. Se nenhuma casa, usa `default` (obrigatorio no schema). Para `action == RESPOND`, resolve `agent_id` a partir da regra ou cai em `tenant_ctx.default_agent_id` (novo campo aditivo no `Tenant` do 003). Retorna um `Decision` que e uma **discriminated union pydantic** de 5 subtipos (`RespondDecision`, `LogOnlyDecision`, `DropDecision`, `BypassAIDecision`, `EventHookDecision`) — cada subtipo carrega apenas os campos validos para aquela acao, eliminando estados invalidos em compile-time.

**Config externa**: `config/routing/<tenant-slug>.yaml`, um arquivo por tenant. Nomes reais: `config/routing/ariel.yaml` + `config/routing/resenhai.yaml` — alinhados com os tenants reais do 003 (`pace-internal` / `resenha-internal`). Loader pydantic valida schema, rejeita campos desconhecidos, exige `default` obrigatorio. Admin panel (epic 009) edita o mesmo schema. Epic 006 (originalmente "Configurable Routing DB") passa a ser trivial — so troca o loader de YAML para tabela `routing_rules`.

**Observabilidade (integra com epic 002)**: em vez de 1 span `route_message`, o router emite 2 spans irmaos sob o `webhook_whatsapp` pai:
- `router.classify`: atributos `prosauai.is_group`, `prosauai.from_me`, `prosauai.is_reaction`, `prosauai.media_type`, `prosauai.group_id`
- `router.decide`: atributos `prosauai.matched_rule`, `prosauai.action`, `prosauai.route`, `prosauai.agent_id` (em RESPOND), `prosauai.drop_reason` (em DROP), `prosauai.event_target` (em EVENT_HOOK)

Sao 6 novas constantes em `prosauai/observability/conventions.py` (namespace flat `prosauai.*` seguindo o padrao do 002). Phoenix ganha waterfall correto mostrando classify + decide como etapas distintas — pre-aprovado pelo reconcile do 002.

**Garantias MECE em 4 camadas**:

1. **Tipo (Layer 1)**: dominio fechado via enums, invariantes validadas em construcao. Espaco de predicados possiveis e finito (~400 combinacoes validas).
2. **Schema (load-time)**: pydantic rejeita config sem `default`, rejeita `priority` duplicado, rejeita `action` invalida. **Overlap analysis pairwise**: para cada par de regras, loader verifica se existe algum `MessageFacts` que casa com ambas; se sim, **ERROR** (hit policy `UNIQUE` do DMN). Zero escape hatch — se overlap existe, a config nao sobe.
3. **Runtime**: `match/case` sobre discriminated union garante que consumer trata os 5 subtipos; mypy/pyright prova exaustividade.
4. **CI (property-based)**: teste exaustivo enumera todos os `MessageFacts` validos do produto cartesiano dos enums e verifica `len(matches) == 1` para cada um. Complementado por Hypothesis para campos livres (`instance`, `sender_phone`). Teste separado de alcancabilidade verifica que toda regra com `instance` especifico e realmente alcancavel por algum fato.

**CLI de DX**: `prosauai router verify config/routing/<tenant>.yaml` roda todas as validacoes localmente (hook pre-commit + CI). `prosauai router explain --tenant X --facts '{...}'` responde "qual regra casaria este fato e por que?".

### Interfaces / Contratos

```python
# prosauai/core/router/facts.py
class Channel(StrEnum):
    INDIVIDUAL = "individual"
    GROUP = "group"

class EventKind(StrEnum):
    MESSAGE = "message"
    GROUP_MEMBERSHIP = "group_membership"
    GROUP_METADATA = "group_metadata"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"

class ContentKind(StrEnum):
    TEXT = "text"
    MEDIA = "media"
    STRUCTURED = "structured"
    REACTION = "reaction"
    EMPTY = "empty"

@dataclass(frozen=True, slots=True)
class MessageFacts:
    # Identidade
    instance: str
    event_kind: EventKind
    content_kind: ContentKind
    # Topologia
    channel: Channel
    from_me: bool
    sender_phone: str | None
    sender_lid_opaque: str | None
    group_id: str | None
    # Conteudo
    has_mention: bool
    is_membership_event: bool
    # Estado (pre-carregado pelo caller)
    is_duplicate: bool
    conversation_in_handoff: bool

    def __post_init__(self) -> None:
        if self.channel == Channel.GROUP and self.group_id is None:
            raise ValueError("GROUP channel requires group_id")
        if self.has_mention and self.channel != Channel.GROUP:
            raise ValueError("has_mention only valid in GROUP channel")
        if self.is_membership_event and self.event_kind != EventKind.GROUP_MEMBERSHIP:
            raise ValueError("is_membership_event requires GROUP_MEMBERSHIP event_kind")

@dataclass(frozen=True, slots=True)
class StateSnapshot:
    is_duplicate: bool
    conversation_in_handoff: bool

    @classmethod
    async def load(cls, redis, tenant_id: str, message_id: str, sender_key: str) -> "StateSnapshot":
        # Reads idempotency key (written by epic 003 check_and_mark_seen) + handoff key
        # (written by epic 005/011 — contract aberto documentado).
        dup, handoff = await redis.mget(
            f"seen:{tenant_id}:{message_id}",
            f"handoff:{tenant_id}:{sender_key}",
        )
        return cls(is_duplicate=bool(dup), conversation_in_handoff=bool(handoff))


# prosauai/core/router/matchers.py — tenant-aware mention detection as data
@dataclass(frozen=True, slots=True)
class MentionMatchers:
    """Frozen value object derived from Tenant once at lifespan startup.

    Encapsulates the 3 mention-detection strategies shipped in epic 003
    (LID JID, phone JID, keyword substring) as immutable data — not as
    injected behaviour. Building this at startup and passing it into
    classify() as a third parameter keeps classify() pure (Bernhardt
    FCIS: configuration values are gathered in the shell).
    """

    lid_opaque: str | None
    phone: str | None
    keywords: tuple[str, ...]

    @classmethod
    def from_tenant(cls, tenant: Tenant) -> "MentionMatchers":
        return cls(
            lid_opaque=tenant.mention_lid_opaque or None,
            phone=tenant.mention_phone or None,
            keywords=tenant.mention_keywords,
        )

    def matches(self, message: InboundMessage) -> bool:
        if self.lid_opaque and f"{self.lid_opaque}@lid" in message.mentioned_jids:
            return True
        if self.phone and f"{self.phone}@s.whatsapp.net" in message.mentioned_jids:
            return True
        text = (message.text or "").lower()
        return any(kw.lower() in text for kw in self.keywords)


def classify(
    message: InboundMessage,
    state: StateSnapshot,
    matchers: MentionMatchers,
) -> MessageFacts:
    """Pure function — no I/O, no globals, deterministic."""
    ...


# prosauai/core/router/engine.py
class Action(StrEnum):
    RESPOND = "respond"
    LOG_ONLY = "log_only"
    DROP = "drop"
    BYPASS_AI = "bypass_ai"
    EVENT_HOOK = "event_hook"

class RespondDecision(BaseModel):
    action: Literal[Action.RESPOND] = Action.RESPOND
    agent_id: UUID
    matched_rule: str
    reason: str | None = None

class LogOnlyDecision(BaseModel):
    action: Literal[Action.LOG_ONLY] = Action.LOG_ONLY
    matched_rule: str
    reason: str | None = None

class DropDecision(BaseModel):
    action: Literal[Action.DROP] = Action.DROP
    matched_rule: str
    reason: str

class BypassAIDecision(BaseModel):
    action: Literal[Action.BYPASS_AI] = Action.BYPASS_AI
    target: Literal["m12_handoff"]
    matched_rule: str
    reason: str | None = None

class EventHookDecision(BaseModel):
    action: Literal[Action.EVENT_HOOK] = Action.EVENT_HOOK
    target: Literal["group_membership_handler"]
    matched_rule: str
    reason: str | None = None

Decision = Annotated[
    Union[RespondDecision, LogOnlyDecision, DropDecision, BypassAIDecision, EventHookDecision],
    Field(discriminator="action"),
]

@dataclass(frozen=True)
class Rule:
    name: str
    priority: int
    when: dict[str, Any]
    action: Action
    agent: UUID | None = None
    target: str | None = None
    reason: str | None = None

    def matches(self, facts: MessageFacts) -> bool: ...

@dataclass(frozen=True)
class RoutingEngine:
    rules: tuple[Rule, ...]
    default: Rule

    def decide(self, facts: MessageFacts, tenant_ctx: Tenant) -> Decision: ...


# prosauai/core/router/__init__.py — public API
async def route(
    message: InboundMessage,
    redis,
    engine: RoutingEngine,
    matchers: MentionMatchers,
    tenant: Tenant,
) -> Decision:
    state = await StateSnapshot.load(redis, tenant.id, message.message_id, message.sender_key)
    facts = classify(message, state, matchers)
    return engine.decide(facts, tenant)
```

### Schema YAML de routing — `config/routing/ariel.yaml`

```yaml
version: 1
tenant: pace-internal

rules:
  # Guards universais (priority 0-9)
  - name: drop_self_echo
    priority: 0
    when: { from_me: true }
    action: DROP
    reason: from_me_loop_guard

  - name: drop_duplicate
    priority: 1
    when: { is_duplicate: true }
    action: DROP
    reason: idempotency

  - name: drop_reaction
    priority: 2
    when: { content_kind: reaction }
    action: DROP
    reason: reaction_ambient_signal

  - name: handoff_bypass
    priority: 5
    when: { conversation_in_handoff: true }
    action: BYPASS_AI
    target: m12_handoff

  # Eventos de grupo (priority 10-19)
  - name: group_membership
    priority: 10
    when: { is_membership_event: true }
    action: EVENT_HOOK
    target: group_membership_handler

  # Rotas por canal (priority 100+)
  - name: individual_support
    priority: 100
    when:
      channel: individual
    action: RESPOND
    # agent omitido → usa tenant.default_agent_id

  - name: group_mention_support
    priority: 110
    when:
      channel: group
      has_mention: true
    action: RESPOND
    # agent omitido → usa tenant.default_agent_id

  - name: group_silent_log
    priority: 120
    when:
      channel: group
      has_mention: false
    action: LOG_ONLY

default:
  action: RESPOND
  reason: no_rule_matched_fallback_to_default
```

Para ResenhAI (`config/routing/resenhai.yaml`) a estrutura e identica mas com priorities distintas enfatizando grupos (community-first): `group_mention_support` priority 90, `group_silent_log` e obrigatorio, `individual_support` priority 100. Ambos tenants referenciam `tenant.default_agent_id` — o YAML nao carrega UUID hardcoded.

### Scope

**Dentro:**

- Rename `ParsedMessage` → `InboundMessage` (alinha com `domain-model.md:40-53`); arquivo `formatter.py` pode virar `inbound.py` no mesmo PR
- Novo campo `default_agent_id: UUID | None = None` em `Tenant` (aditivo, backward-compatible) + update em `tenant_store.py:_build_tenant` + `tenants.example.yaml`
- Layer 1: `classify()` puro + `MessageFacts` com invariantes
- Layer 1': `MentionMatchers` frozen value object em `prosauai/core/router/matchers.py`
- Layer 2: `RoutingEngine` + `Rule` + 5 subtipos de `Decision` (discriminated union)
- Loader YAML pydantic (schema validation + overlap analysis + default obrigatorio)
- CLI `prosauai router verify|explain`
- Property tests exaustivos (enumeracao + Hypothesis) + teste de alcancabilidade por `instance`
- Migracao do `webhooks.py` atual para usar novo `route()` assincrono + `Decision` discriminated union
- Deprecacao do enum `MessageRoute` legado (removido no mesmo PR — rip-and-replace)
- Remocao de `_is_bot_mentioned`, `_is_handoff_ativo`, `route_message` de `router.py` (logica migra para classify + engine + MentionMatchers)
- 6 novas constantes em `prosauai/observability/conventions.py` (MATCHED_RULE, ROUTING_ACTION, DROP_REASON, EVENT_HOOK_TARGET, MESSAGE_IS_REACTION, MESSAGE_MEDIA_TYPE)
- Dois spans irmaos `router.classify` + `router.decide` substituindo o span unico `route_message`
- `StateSnapshot.load()` le `seen:{tenant_id}:{message_id}` (ja escrito pelo 003) + `handoff:{tenant_id}:{sender_key}` (contrato aberto 004→005)
- Fixtures reais `config/routing/ariel.yaml` + `config/routing/resenhai.yaml` (nomes reais, sem `pace-automations.yaml` legado)
- Pre-commit hook rodando `router verify` em todos os `config/routing/*.yaml`
- Atualizacao de `business/process.md` e `engineering/domain-model.md` — a "Fase B" deixa de ser promessa e vira doc de implementacao
- Atualizacao de `test_captured_fixtures.py` (003): `TEST_TENANTS` ganha `default_agent_id=None` (aditivo)

**Fora:**

- **Escrita** da chave Redis `handoff:{tenant_id}:{sender_key}` — fica para epic 005 (Conversation Core) ou epic 011 (Admin Handoff Inbox). 004 so **le**; o contrato e documentado como compromisso.
- Migracao de YAML para tabela DB `routing_rules` — fica para epic 006 (Configurable Routing DB) que agora vira refactor trivial
- Admin panel UI de edicao de regras — fica para epic 009
- Expansao da Layer 2 com expression language (jsonlogic/CEL) — rejeitado no deep-dive, principio "igualdade + conjuncao apenas"
- Regex/glob em campos de `when` — rejeitado no deep-dive (alternativa B descartada)
- `overrides:` escape hatch para overlap intencional — rejeitado no deep-dive
- Mudancas no parser da Evolution API — intocado (003 ja corrigiu 12 reality bugs)
- Mudancas no debounce — intocado
- Configuracao de sampling do OTel — gap pre-existente do 002; flagar para ADR follow-up mas nao corrigir aqui

## Rabbit Holes

- **Exhaustiveness dos enums nao enumera `instance`/`sender_phone`** — sao strings livres. Mitigacao: property test usa Hypothesis strategy para esses campos + teste separado de alcancabilidade carrega cada YAML real e varia apenas os enums por cada `instance` declarado. Pega "shadow rules" (regras que nunca matcham porque outra com wildcard vem antes).
- **`is_duplicate` exige lookup Redis** — mantido fora do `classify()` puro via `StateSnapshot.load()` chamado pelo caller com `MGET` unico (2 keys: seen + handoff). Classify continua sync e deterministica.
- **Overlap analysis falso-positivo em guards universais** — regras com mesmo `when` vazio parcial (ex: so `{from_me: true}`) nao conflitam com regras com campos adicionais se a engine avalia por ordem; mas o checker precisa entender "compativel em campos comuns = overlap". Validar: `{from_me: true}` overlap com `{from_me: true, channel: group}`? SIM, e isso e intencional — a de `priority` menor ganha. Overlap analysis deve detectar e **pedir para o dev reorganizar em regras disjuntas**. Escrever teste unitario do overlap checker com casos exemplares antes de escrever o checker.
- **Discriminated union serialization** — pydantic 2 serializa discriminator automaticamente, mas logging estruturado (structlog) precisa de `model_dump()` explicito. Validar em integracao.
- **Tenant YAML multiplo no dev** — 003 ja opera com 2 tenants reais (Ariel + ResenhAI). Loader deve funcionar com N arquivos desde o dia 1 (`for path in Path("config/routing").glob("*.yaml")`). Testar com as 2 fixtures reais do 004.
- **Migration path do `webhooks.py`** — hoje o handler chama `route_message(msg, tenant)` sync. Migrar para `await route(msg, redis, engine, matchers, tenant)` async requer: (1) carregar `RoutingEngine` + `app.state.matchers: dict[tenant_id, MentionMatchers]` no startup via lifespan; (2) chamar `StateSnapshot.load()` assincrono; (3) mapear `Decision` para o fluxo atual de debounce. Fazer num PR unico — rip-and-replace. Nao criar compat layer com enum antigo.
- **`conversation_in_handoff` sem escritor ainda** — 004 le a key, mas nenhum epic shipado escreve. Solucao: `StateSnapshot.load()` trata `None` como `False` (handoff desligado). Fact permanece `False` em 100% das mensagens ate epic 005/011 comecar a escrever. **Documentar como contrato aberto** no reconcile do 004 + adicionar test explicito assertando o comportamento fallback.
- **`is_membership_event` derivado** — MessageFacts expoe `is_membership_event: bool` derivado de `InboundMessage.event == "group-participants.update" AND group_event_action in {add, remove, promote, demote}`. Nao expor `group_event_action` como enum — evita explosao de facts ortogonais; regra YAML filtra so pelo bool.
- **Drift domain-model vs codigo do 003** — domain-model diz `tenants.settings.default_agent_id` (JSONB nested) e `InboundMessage`; 003 shipou `Tenant` flat + `ParsedMessage`. 004 fecha isso: `Tenant.default_agent_id` (flat, type-safe) + rename para `InboundMessage`. Reconcile do 004 atualiza domain-model ou flaga para revisao.

## Tasks

- [ ] **T0** Rename `ParsedMessage` → `InboundMessage`; mover de `prosauai/core/formatter.py` para `prosauai/core/inbound.py` (ou manter arquivo); atualizar todos os consumers (imports em router.py, webhooks.py, debounce.py, testes do 003) — pure rename, zero mudanca de logica
- [ ] **T1** Adicionar `default_agent_id: UUID | None = None` em `Tenant` dataclass (aditivo); atualizar `_build_tenant` em `tenant_store.py`; atualizar `tenants.example.yaml` com comentario; 1 teste unit em `test_tenant.py` (valor padrao None) + 1 teste em `test_tenant_store.py` (loader le UUID de YAML quando presente)
- [ ] **T2** Scaffold do modulo `prosauai/core/router/` (facts.py, engine.py, loader.py, verify.py, matchers.py, errors.py, `__init__.py`)
- [ ] **T3** `MessageFacts` dataclass + enums + invariantes `__post_init__` + test de construcao invalida (12+ testes unit)
- [ ] **T4** `MentionMatchers` value object + `from_tenant` classmethod + `matches(message)` (6+ testes cobrindo as 3 estrategias do 003: LID, phone, keyword)
- [ ] **T5** `classify(message, state, matchers)` puro — migrar logica de `route_message()` quebrando por fato (15+ testes unit cobrindo cada combinacao de fato)
- [ ] **T6** `StateSnapshot` + `load()` async com `MGET` duplo (seen + handoff); test explicito assertando `conversation_in_handoff=False` quando key nao existe (4+ testes com Redis mock)
- [ ] **T7** `Rule` dataclass + `matches()` + pydantic validators (12+ testes)
- [ ] **T8** 5 subtipos de `Decision` (discriminated union) + exhaustiveness check via `match/case` (5+ testes)
- [ ] **T9** `RoutingEngine.decide()` com agent resolution (rule → tenant default → `RoutingError`) (10+ testes incluindo caso "rule sem agent + tenant sem default → raise")
- [ ] **T10** YAML loader pydantic: schema, default obrigatorio, priority unico, campos conhecidos (15+ testes de rejeicao de config invalida)
- [ ] **T11** Overlap analysis pairwise: `rules_can_overlap()` + integracao no loader (8+ testes com configs propositalmente invalidas)
- [ ] **T12** Property test exaustivo: enumerar `MessageFacts` validos e assertar `len(matches) <= 1` + default sempre alcancavel (fixture com YAML real)
- [ ] **T13** Hypothesis test para `instance`/`sender_phone`/`group_id` livres
- [ ] **T14** Teste de alcancabilidade: "toda regra com `instance` especifico e matchavel" (detector de shadow rules)
- [ ] **T15** CLI `prosauai router verify <path>` (3+ testes integration com fixtures validas e invalidas)
- [ ] **T16** CLI `prosauai router explain --tenant X --facts <json>` (3+ testes)
- [ ] **T17** 6 constantes novas em `prosauai/observability/conventions.py`: `MATCHED_RULE`, `ROUTING_ACTION`, `DROP_REASON`, `EVENT_HOOK_TARGET`, `MESSAGE_IS_REACTION`, `MESSAGE_MEDIA_TYPE`. Atualizar `test_conventions.py`.
- [ ] **T18** Migrar `prosauai/api/webhooks.py` para `await route(...)` + 2 spans irmaos `router.classify` + `router.decide`. Remover span `route_message` legado. Test E2E no `test_webhook.py`.
- [ ] **T19** Atualizar `main.py` lifespan para carregar `RoutingEngine` + construir `app.state.matchers: dict[tenant_id, MentionMatchers]` no startup
- [ ] **T20** Criar `config/routing/ariel.yaml` (9 regras: drop_self_echo, drop_duplicate, drop_reaction, handoff_bypass, group_membership, individual_support, group_mention_support, group_silent_log + default)
- [ ] **T21** Criar `config/routing/resenhai.yaml` (mesma estrutura, priorities community-first)
- [ ] **T22** Pre-commit hook `router verify` em `config/routing/*.yaml`
- [ ] **T23** Atualizar `test_captured_fixtures.py` (003): `TEST_TENANTS` ganha `default_agent_id=None` em ambos; property test valida que as 26 fixtures reais retornam o mesmo `MessageRoute`/acao equivalente no novo engine
- [ ] **T24** Atualizar `business/process.md`: Fase B deixa de ser promessa, vira doc real
- [ ] **T25** Atualizar `engineering/domain-model.md`: Router aggregate com `classify` + `decide` separados; `InboundMessage` confirmado como aggregate; Tenant com `default_agent_id` flat
- [ ] **T26** Remover enum `MessageRoute` legado + `route_message()` + `_is_bot_mentioned()` + `_is_handoff_ativo()` de `prosauai/core/router.py` (rip-and-replace; grep prova zero consumers)
- [ ] **T27** Atualizar `test_router.py` (003) para usar novo engine + `MentionMatchers` ou deletar e substituir pelos testes granulares do novo modulo `core/router/`

## Criterios de Sucesso

- [ ] `ParsedMessage` renomeado para `InboundMessage`; grep em todo o repo retorna zero ocorrencias do nome antigo
- [ ] `Tenant.default_agent_id: UUID | None` existe e carrega corretamente de `tenants.yaml` quando definido
- [ ] Property test exaustivo passa: `len(matches) == 1` para todas as ~400 combinacoes validas de `MessageFacts`
- [ ] Overlap analysis rejeita fixture de config com duas regras sobrepostas (teste negativo)
- [ ] Loader rejeita YAML sem `default` (teste negativo)
- [ ] Loader rejeita YAML com `priority` duplicado (teste negativo)
- [ ] `mypy --strict prosauai/core/router/` passa sem erros (discriminated union prova exhaustiveness)
- [ ] `match/case` sobre `Decision` no `webhooks.py` tipa-se como exaustivo no pyright
- [ ] `prosauai router verify config/routing/ariel.yaml` → exit 0 + 9 rules loaded
- [ ] `prosauai router verify config/routing/resenhai.yaml` → exit 0 + N rules loaded
- [ ] `prosauai router explain` retorna regra correta para 5+ casos exemplares documentados
- [ ] `POST /webhook/whatsapp/Ariel` com payload grupo + mention → `Decision.action == RESPOND`, `agent_id != None`, `matched_rule == "group_mention_support"`
- [ ] `POST /webhook/whatsapp/Ariel` com payload `from_me=true` → `Decision.action == DROP`, `matched_rule == "drop_self_echo"`
- [ ] `POST /webhook/whatsapp/Ariel` com fixture de reaction → `Decision.action == DROP`, `matched_rule == "drop_reaction"`
- [ ] Phoenix mostra 2 spans irmaos `router.classify` + `router.decide` sob cada span `webhook_whatsapp`
- [ ] Span `router.decide` carrega `prosauai.matched_rule`, `prosauai.action`, `prosauai.agent_id` (em RESPOND)
- [ ] Log estruturado de cada webhook inclui `matched_rule` (grep em stdout)
- [ ] `grep -r "MessageRoute\|route_message\|RouteResult\|_is_bot_mentioned\|_is_handoff_ativo" prosauai/` → zero matches (tudo removido)
- [ ] `grep -r "ParsedMessage" prosauai/ tests/` → zero matches (rename completo)
- [ ] Todas as 26 fixtures do `test_captured_fixtures.py` continuam passando com o novo engine (equivalence entre rota antiga e acao nova)
- [ ] Test explicito valida que `conversation_in_handoff=False` quando Redis key nao existe (fallback seguro do contrato aberto)
- [ ] 95+ testes passando (70+ unit, 15+ integration, property tests, CLI tests)

## Decisoes

| Data | Decisao | Rationale |
|------|---------|-----------|
| 2026-04-10 | Arquitetura em 2 layers: `classify()` puro + `RoutingEngine` declarativo | Separa fato (no codigo) de regra (em config). Pedido literal do usuario no deep-dive |
| 2026-04-10 | Hit policy UNIQUE (overlap analysis = ERROR, zero escape hatch) | Garante MECE por construcao. Property test exaustivo fica forte. DMN UNIQUE. Benchmark Q1 do deep-dive |
| 2026-04-10 | `Decision` como discriminated union pydantic (5 subtipos) | Tipo reflete invariantes; mypy prova exhaustiveness no consumer. Benchmark Q7 |
| 2026-04-10 | `classify()` sync e puro + `StateSnapshot` pre-carregado pelo caller | Sans-I/O pattern (h11/urllib3). 1 MGET Redis no caller vs async propagation. Benchmark Q4 |
| 2026-04-10 | 1 YAML por tenant (`config/routing/<tenant-slug>.yaml`) | Mapeia 1:1 ao admin panel (epic 009) e a tabela `routing_rules` (epic 006). Multi-tenant = multi-owner |
| 2026-04-10 | Default obrigatorio no schema YAML | Elimina "limbo" por construcao — pydantic rejeita config sem catch-all |
| 2026-04-10 | `agent` na regra e opcional; ausente → `tenant.default_agent_id` | Permite regras genericas sem hardcodar agente. Evita copia de UUID em toda row RESPOND. DMN 1.3 modela default no nivel da tabela |
| 2026-04-10 | `instance` no `when` e opcional; ausente = wildcard | Guards universais (from_me, duplicate, handoff) nao precisam declarar instance |
| 2026-04-10 | Exhaustiveness test = enumeracao de enums+bools + Hypothesis + teste separado de reachability por instance | Enumeration cobre predicados; Hypothesis cobre valores livres; reachability pega shadow rules. Combo Q3 do deep-dive |
| 2026-04-10 | Rip-and-replace: remover `MessageRoute` / `RouteResult` / `route_message()` / `_is_bot_mentioned` / `_is_handoff_ativo` legados no mesmo PR | Zero consumers externos (tudo vive em `webhooks.py`). Compat layer so acumularia divida |
| 2026-04-10 | Epic dedicado (nao absorver em 005 Conversation Core) | Refactor e scope fechado (~1000 LOC prod + 650 test). Absorver em 005 mistura router com LLM → mega-epic |
| 2026-04-10 | CLI `router verify` + `router explain` como hook pre-commit e CI | DX alta: config invalida nao entra no repo. Trava merge em CI |
| 2026-04-10 | Storage no epic 004 = YAML em disco commitado no repo externo | Versionado em git, auditavel em PR. Migracao para DB fica para epic 006 (refactor trivial) |
| 2026-04-10 | **[REVISADO]** `classify()` consome `InboundMessage` (renomeado de `ParsedMessage`), nao dict | Reaproveita o ACL do 003 (26 fixtures reais, 12 reality fixes). Zero canal alternativo planejado (grep vazio em roadmap/ADRs). Rename alinha com `domain-model.md:40-53` que ja usa `InboundMessage`. DDD ACL: dominio consome DTO tipado, nao dict |
| 2026-04-10 | **[NOVO]** `MentionMatchers` frozen value object como 3o parametro de `classify()`; sem classe `FactExtractor` | Pureza FCIS: configuracao gathered no shell, passada como parametro para o core. h11 faz o mesmo (per-connection config no construtor). Alternativa pre-compute no caller fragmenta definicao de "mention" entre webhooks.py e router.py |
| 2026-04-10 | **[NOVO]** `default_agent_id: UUID \| None` aditivo no `Tenant` dataclass (flat, nao JSONB settings) | 003 nao shipou o campo apesar do `domain-model.md:162` prometer. Flat e type-safe no startup; quando epic 013 migrar para Postgres, JSONB settings vira colunas tipadas. Evita fake "settings" dict intermediario |
| 2026-04-10 | **[NOVO]** 2 spans irmaos `router.classify` + `router.decide` sob `webhook_whatsapp`, com 6 novas constantes flat em `conventions.py` | OTel guidance: operacoes com duracao/failure mode independentes = spans, nao events. Reconcile do 002 ja pre-aprovou `matched_rule` como atributo compativel. Namespace flat `prosauai.*` segue o padrao existente |
| 2026-04-10 | **[NOVO]** Fixtures reais `config/routing/ariel.yaml` + `config/routing/resenhai.yaml` (sem `pace-automations.yaml` legado) | 003 opera com 2 tenants reais; nome `pace-automations` e artefato pre-003. Shipar fixtures reais prova multi-tenant empiricamente + alinha com `test_captured_fixtures.py` que usa `Ariel`/`ResenhAI` como instance names |
| 2026-04-10 | **[NOVO]** `conversation_in_handoff` lido de Redis em 004; escrita e contrato aberto para epic 005 (Conversation Core) ou 011 (Admin Handoff Inbox) | Fact precisa existir no modelo MECE agora para a regra `handoff_bypass` compilar, mesmo sem escritor. Fallback seguro: `StateSnapshot.load()` retorna `False` quando key nao existe. Documentado como contrato aberto no reconcile |
| 2026-04-10 | **[NOVO]** `is_membership_event: bool` derivado de `event == "group-participants.update" AND action in {add,remove,promote,demote}`; nao expor `group_event_action` como fact | Evita explosao de enums ortogonais em `MessageFacts`. Regra YAML so precisa do bool para rotear GROUP_EVENT |

## Notas

(Append-only — adicionar descobertas durante implementacao)

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | Arquitetura | Router em 2 layers: `classify()` puro + `RoutingEngine` declarativo | blueprint §4.6, domain-model Router aggregate |
| 2 | Dominio | `MessageFacts` com enums fechados + invariantes `__post_init__` | domain-model Channel BC |
| 3 | Regras | Hit policy UNIQUE (overlap = ERROR, sem escape hatch) | DMN 1.3 — decision table com hit policy UNIQUE |
| 4 | Tipos | `Decision` como discriminated union pydantic (5 subtipos) | blueprint §1 (pydantic 2 stack), ADR-001 |
| 5 | I/O | `classify()` puro; `StateSnapshot` pre-carregado via MGET no caller | blueprint §4.6 (sans-I/O), ADR-003 |
| 6 | Storage config | 1 YAML per tenant (`config/routing/<slug>.yaml`) | ADR-006 §routing-configuravel, blueprint §4.5 |
| 7 | Schema | Default obrigatorio no YAML; pydantic rejeita config sem catch-all | MECE construction invariant |
| 8 | Agent resolution | `agent` opcional na regra; fallback para `tenant.default_agent_id` | ADR-006 §routing-configuravel |
| 9 | Matching | `instance` opcional no `when`; ausente = wildcard | ADR-006 |
| 10 | Testing | Exhaustiveness = enumeracao enums+bools + Hypothesis + reachability-per-instance | pipeline-contract-base.md auto-review |
| 11 | Migracao | Rip-and-replace: remove enum/funcao legada no mesmo PR | refactor discipline |
| 12 | Placement | Epic dedicado, nao absorvido em 005 (Conversation Core) | Shape Up appetite |
| 13 | DX | CLI `router verify\|explain` como hook pre-commit + CI | blueprint §2.2 |
| 14 | MECE | Garantias em 4 camadas: tipo (Layer 1), schema (load-time), runtime (discriminated union + match/case exhaustiveness), CI (property tests) | blueprint §5 (NFR: testabilidade) |
| 15 | **[REVISADO]** Input type | `classify()` consome `InboundMessage` (renomeado de `ParsedMessage`); reaproveita ACL do epic 003 | domain-model.md:40-53 (aggregate ja tem esse nome); epic 003 formatter.py (26 fixtures reais) |
| 16 | Tenant-aware purity | `MentionMatchers` frozen como 3o parametro de `classify()`; sem classe `FactExtractor` | Bernhardt FCIS, h11 sans-I/O config-in-constructor pattern |
| 17 | Schema Tenant | `default_agent_id: UUID \| None` adicionado flat ao `Tenant` dataclass (nao via settings JSONB) | domain-model.md:162-168 promete; epic 003 nao shipou; ADR-006 §default-agent |
| 18 | Observabilidade | 2 spans irmaos `router.classify` + `router.decide` + 6 constantes flat em `conventions.py` | OTel guidance sobre spans vs events; reconcile-report do 002 pre-aprovou `matched_rule` |
| 19 | Fixtures YAML | `ariel.yaml` + `resenhai.yaml` reais (sem `pace-automations.yaml` legado); alinhados com tenant IDs do 003 | epic 003 pitch (tenants Ariel + ResenhAI dia 1), test_captured_fixtures.py |
| 20 | Handoff contract | `conversation_in_handoff` lido em 004 com fallback `False`; escrita fica para epic 005/011 — contrato aberto documentado | epic 005 escopo (Conversation Core), epic 011 Admin Handoff Inbox |
| 21 | Fact derivation | `is_membership_event` derivado de `group-participants.update + action`; nao expor `group_event_action` como fact separado | evita explosao de enums ortogonais |

## Resolved Gray Areas

**G1 — Onde resolver `agent_id`**: dentro do `RoutingEngine.decide()`, na mesma chamada da classificacao. Alternativa descartada: duas chamadas separadas (`decide_action` + `resolve_agent`). Razao: no codigo as duas fases sempre sao chamadas juntas; separar cria superficie para bug ("esqueci de chamar o resolver"). O diagrama `business/process.md` mantem Fase A/B como separacao didatica; na implementacao e uma chamada.

**G2 — Overlap intencional (ex: cascata com mesma acao)**: nao permitido. Regras precisam ser disjuntas por construcao. Rule explosion e bounded no prosauai (<50 regras per tenant no horizonte previsivel). Se doer no futuro, adiciona-se `overrides:` ou expression language retroativamente.

**G3 — Limite de expressividade das regras (`when` so aceita igualdade + conjuncao)**: aceito. Sem OR, sem NOT, sem regex, sem glob. Casos que hoje pareceriam precisar de OR (ex: "individual OU grupo com mention") viram 2 rows no YAML. Admin panel (epic 009) ganha form trivial (dropdowns).

**G4 — `from_me` / `is_duplicate` sao guards hardcoded ou regras YAML?**: regras YAML (priority 0-5). Consistencia > micro-otimizacao. Custo extra: 2-3 entradas no loop da engine — irrelevante em 1000 msg/s. Reaction tambem entra como guard (priority 2).

**G5 — `conversation_in_handoff` exige lookup externo**: mantido no `StateSnapshot` carregado pelo caller via MGET Redis. Classify permanece pura. **Atualizacao do draft**: a key `handoff:{tenant_id}:{sender_key}` nao tem escritor no epic 003. 004 le com fallback `False`; escrita e contrato aberto documentado para epic 005 (Conversation Core — quando usuario pedir atendimento humano) ou epic 011 (Admin Handoff Inbox — quando humano assume).

**G6 — Tenant sem `default_agent_id` configurado + regra que nao especifica `agent` + match**: `RoutingError` em runtime com mensagem clara. Detectavel tambem no `router verify --tenant <slug>` (detecta "regras que dependem de tenant default mas tenant nao tem default" quando passada `--tenant <slug>`). Ver teste negativo T9.

**G7 — Input type do `classify()` (questao nova)**: consome `InboundMessage` (renomeado de `ParsedMessage`), nao dict. Razao deep: (a) o parser do 003 ja e o ACL contra a Evolution, reparsear seria duplicar o trabalho; (b) zero canais alternativos planejados (grep vazio em roadmap/ADRs por "telegram|signal|sms|rcs"); (c) sans-I/O pattern: o state machine da Evolution ja rodou no parser — `classify()` e downstream consumer; (d) `channels/base.py` ABC ja hardcoda `instance: str`, "channel-agnostic core" ja zarpou para a Evolution; (e) `domain-model.md:40-53` ja usa o nome `InboundMessage` — rename fecha drift doc/code.

**G8 — Mention detection tenant-aware e `classify()` puro (questao nova)**: `MentionMatchers` frozen value object, 3o parametro de `classify()`. Pureza e sobre side effects, nao aridade — passar um dataclass frozen como param e estritamente mais puro que um extractor stateful. O pitch ja usa esse idioma no `RoutingEngine.decide(facts, tenant_ctx)` (Layer 2); Layer 1 segue o mesmo padrao. h11 e sans-I/O tradicionais fazem exatamente isso (per-connection config no construtor). `MentionMatchers.from_tenant(tenant)` e construido uma vez no lifespan + cached em `app.state.matchers: dict[tenant_id, MentionMatchers]`.

**G9 — `default_agent_id` no `Tenant` (questao nova)**: aditivo, opcional, flat (`UUID | None = None`). `domain-model.md:162-168` ja promete esse campo mas epic 003 nao shipou. 004 fecha o gap. Nao usar `settings: dict` intermediario — type-safety no startup e prioridade; quando epic 013 migrar para Postgres, o JSONB settings vira colunas tipadas progressivamente. Alternativa "obrigar toda regra RESPOND declarar `agent`" rejeitada: fere DMN 1.3 (defaults no nivel da tabela) e cria copia redundante de UUID em Ariel (3 rows RESPOND identicas).

**G10 — Observabilidade OTel (questao nova)**: 2 spans irmaos `router.classify` + `router.decide` sob o span pai `webhook_whatsapp`. Constantes flat (`prosauai.matched_rule`, `prosauai.action`, `prosauai.drop_reason`, `prosauai.event_target`, `prosauai.is_reaction`, `prosauai.media_type`) seguindo o padrao existente de `conventions.py`. OTel guidance oficial: operacoes com duracao/failure mode independentes = spans, nao events. Option B (span unico enriquecido) perde porque: (a) conflate falhas classify vs decide; (b) perde per-stage latency (rule engine com 20+ regras pode ficar lento); (c) trai separacao arquitetural MECE. Reconcile-report do 002 ja pre-aprovou `matched_rule` como atributo compativel.

**G11 — Fixtures YAML reais (questao nova)**: `config/routing/ariel.yaml` + `config/routing/resenhai.yaml`, sem `pace-automations.yaml`. 003 ja opera com 2 tenants reais; shipar config real prova multi-tenant empiricamente desde o dia 1 do router, e alinha com os tenant IDs usados em `test_captured_fixtures.py`. Arquivos ficam no **repo externo `paceautomations/prosauai`** (config executavel), nao em madruga (docs). Epic 006 (Configurable Routing DB) migra estas para rows em tabela `routing_rules`.

**G12 — Drift domain-model vs codigo do 003 (descoberta lateral)**: `domain-model.md` diz `tenants.settings.default_agent_id` (JSONB nested) e `InboundMessage`; 003 shipou `Tenant` flat sem `settings` + `ParsedMessage`. 004 fecha: `Tenant.default_agent_id: UUID | None` (flat) + rename para `InboundMessage`. Reconcile do 004 atualiza o domain-model para refletir a decisao flat.

**G13 — `is_membership_event` como enum ou bool (questao nova)**: bool derivado. `MessageFacts.is_membership_event = (event == "group-participants.update" AND group_event_action in {add,remove,promote,demote})`. Nao expor `group_event_action` separado — evita explosao de facts ortogonais. Regra YAML `group_membership` so precisa do bool para rotear `EVENT_HOOK`.

## Applicable Constraints

| Constraint | Source | Impact |
|-----------|--------|--------|
| Multi-tenant RLS obrigatorio em toda tabela de dados | ADR-011 | Quando epic 006 migrar YAML → DB, `routing_rules` table herda RLS policy |
| Config nunca em codigo | ADR-017 | Justificativa primaria do epic: regras saem do codigo |
| pydantic 2 como base de modelagem | ADR-001, blueprint §1 | Discriminated union nativo, validators cross-field |
| Sans-I/O no core domain | blueprint §4.6 | `classify()` sync e puro; I/O apenas no caller via `StateSnapshot.load()` |
| Observabilidade estruturada (structlog) | blueprint §4.4 | `Decision.matched_rule` entra em todo log do webhook |
| OTel conventions flat `prosauai.*` | epic 002 reconcile-report | Novas constantes do 004 seguem o padrao; zero namespace novo |
| Python 3.12+ | blueprint §1 | `match/case` exhaustiveness via mypy/pyright |
| ruff strict + mypy strict | blueprint §5 | Discriminated union + enums dao exhaustiveness gratis |
| Config versionada | blueprint §2.2 | YAML commitado no repo externo `paceautomations/prosauai`, PR-reviewable |
| Domain-model define Router aggregate com classify + resolve | domain-model.md linhas 88-96 | Codigo passa a refletir o domain model que ja existia so no papel |
| Domain-model usa `InboundMessage` como aggregate do Channel BC | domain-model.md linhas 40-53 | Rename `ParsedMessage` → `InboundMessage` fecha drift |
| Hit policy UNIQUE (DMN 1.3) | Benchmark externo (referencia Q1) | Loader rejeita overlap nao-declarado |
| Tenants reais: Ariel (pace-internal) + ResenhAI (resenha-internal) | epic 003 shipado | Fixtures YAML usam esses slugs |
| `Tenant` dataclass shipado pelo 003 sem `default_agent_id` | prosauai/core/tenant.py | 004 adiciona aditivamente (backward-compatible) |
| Auth/parser reality fix ja entregue | epic 003 (T6b-T6j + 26 fixtures) | 004 nao toca formatter/auth; foco exclusivo em router |

## Suggested Approach

1. **T0 — Rename `ParsedMessage → InboundMessage`** (pure rename, zero logica nova; roda testes do 003 pra garantir zero regressao).
2. **T1 — Add `default_agent_id` ao `Tenant`** (aditivo, 1 campo + 1 linha em `_build_tenant` + comentario em example.yaml + 2 testes).
3. **T2 — Scaffold `prosauai/core/router/`** com `facts.py`, `matchers.py`, `engine.py`, `loader.py`, `verify.py`, `errors.py`, `__init__.py`.
4. **T3-T4 — Tipos Layer 1**: `MessageFacts` + enums + invariantes + `MentionMatchers` value object. Testes unitarios do dataclass e dos 3 matchers.
5. **T5-T6 — `classify()` puro + `StateSnapshot`**: migrar logica do `route_message()` quebrando por fact. Cada `if` vira campo de `MessageFacts`. `StateSnapshot.load()` faz MGET duplo (seen + handoff). Test explicito de fallback `False` no handoff.
6. **T7-T8 — Tipos Layer 2**: `Action`, 5 subtipos `Decision`, `Rule`. Testes de exhaustiveness via snapshot mypy.
7. **T9 — `RoutingEngine.decide()`** com agent resolution (rule → tenant default → `RoutingError`). Testes com fixture programatica + caso de erro quando tenant sem default.
8. **T10-T11 — Loader YAML + overlap analysis**: pydantic model, validators, overlap checker pairwise. Testes negativos robustos.
9. **T12-T14 — Property tests**: enumeracao exaustiva + Hypothesis + reachability-per-instance (shadow rules).
10. **T15-T16 — CLI `verify|explain`** usando argparse ou typer. Testes de integracao.
11. **T17 — OTel constants novas** em `conventions.py` + atualizacao do `test_conventions.py`.
12. **T18-T19 — Migracao `webhooks.py` + `main.py` lifespan**: trocar chamada para `await route(...)`, carregar `RoutingEngine` + `app.state.matchers` no startup, 2 spans irmaos substituem span unico. Rip-and-replace do enum legado.
13. **T20-T22 — Fixtures reais `ariel.yaml` + `resenhai.yaml`** + pre-commit hook `router verify`.
14. **T23 — Atualizar `test_captured_fixtures.py`** (003) para garantir que as 26 fixtures reais continuam retornando acoes equivalentes no novo engine. `TEST_TENANTS` ganha `default_agent_id=None`.
15. **T24-T26 — Docs + rip-and-replace final**: atualizar `business/process.md` (Fase B real), `engineering/domain-model.md` (aggregate + Tenant com `default_agent_id` flat), remover enum `MessageRoute` + funcoes legadas, grep comprovando zero consumers.
16. **T27 — Atualizar `test_router.py`** (003) para usar novo engine, ou deletar e deixar so os testes granulares novos do `core/router/`.

> **Proximo passo:** branch `epic/prosauai/004-router-mece` ja criada em ambos os repos (madruga + externo prosauai). Proxima skill: `/speckit.specify prosauai 004-router-mece` para iniciar o ciclo L2. Pre-condicao validada: epic 002 (Observability) + epic 003 (Multi-Tenant Foundation) estao shippados; fase 1 do `docs/prosauai/IMPLEMENTATION_PLAN.md` esta 100% coberta; dividas estruturais do router (enum nao-MECE, regras hardcoded, `agent_id` None, drift domain-model) sao o escopo exclusivo deste epic.
