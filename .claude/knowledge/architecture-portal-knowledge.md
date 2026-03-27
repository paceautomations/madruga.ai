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

0. Vision    →  1. Solution   →  2. Context Map  ─┬──→  4. C4 L2
   Brief           Overview      (DDD Estrateg.)   │       Containers
                   (Features)                      │       + NFRs
                                      │            │
                                      ▼            └──→  5. Integracoes
                                3. Modelo de
                                 Dominio +
                                 Schema
```

## Stack Atual

- **Portal**: Astro + Starlight (SSG com sidebar, markdown nativo, code highlighting)
- **Diagramas interativos**: LikeC4 (modelo .likec4 → React component via Vite plugin)
- **Diagramas estaticos**: Mermaid (fallback nos markdowns, funciona no GitHub/Obsidian)
- **Build script**: `.specify/scripts/vision-build.py` exporta LikeC4 JSON → popula tabelas markdown via `<!-- AUTO:name -->` markers

## Estrutura de Output

```
platforms/<ProjectName>/
├── platform.yaml              ← Manifesto declarativo (nome, lifecycle, views, comandos)
├── business/
│   ├── vision.md              ← Playing to Win: tese, mercado, moat, pricing
│   └── solution-overview.md   ← Feature map Now/Next/Later + personas
├── engineering/
│   ├── domain-model.md        ← DDD tatico + class diagrams + SQL schemas
│   ├── containers.md          ← C4 L2 + tabela (auto-gerada do modelo)
│   ├── context-map.md         ← DDD Context Map (auto-gerado)
│   └── integrations.md        ← Integracoes com protocolos e fallbacks (auto-gerado)
├── decisions/
│   └── ADR-NNN-*.md           ← Nygard: Context, Decision, Alternatives, Consequences
├── epics/
│   └── NNN-slug/pitch.md      ← Shape Up: problema, appetite, solucao, rabbit holes
├── research/                  ← Pesquisas de mercado e benchmarks
└── model/                     ← LikeC4 architecture model
    ├── spec.likec4            ← Element kinds + relationship kinds + tags
    ├── actors.likec4          ← Personas
    ├── platform.likec4        ← Containers internos
    ├── externals.likec4       ← Sistemas externos
    ├── infrastructure.likec4  ← Storage e infra
    ├── ddd-contexts.likec4    ← Bounded contexts com modulos
    ├── relationships.likec4   ← Relacoes (C4 + DDD patterns)
    └── views.likec4           ← Views estruturais + dynamic views
```

### Principio: Portal vs Epicos

- **Portal** (`platforms/<ProjectName>/`) = "como o sistema funciona" — visao estavel, artefatos de arquitetura
- **Diagramas interativos** = LikeC4 React components renderizados no portal Astro (pan, zoom, drill-down)
- **Epicos** (`epics/`) = "como construir cada parte" — Shape Up pitches com spec de implementacao
- Deep-dive por modulo (payloads exatos, regex, state machines) vai nos **epicos**, NAO no portal
- Portal enriquece docs com structs resumidas e tabelas de comunicacao, mas nao detalha implementacao

## LikeC4 Model

### Como funciona

Os arquivos `.likec4` definem elementos (actors, containers, bounded contexts, externals), relacionamentos e views. O portal Astro integra via Vite plugin:

```javascript
// astro.config.mjs
import { LikeC4VitePlugin } from 'likec4/vite-plugin';
// ...
vite: {
  plugins: [LikeC4VitePlugin({ workspace: '../platforms/<project>/model' })]
}
```

### React Component

Cada pagina de diagrama usa o `LikeC4Diagram.tsx`:

```tsx
import { ReactLikeC4, LikeC4ModelProvider } from 'likec4:react';

export default function LikeC4Diagram({ viewId }: { viewId: string }) {
  return (
    <LikeC4ModelProvider>
      <ReactLikeC4 viewId={viewId} pannable zoomable fitView
        enableElementDetails enableRelationshipDetails enableNotations
        onNavigateTo={(nextViewId) => { /* navigate between views */ }} />
    </LikeC4ModelProvider>
  );
}
```

### Paginas Astro

Cada view e uma pagina `.astro`:

```astro
---
import StarlightPage from '@astrojs/starlight/components/StarlightPage.astro';
import LikeC4Diagram from '../../components/viewers/LikeC4Diagram';
---
<StarlightPage frontmatter={{ title: 'Titulo', tableOfContents: false }}>
  <div class="diagram-fullscreen">
    <LikeC4Diagram viewId="<viewId>" client:only="react" />
  </div>
</StarlightPage>
```

### Portal Dev Server

```bash
cd portal
npm install          # roda setup.sh via postinstall (symlink platforms/ → src/content/docs/)
npm run dev          # http://localhost:4321
```

### LikeC4 Standalone (sem portal)

```bash
cd platforms/<project>/model
likec4 serve         # http://localhost:5173 (hot reload)
```

## Templates

### Template: business/vision.md

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

### Template: engineering/context-map.md

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

<!-- AUTO:domains -->
<!-- /AUTO:domains -->

## Relacoes entre dominios

<!-- AUTO:relations -->
<!-- /AUTO:relations -->

## Integracoes externas (ACL)

| Sistema | Protocolo | Direcao | Responsavel |
|---------|-----------|---------|-------------|
| [externo] | [REST/SOAP/gRPC] | [in/out/bidi] | [dominio] |
```

### Template: engineering/domain-model.md

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

### Template: engineering/containers.md

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

<!-- AUTO:containers -->
<!-- /AUTO:containers -->

## Requisitos Nao-Funcionais

| NFR | Target | Mecanismo | Container |
|-----|--------|-----------|-----------|
| [requisito] | [meta mensuravel] | [como e garantido] | [container responsavel] |
```

### Template: engineering/integrations.md

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

<!-- AUTO:integrations -->
<!-- /AUTO:integrations -->
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

### Template: platform.yaml

```yaml
name: <project-name>
title: "<Project> — <Tagline>"
description: "<1 linha>"
lifecycle: design          # design | development | production
version: "0.1.0"
model: model/
views:
  structural:
    - id: index
      label: "System Landscape"
    - id: containers
      label: "C4 L2 — Containers"
    - id: contextMap
      label: "DDD Context Map"
  flows:
    - id: businessFlow
      label: "Business Process"
serve:
  command: "likec4 serve"
  port: 5173
build:
  command: "likec4 build -o dist/"
  export_json: "likec4 export json --pretty --skip-layout -o model/output/likec4.json"
```

## Exemplo de Referencia

Ver `platforms/fulano/` como implementacao de referencia:
- 6 artefatos core (business/, engineering/) + 19 ADRs + 15 epicos Shape Up
- LikeC4 model com 8 .likec4 files, 8 views estruturais + 1 dynamic view
- Portal Astro + Starlight com diagramas interativos (pan, zoom, drill-down)
- `vision-build.py` popula tabelas AUTO nos markdowns a partir do modelo

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
