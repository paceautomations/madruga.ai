---
title: "Roadmap"
updated: 2026-03-30
---
# Madruga AI — Delivery Roadmap

## Epics Shipped

```mermaid
gantt
    title Madruga AI — Epics Implementados
    dateFormat YYYY-MM-DD
    section MVP
    006 SQLite Foundation       :done, e006, 2026-03-29, 1d
    007 Directory Unification   :done, e007, 2026-03-29, 1d
    008 Quality & DX            :done, e008, 2026-03-29, 1d
    009 Decision Log BD         :done, e009, 2026-03-29, 1d
    010 Pipeline Dashboard      :done, e010, 2026-03-30, 1d
```

---

## Epic Table

| # | Epic | Descricao | Status | Concluido |
|---|------|-----------|--------|-----------|
| 006 | SQLite Foundation | BD SQLite (WAL mode) como state store para pipeline. Tabelas: platforms, pipeline_nodes, epics, epic_nodes, pipeline_runs, events, artifact_provenance. db.py com stdlib Python. Migrations incrementais. | **shipped** | 2026-03-29 |
| 007 | Directory Unification | SpecKit opera em epics/ (unificado). DAG dois niveis (L1 + L2). platform.yaml como manifesto declarativo. Copier template atualizado. | **shipped** | 2026-03-29 |
| 008 | Quality & DX | Boilerplate extraido para knowledge files. Skills enxutas. Auto-review por tier. Verify + QA + Reconcile skills implementadas. | **shipped** | 2026-03-29 |
| 009 | Decision Log BD | BD como source of truth para decisions e memory. FTS5 full-text search. CLI import/export. 5 novas migrations. 20+ funcoes em db.py. | **shipped** | 2026-03-29 |
| 010 | Pipeline Dashboard | Dashboard visual no portal Starlight. CLI `status` com tabela + JSON. Mermaid DAG. Filtros por plataforma. | **shipped** | 2026-03-30 |

---

## Proximos Epics (candidatos — sem arquivos criados)

Epics abaixo sao **candidatos identificados** para proximas iteracoes. Serao detalhados (pitch.md, spec, plan, tasks) apenas quando priorizados para implementacao.

| # | Epic (candidato) | Descricao | Complexidade | Prioridade sugerida |
|---|------------------|-----------|-------------|---------------------|
| 011 | CI/CD Pipeline | GitHub Actions: lint (ruff), portal build, template tests (pytest), platform lint. Zero regressoes em merges. | Pequena | Alta |
| 012 | Multi-repo Implement | `speckit.implement` opera em target repos via git worktree. PRs no repo correto. | Media | Media |
| 013 | Namespace Unification | Merge `speckit.*` em `madruga.*`. Namespace unico e consistente. | Pequena | Media |
| 014 | Runtime Engine Migration | Migrar daemon Python de `general/` para `madruga.ai/src/`. SpeckitBridge integrado. | Grande | Baixa |
| 015 | Daemon 24/7 | MadrugaDaemon asyncio: poll kanban, orchestrator, pipeline autonomo. systemd service. | Grande | Baixa |

