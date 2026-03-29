# Madruga AI — Architecture Documentation & Spec-to-Code System

> Sistema de documentacao arquitetural e pipeline spec-to-code para plataformas digitais.
> Data: 2026-03-27 | Autor: Gabriel Hamu | Status: Living Document
> Repositorio: `paceautomations/madruga.ai`

---

## Problema

Documentacao de arquitetura, especificacao de features e implementacao estavam dispersas em repos, skills e scripts sem contexto compartilhado. Resultado: architectural drift, specs sem contexto macro, e documentacao que vira ficcao em semanas.

## Resultado Esperado

Repositorio dedicado `paceautomations/madruga.ai` — pipeline unico onde arquitetura alimenta specs, implementacao fecha o loop, e um daemon executa autonomamente:
- Plataformas como unidade central: `platforms/<name>/` contem Vision (arquitetura macro) + epicos autocontidos (pitch + spec + plan + tasks)
- Cada epico implementado atualiza automaticamente a Vision (RECONCILE)
- LikeC4-first: `.likec4` files como source of truth, markdown como view layer
- 13 skills (namespace `madruga/` + `speckit.*`) — arquitetura, especificacao e execucao
- Artifact Model MECE: cada artefato tem 1 dono (skill) e 1 proposito, progressao linear pitch → spec → plan → tasks → implement
- Portal Starlight com diagramas LikeC4 interativos e auto-discovery de plataformas
- Copier template system para scaffolding padronizado de novas plataformas
- Runtime engine Python (10K LOC) com daemon 24/7, debate engine, decision gates, learning loop
- Mesmas skills e templates usadas tanto pelo humano (interativo) quanto pelo daemon (autonomo via `SpeckitBridge`)

---

## Arquitetura do Sistema

```
FLUXO COMPLETO:

  [HUMANO + SKILLS]                         [DAEMON AUTONOMO]
  (interativo, on-demand)                   (24/7, services/madruga-ai)
  -----------------------                   ---------------------------
  /madruga/platform-new fulano
    -> Copier scaffolding                    MadrugaDaemon (asyncio)
    -> platforms/fulano/ criado              |
    -> Portal registrado                     kanban_poll.py (60s)
                                             |
  /madruga/vision fulano           Obsidian kanban → detecta APPROVED
    -> Playing to Win framework              |
    -> Gera business/vision.md               Orchestrator (slots, queue)
                                             |
  /madruga/solution-overview fulano          SpeckitBridge le:
    -> Feature map + personas                  .claude/commands/speckit.*.md
    -> Gera business/solution-overview.md      .specify/templates/*-template.md
                                               .specify/memory/constitution.md
  Edicao manual LikeC4:                      |
    -> model/*.likec4 (source of truth)      specify -> spec.md
    -> vision-build.py popula AUTO markers     (+ Vision context: brief, context-map)
    -> engineering/ docs atualizados           (+ debate: personas validam, 2 rounds)
                                               (+ clarify: 9 categorias de gaps)
  /speckit.specify fulano 001                  (+ stress test)
    -> Le pitch.md como input                |
    -> Gera spec.md                          plan -> plan.md
                                               (+ Context Map + modelo dominio + ADRs)
  /speckit.plan fulano 001                     (+ specialists: DDD, Perf, Security, DevOps, Cost)
    -> Le spec.md + Vision context           |
    -> Gera plan.md                          tasks -> tasks.md
                                             |
  /speckit.tasks fulano 001                  implement -> codigo no TARGET REPO
    -> Le plan.md + spec.md                    (git worktree no target)
    -> Gera tasks.md                           (code review critics: 4 tipos)
                                               (test runner automatico)
  /speckit.implement fulano 001              |
    -> Executa tasks no TARGET REPO          persona_interview
    -> tasks.md [X] atualizado                 (personas avaliam implementacao)
                                             |
                                             review -> PR criado
                                             |
                                             RECONCILE (planejado)
                                               1. Le diff do PR
                                               2. Compara vs arquitetura
                                               3. drift < 0.3 -> auto-update
                                               4. drift >= 0.3 -> escala humano

  /speckit.analyze fulano
    -> Consistencia Vision<->Specs<->Code
    -> CRITICAL/WARNING/NIT
```

Os dois lados usam as **mesmas skills e templates** — a diferenca e que o lado esquerdo e interativo (humano invoca) e o direito e autonomo (daemon invoca via `claude -p` com `SpeckitBridge`).

---

## Estrutura de Pastas

```
paceautomations/madruga.ai/
├── .specify/                          # SpecKit + platform tooling
│   ├── scripts/
│   │   ├── bash/                      # SpecKit shell scripts
│   │   ├── vision-build.py            # LikeC4 JSON → popula markdown tables
│   │   └── platform.py               # Platform CLI (new, lint, sync, register, list)
│   ├── templates/
│   │   ├── platform/                  # Copier template para scaffolding
│   │   │   ├── copier.yml             # Config + perguntas do template
│   │   │   ├── template/             # Jinja2 files (business/, engineering/, etc.)
│   │   │   └── tests/                # Template validation tests (pytest)
│   │   └── *.md                      # SpecKit templates (spec, plan, tasks, checklist)
│   └── memory/
│       └── constitution.md            # Project constitution
├── platforms/
│   └── fulano/                        # Primeira plataforma
│       ├── platform.yaml              # Manifesto declarativo
│       ├── .copier-answers.yml        # Copier state (enables copier update)
│       ├── business/                  # vision.md, solution-overview.md
│       ├── engineering/               # domain-model.md, integrations.md
│       ├── decisions/                 # ADR-001 a ADR-019 (19 ADRs, formato Nygard)
│       ├── epics/                     # 15 folders (001-015), cada um com pitch.md
│       ├── research/                  # Pesquisas de mercado e benchmarks
│       └── model/                     # LikeC4 architecture model (8 files)
├── portal/                            # Astro + Starlight + LikeC4 React
│   ├── src/lib/platforms.mjs          # Auto-discovery de plataformas
│   ├── src/pages/[platform]/          # Dynamic routes (7 pages + bc/)
│   ├── src/components/viewers/        # LikeC4Diagram.tsx (React wrapper)
│   └── astro.config.mjs              # Sidebar dinamica, LikeC4 Vite plugin
├── .claude/
│   ├── commands/madruga/              # 4 skills de arquitetura
│   ├── commands/speckit.*.md          # 9 skills de especificacao
│   └── knowledge/                     # Knowledge files on-demand
├── docs/                              # Docs auxiliares e comparativos
├── CLAUDE.md                          # Guidelines para Claude Code
├── README.md
│
│   # ── Apos consolidacao (migrar de general/services/madruga-ai) ──
├── src/                               # Runtime engine Python (10K LOC)
│   ├── api/                           # ClaudeClient (claude -p), circuit breaker, retry
│   ├── phases/                        # specify, plan, tasks, implement, interview, review
│   ├── debate/                        # Multi-persona debate engine
│   ├── decisions/                     # 1-way/2-way door classifier + gates
│   ├── memory/                        # SQLite store, learning, patterns
│   ├── clarify/                       # Gap analysis engine
│   ├── git/                           # Worktree + PR creation
│   ├── integrations/                  # Obsidian CRUD, WhatsApp bridge
│   ├── speckit/                       # SpeckitBridge (compositor — le de .claude/ e .specify/)
│   ├── stress/                        # Arch fitness, spec compliance
│   ├── dashboard/                     # FastAPI web dashboard
│   └── daemon.py, orchestrator.py, kanban_poll.py, cli.py, config.py
├── tests/                             # 51 testes (10K LOC)
├── .claude/
│   └── prompts/                       # 22 system prompts para claude -p (debate, review)
│       ├── personas/                  # business-analyst, qa-engineer, security-reviewer
│       ├── specialists/               # DDD, performance, security, devops, cost
│       ├── code_critics/              # code-reviewer, perf-profiler, security-scanner, spec-compliance
│       └── reviewers/                 # integration, regression, UX
├── config.yaml                        # Config principal (repos, throttle, daemon, personas)
├── deploy/                            # systemd service + logrotate
└── server.py                          # FastAPI entry point
```

---

### Three-Layer Documentation Framework

Cada plataforma e documentada em 3 camadas:

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
  └───────────────────────────────┬──────────────────────────────────────────┘
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

#### Business — por que e para quem

| Artefato | Local | Conteudo |
|----------|-------|----------|
| **Vision Brief** | `business/vision.md` | Playing to Win: tese, mercado, moat, pricing |
| **Business Flow** | LikeC4 view `businessFlow` | Pipeline animado ponta-a-ponta (14 modulos) |
| **Solution Overview** | `business/solution-overview.md` | Feature map Now/Next/Later + personas + principios |

#### Engineering — como funciona tecnicamente

| Artefato | Local | Conteudo |
|----------|-------|----------|
| **Domain Model** | `engineering/domain-model.md` | Class diagrams, SQL schemas, Pydantic structs, invariantes |
| **Integrations** | `engineering/integrations.md` | 19 integracoes com protocolo, direcao, frequencia, fallback (AUTO-gerado) |
| **Containers** | Portal + AUTO markers | Tabela de containers C4 L2 (auto-gerada do modelo LikeC4) |
| **Context Map** | Portal + AUTO markers | Bounded contexts DDD + relacoes (auto-gerado) |
| **ADRs** | `decisions/ADR-NNN-*.md` | 19 ADRs formato Nygard: Context, Decision, Alternatives, Consequences |

#### Planning — o que construir e quando

| Artefato | Local | Conteudo |
|----------|-------|----------|
| **Epics** | `epics/NNN-slug/pitch.md` | 15 epicos Shape Up: problema, appetite, solucao, rabbit holes |
| **Roadmap** | Portal `/roadmap/` | Prioridade Now/Next/Later (gerado do frontmatter dos epicos) |

---

### Copier Template System

Novas plataformas sao scaffoldadas a partir de `.specify/templates/platform/`:

```bash
copier copy .specify/templates/platform/ platforms/<name>/
```

Cada plataforma recebe a mesma estrutura (business/, engineering/, decisions/, epics/, model/) com `platform.yaml` como manifesto declarativo e `.copier-answers.yml` para sync futuro via `copier update`.

O `model/spec.likec4` e o unico arquivo de modelo que sincroniza — todos os outros sao platform-specific.

---

### LikeC4 Model Pipeline

Os arquivos `.likec4` sao a **source of truth** para a arquitetura. Pipeline:

1. **Edicao**: 8 arquivos `.likec4` definem elementos, relacoes e views (spec, actors, platform, externals, infrastructure, ddd-contexts, relationships, views)
2. **Export**: `likec4 export json` gera `model/output/likec4.json`
3. **Populate**: `.specify/scripts/vision-build.py` le o JSON e popula tabelas markdown via marcadores `<!-- AUTO:name -->`

Marcadores AUTO disponiveis:

| Marcador | Arquivo | Conteudo gerado |
|----------|---------|-----------------|
| `containers` | `engineering/containers.md` | Containers (tech, porta, responsabilidade) |
| `domains` | `engineering/context-map.md` | Bounded contexts (modulos, pattern DDD) |
| `relations` | `engineering/context-map.md` | Relacoes DDD (upstream/downstream) |
| `integrations` | `engineering/integrations.md` | Integracoes (protocolo, direcao, fallback) |

---

### Portal Starlight

Portal interativo em Astro + Starlight com diagramas LikeC4 (pan, zoom, drill-down):

- **Auto-discovery**: `src/lib/platforms.mjs` escaneia `platforms/*/platform.yaml` e constroi sidebar dinamica
- **Dynamic routes**: `src/pages/[platform]/` gera paginas para toda plataforma automaticamente
- **LikeC4 React**: `LikeC4Diagram.tsx` usa `React.lazy` com imports per-project (`likec4:react/<name>`)
- **Symlinks**: `setup.sh` cria `src/content/docs/<name> → platforms/<name>` para Starlight consumir os markdowns

Paginas por plataforma: landscape, containers, context-map, business-flow, bc/[context], roadmap, decisions.

---

### Artifact Model (MECE)

Cada artefato tem UM dono (skill) e UM proposito. Nenhum artefato duplica informacao de outro. Progressao linear.

#### Platform-Level (Vision)

| Artefato | Dono | Proposito |
|----------|------|-----------|
| `business/vision.md` | `madruga/vision` | Visao macro: tese, mercado, moat, pricing (Playing to Win) |
| `business/solution-overview.md` | `madruga/solution-overview` | Feature map Now/Next/Later + personas + principios |
| Business Flow | LikeC4 view `businessFlow` | Pipeline ponta-a-ponta animado (14 modulos) |
| `engineering/domain-model.md` | Manual | Entidades, class diagrams, SQL schemas, invariantes |
| `engineering/integrations.md` | `vision-build.py` (AUTO) | Integracoes externas (protocolo, direcao, fallback) |
| `engineering/containers.md` | `vision-build.py` (AUTO) | Containers C4 L2 (tech, porta, responsabilidade) |
| `engineering/context-map.md` | `vision-build.py` (AUTO) | Bounded contexts DDD + relacoes |
| `model/*.likec4` | Manual (LikeC4 DSL) | Source of truth: 8 arquivos definem toda a arquitetura |
| `decisions/ADR-*.md` | Manual | Decisoes arquiteturais formato Nygard |
| `platform.yaml` | `madruga/platform-new` | Manifesto declarativo (lifecycle, views, comandos) |

#### Epic-Level (por epico, dentro de `NNN-slug/`)

| Artefato | Dono | Proposito | Input |
|----------|------|-----------|-------|
| `pitch.md` | Manual / `madruga/vision` | Shape Up bet: problema, appetite, solucao, rabbit holes | Discovery interativo |
| `spec.md` | `speckit.specify` | Requisitos funcionais: user scenarios, acceptance criteria | `pitch.md` |
| `plan.md` | `speckit.plan` | Design tecnico: stack, arquitetura, file structure | `spec.md` + Vision context (ADRs, Context Map, modelo dominio) |
| `research.md` | `speckit.plan` | Pesquisa tecnica: decisoes, alternatives, rationale (opcional) | `spec.md` unknowns |
| `data-model.md` | `speckit.plan` | Entidades, campos, relacionamentos (opcional) | `spec.md` entities |
| `contracts/` | `speckit.plan` | API contracts, interfaces (opcional) | `spec.md` functional reqs |
| `tasks.md` | `speckit.tasks` | Breakdown ordenado de tarefas executaveis | `plan.md` + `spec.md` user stories |
| `checklists/` | `speckit.checklist` | Quality gates por dominio | `spec.md` |

#### Regras

- `pitch.md` NAO contem requisitos funcionais (isso e `spec.md`)
- `spec.md` NAO contem decisoes tecnicas (isso e `plan.md`)
- `plan.md` NAO contem task breakdown (isso e `tasks.md`)
- Cada skill GERA seu artefato e LE os anteriores como input
- Progressao linear: `pitch → spec → plan → tasks → implement`

---

### Skills

#### Arquitetura — `.claude/commands/madruga/` (4 skills)

**`madruga/platform-new`** — Scaffolda plataforma
1. Copier copy de `.specify/templates/platform/`
2. Registra no portal (symlinks + LikeC4Diagram.tsx)
3. Resultado: `platforms/<name>/` com toda a estrutura

**`madruga/vision`** — Gera Vision Brief
1. Playing to Win framework (11 perguntas)
2. Gera `business/vision.md`

**`madruga/solution-overview`** — Gera Solution Overview
1. Feature map Now/Next/Later + personas + principios de produto
2. Gera `business/solution-overview.md`

#### Especificacao — `.claude/commands/speckit.*.md` (9 skills)

**`speckit.specify`** — Gera spec.md
1. Le `pitch.md` como input
2. Gera `spec.md` com requisitos funcionais, user scenarios, success criteria
3. Gera `checklists/requirements.md`

**`speckit.clarify`** — Gap analysis context-aware
- Sem `--epic`: Vision gap analysis (9 categorias: dominios incompletos, integracoes ausentes, NFRs vagos, decisoes implicitas, metricas sem targets, anti-escopo, riscos sem mitigacao, entidades orfas, containers desconectados)
- Com `--epic`: Clarificacao de spec (max 3 perguntas NEEDS CLARIFICATION)

**`speckit.plan`** — Design tecnico
1. Le `spec.md` como input principal
2. Injeta Vision context: Context Map, modelo dominio, ADRs
3. Gera `plan.md` + `research.md` (opcional) + `data-model.md` (opcional) + `contracts/` (opcional)

**`speckit.tasks`** — Task breakdown
1. Le `plan.md` + `spec.md` (user stories)
2. Gera `tasks.md` organizado por user story

**`speckit.implement`** — Executa tasks no target repo. Atualiza checkboxes `[X]` em `tasks.md`.

**`speckit.analyze`** — Cross-artifact consistency
- `--scope vision`: Vision↔Vision (consistencia entre artefatos de arquitetura)
- `--scope spec`: spec↔plan↔tasks (consistencia entre artefatos do epico)
- `--scope full` (default): ambos + cross-check Vision↔Specs

**`speckit.checklist`** — Gera quality checklists dentro de `<epic>/checklists/`

**`speckit.constitution`** — Gerencia project constitution (`.specify/memory/constitution.md`)

**`speckit.taskstoissues`** — Exporta tasks para GitHub Issues

**Pipeline**: `specify → clarify → plan → tasks → analyze → implement → taskstoissues`

---

### Epic Lifecycle

Cada epic e um folder autocontido em `platforms/<name>/epics/NNN-slug/`. A pasta cresce progressivamente conforme avanca pelo pipeline:

#### Fase 1 — Criacao (pitch)
```
epics/001-channel-pipeline/
  pitch.md              ← Manual ou /madruga/vision (Shape Up pitch)
```

#### Fase 2 — Especificacao (speckit.specify)
```
epics/001-channel-pipeline/
  pitch.md              ← LIDO (input)
  spec.md               ← CRIADO (requisitos funcionais)
  checklists/
    requirements.md     ← CRIADO (quality gate)
```

#### Fase 3 — Planejamento (speckit.plan)
```
epics/001-channel-pipeline/
  spec.md               ← LIDO (input principal)
  plan.md               ← CRIADO (injeta Vision: Context Map, ADRs, modelo dominio)
  research.md           ← CRIADO (opcional — resolve unknowns)
  data-model.md         ← CRIADO (opcional — entidades)
  contracts/            ← CRIADO (opcional — API specs)
```

#### Fase 4 — Tarefas (speckit.tasks)
```
epics/001-channel-pipeline/
  plan.md               ← LIDO (input principal)
  spec.md               ← LIDO (user stories para organizar tasks)
  tasks.md              ← CRIADO (breakdown ordenado)
```

#### Fase 5 — Implementacao (speckit.implement)
```
Codigo no TARGET REPO (fulano-api, etc.), NAO dentro do epico.
tasks.md checkboxes atualizados [X] conforme progresso.
```

#### Fase 6 — Reconciliacao (FUTURO: RECONCILE)
```
Vision artifacts atualizados se drift < threshold.
roadmap.md status atualizado automaticamente.
```

Formato Shape Up para pitches: Problem, Appetite, Solution, Rabbit Holes, Acceptance Criteria. O frontmatter contem metadados (id, status, phase, appetite, arch modules/contexts/containers).

---

### Decisoes Arquiteturais

| Decisao | Escolha | Rationale |
|---------|---------|-----------|
| Repositorio | `paceautomations/madruga.ai` (dedicado) | Isolamento, CI proprio, CLAUDE.md especifico |
| Template system | Copier (`.specify/templates/platform/`) | Scaffolding padronizado, `copier update` para sync |
| Architecture source of truth | LikeC4 `.likec4` files | DSL tipado, views interativas, export JSON programatico |
| Portal | Astro + Starlight + LikeC4 React | Auto-discovery, SSG, diagramas interativos |
| Config | YAML (`platform.yaml` por plataforma) | Declarativo, humano-readable, sem overhead |
| Storage | File-based (git) → **DB-first com Supabase** (proposto) | Hoje: files-only. Proposta: DB (Supabase/Postgres) como source of truth para estado, metadados e relacoes; Git para conteudo narrativo e modelos LikeC4. Ver `docs/db-first-architecture.md` |
| Spec pipeline | SpecKit (9 skills) | Progressao linear pitch → spec → plan → tasks |
| Epics | Shape Up (folders autocontidos) | Portavel, git-friendly, cada epic contem tudo |
| ADRs | Nygard (Context, Decision, Alternatives, Consequences) | Standard industry, rastreavel |
| Build pipeline | vision-build.py + AUTO markers | LikeC4 JSON → markdown tables automaticamente |

---

### CLI

```bash
# Platform management
python3 .specify/scripts/platform.py list
python3 .specify/scripts/platform.py new <name>
python3 .specify/scripts/platform.py lint <name>
python3 .specify/scripts/platform.py lint --all
python3 .specify/scripts/platform.py sync
python3 .specify/scripts/platform.py register <name>

# Build pipeline
python3 .specify/scripts/vision-build.py <name>
python3 .specify/scripts/vision-build.py <name> --validate-only
python3 .specify/scripts/vision-build.py <name> --export-png

# Portal
cd portal && npm install && npm run dev    # http://localhost:4321

# LikeC4 standalone
cd platforms/<name>/model && likec4 serve  # http://localhost:5173
```

### platform.yaml

Manifesto declarativo de cada plataforma:

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
  command: "likec4 build"
  export_json: "likec4 export json --pretty --skip-layout -o output/likec4.json"
  cwd: "model/"
  markdown: "python3 .specify/scripts/vision-build.py fulano"
```

---

## Runtime Engine (services/madruga-ai)

O engine Python que executa o pipeline autonomamente ja esta construido em `paceautomations/general/services/madruga-ai`. Sao **10K LOC + 10K LOC de testes + 22 prompts + SQLite + daemon systemd**. Este codigo e a continuidade natural do sistema — transforma as skills e templates em execucao autonoma.

### Inventario do Engine

| Camada | Modulos | O que faz |
|--------|---------|-----------|
| **Core Engine** | `daemon.py`, `orchestrator.py`, `kanban_poll.py`, `pipeline.py`, `cli.py`, `config.py` | Daemon 24/7 asyncio que monitora Obsidian kanban e auto-executa pipeline |
| **7 Phases** | `specify.py`, `plan.py`, `tasks.py`, `implement.py`, `persona_interview.py`, `review.py`, `vision.py` | Pipeline completo spec-to-code com review de personas |
| **AI Layer** | `api/client.py`, `circuit_breaker.py`, `retry.py` | Wrapper `claude -p` com circuit breaker e retry |
| **Debate Engine** | `debate/runner.py`, `convergence.py`, `models.py` | Multi-persona debate com convergencia automatica |
| **Decision System** | `decisions/classifier.py`, `gates.py` | Classificador 1-way/2-way door + gates automaticos |
| **Memory/Learning** | `memory/db.py`, `learning.py`, `patterns.py`, `persona_accuracy.py` | SQLite store, pattern extraction, learning loop |
| **Clarify** | `clarify/engine.py` | Gap analysis com 9 categorias |
| **Git Ops** | `git/worktree.py`, `pr.py` | Git worktree para implement + PR creation |
| **Integrations** | `integrations/obsidian.py`, `messaging/` (WhatsApp) | CRUD Obsidian + WhatsApp bridge |
| **Quality** | `stress/arch_fitness.py`, `coverage.py`, `spec_test.py` | Architecture fitness functions + spec compliance |
| **SpecKit Bridge** | `speckit/bridge.py` | Compositor de prompts — le de `.claude/commands/` + `.specify/templates/` + `.specify/memory/`, nao contem agentes |
| **Infra** | `health.py`, `dashboard/`, `deploy/`, `server.py` | FastAPI dashboard + systemd service |
| **22 Prompts** | `prompts/personas/`, `specialists/`, `code_critics/`, `reviewers/` | System prompts para `claude -p` (debate engine, code review). NAO sao skills Claude Code — sao system prompts passados ao subprocess. Ver decisao abaixo. |

### Como o Engine Conecta com as Skills

O `SpeckitBridge` e o ponto de conexao — le diretamente de:
- `.claude/commands/speckit.{name}.md` — skills (specify, plan, tasks, clarify, analyze)
- `.specify/templates/{name}-template.md` — templates (spec, plan, tasks, checklist)
- `.specify/memory/constitution.md` — constitution

Ao migrar o codigo para o madruga.ai, o bridge automaticamente consome as skills e templates que **ja existem** no repo. Zero reescrita de prompts.

O bridge transforma skills interativas em prompts autonomos:
1. Remove frontmatter YAML
2. Remove blocos bash com scripts interativos
3. Remove AskUserQuestion / patterns interativos
4. Injeta bloco "Autonomous Mode" (sem clarification markers, sem esperar humano)
5. Compoe: `constitution + template + skill + epic context + autonomous`

### Separacao: Skills vs Prompts

Tudo vive em `.claude/`, mas com papeis distintos:

| Tipo | Path | Consumido por | Proposito |
|------|------|---------------|-----------|
| **Skills** | `.claude/commands/speckit.*.md` | `SpeckitBridge` (autonomo) + Claude Code (interativo) | Pipeline spec-to-code: specify, plan, tasks, etc. |
| **Skills** | `.claude/commands/madruga/*.md` | Claude Code (interativo) | Arquitetura: platform-new, vision, solution-overview |
| **System prompts** | `.claude/prompts/personas/*.md` | `debate/runner.py` via `claude -p` | Personas para debate (QA, Business, Security) |
| **System prompts** | `.claude/prompts/specialists/*.md` | `debate/runner.py` via `claude -p` | Specialists para plan (DDD, Perf, DevOps, Cost) |
| **System prompts** | `.claude/prompts/code_critics/*.md` | `debate/runner.py` via `claude -p` | Critics para code review (reviewer, profiler, scanner) |
| **System prompts** | `.claude/prompts/reviewers/*.md` | `debate/runner.py` via `claude -p` | Reviewers para interview (integration, regression, UX) |
| **Knowledge** | `.claude/knowledge/*.md` | Claude Code (auto-loaded by skills) | Contexto on-demand |
| **Templates** | `.specify/templates/*.md` | `SpeckitBridge` | Templates de artefatos (spec, plan, tasks) |
| **Constitution** | `.specify/memory/constitution.md` | `SpeckitBridge` | Regras que governam todos os artefatos |

### Plano de Consolidacao

A migracao do engine para o madruga.ai e **plug-and-play** porque o `SpeckitBridge` ja usa os mesmos paths (`.claude/commands/`, `.specify/templates/`, `.specify/memory/`).

#### Etapa 1 — Mover codigo Python

| Origem (`general/services/madruga-ai/`) | Destino (`madruga.ai/`) | Nota |
|---|---|---|
| `src/` (65 arquivos Python) | `src/` | Direto |
| `tests/` (51 testes) | `tests/` | Direto |
| `prompts/` (22 prompts) | `.claude/prompts/` | Consolida tudo em `.claude/` — system prompts para `claude -p`, nao skills interativas |
| `config.yaml` | `config.yaml` | Ajustar `speckit.repo_root` e adicionar `platforms` |
| `pyproject.toml` | `pyproject.toml` | Direto |
| `requirements.txt` | `requirements.txt` | Direto |
| `server.py` | `server.py` | Direto |
| `deploy/` | `deploy/` | Direto |
| `templates/` (dashboard HTML) | `templates/` | Direto |

#### Etapa 2 — Ajustar config.yaml

```yaml
# Atualizar paths para o novo repo
speckit:
  repo_root: ~/repos/paceautomations/madruga.ai   # era general

# Prompts movidos para .claude/
personas:
  fallback_dir: .claude/prompts/personas/          # era prompts/personas/
specialists:
  dir: .claude/prompts/specialists/                # era prompts/specialists/

# Adicionar config de plataformas
platforms:
  fulano:
    repos: [fulano-api, fulano-admin]
    vision_dir: platforms/fulano
```

#### Etapa 3 — Conectar epics ao pipeline

O engine hoje usa `madruga.db` (SQLite) para rastrear epics. Com a proposta DB-first (`docs/db-first-architecture.md`), o destino final e Supabase (PostgreSQL). Transicao:

- **Curto prazo**: SQLite como hoje — script de import le frontmatter dos `pitch.md` e insere no SQLite
- **Medio prazo**: Migrar para Supabase (schema `platforms`, `epics`, `pipeline_runs`, `events`) — queries cross-platform, dashboard real-time, tracking de custo/tokens

#### Etapa 4 — Estender SpeckitBridge para Vision Context

O bridge hoje compoe prompts com `constitution + template + skill + epic`. Para injetar Vision context (arquitetura da plataforma), estender com:

```python
def compose_specify_prompt(self, epic, platform_context=None):
    # ... existing code ...
    if platform_context:
        vision_block = f"\n\n## Platform Vision\n\n{platform_context.vision_brief}\n"
        context_map_block = f"\n\n## Context Map\n\n{platform_context.context_map}\n"
        prompt += vision_block + context_map_block
```

Cada fase recebe contexto proporcional (ver tabela Vision Context Injection abaixo).

#### Etapa 5 — Rodar testes

```bash
cd madruga.ai
pip install -r requirements.txt
pytest  # 51 testes devem passar
```

#### Etapa 6 — Deprecar no general

Apos validacao, marcar `services/madruga-ai/` no general como deprecated com README apontando para o madruga.ai.

### O que NAO migra

- `services/automation-api/` — permanece no general
- `services/doc-api/` — permanece
- `services/vibe-reporting-service/` — permanece
- `services/content_gen/` — permanece
- `obsidian-vault/` — permanece (daemon le via path configuravel)

---

## O Que Vem Depois

### DB-First com Supabase (proposta)

Migracao de storage file-only para DB-first com Supabase. Pesquisa de mercado mostra que todos os frameworks de alta performance (Paperclip, Devin, Backstage, StrongDM) sao DB-backed. Detalhes completos em `docs/db-first-architecture.md`.

**Principio**: Git = source of truth para conteudo (prose, codigo, modelos). DB = source of truth para estado, metadados, relacoes, tracking.

**Schema core**: `platforms`, `epics`, `decisions`, `elements`, `element_relationships`, `tags`, `pipeline_runs`, `events`.

**O que muda**:
- Skills passam a fazer INSERT/UPDATE no Supabase ao criar/avancar artefatos
- Portal le metadata do Supabase (queries SQL) em vez de filesystem scan
- Cross-references (epic ↔ ADR ↔ element) via tabela `tags` — impact analysis real
- Pipeline runs trackados com tokens, custo, duracao
- Events append-only para auditoria e analytics

**O que NAO muda**:
- Vision, pitch, spec, plan prose continuam em Git (markdown)
- LikeC4 model files continuam em Git (.likec4)
- Templates e Copier continuam em Git

**Implementacao incremental** (6 fases):
1. Schema Supabase + `platform.py sync-to-db`
2. Skills SpecKit escrevem no DB
3. `vision-build.py` popula element_graph do LikeC4
4. Portal le metadata do Supabase
5. Cross-references via `tags`
6. Events log + agent run tracking

**Por que Supabase**: ja usamos para Fulano, ja pagamos, experiencia do time, pgvector, real-time, REST auto-gerado.

---

### SpecKit Improvements

Analise comparativa detalhada em `docs/melhorias_base_GSD_BMAD.md`. 6 gaps identificados vs GSD e BMAD:

| Prioridade | Melhoria | Skill proposta | Problema que resolve |
|------------|----------|----------------|---------------------|
| **P1** | Context Rot | `speckit.execute-wave` | Tasks degradam com context window cheio — execucao em waves com subagents frescos |
| **P1** | Codebase Mapping | `speckit.map` | Plan nao conhece o codigo existente (brownfield) — agents paralelos mapeiam stack/patterns/convencoes |
| **P1** | Verify post-impl | `speckit.verify` | Sem verificacao se implementacao cobre a spec — compara spec vs codigo, detecta phantom completions |
| **P2** | State entre sessoes | `speckit.checkpoint` | Contexto perdido entre sessoes — STATE.md com decisoes, blockers, proximos passos |
| **P2** | Discuss phase | `speckit.discuss` | Preferencias de implementacao nao capturadas — gray areas antes do plan |
| **P3** | Research paralelo | Melhoria no `speckit.plan` | Research sequencial consome contexto — subagents paralelos (stack, patterns, pitfalls, libs) |

### Namespace Unification

Merge `speckit.*` em `madruga.*` para namespace unico. As 9 skills de especificacao passam a ser `madruga.specify`, `madruga.plan`, etc. As 4 skills de arquitetura mantem os nomes atuais.

### Architecture Feedback Loop: RECONCILE

Apos implementacao, fechar o loop entre codigo e arquitetura. Design decisions:

**Trigger**: Epic com phase=`review_done`, `platform_id` preenchido.

**3 safety gates**:
1. **Skip**: `platform_id` vazio → reconcile_done direto
2. **Threshold**: `drift_score < 0.3` → auto-apply updates na Vision
3. **1-way door**: Mudanca estrutural → escala humano (nunca auto-apply)

**Logica**:
1. Le diff do PR via `gh api`
2. Compara diff vs arquitetura (LikeC4 model, engineering docs)
3. Calcula `drift_score` (0.0 = aligned, 1.0 = drifted)
4. Se drift < threshold e nao 1-way door → auto-update Vision artifacts
5. Se drift >= threshold → escala humano com proposta de mudanca
6. Registra em changelog
7. Atualiza status no roadmap

**Token budget**: max 50K tokens no prompt. Diff truncado a 30K. ADRs filtrados por relevancia (so os referenciados no epic `arch.modules`).

**Error handling**: Falha → warning + reconcile_done com error flag. NAO bloqueia epico.

**Git Worktree**: Criado na fase `implement` no **target repo** (ex: `fulano-api`), NAO no madruga.ai.

### Vision Context Injection

Cada fase do pipeline recebe contexto da Vision proporcional a sua necessidade:

| Fase | Contexto injetado |
|------|-------------------|
| `specify` | vision_brief + context_map + pitch.md |
| `plan` | context_map + modelo_dominio + ADRs relevantes + spec.md |
| `implement` | ADRs + containers (NFRs) + tasks.md |
| `reconcile` | todos (diff node-by-node) |

ADRs sao filtrados lazy: so carrega os referenciados no frontmatter `arch.modules` do epic.

### Roadmap Auto-Sync

Roadmap.md gerado automaticamente do frontmatter dos epicos (status, phase, priority). O epic frontmatter e a source of truth — o markdown e view layer.

### CI/CD

- Lint Python (ruff)
- Portal build (`npm run build`)
- Template tests (`pytest .specify/templates/platform/tests/`)
- Platform lint (`python3 .specify/scripts/platform.py lint --all`)

### Daemon (ja construido, falta migrar)

O daemon **ja existe** em `services/madruga-ai/` — nao e conceito futuro. `MadrugaDaemon` roda 24/7 como systemd service, monitora Obsidian kanban, e auto-executa o pipeline. Apos a consolidacao (Etapa 1-6 acima), o daemon opera diretamente no madruga.ai.

Capacidades existentes:
- Poll Obsidian kanban a cada 60s (`kanban_poll.py`)
- Orchestrator com max_slots configuravel (`orchestrator.py`)
- Circuit breaker + retry com backoff (`api/circuit_breaker.py`)
- Decision gates: 1-way door → park epic, 2-way door → auto-decide (`decisions/`)
- WhatsApp notifications em gates criticos (`integrations/messaging/`)
- Dashboard web com status em tempo real (`dashboard/`)
- PID file + graceful shutdown (`deploy/madruga-ai.service`)

---

## Validacao End-to-End

### Camada 1 — Documentacao (funciona hoje)

```bash
# 1. Scaffoldar nova plataforma
python3 .specify/scripts/platform.py new teste

# 2. Editar modelo LikeC4
cd platforms/teste/model && likec4 serve

# 3. Gerar markdown tables do modelo
python3 .specify/scripts/vision-build.py teste

# 4. Validar estrutura
python3 .specify/scripts/platform.py lint teste

# 5. Criar epic (manual)
mkdir -p platforms/teste/epics/001-feature && touch platforms/teste/epics/001-feature/pitch.md

# 6. Pipeline SpecKit (interativo)
# /speckit.specify → /speckit.plan → /speckit.tasks → /speckit.analyze

# 7. Build portal com nova plataforma
cd portal && npm run build
```

### Camada 2 — Runtime Engine (apos consolidacao)

```bash
# 8. Instalar dependencias do engine
pip install -r requirements.txt

# 9. Rodar testes
pytest  # 51 testes devem passar

# 10. Registrar epics no SQLite
python3 -m src.cli epic register --platform fulano

# 11. Pipeline autonomo (single epic)
python3 -m src.cli pipeline --epic 001-channel-pipeline

# 12. Daemon 24/7
python3 -m src.cli daemon start  # ou: systemctl start madruga-ai

# 13. Dashboard
# http://localhost:8080 — status em tempo real
```
