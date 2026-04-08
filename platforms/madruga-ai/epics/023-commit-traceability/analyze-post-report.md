# Post-Implementation Analysis Report — Epic 023: Commit Traceability

**Generated**: 2026-04-08
**Phase**: analyze-post (post-implementation consistency check)
**Artifacts analyzed**: spec.md, plan.md, tasks.md, pitch.md + implemented code
**Branch**: `epic/madruga-ai/023-commit-traceability`

---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | CRITICAL | plan.md (entire file) | plan.md é um template vazio — nunca foi preenchido pelo speckit.plan. Tasks foram geradas diretamente de spec.md + pitch.md, sem design artifacts (research.md, data-model.md, contracts/). | Aceitar como decisão pragmática — pitch.md contém toda a arquitetura necessária. Registrar como [DECISAO DO USUARIO]. Plan.md não bloqueia implementação. |
| C1 | Coverage Gap | HIGH | FR-008, FR-009, FR-010, FR-011 | Backfill script (`backfill_commits.py`) não existe. Tarefas T032-T040 (Fase 6) não implementadas. US4 inteira sem cobertura. | Implementar antes do merge — sem backfill, o histórico retroativo fica vazio (SC-002, SC-003 falhando). |
| C2 | Coverage Gap | HIGH | FR-012, FR-013, FR-014, FR-015 | Portal aba "Changes" não existe. Nenhum componente em `portal/src/components/changes/`. Tarefas T026-T031 (Fase 5) não implementadas. US3 inteira sem cobertura. | Implementar antes do merge — sem portal, SC-004 e SC-007 falham. |
| C3 | Coverage Gap | HIGH | FR-016, FR-018 | Reseed e JSON export não implementados. `post_save.py` não tem funções `sync_commits()` ou `export_commits_json()`. Tarefas T041-T045 (Fase 7) e T026-T028 pendentes. | Implementar antes do merge — reseed é safety net (SC-006 depende). |
| U1 | Underspecification | MEDIUM | hook_post_commit.py:L204-208 | SHA composto (`sha:platform`) para commits multi-plataforma quebra a semântica de SHA git. A spec (FR-001) diz "sha UNIQUE" mas o valor armazenado não é o SHA real do git quando multi-platform. Impacta: backfill (precisa usar mesma convenção), portal (link GitHub precisa do SHA real, não composto). | Extrair SHA real para link GitHub. Considerar alternativa: composite key (sha + platform_id) em vez de sha composto no campo text. Ou aceitar e documentar a convenção. |
| U2 | Underspecification | MEDIUM | hook_post_commit.py:L209 | Import `from db_pipeline import insert_commit` dentro de `main()` depende de PYTHONPATH setado pelo shell wrapper. Se chamado diretamente (não via git hook), falha com ModuleNotFoundError. | Usar import relativo ou adicionar sys.path no início do script (como feito nos testes). |
| U3 | Underspecification | MEDIUM | db_pipeline.py:L535 | `insert_commit()` faz `conn.commit()` dentro da função. Para commits multi-plataforma, cada plataforma faz um commit separado ao DB. Se falhar no meio, metade dos registros é salva. | Mover `conn.commit()` para o caller (`main()` em hook_post_commit.py) para transação atômica. NOTA: hook_post_commit.py L222 já faz `conn.commit()` no final, resultando em double-commit. |
| T1 | Coverage Gap | MEDIUM | db_pipeline.py:L613-651 | `get_commit_stats()` implementada (T012) mas SEM testes. Nenhum test case em test_db_pipeline.py cobre esta função. | Adicionar testes para get_commit_stats: caso normal, DB vazio, filtro por plataforma. |
| T2 | Inconsistency | MEDIUM | tasks.md T024 vs Makefile:L50-54 | T024 marcada como `[ ]` (não completada) mas `install-hooks` target JÁ existe no Makefile. Task completada mas não registrada. | Marcar T024 como [x] no tasks.md. |
| T3 | Inconsistency | MEDIUM | tasks.md T025 vs test results | T025 marcada como `[ ]` mas todos os 84 testes passam (31 hook + 53 DB). Task completada mas não registrada. | Marcar T025 como [x] no tasks.md. |
| I2 | Inconsistency | LOW | pitch.md vs hook_post_commit.py | Pitch diz "Hook ~150 LOC". Implementação real: 232 LOC. Dentro do limite <300 LOC do CLAUDE.md, mas 55% acima da estimativa. | Aceitável — LOC estimates 1.5-2x (CLAUDE.md gotcha). Sem ação necessária. |
| I3 | Inconsistency | LOW | pitch.md vs db_pipeline.py | Pitch diz "DB functions ~80 LOC (em db_pipeline.py)". Implementação real: ~152 LOC (linhas 500-651). 90% acima da estimativa. | Mesmo caso de I2 — estimativa base vs real com docstrings. Aceitável. |
| I4 | Inconsistency | LOW | spec.md FR-001 vs 014_commits.sql | Spec diz `files_json TEXT` (nullable implícito). Migration define `files_json TEXT NOT NULL DEFAULT '[]'`. Melhor que a spec — garante sempre JSON válido. | Nenhuma ação — implementação é mais robusta que a spec. |
| I5 | Inconsistency | LOW | spec.md FR-001 vs 014_commits.sql | Spec não menciona CHECK constraint em `source`. Migration adiciona `CHECK (source IN ('hook', 'backfill', 'manual', 'reseed'))`. Melhor que a spec. | Nenhuma ação — melhoria sobre a spec. |
| D1 | Duplication | LOW | hook_post_commit.py + (futuro) backfill | Lógica de detecção de plataforma e epic será duplicada entre hook e backfill. Tasks.md reconhece isso (US5 "reuses detection logic from hook"). | Extrair funções compartilhadas para módulo comum quando backfill for implementado. |

---

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Status | Notes |
|-----------------|-----------|----------|--------|-------|
| FR-001 (tabela commits) | ✅ | T001 | ✅ Implementado | Migration 014 criada e aplicada |
| FR-002 (CRUD) | ✅ | T005-T008 | ✅ Implementado | 4 funções + get_commit_stats (extra) |
| FR-003 (hook automático) | ✅ | T018-T023 | ✅ Implementado | hook_post_commit.py + shell wrapper |
| FR-004 (detecção plataforma) | ✅ | T018-T019 | ✅ Implementado | parse_branch + detect_platforms_from_files |
| FR-005 (detecção epic) | ✅ | T018, T020 | ✅ Implementado | parse_branch + parse_epic_tag |
| FR-006 (multi-plataforma) | ✅ | T016, T022 | ✅ Implementado | 1 row por plataforma com SHA composto |
| FR-007 (best-effort) | ✅ | T017, T022 | ✅ Implementado | try/except em main(), stderr logging |
| FR-008 (backfill script) | ✅ | T035-T039 | ❌ **Não implementado** | backfill_commits.py não existe |
| FR-009 (backfill idempotente) | ✅ | T034, T039 | ❌ **Não implementado** | Depende de FR-008 |
| FR-010 (estratégia híbrida) | ✅ | T035-T037 | ❌ **Não implementado** | Depende de FR-008 |
| FR-011 (commits pré-006) | ✅ | T033, T038 | ❌ **Não implementado** | Depende de FR-008 |
| FR-012 (portal aba Changes) | ✅ | T029-T030 | ❌ **Não implementado** | Nenhum componente portal criado |
| FR-013 (filtros portal) | ✅ | T029 | ❌ **Não implementado** | Depende de FR-012 |
| FR-014 (stats portal) | ✅ | T012, T029 | ⚠️ **Parcial** | get_commit_stats() existe mas portal não consome |
| FR-015 (SHA link GitHub) | ✅ | T029 | ❌ **Não implementado** | Depende de FR-012 |
| FR-016 (reseed sync) | ✅ | T043-T044 | ❌ **Não implementado** | post_save.py não tem sync_commits |
| FR-017 (hook <500ms) | ✅ | T046 | ❌ **Não verificado** | Teste de performance não executado |
| FR-018 (JSON export) | ✅ | T026-T028 | ❌ **Não implementado** | Nenhuma função de export JSON |

---

## Constitution Alignment Issues

| Principle | Status | Detail |
|-----------|--------|--------|
| VII. TDD | ✅ OK | Fases 1-4 seguem TDD — testes escritos antes de implementação, 84 testes passando |
| VII. TDD | ⚠️ PARCIAL | `get_commit_stats()` implementada sem teste correspondente |
| IX. Observability | ⚠️ PARCIAL | Hook loga erros para stderr mas não usa structured logging (JSON format). Aceitável para hook <300 LOC — structured logging seria over-engineering |
| I. Pragmatism | ✅ OK | Implementação foca em resolver o problema (captura automática) |
| IV. Fast Action | ✅ OK | MVP (US1+US2) priorizado e funcional |

---

## Unmapped Tasks

Nenhuma task órfã — todas as tasks mapeiam para user stories ou fases cross-cutting.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Requirements (FR) | 18 |
| Total Tasks | 50 |
| Tasks Implementadas | 25 (T001-T023, T024*, T025*) |
| Tasks Pendentes | 25 (T026-T050) |
| Coverage % (FR com ≥1 task implementada) | 39% (7/18 FRs implementados) |
| Coverage % (FR com task definida) | 100% (18/18 FRs têm tasks) |
| Ambiguity Count | 2 (U1 SHA composto, U2 import path) |
| Duplication Count | 1 (D1 detecção plataforma hook/backfill) |
| Critical Issues Count | 1 (I1 plan.md vazio — aceitável) |
| Tests Passing | 84/84 (100%) |
| LOC New Code | ~550 (hook 232 + DB functions 152 + migration 22 + shell wrapper 13 + tests 440) |

*T024 e T025 implementadas mas não marcadas no tasks.md

---

## Implementation Progress by Phase

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| 1 — Setup | T001-T002 | 2/2 | ✅ Complete |
| 2 — Foundational | T003-T009 | 7/7 | ✅ Complete |
| 3 — US1 Query | T010-T013 | 4/4 | ✅ Complete |
| 4 — US2 Hook | T014-T025 | 10/12 | ⚠️ T024-T025 done but unchecked |
| 5 — US3 Portal | T026-T031 | 0/6 | ❌ Not started |
| 6 — US4 Backfill | T032-T040 | 0/9 | ❌ Not started |
| 7 — US5 Reseed | T041-T045 | 0/5 | ❌ Not started |
| 8 — Polish | T046-T050 | 0/5 | ❌ Not started |

---

## Success Criteria Validation

| SC | Description | Status | Evidence |
|----|-------------|--------|----------|
| SC-001 | 100% commits registrados <500ms | ⚠️ Funcional, não verificado performance | Hook existe e funciona; T046 (timing) não executado |
| SC-002 | Backfill captura ≥95% histórico | ❌ Não implementado | backfill_commits.py não existe |
| SC-003 | 21 commits epic 001 vinculados | ❌ Não implementado | Depende de backfill |
| SC-004 | Consulta epic <10s via portal | ❌ Não implementado | Portal aba Changes não existe |
| SC-005 | Backfill idempotente | ❌ Não implementado | Depende de backfill |
| SC-006 | Hook não bloqueia commits | ✅ Validado | 5 testes de error handling passam |
| SC-007 | Portal Changes funcional | ❌ Não implementado | Componente não criado |

---

## Next Actions

### Bloqueadores para merge (CRITICAL + HIGH)

1. **C1 — Backfill (HIGH)**: Implementar `backfill_commits.py` (Fase 6, T032-T040). Sem backfill, o histórico retroativo — propósito central do epic — não funciona. ~200 LOC estimados.

2. **C2 — Portal Changes (HIGH)**: Implementar aba "Changes" no portal (Fase 5, T026-T031). Sem visualização, o operador ainda depende de `git log` manual.

3. **C3 — Reseed + JSON export (HIGH)**: Implementar `sync_commits()` e `export_commits_json()` em `post_save.py` (Fase 7, T041-T045 + T026-T028). Safety net obrigatória.

### Melhorias recomendadas (MEDIUM)

4. **U3 — Double commit DB**: Remover `conn.commit()` de dentro de `insert_commit()` — deixar o caller controlar a transação. Impacta hook (que já faz commit no final) e futuro backfill.

5. **T1 — Testes get_commit_stats**: Adicionar testes unitários para `get_commit_stats()`. Função existe mas não tem cobertura.

6. **U1 — SHA composto**: Documentar a convenção `sha:platform_id` para multi-platform commits. Garantir que backfill e portal usem a mesma lógica para extrair SHA real (para links GitHub).

7. **T2/T3 — tasks.md desatualizado**: Marcar T024 e T025 como `[x]`.

### Baixa prioridade (LOW)

8. **U2 — Import path**: Adicionar `sys.path` fallback em `hook_post_commit.py` para robustez fora do wrapper.

### Decisão pragmática

9. **I1 — plan.md vazio**: Aceitar. O pitch.md contém todas as decisões arquiteturais necessárias. Plan.md não agrega valor para este epic. [DECISAO DO USUARIO esperada]

### Próximo comando

Se issues acima forem resolvidos:
- `speckit.implement` para completar Fases 5-8

Se issues forem aceitos como-está (MVP sem portal/backfill):
- `/madruga:judge madruga-ai` para review técnico do código implementado

---

handoff:
  from: speckit.analyze (post-implementation)
  to: madruga:judge
  context: "Post-implementation analysis completa. MVP funcional (hook + DB CRUD) com 84 testes passando. 25/50 tasks implementadas. 3 gaps HIGH: backfill, portal Changes, reseed — Fases 5-8 pendentes. 1 issue MEDIUM: double-commit no DB, get_commit_stats sem testes. Recomendação: completar implementação antes do Judge."
  blockers:
    - "Fases 5-8 não implementadas (backfill, portal, reseed, polish)"
  confidence: Alta
  kill_criteria: "Se backfill e portal forem removidos do escopo, ajustar spec.md e tasks.md para refletir escopo reduzido (somente hook + DB CRUD como MVP)."
