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

Create a new platform in the madruga.ai repository using the `platform.py new` script, which automatically:
1. Scaffolds via Copier (complete structure)
2. Injects the import into LikeC4Diagram.tsx (diagrams work automatically)
3. Updates portal symlinks (content appears in Starlight)

After scaffolding, follow the pipeline DAG with `/vision <name>`.

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Usage

- `/platform-new my-saas` — Create platform "my-saas"
- `/platform-new` — Prompt for name and collect context

## Prerequisites

- `copier>=9.4.0` installed (`pip install copier`)
- `likec4` CLI (`npm i -g likec4`)

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
python3 .specify/scripts/platform.py new <name>
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

Then register in the portal (inject LikeC4 + symlinks):
```bash
python3 .specify/scripts/platform.py register <name>
```

### 3. Verify

```bash
python3 .specify/scripts/platform.py lint <name>
python3 .specify/scripts/platform.py list
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
- [x] LikeC4 import injected into LikeC4Diagram.tsx
- [x] Portal symlink created
- [x] .copier-answers.yml generated (enables future `copier update`)

### Structure
platforms/<name>/
├── platform.yaml
├── .copier-answers.yml
├── business/vision.md, solution-overview.md
├── engineering/domain-model.md, containers.md, context-map.md, integrations.md
├── decisions/, epics/, research/
└── model/ (spec.likec4, likec4.config.json, views.likec4, ...)

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
| Scaffold OK but inject/symlinks fail | Run `python3 .specify/scripts/platform.py register <name>` (handles inject + symlinks + validation) |
| Portal does not show the platform | Run `python3 .specify/scripts/platform.py register <name>` and restart `npm run dev` |
| likec4 build fails on empty model | Normal — scaffold generates an empty `dynamic view businessFlow` that triggers a warning. Filling in the content resolves it. |

---
handoff:
  from: platform-new
  to: vision
  context: "Plataforma criada. Vision deve definir posicionamento de negocio."
  blockers: []
