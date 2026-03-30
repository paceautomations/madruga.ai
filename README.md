# madruga.ai

Sistema de documentacao arquitetural e pipeline spec-to-code para plataformas digitais. Documenta o **que** um sistema faz, **por que** as decisoes foram tomadas, e **como** as pecas se conectam — tudo versionado no git, consumivel por humanos e LLMs.

Suporta **N plataformas** a partir de um template Copier compartilhado. Cada plataforma recebe a mesma estrutura de documentacao, integracao com portal e pipeline LikeC4. A primeira plataforma e **Fulano** — agentes WhatsApp para PMEs brasileiras.

---

## Quick Start

```bash
# Pre-requisitos: Node.js 20+, Python 3.11+, likec4, copier
npm i -g likec4
pip install copier pyyaml

# Onboarding interativo (detecta plataformas, explica pipeline, sugere proximo passo)
/getting-started

# Ou direto: criar plataforma + ver status
/platform-new meu-saas
/pipeline meu-saas

# Portal (visualizacao de todas as plataformas)
cd portal && npm install && npm run dev
# Abra http://localhost:4321
```

---

## Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────────────┐
│                         madruga.ai                                  │
├─────────────┬──────────────┬──────────────┬─────────────────────────┤
│  20 Skills  │  Python/Bash │   SQLite DB  │   Portal Astro          │
│  (Claude    │  Scripts     │  (.pipeline/ │   + Starlight            │
│   Code)     │  (.specify/) │   madruga.db)│   + LikeC4 React        │
├─────────────┴──────────────┴──────────────┴─────────────────────────┤
│                     platforms/<name>/                                │
│  platform.yaml │ business/ │ engineering/ │ decisions/ │ epics/      │
│                │ research/ │ model/       │ planning/                │
└─────────────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

1. **Skills** (Claude Code slash commands) geram artefatos markdown + LikeC4
2. **post_save.py** registra cada artefato no SQLite (hash, proveniencia, timestamp)
3. **vision-build.py** exporta modelos LikeC4 → tabelas markdown (marcadores `<!-- AUTO -->`)
4. **Portal** descobre plataformas automaticamente via `platform.yaml` e renderiza tudo
5. **check-platform-prerequisites.sh** valida dependencias antes de cada skill rodar

---

## Pipeline Completo — Da Ideia ao Codigo em Producao

O pipeline e um fluxo continuo de **24 skills** que leva uma plataforma da concepcao ate codigo implementado e testado. Dividido em 2 niveis (L1 = plataforma, L2 = por epic), onde L1 produz a fundacao arquitetural e L2 implementa cada feature.

### Diagrama End-to-End

```
═══════════════════════════════════════════════════════════════════════════════
 L1 — PIPELINE DE PLATAFORMA (13 nodes, roda 1x por plataforma)
═══════════════════════════════════════════════════════════════════════════════

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
                                                   │
═══════════════════════════════════════════════════════════════════════════════
 L2 — CICLO POR EPIC (11 nodes, repete para CADA epic do roadmap)
 Branch obrigatoria: epic/<platform>/<NNN-slug>
═══════════════════════════════════════════════════════════════════════════════
                                                   │
                                            epic-context ←── cria branch
                                                   │
                                            specify (spec.md)
                                                   │
                                            clarify (refina spec)
                                                   │
                                            plan (plan.md)
                                                   │
                                            tasks (tasks.md)
                                                   │
                                            analyze (pre-impl check)
                                                   │
                                            implement (escreve codigo!)
                                                   │
                                            analyze (pos-impl check)
                                                   │
                                            verify (coverage score)
                                                   │
                                            qa (testing specialist)
                                                   │
                                            reconcile (sync docs ↔ codigo)
                                                   │
                                              PR → merge to main
                                                   │
                                          proximo epic ←──────┘
```

### L1 — Pipeline de Plataforma (13 nodes)

Roda **uma vez por plataforma** para construir toda a fundacao: negocio, pesquisa, arquitetura e planejamento.

| # | Skill (comando) | Artefato | Depende de | Camada | Gate |
|---|-----------------|----------|------------|--------|------|
| 1 | `/platform-new` | `platform.yaml` | — | Business | human |
| 2 | `/vision` | `business/vision.md` | platform-new | Business | human |
| 3 | `/solution-overview` | `business/solution-overview.md` | vision | Business | human |
| 4 | `/business-process` | `business/process.md` | solution-overview | Business | human |
| 5 | `/tech-research` | `research/tech-alternatives.md` | business-process | Research | 1-way-door |
| 6 | `/codebase-map` | `research/codebase-context.md` | vision | Research | auto (opcional) |
| 7 | `/adr` | `decisions/ADR-*.md` | tech-research | Engineering | 1-way-door |
| 8 | `/blueprint` | `engineering/blueprint.md` | adr | Engineering | human |
| 9 | `/domain-model` | `engineering/domain-model.md` + `model/ddd-contexts.likec4` | blueprint, business-process | Engineering | human |
| 10 | `/containers` | `engineering/containers.md` + `model/platform.likec4` | domain-model, blueprint | Engineering | human |
| 11 | `/context-map` | `engineering/context-map.md` | domain-model, containers | Engineering | human |
| 12 | `/epic-breakdown` | `epics/*/pitch.md` | domain-model, containers, context-map | Planning | 1-way-door |
| 13 | `/roadmap` | `planning/roadmap.md` | epic-breakdown | Planning | human |

### L2 — Ciclo por Epic (11 nodes)

Repete para **cada epic** definido no roadmap. Cada epic roda em branch dedicada `epic/<platform>/<NNN-slug>`. Aqui e onde o codigo e de fato escrito, testado e validado.

| # | Skill (comando) | Gate | Artefato / Acao | O que faz |
|---|-----------------|------|-----------------|-----------|
| 14 | `/epic-context` | human | `epics/<NNN>/context.md` | **Cria branch** `epic/<platform>/<NNN-slug>` + captura contexto de implementacao. Referencia blueprint, ADRs, domain model |
| 15 | `/speckit.specify` | human | `epics/<NNN>/spec.md` | Cria especificacao da feature a partir de descricao em linguagem natural |
| 16 | `/speckit.clarify` | human | Atualiza `spec.md` | Faz ate 5 perguntas para eliminar ambiguidades na spec |
| 17 | `/speckit.plan` | human | `epics/<NNN>/plan.md` | Gera artefatos de design tecnico (componentes, interfaces, fluxos) |
| 18 | `/speckit.tasks` | human | `epics/<NNN>/tasks.md` | Gera lista de tarefas ordenadas por dependencia com criterios de aceite |
| 19 | `/speckit.analyze` | auto | Report | Check de consistencia pre-impl: spec vs plan vs tasks alinhados? |
| 20 | `/speckit.implement` | auto | **Codigo!** | Executa TODAS as tasks do tasks.md — escreve codigo, testes, config |
| 21 | `/speckit.analyze` | auto | Report | Check de consistencia pos-impl: codigo implementa tudo do tasks? |
| 22 | `/verify` | auto-escalate | Coverage score | Verifica aderencia do codigo vs spec/tasks/arquitetura. Score numerico |
| 23 | `/qa` | human | QA report | Testing specialist — analise estatica, testes, code review, API, browser QA. **Heal loop**: corrige bugs encontrados automaticamente |
| 24 | `/reconcile` | human | Atualiza docs | Detecta drift entre implementacao e documentacao, propoe updates |

Apos reconcile: abrir **PR → code review → merge to main** → proximo epic.

**qa e obrigatorio** — sempre roda com camadas adaptativas (analise estatica, testes, code review, build, API, browser). Roda ANTES do reconcile porque o heal loop pode modificar codigo, criando novo drift.

### Branch Guard

Toda skill do ciclo L2 verifica `git branch --show-current`:
- Se em `main` → **ERRO HARD**. Nenhum trabalho de epic pode acontecer em main
- Se em `epic/*` → OK, procede
- Excecao: `/epic-context` e quem cria a branch

### Gates (tipos de aprovacao)

| Gate | Comportamento | Quando |
|------|--------------|--------|
| `human` | Sempre pausa. Apresenta resumo + scorecard. Espera aprovacao | Decisoes de negocio, arquitetura, planejamento |
| `1-way-door` | Sempre pausa. >=3 alternativas por decisao. Confirmacao EXPLICITA por decisao. Subagent adversarial review | Decisoes irreversiveis (tech stack, ADRs, epic scope) |
| `auto` | Procede automaticamente sem pausa | Checks automaticos, implementacao |
| `auto-escalate` | Auto se OK, escala para humano se encontrar blockers | Verificacao pos-impl |

### Personas por Camada

| Camada | Comportamento da IA |
|--------|---------------------|
| Business | Reduzir escopo. "Isso e essencial pro v1?" Quantificar tudo. Marcar `[VALIDAR]` sem evidencia |
| Research | Default: `[DADOS INSUFICIENTES]`. Toda afirmacao factual precisa de URL. Sem URL → `[FONTE NAO VERIFICADA]` |
| Engineering | "Qual a coisa mais simples que funciona?" Menos componentes, menos abstracoes. Stdlib > biblioteca |
| Planning | Cortar escopo. Appetite default: 2 semanas. Se precisa mais, dividir. Sequenciar por risco |

---

## Contrato Uniforme das Skills (6 Passos)

Toda skill (L1 e L2) segue este contrato:

### Passo 0: Pre-requisitos

```bash
# L1: verifica se artefatos dos nodes predecessores existem
.specify/scripts/bash/check-platform-prerequisites.sh \
  --json --platform <nome> --skill <node-id>

# L2: verifica pre-requisitos do ciclo de epic
.specify/scripts/bash/check-platform-prerequisites.sh \
  --json --platform <nome> --epic <NNN-slug> --skill <node-id>
```

- Se `ready: false` → ERRO com lista de dependencias faltantes e qual skill gera cada uma
- Se `ready: true` → le todos os artefatos disponiveis
- Le `.specify/memory/constitution.md` (principios do projeto)
- **Branch Guard (L2):** se em `main` → ERRO

### Passo 1: Coletar Contexto + Perguntas Estruturadas

Le artefatos das dependencias. Usa deep research (subagents, Context7, web). Apresenta perguntas em 4 categorias:

| Categoria | Pattern |
|-----------|---------|
| **Premissas** | "Assumo que [X]. Correto?" |
| **Trade-offs** | "[A] mais simples ou [B] mais robusto?" |
| **Gaps** | "Nao encontrei info sobre [X]. Voce define ou devo pesquisar?" |
| **Provocacao** | "[Y] e o padrao, mas [Z] pode ser melhor porque [motivo]." |

Apresenta alternativas (>=2 opcoes com pros/cons para cada decisao). **Espera respostas ANTES de gerar.**

### Passo 2: Gerar Artefato (ou Codigo)

- Segue template se existir (spec-template.md, plan-template.md, tasks-template.md)
- Inclui alternativas consideradas
- Marca `[VALIDAR]` onde nao ha dados
- PT-BR para prosa, EN para codigo
- No `/speckit.implement`: executa tasks uma a uma, escrevendo codigo real

### Passo 3: Auto-Review (3 tiers)

| Tier | Quando | O que faz |
|------|--------|-----------|
| **Tier 1** | Gates `auto` | Checks deterministicos: arquivo existe, line count, secoes obrigatorias, sem placeholders, HANDOFF presente |
| **Tier 2** | Gates `human` | Tier 1 + scorecard: decisoes tem >=2 alternativas? Premissas marcadas? Trade-offs explicitos? Best practices pesquisadas? |
| **Tier 3** | Gates `1-way-door` | Tier 1 + Tier 2 + **subagent adversarial** (staff engineer review: alternativas faltando? premissas escondidas? scope creep? abordagem mais simples?) |

### Passo 4: Gate de Aprovacao

Conforme tipo do gate (ver tabela acima). Skills `1-way-door` listam cada decisao irreversivel com >=3 alternativas e pedem confirmacao explicita.

### Passo 5: Save + Report + SQLite

Salva o artefato e registra no banco de dados:

```bash
# L1 (DAG de plataforma):
python3 .specify/scripts/post_save.py \
  --platform <nome> --node <node-id> --skill <skill-id> \
  --artifact <path-relativo>

# L2 (ciclo de epic):
python3 .specify/scripts/post_save.py \
  --platform <nome> --epic <epic-id> \
  --node <node-id> --skill <skill-id> \
  --artifact <path-relativo>
```

O que o post_save.py faz internamente:
1. Calcula SHA-256 hash do artefato
2. Atualiza `pipeline_nodes` (L1) ou `epic_nodes` (L2) com status `done`
3. Registra em `artifact_provenance` (quem gerou o arquivo)
4. Insere evento no audit log (`events`)

Append HANDOFF block no final do artefato:

```yaml
---
handoff:
  from: <esta-skill>
  to: <proxima-skill>
  context: "Contexto para a proxima skill"
  blockers: []
```

Report: arquivo, line count, checks, proximo passo sugerido.

### Skills Utilitarias (fora do pipeline)

| Skill | Proposito |
|-------|-----------|
| `/pipeline` | Mostra status do DAG (L1 + L2) com tabela, Mermaid, % progresso, proximo passo |
| `/checkpoint` | Salva STATE.md com progresso da sessao atual |
| `/getting-started` | Onboarding interativo — detecta plataformas, explica pipeline, recomenda proximo passo |
| `/speckit.checklist` | Gera checklist customizado para a feature |
| `/speckit.constitution` | Cria/atualiza constituicao do projeto |
| `/speckit.taskstoissues` | Converte tasks em GitHub Issues ordenadas por dependencia |

---

## Banco de Dados SQLite

Estado do pipeline persiste em `.pipeline/madruga.db` (SQLite WAL mode, FK ON, busy_timeout 5000ms).

### Schema (11 tabelas + 2 FTS5 virtual)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    platforms      │────<│  pipeline_nodes   │     │     epics        │
│──────────────────│     │──────────────────│     │──────────────────│
│ platform_id (PK) │     │ platform_id (FK) │     │ platform_id (FK) │
│ name             │     │ node_id          │     │ epic_id          │
│ title            │     │ status           │     │ title            │
│ lifecycle        │     │ output_hash      │     │ status           │
│ repo_path        │     │ input_hashes     │     │ appetite         │
│ metadata (JSON)  │     │ output_files     │     │ priority         │
│ created_at       │     │ completed_at     │     │ branch_name      │
│ updated_at       │     │ completed_by     │     │ file_path        │
└──────────────────┘     │ line_count       │     └────────┬─────────┘
                         └──────────────────┘              │
                                                           │
┌──────────────────┐     ┌──────────────────┐     ┌───────┴──────────┐
│    decisions      │     │artifact_provenance│    │   epic_nodes     │
│──────────────────│     │──────────────────│     │──────────────────│
│ decision_id (PK) │     │ platform_id (FK) │     │ platform_id (FK) │
│ platform_id (FK) │     │ file_path        │     │ epic_id (FK)     │
│ epic_id          │     │ generated_by     │     │ node_id          │
│ skill            │     │ epic_id          │     │ status           │
│ title            │     │ output_hash      │     │ output_hash      │
│ number           │     │ generated_at     │     │ completed_at     │
│ status           │     └──────────────────┘     │ completed_by     │
│ superseded_by    │                               └──────────────────┘
│ file_path        │
│ content_hash     │     ┌──────────────────┐
│ decision_type    │     │ decision_links   │
│ context          │     │──────────────────│
│ consequences     │     │ from_decision_id │
│ tags_json        │     │ to_decision_id   │
│ decisions_json   │     │ link_type        │
│ assumptions_json │     └──────────────────┘
│ open_questions   │
└──────────────────┘     ┌──────────────────┐
                         │ memory_entries   │
┌──────────────────┐     │──────────────────│
│  pipeline_runs   │     │ memory_id (PK)   │
│──────────────────│     │ platform_id (FK) │
│ run_id (PK)      │     │ type             │
│ ...              │     │ name             │
└──────────────────┘     │ description      │
                         │ content          │
┌──────────────────┐     │ source           │
│     events       │     │ file_path        │
│──────────────────│     │ content_hash     │
│ event_id (PK)    │     └──────────────────┘
                         │ platform_id (FK) │     │ platform_id (FK) │
                         │ epic_id          │     │ entity_type      │
                         │ node_id          │     │ entity_id        │
                         │ status           │     │ action           │
                         │ agent            │     │ actor            │
                         │ tokens_in/out    │     │ payload (JSON)   │
                         │ cost_usd         │     │ created_at       │
                         │ duration_ms      │     └──────────────────┘
                         │ error            │
                         └──────────────────┘

_migrations (controle de versao do schema)
```

### O que cada tabela armazena

| Tabela | Proposito | Quem escreve |
|--------|-----------|-------------|
| `platforms` | Registro de cada plataforma (nome, lifecycle, metadata) | `post_save.py --reseed`, `platform.py new` |
| `pipeline_nodes` | **DAG Level 1** — status de cada node do pipeline (pending/done/stale/blocked/skipped) + hash do output | `post_save.py` apos cada skill |
| `epics` | Registro de epics (status, appetite, branch, priority) | `post_save.py --reseed`, `epic-context` |
| `epic_nodes` | **DAG Level 2** — status de cada step do ciclo de epic | `post_save.py --epic` |
| `decisions` | Registro de ADRs e decisoes — BD e source of truth, markdown e exportado | `insert_decision()`, `import_adr_from_markdown()` |
| `decision_links` | Grafo de relacionamentos entre decisoes (supersedes, depends_on, related, contradicts) | `insert_decision_link()` |
| `memory_entries` | Memoria persistente (user, feedback, project, reference) — BD e source of truth | `insert_memory()`, `sync_memory.py` |
| `decisions_fts` | FTS5 full-text search em decisoes (title, context, consequences) | Auto-sync via triggers |
| `memory_fts` | FTS5 full-text search em memory (name, description, content) | Auto-sync via triggers |
| `artifact_provenance` | Rastreabilidade — qual skill gerou qual arquivo, com hash | `post_save.py` |
| `pipeline_runs` | Tracking de execucoes (tokens, custo, duracao, erros) | skills (futuro) |
| `events` | Audit log append-only (quem fez o que, quando) | `post_save.py`, `seed_from_filesystem` |

### Status e Staleness

- **`get_platform_status()`** — retorna % de progresso (nodes done / total)
- **`get_stale_nodes()`** — detecta nodes cujas dependencias foram re-executadas depois deles (precisa re-rodar)
- **`seed_from_filesystem()`** — reconstroi estado do DB a partir dos arquivos existentes (idempotente)

### Migracao

Migrações ficam em `.pipeline/migrations/` (nomeadas `001_*.sql`, `002_*.sql`). `db.py:migrate()` aplica pendentes em ordem, com rollback em caso de falha. Tabela `_migrations` controla o que ja foi aplicado.

---

## Estrutura do Repositorio

```
├── .claude/
│   ├── commands/
│   │   ├── madruga/              # 20 skills: 13 L1 + 3 L2 + 4 utilities
│   │   │   ├── platform-new.md   #   Scaffold nova plataforma
│   │   │   ├── vision.md         #   Vision one-pager (Playing to Win)
│   │   │   ├── solution-overview.md
│   │   │   ├── business-process.md
│   │   │   ├── tech-research.md  #   Deep research + decision matrix
│   │   │   ├── codebase-map.md   #   Mapear codebase existente (opcional)
│   │   │   ├── adr.md            #   ADRs formato Nygard
│   │   │   ├── blueprint.md      #   Blueprint com NFRs + deploy topology
│   │   │   ├── domain-model.md   #   DDD bounded contexts + LikeC4
│   │   │   ├── containers.md     #   C4 Level 2 + LikeC4
│   │   │   ├── context-map.md    #   DDD context map
│   │   │   ├── epic-breakdown.md #   Shape Up pitches
│   │   │   ├── roadmap.md        #   Sequenciamento + MVP
│   │   │   ├── epic-context.md   #   Cria branch + contexto do epic
│   │   │   ├── verify.md         #   Verifica codigo vs spec (score)
│   │   │   ├── qa.md             #   QA via Playwright
│   │   │   ├── reconcile.md      #   Detecta drift docs vs codigo
│   │   │   ├── pipeline.md       #   Status do DAG (tabela + Mermaid)
│   │   │   ├── checkpoint.md     #   Salva STATE.md da sessao
│   │   │   └── getting-started.md#   Onboarding interativo
│   │   └── speckit.*.md          # 9 skills SpecKit
│   │       ├── speckit.specify.md
│   │       ├── speckit.clarify.md
│   │       ├── speckit.plan.md
│   │       ├── speckit.tasks.md
│   │       ├── speckit.analyze.md
│   │       ├── speckit.implement.md
│   │       ├── speckit.checklist.md
│   │       ├── speckit.constitution.md
│   │       └── speckit.taskstoissues.md
│   └── knowledge/                # Contratos e referencias
│       ├── pipeline-dag-knowledge.md     # Definicao canonica do DAG
│       ├── pipeline-contract-base.md     # Contrato uniforme (6 passos)
│       ├── pipeline-contract-business.md # Persona business
│       ├── pipeline-contract-engineering.md # Persona engineering
│       ├── pipeline-contract-planning.md # Persona planning
│       └── likec4-syntax.md              # Referencia LikeC4
│
├── .pipeline/                    # Estado SQLite + migrações
│   ├── madruga.db                # Banco (WAL mode)
│   └── migrations/
│       ├── 001_initial.sql       # 8 tabelas base + indexes
│       ├── 002_indexes_and_fixes.sql
│       └── 003_decisions_memory.sql  # decision_links, memory_entries, FTS5 + triggers
│
├── .specify/
│   ├── scripts/
│   │   ├── db.py                 # Thin wrapper SQLite (stdlib only)
│   │   ├── post_save.py          # CLI: registra artefato no DB
│   │   ├── vision-build.py       # LikeC4 JSON → tabelas markdown
│   │   ├── platform.py           # CLI: new, lint, sync, register, list, import/export-adrs/memory
│   │   ├── sync_memory.py       # Sync bidirecional memory ↔ BD
│   │   └── bash/
│   │       ├── check-platform-prerequisites.sh  # Valida dependencias
│   │       └── common.sh         # Funcoes compartilhadas
│   ├── templates/
│   │   ├── platform/             # Copier template para nova plataforma
│   │   │   ├── copier.yml        # Config + perguntas interativas
│   │   │   ├── template/         # Jinja2 files
│   │   │   └── tests/            # Validacao do template (pytest)
│   │   ├── spec-template.md      # Template SpecKit: especificacao
│   │   ├── plan-template.md      # Template SpecKit: plano
│   │   ├── tasks-template.md     # Template SpecKit: tasks
│   │   ├── checklist-template.md # Template SpecKit: checklist
│   │   ├── constitution-template.md
│   │   └── agent-file-template.md
│   ├── hooks/
│   │   └── post-merge            # Auto-reseed BD quando migrations mudam
│   └── memory/
│       └── constitution.md       # Principios do projeto (v1.1.0)
│
├── platforms/                    # N plataformas
│   └── <nome>/
│       ├── platform.yaml         # Manifesto (pipeline DAG, views, lifecycle)
│       ├── .copier-answers.yml   # Estado Copier (habilita copier update)
│       ├── business/
│       │   ├── vision.md         # Vision one-pager
│       │   ├── solution-overview.md
│       │   └── process.md        # Fluxos de negocio (Mermaid)
│       ├── engineering/
│       │   ├── blueprint.md      # NFRs, deploy topology, folder structure
│       │   ├── domain-model.md   # DDD: bounded contexts, aggregates
│       │   ├── containers.md     # C4 Level 2 containers
│       │   ├── context-map.md    # DDD context map
│       │   └── integrations.md   # Integracoes externas
│       ├── decisions/            # ADRs formato Nygard
│       │   └── ADR-NNN-slug.md
│       ├── research/
│       │   ├── tech-alternatives.md  # Decision matrix
│       │   └── codebase-context.md   # Mapa do codebase
│       ├── planning/
│       │   └── roadmap.md        # Sequenciamento + MVP
│       ├── epics/                # Shape Up pitches + SpecKit
│       │   └── NNN-slug/
│       │       ├── pitch.md      # Shape Up pitch
│       │       ├── spec.md       # SpecKit spec
│       │       ├── plan.md       # SpecKit plan
│       │       └── tasks.md      # SpecKit tasks
│       └── model/                # Diagramas LikeC4
│           ├── likec4.config.json
│           ├── spec.likec4       # Unico que synca via Copier
│           ├── ddd-contexts.likec4
│           ├── platform.likec4
│           ├── actors.likec4
│           ├── externals.likec4
│           ├── infrastructure.likec4
│           ├── relationships.likec4
│           └── views.likec4
│
├── portal/                       # Astro + Starlight + LikeC4 React
│   ├── astro.config.mjs          # Auto-descobre plataformas + symlinks
│   ├── src/lib/platforms.mjs     # Discovery via platform.yaml
│   └── src/components/viewers/
│       └── LikeC4Diagram.tsx     # React.lazy com imports por plataforma
│
└── docs/                         # Docs legados
```

---

## Comandos CLI

### Gestao de Plataformas (`platform.py`)

```bash
python3 .specify/scripts/platform.py list              # listar todas as plataformas
python3 .specify/scripts/platform.py new <nome>        # scaffold via Copier (interativo)
python3 .specify/scripts/platform.py lint <nome>        # validar estrutura
python3 .specify/scripts/platform.py lint --all         # validar todas
python3 .specify/scripts/platform.py sync [nome]        # copier update (uma ou todas)
python3 .specify/scripts/platform.py register <nome>    # injetar loader LikeC4 no portal
python3 .specify/scripts/platform.py import-adrs <nome> # importar ADRs markdown para BD
python3 .specify/scripts/platform.py export-adrs <nome> # exportar decisoes do BD para markdown
python3 .specify/scripts/platform.py import-memory      # importar .claude/memory/ para BD
python3 .specify/scripts/platform.py export-memory      # exportar memory entries para markdown
```

### Memory Sync (`sync_memory.py`)

```bash
python3 .specify/scripts/sync_memory.py                # sync bidirecional memory ↔ BD
python3 .specify/scripts/sync_memory.py --import-only  # filesystem → BD
python3 .specify/scripts/sync_memory.py --export-only  # BD → filesystem
python3 .specify/scripts/sync_memory.py --dry-run      # preview sem alteracoes
```

### Pipeline State (`post_save.py`)

```bash
# Registrar artefato (L1 — DAG de plataforma)
python3 .specify/scripts/post_save.py \
  --platform fulano --node vision --skill madruga:vision \
  --artifact business/vision.md

# Registrar artefato (L2 — ciclo de epic)
python3 .specify/scripts/post_save.py \
  --platform fulano --epic 001-channel-pipeline \
  --node specify --skill speckit.specify \
  --artifact epics/001-channel-pipeline/spec.md

# Re-seed plataforma a partir do filesystem
python3 .specify/scripts/post_save.py --reseed --platform fulano

# Re-seed todas as plataformas
python3 .specify/scripts/post_save.py --reseed-all
```

### Verificacao de Pre-requisitos

```bash
# Verificar dependencias de uma skill
.specify/scripts/bash/check-platform-prerequisites.sh \
  --json --platform fulano --skill domain-model

# Status completo do pipeline
.specify/scripts/bash/check-platform-prerequisites.sh \
  --json --platform fulano --status

# Status com dados do DB (hash, staleness)
.specify/scripts/bash/check-platform-prerequisites.sh \
  --json --platform fulano --status --use-db

# Verificar node do ciclo de epic
.specify/scripts/bash/check-platform-prerequisites.sh \
  --json --platform fulano --epic 001-onboarding --skill specify
```

### LikeC4 Build Pipeline (`vision-build.py`)

```bash
python3 .specify/scripts/vision-build.py fulano                  # exportar tudo
python3 .specify/scripts/vision-build.py fulano --validate-only  # apenas validar
python3 .specify/scripts/vision-build.py fulano --export-png     # tambem gerar PNGs
```

### Portal

```bash
cd portal
npm install          # instalar dependencias
npm run dev          # http://localhost:4321 (auto-descobre plataformas)
npm run build        # build de producao
```

### LikeC4 Standalone

```bash
cd platforms/<nome>/model
likec4 serve         # http://localhost:5173 (hot reload)
```

---

## Copier Template System

Novas plataformas sao criadas via Copier a partir de `.specify/templates/platform/`.

### Perguntas Interativas

| Campo | Descricao | Default |
|-------|-----------|---------|
| `platform_name` | Nome em kebab-case | (obrigatorio) |
| `platform_title` | Titulo legivel | Nome capitalizado |
| `platform_description` | Descricao em uma linha | "Plataforma {nome}" |
| `lifecycle` | Fase: design / development / production | design |
| `include_business_flow` | Incluir view de fluxo de negocio? | true |
| `register_portal` | Registrar no portal automaticamente? | true |

### Sync

```bash
# Sincronizar mudancas do template em plataformas existentes
python3 .specify/scripts/platform.py sync
# ou: copier update platforms/<nome>
```

Arquivos em `_skip_if_exists` (decisoes, epics, vision, etc.) nao sao sobrescritos. Apenas `model/spec.likec4` e arquivos estruturais sincronizam.

---

## Constituicao do Projeto

O arquivo `.specify/memory/constitution.md` (v1.1.0) define 9 principios:

1. **Pragmatismo** — "Funciona e entrega valor" > "elegante mas lento"
2. **Automacao** — Se fez 3x, vira script. Buscar APIs/MCPs antes de construir
3. **Conhecimento Estruturado** — Contextos atualizados, templates reutilizaveis
4. **Acao Rapida** — Prototipar primeiro, refinar depois
5. **Alternativas e Trade-offs** — Sempre apresentar opcoes com pros/cons
6. **Honestidade Brutal** — Sem elogios vazios. Apontar problemas cedo
7. **TDD** — Red-Green-Refactor para todo codigo
8. **Decisao Colaborativa** — Perguntar, nao assumir. Validar abordagem
9. **Observabilidade** — Logs estruturados JSON em todos os pontos criticos

---

## Namespaces de Comandos

| Namespace | Escopo | Exemplos |
|-----------|--------|----------|
| **`madruga:*`** | Pipeline de plataforma | `/vision`, `/adr`, `/pipeline`, `/getting-started` |
| **`speckit.*`** | Ciclo de implementacao (dentro de epic) | `/speckit.specify`, `/speckit.plan`, `/speckit.implement` |

---

## Tech Stack

| Componente | Tecnologia |
|-----------|-----------|
| Skills | Markdown (Claude Code custom commands) + YAML frontmatter |
| Scripts | Bash 5.x + Python 3.11+ (stdlib + pyyaml) |
| Estado | SQLite WAL em `.pipeline/madruga.db` |
| Modelos | LikeC4 (.likec4) |
| Portal | Astro + Starlight + LikeC4 React |
| Templates | Copier >= 9.4.0 |
| Formatacao | ruff (Python) |

## Pre-requisitos

- Node.js 20+
- Python 3.11+ com `pyyaml`
- `likec4` CLI: `npm i -g likec4`
- `copier` >= 9.4.0: `pip install copier`

---

## Referencia

Detalhes completos em [CLAUDE.md](CLAUDE.md).
