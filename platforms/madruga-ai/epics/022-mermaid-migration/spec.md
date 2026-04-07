# Feature Specification: Mermaid Migration — LikeC4 to Mermaid Inline

**Feature Branch**: `epic/madruga-ai/022-mermaid-migration`  
**Created**: 2026-04-05  
**Status**: Draft  
**Input**: Migrar todos os diagramas de arquitetura de LikeC4 para Mermaid inline nos documentos Markdown existentes, eliminando todo o tooling LikeC4 do repositorio.

## User Scenarios & Testing

### User Story 1 - Portal sem dependencia LikeC4 (Priority: P1)

Como mantenedor do repositorio, quero que o portal funcione sem nenhuma dependencia do LikeC4 (CLI, VitePlugin, componentes React) para que o build seja mais simples e rapido, sem necessidade de instalar ferramentas extras.

**Why this priority**: LikeC4 e a raiz da complexidade — elimina-lo desbloqueando todas as outras simplificacoes. Sem isso, nenhuma outra story pode ser completada.

**Independent Test**: Rodar `cd portal && npm run build` com sucesso apos remover todas as referencias a LikeC4. O build deve completar sem erros e sem o CLI `likec4` instalado.

**Acceptance Scenarios**:

1. **Given** o portal com todas as referencias a LikeC4 removidas, **When** `npm run build` e executado, **Then** o build completa sem erros.
2. **Given** o `package.json` do portal, **When** inspecionado, **Then** nao contem dependencia `likec4`.
3. **Given** o diretorio `portal/src/`, **When** pesquisado por `LikeC4`, **Then** zero resultados encontrados (sem componentes, types, plugins).

---

### User Story 2 - Diagramas Mermaid inline nos documentos existentes (Priority: P1)

Como consumidor da documentacao arquitetural (dev, tech lead, stakeholder), quero visualizar os diagramas de arquitetura diretamente nos documentos Markdown (blueprint.md, domain-model.md, process.md) para que nao precise navegar para paginas dedicadas e tenha o contexto visual junto com o texto explicativo.

**Why this priority**: E o core da migracao — sem diagramas Mermaid nos docs, a remocao do LikeC4 resultaria em perda de informacao arquitetural. Prioridade igual a P1 porque ambas stories sao co-dependentes.

**Independent Test**: Abrir cada documento no portal (Starlight) e verificar que os diagramas Mermaid renderizam corretamente via `astro-mermaid`.

**Acceptance Scenarios**:

1. **Given** `engineering/blueprint.md` de uma plataforma, **When** renderizado no portal, **Then** exibe diagrama de Deploy Topology (`graph LR`) e diagrama de Containers (`graph LR` com subgraphs).
2. **Given** `engineering/domain-model.md` de uma plataforma, **When** renderizado no portal, **Then** exibe diagrama de Context Map (`flowchart LR`) e diagramas de Bounded Contexts (`classDiagram`) em blocos `<details>`.
3. **Given** `business/process.md` de uma plataforma (quando aplicavel), **When** renderizado no portal, **Then** exibe overview flowchart e deep-dives com `sequenceDiagram` por fase.
4. **Given** ambas plataformas (madruga-ai e prosauai), **When** inspecionadas, **Then** todos os diagramas que existiam em LikeC4 tem equivalente Mermaid inline nos respectivos `.md`.

---

### User Story 3 - Sidebar e navegacao simplificadas (Priority: P2)

Como usuario do portal, quero uma sidebar sem links para paginas de diagrama dedicadas (landscape, containers, context-map, bc/[context], business-flow) para que a navegacao seja mais limpa e intuitiva — os diagramas ja estao dentro dos docs relevantes.

**Why this priority**: Melhora a experiencia do usuario do portal, mas depende das stories P1 estarem completas.

**Independent Test**: Navegar pelo portal e verificar que a sidebar nao contem links para paginas de diagrama removidas, e que nao existem paginas 404.

**Acceptance Scenarios**:

1. **Given** o portal rodando, **When** navego pela sidebar de qualquer plataforma, **Then** nao vejo links para "System Landscape", "Containers", "Context Map", "Bounded Contexts", ou "Business Flow" como paginas separadas.
2. **Given** as URLs antigas de paginas de diagrama (ex: `/prosauai/landscape`), **When** acessadas, **Then** retornam 404 (paginas removidas).
3. **Given** a sidebar de Engineering, **When** inspecionada, **Then** mostra: ADRs, Blueprint, Domain Model, Integrations (sem paginas de diagrama dedicadas).

---

### User Story 4 - Template Copier e manifestos atualizados (Priority: P2)

Como criador de novas plataformas, quero que o template Copier nao gere mais o diretorio `model/` nem blocos `views:`/`serve:`/`build:` no `platform.yaml` para que novas plataformas ja nascem no padrao Mermaid inline.

**Why this priority**: Garante que a migracao nao cria debt para plataformas futuras. Dependencia das stories P1.

**Independent Test**: Rodar `copier copy` para criar uma nova plataforma e verificar que nao gera `model/` e que `platform.yaml` nao tem blocos LikeC4.

**Acceptance Scenarios**:

1. **Given** o template Copier atualizado, **When** uma nova plataforma e criada, **Then** nao existe diretorio `model/` e `platform.yaml` nao contem blocos `views:`, `serve:`, `build:`.
2. **Given** `platform.yaml` de ambas plataformas existentes (madruga-ai, prosauai), **When** inspecionados, **Then** nao contem blocos `views:`, `serve:`, `build:`.

---

### User Story 5 - ADRs e documentacao de decisao atualizados (Priority: P3)

Como membro do time, quero que os ADRs reflitam a decisao de migrar para Mermaid (ADR-020 criado, ADR-001 superseded, ADR-003 atualizado) para que o historico de decisoes esteja correto e rastreavel.

**Why this priority**: Documentacao de decisao e importante mas nao bloqueia funcionalidade. Pode ser feita por ultimo.

**Independent Test**: Ler os ADRs e verificar consistencia: ADR-001 com status "Superseded by ADR-020", ADR-020 existente com justificativa, ADR-003 sem mencoes a LikeC4VitePlugin.

**Acceptance Scenarios**:

1. **Given** ADR-001, **When** lido, **Then** tem status "Superseded" com referencia ao ADR-020.
2. **Given** ADR-020, **When** lido, **Then** documenta a decisao de Mermaid inline, com alternativas consideradas e justificativa.
3. **Given** ADR-003, **When** lido, **Then** nao contem mencoes a LikeC4VitePlugin.

---

### User Story 6 - Skills e pipeline knowledge atualizados (Priority: P3)

Como executor do pipeline (LLM ou dev), quero que os skills de geracao de diagramas (containers, domain-model, context-map, blueprint, business-process) referenciem Mermaid inline como output em vez de arquivos `.likec4` para que o pipeline gere artefatos no formato correto.

**Why this priority**: Necessario para que o pipeline continue funcional apos a migracao, mas nao bloqueia o portal nem os diagramas existentes.

**Independent Test**: Verificar que `pipeline-dag-knowledge.md` lista outputs corretos (`.md` com Mermaid inline) e que skills nao referenciam `.likec4`.

**Acceptance Scenarios**:

1. **Given** `pipeline-dag-knowledge.md`, **When** inspecionado, **Then** nodes `domain-model` e `containers` listam outputs como secoes Mermaid inline em `.md` (nao `.likec4`).
2. **Given** skills impactados, **When** inspecionados, **Then** nao referenciam `.likec4` como output.

---

### Edge Cases

- O que acontece se um documento `.md` nao tiver conteudo suficiente para absorver os diagramas? Cria-se a secao necessaria no documento, com header e diagrama Mermaid.
- Como lidar com diagramas LikeC4 que nao tem equivalente direto em Mermaid (ex: drill-down interativo)? Aceito como trade-off — Mermaid e estatico. Informacao e preservada via secoes `<details>` colapsaveis.
- O que acontece se `astro-mermaid` falhar ao renderizar um diagrama complexo? O portal build falha, indicando o erro. Correcao e feita no Mermaid inline antes de commit.
- E se houver diagramas LikeC4 que nao tem nenhum conteudo informacional util? Sao descartados (ex: arquivos de spec LikeC4 vazios ou boilerplate puro).

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE remover todos os arquivos `.likec4` do repositorio (ambas plataformas + template).
- **FR-002**: O sistema DEVE remover todos os componentes, types e plugins LikeC4 do portal (`LikeC4Diagram.tsx`, `likec4.d.ts`, `LikeC4VitePlugin`).
- **FR-003**: O sistema DEVE remover as 5 paginas `.astro` dedicadas a diagramas (landscape, containers, context-map, bc/[context], business-flow).
- **FR-004**: O sistema DEVE converter o conteudo informacional dos diagramas LikeC4 para Mermaid inline nos documentos existentes, seguindo a Pyramid of Detail:
  - L1: Deploy Topology (`graph LR`) em `blueprint.md`
  - L2: Containers (`graph LR` com subgraphs) em `blueprint.md`
  - L3: Context Map (`flowchart LR`) em `domain-model.md`
  - L4: Bounded Contexts (`classDiagram`) em `domain-model.md` (dentro de `<details>`)
  - L5: Business Flow (`flowchart TD` + `sequenceDiagram`) em `process.md`
- **FR-005**: O sistema DEVE manter nomenclatura consistente entre niveis de diagrama (mesmo identificador de componente em L1, L2, L3, L4).
- **FR-006**: O sistema DEVE incluir cross-references entre secoes de diagramas que apontam para o proximo nivel de detalhe.
- **FR-007**: O sistema DEVE simplificar a sidebar do portal removendo links para paginas de diagrama dedicadas.
- **FR-008**: O sistema DEVE remover os blocos `views:`, `serve:`, `build:` do `platform.yaml` de ambas plataformas.
- **FR-009**: O sistema DEVE atualizar o template Copier para nao gerar diretorio `model/` nem blocos LikeC4 no `platform.yaml`.
- **FR-010**: O sistema DEVE remover `vision-build.py` do repositorio.
- **FR-011**: O sistema DEVE remover o job `likec4 build` do CI.
- **FR-012**: O sistema DEVE criar ADR-020 documentando a decisao de migrar para Mermaid inline.
- **FR-013**: O sistema DEVE marcar ADR-001 como Superseded por ADR-020.
- **FR-014**: O sistema DEVE atualizar ADR-003 removendo mencoes a `LikeC4VitePlugin`.
- **FR-015**: O sistema DEVE atualizar `pipeline-dag-knowledge.md` com os novos outputs dos nodes `domain-model` e `containers`.
- **FR-016**: O sistema DEVE atualizar o `CLAUDE.md` raiz e os CLAUDE.md das plataformas removendo referencias a LikeC4.
- **FR-017**: O sistema DEVE remover `.claude/rules/likec4.md`.
- **FR-018**: O sistema DEVE garantir que `portal build`, `make test`, e `make lint` passam sem erros apos a migracao.
- **FR-019**: O sistema DEVE preservar toda informacao arquitetural existente — nenhum conteudo informacional pode ser perdido na migracao.

### Key Entities

- **Diagrama Mermaid**: Bloco de codigo Mermaid (` ```mermaid `) embutido em um documento `.md`. Tipos: graph, flowchart, classDiagram, sequenceDiagram.
- **Documento Hospedeiro**: Arquivo `.md` existente que recebe diagramas inline (blueprint.md, domain-model.md, process.md).
- **Plataforma**: Diretorio `platforms/<name>/` com seus artefatos. Ambas (madruga-ai e prosauai) sao impactadas.
- **Template Copier**: Template em `.specify/templates/platform/template/` usado para criar novas plataformas.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero arquivos `.likec4` no repositorio apos a migracao (de 22 arquivos para 0).
- **SC-002**: Zero referencias a "LikeC4" no codigo-fonte do portal (de ~15 referencias para 0).
- **SC-003**: Reducao de pelo menos 5 paginas `.astro` dedicadas a diagramas (de 5 para 0).
- **SC-004**: Portal build completa com sucesso sem o CLI `likec4` instalado.
- **SC-005**: Todos os diagramas de ambas plataformas visualizaveis nos respectivos documentos `.md` via portal.
- **SC-006**: `make test`, `make lint` e `portal build` passam sem erros.
- **SC-007**: Novas plataformas criadas via Copier nao contem artefatos LikeC4.
- **SC-008**: Reducao de dependencias externas do portal (remocao do pacote `likec4`).
- **SC-009**: 100% do conteudo informacional dos diagramas LikeC4 preservado nos documentos Mermaid equivalentes.

## Assumptions

- O plugin `astro-mermaid` ja esta instalado e funcional no portal — nao e necessario instalar ou configurar nada novo para renderizar Mermaid.
- Diagramas Mermaid estaticos sao suficientes — a interatividade do LikeC4 (pan, zoom, drill-down) nao agrega valor proporcional a sua complexidade.
- A convencao de nomenclatura consistente (Pyramid of Detail) e suficiente para manter coerencia entre niveis — nao e necessario um modelo unificado.
- Os diagramas LikeC4 de `businessFlow` (315 LOC) podem ser simplificados para overview + deep-dives por fase sem perda de informacao essencial.
- Todas as plataformas existentes (madruga-ai e prosauai) tem os documentos hospedeiros necessarios (`blueprint.md`, `domain-model.md`, `process.md`).
- O CI tem um job `likec4 build` que precisa ser removido (se nao existir, este passo e no-op).
- Skills impactados serao atualizados via `/madruga:skills-mgmt` conforme politica do repositorio.

---
handoff:
  from: speckit.specify
  to: speckit.clarify
  context: "Spec completa para migracao LikeC4 → Mermaid inline. 6 user stories, 19 requisitos funcionais, escopo bem definido pelo pitch. Pronto para clarificacao ou diretamente para planning."
  blockers: []
  confidence: Alta
  kill_criteria: "Se astro-mermaid nao suportar os tipos de diagrama necessarios (classDiagram, sequenceDiagram, flowchart) ou se o portal nao conseguir renderizar Mermaid inline."
