---
description: Gera portal de arquitetura completo — 6 artefatos visuais + ADRs + MkDocs + Arch Viewer
argument-hint: "[nome-do-projeto] [descricao breve do negocio]"
arguments:
  - name: project
    description: "Nome do projeto (kebab-case). Ex: fulano, meu-saas, energy-platform"
    required: false
  - name: context
    description: "Descricao breve do negocio (1-2 frases)"
    required: false
---

# Architecture Portal — Gerador de Documentacao Arquitetural

Gera a documentacao completa de arquitetura de qualquer plataforma/sistema seguindo o framework de 6 artefatos visuais definido em `platforms/fulano/research/documentation_system.md`.

## Uso

- `/architecture-portal` — Modo interativo: coleta contexto via perguntas
- `/architecture-portal meu-projeto "plataforma SaaS de gestao de pedidos"` — Modo direto
- `/architecture-portal fulano` — Atualiza portal existente

## Pre-requisitos

- `mkdocs-material` instalado (`pip install --break-system-packages mkdocs-material`)
- Knowledge: `.claude/knowledge/architecture-portal-knowledge.md`
- Metodologia: `platforms/fulano/research/documentation_system.md`

## Instrucoes

### 1. Coletar Contexto

**Se o argumento `context` foi fornecido**, extrair o maximo possivel e pular para deep dive (passo 2).

**Se nao**, fazer as perguntas de discovery — apresentar TODAS de uma vez para o usuario responder em bloco (NAO uma por uma):

```
Para criar o portal de arquitetura, preciso entender o negocio. Responda o que souber:

1. **Tese**: Qual problema essa plataforma resolve? Por que precisa existir?
2. **Cliente**: Quem e o usuario principal? Mercado/tamanho?
3. **Sucesso**: 3-5 metricas com targets (ex: usuarios ativos, receita, churn)
4. **Principios**: 3-5 regras inegociaveis (ex: "multi-tenant desde dia 1")
5. **Anti-escopo**: O que NAO e? (ex: "nao e CRM, nao e marketplace")
6. **Riscos**: O que pode matar o projeto? (3-6 riscos)
7. **Concorrentes**: Quem mais tenta resolver? Qual seu diferencial?
8. **Processos**: Quais os 2-5 fluxos de negocio principais?
9. **Dominios**: Quais areas logicas o sistema tem?
10. **Tech stack**: Tecnologias decididas? Integracoes externas?
11. **Decisoes**: ADRs ou decisoes tecnicas ja feitas?
```

### 2. Deep Dive (se necessario)

Se o usuario forneceu contexto parcial, usar subagent para pesquisar o dominio:

- Buscar na web sobre o mercado, concorrentes, regulacoes
- Ler documentacao existente no repo (specs/, docs/, README)
- Analisar codigo existente se houver (services/, src/)

Consolidar tudo num entendimento completo antes de gerar.

### 3. Criar Estrutura de Diretorios

```bash
mkdir -p platforms/<ProjectName>/{decisions,epics,stylesheets,flows,data,viewers}
mkdir -p {research}
```

### 4. Gerar os 6 Artefatos Core (em paralelo)

Lancar 3 subagents em paralelo:

**Agent 1 — Vision + Fluxos:**
- `platforms/<ProjectName>/0-vision-brief.md` — seguir template do knowledge file. DEVE incluir secao `## Linguagem Ubiqua` com tabela de termos do dominio
- `platforms/<ProjectName>/index.md` — COPIA LITERAL de 0-vision-brief.md (MkDocs exige index.md como home)
- `platforms/<ProjectName>/1-fluxos-negocio.md` — todos os fluxos num arquivo com Mermaid (fallback). Tabela de modulos DEVE ter colunas `| Modulo | Input | Output | Modelo/Servico |` (extrair I/O dos JSONs). Incluir `???+ tip` com iframe: `http://localhost:8052/flows/viewer.html?flow=<nome>`
- `platforms/<ProjectName>/flows/viewer.html` — copiar template custom fixo de `platforms/Fulano_v2/flows/viewer.html`. HTML5 canvas custom (NOT Drawflow): pan/zoom, minimap, detail panel, bezier curves, drag nodes + localStorage. AI NUNCA edita
- `platforms/<ProjectName>/flows/<nome>.json` — 1 JSON por fluxo. Schema: `{title, description, modules: {ID: {id,title,color,layer,short,x,y,w,h,purpose,inputs[],outputs[],decisions[],connections[],file}}, connections: [{from,to,label,color,arrow}], m14Connections: []}`. AI gera o JSON, viewer.html renderiza
- Iniciar servidor: `cd platforms/<ProjectName> && python3 -m http.server 8052 --bind 0.0.0.0 &`

**Agent 2 — Dominios + Arquitetura:**
- `platforms/<ProjectName>/2-context-map.md` — Context Map com Mermaid graph. Incluir `??? tip` admonition com iframe arch-viewer: `http://localhost:8052/viewers/arch-viewer.html?data=context-map`
- `platforms/<ProjectName>/3-modelo-dominio-schema.md` — DDD tatico + SQL fundidos. Incluir `??? tip` com iframe arch-viewer: `http://localhost:8052/viewers/arch-viewer.html?data=context-map`
- `platforms/<ProjectName>/4-containers-c4.md` — C4 L2 com Mermaid. DEVE incluir secao `## Requisitos Nao-Funcionais` com tabela `| NFR | Target | Mecanismo | Container |`. Incluir `??? tip` com iframe arch-viewer: `http://localhost:8052/viewers/arch-viewer.html?data=containers`
- `platforms/<ProjectName>/5-integracoes.md` — diagrama + tabela. Incluir `??? tip` com iframe arch-viewer: `http://localhost:8052/viewers/arch-viewer.html?data=containers`

**Agent 3 — ADRs + Infra + Portal + Implementation:**
- `platforms/<ProjectName>/decisions/index.md` — indice das ADRs
- `platforms/<ProjectName>/decisions/ADR-NNN-*.md` — 1 por decisao (template do knowledge file)
- `platforms/<ProjectName>/epics/index.md` — indice dos epicos
- `platforms/<ProjectName>/arquitetura-interativa.md` — tab dedicada com botao standalone + iframe arch-viewer fullscreen + tabela de views
- `platforms/<ProjectName>/stylesheets/serena.css` — CSS brand (cores, fontes, tabelas, botao likec4-link)
- `platforms/<ProjectName>/data/flow-pipeline.json` — arch-viewer JSON para fluxo pipeline
- `platforms/<ProjectName>/data/context-map.json` — arch-viewer JSON para context map DDD
- `platforms/<ProjectName>/data/containers.json` — arch-viewer JSON para C4 L2 containers
- `platforms/<ProjectName>/viewers/` — copiar TODOS os arquivos de `platforms/Fulano_v2/viewers/` (arch-viewer.html, core.js, render-*.js). Esses sao templates FIXOS — AI NUNCA regenera ou edita
- `services/vision/mkdocs-<project>.yml` — config MkDocs Material com extra_css, font Poppins, tab "Arquitetura Interativa" no nav
- `platforms/<ProjectName>/epics/roadmap.md` — roadmap com fases de implementacao, stack decisions, timeline
- Engineering standards (anti-patterns, testing architecture, golden dataset format) sao uma secao dentro de `epics/roadmap.md` — NAO arquivo separado

**IMPORTANTE para os subagents:**
- Usar Write tool para criar arquivos (NAO worktree)
- Paths absolutos
- Verificar que cada arquivo foi criado
- Seguir templates do knowledge file `.claude/knowledge/architecture-portal-knowledge.md`
- Mermaid para TODOS os diagramas
- Portugues BR para prosa, ingles para codigo/termos tecnicos

### Layout Guidelines para JSONs

**Flow (type: flow)**: Pipeline vertical top-down. Router (M3) branches laterais. Posicoes explicitas obrigatorias.

**Context Map (type: context-map)**: Grid layout:
- Row 1 (y=60): Persons
- Row 2 (y=220): Bounded Contexts 2x2 (Channel, Conversation lado a lado; Safety, Operations, Observability abaixo)
- Row 3 (y=820+): External systems em grid

**Containers (type: containers)**: C4 L2 top-down:
- Row 1 (y=40): Persons
- Row 2 (y=180): Platform group (api + worker + admin)
- Row 3 (y=440): Infrastructure group (Redis + DB + proxy + observability)
- Row 4 (y=720): External systems

**Regras de ouro**:
- Groups DEVEM envolver filhos: group.x = min(children.x) - 30, group.w = max(children.x+w) - group.x + 30
- Node gap minimo: 30px horizontal, 20px vertical
- Sem sobreposicao de nodes
- Cache-busting: `?_=timestamp` no fetch de JSON

### 5. Validar Artefatos

Apos geracao, verificar:

| Check | Como |
|-------|------|
| Todos os 6 arquivos core existem | `ls platforms/<ProjectName>/[0-5]-*.md` |
| Tab interativa existe | `ls platforms/<ProjectName>/arquitetura-interativa.md` |
| CSS brand existe | `ls platforms/<ProjectName>/stylesheets/serena.css` |
| ADRs existem | `ls platforms/<ProjectName>/decisions/ADR-*.md` |
| Arch-viewer data JSONs existem | `ls platforms/<ProjectName>/data/*.json` |
| Arch-viewer viewers copiados | `ls platforms/<ProjectName>/viewers/arch-viewer.html` |
| MkDocs config existe | `ls services/vision/mkdocs-<project>.yml` |
| Mermaid syntax valida | Verificar que code blocks usam ` ```mermaid ` |
| Iframes inline em Context Map e C4 L2 | Verificar `??? tip` admonitions com iframe arch-viewer |
| Botao standalone na tab interativa | Verificar `likec4-link` class no arquivo |
| Flow viewer existe | `ls platforms/<ProjectName>/flows/viewer.html` |
| Flow JSONs existem | `ls platforms/<ProjectName>/flows/*.json` |
| Glossario no Vision Brief | Verificar secao `## Linguagem Ubiqua` em 0-vision-brief.md e index.md |
| Tabela I/O nos fluxos | Verificar colunas `Input \| Output` na tabela de modulos em 1-fluxos-negocio.md |
| NFRs no C4 L2 | Verificar secao `## Requisitos Nao-Funcionais` em 4-containers-c4.md |
| 2 servidores configurados | Portas 8050 (MkDocs), 8052 (HTTP — arch-viewer + flow viewer) |

### 6. Iniciar Servidores

```bash
# MkDocs Material (porta 8050)
pkill -f "mkdocs serve" 2>/dev/null
cd services/vision && mkdocs serve -f mkdocs-<project>.yml -a 0.0.0.0:8050 > /tmp/mkdocs.log 2>&1 &
cd -

# HTTP server — arch-viewer + flow viewer (porta 8052)
pkill -f "http.server 8052" 2>/dev/null
cd platforms/<ProjectName> && python3 -m http.server 8052 --bind 0.0.0.0 > /tmp/arch-server.log 2>&1 &
cd -

# Alternativa rapida: bash services/vision/start.sh
```

Aguardar ambos subirem e testar com curl.

Validar com curl:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8050/ && echo "MkDocs OK"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8052/viewers/arch-viewer.html && echo "Arch Viewer OK"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8052/flows/viewer.html && echo "Flow server OK"
```

### 7. Validar com Playwright

Abrir cada view e verificar:
1. `?data=flow-pipeline` — screenshot, verificar: nodes sem overlap, connections visiveis, labels legiveis
2. `?data=context-map` — screenshot, verificar: groups envolvem filhos, DDD patterns nas connections
3. `?data=containers` — screenshot, verificar: tech badges/ports visiveis, protocol labels nas connections
4. Home view — 3 cards centralizados, click navega
5. Detail panel — click em node abre panel com dados corretos
6. Drill-down — click em node com link navega para outra view

Se overlap detectado: ajustar posicoes no JSON e re-testar.

### 8. Apresentar Resultado

```
## Portal de Arquitetura Criado

**Projeto:** <nome>
**Arquivos:** <N> artefatos core + <M> ADRs

### Servidores
- **MkDocs:** http://localhost:8050 (docs navegaveis + Mermaid)
- **Arch Viewer:** http://localhost:8052/viewers/arch-viewer.html (drill-down interativo)

### Estrutura
platforms/<ProjectName>/
├── 0-vision-brief.md      ← Por que existe?
├── 1-fluxos-negocio.md    ← Como funciona?
├── 2-context-map.md       ← Quais dominios?
├── 3-modelo-dominio-schema.md ← Objetos + banco?
├── 4-containers-c4.md     ← Pecas tecnicas?
├── 5-integracoes.md       ← Mundo externo?
├── decisions/ADR-*.md     ← Por que assim?
├── data/                  ← JSONs do arch-viewer
│   ├── flow-pipeline.json
│   ├── context-map.json
│   └── containers.json
└── viewers/               ← Templates fixos (NUNCA editar)
    ├── arch-viewer.html
    ├── core.js
    └── render-*.js

### Proximo passo
Revise os artefatos e ajuste conforme necessario.
Para atualizar, rode `/architecture-portal <nome>` novamente.
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| mkdocs-material nao instalado | `pip install --break-system-packages mkdocs-material` |
| Porta 8050/8052 ocupada | `pkill -f "mkdocs serve"` / `pkill -f "http.server 8052"` |
| Arch-viewer nao renderiza | Verificar que `data/*.json` existem e tem schema correto (type, nodes, connections) |
| Nodes sobrepostos no arch-viewer | Ajustar posicoes (x, y) no JSON seguindo Layout Guidelines |
| MkDocs 404 na raiz | Garantir que `index.md` existe no docs_dir |
| Subagent falha ao criar arquivo | Verificar path absoluto e que diretorio pai existe |
| Projeto ja existe | Perguntar: sobrescrever, atualizar ou cancelar |
| Servidores nao sobem | `bash services/vision/start.sh` |
| Viewers faltando | Copiar de `platforms/Fulano_v2/viewers/` — NUNCA regenerar |
