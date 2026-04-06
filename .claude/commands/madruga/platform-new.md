---
description: Create a new platform from the Copier template
arguments:
  - name: platform
    description: "Platform name in kebab-case (e.g., my-saas, energy-platform)"
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Vision One-Pager
    agent: madruga/vision
    prompt: Generate business vision for the new platform
---

# Platform New — Scaffolding

Create a new platform in the madruga.ai repository using the `platform_cli.py new` script, which automatically:
1. Scaffolds via Copier (complete structure)
2. Updates portal symlinks (content appears in Starlight)

After scaffolding, follow the pipeline DAG with `/vision <name>`.

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Persona

Pragmatic DevOps — fast scaffolding, immediate validation. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/platform-new my-saas` — Create platform "my-saas"
- `/platform-new` — Prompt for name and collect context

## Prerequisites

- `copier>=9.4.0` installed (`pip install copier`)

## Instructions

### 1. Collect Name and Context

**If `$ARGUMENTS.platform` exists:** use as name.
**If empty:** prompt for the platform name (kebab-case).

Validate: `^[a-z][a-z0-9-]*$`. If invalid, prompt again.

Also collect (to pass to copier via `-d`):
- **Title** (e.g., "My SaaS — Order Management")
- **Description** (1 line)
- **Lifecycle**: design, development, or production
- **Business flow**: include business flow view? (default: yes)

### 2. Create Platform

Run the script that handles EVERYTHING automatically:

```bash
python3 .specify/scripts/platform_cli.py new <name>
```

**In non-interactive context** (when copier cannot ask questions), use:

```bash
copier copy .specify/templates/platform/ platforms/<name>/ --trust --defaults \
  -d platform_name=<name> \
  -d "platform_title=<title>" \
  -d "platform_description=<description>" \
  -d lifecycle=<lifecycle> \
  -d include_business_flow=true \
  -d register_portal=false
```

Then register in the portal (symlinks + DB):
```bash
python3 .specify/scripts/platform_cli.py register <name>
```

### 3. Verify

```bash
python3 .specify/scripts/platform_cli.py lint <name>
python3 .specify/scripts/platform_cli.py list
```

### 4. Next Step

Inform the user that the platform was created and the next step is to start the documentation pipeline:

```
Platform '<name>' created successfully!

Next step: `/vision <name>` to start the documentation pipeline.
Use `/pipeline <name>` to see the full pipeline status.
```

### 5. Present Result

```
## Platform Created

**Name:** <name>
**Directory:** platforms/<name>/

### What was done automatically
- [x] Structure scaffolded via Copier
- [x] Portal symlink created
- [x] .copier-answers.yml generated (enables future `copier update`)

### Structure
platforms/<name>/
├── platform.yaml
├── .copier-answers.yml
├── business/vision.md, solution-overview.md
├── engineering/domain-model.md, containers.md, context-map.md, integrations.md
├── decisions/, epics/, research/

### Next step
- `/vision <name>` — start documentation pipeline (recommended)
- `/pipeline <name>` — see pipeline DAG status
- `cd portal && npm run dev` — view in portal
```

## Error Handling

| Issue | Action |
|-------|--------|
| copier not installed | `pip install copier` |
| Platform already exists | Ask: overwrite or choose another name |
| Scaffold OK but symlinks fail | Run `python3 .specify/scripts/platform_cli.py register <name>` (handles symlinks + validation) |
| Portal does not show the platform | Run `python3 .specify/scripts/platform_cli.py register <name>` and restart `npm run dev` |

