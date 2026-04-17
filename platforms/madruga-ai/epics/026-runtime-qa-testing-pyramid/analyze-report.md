# Relatório de Análise Pré-Implementação: Runtime QA & Testing Pyramid

**Epic**: 026-runtime-qa-testing-pyramid  
**Gerado por**: `speckit.analyze` (pre-implementation pass)  
**Data**: 2026-04-16  
**Status**: Leitura-apenas — nenhum arquivo foi modificado

---

## Sumário Executivo

Os três artefatos principais (spec.md, plan.md, tasks.md) estão internamente coerentes e prontos para implementação. **Nenhum CRITICAL encontrado.** Há 2 achados HIGH que merecem resolução antes de implementar (ou documentação de decisão consciente): o campo `requires_auth: true` declarado no schema de prosauai sem qualquer FR ou tarefa de implementação, e a ordem das tarefas em Phase 1 que viola o princípio TDD da constituição. Os 3 achados MEDIUM afetam a completude do scaffold Copier, a ambiguidade de exit codes, e a confiabilidade do `$REPO_ROOT` em contextos de execução variados.

---

## Tabela de Achados

| ID | Categoria | Severity | Localização | Resumo | Recomendação |
|----|-----------|----------|-------------|--------|--------------|
| H1 | Underspecification | HIGH | tasks.md:T017, platform.yaml (prosauai) | Campo `requires_auth: true` declarado no schema de `URLEntry` (plan.md Phase 2, platform.yaml prosauai) sem nenhum FR correspondente e nenhuma tarefa de implementação. O campo será gravado no YAML mas `validate_urls` (T009) não tem instrução sobre como tratar URLs autenticadas. | Ou (A) adicionar FR-024 + T009b cobrindo skip/warn para URLs `requires_auth: true` com instruções claras (ex.: testar apenas reachability sem assertar conteúdo), ou (B) remover o campo `requires_auth: true` de platform.yaml de prosauai e do schema de URLEntry até que a funcionalidade seja especificada. |
| H2 | Constitution Alignment | HIGH | tasks.md:T001–T012 | Constituição Princípio VII (TDD): "Write tests before implementation — Red-Green-Refactor". T001–T011 implementam TODO o código de produção de qa_startup.py (11 tarefas) antes de T012 criar qualquer teste. A header do tasks.md menciona "TDD para `qa_startup.py`" mas a ordem de tarefas é GREEN-GREEN, não RED-GREEN-REFACTOR. | Reestruturar Phase 1 intercalando implementação e teste por função: T001 (skeleton), T002+T012a (load_manifest + test_load_manifest), T003+T012b (parse_journeys + test_parse_journeys), etc. Alternativa: adicionar nota explícita declarando que TDD aqui significa "testes escritos junto com cada função iterativamente durante T001–T011, com T012 consolidando a suite" — e atualizar o texto de T001–T011 para mencionar testes unitários inline. |
| M1 | Underspecification | MEDIUM | tasks.md:T017 | T017 atualiza `.specify/templates/platform/template/platform.yaml.jinja` com condicional `{%- if testing_startup_type is defined %}`, mas nenhuma tarefa atualiza `copier.yaml` para adicionar a pergunta `testing_startup_type` ao wizard do Copier. Sem a pergunta no copier.yaml, a variável nunca será definida e o bloco de template nunca será renderizado em plataformas novas. | Adicionar sub-tarefa a T017: atualizar `.specify/templates/platform/copier.yaml` com a pergunta `testing_startup_type` (choices: none/docker/npm/make/script, default: none). |
| M2 | Ambiguity | MEDIUM | tasks.md:T011, T025 | T011 define exit code 2 = "config error" para `qa_startup.py`. T025 usa `exit code 2` para detectar "testing: block ausente" e fazer skip silencioso para o comportamento atual do QA. Porém "config ausente" (estado normal para plataformas sem testing:) e "config malformado" (erro real) retornam o mesmo exit code 2 — o QA não consegue distinguir entre os dois casos. Um config malformado seria silenciosamente ignorado em vez de reportar erro. | Diferenciar exit codes: 0 = ok/warn, 1 = blocker, 2 = testing: absent (sem config), 3 = config error (malformed), 4 = unexpected. Atualizar T011 e T025 com esta distinção. |
| M3 | Underspecification | MEDIUM | tasks.md:T021–T030 | As edições em skill files (T021–T030) inserem referências a `$REPO_ROOT` como variável bash em blocos de código dentro de qa.md. A variável `$REPO_ROOT` é usada por outros scripts do pipeline (implement_remote.py, dag_executor.py) mas sua disponibilidade em contexto de execução do QA skill (bare-lite dispatch, CI, QA local interativo) não está documentada. Se não estiver definida, todos os comandos `python3 $REPO_ROOT/.specify/scripts/qa_startup.py` falharão silenciosamente. | Adicionar nota às tarefas T021–T027: verificar que `$REPO_ROOT` é garantido pelo contexto de execução do QA skill (como é definido em easter.py/dag_executor dispatch), OU usar Path(__file__).parents[2] como fallback dentro do qa_startup.py (já implementado em T011), E documentar na edição do qa.md que o LLM deve detectar REPO_ROOT via `python3 -c "from pathlib import Path; print(Path('$(which python3)').parents[3])"` como fallback. |
| L1 | Inconsistency | LOW | plan.md, tasks.md | plan.md afirma "Phase 6 pode rodar em paralelo com Phase 5" mas tasks.md apresenta Phase 5 e Phase 6 como sequenciais sem marcação de paralelismo inter-phase. Tasks dentro de Phase 6 têm [P] correto, mas a oportunidade de paralelismo entre as duas phases não é aproveitada. | Baixo impacto — phases 5 e 6 editam arquivos distintos (qa.md+speckit.tasks.md vs speckit.analyze.md+blueprint.md). Adicionar nota em tasks.md: "Phase 6 pode iniciar após T029 (qa.md journey) e T030 (speckit.tasks) estarem completos, sem esperar T031 (lint check)." |
| L2 | Inconsistency | LOW | tasks.md:T016, plan.md Phase 2 | J-001 prosauai em tasks.md T016 começa com `api GET http://localhost:3000 assert_redirect:/login` enquanto plan.md descreve J-001 começando com steps de browser. Discrepância menor na ordem dos steps — ambos chegam ao mesmo resultado (login happy path) mas via ordem diferente. | Priorizar a versão do tasks.md (T016) que é mais detalhada e mais recente. Atualizar plan.md Phase 2 para refletir a ordem: api redirect check first, depois browser steps. Impacto operacional mínimo. |
| L3 | Ambiguity | LOW | tasks.md:T030 | T030 instrui a edição de speckit.tasks.md para incluir um bloco bash que executa `qa_startup.py --parse-config` dentro do skill. Este comando usa `$REPO_ROOT` e `$PLATFORM` como variáveis — dentro de um skill markdown, estas são variáveis de contexto LLM (não vars bash reais). O implement pode interpretar isso como literal bash e não como instrução para o LLM do skill. | Reformular a instrução em T030 para ser explícita: "Adicionar instrução ao skill para que o LLM detecte a plataforma ativa via `platform_cli.py current`, leia o platform.yaml da plataforma, e verifique se o bloco `testing:` está presente — sem usar variáveis bash interpoladas." |

---

## Tabela de Cobertura de Requisitos

| Requisito | Tem Task? | Task IDs | Notas |
|-----------|-----------|----------|-------|
| FR-001 (testing: block optional) | ✅ | T013, T014, T017 | |
| FR-002 (lint validates testing: block) | ✅ | T018, T019, T020 | |
| FR-003 (Copier template) | ⚠️ | T017 | Falta task para copier.yaml (M1) |
| FR-004 (retrocompat) | ✅ | T020 | |
| FR-005 (qa_startup.py CLI) | ✅ | T001, T011 | |
| FR-006 (startup types) | ✅ | T007 | |
| FR-007 (JSON output) | ✅ | T011 | |
| FR-008 (--platform + --cwd) | ✅ | T001, T011 | |
| FR-009 (env diff pre-runtime) | ✅ | T021 | |
| FR-010 (required_env BLOCKER) | ✅ | T005, T021 | |
| FR-011 (auto-start services) | ✅ | T026 | |
| FR-012 (health check BLOCKER) | ✅ | T008, T026 | |
| FR-013 (URL reachability BLOCKER) | ⚠️ | T009, T027 | requires_auth: true sem cobertura (H1) |
| FR-014 (screenshots frontend) | ✅ | T023 | |
| FR-015 (journey execution) | ✅ | T029 | |
| FR-016 (analyze URL coverage) | ✅ | T032 | |
| FR-017 (route detection + WARN) | ✅ | T032 | |
| FR-018 (blueprint testing: skeleton) | ✅ | T033 | |
| FR-019 (blueprint journeys.md) | ✅ | T033 | |
| FR-020 (speckit.tasks smoke phase) | ✅ | T030 | |
| FR-021 (journeys.md YAML format) | ✅ | T015, T016, T029 | |
| FR-022 (never expose env values) | ✅ | T004, T005 | |
| FR-023 (placeholder HTML detection) | ✅ | T010 | |

---

## Tasks sem Requisito Mapeado

| Task | Arquivo | Observação |
|------|---------|------------|
| T006 (quick_check) | qa_startup.py | Utilitário interno — suporte a FR-011/FR-012 via start_services. OK. |
| T012 (test suite) | test_qa_startup.py | Testes — suporte transversal a SC-005. OK. |
| T017 (copier template) | platform.yaml.jinja | FR-003 — mas falta copier.yaml (M1). |
| T020, T024, T028, T031, T034 (checkpoints/lint) | vários | Tarefas de validação — SC-005, SC-006. OK. |
| T035–T039 (smoke) | Phase 7 | SC-001 a SC-007 — cobertura de aceitação. OK. |

---

## Verificação de Alinhamento com a Constituição

| Princípio | Status | Observação |
|-----------|--------|------------|
| I. Pragmatismo | ✅ | stdlib only, zero novas dependências |
| II. Automatizar repetitivo | ✅ | qa_startup.py automatiza tarefas hoje manuais |
| IV. Ação rápida + TDD | ⚠️ | TDD mencionado mas ordem de tasks viola Red-Green-Refactor (H2) |
| V. Alternativas | ✅ | research.md documenta alternativas rejeitadas |
| VII. TDD | ⚠️ | VIOLAÇÃO TÉCNICA — ver H2 |
| IX. Observability | ✅ | JSON output estruturado em todos os modos |

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Total de Requisitos (FRs) | 23 |
| Total de Tasks | 39 |
| Cobertura (FRs com ≥1 task) | 22/23 = **95.7%** |
| FRs com cobertura parcial | 2 (FR-003, FR-013) |
| Ambiguidades detectadas | 2 (M2 exit codes, M3 $REPO_ROOT) |
| Duplicações | 0 |
| Achados CRITICAL | 0 |
| Achados HIGH | 2 |
| Achados MEDIUM | 3 |
| Achados LOW | 3 |

---

## Detalhamento SC-001: Cobertura dos 7 Bugs do Epic 007

A spec afirma SC-001 = 100% (7/7 bugs detectados). Análise de cobertura real:

| Bug Escapado | Camada de Detecção | Cobertura no Epic 026 |
|---|---|---|
| `COPY package.json` inexistente no monorepo root | L4 (docker compose build) | ✅ `--start` via docker compose up emite BLOCKER em build failure |
| `COPY .../public` diretório inexistente | L4 (docker compose build) | ✅ Mesma camada — BLOCKER no startup |
| `localhost:3000` ERR_CONNECTION_TIMED_OUT | L5 URL validation | ✅ `--validate-urls` → BLOCKER: connection refused/timeout |
| Dashboard KPIs vazios — API_URL no IP errado | L5 URL + Journey | ✅ Journey J-001 step "dashboard com dados" detecta KPIs vazios |
| Login não apareceu — cookie antigo inválido | Journey J-001 step 2 | ✅ `required: true` journey → BLOCKER |
| Root `/` mostrava placeholder | Journey J-001 step 1 + screenshot | ✅ `_is_placeholder()` + screenshot em J-001 |
| `JWT_SECRET`, `ADMIN_BOOTSTRAP_*` ausentes | env diff | ✅ `--validate-env` → BLOCKER para required_env |

**Conclusão**: SC-001 (7/7) é **alcançável** com a implementação completa (Phases 1–6). A coverage de "API_URL no IP errado" depende das jornadas (Journey J-001 "dashboard com dados"), não do env diff — a spec/pitch é imprecisa ao listar "env diff" para este bug, mas a detecção funciona via camada correta.

---

## Próximas Ações

### Recomendado antes de implementar

**HIGH — Resolver antes de `speckit.implement`:**

1. **H1 — requires_auth: true sem cobertura**: Decidir entre (A) adicionar FR-024 + task em T009 para skip/warn de URLs autenticadas, ou (B) remover o campo de platform.yaml de prosauai na spec e implementação. A opção B é mais simples e segue Constituição I (pragmatismo). Ação sugerida: **editar tasks.md adicionando nota em T009** — "URLs com `requires_auth: true` devem ser puladas silenciosamente com INFO: 'URL requer autenticação — skipping assertions, verificando apenas reachability'."

2. **H2 — TDD ordering**: O path de menor resistência é **atualizar a descrição de T001** para incluir: "Criar skeleton + escrever testes failing para cada função antes de implementar. Usar T002–T011 como sequência de Red-Green por função." Sem reestruturar as tasks, adicionar a instrução deixa claro para o implement que o TDD deve ser aplicado iterativamente.

### Pode proceder com cuidado

**MEDIUM — Resolver durante implementação:**

3. **M1 — copier.yaml**: Implementador deve adicionar a pergunta ao wizard Copier como parte de T017.
4. **M2 — exit codes**: Implementador deve usar código 2 apenas para "config ausente" e código 3 para "malformado" em T011, atualizando a referência em T025 correspondentemente.
5. **M3 — $REPO_ROOT**: O fallback `Path(__file__).parents[2]` já está em T011 — garantir que qa_startup.py prefere env var `REPO_ROOT` e faz fallback determinístico, sem depender de bash propagation nos skill files.

---

## Oferta de Remediação

Os achados acima são analisáveis mas **não bloqueantes** para implementação. Os 2 achados HIGH têm soluções de baixo custo (notas em tasks existentes vs reestruturação).

Deseja que eu sugira edições concretas em tasks.md para os itens H1, H2, e M1? Posso gerar um patch proposto com as alterações mínimas necessárias — sem aplicar automaticamente.

---

---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise pré-implementação concluída. 0 CRITICAL, 2 HIGH, 3 MEDIUM, 3 LOW. Principais riscos: (1) requires_auth: true em prosauai sem FR/task (H1) — resolver adicionando instrução de skip a T009; (2) ordem TDD em Phase 1 viola Constituição VII (H2) — resolver com instrução iterativa em T001; (3) copier.yaml ausente do scope de T017 (M1). A implementação pode avançar com estes ajustes tratados inline. Guardrails críticos permanecem: skill-lint.py após cada edit em .claude/commands/**; make test verde após Phase 1; Phase 1 completa antes de Phases 3-5."
  blockers: []
  confidence: Alta
  kill_criteria: "Se _lint_testing_block() exigir refatoração breaking de platform_cli.py afetando plataformas existentes, ou se qa_startup.py precisar de dependências além de stdlib+pyyaml para suportar os startup types declarados."
