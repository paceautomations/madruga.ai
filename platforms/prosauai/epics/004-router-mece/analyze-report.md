# Specification Analysis Report — Epic 004: Router MECE

**Date**: 2026-04-10
**Artifacts analyzed**: spec.md (242 lines), plan.md (339 lines), tasks.md (328 lines)
**Supplementary**: data-model.md, contracts/router-api.md, pitch.md

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | HIGH | plan.md:L270 "28 tasks", tasks.md:L310 "51 tasks" | plan.md Estimativa de Esforço refere "28 tasks" mas tasks.md produzido por /speckit.tasks expandiu para 51 tasks. LOC estimado ficou idêntico (1210+1160), o que é improvável com quase o dobro de tasks. | Atualizar plan.md seção Estimativa para refletir 51 tasks e recalibrar LOC. Ou aceitar como artefato de evolução natural (plan antecede tasks) e não atualizar. |
| I2 | Inconsistency | HIGH | tasks.md:T044 "config/routing/{tenant.id}.yaml", pitch.md "ariel.yaml / resenhai.yaml" | T044 assume que o arquivo YAML é nomeado por `tenant.id` (ex: `pace-internal.yaml`), mas os arquivos reais criados em T029/T030 são `ariel.yaml` e `resenhai.yaml` (nomeados por instance/slug, não por tenant ID). O YAML internamente declara `tenant: pace-internal`. Loader precisa mapear tenant → arquivo por algum mecanismo (glob + campo tenant interno, ou lookup explícito). | Definir explicitamente a convenção de nomeação de arquivo vs tenant ID no loader. Opção A: arquivo nomeado por `tenant.id` → renomear para `pace-internal.yaml`. Opção B: loader faz glob em `config/routing/*.yaml` e indexa pelo campo `tenant` interno → ajustar T044 para usar essa abordagem. Recomendação: Opção B (já implícita no pitch: "for path in Path('config/routing').glob('*.yaml')"). |
| C1 | Coverage Gap | HIGH | SC-010, tasks.md | SC-010 exige "análise estática confirma que todo consumidor trata todos os 5 tipos de decisão exaustivamente". Nenhuma task roda explicitamente `mypy --strict` ou `pyright` como step de validação. T050 roda `pytest` e `grep` mas não type checker. | Adicionar step em T050 ou criar task dedicada: `mypy --strict prosauai/core/router/` + `pyright prosauai/api/webhooks.py` para provar exhaustiveness do match/case. |
| C2 | Coverage Gap | MEDIUM | SC-011, tasks.md | SC-011 exige `route() < 5ms p99` mas nenhuma task implementa benchmark ou teste de performance. A latência é assumida como "óbvia" (classify <1ms + decide <1ms + MGET ~2-3ms) mas não é verificada. | Adicionar teste de performance simples em T045 ou T050: chamar `route()` 1000x com Redis mock e assertar p99 < 5ms. Ou aceitar que <5ms é implícito dado as operações envolvidas (sem I/O real em testes). |
| C3 | Coverage Gap | MEDIUM | FR-017, tasks.md | FR-017 exige fail-fast no startup quando tenant ativo não tem config YAML. T044 implementa, mas nenhuma task testa explicitamente o cenário de falha (startup com tenant sem config → serviço recusa iniciar). | Adicionar teste negativo em T044: startup com tenant sem config/routing/<slug>.yaml → assertar que serviço levanta exceção no lifespan. |
| U1 | Underspecification | MEDIUM | tasks.md:T044, spec.md edge case L161 | T044 diz "fail-fast se tenant ativo não tem config YAML correspondente" mas não especifica: (a) qual exceção levantar, (b) se é log + sys.exit ou exception no lifespan, (c) mensagem de erro esperada. Edge case no spec diz "detectável previamente via router verify" mas não detalha o comportamento runtime. | Especificar em T044: levantar `RoutingConfigError` com mensagem `"Tenant {tenant.id} has no routing config at config/routing/{slug}.yaml"`. Lifespan propaga exceção → FastAPI recusa iniciar. |
| U2 | Underspecification | MEDIUM | tasks.md:T039 | T039 diz "configurar pre-commit hook em `.pre-commit-config.yaml`" mas não verifica se o repo prosauai já usa pre-commit framework. Se não usa, criar `.pre-commit-config.yaml` do zero é escopo maior. Se já usa, é append trivial. | Verificar se `paceautomations/prosauai` já tem `.pre-commit-config.yaml`. Se não, T039 precisa incluir setup inicial do pre-commit ou usar alternativa (Makefile target, CI step). |
| U3 | Underspecification | LOW | tasks.md:T038 "explain --facts <json>" | T038 não especifica o formato exato do JSON de facts (quais campos obrigatórios, quais opcionais, se aceita enums como string). Spec FR-009 diz "dado um conjunto de fatos e um tenant" sem detalhar formato de input. | Definir em contracts/router-api.md ou T038: explain aceita JSON com campos de MessageFacts (todos obrigatórios exceto sender_phone, sender_lid_opaque, group_id que são nullable). Ou aceita subset e preenche defaults. |
| T1 | Terminology Drift | MEDIUM | spec.md:US1 "tipo_evento", data-model.md "event_kind" | Spec user stories usam termos em português (tipo_evento, tipo_conteudo, canal) mas código e data-model usam inglês (event_kind, content_kind, channel). Aceitável por convenção (prosa PT-BR, código EN), mas os cenários de aceitação misturam idiomas na mesma frase. | Manter como está — a convenção prosa PT-BR / código EN é documentada. Cenários de aceitação são prosa, termos técnicos podem aparecer em inglês. Sem ação necessária. |
| T2 | Terminology Drift | LOW | pitch.md "formatter.py pode virar inbound.py", plan.md "inbound.py RENOMEADO de formatter.py", tasks.md:T001 "manter arquivo" | Pitch sugere rename do arquivo (`formatter.py` → `inbound.py`), plan.md afirma o rename com nota "(arquivo pode manter nome formatter.py)", T001 diz "alterar nome da classe, manter arquivo". Três documentos, três posições. | Decidir: ou renomeia o arquivo para `inbound.py` (alinhado com domain-model) ou mantém `formatter.py` (menor diff). T001 deve ser explícito. Recomendação: manter `formatter.py` (menor risco de quebra de imports; nome fica legacy mas funcional). |
| D1 | Duplication | LOW | spec.md:FR-002 + FR-007 | FR-002 inclui "ausência de sobreposição entre regras" e FR-007 é dedicada exclusivamente a overlap detection. FR-007 é subconjunto de FR-002. | Manter como está — FR-002 é o requisito geral de loading, FR-007 detalha o mecanismo de overlap. A separação é intencional para rastreabilidade. Sem ação necessária. |
| D2 | Duplication | LOW | spec.md:FR-008 + FR-015 | FR-008 (verificação executável localmente e em CI) subsume FR-015 (pre-commit hook). Pre-commit é uma forma de verificação local. | Manter como está — FR-015 especifica o mecanismo concreto (hook), FR-008 é a capability geral. Separação intencional. |

---

## Coverage Summary

### Requirement → Task Mapping

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 (Classificação MECE) | ✅ | T006, T007, T008, T016, T018, T019, T032, T033 | Bem coberto — tipos + impl + property tests |
| FR-002 (Config externa per-tenant) | ✅ | T022, T026, T027, T029, T030, T031 | Schema + loader + fixtures reais |
| FR-003 (Avaliação por prioridade) | ✅ | T011, T012, T020, T024 | Rule + engine |
| FR-004 (Agent resolution) | ✅ | T021, T025 | Impl + tests incluindo caso de erro |
| FR-005 (Decisões tipadas) | ✅ | T009, T010 | Discriminated union + tests |
| FR-006 (Menção tenant-aware) | ✅ | T015, T017 | 3 estratégias testadas |
| FR-007 (Overlap rejection) | ✅ | T023, T028, T034 | Overlap analysis + reachability |
| FR-008 (Verificação CLI) | ✅ | T035, T037 | verify subcommand |
| FR-009 (Explicação) | ✅ | T036, T038 | explain subcommand |
| FR-010 (Observabilidade 2 spans) | ✅ | T040, T042, T043 | Constantes + spans na migração |
| FR-011 (Rename ParsedMessage) | ✅ | T001, T003, T050 | Rename + validação grep |
| FR-012 (default_agent_id) | ✅ | T002, T003 | Aditivo + testes |
| FR-013 (Substituir legado) | ✅ | T041, T043, T046, T047, T050 | Equivalência + remoção + grep |
| FR-014 (Redis state lookup) | ✅ | T013, T014, T045 | StateSnapshot + route() |
| FR-015 (Pre-commit hook) | ✅ | T039 | Hook configurado |
| FR-016 (Startup-only load) | ✅ | T044 | Lifespan implementation |
| FR-017 (Fail-fast startup) | ✅ | T044 | Implementado mas sem teste negativo dedicado (ver C3) |

### Success Criteria → Task Mapping

| SC | Has Buildable Task? | Task IDs | Notes |
|----|---------------------|----------|-------|
| SC-001 (MECE property test) | ✅ | T032, T033 | Enumeração exaustiva + Hypothesis |
| SC-002 (Config inválida rejeitada) | ✅ | T022, T023, T028 | 15+ testes negativos |
| SC-003 (Zero code changes) | ✅ | T029, T030 | Configs YAML reais |
| SC-004 (agent_id válido) | ✅ | T021, T025 | Incluindo caso de erro |
| SC-005 (26 fixtures equivalentes) | ✅ | T041 | Tabela de equivalência explícita |
| SC-006 (Zero referências legado) | ✅ | T046, T050 | Remoção + grep validação |
| SC-007 (Verify < 5s) | ⚠️ | T037 | Implícito — sem teste de performance |
| SC-008 (2 spans OTel) | ✅ | T042, T043 | Constantes + spans |
| SC-009 (95+ testes) | ✅ | Todos os T0xx de teste | Contagem acumulada |
| SC-010 (Exhaustiveness estática) | ❌ | — | Nenhuma task roda mypy/pyright explicitamente |
| SC-011 (route() < 5ms p99) | ❌ | — | Nenhuma task de benchmark |
| SC-012 (Startup valida tenants) | ✅ | T044 | Sem teste negativo dedicado |

### Unmapped Tasks

Nenhuma — todas as 51 tasks mapeiam para pelo menos 1 FR ou atividade de suporte (setup, docs, validação).

### Constitution Alignment Issues

Nenhuma violação encontrada.

| Princípio | Status | Evidência |
|-----------|--------|-----------|
| I. Pragmatism | ✅ | Igualdade + conjunção, sem expression language. Stdlib + pydantic. |
| II. Automate | ✅ | CLI verify/explain, pre-commit hook |
| IV. Fast Action | ✅ | Rip-and-replace, TDD |
| V. Alternatives | ✅ | 8 decisões com ≥2 alternativas em plan.md |
| VI. Brutal Honesty | ✅ | Contrato aberto conversation_in_handoff documentado |
| VII. TDD | ✅ | Tasks explicitamente seguem Red-Green-Refactor |
| VIII. Collaborative | ✅ | 21 decisões no epic-context, deep-dive documentado |
| IX. Observability | ✅ | 2 spans, 6 constantes, matched_rule em logs |

---

## Metrics

| Métrica | Valor |
|---------|-------|
| **Total Requirements (FR)** | 17 |
| **Total Success Criteria (SC)** | 12 |
| **Total Tasks** | 51 |
| **Coverage % (FRs com ≥1 task)** | 100% (17/17) |
| **Coverage % (SCs com task buildable)** | 83% (10/12) |
| **Ambiguity Count** | 3 (U1, U2, U3) |
| **Duplication Count** | 2 (D1, D2) — ambas intencionais |
| **Inconsistency Count** | 2 (I1, I2) |
| **Coverage Gap Count** | 3 (C1, C2, C3) |
| **Terminology Drift Count** | 2 (T1, T2) |
| **Critical Issues** | 0 |
| **High Issues** | 3 (I1, I2, C1) |
| **Medium Issues** | 5 (C2, C3, U1, U2, T2) |
| **Low Issues** | 4 (U3, T1, D1, D2) |

---

## Next Actions

### Recomendação: PROCEED com ajustes menores

Nenhum issue CRITICAL foi encontrado. Os 3 issues HIGH são corrigíveis sem re-especificação:

1. **I1 (plan.md task count)**: Aceitar como artefato de evolução — plan.md foi escrito antes de tasks.md. Não bloqueia implementação. Se desejar consistência documental, atualizar plan.md seção Estimativa.

2. **I2 (naming de arquivo YAML vs tenant.id)**: **Requer decisão antes de implementar T044.** A convenção de nomeação precisa estar clara para o loader. Recomendação: loader faz glob + indexa pelo campo `tenant` interno do YAML (já implícito no pitch "for path in Path(...).glob(...)"). Ajustar descrição de T044.

3. **C1 (mypy/pyright para SC-010)**: Adicionar step de type-checking em T050 ou como task separada. Sem isso, SC-010 (exhaustiveness estática) não é verificável.

**Issues MEDIUM** são melhorias de especificação que podem ser resolvidas durante implementação:
- C2: Performance implícita, aceitável sem benchmark dedicado
- C3: Teste negativo de startup pode ser adicionado em T044
- U1/U2/U3: Detalhes de implementação que o implementador resolve

**Sugestões de comando**:
- Se quiser corrigir I2 e C1 antes de implementar: editar tasks.md manualmente (T044 e T050)
- Se quiser prosseguir direto: `/speckit.implement prosauai 004-router-mece` — implementador resolve I2 e C1 inline

---

## Remediation Summary

Os 3 issues HIGH podem ser corrigidos com edições mínimas:

| Issue | Arquivo | Edição |
|-------|---------|--------|
| I2 | tasks.md:T044 | Trocar `config/routing/{tenant.id}.yaml` por `glob config/routing/*.yaml + indexar por campo tenant interno` |
| C1 | tasks.md:T050 | Adicionar `mypy --strict prosauai/core/router/ && pyright prosauai/api/webhooks.py` ao step de validação |
| I1 | plan.md | Opcional: atualizar "28 tasks" para "51 tasks" na seção Estimativa |

---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise pre-implementação concluída. 0 CRITICAL, 3 HIGH (I1 task count drift plan→tasks, I2 naming arquivo YAML vs tenant.id no loader, C1 falta mypy/pyright para SC-010). Todos corrigíveis inline. 100% dos FRs cobertos por tasks. 83% dos SCs com task buildable (SC-010 e SC-011 sem task explícita). Recomendação: prosseguir com implementação, resolver I2 ao implementar T044 (usar glob + campo tenant interno)."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a convenção de nomeação de arquivos YAML (I2) não for resolvida antes de T044, causando loader que não encontra configs. Se SC-010 (exhaustiveness estática) for ignorado e um subtipo de Decision não for tratado em webhooks.py."
