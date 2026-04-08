---
title: "Roadmap Reassessment — Epic 023: Commit Traceability"
epic: 023-commit-traceability
platform: madruga-ai
date: 2026-04-08
type: roadmap-reassess
updated: 2026-04-08
---
# Roadmap Reassessment — Epic 023: Commit Traceability

**Data:** 2026-04-08 | **Branch:** epic/madruga-ai/023-commit-traceability
**Epic Status:** shipped (com 1 known limitation: FR-016 reseed sync)

---

## 1. O que o Epic 023 Entregou

| Deliverable | Status | Evidencia |
|-------------|--------|-----------|
| Tabela `commits` no SQLite (migration 014) | ✅ Shipped | Schema com indexes, CHECK constraints |
| Funcoes CRUD em db_pipeline.py | ✅ Shipped | insert_commit, get_commits_by_epic, get_commits_by_platform, get_adhoc_commits, get_commit_stats |
| Post-commit hook (Python) | ✅ Shipped | hook_post_commit.py (232 LOC) + shell wrapper |
| Backfill retroativo | ✅ Shipped | backfill_commits.py (413 LOC) — historico desde epic 001 |
| Portal aba "Changes" | ✅ Shipped | ChangesTab.tsx (364 LOC) + control-panel.astro integration |
| JSON export para portal | ✅ Shipped | export_commits_json() em post_save.py |
| Makefile targets | ✅ Shipped | install-hooks, status-json atualizado |
| Reseed commit sync (FR-016) | ❌ Nao implementado | T041-T045 pendentes — known limitation |

**Judge Score:** 91% (PASS) | **QA Score:** 96% | **Testes:** 895 passando (0 falhas)

---

## 2. Aprendizados que Impactam o Roadmap

### 2.1. Estimativas de LOC continuam subestimadas

| Script | Estimado | Real | Desvio |
|--------|----------|------|--------|
| hook_post_commit.py | 150 LOC | 232 LOC | +55% |
| backfill_commits.py | 200 LOC | 413 LOC | +106% |
| DB functions | 80 LOC | ~120 LOC | +50% |
| ChangesTab.tsx | 200 LOC | 364 LOC | +82% |

**Impacto:** Confirma o gotcha do CLAUDE.md (multiplicar por 1.5-2x). Epics futuros devem usar multiplicador 2x sobre estimativas base. Nao impacta sequenciamento, mas appetites devem ser ajustados.

### 2.2. Debt tecnico identificado

| Debt | Severidade | Epic futuro candidato? |
|------|-----------|----------------------|
| Composite SHA (`sha:platform_id`) para multi-plataforma | Medium | Sim — migration para `UNIQUE(sha, platform_id)` |
| FR-016 reseed sync_commits nao implementado | Medium | Pode ser resolvido em epic de polish ou ad-hoc |
| Logica de deteccao de plataforma duplicada (hook vs backfill) | Low | Refactor quando houver 3o consumer |
| Format check deveria ser pre-commit hook | Low | Ja listado em "Nao Este Ciclo" do roadmap |

### 2.3. Pipeline continua eficiente para epics de infra

Epic 023 completou o ciclo L2 completo (12 nodes) em ~1 dia. Padrao consistente com epics 017-022. O pipeline funciona bem para epics de infraestrutura interna do madruga-ai.

### 2.4. TDD como safety net validado novamente

28 testes pre-escritos para backfill detectaram imediatamente que o script nao existia. QA heal loop criou a implementacao — os testes ja definiam o contrato. Confirma Constitution VII.

---

## 3. Estado Atual do Roadmap

### 3.1. Epics Shipped (completo)

| # | Epic | Data | Impacto |
|---|------|------|---------|
| 006-011 | Fundacao (SQLite, dirs, QA, decisions, dashboard, CI) | 2026-03-29/30 | Infraestrutura base |
| 012-016 | **MVP** (multi-repo, DAG executor, Telegram, Judge, Easter) | 2026-03-31 — 2026-04-01 | Pipeline autonomo funcional |
| 017-021 | Post-MVP (observability, hardening, infra-as-code, quality, intelligence) | 2026-04-04/05 | Robustez e observabilidade |
| 022 | Mermaid Migration | 2026-04-07 | Portal com Mermaid build-time |
| **023** | **Commit Traceability** | **2026-04-08** | **Rastreabilidade de commits no DB e portal** |

**Total: 18 epics shipped** (006-023, exceto 022 que pulou numeracao de 011 para 022).

### 3.2. Milestone Status

| Milestone | Status | Epics | Notas |
|-----------|--------|-------|-------|
| **ProsaUAI Operacional** | ✅ Tooling pronto | 012 | Falta teste end-to-end real |
| **Runtime Funcional** | ✅ Funcional | 012, 013 | DAG executor operacional |
| **Autonomia MVP** | ✅ Alcancado 2026-04-01 | 012-016 | MADRUGA_MODE=auto habilitado |
| **Observabilidade** | ✅ Completa | 017 | Traces, evals, cost tracking |
| **Rastreabilidade** | ✅ Completa | 023 | Commits no DB + portal |

---

## 4. Reavaliacao de Prioridades

### 4.1. Candidatos Existentes no Roadmap

| # | Candidato | Prioridade Anterior | Prioridade Revisada | Justificativa |
|---|-----------|---------------------|---------------------|---------------|
| — | ProsaUAI end-to-end | P0 | **P0** (mantida) | Validacao real do pipeline — North Star metric depende disso. Epic 023 nao altera essa prioridade. |
| — | Roadmap auto-atualizado | P2 | **P2** (mantida) | Nice-to-have. Epic 023 (commits no DB) facilita implementacao futura, mas nao e prerequisito. |

### 4.2. Novos Candidatos Emergentes do Epic 023

| # | Candidato | Problema | Complexidade | Prioridade |
|---|-----------|----------|--------------|------------|
| A | Composite SHA fix | SHA composto quebra link GitHub para commits multi-plataforma. Migration para `UNIQUE(sha, platform_id)` + refactor consumers. | S (1-2d) | P3 |
| B | Reseed commit sync (FR-016) | `post_save.py --reseed` nao sincroniza commits. Safety net incompleto. | XS (0.5d) | P2 |
| C | Pre-commit hooks (format + lint) | 6 arquivos passaram sem formatting no epic 023. `ruff format --check` como pre-commit. | XS (0.5d) | P3 |

### 4.3. Recomendacao de Sequenciamento

**Proximo epic recomendado: ProsaUAI end-to-end (P0)**

Razao: Todos os 18 epics shipped sao infraestrutura interna. O North Star metric (80% epics autonomos pitch-to-PR) so pode ser medido com um epic real em repo externo. ProsaUAI e o candidato natural — tooling ja existe (epic 012).

Os candidatos B (reseed sync) e C (pre-commit hooks) sao pequenos o suficiente para serem resolvidos como quick-fixes (`/madruga:quick-fix`) ou commits ad-hoc, sem necessidade de epic completo.

O candidato A (composite SHA) pode esperar — afeta apenas commits multi-plataforma, que sao raros na pratica.

---

## 5. Riscos Atualizados

| Risco | Status | Atualizacao |
|-------|--------|-------------|
| `claude -p` instavel | Sem ocorrencia no epic 023 | Mantido como risco residual |
| Documentation drift acumulado | **Materializado**: drift 73% no reconcile | Mitigacao: reconcile apos cada epic (confirmado eficaz) |
| Team size = 1 | Materializado: epics sequenciais | Sem mudanca |
| LOC estimates subestimados | **Confirmado**: desvio 50-106% | Mitigacao: multiplicador 2x ja documentado em CLAUDE.md |
| **NOVO**: Reseed incompleto | Hook falha → commits perdidos ate backfill manual | Mitigacao: implementar FR-016 como quick-fix |
| **NOVO**: Composite SHA debt | Links GitHub quebrados para multi-platform commits | Mitigacao: raro na pratica, candidato a epic futuro |

---

## 6. Diffs Concretos para roadmap.md

### 6.1. Tabela "Epics Shipped" — adicionar apos epic 021:

```markdown
| 022 | Mermaid Migration | Migracao de diagramas Mermaid para astro-mermaid v2.0.1. Build-time rendering. Eliminacao de tooling legado (Structurizr/LikeC4). | **shipped** | 2026-04-07 |
| 023 | Commit Traceability | Tabela `commits` no SQLite, post-commit hook Python, backfill retroativo desde epic 001, aba "Changes" no portal com filtros e stats, JSON export. Known limitation: reseed sync nao implementado (FR-016). | **shipped** | 2026-04-08 |
```

### 6.2. Gantt "Epics Implementados" — adicionar:

```
    022 Mermaid Migration         :done, e022, 2026-04-07, 1d
    023 Commit Traceability       :done, e023, 2026-04-08, 1d
```

### 6.3. Delivery Sequence Gantt — adicionar na secao Post-MVP:

```
    022 Mermaid Migration         :done, e022, 2026-04-07, 1d
    023 Commit Traceability       :done, e023, 2026-04-08, 1d
```

### 6.4. Atualizar "Proximos Epics (candidatos)":

```markdown
| # | Candidato | Problema | Prioridade | Status |
|---|-----------|----------|------------|--------|
| — | ProsaUAI end-to-end | Primeiro epic completo processado pelo Easter em repo externo ProsaUAI — validacao real do pipeline autonomo pitch-to-PR | P0 | candidato |
| — | Reseed commit sync (FR-016) | post_save --reseed nao sincroniza commits — safety net incompleto | P2 | candidato (quick-fix) |
| — | Roadmap auto-atualizado | Roadmap gerado automaticamente do estado real dos ciclos, com drift score e status de milestones | P2 | candidato |
| — | Composite SHA migration | SHA composto para multi-plataforma quebra link GitHub. Migrar para UNIQUE(sha, platform_id) | P3 | candidato |
```

### 6.5. Atualizar "Roadmap Risks" — adicionar:

```markdown
| Reseed commit sync incompleto | Commits perdidos pelo hook ficam ausentes ate backfill manual | Baixa | Quick-fix: implementar FR-016 (~0.5d) |
| LOC estimates subestimados (confirmado) | Appetites reais 1.5-2x maiores que planejado | Media | Multiplicador 2x documentado em CLAUDE.md |
```

### 6.6. Dependency graph — adicionar:

```mermaid
    E022["022 Mermaid\nMigration"]
    E023["023 Commit\nTraceability"]

    E017 --> E022
    E017 --> E023
```

---

## 7. Objetivos e Resultados — Atualizacao

| Objetivo de Negocio | Product Outcome | Baseline | Target | Status | Epics |
|---------------------|-----------------|----------|--------|--------|-------|
| Autonomia do pipeline | % skills executaveis via CLI | 0% | 80% | ~70% (estimate) | 013, 016 |
| Tempo de resposta a gates | Tempo medio notificacao→aprovacao | ∞ | <30min | Funcional (Telegram) | 014 |
| Qualidade de specs autonomas | % specs com review multi-perspectiva | 0% | 100% | 100% (Judge ativo) | 015 |
| Pipeline cross-repo | Ciclos L2 em repos externos | 0 | ProsaUAI operacional | Tooling pronto, falta validacao | 012 |
| Uptime do pipeline | Horas/dia easter operacional | 0 | 24h | Funcional (systemd) | 016 |
| **Rastreabilidade** | % commits vinculados a epic/ad-hoc | 0% | 100% | **100% (hook + backfill)** | **023** |

> Novo outcome adicionado: rastreabilidade de commits. Alcancado com epic 023.

---

## 8. Auto-Review

### Tier 1 — Checks Deterministicos

| # | Check | Resultado |
|---|-------|-----------|
| 1 | Report existe e nao esta vazio | ✅ PASS |
| 2 | Epics shipped incluem 022 e 023 | ✅ PASS |
| 3 | Candidatos futuros listados | ✅ PASS (4 candidatos) |
| 4 | Riscos atualizados | ✅ PASS (2 novos) |
| 5 | Diffs concretos para roadmap.md | ✅ PASS (6 diffs) |
| 6 | Sem placeholders (TODO/TKTK/???) | ✅ PASS |
| 7 | HANDOFF block presente | ✅ PASS |
| 8 | Objetivos e Resultados atualizado | ✅ PASS |
| 9 | "Nao Este Ciclo" revisado | ✅ PASS (sem mudancas necessarias) |

---

## 9. Resumo Executivo

Epic 023 (Commit Traceability) foi entregue com sucesso. O pipeline agora rastreia cada commit no DB, com identificacao automatica de plataforma e epic via post-commit hook, historico retroativo via backfill, e visualizacao no portal.

**Impacto no roadmap:**
- **Nenhuma reordenacao necessaria** — ProsaUAI end-to-end continua P0
- **2 novos candidatos pequenos** (reseed sync P2, composite SHA P3) — candidatos a quick-fix
- **Risco confirmado**: LOC estimates subestimados (multiplicador 2x validado)
- **1 known limitation aceita**: FR-016 reseed sync (safety net incompleto)

**Proximo passo recomendado:** Merge do epic 023 e iniciar ProsaUAI end-to-end como proximo epic.

---
handoff:
  from: madruga:roadmap
  to: merge
  context: "Roadmap reassessment completo para epic 023. 18 epics shipped (006-023). ProsaUAI end-to-end continua P0 como proximo epic. 2 novos candidatos pequenos identificados (reseed sync, composite SHA). Roadmap.md precisa dos 6 diffs concretos listados no report. Branch pronta para merge."
  blockers: []
  confidence: Alta
  kill_criteria: "Se ProsaUAI for deprioritizado ou se o pipeline mudar fundamentalmente de abordagem (ex: migrar de SQLite para cloud DB)."
