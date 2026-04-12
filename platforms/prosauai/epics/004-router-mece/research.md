# Research — Epic 004: Router MECE

**Date**: 2026-04-10
**Epic**: 004-router-mece
**Branch**: `epic/prosauai/004-router-mece`

---

## R1 — Arquitetura de Decision Tables com Hit Policy UNIQUE

### Contexto

O router precisa garantir que toda mensagem casa com exatamente 1 regra (MECE). O padrao DMN 1.3 define "hit policy UNIQUE" como: para qualquer input, no maximo 1 regra pode casar; se nenhuma casa, o default se aplica.

### Decisao

Implementar verificacao estatica pairwise no loader: para cada par de regras `(Ri, Rj)`, verificar se existe alguma combinacao valida de `MessageFacts` que satisfaz ambas as condicoes. Se sim, rejeitar a configuracao no load-time.

### Rationale

- Verificacao estatica no load-time e mais forte que verificacao dinamica no runtime (pega erros antes de processar mensagens).
- O espaco de predicados e finito e pequeno (~400 combinacoes validas de enums+bools), entao enumeracao exaustiva e viavel.
- DMN 1.3 UNIQUE e exatamente o que queremos: zero ambiguidade, zero cascata.

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Verificacao pairwise no loader (escolhida)** | Pega overlaps antes de servir trafico; exaustiva; O(n²) com n < 50 e trivial | Requer enumeracao de facts validos | ✅ Escolhida |
| **B. Priority-based com first-match (sem overlap check)** | Simples; sem analise estatica | Silencia bugs — duas regras podem casar mas so a primeira ganha; dev nao sabe que a segunda e morta | ❌ Rejeitada |
| **C. Expression language (jsonlogic/CEL) para condicoes** | Expressividade ilimitada; suporta OR/NOT/regex | Overlap analysis indecidivel com expressoes arbitrarias; complexidade desnecessaria para < 50 regras | ❌ Rejeitada |
| **D. Overrides escape hatch para overlap intencional** | Flexivel para edge cases | Quebra garantia MECE; testes de propriedade ficam fracos | ❌ Rejeitada |

### Fontes

- OMG DMN 1.3 Specification §8.3 — Hit Policy (Tabela de Decisao): hit policies UNIQUE, FIRST, PRIORITY, COLLECT, etc.
- Bernhardt, Gary — "Boundaries" (2012) + "Functional Core, Imperative Shell" — pattern de separacao pure/impure que guia classify() vs route()
- h11 (Python HTTP/1.1 sans-I/O library) — referencia de implementacao do padrao sans-I/O

---

## R2 — Discriminated Unions em Pydantic 2.x

### Contexto

O `Decision` retornado pelo router precisa ser um de 5 subtipos (Respond, LogOnly, Drop, BypassAI, EventHook), cada um com campos diferentes. O consumidor (`webhooks.py`) precisa tratar todos os 5 exaustivamente.

### Decisao

Usar `Annotated[Union[...], Field(discriminator="action")]` do pydantic 2.x. Cada subtipo declara `action: Literal[Action.XXX]` como campo discriminador. Consumidores usam `match/case` com type narrowing.

### Rationale

- Pydantic 2.x suporta discriminated unions nativamente com zero overhead de serialization.
- `match/case` do Python 3.12 + mypy/pyright provam exaustividade em compile-time.
- Cada subtipo carrega apenas campos validos para aquela acao — elimina classe de bugs "acessar agent_id em DropDecision".

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Discriminated union pydantic (escolhida)** | Type-safe; exhaustiveness provada; serialization gratis | Requer pydantic 2.x (ja no stack) | ✅ Escolhida |
| **B. Enum + dataclass com campos opcionais** | Simples | Campos invalidos acessiveis; exhaustiveness nao provada | ❌ Rejeitada |
| **C. Visitor pattern / double dispatch** | OOP classico | Boilerplate excessivo; Python nao tem interfaces de visitor | ❌ Rejeitada |

---

## R3 — Property-Based Testing para Exhaustiveness MECE

### Contexto

Precisamos provar que TODA combinacao valida de `MessageFacts` casa com exatamente 1 regra em cada configuracao de tenant.

### Decisao

Abordagem em 3 camadas de teste:

1. **Enumeracao exaustiva**: gerar todas as ~400 combinacoes validas do produto cartesiano `Channel × EventKind × ContentKind × bool × bool × ... ` (filtrando as combinacoes invalidas pelos invariantes do `__post_init__`). Para cada combinacao, assertar `len(matches) == 1` contra cada fixture YAML real.

2. **Hypothesis para campos livres**: `instance`, `sender_phone`, `group_id` sao strings livres — usar `@given(st.text())` para gerar valores arbitrarios e verificar que nao afetam a unicidade do match.

3. **Reachability test por instance**: para cada regra que filtra por `instance` especifico, verificar que existe ao menos 1 combinacao de facts que a atinge (detecta "shadow rules" — regras que nunca matcham porque uma wildcard as precede).

### Rationale

- Enumeracao completa e possivel porque o espaco de enums e finito (2 × 5 × 5 × 2^N bools, filtrado).
- Hypothesis complementa cobrindo campos de string livre que enumeracao nao cobre.
- Reachability e o inverso da uniqueness — garante que nao ha regras mortas.

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Enumeracao + Hypothesis + Reachability (escolhida)** | Cobertura completa em 3 eixos | Mais codigo de teste | ✅ Escolhida |
| **B. Apenas testes manuais com exemplos** | Simples | Nao cobre o espaco todo; risco de gaps | ❌ Rejeitada |
| **C. Formal verification (Z3/SMT solver)** | Matematicamente perfeito | Overkill para < 50 regras; dependencia pesada | ❌ Rejeitada |

---

## R4 — Sans-I/O Pattern para classify()

### Contexto

`classify()` precisa ser pura (sem I/O) para testabilidade e determinismo. Porem, precisa de dados que vem do Redis (duplicata + handoff state) e de config do tenant (mention matchers).

### Decisao

Adotar o pattern de h11/urllib3: I/O e feito pelo "shell" (caller), dados puros sao passados como parametros para o "core" (classify). Concretamente:

- `StateSnapshot.load(redis, ...)` — async, faz MGET no Redis, retorna dataclass frozen
- `MentionMatchers.from_tenant(tenant)` — sync, constroi value object uma vez no startup
- `classify(message, state, matchers)` — sync, puro, deterministic

### Rationale

- Testabilidade: `classify()` e testavel sem mocks de Redis
- Performance: MGET unico (2 keys) vs N chamadas separadas
- Composabilidade: state e matchers sao injetados, nao importados de globals

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Sans-I/O com StateSnapshot pre-carregado (escolhida)** | Puro; testavel; 1 MGET atomico | Caller precisa chamar `StateSnapshot.load()` | ✅ Escolhida |
| **B. classify() async com Redis interno** | Encapsula I/O | Impuro; requer mocks em todo teste; mais dificil de raciocinar | ❌ Rejeitada |
| **C. Repository pattern com interface** | Abstrai storage | Over-engineering para 2 keys Redis; boilerplate | ❌ Rejeitada |

---

## R5 — Overlap Analysis: Algoritmo de Verificacao

### Contexto

Para cada par de regras, precisamos verificar se existe alguma `MessageFacts` que satisfaz ambas as condicoes `when`. Se sim, ha overlap e a config e invalida.

### Decisao

Algoritmo de verificacao por satisfatibilidade conjuntiva:

```python
def rules_can_overlap(r1: Rule, r2: Rule, valid_facts: list[MessageFacts]) -> bool:
    """Verifica se existe algum MessageFacts valido que casa com ambas as regras."""
    for facts in valid_facts:
        if r1.matches(facts) and r2.matches(facts):
            return True
    return False
```

Como o espaco e pequeno (~400 combinacoes), iteracao linear e eficiente. Para N regras, o numero de pares e O(N²/2); com N < 20 e 400 facts, sao ~36.000 avaliacoes — microsegundos.

### Rationale

- Simples, correto, e rapido o suficiente
- Reutiliza a lista de `valid_facts` ja gerada para os property tests
- Nao requer solver externo

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Enumeracao de facts + match pairwise (escolhida)** | Simples; correto; reusa valid_facts | O(N² × F) — mas N < 20, F < 400 | ✅ Escolhida |
| **B. Analise simbolica das condicoes when** | Nao precisa enumerar facts | Complexa; precisa resolver negacoes e wildcards | ❌ Rejeitada |
| **C. SMT solver (Z3)** | Matematicamente perfeito | Dependencia externa pesada; overkill | ❌ Rejeitada |

---

## R6 — Estrategia de Migracao: Rip-and-Replace vs Compat Layer

### Contexto

O router legado (`MessageRoute` enum, `route_message()`, `_is_bot_mentioned()`, `_is_handoff_ativo()`) precisa ser substituido pelo novo sistema. Duas abordagens possiveis.

### Decisao

Rip-and-replace no mesmo PR. Remover completamente o enum e funcoes legadas; atualizar todos os consumers (`webhooks.py`, testes) para usar o novo `route()` + `Decision` discriminated union.

### Rationale

- Zero consumers externos — tudo vive em `webhooks.py` e testes
- Compat layer so acumularia divida tecnica e criaria ambiguidade sobre qual path e o "real"
- As 26 fixtures reais do 003 servem como regression suite — se passam, o refactor e seguro

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Rip-and-replace (escolhida)** | Limpo; sem ambiguidade; divida zero | Requer que todos os testes migrem de uma vez | ✅ Escolhida |
| **B. Compat layer (novo chama antigo)** | Migracao gradual | Dois paths; bugs em qual usar; testes ficam confusos | ❌ Rejeitada |
| **C. Feature flag para toggle old/new** | Rollback facil | Complexidade de flag para router que e deterministic | ❌ Rejeitada |

---

## R7 — Schema YAML: Expressividade das Condicoes `when`

### Contexto

As regras de roteamento definem condicoes `when` que casam contra `MessageFacts`. Qual nivel de expressividade o `when` deve suportar?

### Decisao

Apenas **igualdade + conjuncao**. Cada campo em `when` e comparado por igualdade com o campo correspondente de `MessageFacts`; todos os campos devem casar (AND). Campos ausentes no `when` sao wildcards (match qualquer valor).

### Rationale

- Overlap analysis e decidivel e trivial com igualdade + conjuncao
- Admin panel (epic 009) vira form com dropdowns, sem parser de expressoes
- Casos que pareceriam precisar de OR (ex: "individual OU grupo com mention") viram 2 rows no YAML
- Regras reais do prosauai nunca precisaram de NOT/regex — empirico

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. Igualdade + conjuncao (escolhida)** | Overlap decidivel; admin trivial; 2 rows resolve OR | Menos expressiva | ✅ Escolhida |
| **B. JsonLogic** | Expressividade total (OR, NOT, comparacoes) | Overlap indecidivel; admin precisa de editor de expressoes; dependencia | ❌ Rejeitada |
| **C. CEL (Common Expression Language)** | Boa DX; tipada | Dependencia Go ou reimplementacao; overlap indecidivel | ❌ Rejeitada |
| **D. Regex/glob nos campos** | Flexivel para patterns | Overlap analysis muito mais complexa; overkill para enums | ❌ Rejeitada |

---

## R8 — Observabilidade: Spans vs Events para Classify/Decide

### Contexto

O router atual emite 1 span `route_message`. O novo router tem 2 fases distintas (classify + decide). Como instrumentar?

### Decisao

2 spans irmaos (`router.classify` + `router.decide`) sob o span pai `webhook_whatsapp`. Nao spans aninhados — sao operacoes sequenciais, nao pai-filho.

### Rationale

- OTel guidance: operacoes com duracao e failure mode independentes = spans, nao events
- Spans irmaos permitem medir latencia de cada fase separadamente no Phoenix
- Se `classify` falha, `decide` nao roda — failure isolation
- Events (span events) nao aparecem como nodos no waterfall do Phoenix — perde-se visibilidade

### Alternativas Consideradas

| Alternativa | Pros | Contras | Veredito |
|-------------|------|---------|----------|
| **A. 2 spans irmaos (escolhida)** | Waterfall correto; per-stage latency; failure isolation | 2× overhead de span creation (~microsegundos) | ✅ Escolhida |
| **B. 1 span unico enriquecido com events** | Menos spans | Conflata falhas classify vs decide; perde per-stage latency | ❌ Rejeitada |
| **C. 2 spans aninhados (pai-filho)** | Hierarquia explicita | Classify nao e "filho" de decide — sao sequenciais | ❌ Rejeitada |

---

## Unknowns Resolvidos

| # | Unknown Original | Resolucao |
|---|------------------|-----------|
| 1 | Como implementar hit policy UNIQUE em Python? | Enumeracao pairwise no loader (R1) |
| 2 | Como serializar Decision com 5 subtipos? | Discriminated union pydantic 2.x (R2) |
| 3 | Como provar MECE exaustivamente? | Enumeracao + Hypothesis + reachability (R3) |
| 4 | Como manter classify() pura com dados Redis? | Sans-I/O: StateSnapshot pre-carregado (R4) |
| 5 | Como detectar overlap entre regras? | Enumeracao de facts + match pairwise (R5) |
| 6 | Rip-and-replace ou compat layer? | Rip-and-replace, 26 fixtures como regression (R6) |
| 7 | Qual expressividade no `when`? | Igualdade + conjuncao apenas (R7) |
| 8 | Spans ou events para classify/decide? | 2 spans irmaos (R8) |

---

## NEEDS CLARIFICATION Residuais

Nenhum. Todos os unknowns foram resolvidos pelo deep-dive do epic-context + clarificacoes do spec.
