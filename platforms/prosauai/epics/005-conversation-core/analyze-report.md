# Specification Analysis Report: Conversation Core (Epic 005)

**Epic**: 005-conversation-core  
**Branch**: `epic/prosauai/005-conversation-core`  
**Date**: 2026-04-12  
**Artifacts**: spec.md, plan.md, tasks.md, data-model.md, contracts/conversation-pipeline.md, research.md  
**Type**: Pre-implementation analysis (speckit.analyze)

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F-001 | Duplication | CRITICAL | spec.md FR-007, FR-019 | FR-007 e FR-019 duplicam a regra de fallback para intent "general" quando confidence <0.7. FR-007: "classificar intent, confidence <0.7 fallback general". FR-019: "usar resultado da classificacao para selecionar prompt template, confidence <0.7 fallback general". Mesma regra em dois requisitos. | Consolidar: FR-007 cobre classificacao + fallback. FR-019 foca apenas em "usar resultado para selecionar template + registrar para analytics" sem repetir a regra de confidence. |
| F-002 | Inconsistency | HIGH | plan.md §4.4, tasks.md Estimativas | Estimativa de LOC diverge: plan.md diz **~3900 LOC** (com multiplicador 1.5x), tasks.md soma **~4500 LOC**. Delta de ~15% sem explicacao. Tasks.md tem contagem per-phase mais granular e provavelmente mais precisa. | Atualizar plan.md para ~4500 LOC ou adicionar nota explicando a diferenca (tasks inclui mais testes de integracao e polish). |
| F-003 | Underspecification | HIGH | contracts/conversation-pipeline.md, spec.md, tasks.md | `ConversationRequest.trace_context: dict` (W3C trace context) esta definido no contrato mas **nao aparece em spec, plan ou tasks**. Nenhuma task cria, propaga ou valida `trace_context`. O FlushCallback no contrato tambem nao inclui `trace_context` como parametro. | Opcao A: Adicionar task para propagar W3C trace context do webhook ate ConversationRequest. Opcao B: Remover `trace_context` do contrato se sera derivado do OTel context corrente (mais provavel dado que OTel propagation e automatico). |
| F-004 | Inconsistency | HIGH | plan.md §3.1 pipeline pseudocode, data-model.md flowchart | **Ordem das etapas do pipeline diverge.** Plan.md salva mensagem inbound (passo 4) **antes** do input guard (passo 6) — mensagens bloqueadas ficam persistidas no BD como orfas. Data-model.md flowchart mostra Input Guard **antes** de Save Inbound Message (ordem correta). | Alinhar: Input Guard deve executar antes de salvar mensagem inbound. Atualizar pseudocodigo no plan.md para mover `save_message()` para apos `check_input()`. |
| F-005 | Coverage | HIGH | spec.md FR-015, tasks.md | FR-015 define hard limit de **20 tool calls por conversa**. Nenhuma task implementa ou testa o contador de tool calls por conversa. T054 menciona "Respeitar hard limit de 20 tool calls" mas sem teste de verificacao. | Adicionar teste em T050 ou T051 que verifica: contador de tool calls incrementa, persiste no ConversationState, e bloqueia chamadas adicionais apos atingir 20. |
| F-006 | Inconsistency | HIGH | plan.md §2.3, tasks.md T030, T041 | Plan.md §2.3 descreve `get_or_create_conversation()` completo com logica de inactivity timeout. T030 (Phase 3/US1) implementa `context.py` mas a descricao **nao menciona inactivity timeout**. T041 (Phase 4/US2) "estende" `context.py` adicionando a mesma logica. Ambiguidade: T030 implementa stub ou versao completa? | Esclarecer: se T030 implementa versao completa (conforme plan.md), T041 vira task de verificacao/teste. Se T030 implementa versao basica, documentar explicitamente que timeout e deferido para T041. |
| F-007 | Underspecification | HIGH | contracts/conversation-pipeline.md, tasks.md | Semaforo `asyncio.Semaphore` nao tem timeout built-in. O contrato especifica "Semaforo timeout (60s) -> Fallback" mas nenhuma task implementa ou testa o caminho de timeout do semaforo. `asyncio.wait_for(semaphore.acquire(), timeout=60)` nao e especificado. | Adicionar nota de implementacao em T033 especificando como enforcar timeout no semaforo. Adicionar teste em T024 para o caminho de timeout do semaforo. |
| F-008 | Coverage | HIGH | spec.md FR-011, tasks.md T018 | FR-011 exige preservacao de `agent_id` do router ate o flush. T018 implementa a modificacao no debounce, mas **nao existe teste dedicado** que verifique que agent_id e preservado end-to-end (append -> flush -> callback). | Adicionar teste em T018 ou criar nova task de teste que valida: append com agent_id, _parse_flush_items extrai corretamente, callback recebe agent_id. |
| F-009 | Coverage | MEDIUM | spec.md SC-001, tasks.md | SC-001 exige <30s response time em 95% dos casos. Nenhuma task mede ou valida latencia end-to-end. Plan menciona `<3s p95 para pipeline (excl. debounce)` mas sem teste. | Adicionar assertion de latencia no teste de integracao (T040) ou task de benchmark em Phase 9. Mesmo soft assertion e melhor que nenhuma. |
| F-010 | Coverage | MEDIUM | spec.md SC-007, tasks.md T060 | SC-007 exige cobertura >= 80% por modulo. T060 diz "verificar com pytest --cov" mas nao tem enforcement (flag `--cov-fail-under=80`). | Modificar T060 para incluir `--cov-fail-under=80` no comando pytest. Ou criar CI gate. |
| F-011 | Coverage | MEDIUM | spec.md FR-017, tasks.md | FR-017 (max 1 conversa ativa por customer/channel) e enforced pelo unique partial index. Nenhum teste verifica o constraint de unicidade diretamente (tentar criar segunda conversa ativa deve falhar). | Adicionar teste em T039 que tenta criar 2 conversas ativas para o mesmo customer/channel e verifica erro do BD. |
| F-012 | Underspecification | MEDIUM | spec.md FR-005/FR-006, tasks.md T058 | FR-005 exige PII hasheado em logs. T058 (US6, Phase 8) garante que spans usam `sanitized_text`. Mas spans criados na Phase 3 (US1) podem logar PII em texto plano ate que Phase 8 execute. SC-005 e requisito desde o dia 1. | Mover sanitizacao de PII em spans para Phase 3 (T036 pipeline.py) em vez de Phase 8. Ou documentar risco de PII em spans nas entregas intermediarias. |
| F-013 | Inconsistency | MEDIUM | plan.md §3.1, contracts/conversation-pipeline.md | Pseudocodigo do plan chama `get_or_create_conversation(pool, ..., customer.id, agent_config.id)` com 4 args posicionais. Contrato define 6 parametros: `(pool, tenant_id, customer_id, agent_id, channel, inactivity_timeout_hours)`. Falta `tenant_id` e `channel` na chamada do pseudocodigo. | Atualizar pseudocodigo para incluir todos os parametros. Baixo risco (pseudocodigo apenas) mas confuso para implementadores. |
| F-014 | Underspecification | MEDIUM | plan.md §2.2, contracts/conversation-pipeline.md | `sender_key` e "Phone ou LID opaque" (contrato). Quando e LID (identificador opaco da Evolution API), hashear com SHA-256 como se fosse telefone nao faz sentido semantico. Tratamento de LID completamente nao especificado. | Clarificar em T029: se `sender_key` e LID, armazenar as-is (ja e opaco) ou hashear. Adicionar nota no contrato. |
| F-015 | Inconsistency | MEDIUM | data-model.md (conversations), spec.md FR-017 | Data-model.md tem `CONSTRAINT uq_active_conversation UNIQUE (...) WHERE (status = 'active')` seguido do comentario "nao e suportado diretamente" e depois `CREATE UNIQUE INDEX idx_one_active_per_customer`. Duas definicoes para o mesmo invariante — o constraint falharia em Postgres. | Remover a linha `CONSTRAINT uq_active_conversation` do DDL. Manter apenas o `CREATE UNIQUE INDEX`. Adicionar comentario explicativo. |
| F-016 | Underspecification | MEDIUM | spec.md (Key Entities), plan.md §2.1, data-model.md | Spec Key Entities descreve `ConversationState` com "metadados and session information". Plan e data-model nao tem campo `metadata` em `conversation_states`. | Adicionar `metadata JSONB` a tabela `conversation_states` ou remover referencia a "metadados" da descricao de entidade na spec. |
| F-017 | Underspecification | MEDIUM | plan.md §2.5, contracts §5, data-model.md | `ClassificationResult.prompt_template` (string) seleciona template de prompt, mas `PromptConfig` no data model tem **um unico system_prompt por agent** sem mapeamento intent→template. Nao esta claro como `prompt_template` seleciona prompts diferentes por intent. | Opcao A: Adicionar `intent_template_map: JSONB` a tabela `prompts`. Opcao B: Clarificar que `prompt_template` afeta apenas prefix/suffix dentro de um unico PromptConfig e documentar no contrato. |
| F-018 | Constitution | MEDIUM | Constitution VII (TDD), tasks.md Phase 2 | Phase 2 (Foundational) cria DB layer (pool.py, repositories.py), domain models, e debounce changes (T013-T020) com **zero tarefas de teste dedicadas**. TDD exige testes antes de implementacao. Tests para estes componentes sao apenas indiretos (integration tests na Phase 3). | Adicionar tarefas de unit test para T014 (pool.py — create_pool, with_tenant) e T015 (repositories.py — cada metodo de repo com asyncpg mockado). Sao componentes de alto risco. |
| F-019 | Inconsistency | LOW | data-model.md flowchart, plan.md §3.2 | Flowchart em data-model.md mostra "Deliver via Evolution" como parte do pipeline. Mas plan.md §3.2 mostra que delivery acontece no `_make_flush_conversation` **apos** `process_conversation()` retornar. Pipeline retorna `ConversationResponse`; delivery e externo. | Atualizar flowchart para mostrar `ConversationResponse` como fronteira do pipeline e delivery como passo externo. |
| F-020 | Coverage | LOW | spec.md Edge Cases, tasks.md T018 | Edge case "multiplas mensagens com agent_ids diferentes no mesmo debounce window → usa o ultimo" especificado na spec. T018 implementa (fallback para ultimo). Nao existe teste dedicado para este cenario. | Adicionar test case em T018 para cenario multi-agent_id no debounce. |
| F-021 | Underspecification | LOW | plan.md §1.3, tasks.md T014 | `with_tenant()` usa `SET LOCAL` + transacao. `get_or_create_customer` recebe `pool` (nao `conn`). Comportamento de rollback em falhas parciais nao especificado. Nesting de transacoes nao documentado. | Adicionar nota de error handling em T014: comportamento de rollback, nesting de with_tenant(). |
| F-022 | Coverage | LOW | spec.md FR-015 (8K tokens), tasks.md T022 | 8K token budget mencionado em T003 (config) e T030 (truncation). T022 testa "truncation por token limit" genericamente mas nao testa o boundary de 8000 tokens especificamente. | Adicionar test case em T022 com window excedendo 8000 tokens para verificar truncation exata. |
| F-023 | Inconsistency | LOW | spec.md FR-020, plan.md Performance Goals | FR-020: pool timeout "aguardar ate 5 segundos antes de fallback". Plan Performance Goals: `pool 10 Postgres connections`. T003 config tem `llm_semaphore_size=10` mas nao tem `pool_timeout=5` como setting configuravel. | Adicionar `pool_acquire_timeout=5` como setting em T003 (config.py). |

---

## Coverage Summary

### Functional Requirements → Tasks

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 | Yes | T036, T037, T026 | Pipeline + flush callback + test |
| FR-002 | Yes | T029, T021 | Customer create + test |
| FR-003 | Yes | T030, T022 | Context window + test |
| FR-004 | Yes | T005-T015 | Migrations + DB layer |
| FR-005 | Yes | T031, T027, T057 | Input guard + test + hardening |
| FR-006 | Yes | T035, T028 | Output guard + test |
| FR-007 | Yes | T032, T023 | Classifier + test. **Duplica FR-019** (F-001) |
| FR-008 | Yes | T033, T024 | Agent + test |
| FR-009 | Yes | T034, T025 | Evaluator + test |
| FR-010 | Yes | T044-T047 | Multi-tenant + RLS tests |
| FR-011 | Partial | T018, T038 | Debounce mod + webhook. **Sem teste dedicado** (F-008) |
| FR-012 | Yes | T050-T054 | Tools + registry + tests |
| FR-013 | Yes | T019, T036, T062 | OTel conventions + pipeline spans + verify |
| FR-014 | Yes | T003, T033, T024 | Config + impl + test |
| FR-015 | Partial | T003, T033, T030 | **20 tool calls/conv nao tracked** (F-005) |
| FR-016 | Yes | T009, T044 | Append-only DDL + RLS test |
| FR-017 | Partial | T007, T039 | Unique index. **Constraint test missing** (F-011) |
| FR-018 | Yes | T030/T041, T039 | Inactivity timeout (com ambiguidade F-006) |
| FR-019 | Partial | T032, T036 | **Duplica FR-007** (F-001). `prompt_template` resolution unclear (F-017) |
| FR-020 | Partial | T003, T014 | Pool impl. **Timeout setting missing** (F-023) |

### Success Criteria → Tasks

| SC | Description | Task IDs | Coverage |
|----|-------------|----------|----------|
| SC-001 | <30s, 95% | T037, T063 | **PARTIAL** — sem teste de latencia (F-009) |
| SC-002 | Contexto 3a msg | T040 | COVERED |
| SC-003 | 2 tenants zero leak | T044-T045, T047 | COVERED |
| SC-004 | Qualidade 100% | T025, T026 | COVERED |
| SC-005 | PII nunca plaintext | T055, T057-T058 | **PARTIAL** — Phase 3 spans podem logar PII (F-012) |
| SC-006 | Pipeline traceable OTel | T019, T036, T062 | COVERED |
| SC-007 | Coverage >= 80% | T060 | **PARTIAL** — sem enforcement (F-010) |
| SC-008 | ResenhAI tool call | T053, T050 | COVERED |

---

## Constitution Alignment

| Principio | Status | Evidencia |
|-----------|--------|-----------|
| I. Pragmatism Above All | PASS | Pipeline inline, asyncpg direto, heuristicas, regex guardrails |
| II. Automate Repetitive Tasks | PASS | Migrations SQL, seed data, docker compose |
| III. Structured Knowledge | PASS | research.md, data-model.md, contracts/ documentam decisoes |
| IV. Fast Action | PASS | 10 dias timeboxed, MVP scope controlado |
| V. Alternatives and Trade-offs | PASS | Cada decisao no plan tem >= 2 alternativas |
| VI. Brutal Honesty | PASS | Rabbit holes explicitos, no-gos claros |
| VII. TDD | **PARTIAL** | Phases 3-8 seguem TDD. **Phase 2 sem unit tests** (F-018) |
| VIII. Collaborative Decision Making | PASS | 10 decisoes capturadas, clarifications resolvidas |
| IX. Observability and Logging | PASS | OTel spans por etapa, structlog, correlation_id |

---

## Unmapped Tasks

Nenhuma task orfa. Todas as 63 tasks mapeiam para pelo menos um FR ou SC.

Tasks de suporte (nao mapeiam diretamente para FR/SC):
- **T059** (docstrings) — Constitution III
- **T061** (quickstart validation) — DevEx
- **T063** (code review final) — Verificacao cross-cutting

---

## Metrics

| Metrica | Valor |
|---------|-------|
| Total FRs | 20 |
| FRs fully covered | 14 |
| FRs partially covered | 6 (FR-011, FR-015, FR-017, FR-019, FR-020, FR-007/019 overlap) |
| FRs uncovered | 0 |
| Total SCs | 8 |
| SCs fully covered | 5 |
| SCs partially covered | 3 (SC-001, SC-005, SC-007) |
| Total Tasks | 63 |
| Orphaned Tasks | 0 |
| Coverage % (FR with >= 1 task) | 100% (20/20) |
| Coverage % (FR fully covered) | 70% (14/20) |
| Total Findings | 23 |
| CRITICAL | 1 |
| HIGH | 7 |
| MEDIUM | 10 |
| LOW | 5 |
| Ambiguity Count | 0 (vague adjectives) |
| Duplication Count | 1 (FR-007/FR-019) |

---

## Next Actions

### Issues que DEVEM ser resolvidos antes de `/speckit.implement`:

1. **F-001 (CRITICAL)**: Consolidar FR-007 e FR-019 na spec.md para eliminar duplicacao da regra de confidence.
2. **F-004 (HIGH)**: Alinhar ordem do pipeline — input guard ANTES de salvar mensagem inbound. Atualizar pseudocodigo no plan.md.
3. **F-005 (HIGH)**: Adicionar task para implementar e testar hard limit de 20 tool calls por conversa.
4. **F-006 (HIGH)**: Clarificar se T030 implementa inactivity timeout completo ou stub. Atualizar descricao da task.

### Issues recomendados (podem ser resolvidos durante implementacao):

5. **F-003 (HIGH)**: Decidir sobre `trace_context` no contrato — remover ou adicionar task de propagacao.
6. **F-007 (HIGH)**: Especificar implementacao de timeout no semaforo (asyncio.wait_for).
7. **F-008 (HIGH)**: Adicionar teste de agent_id end-to-end no debounce.
8. **F-012 (MEDIUM)**: Mover sanitizacao de PII em spans para Phase 3 (nao esperar Phase 8).
9. **F-018 (MEDIUM)**: Adicionar unit tests para Phase 2 (pool.py, repositories.py) — Constitution VII.

### Proceed se apenas LOW/MEDIUM restarem:

Se os 4 issues criticos/altos acima forem resolvidos, o implementador pode prosseguir com `/speckit.implement`. Os issues MEDIUM e LOW podem ser enderecados durante a implementacao sem risco de retrabalho significativo.

### Comandos sugeridos:

- Resolver F-001: `/speckit.specify prosauai` com refinamento de FR-007/FR-019
- Resolver F-004/F-006: Editar plan.md manualmente (ordem do pipeline + clarificar T030 scope)
- Resolver F-005: Editar tasks.md manualmente (adicionar task T064 para tool call counter)
- Apos resolucao: `/speckit.implement prosauai` para iniciar implementacao

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Analise pre-implementacao completa para Conversation Core (epic 005). 23 findings: 1 CRITICAL (FR duplicado), 7 HIGH (LOC diverge, trace_context missing, pipeline order, tool call limit, T030/T041 ambiguidade, semaforo timeout, agent_id test). Coverage 100% FRs com tasks (14/20 fully covered). 4 issues DEVEM ser resolvidos antes de implement: consolidar FR-007/019, alinhar pipeline order, adicionar tool call limit task, clarificar T030 scope."
  blockers:
    - "F-001: FR-007 e FR-019 duplicam regra de confidence fallback"
    - "F-004: Ordem do pipeline diverge entre plan e data-model"
    - "F-005: Hard limit de 20 tool calls sem task de implementacao/teste"
    - "F-006: Ambiguidade se T030 ou T041 implementa inactivity timeout"
  confidence: Alta
  kill_criteria: "Se os 4 blockers HIGH/CRITICAL nao forem resolvidos, a implementacao vai produzir codigo ambiguo ou inconsistente com a spec."
