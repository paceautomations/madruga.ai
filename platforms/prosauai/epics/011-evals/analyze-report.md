# Specification Analysis Report — Epic 011-evals (pre-implement)

**Date**: 2026-04-24
**Scope**: `spec.md` (54 FRs, 12 SCs, 22 assumptions), `plan.md` (3 PRs, 5 migrations), `tasks.md` (105 tasks in 10 phases)
**Mode**: Autonomous pre-implementation cross-artifact consistency check (read-only).

---

## Summary Table

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity / Gap | HIGH | spec.md:L181 (FR-011) | FR-011 marca `[VALIDAR]` se edição programática de `tenants.yaml` existe no epic 010. Plano e tasks.md T071 assumem que sim (escreve YAML com backup `.bak` + fsync), mas a assumption não foi confirmada. | Validar em T020/T071 (antes do PATCH endpoint) se epic 010 já tem writer. Se não, ajustar FR-011 para "via redeploy" ou adicionar task de infra YAML writer reutilizável. |
| A2 | Ambiguity | MEDIUM | spec.md:L234 (FR-043) | FR-043 cita ação `log + email`, mas A11 confessa "[VALIDAR] — se canal email do admin já existe". Nenhuma task valida/implementa canal email. | Adicionar task em Phase 9 para (a) validar canal email do admin ou (b) rebaixar FR-043 para `log` apenas em v1, removendo `email`. Como está, FR-043 é parcialmente não-implementável. |
| C1 | Coverage Gap | MEDIUM | spec.md FR-042, FR-043 | FR-042 (métrica below_threshold) aparece em T016 facade, mas NENHUMA task faz o wire `persist` → `below_threshold_total` emission. Spec exige emissão "sempre que score < threshold"; T022 não implementa essa comparação. | Adicionar subtask em T022 (ou nova task em Phase 3) que lê `tenant_config.evals.alerts` e compara score pós-INSERT, emitindo métrica quando violado. Em `mode=shadow`, NO-OP nos alerts (FR-044). |
| C2 | Coverage Gap | MEDIUM | spec.md FR-044 | FR-044 exige que `mode=shadow` NUNCA dispare alertas (log-only). Nenhuma task testa explicitamente o bloqueio de alertas em shadow vs on. | Adicionar caso em T027 ou T089: `mode=shadow + score<threshold` → métrica persistida mas alerta estruturado NÃO emitido. |
| C3 | Coverage Gap | LOW | spec.md FR-051 | FR-051 exige que spans batch DeepEval criem novo trace raiz (não attached ao pipeline). T045 menciona span root mas não testa explicitamente que `trace_id` é novo/diferente do `message_id.trace_id`. | Adicionar assertion em T049 integration: span `eval.batch.deepeval` tem `trace_id` distinto dos spans das mensagens processadas. |
| I1 | Inconsistency | HIGH | plan.md §"Retention matrix" + tasks.md T066-T069 | Plano posiciona retention cron em PR-B (linha "PR-B coding"); tasks.md coloca T066-T069 em Phase 7 (User Story 5, P3) que o plan cut-line marca como "PR-B endpoint + PR-C UI". Retention (FR-052-054) é infra crítica (LGPD + storage), não parte da curation story. | Mover T066-T069 para Phase 2 (Foundational) ou criar sub-phase "Retention" entre Phase 7 e 8. Se PR-C for sacrificado, retention deve estar em PR-B (garantido). Cut-line atual corre risco de sacrificar retention junto com UI. |
| I2 | Inconsistency | MEDIUM | plan.md §"PR-B entregáveis" vs tasks.md Phase 6/7 | Plan diz PR-B inclui "endpoint POST /admin/traces/{trace_id}/golden"; tasks.md coloca essa task (T061) em Phase 7 (US5 P3). Promptfoo generator (T055 em Phase 6/US4) depende semanticamente de `golden_traces`, mas tabela só existe após T058 (Phase 7). | Reordenar: criar Phase 6.5 (golden backend — migration 5 + endpoint + queries) ANTES de Phase 6 generator, ou documentar explicitamente que T055 roda contra tabela vazia em US4 e a integração real é validada apenas em T064. |
| I3 | Inconsistency | LOW | spec.md Priorities vs plan.md PR ordering | Spec classifica US5 (golden curation) como P3 e US4 (Promptfoo CI) como P2, sugerindo US4 pode ir primeiro. Plan PR-B empurra ambos para semana 2, tasks.md mantém ordem numérica (US4 antes de US5), mas generator depende de schema de US5. | Clarificar: US4 "Promptfoo smoke" sem golden_traces é viável (5 hand-written cases) — só o `generate.py` depende de US5. Reforçar em plan/tasks que T052-T054 (smoke + action) são standalone P2 e T055 + T064 requerem US5 merge primeiro. |
| D1 | Duplication | LOW | spec.md FR-017 vs FR-049 | FR-017 declara métrica `autonomous_resolution_ratio{tenant}` emitida pelo cron; FR-049 lista a mesma métrica na seção Observabilidade. Semântica idêntica. | Consolidar em FR-049 ou referenciar cross-FR em FR-017. Baixa prioridade — não impacta tasks. |
| U1 | Underspecification | MEDIUM | spec.md FR-021 + A13 | FR-021 descreve sampler "estratificado por intent"; A13 marca `[VALIDAR] — se não existir, sampler cai para uniforme`. Plan data-model.md §5.3 e task T043 usam `traces.intent` como fonte. Não há confirmação de que `traces.intent` existe no epic 008. | Adicionar spike task em Phase 1 (`grep traces.intent em repo prosauai`) ou fallback explícito em T043 (`COALESCE(intent, 'unknown')`). |
| U2 | Underspecification | LOW | spec.md FR-020 "sampler estratificado" | Spec não define proporções da estratificação (ex: top-5 intents, ou uniform por intent). Impacta reproducibilidade do DeepEval batch. | Definir em T043 (ou ADR-039): `LIMIT` distribuído proporcionalmente ao `COUNT(*) GROUP BY intent` OU uniform per intent bucket. |
| U3 | Underspecification | LOW | tasks.md T054 (promptfoo-smoke.yml) | Task cita "start Bifrost mock ou usar BIFROST_BASE_URL de ambiente" sem definir qual. Flakiness dependerá dessa decisão. | Decidir entre (a) Bifrost real com API key de CI (risco de custo), (b) mock deterministic em repo. Recomendo (b). |
| CS1 | Constitution Alignment | LOW | Plan §Constitution Check | Plan declara PASS em todos 9 princípios. Validação rápida confirma: 1 lib nova (`deepeval`), fire-and-forget ADR-028 honrado, feature flag reversível <60s, TDD com cobertura target ≥95%. Nenhuma violação aparente. | Nenhuma ação. |
| E1 | Edge Case Gap | LOW | spec.md §Edge Cases | Edge case "Postgres recusa INSERT por constraint inesperada" não listado. Dado que fire-and-forget (A6) aceita perda ≤0.5%, vale adicionar explicitamente. | Considerar adicionar em próxima iteração (não-bloqueante). |

---

## Coverage Summary

**Functional Requirements with buildable work**: 54 FRs. Mapeamento (inferência por keywords e task descriptions):

| FR range | Cobertura observada | Tasks principais |
|----------|--------------------|-----------------|
| FR-001…FR-008 (US1 persist online) | ✅ Completa | T021-T031 |
| FR-009…FR-012 (feature flag) | ⚠️ FR-011 pendente (A1 acima) | T015, T018-T019, T071 |
| FR-013…FR-018 (US2 auto_resolved) | ✅ Completa | T012, T032-T039 |
| FR-019…FR-027 (US3 DeepEval batch) | ✅ Completa | T040-T051 |
| FR-028…FR-031 (golden_traces table + endpoint) | ✅ Completa | T058-T065 |
| FR-032…FR-035 (Promptfoo CI) | ✅ Completa (com I2) | T052-T057 |
| FR-036…FR-041 (Admin UI) | ✅ Completa | T074-T081 |
| FR-042…FR-045 (Alerting) | ⚠️ C1+C2 gaps | T016, T089 |
| FR-046…FR-048 (LGPD/Privacy) | ✅ Completa | T082-T083 |
| FR-049…FR-051 (Observability) | ⚠️ C3 gap trace_id isolation | T016, T045, T050 |
| FR-052…FR-054 (Retention) | ⚠️ I1 (PR placement risk) | T066-T069 |

**Success Criteria (buildable portion)**: 12 SCs. Todos têm gate explícito em tasks:
- SC-001 (coverage online) → T030 + T089 monitoring
- SC-002 (coverage offline) → T049 integration
- SC-003 (zero latency impact) → T031 benchmark gate PR-A
- SC-004 (KPI visible) → T037 + T075
- SC-005 (CI gate) → T054
- SC-006 (dataset grows) → medido pós-rollout (T096)
- SC-007 (flag reversible) → T019 + T071
- SC-008 (shadow gate) → T094 rollout criterion
- SC-009 (dashboard <1s) → T081 playwright bench
- SC-010 (tenant segregation) → T077
- SC-011 (cost ≤budget) → T099
- SC-012 (CI <3min) → T054 timeout

**Unmapped Tasks**: Nenhuma task órfã detectada — todas as 105 tasks mapeiam para FR, SC ou polish cross-cutting explícito.

**Constitution Alignment Issues**: Nenhuma. Plano passa nos 9 princípios.

---

## URL Coverage Check (testing: present)

`platform.yaml` tem bloco `testing:` com `startup.type=docker` e 6 URLs declaradas. Rotas novas desta epic:

| Rota nova | Declarada em testing.urls? | Ação |
|-----------|---------------------------|------|
| `POST /admin/traces/{trace_id}/golden` | Não (endpoint dinâmico com path param) | Aceitável — URLs dinâmicas validadas via Journey J-001 (T105) |
| `PATCH /admin/tenants/{id}/evals` | Não | Mesmo caso — endpoint admin autenticado |
| `GET /admin/metrics/evals` | Não | Mesmo caso |

**Finding**: URLs declaradas em `testing.urls` são genéricas de health/frontend/webhook. Os 3 endpoints admin novos não entram nesse bloco (padrão epic 008 também não declara). Aceitável — cobertura feita via Playwright E2E (T080) e unit/integration tests. Nenhuma ação necessária.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Requirements (FR) | 54 |
| Total Success Criteria (SC) | 12 |
| Total Assumptions | 22 (7 marked [VALIDAR]) |
| Total Tasks | 105 |
| Coverage % (FR → ≥1 task) | ~96% (52/54; FR-011 pendente, FR-043 parcial) |
| Ambiguity Count | 2 (FR-011, FR-043) |
| Coverage Gaps | 3 (below_threshold wire, shadow-alert bypass test, batch trace_id isolation test) |
| Inconsistencies | 3 (retention in PR-C risk, golden table ordering, US4-US5 dependency) |
| Duplication Count | 1 (FR-017 vs FR-049, low impact) |
| Underspecifications | 3 (intent column, sampling proportions, Bifrost CI mock) |
| Critical Issues (BLOCKER) | 0 |
| High Issues | 2 (A1, I1) |
| Medium Issues | 5 (A2, C1, C2, I2, U1) |
| Low Issues | 5 (C3, I3, D1, U2, U3) |

---

## Next Actions

Nenhum issue **CRITICAL** — epic pode prosseguir para `/speckit.implement` com as seguintes mitigações durante execução:

### HIGH priority (tratar antes ou no início do PR-A)

1. **A1 (FR-011 VALIDAR tenants.yaml writer)**: Em Phase 1, adicionar spike: `grep -r "yaml.safe_dump\|write_text" apps/api/prosauai/config*` no repo prosauai. Se epic 010 não tem writer, adicionar task dedicada antes de T071.
2. **I1 (Retention PR placement)**: Mover T066-T069 (retention cron) de Phase 7 para Phase 5 (junto com DeepEval batch) ou Phase 2 (foundational). Garante que PR-B inclui retention mesmo se PR-C sacrificado.

### MEDIUM priority (tratar durante US1/US3 implementation)

3. **C1 (below_threshold emission)**: Adicionar subtask em T022 para comparar score vs `tenant_config.evals.alerts` pós-INSERT, emitir `eval_score_below_threshold_total` quando violado. Testar em T027.
4. **C2 (shadow alert bypass test)**: Adicionar caso em T027: shadow mode + score < threshold → métrica persiste, alerta NO-OP.
5. **I2 (golden ordering)**: Reordenar tasks: T058 (migration 5) + T060-T061 (queries + endpoint) antes de T055 (generator), OU documentar que T055 tolera tabela vazia em US4.
6. **U1 (traces.intent column)**: Spike em Phase 1 para confirmar existência. Fallback: T043 usa `COALESCE(intent, 'unknown')`.

### LOW priority (tratar durante polish / Phase 9)

7. **C3, I3, D1, U2, U3, E1**: Ajustes de spec/docs/tests incrementais. Nenhum bloqueia merge.

### Recomendação de execução

**Pode prosseguir para `/speckit.implement`** após aplicar mitigações HIGH (A1, I1). Risco baseline baixo — zero BLOCKERs, alto alinhamento entre spec/plan/tasks/constitution. Coverage ~96% dos FRs com tasks 1:1. Gates de merge explícitos (T031 benchmark, T080 Playwright, T099 custo) garantem falsificabilidade.

### Remediação automática

Se desejar, posso gerar em pull separado:

- **R1**: Patch em tasks.md movendo T066-T069 para Phase 5 (cobre I1).
- **R2**: Nova subtask "T022b: emit below_threshold metric post-insert" (cobre C1+C2).
- **R3**: Spike task em Phase 1 para validar A1 + U1.

Diga "aplicar R1" / "aplicar R1+R2+R3" e gero o patch — não aplico automaticamente (policy read-only do `/speckit.analyze`).

---

<!-- HANDOFF -->
---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Pre-implement analyze concluído: 0 BLOCKERs, 2 HIGH (A1 tenants.yaml writer pendente, I1 retention cron em risco de ser sacrificado com PR-C), 5 MEDIUM, 5 LOW. Coverage 96% dos 54 FRs. 105 tasks mapeiam bem para spec. Recomendo aplicar mitigações HIGH antes de T001 ou absorver durante PR-A (A1) e PR-B (I1 via move tasks). Zero violação de constitution. Gates de merge rigorosos (T031, T080, T099)."
  blockers: []
  confidence: Alta
  kill_criteria: "(a) Spike A1 revela ausência de YAML writer E epic 010 writer não é reutilizável → FR-011 precisa refactor (endpoint vira no-op com message 'use redeploy'). (b) T066-T069 permanecerem em Phase 7 e PR-C ser sacrificado → retention não vai a produção → storage e LGPD comprometidos após 90d. (c) FR-042/043 alerting nunca é wireado → SC-008 gate (shadow → on decision) perde sinal crítico."
