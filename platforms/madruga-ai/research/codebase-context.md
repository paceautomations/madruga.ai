---
title: "Codebase Context"
updated: 2026-03-31
---
# Madruga AI — Codebase Context

> Análise de codebase existente (brownfield). Última atualização: 2026-03-31.

---

## Resumo

Monorepo Python + TypeScript (~827 arquivos). Python (stdlib + pyyaml) para tooling de pipeline e estado SQLite. Astro + Starlight + React para portal de documentação. LikeC4 para modelos arquiteturais. Copier para templates multi-plataforma.

---

## Estrutura de Arquivos

```
├── .specify/scripts/       # Tooling Python (db, platform CLI, vision-build, lint)
│   ├── bash/               # Scripts Bash (prereqs, setup, tests)
│   └── tests/              # Pytest para DB e templates
├── .specify/templates/     # Copier template para novas plataformas
│   └── platform/           # copier.yml + template/ (Jinja2) + tests/
├── .claude/commands/madruga/  # 21 skills (L1 + L2 + utilitários)
├── .claude/knowledge/      # 7 knowledge files (contratos, DAG, LikeC4 syntax)
├── .pipeline/              # SQLite DB + 6 migrations SQL
├── platforms/              # 2 plataformas (madruga-ai, fulano)
│   └── <name>/             # business/ engineering/ decisions/ epics/ model/ planning/ research/
├── portal/                 # Astro + Starlight site
│   └── src/                # components/ lib/ pages/ (auto-descobre plataformas)
├── .github/workflows/      # CI: 6 jobs (lint, likec4, db-tests, templates, bash, portal)
└── docs/                   # Docs legados
```

---

## Stack Tecnológico

| Categoria | Tecnologia | Versão | Evidência |
|-----------|-----------|--------|-----------|
| Linguagem | Python | 3.11+ | `.github/workflows/ci.yml:15` |
| Linguagem | TypeScript/JS | ES2022 | `portal/package.json` |
| Framework | Astro + Starlight | 6.0.1 / 0.38.2 | `portal/package.json` |
| Arquitetura | LikeC4 | 1.51.0 | `portal/package.json` (devDep) |
| Banco de dados | SQLite WAL | stdlib | `.specify/scripts/db.py:7` |
| Template | Copier | ≥9.4.0 | `.specify/templates/platform/copier.yml` |
| CI | GitHub Actions | — | `.github/workflows/ci.yml` |
| Linting | Ruff | 0.15.6 | `.ruff_cache/`, `ci.yml:20-21` |
| UI | React | 19.2.4 | `portal/package.json` |

---

## Dependências Principais

| Dependência | Versão | Propósito | Evidência |
|-------------|--------|-----------|-----------|
| `@xyflow/react` | 12.10.2 | Visualização DAG (dashboard) | `portal/package.json` |
| `elkjs` | 0.11.1 | Layout de grafos | `portal/package.json` |
| `astro-mermaid` | 2.0.1 | Diagramas Mermaid no Starlight | `portal/package.json` |
| `js-yaml` | 4.1.1 | Parsing YAML | `portal/package.json` |
| `sharp` | 0.34.2 | Otimização de imagens | `portal/package.json` |
| `svg-pan-zoom` | 3.6.2 | SVG interativo | `portal/package.json` |
| `pyyaml` | — | Parsing YAML (Python) | `.specify/scripts/db.py:37` |

---

## Padrões Detectados

| Padrão | Evidência | Arquivo(s) |
|--------|----------|------------|
| Migrations SQL sequenciais (001→005) | 6 arquivos .sql numerados | `.pipeline/migrations/` |
| WAL mode + busy_timeout 5s | Comentário no header | `.specify/scripts/db.py:7-10` |
| SQLite thin wrapper (stdlib only) | 1.720 LOC, single-writer | `.specify/scripts/db.py` |
| CLI via argparse | Padrão uniforme nos scripts | `platform.py`, `post_save.py`, `skill-lint.py` |
| Copier + Jinja2 templates | Template com `_skip_if_exists` | `.specify/templates/platform/` |
| Contrato de 6 passos por skill | Knowledge file dedicado | `.claude/knowledge/pipeline-contract-base.md` |
| AUTO markers em markdown | `<!-- AUTO:name -->` populados por script | `.specify/scripts/vision-build.py` |
| React lazy loading por plataforma | Imports dinâmicos `likec4:react/<name>` | `portal/src/components/viewers/LikeC4Diagram.tsx` |
| DAG interativo com @xyflow/react | Componente React dedicado | `portal/src/components/dashboard/PipelineDAG.tsx` |
| Auto-descoberta de plataformas | Scan `platforms/*/platform.yaml` | `portal/src/lib/platforms.mjs` |

---

## Integrações

| Serviço | Tipo | Evidência |
|---------|------|-----------|
| GitHub Actions CI | 6 jobs: lint, likec4, db-tests, templates, bash-tests, portal-build | `.github/workflows/ci.yml` |
| LikeC4 CLI | Build + export JSON → pipeline markdown | `vision-build.py`, `platform.yaml:36-37` |
| Copier | Scaffolding + sync de plataformas | `.specify/templates/platform/`, `platform.py` |
| SQLite + FTS5 | State store (nodes, decisions, memory) | `db.py`, `.pipeline/migrations/003b_fts5.sql` |

---

## Scripts Python (core tooling)

| Script | LOC | Propósito |
|--------|-----|-----------|
| `db.py` | 1.720 | Wrapper SQLite — migrations, CRUD, FTS5, seed |
| `platform.py` | 755 | CLI: new, lint, sync, register, status, import/export |
| `skill-lint.py` | 358 | Lint de skills e knowledge files |
| `vision-build.py` | 297 | LikeC4 JSON → tabelas AUTO em markdown |
| `post_save.py` | 258 | Registro de conclusão de skill no DB |
| `sync_memory.py` | 169 | Sync .claude/memory/ ↔ SQLite |
| `config.py` | 14 | Constantes de path compartilhadas |

---

## Observações

- **db.py concentra complexidade**: 1.720 LOC num único arquivo — candidato a split se crescer mais (migrations, queries, seed poderiam ser módulos separados).
- **Sem requirements.txt de produção**: Dependências Python são stdlib + pyyaml. `requirements-dev.txt` existe para CI (ruff, pytest, copier).
- **Portal JS é ~212 arquivos**: Maioria gerada pelo Astro/Starlight. Código custom concentrado em `src/components/` e `src/lib/`.
- **FTS5 opcional**: `db.py` detecta disponibilidade em runtime — degrada gracefully se ausente.
