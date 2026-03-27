# Vision — Architecture Documentation System

Sistema de documentacao de arquitetura para plataformas digitais. Documenta o **que** um sistema faz, **por que** as decisoes foram tomadas, e **como** as pecas se conectam — tudo versionado no git, consumivel por humanos e LLMs.

Plataforma atual: **Fulano** — plataforma multi-tenant de agentes conversacionais WhatsApp para PMEs brasileiras.

## Quick Start

```bash
# Portal interativo (Astro + LikeC4 diagrams)
cd services/vision/portal
npm install                    # roda setup.sh automaticamente (postinstall)
npm run dev                    # http://localhost:4321

# Build script — popula tabelas AUTO nos markdowns a partir do modelo LikeC4
python3 .specify/scripts/vision-build.py fulano

# LikeC4 dev server — editar modelo com hot reload (sem portal)
cd services/vision/platforms/fulano/model
likec4 serve                   # http://localhost:5173
```

## Framework

Cada plataforma e documentada em 3 camadas, do estrategico ao operacional:

```
                    ┌─────────────────────────────────────────────────────┐
                    │                    BUSINESS                         │
                    │                                                     │
                    │   Vision Brief ──→ Business Flow ──→ Solution       │
                    │   (por que?)        (como funciona?)   Overview     │
                    │                                        (o que?)     │
                    └───────────────────────┬─────────────────────────────┘
                                            │
                                            ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                           ENGINEERING                                    │
  │                                                                          │
  │   Landscape ──→ Containers ──→ Context Map ──→ Domain Model              │
  │   (C4 L1)       (C4 L2)       (DDD)           (entities + SQL)          │
  │                                    │                                     │
  │                                    └──→ Integrations (endpoints,         │
  │                                          payloads, fallbacks)            │
  │                                                                          │
  │   ADRs ← registra decisoes tecnicas a cada ponto                        │
  └───────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      ▼
              ┌───────────────────────────────────────────────┐
              │                  PLANNING                      │
              │                                                │
              │   Roadmap (Now/Next/Later)                     │
              │       └──→ Epics (Shape Up pitches)            │
              │                └──→ spec → plan → tasks        │
              └────────────────────────────────────────────────┘
```

### Business — por que e para quem

| Artefato | Pergunta |
|----------|----------|
| **Vision Brief** | Por que existe? Para quem? Moat competitivo? (Playing to Win) |
| **Business Flow** | Como funciona ponta-a-ponta? (pipeline animado, decision points, 14 modulos) |
| **Solution Overview** | O que construir e em que ordem? (feature map Now/Next/Later + personas) |

### Engineering — como funciona tecnicamente

| Artefato | Pergunta |
|----------|----------|
| **System Landscape** | Quais atores e sistemas interagem? (C4 L1) |
| **Containers** | Quais processos deployaveis, storage e protocolos? (C4 L2, auto-gerado) |
| **Context Map** | Quais dominios, fronteiras e relacoes DDD? (ACL, Conformist, Pub-Sub, auto-gerado) |
| **Domain Model** | Quais entidades, invariantes, schemas SQL e Pydantic structs? |
| **Integrations** | Como conecta com sistemas externos? (endpoints, payloads, fallbacks, auto-gerado) |
| **ADRs** | Por que essa decisao e nao outra? (Nygard: Context, Decision, Alternatives, Consequences) |

### Planning — o que construir e quando

| Artefato | Pergunta |
|----------|----------|
| **Roadmap** | Qual a prioridade? (Now/Next/Later, auto-gerado do frontmatter dos epicos) |
| **Epics** | Como entregar cada feature? (Shape Up: problema, appetite, solucao, rabbit holes, criterios) |

Complementar: **Research** — pesquisas de mercado e benchmarks tecnicos.

## Estrutura

```
services/vision/
├── platforms/
│   └── fulano/                          # Plataforma Fulano
│       ├── platform.yaml                # Manifesto (nome, lifecycle, views, comandos)
│       ├── business/
│       │   ├── vision.md                # Playing to Win: tese, mercado, moat, pricing
│       │   └── solution-overview.md     # Feature map Now/Next/Later + personas
│       ├── engineering/
│       │   ├── domain-model.md          # Class diagrams + SQL schemas + Pydantic structs
│       │   ├── containers.md            # Tabela de containers (auto-gerada do modelo)
│       │   ├── context-map.md           # Dominios + relacoes DDD (auto-gerado)
│       │   └── integrations.md          # 19 integracoes com protocolos e fallbacks (auto-gerado)
│       ├── decisions/                   # ADR-001 a ADR-019
│       ├── epics/                       # 001 a 015 (Shape Up pitches)
│       │   └── NNN-slug/pitch.md
│       ├── research/                    # Deep research (mercado, benchmarks)
│       └── model/                       # LikeC4 architecture model
│           ├── spec.likec4              # Element kinds + relationship kinds + tags
│           ├── actors.likec4            # Personas (agent, admin)
│           ├── platform.likec4          # Containers internos (api, worker, admin)
│           ├── externals.likec4         # Sistemas externos (Evolution API, Claude, etc.)
│           ├── infrastructure.likec4    # Storage e infra (Redis, Supabase, Bifrost, etc.)
│           ├── ddd-contexts.likec4      # 5 bounded contexts com 14 modulos
│           ├── relationships.likec4     # 50 relacoes (C4 + DDD patterns + pipeline flow)
│           └── views.likec4             # 8 views estruturais + 1 dynamic (business flow)
├── portal/                              # Astro + Starlight + LikeC4 React
│   ├── astro.config.mjs                 # Sidebar, plugins, LikeC4 Vite integration
│   ├── setup.sh                         # Cria symlink platforms/ → content/docs/
│   ├── src/pages/fulano/               # Paginas do portal (diagramas, roadmap, decisions)
│   └── src/components/viewers/         # LikeC4Diagram.tsx (React wrapper)
└── README.md                            # Este arquivo

scripts/
└── vision-build.py                      # Exporta LikeC4 JSON → popula tabelas markdown
```

## Pre-requisitos

- **Node.js** 20+
- **Python** 3.11+
- **likec4** CLI: `npm i -g likec4`

## Portal — Paginas

O portal Astro renderiza diagramas LikeC4 interativos (pan, zoom, drill-down) + docs markdown:

| Camada | Pagina | Conteudo |
|--------|--------|----------|
| Business | `/fulano/business/vision/` | Vision Brief (Playing to Win) |
| Business | `/fulano/business-flow/` | Pipeline completo animado (14 modulos, 8 fases) |
| Business | `/fulano/business/solution-overview/` | Feature map + personas |
| Engineering | `/fulano/landscape/` | System Landscape (C4 L1) |
| Engineering | `/fulano/containers/` | Containers interativo (C4 L2) |
| Engineering | `/fulano/context-map/` | DDD Context Map interativo |
| Engineering | `/fulano/bc-channel/` | Zoom: Bounded Context Channel |
| Engineering | `/fulano/bc-conversation/` | Zoom: Bounded Context Conversation (Core) |
| Engineering | `/fulano/bc-safety/` | Zoom: Bounded Context Safety |
| Engineering | `/fulano/bc-operations/` | Zoom: Bounded Context Operations |
| Planning | `/fulano/roadmap/` | Roadmap auto-gerado (Now/Next/Later) |
| Planning | `/fulano/epics/*/pitch/` | 15 epicos Shape Up |
| ADRs | `/fulano/decisions/` | 19 ADRs com decisao, alternativas e status |

## vision-build.py

Script Python que exporta o modelo LikeC4 para JSON e popula tabelas markdown automaticamente via marcadores `<!-- AUTO:nome -->`:

| Marcador | Arquivo | Conteudo gerado |
|----------|---------|-----------------|
| `containers` | `engineering/containers.md` | Tabela de containers (tech, porta, responsabilidade) |
| `domains` | `engineering/context-map.md` | Tabela de bounded contexts (modulos, pattern DDD) |
| `relations` | `engineering/context-map.md` | Relacoes DDD (upstream/downstream, tipo, descricao) |
| `integrations` | `engineering/integrations.md` | Integracoes (protocolo, direcao, frequencia, fallback) |

## platform.yaml

Manifesto declarativo de cada plataforma. Define nome, lifecycle, views disponiveis e comandos:

```yaml
name: fulano
title: "Fulano — Agentes WhatsApp"
lifecycle: design          # design | development | production
version: "0.5.0"
model: model/
views:
  structural: [index, containers, contextMap, channelDetail, ...]
  flows: [businessFlow]
serve:
  command: "likec4 serve"
  port: 5173
build:
  command: "likec4 build -o dist/"
  export_json: "likec4 export json --pretty --skip-layout -o model/output/likec4.json"
  markdown: "python3 .specify/scripts/vision-build.py fulano"
```
