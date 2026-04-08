# Specification Analysis Report — Epic 023: Commit Traceability

**Generated**: 2026-04-08
**Artifacts analyzed**: spec.md (161 lines), plan.md (104 lines), tasks.md (302 lines), pitch.md (reference)
**Constitution**: v1.1.0

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Inconsistency | CRITICAL | plan.md (entire file) | plan.md é o template bruto — nunca foi preenchido por `/speckit.plan`. Contém placeholders `[FEATURE]`, `[DATE]`, `NEEDS CLARIFICATION` e opções "REMOVE IF UNUSED". tasks.md foi gerado diretamente de spec.md + pitch.md, pulando o design phase. | Rodar `/speckit.plan madruga-ai` para preencher, OU aceitar pitch.md como substituto — pitch contém schema SQL, 9 decisões arquiteturais, approach detalhado, e restrições. Documentar como `[DECISAO DO USUARIO]`. |
| C2 | Constitution | CRITICAL | Constitution IX vs tasks.md (T018-T022, T035-T039) | Constituição Princípio IX exige structured logging para TODAS operações. Hook e backfill mencionam apenas stderr para erros (FR-007). Nenhum task endereça logging estruturado (timestamp, level, correlation_id, context). | Adicionar logging ao hook e backfill. Mínimo: `json.dumps({"timestamp": "...", "level": "INFO/ERROR", "message": "...", "context": {"sha": "..."}})` em stderr. stdlib only (sem structlog). |
| H1 | Inconsistency | HIGH | tasks.md:T002 | T002 verifica migration via `from .specify.scripts.db_core import migrate` — path de import Python inválido (`.specify` é diretório com ponto, não package Python válido). | Mudar para subprocess: `python3 -c "import sys; sys.path.insert(0,'.specify/scripts'); from db_core import migrate; ..."` ou usar padrão existente `make seed`. |
| H2 | Ambiguity | HIGH | spec.md:FR-005, tasks.md:T020 | Tag `[epic:NNN]` extrai apenas número (ex: `015`), mas DB armazena slug completo (ex: `015-whatsapp-daemon`). `parse_epic_tag()` não especifica como mapear NNN → slug. Spec diz retorna `015-*` (com asterisco!) — impreciso. | Definir: armazenar valor exato que hook resolve — slug completo do branch (`023-commit-traceability`) ou NNN puro da tag (`015`). Queries devem usar `LIKE 'NNN%'` para compatibilidade. |
| H3 | Underspecification | HIGH | tasks.md:T029 | `ChangesTab.tsx` não especifica como carrega `commits-status.json`. Portal usa `loadStatusData()` de `platforms.mjs` para pipeline data, mas não existe loader para commits. Componente React precisa de dados — como os recebe? | Adicionar sub-task: criar `loadCommitsData()` em `portal/src/lib/platforms.mjs`, ou passar dados como prop do Astro page (padrão existente com `statusData`). |
| H4 | Underspecification | HIGH | spec.md:FR-015, tasks.md:T029 | SHA deve linkar para GitHub (FR-015), mas nenhum task especifica de onde vem a URL base do repo. `platform.yaml` tem `repo.org` + `repo.name` mas esse dado não está no `commits-status.json`. | Incluir `repo_url` no JSON export (T026): `https://github.com/{org}/{name}` por plataforma. Ou incluir `github_base_url` campo no JSON. |
| H5 | Coverage | HIGH | spec.md:FR-017, tasks.md:T046 | FR-017 exige hook < 500ms. T046 apenas "verifica manualmente" 3 commits. Sem teste automatizado — se hook degradar em CI ou outra máquina, não detecta. | Converter T046 em teste com timing: `time_start = time.time()` → run hook logic → assert < 500ms. Ou aceitar como verificação manual com `[RISCO: no automated perf test]`. |
| M1 | Coverage | MEDIUM | spec.md:FR-014, tasks.md:T012 | `get_commit_stats()` (T012) não tem teste dedicado. T010-T011 testam `get_commits_by_epic` e empty query, mas nunca testam a função de stats (adhoc_pct, commits_per_epic dict). | Adicionar test case para `get_commit_stats()` — verify total_commits, commits_per_epic, adhoc_count com dados conhecidos. |
| M2 | Underspecification | MEDIUM | tasks.md:T043-T044 | `sync_commits()` precisa reusar lógica de detecção do hook. T044 diz "reuses platform detection logic" sem especificar HOW — import direto? Duplicação? Path de import entre hook e post_save? | Extrair funções compartilhadas para módulo importável, ou documentar: `from hook_post_commit import parse_branch, detect_platforms_from_files`. Marcar funções em T018-T020 como importáveis. |
| M3 | Ambiguity | MEDIUM | spec.md:FR-011, tasks.md:T038 | `classify_pre006()` usa `cutoff_sha='d6befe0'` (SHA parcial). Algoritmo de comparação não especificado — como determinar se um commit é "antes" do cutoff? Via posição no git log? Via `git merge-base --is-ancestor`? | Especificar: processar git log sequencialmente e usar flag booleana ao encontrar cutoff SHA. Mais simples que ancestor check. |
| M4 | Terminology | MEDIUM | spec.md, tasks.md | Uso inconsistente de formato de `epic_id`: pitch diz `001-inicio-de-tudo`, spec usa `012-...` (ellipsis), tasks usa `023-commit-traceability`. Backfill precisa do slug — mas merge commit messages podem não conter o slug exato. | Definir convenção: `epic_id` = slug completo do branch (sem `epic/<platform>/` prefix). Backfill extrai do branch name no merge commit. |
| M5 | Coverage | MEDIUM | spec.md:SC-004 | SC-004 (responder "quais commits do epic X?" em <10s via portal) não tem task de teste. Portal testing é inteiramente manual. | Adicionar nota: verificação manual durante QA phase, ou adicionar Playwright test para portal load. |
| M6 | Underspecification | MEDIUM | tasks.md:T026 | `export_commits_json()` não especifica handling de commits multi-plataforma (mesmo SHA em múltiplas rows). JSON exporta todas as rows? Agrupa por plataforma? | Exportar TODAS as rows (incluindo duplicatas cross-platform). Filtro client-side no ChangesTab resolve. Documentar no schema. |
| L1 | Style | LOW | tasks.md | LOC estimates subestimadas (CLAUDE.md: 1.5-2x). Hook 150→225-300, backfill 200→300-400. Backfill pode exceder limite 300 LOC com argparse + logging. | Monitorar durante implementação. Se exceder 300 LOC, extrair `commit_utils.py` com funções compartilhadas. |
| L2 | Inconsistency | LOW | tasks.md:T023 | `.specify/scripts/git-hooks/` directory não existe. Nenhum task cria o diretório. | Adicionar `mkdir -p` implícito em T023 ou T024. |
| L3 | Duplication | LOW | spec.md:FR-009 vs FR-008 | FR-009 (idempotência) é detalhe de implementação de FR-008 (backfill). Poderiam ser merged. | Manter separados — explícito é melhor. Ambos mapeiam para T039. |

---

## Coverage Summary

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (tabela commits) | ✅ | T001, T002 | |
| FR-002 (CRUD functions) | ✅ | T005-T008 | |
| FR-003 (post-commit hook) | ✅ | T018-T022 | |
| FR-004 (platform detection) | ✅ | T018, T019 | |
| FR-005 (epic detection) | ⚠️ | T018, T020 | NNN→slug mapping ambíguo (H2) |
| FR-006 (multi-platform) | ✅ | T019, T022 | Testado T016 |
| FR-007 (best-effort hook) | ✅ | T022 | Testado T017 |
| FR-008 (backfill) | ✅ | T035-T039 | |
| FR-009 (idempotência) | ✅ | T039 | Overlap FR-008 |
| FR-010 (estratégia híbrida) | ✅ | T035-T037 | |
| FR-011 (pre-006 → epic 001) | ✅ | T038, T033 | |
| FR-012 (portal Changes tab) | ✅ | T029, T030 | |
| FR-013 (filtros) | ✅ | T029 | Client-side |
| FR-014 (stats) | ⚠️ | T012, T029 | T012 sem teste (M1) |
| FR-015 (SHA GitHub link) | ⚠️ | T029 | URL base ausente (H4) |
| FR-016 (reseed sync) | ✅ | T043, T044 | |
| FR-017 (< 500ms) | ⚠️ | T046 | Verificação manual apenas (H5) |
| FR-018 (JSON export) | ✅ | T026-T028 | |

**Coverage: 18/18 FRs mapped (100%) — 4 com ressalvas de qualidade**

---

## Constitution Alignment Issues

| Principle | Status | Detail |
|-----------|--------|--------|
| I. Pragmatism | ✅ PASS | Abordagem simples: SQLite + git subprocess + hook |
| IV. Fast Action + TDD | ✅ PASS | TDD enforced — testes antes de implementação em todas fases |
| V. Alternatives | ⚠️ PARTIAL | plan.md deveria documentar alternativas (está vazio). pitch.md cobre parcialmente em Rabbit Holes e Captured Decisions |
| VI. Brutal Honesty | ✅ PASS | Riscos documentados com mitigações |
| VII. TDD | ✅ PASS | Red-Green-Refactor em todas fases |
| VIII. Collaborative Decisions | ✅ PASS | 9 decisões + 5 gray areas resolvidas no pitch |
| **IX. Observability** | ❌ FAIL | **Nenhum logging estruturado especificado para hook ou backfill** |

---

## Unmapped Tasks

Nenhum — todos os 50 tasks mapeiam a pelo menos um FR ou SC.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Requirements (FR) | 18 |
| Total Success Criteria (SC) | 7 |
| Total Tasks | 50 |
| Coverage % (FR with ≥1 task) | 100% (18/18) |
| Coverage % (SC with ≥1 task) | 86% (6/7 — SC-004 sem task) |
| Ambiguity Count | 3 (H2, M3, M4) |
| Duplication Count | 1 (L3) |
| Critical Issues | 2 |
| High Issues | 5 |
| Medium Issues | 6 |
| Low Issues | 3 |

---

## Next Actions

### CRITICAL (resolver antes de `/speckit.implement`):

1. **C1 — plan.md vazio**: Duas opções:
   - **Opção A**: Rodar `/speckit.plan madruga-ai` para preencher com research, data model, architecture decisions. Mais correto processualmente.
   - **Opção B** (recomendado): Aceitar pitch.md como substituto — é excepcionalmente detalhado (190 linhas, schema SQL, 9 decisões, 5 gray areas, LOC estimates, timeline). Adicionar nota ao plan.md: "Architecture documented in pitch.md — plan phase bypassed per user decision." Evita duplicação de esforço.

2. **C2 — Structured logging**: Adicionar ao escopo de T022 e T039 — `json.dumps()` em stderr com timestamp/level/message/context. ~10 LOC adicionais por script. Sem dependência externa.

### HIGH (devem ser resolvidos):

3. **H1 — Fix import path** (T002): Mudar para subprocess ou sys.path.
4. **H2 — Definir `[epic:NNN]` matching**: Armazenar NNN puro ou slug? Queries prefix match?
5. **H3 — Portal data loading**: Adicionar loader function ou prop pattern.
6. **H4 — GitHub URL no JSON**: Incluir repo_url derivado de platform.yaml.
7. **H5 — Performance test**: Automatizar ou aceitar como manual.

### Se CRITICALs resolvidos:

Pode prosseguir para `/speckit.implement`. Issues MEDIUM e LOW podem ser endereçados inline durante implementação sem rework significativo.

---

## Remediation Offer

Deseja que eu sugira edits concretos para os top 5 issues (C1, C2, H1, H2, H3)? Não aplicarei edits automaticamente — esta análise é read-only.

---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise pré-implementação identificou 2 CRITICAL (plan.md vazio + logging ausente), 5 HIGH, 6 MEDIUM. Coverage 100% FRs→tasks. Recomendação: aceitar pitch como substituto do plan (C1) e adicionar structured logging ao scope (C2) antes de implementar."
  blockers:
    - "C1: plan.md é template bruto — decisão pendente: preencher ou aceitar pitch como substituto"
    - "C2: structured logging ausente no hook e backfill — violação constituição IX"
  confidence: Media
  kill_criteria: "Se a decisão sobre plan.md não for tomada, o ciclo L2 fica inconsistente. Se logging não for endereçado, constitution violation persiste."
