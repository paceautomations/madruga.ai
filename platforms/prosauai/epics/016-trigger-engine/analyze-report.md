# Specification Analysis Report — Epic 016 Trigger Engine

**Date**: 2026-04-28
**Mode**: Pre-implementation (autonomous dispatch)
**Scope**: spec.md (43 FRs, 12 SCs, 5 user stories) + plan.md (2 PRs, 9 phases) + tasks.md (106 tasks T001-T101 + T900-T905)
**Constitution**: `.specify/memory/constitution.md` — 9 principles (Pragmatismo, Automate, Knowledge, Fast action, Alternativas, Brutal honesty, TDD, Collaborative, Observability)

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Constitution | LOW | plan.md §Constitution Check | Principios listados como I-IX ao inves dos 9 nomeados em CLAUDE.md (Pragmatismo, Automate, Knowledge, etc). Mapeamento implicito mas nao explicito. | Adicionar mapping inline (e.g. "I — Pragmatismo & Simplicidade"). Ja parcialmente feito; consistente. |
| A1 | Ambiguity | MEDIUM | spec.md FR-019; tasks.md T009 | "ON DELETE CASCADE" para LGPD SAR marcado `[VALIDAR]` com DPO mas nao ha tarefa explicita para DPO sign-off antes do PR-A merge. Hard delete e 1-way-door se DPO requerer anonimizacao. | Adicionar T005.5 (ou pre-PR-A): "Validar com DPO/juridico se hard delete via CASCADE atende LGPD ou requer anonimizacao". Bloqueia T006 se anonimizacao requerida. |
| A2 | Ambiguity | LOW | spec.md FR-027 | "Network error / 5xx Evolution MUST disparar retry exponential backoff 3x" — nao especifica delays exatos (1s/2s/4s? 100ms/500ms/2s?). | Decisao deferida ao httpx-retries pattern existente. Marcar `[VALIDAR]` ou linkar config. |
| A3 | Ambiguity | LOW | spec.md edge cases | "Tick processa parte dos customers entao trava (timeout)" — sem definicao explicita de timeout do tick (2s p95 e goal mas nao hard limit). | Definir hard timeout (e.g. 30s) que aborta tick e libera lock advisory. Adicionar a FR-040. |
| U1 | Underspecified | MEDIUM | spec.md FR-022; plan.md §B.1; tasks.md T077 | `EvolutionProvider.send_template` API contract assume Evolution endpoint `/message/sendTemplate/{instance}` existe mas pitch.md riscos lista "Evolution `/sendTemplate` semantica surpreende — Probabilidade Alta". Sem teste de viabilidade pre-PR-B. | Adicionar T005.6 (PR-A): smoke isolado contra Evolution dev sandbox para confirmar endpoint + semantica `components` antes de comprometer PR-B scope. Reduz risco de cut-line. |
| U2 | Underspecified | LOW | spec.md FR-038 | "filtros (tenant, trigger_id, customer_phone, status, date range) com debounce 300ms" — nao especifica formato exato de date range (ISO, picker shadcn). | Trivial; resolvido em T067 implementacao. |
| U3 | Underspecified | LOW | tasks.md T079 | `messages.metadata.triggered_by` populado via subquery em INSERT inbound — nao especifica se e atomico (mesma tx) ou async. Race possivel se INSERT inbound acontecer antes de UPDATE trigger_events.sent_at. | Especificar: subquery captura ultimo `sent_at` no momento do INSERT — e snapshot, race aceitavel (record-keeping nao-critico). |
| G1 | Coverage Gap | MEDIUM | spec.md SC-007; tasks.md | SC-007 "template rejection rate <5% apos 30d" — sem task explicita para baseline measurement ou alarme se rate >5%. Alert FR-034 dispara em >10%, deixando 5-10% gap silencioso. | Adicionar warning rule entre 5-10% (info severity) ou ajustar SC-007 para >10% para alinhar com FR-034. |
| G2 | Coverage Gap | LOW | spec.md SC-012 | SC-012 "shadow→live taxa match efetiva >=80%" — sem task explicita comparando dry_run vs live counts. | T100 (24h baseline live) implicitamente cobre mas nao explicita comparison. Adicionar assert no T100 ou nova T100.1. |
| G3 | Coverage Gap | LOW | spec.md FR-039; tasks.md T079 | `messages.metadata.triggered_by` record-keeping — sem teste explicito que verifica populacao correta. | Adicionar test em T079 (e.g. inbound apos sent_at <24h → metadata populada; >24h → vazia). |
| I1 | Inconsistency | LOW | pitch.md captured #18; spec.md FR-021 | pitch.md menciona apenas `scheduled_event_at` ALTER customers; spec.md adiciona `opt_out_at` como decisao do clarify (FR-021). Coerente mas pitch.md nao foi atualizado pos-clarify. | Cosmetic — pitch.md e snapshot do epic-context. Anotar em decisions.md que opt_out_at foi adicionado em clarify. |
| I2 | Inconsistency | LOW | spec.md FR-023; tasks.md T077 | FR-023 diz "decorado com circuit breaker per (tenant, phone_number_id) — pattern epic 014". Epic 014 esta `drafted`, nao `shipped`. Hard dep. | Ja assumption explicita em spec.md. Cut-line PR-B fica em 016.1 se 014 nao shipa. Tasks T077 implementacao **assume breaker disponivel** sem fallback. Adicionar feature flag para desabilitar breaker se 014 atrasar. |
| I3 | Inconsistency | LOW | tasks.md T034 vs T064 | T034 (US1) diz regenerar openapi.yaml manual em PR-A; T064 (US4) regenera via `pnpm gen:api` em PR-B. Workflow inconsistente. | Padronizar: regenerar uma vez em T064 (PR-B) cobrindo PATCH customers + GET triggers. Remover regeneracao em T034 (admin endpoint customers ja existe; apenas adicionar campos opcionais). |
| D1 | Duplication | LOW | spec.md FR-014; FR-029 | Counters `trigger_cooldown_blocked_total` (FR-029) e `trigger_skipped_total{reason='cooldown'}` (FR-029) — ambos cobrem mesma situacao. | Manter ambos (cooldown_blocked e subset semantico de skipped) per FR-029 explicit. Nao bug, design intencional. |
| D2 | Duplication | LOW | spec.md SC-008; T041 | SC-008 "zero duplicate sends" e FR-017 "idempotencia 2 niveis" — overlapping. T041 testa db_race; T040 testa app-check. Coverage redundante mas saudavel. | OK — defense-in-depth justificado. |
| Q1 | Quality | MEDIUM | tasks.md T035 | Engine orchestrator (T035) e a tarefa mais complexa do PR-A (~6h LOC estimate em plan §A.7). Nao quebrada em sub-tasks. | Quebrar em: T035a (loop por trigger + matcher dispatch), T035b (filtros em ordem), T035c (persist + status states), T035d (snapshot atomico FR-043). Aumenta granularidade + commit frequency. |
| Q2 | Quality | LOW | tasks.md Phase 8 | T076-T101 misturados em Polish — send_template (US1/2/3 dependency, P1) coabita com docs/bench (P3) na mesma fase. | Reorganizar: criar Phase 8a (send_template real — completa US1-3) + Phase 8b (Polish + Ariel rollout). Clarifica priority. |
| Q3 | Quality | LOW | spec.md FR-030 | Cost gauge separate lifespan task com advisory lock proprio — adiciona 2a periodic task ao processo. | Considerar consolidar em 1 lifespan task com 2 sub-loops (cadences diferentes) para reduzir lock overhead. Trade-off: simplicidade vs isolation. Aceitavel como esta. |
| Q4 | Quality | LOW | tasks.md T011 vs Constitution VII | "Testes em 3 camadas" prometido em Constitution Check VII (plan.md). Tasks.md tem unit + integration; falta camada (c) regression suite explicita como gate. | Adicionar T091 ja cobre regression. OK. |

---

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (cron 15s + advisory lock) | Yes | T018, T019, T020 | |
| FR-002 (3 trigger types pre-built) | Yes | T012, T029, T047, T054 | |
| FR-003 (tenants.yaml hot reload <60s) | Yes | T013, T088 | reusa config_poller existente |
| FR-004 (Pydantic validation startup + reload) | Yes | T011, T012, T014, T015 | |
| FR-005 (triggers.enabled per tenant) | Yes | T035 | implicito via skipped check |
| FR-006 (per trigger enabled) | Yes | T035 | |
| FR-007 (pool_tenant RLS) | Yes | T029, T047, T054 | |
| FR-008 (declarative match filters) | Yes | T029 | |
| FR-009 (opt_out_at filter) | Yes | T029, T030 | |
| FR-010 (handoff filter ai_active) | Yes | T029, T047, T054 | |
| FR-011 (hard cap 100) | Yes | T029, T072 | LIMIT 100 SQL + bench |
| FR-012 (cooldown per tenant/customer/trigger) | Yes | T027, T030 | |
| FR-013 (daily cap per customer) | Yes | T027, T030, T072 | |
| FR-014 (skipped status + counters) | Yes | T038 | |
| FR-015 (Redis restore from SQL) | Yes | T030, T042 | |
| FR-016 (trigger_events schema) | Yes | T006 | |
| FR-017 (idempotency 2 layers) | Yes | T006, T016, T017, T041 | UNIQUE INDEX + app-check |
| FR-018 (retention 90d) | Yes | T009 | |
| FR-019 (LGPD CASCADE) | Yes (partial) | T006 | **GAP**: sem task DPO sign-off (A1) |
| FR-020 (scheduled_event_at) | Yes | T007 | |
| FR-021 (opt_out_at) | Yes | T008 | |
| FR-022 (send_template) | Yes | T077 | risco U1 |
| FR-023 (breaker integration) | Yes | T077 | dep epic 014 (I2) |
| FR-024 (warmup cap) | Yes | T077 | dep epic 014 |
| FR-025 (Jinja sandboxed render) | Yes | T028, T031 | reusa epic 015 |
| FR-026 (template rejection alert) | Yes | T078, T084 | |
| FR-027 (5xx retry 3x) | Yes (partial) | T076 | **GAP**: A2 delays nao especificados |
| FR-028 (shadow mode dry_run) | Yes | T035, T097 | |
| FR-029 (5 Prometheus series) | Yes | T021, T038 | |
| FR-030 (cost gauge separate task) | Yes | T081, T082, T083 | |
| FR-031 (OTel spans) | Yes | T023, T037 | |
| FR-032 (structlog logs) | Yes | T037 | |
| FR-033 (cardinality <50K lint) | Yes | T022, T024, T094 | |
| FR-034 (2 alert rules) | Yes | T084, T085, T086 | gap G1 5-10% rejection |
| FR-035 (admin endpoint) | Yes | T060, T061, T062, T063 | |
| FR-036 (BYPASSRLS + filtro tenant) | Yes | T062 | |
| FR-037 (admin UI) | Yes | T066, T067, T068, T069 | |
| FR-038 (filtros debounce) | Yes | T067 | |
| FR-039 (triggered_by metadata) | Yes (partial) | T079 | **GAP**: U3 atomicity, G3 sem teste |
| FR-040 (tick p95 <2s) | Yes | T045, T092 | |
| FR-041 (stuck-detection UPDATE in-place) | Yes | T016, T017, T035 | |
| FR-042 (template_ref cross-ref validation) | Yes | T014, T015 | |
| FR-043 (snapshot atomico tick) | Yes | T035, T074 | |

| Success Criterion | Has Task? | Task IDs | Notes |
|-------------------|-----------|----------|-------|
| SC-001 (Ariel ship em 5d) | Yes | T097-T101 | gated por Meta approval |
| SC-002 (zero ban 30d) | Yes (operacional) | T100 | observacional |
| SC-003 (cap blocks 100%) | Yes | T072 | |
| SC-004 (tick p95 <2s) | Yes | T045, T092 | |
| SC-005 (audit <2min) | Yes | T071, T101 | |
| SC-006 (admin p95 <300ms) | Yes | T060, T093 | |
| SC-007 (rejection <5% 30d) | Yes (gap) | T084 | **GAP G1**: alert dispara em >10% |
| SC-008 (zero duplicate) | Yes | T041, T042 | |
| SC-009 (hard cap exact) | Yes | T072 | |
| SC-010 (hot reload <60s) | Yes | T015 | |
| SC-011 (cost alert <5min) | Yes | T086 | |
| SC-012 (shadow→live >=80%) | Yes (gap) | T100 | **GAP G2**: sem assert explicito |

**Coverage**: 43/43 FRs com tasks (100%); 12/12 SCs com tasks (100%, 2 com gaps menores).

---

## Constitution Alignment Issues

Nenhum conflito CRITICAL detectado. Plan.md §Constitution Check declara passa em todos 9 principios. Validacao independente:

- **Pragmatismo (I)**: ✅ Reusa massivo de patterns (epic 010, 014, 015, 008, 003, 005, 006). Zero deps Python novas.
- **Automate (II)**: ✅ Pattern handoff scheduler + admin trace explorer + retention cron — todos reusados.
- **Knowledge structured (III)**: ✅ decisions.md semeada (35 itens) + 2 ADRs draft (049, 050).
- **Fast action (IV)**: ✅ 2 PRs sequenciais mergeable em develop, reversivel via flag <60s.
- **Alternativas (V)**: ✅ research.md (R1-R7) com pros/cons.
- **Brutal honesty (VI)**: ✅ Reconhece publicamente: cron-only e simplificacao, ADR-006 Phase 2 nunca implementado, opt-out NLP fica 016.1+, hard delete LGPD com [VALIDAR].
- **TDD (VII)**: ✅ Tests escritos antes da implementacao em todas user stories.
- **Collaborative (VIII)**: ✅ 35 decisoes auditaveis (30 epic-context + 5 clarify) + 12 D-PLAN novas.
- **Observability (IX)**: ✅ 5 counters + 1 gauge + 2 alerts + spans OTel + structlog + cardinality lint.

---

## Unmapped Tasks

Nenhuma. Todas as 106 tasks mapeiam para >=1 FR ou SC ou setup/foundational/polish necessario.

---

## Metrics

- **Total Functional Requirements**: 43
- **Total Success Criteria**: 12
- **Total Tasks**: 106 (T001-T101 + T900-T905 deployment smoke)
- **Total User Stories**: 5 (US1-US2 P1, US3-US4 P2, US5 P3)
- **Coverage % (FRs com >=1 task)**: 100% (43/43)
- **Coverage % (SCs com >=1 task)**: 100% (12/12, 2 com gaps menores G1/G2)
- **Ambiguity Count**: 3 (A1 medium, A2 low, A3 low)
- **Underspecified Count**: 3 (U1 medium, U2 low, U3 low)
- **Coverage Gap Count**: 3 (G1 medium, G2 low, G3 low)
- **Inconsistency Count**: 3 (todos low)
- **Duplication Count**: 2 (todos LOW, defense-in-depth justificado)
- **Quality Issues**: 4 (Q1 medium, Q2-Q4 low)
- **Critical Issues Count**: **0**
- **High Issues Count**: **0**

---

## Next Actions

**Veredito**: ✅ **PRONTO para `/speckit.implement`** com ressalvas menores.

Zero CRITICAL ou HIGH findings. 4 MEDIUM findings (A1, U1, G1, Q1) sao melhorias incrementais sem bloqueio:

1. **A1 (LGPD DPO sign-off)** — bloqueia merge de T009 mas nao bloqueia inicio da implementacao. **Recomendado**: criar issue paralela DPO antes de T009.
2. **U1 (Evolution endpoint smoke)** — risco PR-B. **Recomendado**: smoke test isolado em T005.6 antes de comprometer escopo PR-B.
3. **G1 (rejection rate threshold gap 5-10%)** — escolher: ajustar SC-007 para >10% OU adicionar warning rule. **Recomendado**: ajustar SC-007 para alinhar com alert (resolucao trivial em decisions.md).
4. **Q1 (T035 engine orchestrator monolitico)** — quebrar em 4 sub-tasks aumenta commit frequency. **Recomendado** mas nao bloqueia.

LOW findings sao cosmeticos ou ja absorvidos em cut-lines/handoffs documentados.

### Remediation suggestions (top 5)

1. **A1**: Adicionar `T005.5 [P] Validar com DPO se hard delete CASCADE atende LGPD ou requer anonimizacao` em Phase 1 antes de T006/T009.
2. **U1**: Adicionar `T005.6 [P] Smoke test isolado contra Evolution dev sandbox confirmando /sendTemplate semantica components` em Phase 1 (de-risk PR-B).
3. **G1**: Editar SC-007 para `template rejection rate <10%` alinhando com FR-034 alert critical em >10%, OR adicionar regra warning entre 5-10% em config/rules/triggers.yml.
4. **Q1**: Quebrar T035 em T035a/b/c/d (loop+dispatch / filtros / persist+status / snapshot atomico).
5. **U3**: Especificar em T079 que subquery `triggered_by` e snapshot no momento do INSERT inbound (race aceitavel — record-keeping nao-critico).

### Suggested commands

- `/speckit.implement prosauai 016-trigger-engine` — proceder com implementacao (ressalvas absorvidas pelos cut-lines documentados).
- (opcional) `/speckit.tasks prosauai 016-trigger-engine --refine` — aplicar Q1 + A1 + U1 antes de implementar.

---

## Remediation offer

Posso sugerir edits concretos para os 4 MEDIUM findings (A1, U1, G1, Q1) — basta confirmar. Caso contrario, prossiga direto para `/speckit.implement`.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Analise pre-implementation completa. Zero CRITICAL/HIGH findings. 4 MEDIUM findings (LGPD DPO sign-off, Evolution endpoint smoke pre-PR-B, rejection rate threshold gap 5-10%, engine orchestrator T035 monolitico) sao melhorias incrementais sem bloqueio — todas absorvidas nos cut-lines ja documentados em pitch.md/plan.md/tasks.md. Coverage 100% FRs (43/43) e 100% SCs (12/12, 2 com gaps menores). Constitution Check passa em 9/9 principios. Pronto para /speckit.implement."
  blockers: []
  confidence: Alta
  kill_criteria: "Reanalisar se: (a) DPO bloquear hard delete CASCADE → FR-019 + T009 precisam re-design (anonimizacao); (b) Evolution /sendTemplate smoke falhar → PR-B precisa pivot Cloud API direto Meta Graph; (c) operador escolher cancelar epic apos PR-A → re-spec necessario (PR-B vira 016 cancelado, dry_run continua util)."
