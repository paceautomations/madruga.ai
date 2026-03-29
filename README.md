# madruga.ai

Sistema de documentacao arquitetural e pipeline spec-to-code para plataformas digitais. Documenta o **que** um sistema faz, **por que** as decisoes foram tomadas, e **como** as pecas se conectam — tudo versionado no git, consumivel por humanos e LLMs.

Suporta **N plataformas** a partir de um template Copier compartilhado. Cada plataforma recebe a mesma estrutura de documentacao, integracao com portal e pipeline LikeC4.

## Quick Start

```bash
# Pre-requisitos: Node.js 20+, Python 3.11+, likec4, copier
npm i -g likec4
pip install copier pyyaml

# Portal (visualizacao)
cd portal && npm install && npm run dev
# Abra http://localhost:4321

# Onboarding interativo
/getting-started

# Ou direto: criar plataforma + ver status
/platform-new meu-saas
/pipeline meu-saas
```

## Pipeline de Documentacao (DAG)

Cada plataforma e documentada incrementalmente por **13 skills atomicas** orquestradas por um DAG.

```
BUSINESS       platform-new → vision → solution-overview → business-process
                   │                                           │
RESEARCH           ├── codebase-map (opcional)                 │
                   │                                           ▼
                   │                                     tech-research
                   │                                           │
ENGINEERING        │                                           ▼
                   │                                          adr
                   │                                           │
                   │                                           ▼
                   │                                       blueprint
                   │                                        │    │
                   │                                        ▼    ▼
                   └─────────────────────────→ domain-model → containers
                                                   │              │
                                                   └─→ context-map
                                                          │
PLANNING                                    epic-breakdown ←──┘
                                                   │
                                                roadmap
```

### Gates

| Gate | Comportamento | Skills |
|------|--------------|--------|
| `human` | Sempre pausa para aprovacao | platform-new, vision, solution-overview, business-process, blueprint, domain-model, containers, context-map, roadmap |
| `1-way-door` | Sempre pausa — decisoes irreversiveis | tech-research, adr, epic-breakdown |
| `auto` | Procede automaticamente | codebase-map |
| `auto-escalate` | Auto se OK, escala se encontrar blockers | verify |

### Ciclo Per-Epic (pos-roadmap)

**Obrigatorio: cada epic roda em branch `epic/<platform>/<NNN-slug>`.** `epic-context` cria a branch. Merge via PR apos reconcile.

```
epic-context (cria branch) → specify → clarify → plan → tasks → analyze → implement → verify → qa (opcional) → reconcile → PR/merge
```

### Estimativas de Tempo

| Fase | Skills | Estimativa |
|------|--------|-----------|
| Negocio | platform-new, vision, solution-overview, business-process | ~2h |
| Pesquisa | tech-research, codebase-map (opcional) | ~1h |
| Engenharia | adr, blueprint, domain-model, containers, context-map | ~3h |
| Planejamento | epic-breakdown, roadmap | ~1h |
| **Total pipeline** | | **~7h** |
| Per-Epic cycle | epic-context → ... → reconcile | ~2-4h |

## Contrato das Skills

Toda skill do pipeline segue um contrato uniforme de 6 passos:

| Passo | O que acontece |
|-------|---------------|
| 0. Pre-requisitos | Check de dependencias + validacao da constituicao |
| 1. Contexto | Leitura de artefatos + perguntas estruturadas (Premissas, Trade-offs, Gaps, Provocacao) |
| 2. Geracao | Produz artefato seguindo template |
| 3. Auto-review | Tiered: Tier 1 (auto checks), Tier 2 (scorecard), Tier 3 (adversarial subagent para 1-way-door) |
| 4. Gate | Aprovacao humana ou automatica conforme tipo |
| 5. Save + handoff | Salva artefato, atualiza SQLite, reporta resultado, sugere proximo passo |

## Estrutura do Repositorio

```
platforms/                   # N plataformas (fulano, madruga-ai, ...)
  <name>/
    platform.yaml            # Manifesto (pipeline DAG, views, lifecycle)
    business/                # Vision, solution overview, business process
    engineering/             # Blueprint, domain model, containers, context map
    decisions/               # ADRs (formato Nygard)
    epics/                   # Shape Up pitches + SpecKit artifacts
    model/                   # LikeC4 architecture diagrams (.likec4)

.claude/commands/madruga/    # 20 skills (13 DAG + 7 utilities)
.claude/knowledge/           # Knowledge files (contracts, references)
.specify/scripts/            # Bash + Python automation
.pipeline/                   # SQLite DB (state tracking) + migrations
portal/                      # Astro + Starlight + LikeC4 (visualizacao)
```

## Comandos

```bash
# Gestao de Plataformas
python3 .specify/scripts/platform.py list              # listar plataformas
python3 .specify/scripts/platform.py new <nome>        # criar nova (copier)
python3 .specify/scripts/platform.py lint --all        # validar todas

# Portal
cd portal && npm install && npm run dev                # http://localhost:4321

# Pipeline (Claude Code skills)
/getting-started                    # onboarding interativo
/pipeline <plataforma>              # status + proximo passo
/vision <plataforma>                # gerar vision one-pager
```

## Command Namespaces

- **`madruga:*`** (ex: `/vision`, `/adr`, `/pipeline`) — Pipeline de documentacao. Opera no nivel da plataforma.
- **`speckit.*`** (ex: `/speckit.specify`, `/speckit.plan`) — Ciclo de implementacao. Opera dentro de um epic.

## Tech Stack

- **Skills**: Markdown (Claude Code custom commands) + YAML frontmatter
- **Scripts**: Bash 5.x + Python 3.11+ (stdlib + pyyaml)
- **Modelos**: LikeC4 (.likec4)
- **Portal**: Astro + Starlight + LikeC4 React
- **Estado**: SQLite WAL em `.pipeline/madruga.db`
- **Templates**: Copier para scaffolding

## Pre-requisitos

- Node.js 20+
- Python 3.11+ com `pyyaml`
- `likec4` CLI: `npm i -g likec4`
- `copier` >= 9.4.0: `pip install copier`

## Referencia

Detalhes completos em [CLAUDE.md](CLAUDE.md).
