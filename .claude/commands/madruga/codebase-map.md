---
description: Map an existing codebase (brownfield) or declare greenfield — produces evidence-anchored architecture summary for downstream L1 skills
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Continue to Tech Research
    agent: madruga/tech-research
    prompt: "Codebase context generated. Continue with technology alternatives — for brownfield, treat existing stack as the default option in the decision matrix."
---

# Codebase Map — Brownfield Architecture Extraction

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md`.

Map an existing codebase against `platform.yaml:repo` binding (brownfield) or declare greenfield. Produces an evidence-anchored summary that downstream L1 skills (tech-research, adr, blueprint, domain-model, containers) consume to ground their decisions in real code.

**Optional DAG node** — if not executed, no downstream node is blocked. But if `platform.yaml` declares a `repo:` block that resolves to real code, this skill MUST run before tech-research/blueprint to avoid hallucinated architecture.

## Cardinal Rule: ZERO Unsourced Claims

Every statement about the codebase MUST cite a `path/to/file:line`. No evidence → mark `[VALIDAR]`, `[ESTIMAR]` (for guessed metrics), or remove the statement.

**NEVER:**
- Assert a pattern exists without a grep hit (cite the file:line)
- List a dependency without reading the manifest that declares it (cite the manifest)
- Invent metrics (LOC, file counts, contributor counts) without measuring (cite the command)
- Describe an integration without finding the actual SDK import or HTTP call site
- Skip `CLAUDE.md` / `AGENTS.md` / `README.md` if they exist — the team already encoded conventions there
- Read `node_modules/`, lock files, generated code, or build outputs (skip-list below)

## Persona

Code archaeologist — forensic, no opinion, refuses to speculate. Cites `path:line` on every claim. Reads `CLAUDE.md` / `AGENTS.md` / `README.md` first because the team has already done half the work. Knows `node_modules/`, `dist/`, `*.lock`, `*.snap`, `__snapshots__/`, `coverage/` are noise. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/madruga:codebase-map prosauai` — Map the codebase for platform "prosauai"
- `/madruga:codebase-map` — Prompt for the platform name

## Output Directory

Save to `platforms/<name>/research/codebase-context.md`.

## Instructions

### 1. Collect Context + Ask Questions

#### 1a. Resolve repo (Step 0 plumbing)

Beyond the contract-base prerequisites:

1. **Resolve local clone** via the canonical helper (NEVER reinvent):
   ```bash
   REPO_PATH=$(python3 .specify/scripts/ensure_repo.py <platform>)
   ```
   - Self-ref platforms (e.g., madruga.ai) → returns the repo root.
   - External platforms → clones (SSH→HTTPS fallback) under `~/repos/<org>/<name>` or fetches.
   - Exit code ≠ 0 OR `repo:` block missing → treat as **greenfield**, log warning, skip to §2 greenfield path.

2. **Capture repo context** (cited in §3 of artifact):
   ```bash
   git -C "$REPO_PATH" rev-parse --short HEAD          # head_sha
   git -C "$REPO_PATH" log -1 --format=%cI             # head_date (ISO)
   git -C "$REPO_PATH" rev-list --count HEAD            # total_commits
   git -C "$REPO_PATH" shortlog -sn --since='90 days ago' | wc -l  # contributors_90d
   git -C "$REPO_PATH" log --since='30 days ago' --oneline | wc -l # commits_30d
   ```

3. **Branch awareness**: `base_branch` from `python3 -c "import sys; sys.path.insert(0,'.specify/scripts'); from ensure_repo import load_repo_binding; print(load_repo_binding('<platform>')['base_branch'])"`. Default `main` if missing.

#### 1b. Pass 0 — Manifest sweep (sequential, ≤8 reads)

Read **only** these files if they exist (skip silently otherwise). This is the cheapest, highest-signal pass:

| Priority | File | Why |
|----------|------|-----|
| 1 | `package.json` | JS/TS stack, scripts, deps |
| 1 | `pyproject.toml` | Python stack, deps, runtime |
| 1 | `requirements.txt` | Python deps (legacy) |
| 1 | `go.mod` | Go module + version |
| 1 | `Cargo.toml` | Rust crate |
| 1 | `Gemfile` | Ruby |
| 1 | `composer.json` | PHP |
| 1 | `pom.xml` | Java/Maven |
| 2 | `CLAUDE.md` | Team-encoded conventions (read in full — gold) |
| 2 | `AGENTS.md` | Agent conventions (gold) |
| 2 | `README.md` | Project intent (read first 200 lines) |
| 2 | `.env.example` | Required env vars (lists secrets without values) |

Infer the **primary stack** strictly from these manifests. No inference without a manifest hit.

#### 1c. Pass 1 — Top-level walk (1 listing)

```bash
ls -F "$REPO_PATH"
```

Annotate which top-level dirs are framework-standard (`app/`, `src/`, `pages/`, `components/`, `services/`, `lib/`, `migrations/`, `supabase/`, `n8n_backend/`, `.github/workflows/`, `docker/`). Skip the rest until Pass 2 demands them.

#### 1d. Pass 2 — Fan-out (5 specialized subagents, single message)

Spawn 5 Agent (subagent_type=Explore) calls in **one message** with parallel tool blocks. Each receives the resolved `$REPO_PATH`, the **canonical skip-list**, an explicit budget, and a fixed YAML return format. Mechanical consolidation in §2.

**Canonical skip-list (shared across all 5 agents):**

```
node_modules/, .next/, .nuxt/, .turbo/, dist/, build/, out/, target/,
.venv/, venv/, __pycache__/, .git/, .pipeline/, .gradle/,
*.lock, package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, Cargo.lock,
coverage/, .nyc_output/, .expo/, .cache/, vendor/, third_party/,
*.snap, *.snapshot, fixtures/, __snapshots__/, generated/, .gen/,
*.min.js, *.min.css, *.map, dist-types/
```

**Agent budgets and returns:**

| Agent | Focus | Budget | Return (fixed YAML) |
|-------|-------|--------|---------------------|
| **A — Stack & Versions** | Manifests already loaded in Pass 0 + extract direct deps with versions + detect runtime (engines field, python_requires) | ≤3 file reads | `stack: {language, framework, runtime, db, build, test}` + `direct_deps: [{name, version, evidence}]` |
| **B — Structure & Entrypoints** | Annotated tree (3 levels), entrypoints (`scripts.start`, server file, `app/_layout.tsx`, `next.config.*`, `manage.py`, `main.py`), file count by extension (top 5) | ≤8 file reads + 2 grep | `tree: <text>` + `entrypoints: [{type, target, evidence}]` + `file_counts: [{ext, n}]` |
| **C — Data & Schemas** | `migrations/`, `*.sql`, `prisma/schema.prisma`, `models.py`, `*Schema.ts`, `supabase/migrations/`. Names of tables/entities only — no columns. | ≤6 file reads | `entities: [{name, file, type}]` |
| **D — Integrations & External Calls** | Grep for `axios`, `fetch(`, `httpx`, `requests.`, SDK imports (`@supabase/`, `stripe`, `aws-sdk`, `openai`, etc.). Read `.env.example` to map secrets. Webhook routes. | ≤4 file reads + 4 grep | `integrations: [{service, type, sdk, evidence}]` + `env_vars: [{name, file_line}]` |
| **E — CI/CD & Deploy** | `.github/workflows/*.yml`, `Dockerfile*`, `docker-compose*.yml`, `eas.json`, `vercel.json`, `app.json` (Expo), Terraform/Pulumi if present | ≤6 file reads | `pipelines: [{name, trigger, target, evidence}]` + `runtime_target: <env description>` |

Each agent **MUST** return its YAML block. Consolidation in §2 is mechanical — copy structures, merge sources.

#### 1e. Pass 3 — Structured Questions (numbered)

Per `pipeline-contract-base.md` Step 1. Number sequentially so the user can reply "1 — sim, 2 — opção B, 3 — você define". Categories: **Premissas / Trade-offs / Gaps / Provocação**.

Brownfield-typical examples:
1. **Premissa**: "Assumo que `n8n_backend/` orquestra workflows e o frontend Expo só consome via Supabase REST. Correto?"
2. **Gap**: "Não encontrei docs explícitas de auth — usa Supabase Auth puro ou tem camada própria?"
3. **Provocação**: "Detectei `services/` e `lib/` com responsabilidades sobrepostas. Existe convenção interna para a separação?"

Apply Pushback Protocol from contract-base. Use uncertainty markers `[VALIDAR]`, `[ESTIMAR]`, `[DEFINIR]`, `[FONTE?]`, `[RISCO: ...]`, `[DECISAO DO USUARIO]`.

### 2. Generate Codebase Context

#### 2a. Brownfield template (target 100–200 lines)

```markdown
---
title: "Codebase Context"
updated: <YYYY-MM-DD>
repo_sha: <head_sha curto>
repo_branch: <base_branch>
---
# <Nome> — Codebase Context

> Mapeamento brownfield gerado a partir de `<org/name>@<head_sha>`. Última atualização: <YYYY-MM-DD>.

---

## 1. Status

`[BROWNFIELD]` — <1 linha justificando com evidência: ex. "package.json:2 declara `expo` e `app/` segue Expo Router">.

---

## 2. Resumo Executivo

<3-5 linhas: o que faz, stack primário, escala (LOC/arquivos/idade), saúde (commits últimos 30d, contributors 90d). Cada número com evidência ou marcador `[ESTIMAR]`.>

---

## 3. Repo Context

| Campo | Valor | Evidência |
|-------|-------|-----------|
| Org/Name | <org>/<name> | platform.yaml:repo |
| Branch base | <base_branch> | platform.yaml:repo.base_branch |
| HEAD SHA | <head_sha> | git rev-parse --short HEAD |
| Último commit | <head_date> | git log -1 --format=%cI |
| Total commits | <N> | git rev-list --count HEAD |
| Contributors (90d) | <N> | git shortlog -sn --since=90.days |
| Commits (30d) | <N> | git log --since=30.days |

---

## 4. Stack & Versões

| Categoria | Tecnologia | Versão | Evidência |
|-----------|-----------|--------|-----------|
| Linguagem | <X> | <ver> | <manifest:line> |
| Framework | <X> | <ver> | <manifest:line> |
| Runtime | <X> | <ver> | <manifest:line> |
| DB | <X> | <ver> | <evidência> |
| Build | <X> | <ver> | <evidência> |
| Test runner | <X> | <ver> | <manifest:line> |

> Mínimo obrigatório: linguagem, framework, runtime, DB, build, test.

---

## 5. Folder Structure

Tree anotado (max 3 níveis), com propósito e LOC aproximado por dir top-level.

```text
<repo>/
├── <dir>/        # <propósito> (~<LOC> linhas, <N> arquivos)
├── ...
```

---

## 6. Entrypoints

| Tipo | Comando/Arquivo | Evidência |
|------|----------------|-----------|
| Dev start | <ex: `npm run start`> | <manifest:line> |
| Prod start | <comando> | <evidência> |
| App entry | <ex: app/_layout.tsx> | <file:line> |
| Build | <comando> | <manifest:line> |

---

## 7. Data Schemas

Entidades/tabelas detectadas (nomes apenas — colunas vão para `domain-model.md`).

| Entidade | Arquivo | Tipo |
|----------|---------|------|
| `<nome>` | <path:linha> | SQL migration / Prisma / Pydantic / TS interface |

> Se não houver schemas detectáveis: linha única "Sem schemas formais detectados — modelo emerge em `<dir>/`."

---

## 8. Integrações Externas

| Serviço | Tipo | SDK/Protocolo | Evidência |
|---------|------|---------------|-----------|
| <Supabase> | Auth+DB+Storage | @supabase/supabase-js | <file:linha> |
| <Stripe> | Payments | stripe | <file:linha> |

---

## 9. CI/CD & Deploy

| Pipeline | Trigger | Target | Evidência |
|----------|---------|--------|-----------|
| <nome> | <push/pr/cron> | <env> | <.github/workflows/X.yml> |

> Se sem CI: marcar "Sem CI configurado" e listar manifests de deploy local (`Dockerfile`, `docker-compose.yml`, scripts).

---

## 10. Env & Secrets

Variáveis declaradas em `.env.example` (lista, sem valores).

- `<NOME_VAR>` — `.env.example:linha` — <propósito inferido se óbvio>

> Se sem `.env.example`: marcar `[VALIDAR]` e listar greps de `process.env.` / `os.environ` / `os.getenv` mais frequentes.

---

## 11. Tests

| Aspecto | Valor | Evidência |
|---------|-------|-----------|
| Framework | <Jest/pytest/vitest/...> | <manifest:line> |
| Suites | <unit, integration, e2e> | <dirs detectados> |
| Coverage | <%> ou `[VALIDAR]` | <coverage/lcov.info ou similar> |

---

## 12. Decisões Pré-Existentes

Decisões já documentadas pelo time em `CLAUDE.md` / `AGENTS.md` / `docs/` — citações textuais curtas (≤2 linhas cada) com source. Ouro para `tech-research` e `adr`.

- "<citação>" — `<arquivo:linha>`
- ...

> Se sem CLAUDE.md/AGENTS.md/docs: deixar seção com "Sem decisões formais documentadas — projetar a partir da estrutura."

---

## 13. Hot Spots

Top 5 arquivos por LOC e top 5 por churn (commits últimos 90d). Indica candidatos a refactor / risco para epics futuros.

| Arquivo | LOC | Commits 90d | Sinal |
|---------|-----|-------------|-------|
| <path> | <N> | <N> | <churn alto / módulo central / lógica complexa> |

---

## 14. Observações

Riscos / débitos / oportunidades — cada bullet com referência `file:line`. Sem prescrever solução (isso é de ADR/blueprint).

- <observação> — `<arquivo:linha>`
- ...

---
handoff:
  from: codebase-map
  to: tech-research
  context: "Stack atual: <X>. <N> integrações externas. <M> decisões pré-existentes capturadas em CLAUDE.md/AGENTS.md."
  blockers: []
  confidence: <Alta|Média|Baixa>
  kill_criteria: "Repo migra para outra stack primária OU base_branch muda OU >50% dos arquivos mapeados são deletados"
```

#### 2b. Greenfield template (target 10–20 lines)

```markdown
---
title: "Codebase Context"
updated: <YYYY-MM-DD>
repo_sha: null
repo_branch: null
---
# <Nome> — Codebase Context

> `[GREENFIELD]` — sem codebase existente.

## 1. Status

`[GREENFIELD]` — <razão: ex. "platform.yaml não declara `repo:` block" ou "ensure_repo.py falhou: <erro>">.

## 2. Implicações

- Sem dívida técnica pré-existente.
- Liberdade plena para escolha de stack e padrões em `tech-research` / `adr`.
- Sem integrações legadas a considerar.

---
handoff:
  from: codebase-map
  to: tech-research
  context: "Greenfield. Próxima skill começa com folha em branco."
  blockers: []
  confidence: Alta
  kill_criteria: "platform.yaml passa a declarar repo: block resolvível"
```

### Auto-Review Additions

Per contract-base, gate=`auto` → **Tier 1 only** (deterministic checks, no LLM judgment).

| # | Check | How | On Failure |
|---|-------|-----|------------|
| 1 | Output exists and non-empty | `test -s platforms/<n>/research/codebase-context.md` | Re-run §2 |
| 2 | Lines within range | `wc -l` → 100–200 (brownfield) or 10–20 (greenfield) | Condense or expand |
| 3 | Frontmatter has repo_sha + repo_branch + updated | `grep -E '^(repo_sha\|repo_branch\|updated):'` returns 3 | Add missing fields |
| 4 | All 14 H2 sections present (brownfield) | `grep -cE '^## [0-9]+\.' = 14` | Add missing section |
| 5 | No unresolved placeholders | `grep -cE 'TODO\|TKTK\|\?\?\?\|PLACEHOLDER' = 0` (uncertainty markers `[VALIDAR]` etc. are allowed) | Resolve or mark with proper marker |
| 6 | HANDOFF block present | `grep -c '^handoff:'` = 1 | Append HANDOFF block |
| 7 | Stack table has ≥1 evidence per row | `grep -cE '\.[a-z]+:[0-9]+\|[VALIDAR]\|[ESTIMAR]'` ≥ row count | Add `path:line` evidence or mark |
| 8 | No skip-list dirs cited as evidence | `grep -E 'node_modules\|dist/\|\.lock'` = 0 | Replace with real source |

## Error Handling

| Problem | Action |
|---------|--------|
| `ensure_repo.py` fails (SSH+HTTPS both fail) | Greenfield with warning. Suggest: configure SSH keys or set `repos_base_dir` in DB. |
| `repo:` block missing in platform.yaml | Hard error: "Run `python3 .specify/scripts/platform_cli.py register <name>` or complete the `repo:` block in platform.yaml". |
| Repo > 10k non-skipped files | Sample: limit Pass 1 to top-level + entrypoints. Mark aggregate metrics with `[ESTIMAR]`. |
| Multiple primary languages | List all in §4 Stack table. Pick "primary" by largest LOC + main manifest hit. |
| `CLAUDE.md` / `AGENTS.md` absent | OK — §12 stays minimal. Do not invent decisions. |
| Repo working tree dirty | Do NOT block — codebase-map reads only. Log warning, proceed against HEAD. |
| Self-ref platform (madruga.ai itself) | `ensure_repo.py` returns `REPO_ROOT`. Skip clone path, proceed normally. |
| Pass 2 subagent times out | Continue with remaining 4. Mark missing section with `[VALIDAR — agent timeout]`. Do not retry. |
