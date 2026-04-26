# Specification Analysis Report — Epic 011-evals (post-implement)

**Date**: 2026-04-25
**Mode**: Autonomous post-implementation cross-artifact consistency check (read-only).
**Scope**: spec.md (54 FRs, 12 SCs, 22 assumptions), plan.md (3 PRs, 5 migrations), tasks.md (105 tasks across 10 phases), implement-report.md, decisions.md (22 decisions), pre-implement analyze-report.md.
**Branch**: `epic/prosauai/011-evals`

---

## Executive Summary

Implementação reportada como `all tasks already done` (implement-report.md). Phases 1-9 marcadas `[x]` em tasks.md (T001-T099 visíveis no contexto; T100-T105 deployment-smoke truncados mas mencionados como existentes). 5 migrations aditivas executadas, módulo `evals/` criado, 2 ADRs novos (039-040) finalizados em status `accepted`, 3 ADRs estendidos (008/027/028), feature flag `evals.mode` ativa em `tenants.yaml`, 4 cards admin renderizados, Promptfoo CI gate em `.github/workflows/promptfoo-smoke.yml`, retention cron + LGPD SAR wiring concluídos.

Esta análise pós-implement re-roda os checks da pre-implement analyze-report e identifica:
1. Quais findings da pre-analyze foram mitigados durante implementação (resolved).
2. Findings novos que emergiram do código entregue (post-impl).
3. Drift detection candidate flags entre artefatos finais.

---

## Findings Table

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| R1 | Resolved (was A1) | — | tasks.md T071 | Pre-analyze flagou FR-011 `[VALIDAR]` sobre writer programático de `tenants.yaml`. T071 implementou escrita atômica com backup `.bak` + fsync. | Closed. Atualizar spec FR-011 removendo marker `[VALIDAR]`. |
| R2 | Resolved (was C1) | — | T022 docstring + persist.py | Pre-analyze C1: `persist` não comparava score vs threshold para `below_threshold_total`. T022 incorporou `maybe_emit_below_threshold` (passo (d) na docstring da task). | Closed. Verificar via grep do método em produção. |
| R3 | Resolved (was C2) | — | T035 unit + T028 | shadow vs on alert blocking testado em test_heuristic_online com casos `mode=shadow → schedule sem alert`. | Closed. |
| R4 | Resolved (was U1) | — | T043 deepeval_batch.py | A13 [VALIDAR] sobre `traces.intent`: T043 implementou `COALESCE(intent, 'unknown')` + LEFT JOIN para preservar messages sem trace. | Closed. |
| R5 | Partially resolved (was I1) | LOW | tasks.md T066-T069 | Pre-analyze I1: retention placement risk (cut-line poderia sacrificar retention junto com UI). Tasks finais executaram T066-T069 dentro de Phase 7 e foram concluídas. Sem cut, sem risco operacional efetivo, mas a posição arquitetural permanece em uma user-story P3. | Para epic futuro: mover retention para Phase 2 (Foundational) como pattern padrão. Não bloqueia. |
| P1 | Coverage Gap (post-impl) | MEDIUM | spec.md FR-043 + T086 runbook | FR-043 menciona ação `log + email`. Runbook T086 e nota T089 explicitam que "alertas SAO log-only em v1; integração Grafana Alerting/PagerDuty fica para 011.1". Implementação alinhada com decisão consciente, mas FR-043 ainda lista `email` sem caveat. | Atualizar spec FR-043 para "log (v1) — email/critical adiado para 011.1 conforme T089/runbook" ou abrir reverse-reconcile patch para alinhar. |
| P2 | Inconsistency (post-impl) | LOW | T011 vs plan.md §Schema migrations | Plan declara `CREATE UNIQUE INDEX CONCURRENTLY` para migration 2; T011 documentou que dropou `CONCURRENTLY` por incompatibilidade com `dbmate v2.32 transaction:false directive` no harness CI. Migration final é não-CONCURRENTLY com runbook manual para produção. | Atualizar plan.md §Schema migrations + research.md para refletir que UNIQUE index foi feito em transação simples; runbook de produção em tabelas grandes documenta CONCURRENTLY como passo manual. |
| P3 | Underspecification (post-impl) | LOW | T079 frontend | Tenant evals badge mostra "—" quando TenantSummary não projeta `evals.mode` no payload da listagem. Implementação tem TODO implícito ("Surfacing the current mode in the list payload requires a small backend follow-up"). | Criar ticket follow-up (011.1 ou polish) para estender `TenantSummary` com `evals_mode`, evitando UX confusa de badge "—" inicial. |
| P4 | Coverage Gap (post-impl) | LOW | T076 disabled state | T076 documenta que wiring explícito de `GET /admin/tenants/{slug}` para fetchar `evals.mode` foi deferred — empty state "Sem dados ainda" cobre operacionalmente, mas FR-040 exige skeleton específico "Evals desabilitados para este tenant" condicionado em mode=off. | Em produção, validar UX manualmente: tenant com mode=off mostra a copy correta? Se UX mistura "off" com "0 rows" ambiguamente, abrir polish task. |
| P5 | Inconsistency (post-impl) | LOW | T074 gen:api | T074 criou `api.evals.ts` separado em vez de mergear no `api.ts` canônico do epic 008. Decisão pragmática (epic-isolation), mas plan.md §Tipos gerados sugeria `pnpm gen:api` único. | Documentar em quickstart.md + decisions.md que o pattern de epic atual é arquivos `api.<epic>.ts` separados. Atualizar pattern no copier template ou skill se for adotar permanentemente. |
| P6 | Resolved-with-deviation | LOW | T029 / T030 | T030 documenta "Mock-based integration per repo convention — project does not use testcontainers-postgres". Plan.md prescreveu testcontainers-postgres explicitamente para Phase 5 / Phase 7. Implementação seguiu convenção do repo (mock-based). | Atualizar plan.md §Testing strategy ou abrir ADR para registrar que projeto prosauai usa AsyncMock em vez de testcontainers — precedente para epics futuros. |
| P7 | Inconsistency (post-impl) | LOW | T065 cascade test | T065 marcado como `[P]` cascade test, mas validation marcada como "deferred to integration test T065 (mock-based — no live Postgres in this repo's CI; cascade semantics covered by FK clause + integration test assertion)". FR-031 exige cascade real testado. | Validar manualmente em staging que `DELETE FROM public.traces WHERE trace_id=X` apaga linhas em `golden_traces` (one-off SQL teste documentado em runbook LGPD). |
| P8 | Underspecification (post-impl) | LOW | T062 OpenAPI | T062 nota: `apps/api/prosauai` não mantém OpenAPI YAML local; admin frontend regenera tipos do canonical spec em `madruga.ai/platforms/prosauai/epics/011-evals/contracts/openapi.yaml`. Plan dizia "Atualizar `apps/api/prosauai/api/admin/openapi.yaml`". | Confirmar que o spec canônico em `contracts/openapi.yaml` é a source of truth e que não há shadow YAML no backend. Documentar em quickstart.md. |
| C1 | Constitution Alignment | — | All artifacts | Re-check: 9 princípios validados pela implementação real. Pragmatismo (1 lib nova `deepeval`), TDD (≥95% coverage em persist + autonomous_resolution per task descriptions), feature flag reversível, fire-and-forget honrado, observability via structlog facade (sem `prometheus_client` dep). Nenhuma violação. | None. |
| D1 | Drift Detection Hint | LOW | tasks.md T100-T105 | Phase 10 (Deployment Smoke) truncada no contexto desta análise — não foi possível verificar checkmarks `[x]` nem screenshots reais. Implement-report.md genérico ("all tasks already done") não confirma. | Antes de `/madruga:reconcile`, validar manualmente: `ls platforms/prosauai/epics/011-evals/screenshots/` deve ter outputs do Journey/Playwright; `easter-tracking.md` deve ter daily checkpoint final. |

---

## Coverage Summary

| FR range | Pre-impl status | Post-impl status | Gap remanescente |
|----------|-----------------|------------------|------------------|
| FR-001…FR-008 (US1 persist online) | ✅ | ✅ | — |
| FR-009…FR-012 (feature flag) | ⚠️ A1 | ✅ R1 (T071 implementou writer) | Remover [VALIDAR] em FR-011 |
| FR-013…FR-018 (US2 auto_resolved) | ✅ | ✅ | — |
| FR-019…FR-027 (US3 DeepEval batch) | ✅ | ✅ | — |
| FR-028…FR-031 (golden_traces + endpoint) | ✅ | ✅ (com P7 cascade test deferred) | Validar cascade em staging |
| FR-032…FR-035 (Promptfoo CI) | ✅ | ✅ | — |
| FR-036…FR-041 (Admin UI) | ✅ | ✅ (P3+P4 nits UX) | Polish UX badge "—" |
| FR-042…FR-045 (Alerting) | ⚠️ C1+C2 | ✅ R2+R3 + P1 (FR-043 desalinhado com runbook) | Atualizar FR-043 ou abrir reverse-reconcile |
| FR-046…FR-048 (LGPD/Privacy) | ✅ | ✅ (T082-T083 SAR module criado from scratch) | — |
| FR-049…FR-051 (Observability) | ⚠️ C3 | ✅ (T045 OTel root span + T090 metric validation) | — |
| FR-052…FR-054 (Retention) | ⚠️ I1 | ✅ R5 (T066-T069 done) | Reorganizar phase em epics futuros |

**Success Criteria**: 12 SCs. SC-003 (p95 gate) validado por T031 benchmark. SC-005 (CI gate) validado por T054 + smoke suite. SC-007 (feature flag reversível) validado por T018-T019 + config_poller existente. SC-009 (cards <1s) validado por T081 benchmark. Demais SCs (SC-001/002/004/006/008/010/011/012) requerem dados reais de produção pós-rollout (não-blocking pré-merge; dependem do gate operacional Ariel shadow→on).

**Constitution Alignment**: PASS — sem violações detectadas.

**Unmapped Tasks**: Nenhuma tarefa órfã identificada nas Phases 1-9 visíveis. Phase 10 (T100-T105) truncada — D1 acima.

---

## Metrics

- Total Functional Requirements: **54**
- Total buildable Success Criteria: **12** (todos com gate identificável)
- Total Tasks: **105** (T001-T099 visíveis + T100-T105 truncados)
- Tasks marked `[x]` no contexto visível: **99/99** (100%)
- Coverage % (FRs com ≥1 task associada): **~100%**
- Pre-impl findings: **14** (1 HIGH, 4 MEDIUM, 9 LOW)
- Post-impl findings: **8 novos** (0 HIGH, 1 MEDIUM, 7 LOW) + **4 resolved** (R1-R4) + **1 partially resolved** (R5)
- Critical Issues Count: **0** (zero blockers para reconcile)
- Constitution Violations: **0**

---

## Next Actions

1. **No blockers** para `/madruga:judge` ou `/madruga:qa` — implementação consistente com spec e plan.
2. **Antes de `/madruga:reconcile`**:
   - Verificar Phase 10 deployment smoke: confirmar `screenshots/` populado e checkmarks Phase 10 (`[x]`).
   - Atualizar spec FR-011 (remover `[VALIDAR]`) e FR-043 (alinhar com decisão log-only v1) — caso contrário reconcile detectará drift de doc vs runbook.
   - Documentar em decisions.md a decisão pragmática T030/T065 (mock-based testing em vez de testcontainers-postgres).
3. **Polish opcional (não-blocking, candidato 011.1)**:
   - P3: badge "—" no Tenants tab — estender `TenantSummary` com `evals_mode`.
   - P4: empty state UX — diferenciar "off" de "sem dados ainda".
   - P5: documentar pattern `api.<epic>.ts` separado.
   - P7: cascade test manual em staging (one-off SQL).
4. **Suggested commands**:
   - `/madruga:judge` — multi-persona review final do código entregue (4 personas + judge pass).
   - `/madruga:qa` — testing layers (static analysis, tests, browser QA se Playwright MCP disponível).
   - `/madruga:reconcile` — após judge+qa, fechar o ciclo L2.

---

<!-- HANDOFF -->
---
handoff:
  from: speckit.analyze (post-impl)
  to: madruga:judge
  context: "Post-impl analyze: 4 findings pre-impl resolvidos durante implementação (R1-R4), 1 parcialmente resolvido (R5 retention placement). 8 findings novos pós-impl, todos LOW exceto P1 (FR-043 alerting log+email desalinhado com runbook v1 log-only — MEDIUM). Zero CRITICAL/HIGH/Constitution violations. Phase 10 deployment-smoke truncada no contexto — verificar manualmente antes de reconcile. Implementação consistente com plan; pequenos desvios pragmáticos documentados (mock-based testing T030/T065, api.<epic>.ts separado T074, dbmate sem CONCURRENTLY T011, OpenAPI canonical no madruga.ai T062)."
  blockers: []
  confidence: Alta
  kill_criteria: "(a) Phase 10 deployment-smoke não tem screenshots ou checkmarks — bloquear reconcile até confirmar smoke executado. (b) Cascade golden_traces → traces nunca testado em staging real — bloquear rollout `on` em produção até validar SQL one-off. (c) FR-043 spec drift remanescente após reconcile — abrir reverse-reconcile patch."
