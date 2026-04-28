# Specification Analysis Report — Epic 015: Agent Pipeline Steps

**Date**: 2026-04-27
**Branch**: `epic/prosauai/015-agent-pipeline-steps`
**Mode**: autonomous dispatch (read-only cross-artifact consistency check)
**Inputs analyzed**: `spec.md`, `plan.md`, `tasks.md`, `data-model.md` (referenced), `contracts/openapi.yaml` (referenced), `.specify/memory/constitution.md`

---

## Findings

| ID  | Category | Severity | Location(s) | Summary | Recommendation |
|-----|----------|----------|-------------|---------|----------------|
| C1  | Constitution | LOW | spec.md (whole) | Constituição global do projeto está em PT-BR e foca em pipeline madruga.ai (DAG de skills, ADRs Nygard, etc.); não há principles MUST que conflitem com este épico de domínio (prosauai). | Nenhuma ação — épico não viola constitution. |
| I1  | Inconsistency | HIGH | spec.md FR-021 ("step 10"), plan.md Summary ("step_order=9") | spec descreve `generate_response` como **step 10** ("step 10 do pipeline de conversa"); plan diz **step_order=9** referenciando `STEP_NAMES` real do código. Drift entre spec e plan sobre ordinal do step. | Alinhar spec.md para "step 9" (ou neutro: "o step `generate_response`"); spec não deve cravar ordinal divergente do código. |
| I2  | Inconsistency | HIGH | spec.md FR-040/FR-041/FR-050/FR-051 (versionamento e canary obrigatórios) vs plan.md D-PLAN-02 + tasks Phase 9 (DEFERRED) | Spec exige `agent_config_versions` para versionamento (FR-040), ativação per-version (FR-041) e canary per-version (FR-050/FR-051). Plan declara `agent_config_versions` **inexistente em produção** e adia para épico futuro; tasks Phase 9 marcada como cut-line / DEFERRED. Resultado: requisitos funcionais marcados como obrigatórios no spec não são entregues no plan. | Atualizar spec (downgrade FR-040/041/050/051 para "follow-up" ou marcador `[DEFERIDO ADR-019]`) ou explicitamente reabrir D-PLAN-02. Risco real de implementar e descobrir que aceitação falha contra o spec. |
| I3  | Inconsistency | MEDIUM | spec.md US3 AC4 ("config hot reload — sem deploy") vs spec.md FR-020 + plan D-PLAN-06 (snapshot atômico) | US3 acceptance scenario 4 promete **hot reload imediato** ("já executa com a nova configuração"); FR-020/D-PLAN-06 garantem snapshot atômico que afeta apenas a **próxima** invocação. As duas afirmações são compatíveis mas o "imediato" da US3 sem qualificação pode ser mal interpretado em testes de aceitação. | Reformular AC4 da US3 para "a próxima mensagem entrante para o tenant já executa…" — alinhado a FR-020. |
| C2  | Coverage Gap | HIGH | spec.md FR-046 (rollback button) vs tasks T101 (fallback condicional) | FR-046 exige botão "Rollback" no admin com troca atômica <1 s. Task T101 reconhece que sem `agent_config_versions` (D-PLAN-02) o rollback precisa ser reconstruído via `audit_log` ("Document approach in decisions.md based on T093 outcome") — caminho não está garantido. Sem agent_config_versions, FR-046 não tem implementação determinística. | Decidir e cravar approach no plan/tasks: ou (a) `audit_log` reverso, ou (b) tabela `pipeline_steps_history` minimal, ou (c) marcar FR-046 como deferido. |
| C3  | Coverage Gap | MEDIUM | spec.md FR-052, US4 AC3 ("amostra insuficiente — N=X") vs tasks T112 | T112 cobre FR-052 mas Phase 9 inteira é cut-line / pode ser DEFERRED (T110). Se DEFERRED, FR-052 não tem implementação. | Marcar FR-051/FR-052 como condicionais a Phase 9 (paridade com I2). |
| C4  | Coverage Gap | MEDIUM | spec.md SC-011 (2 tenants em 60 dias, 0 incidente) | Sem task associada — métrica de adoção pós-ship dependente de produto. | Aceitável (SC pós-launch). Mover para `## Post-launch outcome metrics` no spec ou marcar `[outcome — não-buildable]`. |
| C5  | Coverage Gap | LOW | spec.md FR-072 (idempotência migrations) | Coberto por T011 (`ADD COLUMN IF NOT EXISTS`) e T054 (run dbmate twice). OK. | Nenhuma. |
| A1  | Ambiguity | MEDIUM | spec.md FR-064 ("`pipeline_version` (UUID do agent_config_versions)") vs plan T073 (`"pipeline_version": "unversioned-v1"`) | Spec diz que `pipeline_version` deve ser UUID de `agent_config_versions`. Plan grava string literal `"unversioned-v1"` (porque tabela não existe — D-PLAN-02). Spec ainda espera UUID; futuros consumidores que filtrem por UUID falham. | Atualizar FR-064 para refletir D-PLAN-02 (string sentinel até versioning shippar) ou inverter decisão. |
| A2  | Ambiguity | LOW | spec.md FR-024 ("warning logado uma vez por agente/step") | "Uma vez" — em qual janela? Plan T016 implementa via `functools.lru_cache` (process-lifetime, perdido em restart). Aceitável mas spec não declara escopo. | Adicionar nota: "deduplicação por process-lifetime (reseta no restart do worker)". |
| A3  | Ambiguity | LOW | spec.md FR-029 ("input/output truncados a 8 KB"), data-model truncate 4 KB por sub-step | spec FR-029 menciona 8 KB; plan/data-model usa 4 KB por sub-step (cap total 32 KB). Drift de 8 KB → 4 KB. | Alinhar: atualizar FR-029 para 4 KB por sub-step ou justificar diferença (input vs output combinados). |
| A4  | Ambiguity | LOW | spec.md SC-013 ("3 semanas para fase 1") | "Fase 1" definida como FR-001..FR-030 + FR-070..FR-072. Plan/Tasks definem fase 1 como PR-1..PR-4 + PR-3 backend de US5 (FR-060..FR-064 parciais). Levemente diferente. | Alinhar definições — referenciar PRs por número. |
| U1  | Underspecification | MEDIUM | spec.md US3 AC2 (formulário tipado por step_type) | AC2 lista campos por step_type mas omite `condition` (presente em FR-024). Plan T097 inclui condition. | Adicionar "campo opcional `condition`" ao AC2 da US3. |
| U2  | Underspecification | LOW | spec.md FR-014 (`routing_map: {intent → model}`) | Não declara comportamento quando `state.classifier is None` (sem classifier prévio). Plan T021/T025 cobrem esse caso (usa `default_model`). | Spec poderia adicionar nota explícita; aceitável já que comportamento é o esperado. |
| D1  | Duplication | LOW | spec.md FR-026 e Edge Case "loop infinito" | Mecanismo de fallback descrito 3× (FR-026, FR-027, Edge Cases). Consistente, sem conflito. | Consolidar em FR-026 + referência. |
| T1  | Terminology | LOW | spec.md "FALLBACK_MESSAGE" vs plan.md "fallback canned" / "FALLBACK_MESSAGE" | Mistura `fallback canned`, `FALLBACK_MESSAGE`, `mensagem canned`. Mesma coisa. | Glossary 1 termo (sugestão: `FALLBACK_MESSAGE`). |
| T2  | Terminology | LOW | spec.md "agent_pipeline_steps" / "Pipeline Step" / "pipeline step" | Mistura singular/plural/snake/space. Aceitável (snake = tabela, espaço = conceito). | Sem ação. |
| F1  | Coverage Gap | MEDIUM | spec.md FR-006 (índices em `(agent_id, step_order)` e `(tenant_id)`) | Plan T010 cria `idx_pipeline_agent_active (agent_id, is_active, step_order)` — diferente. Possivelmente melhor, mas não bate exatamente FR-006. | Confirmar no plan que esse índice substitui ambos os requisitados; atualizar FR-006 para `(agent_id, is_active, step_order) + (tenant_id)`. |
| F2  | Coverage Gap | LOW | spec.md FR-046 ("rollback <1 s") sem benchmark task | Sem assertiva de latência em tasks. | Adicionar smoke check em T100 ou T101 (Playwright timeout assertion). |
| F3  | Coverage Gap | LOW | spec.md FR-061 (Trace Explorer renderiza sub-steps) | Coberto por T076–T077 (cut-line P2). Se cortado, FR-061 não entrega. | Marcar FR-061 como cut-line ou exigir parte do MVP. |
| F4  | URL coverage | INFO | platform.yaml `testing.urls` | Tasks Phase 11 declaram smoke contra `localhost:3000` e `localhost:3000/admin/login`. Não há rotas FastAPI **novas** introduzidas para usuários finais — apenas admin endpoints (`/admin/agents/{id}/pipeline-steps` GET/PUT). | Verificar manualmente se admin endpoints novos exigem entry em `platform.yaml:testing.urls`. Próxima execução do `qa_startup.py --parse-config` validará. |

---

## Coverage Summary

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001..FR-006 (schema) | ✅ | T010, T013, T014 | Índice diverge (ver F1). |
| FR-010..FR-015 (step types) | ✅ | T024, T025, T043, T082, T083 | Resolver/summarizer em PR-4. |
| FR-020..FR-030 (execution) | ✅ | T015–T029, T044, T045 | Core do épico. |
| FR-040..FR-046 (versionamento + admin) | ⚠️ | T090–T101 | FR-040/041/046 dependem de `agent_config_versions` ausente — ver I2/C2. |
| FR-050..FR-052 (canary métricas) | ⚠️ | T110–T115 | Phase 9 cut-line/DEFERRED. |
| FR-060..FR-064 (trace) | ✅ | T070–T079 | T076–T079 cut-line P2. |
| FR-070..FR-072 (compat) | ✅ | T050, T051, T052, T054 | Hard gate. |
| SC-001..SC-013 | parcial | benchmarks T051, T126 | SC-011 é outcome pós-launch. SC-004 (taxa retomadas) requer análise manual sem task. |

**Unmapped tasks**: nenhuma — todas as tarefas mapeiam de volta a FR/SC ou são polish/setup explicitos.

---

## Constitution Alignment Issues

Nenhuma violação MUST detectada. O épico atende princípios de pragmatismo, observability, TDD na camada crítica (PR-2 escreve testes antes do executor), e auditabilidade (`decisions.md` continuamente enriquecido).

---

## Metrics

- **Total Functional Requirements**: 41 (FR-001 a FR-072 com lacunas numéricas intencionais)
- **Total Success Criteria**: 13 (SC-001..SC-013)
- **Total Tasks**: ~85 (T001..T135)
- **Coverage % (FR com ≥1 task)**: ~93% (3 FRs condicionais a `agent_config_versions`)
- **Ambiguity Count**: 4 (A1..A4)
- **Duplication Count**: 1 (D1)
- **Inconsistency Count**: 3 (I1..I3)
- **Coverage Gap Count**: 5 (C2..C5, F1..F3)
- **Critical Issues Count**: 0
- **High Issues Count**: 2 (I1, I2, C2)

---

## Next Actions

1. **Resolver I2 + C2 (HIGH)**: decidir e documentar approach para FR-040/041/046/050/051 dado D-PLAN-02. Recomendado: marcar esses FRs como `[DEFERIDO ADR-019]` no spec antes de `/speckit.implement`, ou cravar implementação minimal de versioning neste épico. Sem essa decisão, aceitação ficará ambígua.
2. **Resolver I1 (HIGH)**: alinhar ordinal do `generate_response` em spec ↔ código (step 9 conforme `STEP_NAMES`).
3. **Resolver A1 (MEDIUM)**: atualizar FR-064 para refletir sentinel `"unversioned-v1"` enquanto versioning não existe.
4. **Resolver A3 (LOW)**: alinhar 4 KB vs 8 KB no FR-029 vs data-model.
5. **Atualizar F1**: padronizar índice em FR-006.

**Nenhum CRITICAL identificado** — recomendação: usuário pode prosseguir para `/speckit.implement` após alinhar I1, I2 e C2 (mesmo que via update no spec marcando deferimento explícito). Issues MEDIUM/LOW podem ser endereçadas em paralelo durante PR-1.

**Comandos sugeridos**:
- `/speckit.specify` (refinement) — alinhar I1, I2, A1, A3.
- `/speckit.plan` (refinement) — confirmar D-PLAN-02 cobre I2/C2 e atualizar FR-046.
- `/speckit.implement` — pode prosseguir após resolução dos HIGHs.

---

## Optional Remediation

Posso propor, quando solicitado, edits concretos para os top 3 issues (I1, I2, C2). **Nenhum edit foi aplicado** — este relatório é estritamente read-only.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise consistência de epic 015 (spec/plan/tasks/data-model). Zero CRITICAL. 3 HIGH: (I1) ordinal step generate_response divergente entre spec (step 10) e plan (step_order=9 do código real); (I2) FR-040/041/050/051 do spec exigem agent_config_versions que D-PLAN-02 declara inexistente — risco de aceitação falhar; (C2) FR-046 rollback button sem path determinístico sem versioning. Recomendação: alinhar spec antes de implement OR marcar FRs como [DEFERIDO ADR-019]. Demais issues (3 MEDIUM, 8 LOW) endereçáveis durante PR-1. Coverage 93%, Constitution OK, TDD honrado para core executor."
  blockers: []
  confidence: Alta
  kill_criteria: "Análise inválida se: (a) decisão de implementar agent_config_versions dentro deste épico — invalida I2/C2 e revira escopo; (b) cut-line antecipada (semana 2 em vez de 3) — Phase 8/9 não acontecem e FRs P2 viram explicitamente DEFERRED; (c) descoberta em PR-1 de que step_order de generate_response no código mudou (épico 008 mexeu) — atualizar I1; (d) revelação que FR-064 nunca foi usada por consumidor downstream — A1 vira non-issue; (e) novo épico paralelo materializa agent_config_versions antes de PR-5 — re-priorizar Phase 9 para mandatory."
