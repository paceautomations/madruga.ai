---
title: "ADR-020: Mermaid Inline Diagrams"
status: accepted
date: 2026-04-05
supersedes: ADR-001
decision: Substituir LikeC4 por diagramas Mermaid inline nos documentos Markdown existentes
  (blueprint.md, domain-model.md, process.md), eliminando todo o tooling LikeC4 do repositorio.
alternatives: Manter LikeC4, Structurizr DSL, Arquivos Mermaid separados (.mmd), PlantUML
rationale: Mermaid inline elimina tooling desproporcional (8 .likec4 files, VitePlugin,
  vision-build.py, 5 paginas .astro, CLI), usa astro-mermaid ja instalado, e nativamente
  suportado por LLMs, GitHub e qualquer viewer Markdown.
---
# ADR-020: Mermaid Inline Diagrams — Substituicao do LikeC4

## Status

Accepted — 2026-04-05. Supersedes [ADR-001](ADR-001-likec4-source-of-truth.md).

## Contexto

ADR-001 (2026-03-27) estabeleceu LikeC4 como source of truth para modelos arquiteturais. Na pratica, o tooling envolvido mostrou-se desproporcional ao valor entregue:

- **8 arquivos `.likec4` por plataforma** (actors, externals, platform, ddd-contexts, infrastructure, relationships, views, spec) — alta superficie de manutencao
- **Tooling custom extenso**: `LikeC4Diagram.tsx` (104 LOC), `platformLoaders` (import map manual), `buildViewPaths()`, `vision-build.py` (JSON → AUTO markers), `likec4.d.ts`, `LikeC4VitePlugin`
- **5 paginas `.astro` dedicadas** apenas para renderizar diagramas (landscape, containers, context-map, bc/[context], business-flow)
- **Dependencia de CLI**: `likec4` CLI precisa estar instalado, `likec4 serve` para dev, `likec4 build` no CI
- **DX ruim para LLMs**: LikeC4 DSL tem pouco treinamento nos modelos — gera erros frequentes e requer correcoes manuais
- **Overhead por plataforma**: cada nova plataforma exige adicionar `platformLoaders` em `LikeC4Diagram.tsx`
- **Qualidade visual insatisfatoria**: os diagramas LikeC4 nao estavam ficando visualmente bons

Enquanto isso, o portal ja tem `astro-mermaid` v2.0.1 instalado e funcional. Mermaid renderiza nativamente no GitHub, Starlight, e qualquer viewer Markdown. Os diagramas que realmente agregam valor (domain model, deploy topology, business flow) podem ser expressos como Mermaid inline nos proprios `.md`.

## Decisao

Substituir LikeC4 por diagramas Mermaid inline nos documentos Markdown existentes (`blueprint.md`, `domain-model.md`, `process.md`), eliminando todo o tooling LikeC4 do repositorio.

### Pyramid of Detail (convencao de camadas)

A coerencia entre niveis de diagrama e garantida por convencao (naming contract + cross-references), nao por modelo unificado:

| Nivel | Tipo Mermaid | Documento | O que mostra |
|-------|--------------|-----------|--------------|
| L1 | `graph LR` | blueprint.md "Deploy Topology" | Sistema + externos + conectividade |
| L2 | `graph LR` + subgraphs | blueprint.md "Containers" | Containers internos + integracoes |
| L3 | `flowchart LR` | domain-model.md "Context Map" | Bounded contexts + relacoes DDD |
| L4 | `classDiagram` | domain-model.md `<details>` por BC | Aggregates, entities, invariantes |
| L5 | `flowchart TD` + `sequenceDiagram` | process.md | Fluxo de negocio end-to-end |

### Tipos de diagrama Mermaid

Usa-se sintaxe estavel e amplamente suportada (`graph`, `flowchart`, `classDiagram`, `sequenceDiagram`). A sintaxe experimental `C4Context`/`C4Container` do Mermaid foi descartada por instabilidade e menor suporte em renderers.

## Alternativas Consideradas

### 1. Manter LikeC4 (status quo)

- **Pros**: modelo unificado com drill-down interativo (pan, zoom, navegacao entre niveis), export JSON estruturado para pipelines, tipagem de elementos C4
- **Cons**: tooling desproporcional ao valor, DX ruim para LLMs, qualidade visual insatisfatoria, dependencia de CLI e VitePlugin, overhead por plataforma nova, comunidade pequena
- **Decisao**: Rejeitado — a complexidade nao se justifica pelo valor entregue

### 2. Structurizr DSL

- **Pros**: maduro, amplamente adotado, suporte nativo C4, workspace-as-code
- **Cons**: requer JVM para renderizar, sem componente React para embed direto no Starlight, licenca comercial para features avancadas, DSL menos flexivel para DDD patterns customizados, troca uma dependencia de CLI por outra
- **Decisao**: Rejeitado — introduziria nova dependencia pesada (JVM) sem resolver o problema de complexidade

### 3. Arquivos Mermaid separados (.mmd)

- **Pros**: separacao de concerns (diagrama vs texto), possibilidade de tooling dedicado (`mmdc`)
- **Cons**: duplica a fragmentacao de arquivos (mesmo problema do LikeC4 com 8 arquivos por plataforma), requer import/include nos `.md`, perde a vantagem de diagrama-junto-com-contexto
- **Decisao**: Rejeitado — inline nos `.md` e mais simples e mantem contexto junto com diagrama

### 4. PlantUML

- **Pros**: extremamente maduro, vasta documentacao, suporte C4 via stdlib, comunidade grande
- **Cons**: requer servidor Java para renderizar, sintaxe verbosa, sem componente React, output apenas imagem (sem interatividade), setup mais complexo que Mermaid
- **Decisao**: Rejeitado — requer dependencia Java e nao tem renderizacao nativa em Markdown viewers

## Consequencias

### Positivas

- [+] Elimina tooling desproporcional: 8 `.likec4` files, VitePlugin, vision-build.py, 5 paginas `.astro`, platformLoaders, likec4.d.ts
- [+] Zero dependencias extras — `astro-mermaid` ja esta instalado e funcional
- [+] Mermaid e nativamente suportado por GitHub, Starlight, e qualquer viewer Markdown
- [+] LLMs conhecem Mermaid muito melhor que LikeC4 — menos erros de geracao
- [+] Diagrama inline junto com texto explicativo — contexto visual unificado
- [+] Sidebar do portal simplificada — menos paginas, navegacao mais limpa
- [+] Novas plataformas nao precisam de setup LikeC4 (sem `model/`, sem `likec4.config.json`)
- [+] CI simplificado — remove job `likec4 build`
- [+] Build do portal mais rapido — sem VitePlugin de LikeC4

### Negativas

- [-] Perde interatividade (pan, zoom, drill-down) — Mermaid e estatico
- [-] Perde modelo unificado com tipagem de elementos — coerencia depende de convencao (naming contract)
- [-] Perde export JSON estruturado — pipelines que dependiam de `likec4.json` precisam de alternativa
- [-] Diagramas complexos podem ficar ilegiveisveis em Mermaid — mitigado com decomposicao em `<details>` e limite de ~50 linhas por bloco

### Mitigacoes

- Interatividade: diagramas estaticos sao suficientes para documentacao arquitetural. `<details>` blocks permitem drill-down manual.
- Coerencia: naming contract documentado (Pyramid of Detail), cross-references entre niveis, auto-review nos skills de geracao.
- JSON export: nao ha pipeline que dependa de `likec4.json` apos remocao de `vision-build.py`. Tabelas AUTO passam a ser manuais (poucas, drift detectado pelo reconcile).

## Decisoes Relacionadas

- **ADR-001** (Superseded): LikeC4 como source of truth — substituido por esta decisao
- **ADR-003** (Updated): Astro + Starlight portal — atualizado para remover referencias a LikeC4VitePlugin
- **ADR-004** (Unchanged): File-based storage — reforçado: Mermaid inline e filesystem-first
