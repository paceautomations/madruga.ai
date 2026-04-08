---
id: "022"
title: "Mermaid Migration — LikeC4 to Mermaid Inline"
status: in_progress
phase: now
risk: low
tags: [portal, diagrams, simplification, dx]
updated: 2026-04-05
---
# 022 — Mermaid Migration: LikeC4 to Mermaid Inline

## Problem

Os diagramas de arquitetura gerados com LikeC4 nao estao ficando visualmente bons. Alem disso, o tooling envolvido e desproporcional ao valor entregue:

- **8 arquivos `.likec4`** por plataforma (actors, externals, platform, ddd-contexts, infrastructure, relationships, views, spec)
- **Tooling custom**: `LikeC4Diagram.tsx` (104 LOC), `platformLoaders` (import map manual), `buildViewPaths()`, `vision-build.py`, `likec4.d.ts`, `LikeC4VitePlugin`
- **5 paginas `.astro` dedicadas** apenas para renderizar diagramas (landscape, containers, context-map, bc/[context], business-flow)
- **Dependencia de CLI**: `likec4` CLI precisa estar instalado, `likec4 serve` para dev, `likec4 build` no CI
- **DX ruim para LLMs**: LikeC4 DSL tem pouco treinamento nos modelos — gera erros frequentes
- **Manutencao por plataforma**: cada nova plataforma exige adicionar `platformLoaders` em `LikeC4Diagram.tsx`

Enquanto isso, o portal ja tem `astro-mermaid` instalado e funcional. Mermaid renderiza nativamente no GitHub, Starlight, e qualquer viewer Markdown. Os diagramas que realmente agregam valor (domain model, business flow, deploy topology) podem ser expressos como Mermaid inline nos proprios `.md`.

## Solution

### Estrategia: Mermaid inline nos documentos existentes

Eliminar todas as paginas de diagrama dedicadas. Os diagramas passam a viver **dentro** dos documentos que ja existem, renderizados nativamente pelo `astro-mermaid`.

### De-Para Completo

| Antes (LikeC4) | Depois (Mermaid) | Onde vive |
|-----------------|------------------|-----------|
| `/landscape/` (pagina .astro + LikeC4Diagram) | `graph LR` no `engineering/blueprint.md` secao "Deploy Topology" | Inline |
| `/containers/` (pagina .astro + LikeC4Diagram) | `graph LR` com subgraphs no `engineering/blueprint.md` secao "Containers" | Inline |
| `/context-map/` (pagina .astro + LikeC4Diagram) | `flowchart LR` no `engineering/domain-model.md` secao "Context Map" | Inline |
| `/bc/[context]/` (pagina .astro + LikeC4Diagram) | `classDiagram` em `<details>` por BC no `engineering/domain-model.md` | Inline |
| `/business-flow/` (pagina .astro + LikeC4Diagram) | Overview `flowchart TD` + `<details>` com `sequenceDiagram` por fase no `business/process.md` | Inline |
| 8x `.likec4` files por plataforma | Zero arquivos extras — tudo dentro dos `.md` | N/A |
| `model/likec4.config.json` | Removido | N/A |
| `model/output/likec4.json` | Removido | N/A |

### Sidebar Simplificada

```
Engineering/
  ADRs/
  Blueprint          ← contem deploy topology + containers (Mermaid inline)
  Domain Model       ← contem context map + BC deep-dives (Mermaid inline)
  Context Map        ← REMOVIDO (absorvido pelo Domain Model)
  System Landscape   ← REMOVIDO (absorvido pelo Blueprint)
  Containers         ← REMOVIDO (absorvido pelo Blueprint)
  Integrations
```

### Pyramid of Detail (convenção de camadas)

Sem modelo unificado LikeC4, a coerencia entre niveis e garantida por convencao:

| Nivel | Tipo Mermaid | Onde | O que mostra |
|-------|--------------|------|--------------|
| L1 | `graph LR` | blueprint.md "Deploy Topology" | Sistema + externos + conectividade |
| L2 | `graph LR` + subgraphs | blueprint.md "Containers" | Containers internos + integracoes |
| L3 | `flowchart LR` | domain-model.md "Context Map" | Bounded contexts + relacoes DDD |
| L4 | `classDiagram` | domain-model.md `<details>` por BC | Aggregates, entities, invariantes |
| L5 | `flowchart TD` + `sequenceDiagram` | process.md | Fluxo de negocio end-to-end |

**Regras de coerencia:**
1. **Nomenclatura consistente** — mesmo nome em todos os niveis (ex: `prosauai-api` no L1 = `prosauai-api` no L2 = `ProsaUAIApi` no L4)
2. **Cross-reference via links** — cada secao aponta para o proximo nivel de detalhe
3. **Top-down generation** — skills geram de cima para baixo: `blueprint` (L1+L2), `domain-model` (L3+L4), `business-process` (L5)

### Tipos de Diagrama (simplificacao C4)

Em vez de manter a hierarquia formal C4 (Context/Container/Component/Code), usamos 3 tipos pragmaticos:

| Tipo | Mermaid | Valor unico | Substitui |
|------|---------|-------------|-----------|
| Deploy Topology | `graph LR` | O que roda onde, como se conecta | C4 Context + C4 Container |
| Domain Model | `classDiagram` + `flowchart` | Entidades, aggregates, relacoes DDD | C4 Component + DDD diagrams |
| Business Flow | `sequenceDiagram` + `flowchart TD` | Como dados fluem pelo sistema | C4 Dynamic View |

## Rabbit Holes

- **Nao** tentar replicar a interatividade do LikeC4 (pan, zoom, drill-down, navigation buttons) — Mermaid e estatico e isso e aceitavel
- **Nao** criar um componente React custom para Mermaid — `astro-mermaid` ja faz o trabalho
- **Nao** adicionar `mmdc` (mermaid-cli) ao CI — o portal build via `astro-mermaid` ja valida syntax
- **Nao** tentar converter 1:1 os 315 linhas de `businessFlow` LikeC4 — simplificar para overview + deep-dives por fase
- **Nao** criar arquivos `.mmd` separados — Mermaid inline nos `.md` e o padrao

## No-gos

- Nao mudar o framework do portal (Astro + Starlight permanece)
- Nao alterar a estrutura de diretorios `platforms/<name>/`
- Nao perder informacao arquitetural — todo conteudo dos `.likec4` deve estar representado nos `.md`

## Dependencies

- Nenhuma dependencia de epics anteriores (todos shipped)
- Impacta: portal, template Copier, skills (containers, domain-model, context-map, blueprint, business-process), CI, platform.yaml schema

## Acceptance Criteria

- [ ] Zero arquivos `.likec4` no repositorio
- [ ] Zero referencias a LikeC4 no portal (sem VitePlugin, sem LikeC4Diagram.tsx, sem platformLoaders)
- [ ] `vision-build.py` removido
- [ ] Paginas dedicadas de diagrama removidas (landscape, containers, context-map, bc/[context], business-flow)
- [ ] Sidebar do portal simplificada (sem links para paginas de diagrama)
- [ ] Diagramas Mermaid inline nos `.md` de ambas plataformas (madruga-ai + prosauai)
- [ ] `platform.yaml` sem bloco `views:` (ambas plataformas)
- [ ] Template Copier atualizado (sem `.likec4`, sem `model/`)
- [ ] CI sem job `likec4 build`
- [ ] ADR-001 marcado como Superseded, novo ADR-020 criado
- [ ] ADR-003 atualizado (sem mencao a LikeC4VitePlugin)
- [ ] Skills atualizados: outputs de `.likec4` para Mermaid inline nos `.md`
- [ ] Pipeline DAG knowledge atualizado (outputs dos nodes domain-model, containers)
- [ ] `portal build` passa sem erros
- [ ] `make test` passa sem erros
- [ ] `make lint` passa sem erros

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|----------|------------------------|
| 1 | Diagramas | Mermaid inline nos `.md` existentes (nao paginas dedicadas) | ADR-001 (superseded) → ADR-020 |
| 2 | Sidebar | Remover links de diagrama dedicados — docs absorvem diagramas | ADR-003 (atualizado) |
| 3 | C4 formal | Simplificar para 3 tipos pragmaticos: deploy topology, domain model, business flow | Pragmatismo > elegancia (CLAUDE.md) |
| 4 | Mermaid C4 syntax | Usar `flowchart`/`graph` com subgraphs (nao `C4Context`/`C4Container`) — mais flexivel | Estabilidade da syntax padrao |
| 5 | vision-build.py | Remover completamente — tabelas AUTO passam a ser manuais (poucas, drift detectado pelo reconcile) | ADR-004 filesystem-first |
| 6 | CI | Remover job `likec4 build` sem substituicao — `astro-mermaid` valida no portal build | Menos tooling = menos manutencao |
| 7 | businessFlow | Overview flowchart + deep-dives sequence por fase (nao conversao 1:1) | Legibilidade > completude |
| 8 | ADRs | ADR-020 supersede ADR-001. ADR-003 atualizado in-place | Nygard format (CLAUDE.md) |

## Resolved Gray Areas

**1. Modelo unificado vs diagramas independentes**
LikeC4 tinha um modelo unificado com drill-down. Com Mermaid, cada diagrama e independente. A coerencia e garantida por convencao (naming contract + cross-references + auto-review nos skills), nao por tooling. Aceito como trade-off — o modelo unificado nao estava agregando valor suficiente.

**2. Diagramas complexos (businessFlow 315 LOC)**
Quebrar em overview (flowchart ~20 linhas) + deep-dives por fase (sequence ~30 linhas cada) dentro de `<details>`. Preserva toda informacao sem diagrama ilegivel.

**3. `model/` directory**
Sera removido de ambas plataformas. Todo conteudo migra para `engineering/` e `business/`. Template Copier atualizado para nao gerar `model/`.

**4. platformLoaders e LikeC4Diagram.tsx**
Removidos. Nenhum componente React substituto necessario — `astro-mermaid` renderiza server-side.

## Applicable Constraints

- **Python: stdlib + pyyaml** (CLAUDE.md) — nenhum script novo precisa de deps extras
- **Scripts < 300 LOC** (CLAUDE.md) — remocao de `vision-build.py` reduz LOC total
- **Pragmatismo > elegancia** (CLAUDE.md) — motivacao principal da migracao
- **Edit `.claude/commands/` via `/madruga:skills-mgmt`** — skills impactados devem ser editados via skill management

## Suggested Approach

### Fase 1: Portal cleanup (remover LikeC4)
1. Remover `LikeC4VitePlugin` do `astro.config.mjs`
2. Remover `LikeC4Diagram.tsx`, `likec4.d.ts`
3. Remover paginas `.astro` dedicadas (landscape, containers, context-map, bc/[context], business-flow)
4. Simplificar `buildSidebar()` e `buildViewPaths()` em `platforms.mjs`
5. Remover `resolveNodeHref` references a `.likec4`
6. Remover dep `likec4` do `package.json`

### Fase 2: Converter diagramas (ProsaUAI + Madruga-AI)
7. Converter `views.likec4` → Mermaid inline no `business/process.md` (businessFlow)
8. Converter `platform.likec4` + `infrastructure.likec4` → Mermaid inline no `engineering/blueprint.md`
9. Converter `ddd-contexts.likec4` → Mermaid inline no `engineering/domain-model.md`
10. Converter `actors.likec4` + `externals.likec4` + `relationships.likec4` → absorvidos nos diagramas acima
11. Remover `model/` directory de ambas plataformas
12. Remover `vision-build.py`

### Fase 3: Manifesto + Template
13. Remover bloco `views:`, `serve:`, `build:` do `platform.yaml` (ambas plataformas)
14. Atualizar template Copier (remover `model/`, atualizar `platform.yaml.jinja`)
15. Atualizar `pipeline-dag-knowledge.md` (outputs dos nodes domain-model, containers)

### Fase 4: ADRs + Docs
16. Criar ADR-020 (Mermaid inline supersede LikeC4)
17. Atualizar ADR-001 status para Superseded
18. Atualizar ADR-003 (remover LikeC4VitePlugin)
19. Atualizar `engineering/blueprint.md` (stack table: LikeC4 → Mermaid)
20. Atualizar `engineering/domain-model.md` (remover classes LikeC4Model, LikeC4Element, etc)

### Fase 5: CI + Cleanup
21. Remover job `likec4 build` do CI
22. Remover `.claude/rules/likec4.md`
23. Atualizar CLAUDE.md (remover mencoes a LikeC4)
24. Atualizar `platforms/madruga-ai/CLAUDE.md` e `platforms/prosauai/CLAUDE.md`
25. `make test` + `make lint` + portal build

## Inventario de Arquivos Impactados

### Remover
| Arquivo | Motivo |
|---------|--------|
| `portal/src/components/viewers/LikeC4Diagram.tsx` | Componente React LikeC4 |
| `portal/src/likec4.d.ts` | Type declarations LikeC4 |
| `portal/src/pages/[platform]/landscape.astro` | Pagina dedicada |
| `portal/src/pages/[platform]/containers.astro` | Pagina dedicada |
| `portal/src/pages/[platform]/context-map.astro` | Pagina dedicada |
| `portal/src/pages/[platform]/bc/[context].astro` | Pagina dedicada |
| `portal/src/pages/[platform]/business-flow.astro` | Pagina dedicada |
| `.specify/scripts/vision-build.py` | Build pipeline LikeC4 → AUTO markers |
| `.claude/rules/likec4.md` | Regras LikeC4 |
| `platforms/*/model/*.likec4` | Todos os arquivos de modelo (16 arquivos) |
| `platforms/*/model/likec4.config.json` | Config LikeC4 por plataforma |
| `platforms/*/model/output/` | JSON exportado |

### Alterar
| Arquivo | Mudanca |
|---------|---------|
| `portal/astro.config.mjs` | Remover LikeC4VitePlugin import e config |
| `portal/src/lib/platforms.mjs` | Remover buildViewPaths, simplificar buildSidebar |
| `portal/src/lib/constants.ts` | Remover resolveNodeHref refs a .likec4 |
| `portal/src/components/dashboard/PipelineDAG.tsx` | Remover refs LikeC4 se houver |
| `portal/package.json` | Remover dep `likec4` |
| `platforms/madruga-ai/platform.yaml` | Remover blocos views, serve, build |
| `platforms/prosauai/platform.yaml` | Remover blocos views, serve, build |
| `platforms/madruga-ai/engineering/blueprint.md` | Adicionar Mermaid deploy topology + containers |
| `platforms/madruga-ai/engineering/domain-model.md` | Adicionar Mermaid context map + remover classes LikeC4 |
| `platforms/madruga-ai/business/process.md` | Adicionar Mermaid business flow (se aplicavel) |
| `platforms/prosauai/engineering/blueprint.md` | Adicionar Mermaid deploy topology + containers |
| `platforms/prosauai/engineering/domain-model.md` | Adicionar Mermaid context map |
| `platforms/prosauai/business/process.md` | Converter businessFlow para Mermaid |
| `.claude/knowledge/pipeline-dag-knowledge.md` | Outputs de domain-model e containers |
| `.specify/templates/platform/template/` | Remover model/, atualizar platform.yaml.jinja |
| `platforms/madruga-ai/CLAUDE.md` | Remover LikeC4 do stack |
| `platforms/prosauai/CLAUDE.md` | Remover LikeC4 do stack (se mencionado) |
| `CLAUDE.md` | Remover refs LikeC4, prerequisito likec4 CLI |

### Criar
| Arquivo | Conteudo |
|---------|----------|
| `platforms/madruga-ai/decisions/ADR-020-mermaid-inline-diagrams.md` | Mermaid como padrao, supersede ADR-001 |
