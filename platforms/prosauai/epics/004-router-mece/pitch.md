---
id: "004"
title: "Router MECE — Classificacao pura + regras externalizadas + agent resolution"
status: drafted
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
---

# 004 — Router MECE

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | M3 (Smart Router) | [Containers (Interactive)](../../engineering/containers/) |
| Contextos | Channel | [Context Map](../../engineering/context-map/) |
| Containers | prosauai-api | [Containers (Interactive)](../../engineering/containers/) |

## Problema

O epic 001 entregou o `Smart Router` funcional mas com tres divida estruturais que bloqueiam evolucao:

1. **Nao-MECE por construcao.** O enum `MessageRoute` conflata tres eixos ortogonais: tipo de mensagem (individual/grupo), estado de conversa (handoff/normal) e acao (respond/log/drop). O resultado e que `SUPPORT`, `GROUP_RESPOND`, `GROUP_SAVE_ONLY`, `GROUP_EVENT`, `HANDOFF_ATIVO` e `IGNORE` nao sao mutuamente exclusivos conceitualmente — o nome `SUPPORT` ja decide que "individual → suporte" esta hardcoded. Nao ha como expressar "individual em handoff ativo" sem criar constante nova.

2. **Regras de negocio cimentadas em codigo.** O `route_message()` em `prosauai/core/router.py` tem regras dentro de if/elif: "from_me primeiro", "individual vira SUPPORT", "grupo com mention vira GROUP_RESPOND". Trocar "individual → vendas" para "individual → onboarding" exige mudar enum, codigo e testes. Admin panel (epic 008) nao tem o que editar.

3. **`agent_id` sempre None.** O `RouteResult.agent_id` existe desde o dia 1 por decisao 10 do epic 001 ("evita breaking change futuro"), mas **nenhum lugar do codigo escreve valor nele**. A "Fase B — Agent Resolution" do diagrama em `business/process.md` e ficcao — existe so no Mermaid, nao no Python. Quando o epic 004 (Conversation Core + LLM) for implementado, ele vai ter que inventar `agent_id` do nada ou hardcodar `tenant.settings.default_agent_id` direto, bypassando qualquer conceito de regra.

O deep-dive que originou este epic esta registrado na conversa [2026-04-10 — Router MECE deep-dive]. O pedido do usuario foi literal: "regras que sao fato ficam no codigo; links entre fatos e agentes ficam fora do codigo, sempre MECE". O problema (3) torna este refactor **bloqueio duro** para qualquer epic que invoque LLM — sem ele, o epic 004 herda o bug.

## Valor de Negocio

- [ ] Classificacao de mensagem e MECE por construcao — provado em CI via enumeracao exaustiva dos fatos possiveis
- [ ] Mudar regras de roteamento sem deploy — editar `config/routing/<tenant>.yaml` (epic 004) ou row em `routing_rules` (epic 006)
- [ ] `agent_id` resolvido de verdade pelo router — epic 005 (Conversation Core) consome `Decision.agent_id` em vez de hardcodar default
- [ ] Observabilidade: cada mensagem loga qual regra casou (`matched_rule`), nao apenas `route.value`
- [ ] Admin panel (epic 008) ganha modelo de dados pronto — cada regra = 1 row editavel

## Solucao

Arquitetura em duas camadas, separando **fatos** de **regras**:

**Layer 1 — `classify()`**: funcao pura `payload → MessageFacts`, 100% deterministica, sem I/O, sem config. `MessageFacts` e um dataclass frozen com campos ortogonais (enums + bool): `channel`, `event_kind`, `content_kind`, `from_me`, `has_mention`, `is_membership_event`, `is_duplicate`, `conversation_in_handoff`. Estado externo (`is_duplicate`, `conversation_in_handoff`) e pre-carregado pelo caller num `StateSnapshot` via `MGET` unico no Redis — `classify()` continua sync e pura. Invariantes cross-field sao validadas em `__post_init__` (ex: `has_mention ⟹ channel == GROUP`), impedindo a construcao de fatos impossiveis.

**Layer 2 — `RoutingEngine.decide(facts, tenant_ctx)`**: avalia rules ordenadas por `priority ASC`, primeira cujo `when` casa ganha. Se nenhuma casa, usa `default` (obrigatorio no schema). Para `action == RESPOND`, resolve `agent_id` a partir da regra ou cai em `tenant_ctx.default_agent_id`. Retorna um `Decision` que e uma **discriminated union pydantic** de 5 subtipos (`RespondDecision`, `LogOnlyDecision`, `DropDecision`, `BypassAIDecision`, `EventHookDecision`) — cada subtipo carrega apenas os campos validos para aquela acao, eliminando estados invalidos em compile-time.

**Config externa**: `config/routing/<tenant-slug>.yaml`, um arquivo por tenant. Loader pydantic valida schema, rejeita campos desconhecidos, exige `default` obrigatorio. Admin panel (epic 008) edita o mesmo schema. Epic 005 (originalmente "Configurable Routing DB") passa a ser trivial — so troca o loader de YAML para tabela `routing_rules`.

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
    sender_phone: str
    group_id: str | None
    # Conteudo
    has_mention: bool
    is_membership_event: bool
    # Estado
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
    async def load(cls, redis, message_id: str, conv_key: str) -> "StateSnapshot":
        dup, handoff = await redis.mget(f"seen:{message_id}", f"handoff:{conv_key}")
        return cls(is_duplicate=bool(dup), conversation_in_handoff=bool(handoff))

def classify(payload: dict, state: StateSnapshot) -> MessageFacts: ...


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

    def decide(self, facts: MessageFacts, tenant_ctx: TenantCtx) -> Decision: ...


# prosauai/core/router/__init__.py — public API
def route(payload: dict, state: StateSnapshot, engine: RoutingEngine, tenant_ctx: TenantCtx) -> Decision:
    facts = classify(payload, state)
    return engine.decide(facts, tenant_ctx)
```

### Schema YAML de routing

```yaml
# config/routing/pace-automations.yaml
version: 1
tenant: pace-automations

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

  # Rotas por numero+canal (priority 100+)
  - name: main_line_individual_sales
    priority: 100
    when:
      instance: "5511999998888"
      channel: individual
    action: RESPOND
    agent: agent-vendas-uuid

  - name: main_line_group_mention_community
    priority: 110
    when:
      instance: "5511999998888"
      channel: group
      has_mention: true
    action: RESPOND
    agent: agent-comunidade-uuid

  - name: main_line_group_silent_log
    priority: 120
    when:
      instance: "5511999998888"
      channel: group
      has_mention: false
    action: LOG_ONLY

default:
  action: RESPOND
  # agent omitido → usa tenant_ctx.default_agent_id
  reason: no_rule_matched_fallback_to_default
```

### Scope

**Dentro:**

- Layer 1: `classify()` puro + `MessageFacts` com invariantes
- Layer 2: `RoutingEngine` + `Rule` + 5 subtipos de `Decision` (discriminated union)
- Loader YAML pydantic (schema validation + overlap analysis + default obrigatorio)
- CLI `prosauai router verify|explain`
- Property tests exaustivos (enumeracao + Hypothesis) + teste de alcancabilidade por `instance`
- Migracao do `webhooks.py` atual para usar novo `route()` + `Decision` discriminated union
- Backfill do `tenants.settings.default_agent_id` (fallback seguro durante migracao)
- Deprecacao do enum `MessageRoute` legado (removido no mesmo PR — ver decisao 8)
- Pre-commit hook rodando `router verify` em todos os `config/routing/*.yaml`
- Atualizacao de `business/process.md` e `engineering/domain-model.md` — a "Fase B" deixa de ser promessa e vira doc de implementacao

**Fora:**

- Migracao de YAML para tabela DB `routing_rules` — fica para epic 005 (Configurable Routing DB) que agora vira refactor trivial
- Admin panel UI de edicao de regras — fica para epic 008
- Expansao da Layer 2 com expression language (jsonlogic/CEL) — rejeitado no deep-dive, principio "igualdade + conjuncao apenas"
- Regex/glob em campos de `when` — rejeitado no deep-dive (alternativa B descartada)
- `overrides:` escape hatch para overlap intencional — rejeitado no deep-dive
- Mudancas no parser da Evolution API (`formatter.py`) — intocado
- Mudancas no debounce — intocado

## Rabbit Holes

- **Exhaustiveness dos enums nao enumera `instance`/`sender_phone`** — sao strings livres. Mitigacao: property test usa Hypothesis strategy para esses campos + teste separado de alcancabilidade carrega cada YAML real e varia apenas os enums por cada `instance` declarado. Pega "shadow rules" (regras que nunca matcham porque outra com wildcard vem antes).
- **`is_duplicate` exige lookup Redis** — mantido fora do `classify()` puro via `StateSnapshot.load()` chamado pelo caller com `MGET` unico (1 roundtrip). Classify continua sync e deterministica.
- **Overlap analysis falso-positivo em guards universais** — regras com mesmo `when` vazio parcial (ex: so `{from_me: true}`) nao conflitam com regras com campos adicionais se a engine avalia por ordem; mas o checker precisa entender "compativel em campos comuns = overlap". Validar: `{from_me: true}` overlap com `{from_me: true, channel: group}`? SIM, e isso e intencional — a de `priority` menor ganha. Overlap analysis deve detectar e **pedir para o dev reorganizar em regras disjuntas** (ex: guards nunca conflitam com routes porque guards matcham `from_me/is_duplicate/handoff` que routes nao mencionam). Escrever teste unitario do overlap checker com casos exemplares antes de escrever o checker.
- **Discriminated union serialization** — pydantic 2 serializa discriminator automaticamente, mas logging estruturado (structlog) precisa de `model_dump()` explicito. Validar em integracao.
- **Tenant YAML multiplo no dev** — no epic 004 temos apenas 1 tenant (`pace-automations`). Loader deve funcionar com N arquivos desde o dia 1 (`for path in Path("config/routing").glob("*.yaml")`). Testar com 2 fixtures para provar.
- **Migration path do `webhooks.py`** — hoje o handler chama `route_message(msg, settings)` direto. Migrar para `route(payload, state, engine, tenant_ctx)` requer: (1) carregar `RoutingEngine` no startup via lifespan; (2) carregar `StateSnapshot` por request; (3) mapear `Decision` para o fluxo atual de `echo response`. Fazer num PR unico — rip-and-replace. Nao criar compat layer com enum antigo.

## Tasks

- [ ] Scaffold do modulo `prosauai/core/router/` (facts.py, engine.py, loader.py, verify.py, errors.py, __init__.py)
- [ ] `MessageFacts` dataclass + enums + invariantes `__post_init__` (12+ testes unit)
- [ ] `classify()` puro — migrar logica de `route_message()` atual (15+ testes unit cobrindo cada combinacao de fato)
- [ ] `StateSnapshot` + `load()` async com `MGET` (4+ testes com Redis mock)
- [ ] `Rule` dataclass + `matches()` + pydantic validators (12+ testes)
- [ ] 5 subtipos de `Decision` (discriminated union) + exhaustiveness check via `match/case` (5+ testes)
- [ ] `RoutingEngine.decide()` com agent resolution (rule → tenant default → error) (10+ testes)
- [ ] YAML loader pydantic: schema, default obrigatorio, priority unico, campos conhecidos (15+ testes de rejeicao de config invalida)
- [ ] Overlap analysis pairwise: `rules_can_overlap()` + integracao no loader (8+ testes com configs propositalmente invalidas)
- [ ] Property test exaustivo: enumerar `MessageFacts` validos e assertar `len(matches) <= 1` + default sempre alcancavel (fixture com YAML real + YAML minimal)
- [ ] Hypothesis test para `instance`/`sender_phone`/`group_id` livres
- [ ] Teste de alcancabilidade: "toda regra com `instance` especifico e matchavel" (detector de shadow rules)
- [ ] CLI `prosauai router verify <path>` (3+ testes integration com fixtures validas e invalidas)
- [ ] CLI `prosauai router explain --tenant X --facts <json>` (3+ testes)
- [ ] Migrar `prosauai/api/webhooks.py` para chamar `route(payload, state, engine, tenant_ctx)` — remover `route_message()` legado
- [ ] Atualizar `main.py` lifespan para carregar `RoutingEngine` no startup
- [ ] Fixture `config/routing/pace-automations.yaml` com 7+ regras cobrindo todos os casos de uso atuais
- [ ] Pre-commit hook `router verify` em `config/routing/*.yaml`
- [ ] Atualizar `business/process.md`: Fase B deixa de ser promessa, vira doc real
- [ ] Atualizar `engineering/domain-model.md`: Router aggregate com `classify` + `decide` separados
- [ ] Remover enum `MessageRoute` legado de `prosauai/core/router.py` + atualizar consumers (grep prova zero consumers)

## Criterios de Sucesso

- [ ] Property test exaustivo passa: `len(matches) == 1` para todas as ~400 combinacoes validas de `MessageFacts`
- [ ] Overlap analysis rejeita fixture de config com duas regras sobrepostas (teste negativo)
- [ ] Loader rejeita YAML sem `default` (teste negativo)
- [ ] Loader rejeita YAML com `priority` duplicado (teste negativo)
- [ ] `mypy --strict prosauai/core/router/` passa sem erros (discriminated union prova exhaustiveness)
- [ ] `match/case` sobre `Decision` no `webhooks.py` tipa-se como exaustivo no pyright
- [ ] `prosauai router verify config/routing/pace-automations.yaml` → exit 0 + 8 rules loaded
- [ ] `prosauai router explain` retorna regra correta para 5+ casos exemplares documentados
- [ ] `POST /webhook/whatsapp/{instance}` com payload grupo + mention → `Decision.action == RESPOND`, `agent_id != None`, `matched_rule == "main_line_group_mention_community"`
- [ ] `POST /webhook/whatsapp/{instance}` com payload `from_me=true` → `Decision.action == DROP`, `matched_rule == "drop_self_echo"`
- [ ] Log estruturado de cada webhook inclui `matched_rule` (grep em stdout)
- [ ] `grep -r "MessageRoute\|route_message\|RouteResult" prosauai/` → zero matches (tudo removido)
- [ ] 80+ testes passando (70+ unit, 10+ integration, property tests)

## Decisoes

| Data | Decisao | Rationale |
|------|---------|-----------|
| 2026-04-10 | Arquitetura em 2 layers: `classify()` puro + `RoutingEngine` declarativo | Separa fato (no codigo) de regra (em config). Pedido literal do usuario no deep-dive |
| 2026-04-10 | Hit policy UNIQUE (overlap analysis = ERROR, zero escape hatch) | Garante MECE por construcao. Property test exaustivo fica forte. DMN UNIQUE. Benchmark Q1 do deep-dive |
| 2026-04-10 | `Decision` como discriminated union pydantic (5 subtipos) | Tipo reflete invariantes; mypy prova exhaustiveness no consumer. Benchmark Q7 |
| 2026-04-10 | `classify()` sync e puro + `StateSnapshot` pre-carregado pelo caller | Sans-I/O pattern (h11/urllib3). 1 MGET Redis no caller vs async propagation. Benchmark Q4 |
| 2026-04-10 | 1 YAML por tenant (`config/routing/<tenant-slug>.yaml`) | Mapeia 1:1 ao admin panel (epic 008) e a tabela `routing_rules` (epic 005). Multi-tenant = multi-owner. Benchmark Q5 |
| 2026-04-10 | Default obrigatorio no schema YAML | Elimina "limbo" por construcao — pydantic rejeita config sem catch-all |
| 2026-04-10 | `agent` na regra e opcional; ausente → `tenant_ctx.default_agent_id` | Permite regras genericas ("individual responde com agente X") sem hardcodar agente. Compativel com `domain-model.md` |
| 2026-04-10 | `instance` no `when` e opcional; ausente = wildcard | Guards universais (from_me, duplicate, handoff) nao precisam declarar instance. Match por igualdade em campos declarados apenas |
| 2026-04-10 | Exhaustiveness test = enumeracao de enums+bools (Cartesian) + Hypothesis para campos livres + teste separado de reachability por instance | Enumeration cobre predicados; Hypothesis cobre valores livres; reachability pega shadow rules. Combo Q3 do deep-dive |
| 2026-04-10 | Rip-and-replace: remover `MessageRoute` / `RouteResult` / `route_message()` legados no mesmo PR | Zero consumers externos (tudo vive em `webhooks.py`). Compat layer so acumularia divida |
| 2026-04-10 | Epic dedicado (nao absorver em 005 Conversation Core) | Refactor e scope fechado (~800 LOC prod + 500 test). Absorver em 005 mistura router com LLM → mega-epic. Q6 |
| 2026-04-10 | CLI `router verify` + `router explain` como hook pre-commit e CI | DX alta: config invalida nao entra no repo. Trava merge em CI |
| 2026-04-10 | Storage no epic 004 = YAML em disco commitado | Versionado em git, auditavel em PR. Migracao para DB fica para epic 006 (refactor trivial: trocar loader) |

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
| 8 | Agent resolution | `agent` opcional na regra; fallback para `tenant_ctx.default_agent_id` | ADR-006 §routing-configuravel |
| 9 | Matching | `instance` opcional no `when`; ausente = wildcard | ADR-006 |
| 10 | Testing | Exhaustiveness = enumeracao enums+bools + Hypothesis + reachability-per-instance | pipeline-contract-base.md auto-review |
| 11 | Migracao | Rip-and-replace: remove enum/funcao legada no mesmo PR | refactor discipline |
| 12 | Placement | Epic dedicado, nao absorvido em 005 (Conversation Core) | Shape Up appetite |
| 13 | DX | CLI `router verify|explain` como hook pre-commit + CI | blueprint §2.2 |
| 14 | MECE | Garantias em 4 camadas: tipo (Layer 1), schema (load-time), runtime (discriminated union + match/case exhaustiveness), CI (property tests) | blueprint §5 (NFR: testabilidade) |

## Resolved Gray Areas

**Onde resolver `agent_id`**: dentro do `RoutingEngine.decide()`, na mesma chamada da classificacao. Alternativa descartada: duas chamadas separadas (`decide_action` + `resolve_agent`). Razao: no codigo as duas fases sempre sao chamadas juntas; separar cria superficie para bug ("esqueci de chamar o resolver"). O diagrama `business/process.md` mantem Fase A/B como separacao didatica; na implementacao e uma chamada.

**Overlap intencional (ex: cascata com mesma acao)**: nao permitido. Regras precisam ser disjuntas por construcao. Rule explosion e bounded no prosauai (<50 regras per tenant no horizonte previsivel). Se doer no futuro, adiciona-se `overrides:` ou expression language retroativamente.

**Limite de expressividade das regras (`when` so aceita igualdade + conjuncao)**: aceito. Sem OR, sem NOT, sem regex, sem glob. Casos que hoje pareceriam precisar de OR (ex: "individual OU grupo com mention") viram 2 rows no YAML. Admin panel (epic 008) ganha form trivial (dropdowns).

**`from_me` / `is_duplicate` sao guards hardcoded ou regras YAML?**: regras YAML (priority 0-5). Consistencia > micro-otimizacao. Custo extra: 2 entradas no loop da engine — irrelevante em 1000 msg/s.

**`conversation_in_handoff` exige lookup externo**: mantido no `StateSnapshot` carregado pelo caller via MGET Redis. Classify permanece pura.

**Tenant sem `default_agent_id` configurado + regra que nao especifica `agent` + match**: `RoutingError` em runtime com mensagem clara. Detectavel tambem no `router verify` (detecta "regras que dependem de tenant default mas tenant nao tem default" quando passada `--tenant <slug>`). Ver teste negativo.

**Storage durante o epic 004**: YAML em `config/routing/*.yaml` commitado no repo externo `paceautomations/prosauai`. Epic 006 (originalmente "Configurable Routing + Groups") vira refactor minimo — troca loader de YAML para `routing_rules` table em Supabase. O schema Python (`Rule`, `RoutingEngine`) fica identico.

**Impacto no roadmap**: epic 006 (Configurable Routing DB) fica drasticamente menor porque este epic ja entrega engine completo. Epic 009 (Admin Panel) ganha modelo pronto. Epic 005 (Conversation Core) deixa de hardcodar `tenant.settings.default_agent_id` — consome `Decision.agent_id` direto.

## Applicable Constraints

| Constraint | Source | Impact |
|-----------|--------|--------|
| Multi-tenant RLS obrigatorio em toda tabela de dados | ADR-011 | Quando epic 006 migrar YAML → DB, `routing_rules` table herda RLS policy |
| Config nunca em codigo | ADR-017 | Justificativa primaria do epic: regras saem do codigo |
| pydantic 2 como base de modelagem | ADR-001, blueprint §1 | Discriminated union nativo, validators cross-field |
| Sans-I/O no core domain | blueprint §4.6 | `classify()` sync e puro; I/O apenas no caller |
| Observabilidade estruturada (structlog) | blueprint §4.4 | `Decision.matched_rule` entra em todo log do webhook |
| Python 3.12+ | blueprint §1 | `match/case` exhaustiveness via mypy/pyright |
| ruff strict + mypy strict | blueprint §5 | Discriminated union + enums dao exhaustiveness gratis |
| Config versionada | blueprint §2.2 | YAML commitado no repo externo, PR-reviewable |
| Domain-model define Router aggregate com classify + resolve | domain-model.md linhas 88-96 | Codigo passa a refletir o domain model que ja existia so no papel |
| Hit policy UNIQUE (DMN 1.3) | Benchmark externo (referencia Q1) | Loader rejeita overlap nao-declarado |

## Suggested Approach

1. **Scaffold + tipos Layer 1** — `facts.py` com `MessageFacts`, enums, `StateSnapshot`, invariantes `__post_init__`. Zero logica de routing ainda. Testes unitarios do dataclass.
2. **`classify()` puro** — migrar logica do `route_message()` atual quebrando por fato. Cada `if` vira campo de `MessageFacts`. Testes com payloads reais da fixture `tests/fixtures/evolution_payloads.json` (reusar do epic 001).
3. **Tipos Layer 2** — `Action` enum, 5 subtipos de `Decision` (discriminated union), `Rule` dataclass. Testes de exhaustiveness do `match/case` via snapshot de mypy/pyright.
4. **`RoutingEngine.decide()`** — iteracao por priority ASC, agent resolution (rule → tenant default → RoutingError). Testes com fixture programatica.
5. **Loader YAML** — pydantic model do `RoutingConfig`, validators (default obrigatorio, priority unico, campos conhecidos, action valida). Testes de rejeicao.
6. **Overlap analysis** — `rules_can_overlap()` + integracao no loader. Testes com configs propositalmente sobrepostas.
7. **Property tests** — enumeracao exaustiva + Hypothesis + reachability-per-instance.
8. **CLI** — `prosauai router verify|explain` usando typer ou argparse. Testes de integracao.
9. **Fixture YAML** — `config/routing/pace-automations.yaml` cobrindo todos os casos do epic 001 (7+ regras).
10. **Migracao `webhooks.py`** — trocar chamada + carregamento de `RoutingEngine` no lifespan + `StateSnapshot.load()` no request. Rip-and-replace do enum legado.
11. **Pre-commit hook** — `router verify` em `config/routing/*.yaml` no repo externo.
12. **Docs** — atualizar `business/process.md` (Fase B real) + `engineering/domain-model.md` (Router aggregate com classify+decide) + decisions.md.

> **Proximo passo:** aguardar promocao via `/madruga:epic-context prosauai 004-router-mece` (draft → in_progress, cria branch `epic/prosauai/004-router-mece`, faz delta review). Antes da promocao: validar que epic 002 (Observability) e epic 003 (TBD) estao shippados para nao cascatear.
