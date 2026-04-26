# Specification Quality Checklist: Evals — Offline + Online + Dataset Incremental

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-04-24
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — spec references data shape + behavior, not concrete Python/FastAPI code. Nomes como `asyncpg`, `FastAPI`, `structlog` aparecem **apenas** em Assumptions (dependências do stack existente, necessárias para rastreabilidade), nunca em requirements funcionais.
- [x] Focused on user value and business needs — cada user story abre com papel ("Como operador/CEO/admin/engenheiro") e valor ("quero X para Y").
- [x] Written for non-technical stakeholders — prose em PT-BR, acceptance scenarios em Given/When/Then, jargão técnico apenas onde necessário (SQL em FR-015 por precisão operacional).
- [x] All mandatory sections completed — User Scenarios & Testing, Requirements, Success Criteria, Assumptions todas presentes.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — pitch resolveu todas as gray areas; `[VALIDAR]` e `[DEFINIR]` foram usados conforme vocabulário padrão madruga (ver pipeline-contract-base.md §Uncertainty Markers) em vez de `[NEEDS CLARIFICATION]`, que é reservado para questões bloqueantes.
- [x] Requirements are testable and unambiguous — cada FR referencia comportamento observável (query SQL, métrica Prometheus, log key, UI state) com condição clara.
- [x] Success criteria are measurable — SC-001..SC-012 têm números concretos, janelas temporais, tolerâncias explícitas.
- [x] Success criteria are technology-agnostic (no implementation details) — SC falam de coverage %, p95 latency, valores de KPI, tempo de load de dashboard. Zero menção a stack específico na seção SC.
- [x] All acceptance scenarios are defined — 6 user stories × 3-7 scenarios Given/When/Then = ~30 scenarios cobrindo happy path + edge cases principais.
- [x] Edge cases are identified — 15 edge cases explícitos cobrindo: grupo vs 1:1, payload grande, tenant recém-criado, Bifrost caído, Postgres caído, config flip mid-run, concurrent CI, star duplicado, trace deletado, score fora de range, prompt injection no DeepEval, idiomas, recálculo de auto_resolved.
- [x] Scope is clearly bounded — pitch define cut-line (PR-C sacrificável), spec carrega essa fronteira em prioridades (P3 = golden UI + admin cards).
- [x] Dependencies and assumptions identified — 18 assumptions documentadas (A1..A18), 5 com marcador `[VALIDAR]` para acompanhamento.

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — cada FR-NNN é verificável via SQL/log/métrica/UI; scenarios das user stories cobrem os principais FRs (FR-001..FR-008 → US1 scenarios, FR-013..FR-018 → US2, etc.).
- [x] User scenarios cover primary flows — US1 cobre 100% de persistência online, US2 cobre KPI North Star, US3 cobre métricas de qualidade, US4 cobre CI gate, US5+US6 cobrem admin UX.
- [x] Feature meets measurable outcomes defined in Success Criteria — SC-001..SC-012 mapeiam 1:1 em FRs do epic (SC-001 → FR-001/008; SC-002 → FR-020; SC-003 → FR-001 fire-and-forget + FR-008; etc.).
- [x] No implementation details leak into specification — Functional Requirements descrevem **o que** deve acontecer, não **como**. Menções a `tenants.yaml`, `eval_scores`, `golden_traces` são **nomes de contratos/entidades**, não detalhes de implementação; são necessárias para definir invariants inter-epic.

## Notes

- Spec gerado em modo autônomo (claude -p, sem human-in-the-loop). Nenhum gate humano foi acionado — conforme override do pipeline contract base para autonomous dispatch mode.
- 18 assumptions com 5 `[VALIDAR]` documentam incerteza consciente (A3 DeepEval compat Python 3.12, A9 idioma, A11 canal email, A13 coluna intent, mais A10 `[DEFINIR]` para valor de sample rate em 011.1). Nenhuma é bloqueante para iniciar `/speckit.clarify`.
- Cut-line do pitch preservado: US3+US4 podem virar 011.1 se semana 2 estourar; US1+US2 formam MVP mínimo; US5+US6 (P3) são incrementais.
- Pronto para `/speckit.clarify` ou `/speckit.plan`. Recomendação: rodar `/speckit.clarify` primeiro para pressionar os 5 [VALIDAR] antes de comprometer design.
