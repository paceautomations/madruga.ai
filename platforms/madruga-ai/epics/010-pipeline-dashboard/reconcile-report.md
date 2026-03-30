---
title: "Reconcile Report — Epic 010"
platform: madruga-ai
epic: 010-pipeline-dashboard
drift_score: 66.7
updated: 2026-03-30
---

# Reconcile Report — Epic 010 (Platform-Repo Binding + Dashboard)

## Drift Score: 66.7%

6 de 9 documentos estao atualizados. 3 documentos com drift detectado.

---

## Documentation Health Table

| # | Documento | Categorias | Status | Drift Items |
|---|----------|-----------|--------|-------------|
| 1 | business/vision.md | D1 | CURRENT | 0 |
| 2 | business/solution-overview.md | D1 | **OUTDATED** | 1 |
| 3 | engineering/blueprint.md | D2 | CURRENT | 0 |
| 4 | engineering/domain-model.md | D4 | **OUTDATED** | 3 |
| 5 | engineering/containers.md | D2, D8 | CURRENT | 0 |
| 6 | engineering/context-map.md | D8 | CURRENT | 0 |
| 7 | model/*.likec4 | D3 | CURRENT | 0 |
| 8 | decisions/ADR-*.md | D5 | **OUTDATED** | 1 |
| 9 | planning/roadmap.md | D6 | N/A | WARNING: arquivo nao existe |

---

## Raio de Impacto

| Area Alterada | Docs Diretamente Afetados | Transitivamente Afetados | Esforco |
|--------------|--------------------------|-------------------------|---------|
| `local_config` table + `platform.py use/current` | domain-model.md, solution-overview.md | containers.md (minor) | ~20min |
| `platforms` table com repo_org/repo_name/tags | domain-model.md (Platform entity) | ADR-004 (amend) | ~15min |
| Per-platform CLAUDE.md + copier template | Nenhum (feature nova, ja documentada no CLAUDE.md) | — | 0min |

---

## Drift Items

### D1 — Scope Drift

| ID | Doc | Estado Atual | Estado Real | Severidade |
|----|-----|-------------|-------------|------------|
| D1.1 | solution-overview.md:50 | Platform CLI lista: `new, lint, sync, register, list` | CLI agora tem tambem: `use`, `current`, `status --json` | **medium** |

**Diff proposto (solution-overview.md:50):**

Antes:
```
| **Platform CLI** | `platform.py` com comandos `new`, `lint`, `sync`, `register`, `list`. Scaffold de plataformas via Copier, validacao de estrutura, registro no portal. | Arquiteto-Operator | Tempo para criar nova plataforma: < 2min |
```

Depois:
```
| **Platform CLI** | `platform.py` com comandos `new`, `lint`, `sync`, `register`, `list`, `use`, `current`, `status`. Scaffold de plataformas via Copier, validacao de estrutura, registro no portal, plataforma ativa, e pipeline status (tabela + JSON). | Arquiteto-Operator | Tempo para criar nova plataforma: < 2min |
```

---

### D2 — Architecture Drift

Nenhum drift detectado. Blueprint permanece valido — as mudancas sao adicoes ao CLI existente, nao alteracoes na topologia.

---

### D3 — Model Drift

Nenhum drift detectado. Modelos LikeC4 nao precisam de atualizacao — as mudancas sao no schema do BD e CLI, nao em containers ou relacoes.

---

### D4 — Domain Drift

| ID | Doc | Estado Atual | Estado Real | Severidade |
|----|-----|-------------|-------------|------------|
| D4.1 | domain-model.md:114 | "Nao ha banco de dados neste contexto. Toda persistencia e baseada em filesystem" | SQLite existe desde epic 006. Agora com tabela `local_config` e 5 colunas novas em `platforms` | **high** |
| D4.2 | domain-model.md:19-28 | `Platform` entity nao tem campos repo | Platform agora tem: `repo_org`, `repo_name`, `base_branch`, `epic_branch_prefix`, `tags_json` | **medium** |
| D4.3 | domain-model.md:129 | Invariante: "platform.yaml com campos name, lifecycle e views" | Agora tambem tem campos opcionais: `repo:` block e `tags:` | **low** |

**Diff proposto (D4.1 — domain-model.md:112-125):**

Antes:
```markdown
### Storage Model

Nao ha banco de dados neste contexto. Toda persistencia e baseada em **filesystem**:

| Artefato | Formato | Caminho |
|----------|---------|---------|
| Manifesto da plataforma | YAML | `platforms/<slug>/platform.yaml` |
```

Depois:
```markdown
### Storage Model

Persistencia hibrida: **filesystem** (source of truth para escrita) + **SQLite** (interface de leitura, cache, estado local).

| Artefato | Formato | Caminho |
|----------|---------|---------|
| Manifesto da plataforma | YAML | `platforms/<slug>/platform.yaml` |
| Pipeline state | SQLite | `.pipeline/madruga.db` (tabelas: platforms, pipeline_nodes, epics, epic_nodes, local_config) |
| Contexto da plataforma | Markdown | `platforms/<slug>/CLAUDE.md` |
```

**Diff proposto (D4.2 — domain-model.md:19-28):**

Antes:
```
    class Platform {
        +string slug
        +string display_name
        +string lifecycle_stage
        +string[] views
        +map commands
        +path root_dir
        +load_manifest()
        +validate_structure() bool
    }
```

Depois:
```
    class Platform {
        +string slug
        +string display_name
        +string lifecycle_stage
        +string[] views
        +map commands
        +path root_dir
        +string repo_org
        +string repo_name
        +string base_branch
        +string epic_branch_prefix
        +string[] tags
        +load_manifest()
        +validate_structure() bool
        +resolve_repo_path() path
    }
```

**Diff proposto (D4.3 — domain-model.md:129):**

Antes:
```
- Toda plataforma **deve** ter `platform.yaml` com campos `name`, `lifecycle` e `views`
```

Depois:
```
- Toda plataforma **deve** ter `platform.yaml` com campos `name`, `lifecycle` e `views`. Campos opcionais: `repo:` (org, name, base_branch, epic_branch_prefix) e `tags:[]`
```

---

### D5 — Decision Drift

| ID | Doc | Estado Atual | Estado Real | Severidade |
|----|-----|-------------|-------------|------------|
| D5.1 | ADR-004-file-based-storage.md | status: accepted. "File-based storage como persistencia primaria" | SQLite e agora co-primary (tabelas platforms, pipeline_nodes, local_config). Filesystem continua sendo source-of-truth para escrita, mas BD e interface de leitura. | **medium** |

**Recomendacao:** **Amend** (nao supersede). O ADR-004 ainda e valido — filesystem continua como source of truth para escrita. Mas precisa de uma clausula de excecao:

> **Amendamento (2026-03-30):** SQLite (.pipeline/madruga.db) foi adicionado como cache de leitura e estado local (pipeline status, active_platform, repo binding). Filesystem permanece como source of truth para escrita. O BD e populado via `reseed` a partir dos YAMLs. Veja ADR-012 para detalhes do SQLite WAL mode.

---

### D6 — Roadmap Drift

**WARNING**: `planning/roadmap.md` nao existe para madruga-ai. Revisao do roadmap nao aplicavel.

---

### D7 — Epic Drift (Impacto Futuro)

Nenhum impacto em epics futuros detectado. Os epics restantes (006-009) ja foram concluidos. As mudancas de repo binding sao aditivas e nao quebram premissas de nenhum epic existente.

---

### D8 — Integration Drift

Nenhum drift detectado. Context map nao precisa de atualizacao — nenhuma integracao nova foi adicionada.

---

## Revisao do Roadmap

**WARNING**: `planning/roadmap.md` nao existe para madruga-ai.

### Status do Epic 010

| Campo | Planejado | Real | Observacao |
|-------|-----------|------|------------|
| Escopo | Pipeline dashboard (status, heatmap, DAG) | Implementou repo binding + active platform + status CLI | Sub-entrega do dashboard |
| Status | Em andamento | Parcialmente completo | Repo binding entregue, dashboard HTML visual pendente |

---

## Impacto em Epics Futuros

Nenhum impacto em epics futuros detectado.

---

## Scorecard

| # | Item | Auto-Avaliacao |
|---|------|----------------|
| 1 | Todo drift item tem estado atual vs esperado | Sim |
| 2 | Diffs LikeC4 sintaticamente validos | N/A (sem diffs LikeC4) |
| 3 | Revisao do roadmap completa | N/A (roadmap nao existe) |
| 4 | Contradicoes ADR flaggadas com recomendacao | Sim (D5.1 — amend) |
| 5 | Impacto em epics futuros avaliado | Sim (zero impacto) |
| 6 | Diffs concretos fornecidos | Sim |
| 7 | Trade-offs explicitos | Sim |

---

handoff:
  from: reconcile
  to: pipeline
  context: "Reconciliacao concluida para epic 010. Drift score: 66.7%. 3 docs com drift (domain-model, solution-overview, ADR-004). 5 drift items — 1 high (storage model desatualizado), 3 medium, 1 low. Acao: aplicar diffs propostos nos 3 docs."
  blockers: []
