---
description: Create a new platform or onboard an existing one into the Copier template
arguments:
  - name: platform
    description: "Platform name in kebab-case (e.g., my-saas, energy-platform)"
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Vision One-Pager
    agent: madruga/vision
    prompt: Generate business vision for the new platform
  - label: Map Existing Codebase (brownfield)
    agent: madruga/codebase-map
    prompt: "Brownfield platform — map existing codebase before starting documentation pipeline"
---

# Platform New — Scaffolding

Create a new platform in the madruga.ai repository using the Copier template, which automatically scaffolds the directory structure, portal symlinks, and platform manifest.

Supports two modes:
- **Greenfield**: brand-new platform, no existing repository
- **Brownfield**: platform already exists as a GitHub repo — scaffold docs + clone repo locally

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Cardinal Rule: ZERO Silent Assumptions About Platform Type

Always ask greenfield vs brownfield before scaffolding. Never infer mode from the platform name or repo presence.

**NEVER:**
- Scaffold without confirming mode (new vs existing)
- Run `ensure_repo.py` before `platform_cli.py new` has finished (symlinks + DB + status JSON are created by the script)
- Pass flags not defined in `copier.yml` or `platform_cli.py new --help`
- Call copier directly — always go through `platform_cli.py new` (it handles copier + symlinks + DB + JSON atomically)

## Output Directory

Scaffold output: `platforms/<name>/` (full directory tree created by Copier).

## Persona

Pragmatic DevOps — fast scaffolding, immediate validation. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/platform-new my-saas` — Create platform "my-saas" (prompted for mode)
- `/platform-new resenhai` — Onboard existing repo "resenhai-expo" (prompted for mode)
- `/platform-new` — Prompt for name and mode

## Prerequisites

- `copier>=9.4.0` installed (`pip install copier`)

## Instructions

### 1. Collect Name

**If `$ARGUMENTS.platform` exists:** use as name.
**If empty:** prompt for the platform name (kebab-case).

Validate: `^[a-z][a-z0-9-]*$`. If invalid, prompt again.

### 2. Ask Mode: Greenfield vs Brownfield

```
Is this a new platform (greenfield) or an existing repository (brownfield)?
[N] New — code will be created from scratch
[E] Existing — repo already exists on GitHub, I want to document it
```

---

#### Mode N — Greenfield

Collect:
- **Title** (e.g., "My SaaS — Order Management")
- **Description** (1 line)
- **Lifecycle**: design, development, or production (default: design)

Set `repo_name=""` — `platform.yaml` will have an empty `repo.name` (block always emitted, `ensure_repo.py` skips empty names).

#### Mode E — Brownfield

Collect base info (same as greenfield):
- **Title**, **Description**, **Lifecycle**

Then collect repo binding:

| Field | Question | Example |
|-------|----------|---------|
| `repo.org` | GitHub org? | `paceautomations` |
| `repo.name` | Exact repo name on GitHub? | `resenhai-expo` |
| `repo.base_branch` | Base branch for PRs? (default: main) | `develop` |

> **Self-ref note**: If the user is documenting THIS repository (madruga.ai itself), `repo.name` must be exactly `"madruga.ai"` (dot, not hyphen). `ensure_repo.py` detects this string and returns the local path without cloning.

---

### 3. Create Platform

Use `platform_cli.py new` with explicit flags — the script handles **everything atomically**: Copier scaffolding, portal symlinks, DB seed, and `pipeline-status.json` refresh.

**Greenfield** (`repo_name` empty — no external repo):
```bash
python3 .specify/scripts/platform_cli.py new <name> \
  --title "<title>" \
  --description "<description>" \
  --lifecycle <lifecycle> \
  --repo-org paceautomations \
  --repo-name "" \
  --repo-branch main \
  --tags "<csv,opcional>" \
  --testing-startup <none|docker|npm|python>
```

**Brownfield** (existing GitHub repo):
```bash
python3 .specify/scripts/platform_cli.py new <name> \
  --title "<title>" \
  --description "<description>" \
  --lifecycle <lifecycle> \
  --repo-org <org> \
  --repo-name <repo_name> \
  --repo-branch <base_branch> \
  --tags "<csv,opcional>" \
  --testing-startup <none|docker|npm|python>
```

**Optional flags**:
- `--tags`: CSV de tags renderizadas em `platform.yaml` (ex: `whatsapp,multi-tenant`). Vazio omite o campo.
- `--testing-startup`: tipo de startup do app para testes E2E. `none` omite o bloco `testing:`. Outros valores geram esqueleto a preencher (`command`, `health_checks`, `urls`, `required_env`).

> **What the script does automatically:**
> 1. Copier scaffold (non-interactive, `--defaults` + `-d` flags)
> 2. Portal symlinks at `portal/src/content/docs/<name>/` (no dev-server restart needed)
> 3. SQLite DB seed (`pipeline_nodes` + `platforms` tables)
> 4. `portal/src/data/pipeline-status.json` regenerated (platform appears in Execution tab immediately)

> **Dependency order for brownfield**: `platform.yaml` is written by step 1 with the `repo:` block — `ensure_repo.py` (step 4 below) runs after, so the dependency is automatically satisfied.

### 4. Clone External Repo (Brownfield only)

After scaffold + register, clone or fetch the external repo:

```bash
python3 .specify/scripts/ensure_repo.py <name>
```

What the script does:
- Reads `platforms/<name>/platform.yaml` → `repo:` block
- Self-ref (`repo.name == "madruga.ai"`): returns `REPO_ROOT`, no clone
- External: clones via SSH (`git@github.com:<org>/<name>.git`), HTTPS fallback
- Destination: `~/repos/<org>/<repo_name>` (default; controlled by `repos_base_dir` in DB)
- If repo already exists: runs `git fetch --all --prune`

Inform the user of the cloned path. The default is `~/repos/<org>/<repo_name>`.

### 5. Verify

```bash
python3 .specify/scripts/platform_cli.py lint <name>
python3 .specify/scripts/platform_cli.py list
```

### 6. Present Result

**Greenfield:**

```
## Platform Created

**Name:** <name>
**Directory:** platforms/<name>/

### What was done automatically
- [x] Structure scaffolded via Copier
- [x] Portal symlinks created at portal/src/content/docs/<name>/
- [x] DB seeded (platform visible in pipeline immediately)
- [x] pipeline-status.json refreshed (Execution tab shows platform)
- [x] decisions.md created (running decisions log)
- [x] .copier-answers.yml generated (enables future `copier update`)

### Structure
platforms/<name>/
├── platform.yaml
├── decisions.md          ← running decisions log
├── .copier-answers.yml
├── business/vision.md, solution-overview.md, process.md
├── engineering/domain-model.md, blueprint.md, containers.md, context-map.md
├── decisions/, epics/, research/, planning/
├── testing/journeys.md   ← skeleton para QA E2E (preencher quando definir jornadas)

### Next step
- `/vision <name>` — start documentation pipeline
- `/pipeline <name>` — see pipeline DAG status
```

**Brownfield:**

```
## Platform Onboarded

**Name:** <name>
**Directory:** platforms/<name>/

### What was done automatically
- [x] Structure scaffolded via Copier
- [x] Portal symlinks created at portal/src/content/docs/<name>/
- [x] DB seeded (platform visible in pipeline immediately)
- [x] pipeline-status.json refreshed (Execution tab shows platform)
- [x] decisions.md created (running decisions log)
- [x] .copier-answers.yml generated

### Repo Binding
- org: <org>
- name: <repo_name>
- base_branch: <base_branch>
- local path: ~/repos/<org>/<repo_name> ✓ (cloned/fetched)

(To change the base directory: python3 .specify/scripts/platform_cli.py set-config repos_base_dir <path>)

### Next step
- `/codebase-map <name>` — map existing codebase (recommended for brownfield — optional DAG node)
- `/vision <name>` — start documentation pipeline
- `/pipeline <name>` — see pipeline DAG status
```

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Was mode (greenfield/brownfield) explicitly asked? | Ask before proceeding |
| 2 | Brownfield: does `platform.yaml` contain `repo:` block after scaffold? | Re-run copier with correct `-d repo_name=` flag |
| 3 | Brownfield: did `ensure_repo.py` run successfully after scaffold? | Check error table; retry or show manual clone command |
| 4 | Lint passes with 0 FAIL? | Run `platform_cli.py lint <name>` and fix blockers |
| 5 | Next step recommendation matches mode? | Brownfield → `/codebase-map`; Greenfield → `/vision` |

## Error Handling

| Problem | Action |
|---------|--------|
| copier not installed | `pip install copier` |
| Platform already exists | Ask: overwrite or choose another name |
| `ensure_repo.py` exits with "no repo: block" | Copier did not generate `repo:` block — verify `-d repo_name=` was passed correctly. Re-run copier or edit `platform.yaml` manually |
| SSH + HTTPS clone both fail | Scaffold already done. Run: `git clone https://github.com/<org>/<name>.git ~/repos/<org>/<name>`. Check GitHub credentials and that the repo exists |
| `ensure_repo.py` fails for other reason | Platform is scaffolded and functional. Clone can be retried: `python3 .specify/scripts/ensure_repo.py <name>` |
| Scaffold OK but symlinks/DB fail | Run `python3 .specify/scripts/platform_cli.py register <name>` (idempotent — re-creates symlinks, re-seeds DB, refreshes JSON) |
| Portal does not show the platform | Run `python3 .specify/scripts/platform_cli.py register <name>` — no dev-server restart needed |
