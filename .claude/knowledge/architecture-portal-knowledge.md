# Architecture Portal — Knowledge File

Referencia completa para a skill `/architecture-portal`. Contem templates, exemplos e convencoes.

## Metodologia

Framework de 6 artefatos visuais inspirado nas melhores praticas de:
- Uber (DOMA, RFCs), Google (Design Docs, SRE), Amazon (Working Backwards), Stripe (API Design)
- Netflix (Full Cycle Devs, Paved Road), Spotify (DIBB, Backstage), Shopify (DDD, Modular Monolith)
- Shape Up (Basecamp), Team Topologies, C4 Model (Simon Brown)

## Os 6 Artefatos Core

```
VISAO               NEGOCIO              DOMINIO                    TECNICO

0. Vision    →  1. Fluxo de   →  2. Context Map  ─┬──→  4. C4 L2
   Brief +         Negocio      (DDD Estrateg.)   │       Containers
   Glossario       (c/ I/O)                       │       + NFRs
                                      │            │
                                      ▼            └──→  5. Integracoes
                                3. Modelo de
                                 Dominio +
                                 Schema
```

## Estrutura de Output

```
platforms/<ProjectName>/
├── index.md                    ← Copia de 0-vision-brief.md (MkDocs index)
├── 0-vision-brief.md           ← Passo 0: Vision Brief
├── 1-fluxos-negocio.md         ← Passo 1: Fluxos (Mermaid fallback + iframe Arch Viewer)
├── 2-context-map.md            ← Passo 2: DDD Estrategico (Mermaid + iframe Arch Viewer)
├── 3-modelo-dominio-schema.md  ← Passo 3: DDD Tatico + ERD fundido
├── 4-containers-c4.md          ← Passo 4: C4 L2 (Mermaid + iframe Arch Viewer)
├── 5-integracoes.md            ← Passo 5: Integracoes + tabela
├── arquitetura-interativa.md   ← Tab dedicada: Arch Viewer fullscreen + tabela views
├── flows/
│   ├── viewer.html             ← Template HTML5 Canvas FIXO (AI nunca edita)
│   └── <nome>.json             ← 1 JSON por fluxo (AI gera/consome)
├── data/
│   ├── flow-pipeline.json       ← Pipeline M1-M14
│   ├── context-map.json         ← DDD bounded contexts
│   └── containers.json          ← C4 L2 + integrations
├── viewers/
│   ├── arch-viewer.html         ← Shell HTML (AI nunca edita)
│   ├── core.js                  ← Engine compartilhado
│   ├── render-flow.js           ← Renderer pipeline
│   ├── render-context.js        ← Renderer DDD
│   └── render-containers.js     ← Renderer C4
├── stylesheets/
│   └── serena.css              ← CSS brand
├── decisions/
│   ├── index.md
│   └── ADR-NNN-*.md
├── epics/
│   └── index.md
└── research/                   ← Pesquisas de mercado e benchmarks (por projeto)
mkdocs-<project>.yml            ← Config MkDocs Material
```

### Principio: Portal vs Epicos

- **Portal** (`platforms/<ProjectName>/`) = "como o sistema funciona" — visao estavel, artefatos de arquitetura
- **Arch Viewer** (`viewers/` + `data/`) = visualizacao interativa com drill-down entre views (flow, context-map, containers)
- **Epicos** (`epics/`) = "como construir cada parte" — roadmap.md + per-epic specs de implementacao
- Deep-dive por modulo (payloads exatos, regex, state machines) vai nos **epicos**, NAO no portal
- Portal enriquece docs com structs resumidas e tabelas de comunicacao, mas nao detalha implementacao

## Fluxos Interativos (HTML5 Canvas Viewer)

### Principio: 1 template viewer, N JSONs

- `flows/viewer.html` e template fixo: HTML5 canvas custom com pan/zoom/minimap/detail panel/bezier curves/drag nodes + localStorage. NAO usa Drawflow. Baseado no fluxo-agente.html original
- AI NUNCA edita viewer.html — so gera/consome os `.json`
- Cada fluxo e um `.json` com a mesma estrutura que `const modules`/`connections` do JS original
- Servido via Python HTTP server (porta 8052), embedado no MkDocs via iframe
- Mermaid flowchart mantido abaixo como fallback (funciona offline/GitHub/Obsidian)

### JSON Schema (contrato AI)

Chaves: `modules` (nao `nodes`) para compatibilidade com o viewer.

```json
{
  "title": "string — nome do fluxo",
  "description": "string — 1 linha descritiva",
  "modules": {
    "<MODULE_ID>": {
      "id": "string — ex: M1, M2, SAVE",
      "title": "string — nome do modulo",
      "color": "string — #hex",
      "layer": "string — reception, routing, core, etc",
      "short": "string — descricao curta 1 linha",
      "x": "number", "y": "number", "w": "number", "h": "number",
      "purpose": "string — paragrafo descritivo",
      "inputs": ["array de strings — o que recebe"],
      "outputs": ["array de strings — o que produz"],
      "decisions": ["array de strings — pontos de decisao ([] se nenhum)"],
      "connections": ["array de MODULE_IDs destino"],
      "file": "string — path no repo (opcional)",
      "isRouter": "boolean (opcional — true para routers como M3)",
      "isTerminal": "boolean (opcional — true para terminais como SAVE, IGNORE)"
    }
  },
  "connections": [
    {
      "from": "string — MODULE_ID",
      "to": "string — MODULE_ID",
      "label": "string — rotulo (opcional)",
      "color": "string — #hex",
      "arrow": "string — arrow-green, arrow-orange, etc"
    }
  ],
  "m14Connections": ["array de MODULE_IDs que M14 conecta via dashed lines"]
}
```

### Layer → Color mapping

| Layer | Color | Uso |
|---|---|---|
| reception | #2ecc71 | Ingestao (webhooks, normalizar) |
| routing | #ff8844 | Decisao de rota |
| core | #22ddcc | Pipeline central |
| agent (M8) | #8866ff | Execucao agente IA |
| eval (M9) | #ffcc44 | Avaliacao qualidade |
| output (M10,M11) | #4488ff | Saida e entrega |
| handoff | #ff4466 | Transferencia humano |
| trigger | #ff66aa | Mensagens proativas |
| observability | #888899 | Tracing e metricas |
| terminal | #888899 | Estados finais |

### Posicionamento de nodes

- Pipeline linear vertical: x fixo (ex: 560), y incrementa 150px por step
- Branches do router: x diferente por branch, mesmo y
- Cada node tem w (width) e h (height) explicitos
- AI posiciona, viewer renderiza com bezier curves automaticas

### Como embedar no MkDocs

Requer Python HTTP server rodando: `cd platforms/<Project> && python3 -m http.server 8052 --bind 0.0.0.0 &`

```markdown
???+ tip "Pipeline interativo (clique nos modulos)"
    <iframe src="http://localhost:8052/flows/viewer.html?flow=<nome>"
            width="100%" height="600px"
            style="border: 1px solid #333; border-radius: 8px; background: #1a1a2e;">
    </iframe>
```

### Drag + localStorage (viewer.html)

O viewer suporta drag-and-drop nos nodes:
- Click + arrasta → move o node, connections seguem automaticamente
- Click rapido (sem arrastar) → abre detail panel
- Posicoes salvas em localStorage (`flow-layout-{flowName}`)
- Botao "Reset Layout" no toolbar → volta posicoes originais do JSON
- AI NAO precisa saber disso — e feature do template, transparente para o JSON

### Servidores (2 portas)

| Porta | Servico | Comando |
|---|---|---|
| 8050 | MkDocs Material | `mkdocs serve -f mkdocs-<project>.yml -a 0.0.0.0:8050 &` |
| 8052 | Arch Viewer + data JSONs | `cd platforms/<Project> && python3 -m http.server 8052 --bind 0.0.0.0 &` |

Script para iniciar todos: ver `scripts/start-portal.sh` (se existir) ou rodar os 2 comandos manualmente.

## Templates

### Template: 0-vision-brief.md

```markdown
# [Nome da Plataforma] — Vision Brief

> [Tagline de 1 linha]

## Tese
[1 paragrafo. Por que isso precisa existir? Qual problema estrutural resolve?]

## Visao de futuro (12-18 meses)
[Descreva como se ja existisse. Concreto, nao aspiracional.]

## Quem e o cliente
| Dimensao | Detalhe |
|----------|---------|
| **Persona** | [descricao] |
| **Mercado** | [tamanho] |
| **Segmento inicial** | [foco] |
| **Dor principal** | [problema] |

## O que e sucesso
| Metrica | Hoje | 6 meses | 12 meses |
|---------|------|---------|----------|
| [metrica 1] | X | Y | Z |
| [metrica 2] | X | Y | Z |

## Principios inegociaveis
1. **[Principio]** — [justificativa]
2. **[Principio]** — [justificativa]

## O que NAO e
| NAO e... | Porque |
|----------|--------|
| [X] | [razao] |

## Riscos existenciais
| # | Risco | Impacto | Mitigacao |
|---|-------|---------|----------|
| 1 | [risco] | [impacto] | [mitigacao] |

## Landscape
| Player | Foco | Forca | Fraqueza vs nos |
|--------|------|-------|-----------------|
| [concorrente] | [foco] | [forca] | [fraqueza] |

## Linguagem Ubiqua

Termos padronizados usados em toda a documentacao e codigo.

| Termo | Definicao | Dominio |
|-------|-----------|---------|
| [Termo 1] | [Definicao precisa, 1 frase] | [Dominio/area] |
| [Termo 2] | [Definicao precisa, 1 frase] | [Dominio/area] |
```

### Template: 1-fluxos-negocio.md

```markdown
# Fluxos de Negocio

[Intro breve]

| # | Fluxo | Descricao |
|---|-------|-----------|
| 1 | [Fluxo A](#fluxo-a) | [descricao] |
| 2 | [Fluxo B](#fluxo-b) | [descricao] |

---

## Fluxo A

> [Descricao em 1 linha]

### Pipeline

\`\`\`mermaid
flowchart TD
    A[Inicio] --> B{Decisao}
    B -->|Sim| C[Acao 1]
    B -->|Nao| D[Acao 2]
    C --> E[Fim]
    D --> E
\`\`\`

### Descricao dos modulos
| Modulo | Input | Output | Modelo/Servico |
|--------|-------|--------|----------------|
| **[ID]** [Nome] | [o que recebe] | [o que produz] | [tech/servico] |

### Notas
- [nota relevante]

---

## Fluxo B
[mesmo padrao]
```

### Template: 2-context-map.md

```markdown
# Context Map (DDD Estrategico)

[Intro — quantos dominios, como se relacionam]

## Mapa de Dominios

\`\`\`mermaid
graph TB
    subgraph Platform
        D1[Dominio 1]
        D2[Dominio 2]
        D3[Dominio 3]
    end

    D1 -->|Customer-Supplier| D2
    D2 -->|Conformist| D3

    subgraph External
        E1[Sistema Externo 1]
        E2[Sistema Externo 2]
    end

    D1 -.->|ACL| E1
    D3 -.->|ACL| E2
\`\`\`

## Dominios

### [Dominio 1] — [descricao curta]
- **Responsabilidade:** [o que faz]
- **Modulos:** [M1, M2, ...]
- **Linguagem ubiqua:** [termos chave]

## Relacoes entre dominios

| Origem | Destino | Tipo | Descricao |
|--------|---------|------|-----------|
| D1 | D2 | Customer-Supplier | [o que passa] |

## Integracoes externas (ACL)

| Sistema | Protocolo | Direcao | Responsavel |
|---------|-----------|---------|-------------|
| [externo] | [REST/SOAP/gRPC] | [in/out/bidi] | [dominio] |
```

### Template: 3-modelo-dominio-schema.md

```markdown
# Modelo de Dominio + Schema

[Intro — DDD tatico + ERD fundidos. Cada secao = 1 bounded context.]

---

## [Dominio 1] (M1, M2, ...)

### Modelo de Dominio

\`\`\`mermaid
classDiagram
    class Entidade {
        +UUID id
        +String nome
        +Status status
        +criar()
        +atualizar()
    }
    class ValorObjeto {
        +Tipo campo1
        +Tipo campo2
    }
    Entidade *-- ValorObjeto
\`\`\`

### Schema SQL

\`\`\`sql
CREATE TABLE entidades (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome        VARCHAR(255) NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
\`\`\`

### Invariantes
- [regra de negocio 1]
- [regra de negocio 2]

---

## [Dominio 2]
[mesmo padrao]
```

### Template: 4-containers-c4.md

```markdown
# C4 L2 — Containers

[Intro breve]

## Diagrama

\`\`\`mermaid
graph TB
    User([Usuario]) --> WebApp
    Admin([Admin]) --> AdminApp

    subgraph Platform
        WebApp[Web App<br>React :3000]
        API[API<br>FastAPI :8040]
        Worker[Worker<br>ARQ]
        DB[(PostgreSQL)]
        Cache[(Redis)]
    end

    WebApp --> API
    API --> DB
    API --> Cache
    Worker --> DB

    API --> ExtSystem[Sistema Externo]
\`\`\`

## Containers

| Container | Tecnologia | Porta | Responsabilidade |
|-----------|-----------|-------|-----------------|
| [nome] | [tech] | [porta] | [o que faz] |

## Requisitos Nao-Funcionais

| NFR | Target | Mecanismo | Container |
|-----|--------|-----------|-----------|
| [requisito] | [meta mensuravel] | [como e garantido] | [container responsavel] |
```

### Template: 5-integracoes.md

```markdown
# Integracoes

[Intro breve]

## Diagrama

\`\`\`mermaid
graph LR
    subgraph Plataforma
        API[API]
        Worker[Worker]
    end

    API <-->|REST| Ext1[Sistema 1]
    Worker -->|Webhook| Ext2[Sistema 2]
    Ext3[Sistema 3] -->|SFTP| Worker
\`\`\`

## Tabela de Integracoes

| Sistema | Protocolo | Direcao | Frequencia | Dados | Fallback |
|---------|-----------|---------|-----------|-------|----------|
| [sistema] | [REST/SOAP/gRPC] | [in/out/bidi] | [real-time/batch] | [o que trafega] | [retry/DLQ/manual] |
```

### Template: ADR

```markdown
# ADR-NNN: [Titulo curto]
**Status:** Accepted | **Data:** YYYY-MM-DD

## Contexto
[Forcas em jogo, constraints, problema]

## Decisao
We will [decisao em presente].

## Alternativas consideradas
### [Alternativa A]
- Pros: ...
- Cons: ...
### [Alternativa B]
- Pros: ...
- Cons: ...

## Consequencias
- [+] Beneficio
- [-] Trade-off aceito
```

### Template: mkdocs.yml

```yaml
site_name: "[Nome] — Architecture Portal"
site_description: "[Descricao]"
docs_dir: "platforms/[ProjectDir]"

theme:
  name: material
  language: pt-BR
  font:
    text: Poppins
    code: JetBrains Mono
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.indexes
    - navigation.top
    - content.code.copy
    - search.suggest
    - search.highlight
  palette:
    - scheme: slate
      primary: custom
      accent: custom
      toggle:
        icon: material/brightness-4
        name: Modo claro
    - scheme: default
      primary: custom
      accent: custom
      toggle:
        icon: material/brightness-7
        name: Modo escuro

extra_css:
  - stylesheets/serena.css

markdown_extensions:
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.details
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - admonition
  - attr_list
  - md_in_html
  - tables
  - toc:
      permalink: true

nav:
  - "0. Vision Brief": index.md
  - "1. Fluxos de Negocio": 1-fluxos-negocio.md
  - "2. Context Map (DDD)": 2-context-map.md
  - "3. Modelo Dominio + Schema": 3-modelo-dominio-schema.md
  - "4. C4 L2 — Containers": 4-containers-c4.md
  - "5. Integracoes": 5-integracoes.md
  - "Arquitetura Interativa": arquitetura-interativa.md
  - Decisoes (ADRs):
    - Indice: decisions/index.md
  - Epics: epics/index.md
```

### Template: arquitetura-interativa.md

```markdown
# Arquitetura Interativa

> Explore a arquitetura com drill-down. Clique nos elementos para navegar entre views.

???+ tip "Pipeline (flow)"
    <iframe src="http://localhost:8052/viewers/arch-viewer.html?data=flow-pipeline"
            width="100%" height="800px"
            style="border: 1px solid #333; border-radius: 8px; background: #1a1a2e;">
    </iframe>

---

## Views disponiveis

| View | Dados | O que mostra |
|------|-------|-------------|
| [Pipeline](http://localhost:8052/viewers/arch-viewer.html?data=flow-pipeline){target="_blank"} | `data/flow-pipeline.json` | Fluxo M1-M14 |
| [Context Map](http://localhost:8052/viewers/arch-viewer.html?data=context-map){target="_blank"} | `data/context-map.json` | DDD bounded contexts |
| [Containers](http://localhost:8052/viewers/arch-viewer.html?data=containers){target="_blank"} | `data/containers.json` | C4 L2 + integracoes |

!!! note "Servidor necessario"
    Requer HTTP server rodando em `localhost:8052`.
    Para iniciar: `cd platforms/<Project> && python3 -m http.server 8052 --bind 0.0.0.0`
```

### Padrao: iframe arch-viewer inline (Context Map e C4 L2)

Nos arquivos `2-context-map.md` e `4-containers-c4.md`, adicionar ACIMA do diagrama Mermaid:

```markdown
??? tip "Versao interativa (Arch Viewer)"
    Clique nos elementos para navegar. Requer HTTP server rodando em `localhost:8052`.

    <iframe src="http://localhost:8052/viewers/arch-viewer.html?data=<type>"
            width="100%" height="500px"
            style="border: 1px solid #333; border-radius: 8px; background: #1a1a2e;">
    </iframe>
```

O Mermaid estatico fica abaixo como fallback (funciona no GitHub/Obsidian sem servidor).

### Nota: CSS brand

O arquivo `stylesheets/serena.css` customiza cores, fontes e tabelas do MkDocs Material. Usar como base e ajustar cores para o brand do projeto. Classes importantes:
- `--md-primary-fg-color` — cor principal (header, links, tabs ativos)
- `--md-accent-fg-color` — cor de destaque (hover, badges)
- `.arch-viewer-link` — botao coral com gradient para links do Arch Viewer
- Tabelas: header colorido, linhas alternadas, texto branco no header

## Exemplo Completo

Ver `platforms/Fulano_v2/` como implementacao de referencia:
- 6 artefatos core + tab interativa + CSS brand + 10 ADRs + Arch Viewer JSONs
- MkDocs Material com tabs navegaveis + iframes Arch Viewer inline
- Arch Viewer com 3 view types: flow-pipeline, context-map, containers
- Abordagem hibrida: Mermaid estatico (fallback offline) + Arch Viewer interativo (quando servidor roda)

## Perguntas de Discovery (Fase 1)

Perguntas essenciais para extrair o contexto do negocio:

1. **Tese**: Qual o problema que essa plataforma resolve? Por que precisa existir?
2. **Cliente**: Quem e o usuario principal? Qual o tamanho do mercado?
3. **Sucesso**: Quais metricas definem sucesso? (3-5 metricas com targets)
4. **Principios**: Quais regras sao inegociaveis? (3-5 principios)
5. **Anti-escopo**: O que essa plataforma NAO e? (evitar scope creep)
6. **Riscos**: O que pode matar o projeto? (3-6 riscos com mitigacao)
7. **Concorrentes**: Quem mais tenta resolver isso? Qual nosso diferencial?
8. **Processos**: Quais sao os fluxos de negocio principais? (2-5 fluxos)
9. **Dominios**: Quais areas logicas o sistema tem? Como se conectam?
10. **Tech stack**: Quais tecnologias ja estao decididas? Quais integracoes externas?
11. **Decisoes ja tomadas**: Tem ADRs ou decisoes tecnicas ja feitas?
