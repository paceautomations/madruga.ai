# CLAUDE.md — madruga.ai

Docs e comentários em português brasileiro. Código em inglês.
Commits em PT-BR com prefixos: feat:, fix:, chore:, merge:.
Epics rodam em branch dedicada `epic/<platform>/<NNN-slug>` — merge via PR.
Numerar perguntas estruturadas (1, 2, 3…) para resposta por número.

## O que é

Sistema de documentação arquitetural para N plataformas digitais.
Template Copier compartilhado. Primeira plataforma: Fulano (WhatsApp agent, SMBs brasileiras).
Pipeline de 24 skills (L1 plataforma + L2 por epic): @.claude/knowledge/pipeline-dag-knowledge.md

## Onde encontrar

- Skills: `.claude/commands/madruga/` | Knowledge: `.claude/knowledge/`
- Plataformas: `platforms/<name>/` (business/, engineering/, decisions/, epics/, model/)
- Scripts: `.specify/scripts/` | Portal: `portal/`

## Comandos essenciais

`make test` | `make lint` | `make ruff` | `make seed`
`python3 .specify/scripts/platform.py list|status|use|lint <name>`
`/madruga:getting-started` (onboarding) | `/madruga:pipeline` (status)
Referência completa: @.claude/knowledge/commands.md

## Namespaces

- `madruga:*` — pipeline completo (L1 + L2 + utilities)
- `speckit.*` — ciclo L2: specify → clarify → plan → tasks → analyze → implement

## Convenções

- platform.yaml: manifest com repo binding, views, lifecycle stage
- `platform.py use <name>` define plataforma ativa — skills consultam quando sem argumento
- Cada `platforms/<name>/` tem CLAUDE.md próprio com contexto platform-specific (on-demand)
- ADRs: formato Nygard. Epics: Shape Up pitch. Planned epics vivem só no roadmap.md
- Repo binding: `platform.yaml` → `repo:` block. External repos em `{repos_base_dir}/{repo_org}/{repo_name}`
- Python: stdlib + pyyaml. SQLite WAL mode. Ruff para lint/format.
- Tech stack: Markdown skills + YAML frontmatter, Bash 5.x, Python 3.11+, LikeC4, Astro + Starlight

## Princípios

Pragmatismo > elegância. Automatizar na 3ª repetição. Bias for action. Usar Context7 para docs atualizadas.
Sempre apresentar trade-offs com prós/contras. Honestidade brutal — sem elogios vazios.
Prototipar primeiro, refinar depois. Ship imperfeito hoje > perfeito nunca.

## Hooks ativos

- PostToolUse em `platforms/**` → auto-registra no SQLite (hook_post_save.py)
- PostToolUse em `.claude/**/memory/**` → auto-sync memory (sync_memory.py)
- Git post-merge → auto-reseed DB se migrations mudaram
- Auto-simplify: após implementação tocando 3+ arquivos → rodar /simplify (skip one-liners/docs)

## Workflow enforcement

Plan mode → auto-review com subagent antes de apresentar. Prompt do subagent: "You are a staff engineer reviewing an implementation plan. Be harsh and direct. Check for: missed edge cases, over-engineering, simpler alternatives, security risks, missing error handling at boundaries, unrealistic assumptions. Output a bullet list of issues found (BLOCKER/WARNING/NIT) and an overall verdict."
LOC estimates: multiplicar por 1.5-2x (docstrings, argparse, logging não entram na base).
Scripts < 300 LOC: escrever completo + testes de uma vez (batch), sem incrementalismo vazio.

## Epic workflow

- **Planned epics** vivem só em `planning/roadmap.md` — sem arquivos criados
- **Active epics** (entrando L2) ganham `epics/NNN-slug/` com pitch.md, spec, plan, tasks
- `/madruga:epic-breakdown` para candidatos no roadmap; `/madruga:epic-context` para iniciar

## Prerequisites

Node.js 20+ | Python 3.11+ | `likec4` CLI (`npm i -g likec4`) | `copier` >= 9.4.0

## Compact instructions

Preservar no compact: arquivos modificados, estado dos testes, epic/task ativa,
decisões arquiteturais da sessão, hipóteses de debug em andamento.

Editar sources .likec4, rodar vision-build.py para regenerar AUTO markers.
Adicionar platformLoaders em LikeC4Diagram.tsx ao criar plataforma.
Epic branches obrigatórias para L2. Commitar em main só via PR.
