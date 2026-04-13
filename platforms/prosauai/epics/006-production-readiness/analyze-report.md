# Specification Analysis Report — Epic 006 Production Readiness

**Data**: 2026-04-12
**Artefatos analisados**: spec.md, plan.md, tasks.md, research.md, data-model.md, contracts/
**Status**: Pre-implementation analysis

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | CRITICAL | spec.md:FR-010, spec.md:US6-AC4, plan.md:L40, research.md:L95-100, data-model.md:L86 | **FR-010 afirma que messages DEVE ter UNIQUE index global em `id`**, mas plan.md e research.md corrigem explicitamente: PG 15 NÃO suporta UNIQUE(id) em tabela particionada por `created_at`. Tasks.md (T009) já implementa a remoção da FK. Spec não foi atualizada. | Atualizar FR-010: remover UNIQUE index global, documentar remoção da FK e validação app-level. Atualizar US6-AC4 para remover cenário de FK. |
| I2 | Inconsistency | HIGH | spec.md:FR-015, spec.md:FR-020, spec.md:US5-AC3, plan.md:L41, research.md:L139-141, tasks.md:T022 | **Spec descreve Phoenix schema isolation via `search_path`** (FR-015: "usando search_path=observability", FR-020: "via search_path na connection string"). Plan e research corrigem: usar `PHOENIX_SQL_DATABASE_SCHEMA` env var (oficial desde v4.33.0). Tasks.md T022 implementa corretamente com env var. Spec ficou desatualizada. | Atualizar FR-015 e FR-020 para referenciar `PHOENIX_SQL_DATABASE_SCHEMA=observability` em vez de search_path. Atualizar US5-AC3. |
| I3 | Inconsistency | MEDIUM | data-model.md:L138, data-model.md:L86, data-model.md:L239 | **data-model.md contradiz a si mesmo**: tabela de mudanças (L138) diz "FK message_id via UNIQUE index global", mas o texto explicativo (L86) diz "FK removida". ER diagram (L239) marca `message_id` como FK. | Corrigir tabela L138 para "FK removida — validação app-level". Remover anotação FK do ER diagram. |
| I4 | Inconsistency | MEDIUM | plan.md:L458, tasks.md:summary | **Plan estima 20 tasks; tasks.md tem 34.** Plan foi escrito antes da granularização final de tasks. Discrepância causa confusão se alguém ler o plan isolado. | Atualizar "Resumo de Estimativas" no plan.md para refletir 34 tasks. Manter estimativa de 5 dias (razão: tasks são mais granulares mas mesmo escopo). |
| D1 | Duplication | HIGH | tasks.md:T019, T022, T028 | **T019 cria docker-compose.prod.yml JÁ com Phoenix e Netdata configs, mas T022 e T028 reescrevem os mesmos services.** T019 descreve: "Phoenix Postgres backend with PHOENIX_SQL_DATABASE_SCHEMA=observability, Netdata container on 127.0.0.1:19999". T022: "Configure Phoenix in docker-compose.prod.yml: set PHOENIX_SQL_DATABASE_SCHEMA...". T028: "Configure Netdata container in docker-compose.prod.yml...". | Clarificar que T019 cria o arquivo skeleton, e T022/T028 refinam configs específicas. Ou consolidar T022/T028 dentro de T019 e eliminar duplicação. |
| C1 | Coverage Gap | HIGH | spec.md:FR-020, tasks.md | **FR-020 exige validação pós-startup** (`SELECT count(*) FROM information_schema.tables WHERE table_schema = 'observability' > 0`), mas **nenhuma task implementa essa validação**. T022 apenas configura env vars. | Adicionar subtask em T022 ou criar task nova: implementar healthcheck/script que verifica tabelas Phoenix no schema `observability` após startup. |
| U1 | Underspecification | MEDIUM | spec.md:FR-012, tasks.md:T025 | **Cron de retention para Phoenix traces**: FR-012 e T025 especificam `DELETE FROM spans WHERE start_time < threshold`, mas **o nome exato das tabelas do Phoenix no schema `observability` é desconhecido** (Phoenix gerencia seu próprio schema). A query pode falhar se o table name for diferente. | Documentar que a purge de traces Phoenix depende da estrutura interna do Phoenix. Adicionar discovery query no retention.py: listar tabelas no schema `observability` e identificar a tabela de spans dinamicamente. Ou usar a API de cleanup do Phoenix se existir. |
| U2 | Underspecification | MEDIUM | spec.md:FR-014, tasks.md:T025 | **service_role credentials para purge**: FR-014 exige role com BYPASSRLS para DELETE em tabelas não-particionadas. T020 (.env.example) menciona "service_role credentials", mas **nenhuma task detalha como obter/configurar essa credencial** no Supabase. | Adicionar nota no T020 ou quickstart.md: instruções para obter service_role key do Supabase dashboard (Settings > API > service_role key). |
| U3 | Underspecification | LOW | tasks.md:T007 | **Partições iniciais em T007**: task diz "create 3 initial monthly partitions" mas não especifica **quais meses** (mês corrente + 2 futuros? ou baseado na data de execução da migration?). | Especificar: migration cria partições para mês corrente + 2 meses futuros. Como a migration roda no startup, os meses são determinados em runtime. Usar `CURRENT_DATE` no SQL ou criar via migration runner (Python) para gerar nomes dinâmicos. |
| U4 | Underspecification | LOW | tasks.md:T011, contracts/migration-runner.md | **asyncpg multi-statement execution**: research.md (L71) nota que asyncpg suporta múltiplos statements desde v0.27, mas migrations SQL podem conter `DO $$ ... $$` blocks, `CREATE TYPE`, etc. Não há task de validação para SQL syntax compatibility. | T014 (testes) já cobre "applies DDL correctly". Garantir que os testes usem as migrations reais (com ENUMs, DO blocks) e não SQL simplificado. |
| F1 | Inconsistency | LOW | spec.md:Clarifications, spec.md:FR-020 | **Clarification diz search_path funciona**, FR-020 propõe search_path como mecanismo, mas plan/research corrigem para env var. Clarification ficou stale. | Adicionar nota na clarification indicando que foi superseded pela pesquisa (research.md §4). |
| F2 | Inconsistency | LOW | spec.md:Assumptions, data-model.md:L85 | **Spec assumptions (PG 15 UNIQUE)**: "Postgres 15+, que suporta FK em tabelas particionadas e UNIQUE indexes globais em partitioned tables." A segunda parte é incorreta (confirmado pela research). | Corrigir assumption para: "PG 15+ suporta FK em tabelas particionadas. UNIQUE indexes globais NÃO suportam coluna não-partition-key." |
| T1 | Terminology | LOW | tasks.md, plan.md | **"Phase" terminology drift**: plan.md usa "Fase 1/2/3/4" para implementation phases. tasks.md usa "Phase 1-10" com numbering diferente. Fase 1 do plan = Phase 2 do tasks. | Não bloqueante — tasks.md reorganizou fases por user story. Considerar adicionar mapeamento plan→tasks no header do tasks.md. |

---

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 | Yes | T003-T010 | Migration rewrites create all tables in `prosauai` |
| FR-002 | Yes | T003 | Creates `prosauai_ops.tenant_id()` |
| FR-003 | Yes | T003, T015 | Migration + validation test |
| FR-004 | Yes | T003 | `CREATE SCHEMA IF NOT EXISTS admin` |
| FR-005 | Yes | T012 | `server_settings={'search_path': ...}` |
| FR-006 | Yes | T011 | Migration runner with asyncpg |
| FR-007 | Yes | T013 | Lifespan integration, fail-fast |
| FR-008 | Yes | T007 | `PARTITION BY RANGE (created_at)` |
| FR-009 | Yes | T023, T025 | Partition manager + retention cron |
| FR-010 | **STALE** | T009 | **Spec says UNIQUE index; plan/tasks remove FK. Spec needs update.** |
| FR-011 | Yes | T021 | YAML anchor x-logging |
| FR-012 | Yes | T025, T026 | retention.py + retention_cli.py |
| FR-013 | Yes | T026 | `--dry-run` flag (default true) |
| FR-014 | Yes | T025 | DROP PARTITION for messages, BYPASSRLS for others |
| FR-015 | **STALE** | T022 | **Spec says search_path; task uses PHOENIX_SQL_DATABASE_SCHEMA** |
| FR-016 | Yes | T028 | Netdata on 127.0.0.1:19999 |
| FR-017 | Yes | T025 | structlog with run_id, table, rows_purged, etc. |
| FR-018 | Yes | T011 | Runner uses same search_path |
| FR-019 | Yes | T019, T028 | Resource limits in docker-compose.prod.yml |
| FR-020 | **PARTIAL** | T022 | Config done, but **post-startup validation query not implemented** |
| FR-021 | Yes | T025, T026 | Idempotent, structured logging |

### Success Criteria Coverage

| SC Key | Has Task? | Task IDs | Notes |
|--------|-----------|----------|-------|
| SC-001 | Yes | T018-T020 | Docker compose prod + .env.example |
| SC-002 | Yes | T011, T014 | Runner + idempotency tests |
| SC-003 | Yes | T021 | Log rotation config |
| SC-004 | Yes | T025-T027 | Retention + tests |
| SC-005 | Yes | T022 | Phoenix Postgres backend |
| SC-006 | Yes | T028 | Netdata dashboard |
| SC-007 | Yes | T015 | Schema isolation integration test |
| SC-008 | Yes | T025 | DROP PARTITION performance |

---

## Constitution Alignment Issues

| Princípio | Status | Detalhe |
|-----------|--------|---------|
| I. Pragmatismo | ✅ PASS | Soluções simples: script custom, Netdata, sleep loop |
| II. Automatizar | ✅ PASS | Migration runner + retention cron + partition manager |
| III. Conhecimento | ✅ PASS | research.md, data-model.md, contracts/ documentam decisões |
| IV. Ação rápida | ✅ PASS | Forward-only migrations, TDD planejado |
| V. Alternativas | ✅ PASS | Cada decisão tem ≥2 alternativas em research.md |
| VI. Honestidade | ⚠️ PARTIAL | Correção do UNIQUE index feita em plan/research mas **não propagada para spec** |
| VII. TDD | ✅ PASS | T014, T015-T017, T024, T027 cobrem todos os módulos novos |
| VIII. Decisão colab. | ✅ PASS | Clarifications documentadas |
| IX. Observabilidade | ✅ PASS | Log rotation + structlog + Netdata |

**Nota sobre Princípio VI**: A honestidade brutal foi aplicada na correção do UNIQUE index (plan/research), mas a propagação incompleta para a spec viola o princípio de manter informação consistente e acessível.

---

## Unmapped Tasks

Nenhuma task sem requirement associado. Todas as 34 tasks mapeiam para pelo menos um FR ou SC.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 21 |
| Total Success Criteria | 8 |
| Total User Stories | 7 |
| Total Tasks | 34 |
| FR Coverage (FR with ≥1 task) | 21/21 (100%) |
| FR Stale (spec not updated after plan correction) | 2 (FR-010, FR-015) |
| FR Partial (task exists but incomplete) | 1 (FR-020 — missing validation) |
| SC Coverage | 8/8 (100%) |
| Ambiguity Count | 4 (U1-U4) |
| Duplication Count | 1 (D1) |
| Critical Issues | 1 (I1) |
| High Issues | 3 (I2, D1, C1) |
| Medium Issues | 4 (I3, I4, U1, U2) |
| Low Issues | 5 (U3, U4, F1, F2, T1) |
| Total Findings | 13 |

---

## Next Actions

### Before `/speckit.implement` (resolve CRITICAL + HIGH)

1. **[CRITICAL] Atualizar spec.md FR-010 e US6-AC4** — Remover referência a UNIQUE index global. Documentar que FK `eval_scores.message_id` foi removida em favor de validação app-level. Racional já documentado em research.md §3.
2. **[HIGH] Atualizar spec.md FR-015, FR-020, US5-AC3** — Trocar "search_path=observability" por "PHOENIX_SQL_DATABASE_SCHEMA=observability". Alinhar com plan.md e research.md §4.
3. **[HIGH] Resolver duplicação T019/T022/T028** — Clarificar no tasks.md que T019 cria o skeleton do arquivo e T022/T028 adicionam configurações específicas. Ou consolidar em uma única task.
4. **[HIGH] Adicionar task para validação pós-startup do Phoenix** (FR-020) — Script ou healthcheck que verifica `information_schema.tables WHERE table_schema = 'observability'`.

### Recomendado (pode prosseguir sem, mas melhora qualidade)

5. **[MEDIUM] Corrigir data-model.md inconsistências internas** — Tabela L138 e ER diagram L239 ainda referenciam FK que foi removida.
6. **[MEDIUM] Atualizar plan.md task count** — Trocar "20 tasks" por "34 tasks" no resumo de estimativas.
7. **[MEDIUM] Detalhar purge de Phoenix traces** (U1) — Investigar nomes de tabelas do Phoenix no schema observability. Adicionar discovery dinâmico no retention.py.
8. **[MEDIUM] Documentar setup de service_role** (U2) — Instruções no quickstart.md ou .env.example.

### Baixa prioridade (Polish)

9. **[LOW] Especificar meses das partições iniciais** (U3) — Runtime-based via CURRENT_DATE.
10. **[LOW] Corrigir assumption sobre PG 15 UNIQUE** (F2) — Atualizar seção Assumptions da spec.
11. **[LOW] Adicionar mapeamento plan phases → tasks phases** (T1) — Nota no header do tasks.md.

---

## Remediation Summary

**Issues 1-4 são resolvíveis com edits pontuais** (~15 min total): atualizar 3 FRs na spec, 2 ACs, 1 tabela e 1 diagram no data-model, clarificar 1 task boundary, adicionar 1 subtask. Nenhum requer replanejamento ou mudança de arquitetura.

**Nenhum BLOCKER estrutural encontrado.** A arquitetura é sólida, as decisões estão bem fundamentadas (research.md), e a cobertura de tasks é completa. O problema central é **propagação incompleta de correções** da fase de pesquisa para a spec — as 2 correções identificadas no plan.md (UNIQUE index e Phoenix schema mechanism) foram implementadas nos tasks mas não refletidas na spec.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise de consistência completa. 13 findings: 1 CRITICAL (FR-010 UNIQUE index stale na spec), 3 HIGH (Phoenix mechanism stale, task duplication, coverage gap em Phoenix validation). Recomendação: corrigir spec.md (FRs e ACs), data-model.md (tabela e ER), e clarificar T019/T022/T028 antes de implementar. Sem blockers estruturais — arquitetura sólida, cobertura 100% em FR e SC."
  blockers: []
  confidence: Alta
  kill_criteria: "Se corrections do UNIQUE index e Phoenix mechanism não forem propagadas para spec antes do implement, implementador pode seguir spec desatualizada e implementar UNIQUE index impossível ou search_path incorreto."
