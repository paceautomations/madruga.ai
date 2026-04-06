# madruga.ai

Sistema de documentacao arquitetural e pipeline spec-to-code para plataformas digitais. Documenta o **que** um sistema faz, **por que** as decisoes foram tomadas, e **como** as pecas se conectam — tudo versionado no git, consumivel por humanos e LLMs.

Suporta **N plataformas** a partir de um template Copier compartilhado. Inclui orquestrador 24/7 (Easter), notificacoes Telegram para gates, observabilidade com tracing e evals, e um ciclo completo de 24 skills que leva uma ideia ate codigo implementado e testado. **12 epics shipped** (006-017), ~10.800 LOC de testes, 32 skills, 28 scripts Python.

---

## Quick Start

```bash
# Pre-requisitos: Node.js 20+, Python 3.11+, copier
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
┌──────────────────────────────────────────────────────────────────────────────┐
│                              madruga.ai                                       │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────────┤
│  32 Skills   │  28 Python   │   SQLite DB  │   Easter     │  Portal Astro    │
│  (Claude     │  Scripts     │  (.pipeline/ │  (FastAPI    │  + Starlight     │
│   Code)      │  (.specify/) │   madruga.db)│   24/7)      │  + Mermaid       │
├──────────────┴──────────────┴──────────────┴──────────────┴──────────────────┤
│                          platforms/<name>/                                     │
│  platform.yaml │ business/ │ engineering/ │ decisions/ │ epics/               │
│                │ research/ │ planning/                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

1. **Skills** (Claude Code slash commands) geram artefatos markdown com Mermaid inline
2. **post_save.py** registra cada artefato no SQLite (hash, proveniencia, timestamp)
3. **Portal** descobre plataformas automaticamente via `platform.yaml` e renderiza tudo
5. **check-platform-prerequisites.sh** valida dependencias antes de cada skill rodar
6. **easter.py** orquestra pipeline 24/7 — poll epics ativos, dispatch via `claude -p`, notifica gates via Telegram
7. **eval_scorer.py** calcula scores heuristicos em 4 dimensoes (quality, adherence, completeness, cost_efficiency)
8. **Telegram Bot** notifica gates pendentes com inline keyboard para approve/reject

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
                                            judge (4-persona review)
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
| 9 | `/domain-model` | `engineering/domain-model.md` | blueprint, business-process | Engineering | human |
| 10 | `/containers` | `engineering/containers.md` | domain-model, blueprint | Engineering | human |
| 11 | `/context-map` | `engineering/context-map.md` | domain-model, containers | Engineering | human |
| 12 | `/epic-breakdown` | `epics/*/pitch.md` | domain-model, containers, context-map | Planning | 1-way-door |
| 13 | `/roadmap` | `planning/roadmap.md` | epic-breakdown | Planning | human |

### L2 — Ciclo por Epic (11 nodes)

Repete para **cada epic** definido no roadmap. Cada epic roda em branch dedicada `epic/<platform>/<NNN-slug>`. Aqui e onde o codigo e de fato escrito, testado e validado.

| # | Skill (comando) | Gate | Artefato / Acao | O que faz |
|---|-----------------|------|-----------------|-----------|
| 14 | `/epic-context` | human | `epics/<NNN>/pitch.md` | **Cria branch** `epic/<platform>/<NNN-slug>` + enriquece pitch.md com decisoes de implementacao. Suporta `--draft` para planejar em main sem criar branch |
| 15 | `/speckit.specify` | human | `epics/<NNN>/spec.md` | Cria especificacao da feature a partir de descricao em linguagem natural |
| 16 | `/speckit.clarify` | human | Atualiza `spec.md` | Faz ate 5 perguntas para eliminar ambiguidades na spec |
| 17 | `/speckit.plan` | human | `epics/<NNN>/plan.md` | Gera artefatos de design tecnico (componentes, interfaces, fluxos) |
| 18 | `/speckit.tasks` | human | `epics/<NNN>/tasks.md` | Gera lista de tarefas ordenadas por dependencia com criterios de aceite |
| 19 | `/speckit.analyze` | auto | Report | Check de consistencia pre-impl: spec vs plan vs tasks alinhados? |
| 20 | `/speckit.implement` | auto | **Codigo!** | Executa TODAS as tasks do tasks.md — escreve codigo, testes, config |
| 21 | `/speckit.analyze` | auto | Report | Check de consistencia pos-impl: codigo implementa tudo do tasks? |
| 22 | `/judge` | auto-escalate | Judge report | Tech-reviewers: 4 personas paralelas (Arch Reviewer, Bug Hunter, Simplifier, Stress Tester) + Judge pass com decision classifier |
| 23 | `/qa` | human | QA report | Testing specialist — analise estatica, testes, code review, build, API, browser QA. **Heal loop**: corrige bugs encontrados automaticamente |
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
| `auto-escalate` | Auto se OK, escala para humano se encontrar blockers | Judge review pos-impl |

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
| `/skills-mgmt` | Gerencia ciclo de vida de skills — create, edit, lint, audit, dedup |
| `/quick-fix` | Fast lane L2 para bug fixes e mudancas pequenas — specify → implement → judge (pula plan, tasks, analyze, qa, reconcile) |
| `/verify` | `[DEPRECATED]` → Redireciona para `/judge` |
| `/speckit.checklist` | Gera checklist customizado para a feature |
| `/speckit.constitution` | Cria/atualiza constituicao do projeto |
| `/speckit.taskstoissues` | Converte tasks em GitHub Issues ordenadas por dependencia |

---

## Banco de Dados SQLite

Estado do pipeline persiste em `.pipeline/madruga.db` (SQLite WAL mode, FK ON, busy_timeout 5000ms).

### Schema (13 tabelas + 2 FTS5 virtual)

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
│ platform_id (FK) │     │ name             │
│ epic_id          │     │ description      │
│ node_id          │     │ content          │
│ status           │     │ source           │
│ agent            │     │ file_path        │
│ tokens_in        │     │ content_hash     │
│ tokens_out       │     └──────────────────┘
│ cost_usd         │
│ duration_ms      │     ┌──────────────────┐
│ trace_id         │     │     traces       │
│ error            │     │──────────────────│
└──────────────────┘     │ trace_id (PK)    │
                         │ platform_id (FK) │
┌──────────────────┐     │ epic_id          │
│     events       │     │ run_id           │
│──────────────────│     │ status           │
│ event_id (PK)    │     │ started_at       │
│ platform_id (FK) │     │ completed_at     │
│ epic_id          │     │ metadata (JSON)  │
│ node_id          │     └──────────────────┘
│ entity_type      │
│ entity_id        │     ┌──────────────────┐
│ action           │     │   eval_scores    │
│ actor            │     │──────────────────│
│ payload (JSON)   │     │ score_id (PK)    │
│ created_at       │     │ trace_id (FK)    │
└──────────────────┘     │ platform_id (FK) │
                         │ dimension        │
                         │ score            │
                         │ metadata (JSON)  │
                         │ created_at       │
                         └──────────────────┘

_migrations (controle de versao do schema)
```

### O que cada tabela armazena

| Tabela | Proposito | Quem escreve |
|--------|-----------|-------------|
| `platforms` | Registro de cada plataforma (nome, lifecycle, metadata, repo binding, tags) | `post_save.py --reseed`, `platform_cli.py new` |
| `local_config` | Configuracao local da maquina (active_platform, repos_base_dir) — nao commitado | `platform_cli.py use` |
| `pipeline_nodes` | **DAG Level 1** — status de cada node do pipeline (pending/done/stale/blocked/skipped) + hash do output | `post_save.py` apos cada skill |
| `epics` | Registro de epics (status, appetite, branch, priority) | `post_save.py --reseed`, `epic-context` |
| `epic_nodes` | **DAG Level 2** — status de cada step do ciclo de epic | `post_save.py --epic` |
| `decisions` | Registro de ADRs e decisoes — BD e source of truth, markdown e exportado | `insert_decision()`, `import_adr_from_markdown()` |
| `decision_links` | Grafo de relacionamentos entre decisoes (supersedes, depends_on, related, contradicts) | `insert_decision_link()` |
| `memory_entries` | Memoria persistente (user, feedback, project, reference) — BD e source of truth | `insert_memory()`, `sync_memory.py` |
| `decisions_fts` | FTS5 full-text search em decisoes (title, context, consequences) | Auto-sync via triggers |
| `memory_fts` | FTS5 full-text search em memory (name, description, content) | Auto-sync via triggers |
| `artifact_provenance` | Rastreabilidade — qual skill gerou qual arquivo, com hash | `post_save.py` |
| `pipeline_runs` | Tracking de execucoes — tokens, custo USD, duracao, erros, trace_id | `dag_executor.py`, `easter.py` |
| `traces` | Tracing hierarquico por pipeline run (trace → spans) | `dag_executor.py`, `db_observability.py` |
| `eval_scores` | Scores heuristicos em 4 dimensoes (quality, adherence_to_spec, completeness, cost_efficiency) | `eval_scorer.py` |
| `events` | Audit log append-only (quem fez o que, quando) | `post_save.py`, `seed_from_filesystem` |

### Status e Staleness

- **`get_platform_status()`** — retorna % de progresso (nodes done / total)
- **`get_stale_nodes()`** — detecta nodes cujas dependencias foram re-executadas depois deles (precisa re-rodar)
- **`seed_from_filesystem()`** — reconstroi estado do DB a partir dos arquivos existentes (idempotente)

### Migracao

Migracoes ficam em `.pipeline/migrations/` (10 arquivos: `001_initial.sql` ate `010_observability.sql`). `db_core.py:migrate()` aplica pendentes em ordem, com rollback em caso de falha. Tabela `_migrations` controla o que ja foi aplicado.

---

## Estrutura do Repositorio

```
├── .claude/
│   ├── commands/
│   │   ├── madruga/              # 23 skills: 13 L1 + 4 L2 + 6 utilities
│   │   │   ├── platform-new.md   #   Scaffold nova plataforma
│   │   │   ├── vision.md         #   Vision one-pager (Playing to Win)
│   │   │   ├── solution-overview.md
│   │   │   ├── business-process.md
│   │   │   ├── tech-research.md  #   Deep research + decision matrix
│   │   │   ├── codebase-map.md   #   Mapear codebase existente (opcional)
│   │   │   ├── adr.md            #   ADRs formato Nygard
│   │   │   ├── blueprint.md      #   Blueprint com NFRs + deploy topology
│   │   │   ├── domain-model.md   #   DDD bounded contexts + Mermaid
│   │   │   ├── containers.md     #   C4 Level 2 + Mermaid
│   │   │   ├── context-map.md    #   DDD context map
│   │   │   ├── epic-breakdown.md #   Shape Up pitches
│   │   │   ├── roadmap.md        #   Sequenciamento + MVP
│   │   │   ├── epic-context.md   #   Cria branch + enriquece pitch.md (suporta --draft)
│   │   │   ├── judge.md          #   Tech-reviewers: 4 personas + judge pass
│   │   │   ├── qa.md             #   QA adaptativo: static, tests, code review, browser
│   │   │   ├── reconcile.md      #   Detecta drift docs vs codigo
│   │   │   ├── quick-fix.md      #   Fast lane L2 (specify→implement→judge)
│   │   │   ├── skills-mgmt.md    #   Gerencia ciclo de vida de skills
│   │   │   ├── verify.md         #   [DEPRECATED] → judge
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
│   └── knowledge/                # Contratos, referencias e personas
│       ├── pipeline-dag-knowledge.md     # Definicao canonica do DAG
│       ├── pipeline-contract-base.md     # Contrato uniforme (6 passos)
│       ├── pipeline-contract-business.md # Persona business
│       ├── pipeline-contract-engineering.md # Persona engineering
│       ├── pipeline-contract-planning.md # Persona planning
│       ├── commands.md                   # Referencia completa de comandos
│       ├── decision-classifier-knowledge.md # Risk scoring para decisoes
│       ├── judge-config.yaml             # Config extensivel do Judge
│       ├── qa-template.md                # Template de QA report
│       └── personas/                     # Personas do Judge (4 tech-reviewers)
│           ├── arch-reviewer.md
│           ├── bug-hunter.md
│           ├── simplifier.md
│           └── stress-tester.md
│
├── .github/
│   ├── CODEOWNERS                # Review obrigatorio em .claude/, CLAUDE.md
│   ├── pull_request_template.md  # Template de PR (summary, security impact, test plan)
│   └── workflows/
│       └── ci.yml                # 6 jobs: lint, db-tests, smoke-test, templates, bash-tests, portal-build
│
├── .pipeline/                    # Estado SQLite + migracoes
│   ├── madruga.db                # Banco (WAL mode)
│   └── migrations/
│       ├── 001_initial.sql             # 8 tabelas base + indexes
│       ├── 002_indexes_and_fixes.sql
│       ├── 003a_decisions_memory.sql   # decision_links, memory_entries
│       ├── 003b_fts5.sql              # FTS5 virtual tables + triggers
│       ├── 004_decision_body.sql
│       ├── 005_platform_repo.sql      # repo binding
│       ├── 006_epic_delivered_at.sql
│       ├── 007_gate_fields.sql        # gate approval tracking
│       ├── 008_telegram_message_id.sql # Telegram integration
│       ├── 009_add_drafted_status.sql  # epic-context --draft mode
│       └── 010_observability.sql       # traces, eval_scores, pipeline_runs extensions
│
├── .specify/
│   ├── scripts/
│   │   ├── # --- Core DB ---
│   │   ├── db.py                 # Re-export facade (backward compat)
│   │   ├── db_core.py            # Connection, migration, transactions
│   │   ├── db_pipeline.py        # Pipeline CRUD (platforms, nodes, epics, runs)
│   │   ├── db_decisions.py       # Decisions, memory, FTS5
│   │   ├── db_observability.py   # Traces, spans, eval scores
│   │   ├── errors.py             # Error hierarchy (PipelineError, ConfigError, etc.)
│   │   ├── config.py             # Shared configuration
│   │   ├── log_utils.py          # Structured logging helpers
│   │   ├── # --- Pipeline ---
│   │   ├── dag_executor.py       # Custom DAG executor: topological sort, claude -p dispatch, gates, retry/circuit breaker
│   │   ├── post_save.py          # CLI: registra artefato no DB
│   │   ├── eval_scorer.py        # Heuristic eval scoring (4 dimensoes)
│   │   ├── observability_export.py # Export traces/spans/evals como CSV
│   │   ├── decision_classifier.py # Risk score para decisoes
│   │   ├── # --- Easter (24/7 orchestrator) ---
│   │   ├── easter.py             # FastAPI app: dag_scheduler + Telegram + health + observability API
│   │   ├── telegram_bot.py       # Bot Telegram standalone (aiogram 3.x)
│   │   ├── telegram_adapter.py   # Adapter para easter ↔ Telegram
│   │   ├── ntfy.py               # ntfy.sh fallback notifications
│   │   ├── sd_notify.py          # systemd watchdog integration
│   │   ├── # --- Tools ---
│   │   ├── platform_cli.py       # CLI: new, lint, sync, register, list, use, current, status, import/export, gate
│   │   ├── skill-lint.py         # Lint all skills (frontmatter, handoffs, archetype compliance)
│   │   ├── sync_memory.py        # Sync bidirecional memory ↔ BD
│   │   ├── memory_consolidate.py # Pruning e consolidacao de memories
│   │   ├── # --- Multi-repo ---
│   │   ├── ensure_repo.py        # Clone/pull repos externos (SSH/HTTPS)
│   │   ├── worktree.py           # Git worktree isolado para epics
│   │   ├── implement_remote.py   # claude -p em repo externo + PR via gh
│   │   ├── # --- Hooks ---
│   │   ├── hook_post_save.py     # PostToolUse: auto-registra em SQLite
│   │   ├── hook_skill_lint.py    # PostToolUse: auto skill-lint
│   │   ├── # --- Tests (29 arquivos, ~10.800 LOC) ---
│   │   └── tests/
│   │       └── test_*.py         # pytest (make test)
│   │   └── bash/
│   │       ├── check-platform-prerequisites.sh  # Valida dependencias
│   │       ├── check-prerequisites.sh
│   │       ├── common.sh         # Funcoes compartilhadas
│   │       ├── create-new-feature.sh
│   │       ├── setup-plan.sh
│   │       └── update-agent-context.sh
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
│       ├── platform.yaml         # Manifesto (pipeline DAG, views, lifecycle, repo binding)
│       ├── CLAUDE.md             # Contexto especifico da plataforma
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
│
├── portal/                       # Astro + Starlight + Mermaid (astro-mermaid)
│   ├── astro.config.mjs          # Auto-descobre plataformas + symlinks
│   ├── src/lib/platforms.mjs     # Discovery via platform.yaml
│   └── src/components/
│       ├── dashboard/
│       │   └── PipelineDAG.tsx       # Visualizacao do DAG pipeline
│       └── observability/
│           ├── ObservabilityDashboard.tsx  # Dashboard principal (4 tabs)
│           ├── RunsTab.tsx            # Pipeline runs com metricas
│           ├── TracesTab.tsx          # Tracing hierarquico
│           ├── EvalsTab.tsx           # Eval scores por dimensao
│           ├── CostTab.tsx            # Custo acumulado por skill/epic
│           └── formatters.ts          # Formatacao de dados
│
├── etc/
│   └── systemd/
│       └── madruga-easter.service    # Unit file systemd para Easter 24/7
│
├── CONTRIBUTING.md               # Regras de PR, commits, AI-generated code
├── SECURITY.md                   # Trust model, secret management, subprocess isolation
└── docs/                         # Docs de referencia
```

---

## Comandos CLI

### Gestao de Plataformas (`platform_cli.py`)

```bash
python3 .specify/scripts/platform_cli.py list              # listar todas (repo, tags, plataforma ativa)
python3 .specify/scripts/platform_cli.py new <nome>        # scaffold via Copier (interativo)
python3 .specify/scripts/platform_cli.py use <nome>        # definir plataforma ativa
python3 .specify/scripts/platform_cli.py current            # mostrar plataforma ativa
python3 .specify/scripts/platform_cli.py lint <nome>        # validar estrutura
python3 .specify/scripts/platform_cli.py lint --all         # validar todas
python3 .specify/scripts/platform_cli.py sync [nome]        # copier update (uma ou todas)
python3 .specify/scripts/platform_cli.py status <nome>      # pipeline status (tabela humana)
python3 .specify/scripts/platform_cli.py status --all --json # todas plataformas (JSON para dashboard)
python3 .specify/scripts/platform_cli.py import-adrs <nome> # importar ADRs markdown para BD
python3 .specify/scripts/platform_cli.py export-adrs <nome> # exportar decisoes do BD para markdown
python3 .specify/scripts/platform_cli.py import-memory      # importar .claude/memory/ para BD
python3 .specify/scripts/platform_cli.py export-memory      # exportar memory entries para markdown
python3 .specify/scripts/platform_cli.py gate list <nome>   # listar gates pendentes
python3 .specify/scripts/platform_cli.py gate approve <id>  # aprovar gate
```

### DAG Executor (`dag_executor.py`)

```bash
# Executar pipeline L1 (plataforma)
python3 .specify/scripts/dag_executor.py --platform <nome> --dry-run  # preview da ordem
python3 .specify/scripts/dag_executor.py --platform <nome>            # executar L1

# Executar pipeline L2 (epic)
python3 .specify/scripts/dag_executor.py --platform <nome> --epic <slug>

# Resume de checkpoint
python3 .specify/scripts/dag_executor.py --platform <nome> --resume
```

### Easter — Orquestrador 24/7 (`easter.py`)

```bash
# Iniciar localmente
python3 .specify/scripts/easter.py

# Via systemd
systemctl --user start madruga-easter
systemctl --user status madruga-easter
```

Endpoints HTTP:

| Endpoint | Descricao |
|----------|-----------|
| `GET /health` | Liveness check (sempre 200) |
| `GET /status` | Estado completo do Easter em JSON |
| `GET /api/traces` | Lista traces com paginacao |
| `GET /api/traces/{trace_id}` | Detalhe do trace com spans e evals |
| `GET /api/evals` | Eval scores com filtros |
| `GET /api/stats` | Stats agregados por dia |
| `GET /api/export/csv` | Export traces/spans/evals como CSV |

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

### Skill Lint (`skill-lint.py`)

```bash
python3 .specify/scripts/skill-lint.py                 # lint all skills
python3 .specify/scripts/skill-lint.py --skill <name>  # lint one skill
python3 .specify/scripts/skill-lint.py --json           # JSON output
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

### Portal

```bash
cd portal
npm install          # instalar dependencias
npm run dev          # http://localhost:4321 (auto-descobre plataformas)
npm run build        # build de producao
```

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
python3 .specify/scripts/platform_cli.py sync
# ou: copier update platforms/<nome>
```

Arquivos em `_skip_if_exists` (decisoes, epics, vision, etc.) nao sao sobrescritos. Apenas arquivos estruturais sincronizam.

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
| **`madruga:*`** | Pipeline de plataforma | `/vision`, `/adr`, `/judge`, `/pipeline`, `/getting-started` |
| **`speckit.*`** | Ciclo de implementacao (dentro de epic) | `/speckit.specify`, `/speckit.plan`, `/speckit.implement` |

---

## Tech Stack

| Componente | Tecnologia |
|-----------|-----------|
| Skills | Markdown (Claude Code custom commands) + YAML frontmatter |
| Scripts | Python 3.11+ (stdlib + pyyaml) + Bash 5.x |
| Estado | SQLite WAL em `.pipeline/madruga.db` (13 tabelas + 2 FTS5) |
| Diagramas | Mermaid (inline em .md, renderizado por astro-mermaid) |
| Portal | Astro + Starlight + Mermaid + observability dashboard |
| Easter | FastAPI + uvicorn + aiogram 3.x + structlog + Sentry |
| Notificacao | Telegram Bot API (aiogram) + ntfy.sh fallback |
| Templates | Copier >= 9.4.0 |
| CI | GitHub Actions (lint, db-tests, smoke-test, templates, bash-tests, portal-build) |
| Formatacao | ruff (Python) |
| Testes | pytest (29 arquivos, ~10.800 LOC) |

---

## Epics Shipped

| # | Epic | Descricao |
|---|------|-----------|
| 006 | SQLite Foundation | BD SQLite (WAL mode) como state store. db.py, migrations, CI, guardrails |
| 007 | Directory Unification | SpecKit opera em epics/. DAG dois niveis (L1+L2). platform.yaml como manifesto |
| 008 | Quality & DX | Knowledge files, skills enxutas, auto-review por tier, verify + QA + reconcile |
| 009 | Decision Log BD | BD como source of truth para decisions e memory. FTS5, CLI import/export |
| 010 | Pipeline Dashboard | Dashboard visual no portal Starlight. CLI status com tabela + JSON + Mermaid |
| 011 | CI/CD Pipeline | GitHub Actions: 6 jobs (lint, db-tests, smoke-test, templates, bash, portal) |
| 012 | Multi-repo Implement | git worktree para repos externos. ensure_repo, worktree isolado, implement_remote + PR |
| 013 | DAG Executor + Bridge | Custom DAG executor: Kahn's topological sort, claude -p dispatch, human gates, retry/circuit breaker |
| 014 | Telegram Notifications | Bot Telegram (aiogram 3.x): notifica human gates, inline keyboard approve/reject, backoff exponencial |
| 015 | Subagent Judge | Tech-reviewers: 4 personas paralelas + Judge pass. Decision Classifier (risk score). Substitui verify |
| 016 | Easter 24/7 | FastAPI + asyncio: dag_scheduler, Telegram gates, health_checker + systemd watchdog, Sentry |
| 017 | Observability & Evals | Traces hierarquicos, eval scoring (4 dimensoes), API REST, portal dashboard (4 tabs), cleanup 90 dias |

---

## Pre-requisitos

- Node.js 20+
- Python 3.11+ com `pyyaml`
- `copier` >= 9.4.0: `pip install copier`
- Para Easter: `pip install fastapi uvicorn aiogram structlog sentry-sdk`

---

## Referencia

Detalhes completos em [CLAUDE.md](CLAUDE.md). Regras de contribuicao em [CONTRIBUTING.md](CONTRIBUTING.md). Modelo de seguranca em [SECURITY.md](SECURITY.md).
