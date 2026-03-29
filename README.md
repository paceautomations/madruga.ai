# madruga.ai

Sistema de documentacao de arquitetura para plataformas digitais. Documenta o **que** um sistema faz, **por que** as decisoes foram tomadas, e **como** as pecas se conectam — tudo versionado no git, consumivel por humanos e LLMs.

Suporta **N plataformas** a partir de um template Copier compartilhado. Cada plataforma recebe a mesma estrutura de documentacao, integracao com portal e pipeline LikeC4. A primeira plataforma e **Fulano** — agentes conversacionais WhatsApp multi-tenant para PMEs brasileiras.

## Pipeline de Documentacao (DAG)

Cada plataforma e documentada incrementalmente por **21 skills atomicas** orquestradas por um DAG. Cada skill e autocontida (contexto fresco), produz um artefato e e validada antes de prosseguir.

```
BUSINESS
  1. platform-new ─→ 2. vision ─→ 3. solution-overview ─→ 4. business-process
                       │                                         │
                       ├─ ─ ─ ─→ 6. codebase-map (opcional)     │
                       │                                         │
RESEARCH               │                                         │
                       │              5. tech-research ←─────────┘
                       │                     │
ENGINEERING            │                     ▼
                       │              7. adr-gen
                       │                     │
                       │                     ▼
                       │              8. blueprint ──────────→ 9. folder-arch
                       │                  │    │
                       │                  │    └────────────┐
                       │                  ▼                 ▼
                       └────────→ 10. domain-model ──→ 11. containers
                                       │    │              │
                                       │    └──────→ 12. context-map
                                       │                   │
PLANNING                               ▼                   │
                                  13. epic-breakdown ←─────┘
                                       │
                                       ▼
                                  14. roadmap
                                       │
                                       ▼
PER-EPIC CYCLE              ┌───────────────────────────┐
(repete por epico)          │  discuss                  │
                            │    → speckit.specify      │
                            │    → speckit.clarify      │
                            │    → speckit.plan         │
                            │    → speckit.tasks        │
                            │    → speckit.analyze      │
                            │    → speckit.implement    │
                            │    → speckit.analyze      │
                            │    → verify               │
                            │    → test-ai (opcional)   │
                            │    → reconcile            │
                            └───────────────────────────┘
### Gates

| Gate | Comportamento | Skills |
|------|--------------|--------|
| `human` | Sempre pausa para aprovacao | platform-new, vision, solution-overview, business-process, blueprint, folder-arch, domain-model, containers, context-map, roadmap |
| `1-way-door` | Sempre pausa — decisoes irreversiveis | tech-research, adr-gen, epic-breakdown |
| `auto` | Procede automaticamente | codebase-map |
| `auto-escalate` | Auto se OK, escala se encontrar blockers | verify |

### DAG Nodes (14 skills)

| # | Skill | Output | Depende de | Gate |
|---|-------|--------|------------|------|
| 1 | `platform-new` | platform.yaml | — | human |
| 2 | `vision-one-pager` | business/vision.md | platform-new | human |
| 3 | `solution-overview` | business/solution-overview.md | vision | human |
| 4 | `business-process` | business/process.md | solution-overview | human |
| 5 | `tech-research` | research/tech-alternatives.md | business-process | 1-way-door |
| 6 | `codebase-map` | research/codebase-context.md | vision | auto (opcional) |
| 7 | `adr-gen` | decisions/ADR-*.md | tech-research | 1-way-door |
| 8 | `blueprint` | engineering/blueprint.md | adr-gen | human |
| 9 | `folder-arch` | engineering/folder-structure.md | blueprint | human |
| 10 | `domain-model` | engineering/domain-model.md + model/ddd-contexts.likec4 | blueprint, business-process | human |
| 11 | `containers` | engineering/containers.md + model/platform.likec4 | domain-model, blueprint | human |
| 12 | `context-map` | engineering/context-map.md | domain-model, containers | human |
| 13 | `epic-breakdown` | epics/*/pitch.md | domain-model, containers, context-map | 1-way-door |
| 14 | `roadmap` | planning/roadmap.md | epic-breakdown | human |

### Ciclo Per-Epic (pos-roadmap)

Apos o roadmap, cada epico segue:

| Step | Skill | Gate | O que faz |
|------|-------|------|-----------|
| 1 | `discuss` | human | Captura contexto e decisoes de implementacao |
| 2 | `speckit.specify` | human | Especificacao da feature |
| 3 | `speckit.clarify` | human | Reduz ambiguidade na spec antes de planejar |
| 4 | `speckit.plan` | human | Artefatos de design |
| 5 | `speckit.tasks` | human | Task breakdown |
| 6 | `speckit.analyze` | auto | Consistencia pre-impl (spec/plan/tasks) |
| 7 | `speckit.implement` | auto | Executa tasks |
| 8 | `speckit.analyze` | auto | Consistencia pos-impl |
| 9 | `verify` | auto-escalate | Verifica implementacao vs spec/tasks/arquitetura |
| 10 | `test-ai` | human (opcional) | QA test via Playwright — pular para epics sem UI |
| 11 | `reconcile` | human | Detecta e corrige drift entre implementacao e docs |

`test-ai` roda antes de `reconcile` porque seu heal loop pode alterar codigo, criando drift novo.

### Utility Skills

| Skill | O que faz |
|-------|-----------|
| `pipeline-status` | Tabela + Mermaid DAG colorido + progresso |
| `pipeline-next` | Recomenda proximo passo (NAO auto-executa) |
| `checkpoint` | Salva STATE.md com progresso da sessao |

## Contrato das Skills

Toda skill do pipeline segue um contrato uniforme de 6 passos:

| Passo | O que acontece |
|-------|---------------|
| 0. Pre-requisitos | Check de dependencias + validacao da constituicao |
| 1. Contexto | Leitura de artefatos + perguntas estruturadas (Premissas, Trade-offs, Gaps, Provocacao) |
| 2. Geracao | Produz artefato seguindo template |
| 3. Auto-review | Checklist de qualidade (alternativas documentadas, trade-offs explicitos, dados) |
| 4. Gate | Aprovacao humana ou automatica conforme tipo |
| 5. Save + handoff | Salva artefato, reporta resultado, sugere proximo passo |

## Framework de 3 Camadas

Cada plataforma e documentada em 3 camadas:

### Business — por que e para quem

| Artefato | Pergunta |
|----------|----------|
| **Vision Brief** | Por que existe? Para quem? Moat competitivo? (Playing to Win) |
| **Business Process** | Como funciona ponta-a-ponta? (pipeline, decision points) |
| **Solution Overview** | O que construir e em que ordem? (feature map Now/Next/Later + personas) |

### Engineering — como funciona tecnicamente

| Artefato | Pergunta |
|----------|----------|
| **Blueprint** | Cross-cutting concerns, NFRs, deploy topology? |
| **Folder Architecture** | Como organizar o codigo? (naming conventions, module boundaries) |
| **Domain Model** | Quais entidades, invariantes, schemas SQL? (DDD tatico) |
| **Containers** | Quais processos deployaveis, storage e protocolos? (C4 L2) |
| **Context Map** | Quais dominios, fronteiras e relacoes DDD? |
| **ADRs** | Por que essa decisao e nao outra? (Nygard: Context, Decision, Alternatives, Consequences) |

### Planning — o que construir e quando

| Artefato | Pergunta |
|----------|----------|
| **Epic Breakdown** | Como dividir em entregas? (Shape Up: problema, appetite, solucao, rabbit holes) |
| **Roadmap** | Qual a sequencia e o MVP? (dependencias entre epicos, milestones) |

## Estrutura do Repositorio

```
.specify/                          # SpecKit + platform tooling
  scripts/
    bash/                          # Shell scripts (check-prerequisites, etc.)
    vision-build.py                # LikeC4 JSON → markdown tables (AUTO markers)
    platform.py                    # Platform CLI (new, lint, sync, register, list)
  templates/
    platform/                      # Copier template para novas plataformas
    *.md                           # SpecKit templates (spec, plan, tasks, etc.)
  memory/                          # Constituicao e memoria do projeto

platforms/
  fulano/                          # Primeira plataforma (Fulano)
  <nova-plataforma>/               # Plataformas adicionais (via copier)
    platform.yaml                  # Manifesto (nome, lifecycle, views, commands)
    business/                      # Vision brief, solution overview, business process
    engineering/                   # Blueprint, domain model, containers, context map
    decisions/                     # ADRs (formato Nygard)
    epics/                         # Shape Up pitch documents
    research/                      # Pesquisa de mercado, benchmarks tecnicos
    model/                         # LikeC4 architecture model (.likec4 files)

portal/                            # Astro + Starlight (auto-descobre plataformas)
  src/lib/platforms.mjs            # Platform discovery + sidebar dinamica
  src/pages/[platform]/            # Dynamic routes para todas plataformas

.claude/
  commands/madruga/                # 21 skills (14 DAG + 6 utilities + test-ai)
  knowledge/                       # Knowledge files carregados on-demand pelas skills
```

## Comandos

```bash
# Gestao de Plataformas
python3 .specify/scripts/platform.py list              # listar plataformas
python3 .specify/scripts/platform.py new <nome>        # criar nova (copier)
python3 .specify/scripts/platform.py lint <nome>       # validar estrutura
python3 .specify/scripts/platform.py lint --all        # validar todas
python3 .specify/scripts/platform.py sync              # copier update em todas
python3 .specify/scripts/platform.py register <nome>   # atualizar symlinks do portal

# Portal
cd portal && npm install && npm run dev                # http://localhost:4321

# LikeC4
cd platforms/<nome>/model && likec4 serve              # http://localhost:5173

# Build Pipeline
python3 .specify/scripts/vision-build.py <nome>              # popular tabelas AUTO
python3 .specify/scripts/vision-build.py <nome> --export-png  # exportar PNGs

# Pipeline Navigation (Claude Code skills)
/pipeline-status <plataforma>          # ver status do DAG
/pipeline-next <plataforma>            # proximo passo recomendado
```

## Pre-requisitos

- Node.js 20+
- Python 3.11+ com `pyyaml`
- `likec4` CLI: `npm i -g likec4`
- `copier` >= 9.4.0: `pip install copier`
