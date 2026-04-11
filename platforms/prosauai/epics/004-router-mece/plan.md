# Implementation Plan: Router MECE — Classificação Pura + Regras Externalizadas + Agent Resolution

**Branch**: `epic/prosauai/004-router-mece` | **Date**: 2026-04-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/004-router-mece/spec.md`

## Summary

Refatorar o router do prosauai separando classificação de mensagens (fatos puros, sync, sem I/O) de regras de roteamento (configuração YAML externa por tenant). Resolver `agent_id` que está sempre None desde o epic 001. Garantir propriedade MECE por construção em 4 camadas: tipo (enums + invariantes), schema (loader pydantic rejeita overlap), runtime (discriminated union exaustiva), CI (property tests enumeram todas as combinações válidas).

## Technical Context

**Language/Version**: Python 3.12 (match/case, StrEnum nativo)
**Primary Dependencies**: FastAPI >=0.115, pydantic 2.x, redis[hiredis] >=5.0, httpx, structlog, opentelemetry-sdk, hypothesis (dev)
**Storage**: Redis 7 (state lookup: seen + handoff keys), YAML em disco (routing config)
**Testing**: pytest + hypothesis (property-based), pytest-asyncio (async Redis mocks)
**Target Platform**: Linux server (prosauai-api container)
**Project Type**: Web service (FastAPI webhook handler)
**Performance Goals**: `route()` < 5ms p99 (classify <1ms + decide <1ms + Redis MGET ~2-3ms)
**Constraints**: Zero downtime para tenants existentes; backward-compatible com 26 fixtures reais do epic 003
**Scale/Scope**: 2 tenants reais (Ariel + ResenhAI), < 20 regras por tenant, ~400 combinações válidas de MessageFacts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Evidência |
|-----------|--------|-----------|
| **I. Pragmatism Above All** | ✅ PASS | Solução mais simples que funciona: igualdade + conjunção nas regras, sem expression language. Performance-aware: MGET único no Redis. |
| **II. Automate Repetitive Tasks** | ✅ PASS | CLI `router verify\|explain` automatiza validação de config. Pre-commit hook automatiza CI. |
| **IV. Fast Action Over Excessive Planning** | ✅ PASS | Rip-and-replace (sem compat layer). TDD: 95+ testes. Property tests como rede de segurança para iterar rápido. |
| **V. Alternatives and Trade-offs** | ✅ PASS | 8 decisões de research com alternativas documentadas em `research.md`. Cada decisão tem ≥2 alternativas. |
| **VI. Brutal Honesty** | ✅ PASS | `conversation_in_handoff` marcado como contrato aberto — honesto sobre o gap. `default_agent_id` fecha drift doc/code. |
| **VII. TDD** | ✅ PASS | Tipos e invariantes primeiro (T3-T4), testes de classificação antes de classify() (T5), property tests antes de integração (T12-T14). |
| **VIII. Collaborative Decision Making** | ✅ PASS | 21 decisões documentadas no epic-context com alternativas. Deep-dive com usuário no 2026-04-10. |
| **IX. Observability and Logging** | ✅ PASS | 2 spans OTel (classify + decide) + 6 novas constantes + `matched_rule` em todo log estruturado. |

**Violations**: Nenhuma.

### Constitution Re-Check (Post Phase 1)

| Princípio | Status | Evidência Atualizada |
|-----------|--------|---------------------|
| **I. Pragmatism** | ✅ PASS | Data model usa dataclasses frozen (stdlib) + pydantic (já no stack). Zero dependências novas em prod. |
| **VII. TDD** | ✅ PASS | Data model define entidades testáveis isoladamente. Cada entidade tem testes unitários antes da integração. |
| **IX. Observability** | ✅ PASS | Constantes OTel definidas no data model (6 novos atributos flat em `conventions.py`). |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/004-router-mece/
├── plan.md              # This file
├── research.md          # Phase 0 output — 8 research decisions
├── data-model.md        # Phase 1 output — 8 entidades + relações
├── quickstart.md        # Phase 1 output — setup + verificação + testes
├── contracts/
│   └── router-api.md    # Phase 1 output — public API + YAML schema + CLI
└── tasks.md             # Phase 2 output (gerado por /speckit.tasks)
```

### Source Code (repository externo: paceautomations/prosauai)

```text
prosauai/
├── core/
│   ├── router/                    # NOVO — módulo completo do router MECE
│   │   ├── __init__.py            # Public API: route(), re-exports
│   │   ├── facts.py               # Channel, EventKind, ContentKind, MessageFacts, classify()
│   │   ├── matchers.py            # MentionMatchers value object
│   │   ├── engine.py              # Action, Decision subtypes, Rule, RoutingEngine
│   │   ├── loader.py              # YAML loader, pydantic schema, overlap analysis
│   │   ├── verify.py              # CLI: router verify | explain
│   │   └── errors.py              # RoutingError, RoutingConfigError, AgentResolutionError
│   ├── inbound.py                 # RENOMEADO de formatter.py (ParsedMessage → InboundMessage)
│   │                              # Nota: arquivo pode manter nome formatter.py com classe renomeada
│   ├── tenant.py                  # MODIFICADO — +default_agent_id: UUID | None = None
│   ├── tenant_store.py            # MODIFICADO — _build_tenant lê default_agent_id
│   ├── router.py                  # REMOVIDO — enum MessageRoute, route_message(), helpers
│   ├── debounce.py                # INTOCADO
│   └── idempotency.py             # INTOCADO
├── observability/
│   └── conventions.py             # MODIFICADO — +6 constantes (MATCHED_RULE, etc.)
├── api/
│   ├── webhooks.py                # MODIFICADO — usa route() + match/case Decision
│   └── dependencies.py            # INTOCADO
└── main.py                        # MODIFICADO — lifespan carrega engines + matchers

config/
└── routing/
    ├── ariel.yaml                 # NOVO — 9 regras para tenant Ariel (pace-internal)
    └── resenhai.yaml              # NOVO — N regras para tenant ResenhAI (resenha-internal)

tests/
├── unit/
│   ├── test_facts.py              # NOVO — MessageFacts + classify() (15+ testes)
│   ├── test_matchers.py           # NOVO — MentionMatchers (6+ testes)
│   ├── test_engine.py             # NOVO — RoutingEngine + Decision (10+ testes)
│   ├── test_loader.py             # NOVO — YAML loader + overlap (15+ testes)
│   ├── test_mece_exhaustive.py    # NOVO — property tests exaustivos (enumeração + hypothesis)
│   ├── test_mece_reachability.py  # NOVO — reachability por instance (shadow rules)
│   ├── test_verify.py             # NOVO — CLI integration (6+ testes)
│   ├── test_tenant.py             # MODIFICADO — +1 teste default_agent_id
│   ├── test_tenant_store.py       # MODIFICADO — +1 teste loader lê UUID
│   ├── test_conventions.py        # MODIFICADO — valida novas constantes
│   └── test_router.py             # REMOVIDO ou SUBSTITUÍDO pelos novos testes granulares
├── integration/
│   └── test_captured_fixtures.py  # MODIFICADO — TEST_TENANTS +default_agent_id, equivalência
└── fixtures/
    └── captured/                  # INTOCADO — 26 fixtures reais do epic 003
```

**Structure Decision**: Módulo `prosauai/core/router/` como package (não arquivo único) porque contém 7 arquivos com responsabilidades distintas. Separação por camada (facts/engine/loader/verify) alinha com a arquitetura em 2 layers do pitch.

## Complexity Tracking

> Nenhuma violação de constituição encontrada. Tabela vazia.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Design Decisions (Phase 1)

### D1 — `classify()` como função pura (sans-I/O)

**Escolha**: `classify(message, state, matchers) -> MessageFacts` — sync, sem efeitos colaterais, determinística.

**Alternativas**:
1. ✅ **Função pura com StateSnapshot injetado** — testável sem mocks; 1 MGET no caller
2. ❌ **Função async com Redis interno** — impura; requer mocks em todo teste
3. ❌ **Repository pattern** — over-engineering para 2 keys Redis

**Justificativa**: Pattern h11/urllib3 (sans-I/O). I/O fica no shell (caller), computação pura no core. Testabilidade é prioridade (Constitution VII).

### D2 — Decision como discriminated union (5 subtipos)

**Escolha**: `Annotated[Union[Respond, LogOnly, Drop, BypassAI, EventHook], Field(discriminator="action")]`

**Alternativas**:
1. ✅ **Discriminated union pydantic 2.x** — type-safe; exhaustiveness provada; serialization grátis
2. ❌ **Enum + dataclass com campos opcionais** — campos inválidos acessíveis; sem exhaustiveness
3. ❌ **Visitor pattern** — boilerplate excessivo em Python

**Justificativa**: mypy/pyright provam que `match/case` em `webhooks.py` trata todos os 5 subtipos. Elimina bug "acessar agent_id de DropDecision".

### D3 — Overlap analysis pairwise no loader

**Escolha**: Enumerar ~400 MessageFacts válidos; para cada par de regras, verificar se algum fato casa com ambas.

**Alternativas**:
1. ✅ **Enumeração + match pairwise** — simples, correto, rápido (O(N² × F) com N<20, F<400)
2. ❌ **Análise simbólica das condições** — complexa; precisa resolver negações e wildcards
3. ❌ **SMT solver (Z3)** — dependência pesada; overkill para <50 regras

**Justificativa**: Espaço de predicados é finito e pequeno. Iteração linear é microsegundos.

### D4 — Igualdade + conjunção nas condições `when`

**Escolha**: Cada campo em `when` comparado por igualdade. Todos devem casar (AND). Campos ausentes = wildcard.

**Alternativas**:
1. ✅ **Igualdade + conjunção** — overlap decidível; admin trivial; OR vira 2 rows
2. ❌ **JsonLogic** — overlap indecidível; dependência; admin precisa de editor
3. ❌ **CEL** — dependência Go; overlap indecidível
4. ❌ **Regex/glob** — overlap analysis muito mais complexa

**Justificativa**: Regras reais do prosauai nunca precisaram de NOT/regex. 2 rows no YAML resolvem o OR.

### D5 — 2 spans irmãos para classify + decide

**Escolha**: `router.classify` + `router.decide` como spans irmãos sob `webhook_whatsapp`.

**Alternativas**:
1. ✅ **2 spans irmãos** — waterfall correto; per-stage latency; failure isolation
2. ❌ **1 span único enriquecido** — conflata falhas; perde per-stage latency
3. ❌ **2 spans aninhados (pai-filho)** — classify não é "filho" de decide

**Justificativa**: OTel guidance: operações com duração/failure mode independentes = spans.

### D6 — Rip-and-replace do router legado

**Escolha**: Remover enum `MessageRoute`, `route_message()`, `_is_bot_mentioned()`, `_is_handoff_ativo()` no mesmo PR.

**Alternativas**:
1. ✅ **Rip-and-replace** — limpo; sem ambiguidade; 26 fixtures como regression
2. ❌ **Compat layer** — dois paths; bugs em qual usar
3. ❌ **Feature flag** — complexidade para router determinístico

**Justificativa**: Zero consumers externos. Tudo vive em `webhooks.py` e testes.

### D7 — MentionMatchers como value object frozen

**Escolha**: `MentionMatchers` frozen dataclass construído uma vez no lifespan, passado como 3o param de `classify()`.

**Alternativas**:
1. ✅ **Value object frozen** — puro; cached; reutilizável
2. ❌ **FactExtractor stateful** — impuro; fragmenta definição de "mention"
3. ❌ **Pre-compute has_mention no caller** — fragmenta lógica entre webhooks.py e router

**Justificativa**: Bernhardt FCIS: "configuration values gathered in the shell and passed as parameters to pure functions".

### D8 — `default_agent_id` flat no Tenant

**Escolha**: `default_agent_id: UUID | None = None` como campo aditivo flat no `Tenant` dataclass.

**Alternativas**:
1. ✅ **Campo flat** — type-safe; backward-compatible; aditivo
2. ❌ **Settings JSONB nested** — perde type-safety no startup; domain-model promete mas 003 não shipou
3. ❌ **Obrigar toda regra RESPOND declarar agent** — cópia redundante de UUID; fere DMN defaults

**Justificativa**: Flat é type-safe. Quando epic 013 migrar para Postgres, settings JSONB vira colunas tipadas.

## Implementation Phases

### Phase 0: Research ✅

Todos os unknowns resolvidos em `research.md`:
- R1: Hit policy UNIQUE via enumeração pairwise
- R2: Discriminated union pydantic 2.x
- R3: Property tests (enumeração + Hypothesis + reachability)
- R4: Sans-I/O pattern para classify()
- R5: Overlap analysis por enumeração de facts
- R6: Rip-and-replace (sem compat layer)
- R7: Igualdade + conjunção nas condições
- R8: 2 spans irmãos (classify + decide)

### Phase 1: Design & Contracts ✅

Artefatos gerados:
- `data-model.md` — 8 entidades com relações e mapeamento legado→novo
- `contracts/router-api.md` — public API, YAML schema, CLI, error types, integration points
- `quickstart.md` — setup, verificação, testes, uso programático

### Phase 2: Tasks (próximo passo)

Gerado por `/speckit.tasks` — quebra do plano em tarefas ordenadas por dependência.

## Sequência de Implementação (Visão Geral)

```mermaid
graph LR
    T0[T0 Rename<br/>ParsedMessage→InboundMessage] --> T2[T2 Scaffold<br/>router/ module]
    T1[T1 Add<br/>default_agent_id] --> T9

    T2 --> T3[T3 MessageFacts<br/>+ enums + invariantes]
    T2 --> T8[T8 Decision<br/>subtypes]

    T3 --> T4[T4 MentionMatchers<br/>value object]
    T3 --> T5[T5 classify()<br/>puro]
    T3 --> T6[T6 StateSnapshot<br/>+ load()]

    T4 --> T5
    T6 --> T5

    T8 --> T7[T7 Rule<br/>+ matches()]
    T7 --> T9[T9 RoutingEngine<br/>decide()]

    T5 --> T10[T10 YAML loader<br/>+ pydantic]
    T9 --> T10

    T10 --> T11[T11 Overlap<br/>analysis]
    T10 --> T12[T12 Property test<br/>exaustivo]
    T11 --> T12

    T12 --> T13[T13 Hypothesis<br/>campos livres]
    T12 --> T14[T14 Reachability<br/>shadow rules]

    T10 --> T15[T15 CLI verify]
    T10 --> T16[T16 CLI explain]

    T5 --> T17[T17 OTel<br/>constantes]
    T9 --> T18[T18 Migrar<br/>webhooks.py]
    T17 --> T18

    T10 --> T19[T19 Migrar<br/>main.py lifespan]
    T18 --> T19

    T10 --> T20[T20 ariel.yaml]
    T10 --> T21[T21 resenhai.yaml]

    T20 --> T22[T22 Pre-commit<br/>hook]
    T21 --> T22

    T18 --> T23[T23 Fixture<br/>equivalence]

    T23 --> T24[T24 Update<br/>process.md]
    T23 --> T25[T25 Update<br/>domain-model.md]
    T23 --> T26[T26 Remove<br/>legado]
    T26 --> T27[T27 Update<br/>test_router.py]
```

## Estimativa de Esforço

| Grupo | Tasks | LOC Prod (est.) | LOC Test (est.) | Complexidade |
|-------|-------|----------------|----------------|-------------|
| Rename + Scaffold | T0, T2 | ~50 | ~20 | Baixa |
| Tenant extension | T1 | ~10 | ~20 | Baixa |
| Layer 1 (Facts) | T3, T4, T5, T6 | ~300 | ~250 | Média |
| Layer 2 (Engine) | T7, T8, T9 | ~200 | ~200 | Média |
| Loader + Validation | T10, T11 | ~250 | ~200 | Alta |
| Property Tests | T12, T13, T14 | — | ~200 | Média |
| CLI | T15, T16 | ~100 | ~60 | Baixa |
| OTel + Migration | T17, T18, T19 | ~150 | ~80 | Média |
| Config + Hook | T20, T21, T22 | ~100 | ~30 | Baixa |
| Fixtures + Cleanup | T23, T26, T27 | ~50 | ~100 | Média |
| Docs | T24, T25 | — | — | Baixa |
| **Total** | **28 tasks** | **~1210 LOC** | **~1160 LOC** | — |

> Nota: estimativas LOC multiplicadas por 1.5x (CLAUDE.md gotcha — docstrings, argparse, logging).

## Riscos e Mitigações

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|-------|---------------|---------|-----------|
| 1 | Overlap analysis falso-positivo em guards universais | Média | Alto | Escrever teste unitário do overlap checker com casos exemplares ANTES de escrever o checker (T11) |
| 2 | Discriminated union serialization com structlog | Baixa | Médio | Validar `model_dump()` em teste de integração (T18) |
| 3 | 26 fixtures do 003 não produzem equivalência exata | Baixa | Alto | Mapear cada `MessageRoute` para `Action` equivalente; rodar equivalência como primeiro teste (T23) |
| 4 | `conversation_in_handoff` sempre False (sem escritor) | Esperado | Baixo | Documentar como contrato aberto; teste explícito do fallback (T6) |
| 5 | Tenant YAML sem `default_agent_id` + regra RESPOND sem agent | Média | Médio | `RoutingError` em runtime + `router verify --tenant` detecta (T9, T15) |

## Dependências Externas

| Dependência | Status | Impacto se Indisponível |
|-------------|--------|------------------------|
| Redis 7 | ✅ Disponível (epic 003) | `StateSnapshot.load()` falha → fail-fast |
| OTel + Phoenix | ✅ Disponível (epic 002) | Spans não emitidos — funcional sem observabilidade |
| 26 fixtures reais | ✅ Disponível (epic 003) | Regression suite não roda — blocker para merge |
| hypothesis (dev) | ✅ Disponível (pip) | Property tests não rodam — não bloqueia funcionalidade |

---
handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plano completo com 28 tasks, 8 research decisions, data model com 8 entidades, contracts com public API + YAML schema + CLI. Estimativa: ~1210 LOC prod + ~1160 LOC test. Pronto para quebra em tasks ordenadas por dependência."
  blockers: []
  confidence: Alta
  kill_criteria: "Se as 26 fixtures reais do epic 003 não puderem ser mapeadas para o novo sistema de decisions (equivalência comportamental impossível), ou se o espaço de MessageFacts válidos explodir além de ~1000 combinações tornando a enumeração exaustiva inviável."
