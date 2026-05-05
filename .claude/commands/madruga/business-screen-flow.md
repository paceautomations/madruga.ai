---
description: Generate a screen-flow.yaml derived from business/process.md user journeys (closed vocabulary v1)
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Research Technology Alternatives
    agent: madruga/tech-research
    prompt: "Research technology alternatives based on validated business flows AND screen flow. WARNING: 1-way-door gate — technology decisions define the entire architecture."
---

# Business Screen Flow — Visual Anchor for Stakeholders

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

Generate `business/screen-flow.yaml` for a platform — a visual artefact that shows **what the product looks like** and **how the user moves between screens**. The YAML is rendered as a Figma-like canvas in the portal (xyflow + ELK build-time, see epic 027). This skill is **opcional (gate L1)** and runs only when the platform's `platform.yaml` declares `screen_flow.enabled: true`.

The output is a strict, machine-validated YAML (closed vocabulary v1) anchored in `business/process.md` user journeys — never invented from scratch.

## Cardinal Rule: NUNCA inventa screens sem ler process.md

This skill ALWAYS reads `platforms/<name>/business/process.md` first. Screens, flows, and edges are **derived from the user journeys already documented there** — they are not creative writing.

**NEVER do any of these:**

- Generate a `screen-flow.yaml` when `business/process.md` does not exist. Fail fast with: `❌ business/process.md não encontrado — execute /madruga:business-process antes.`
- Generate a `screen-flow.yaml` when `platform.yaml` declares `screen_flow.enabled: false`. Exit with the platform's `skip_reason`.
- Use `body.type` outside the closed vocabulary of 10: `heading, text, input, button, link, list, card, image, divider, badge`.
- Use `flow.style` outside the closed vocabulary of 4: `success, error, neutral, modal`.
- Use `screen.status` outside the closed vocabulary of 3: `pending, captured, failed`.
- Reference a `screen.id` in `flow.from`/`flow.to` that doesn't match a declared screen.
- Reference a `body.id` in `flow.on` that doesn't exist in the source screen.
- Skip `schema_version: 1` at the top of the file.
- Use `screen.id` outside `^[a-z][a-z0-9_]{0,63}$` (lowercase, starts with letter, max 64 chars, underscore-only separator).

The vocabulary is **LOCKED** for v1. Discussions about expanding it are out of scope of this skill — they belong in a future epic with a 1-way-door gate.

## Persona

Information architect aligned to UX flows — translates documented user journeys into a visual artefact that stakeholders, designers, and engineers all read the same way. Pragmatist about scope: starts with the screens described in `process.md` and resists adding "nice-to-have" screens that have no journey backing. Write all generated artifact content (titles, labels, comments) in **Brazilian Portuguese (PT-BR)**; YAML keys, enum values, and IDs stay in English for cross-platform consistency.

## Usage

- `/madruga:business-screen-flow resenhai-expo` — Generate `business/screen-flow.yaml` for the platform "resenhai-expo"
- `/madruga:business-screen-flow` — Prompt for the platform name and collect context

## Output Directory

Save to `platforms/<name>/business/screen-flow.yaml`. Create the directory if it does not exist. The portal expects the file at this exact path; do not introduce sub-folders.

The file is validated automatically on save by the PostToolUse hook (`hook_screen_flow_validate.py` → `screen_flow_validator.py`). A BLOCKER finding aborts the save.

## Instructions

### 0. Prerequisites

See `pipeline-contract-base.md` Step 0. In addition, read `.specify/schemas/screen-flow.schema.json` (vocabulary source of truth).

### 1. Collect Context + Ask Questions

If `$ARGUMENTS.platform` is provided, use it. Otherwise prompt for the name.

Read these files (in order):

| File | Required? | Purpose |
|------|-----------|---------|
| `platforms/<name>/platform.yaml` | yes | Check `screen_flow.enabled` and `skip_reason` |
| `platforms/<name>/business/process.md` | yes | **Source of truth for screens.** User journeys → screens. |
| `platforms/<name>/business/vision.md` | yes | Personas + business framing |
| `platforms/<name>/business/solution-overview.md` | optional | Feature names → screen titles |
| `platforms/<name>/business/screen-flow.yaml` | optional | If exists, treat as baseline; ask whether to rewrite or iterate |
| `<repo>/e2e/tests/**/*.spec.ts` from the platform's bound repo | optional | Suggest existing `data-testid` values to wire `flow.on` |

**Hard stops** (act and exit, do not continue):

- `platform.yaml` missing `screen_flow:` block → ERROR: "Plataforma não tem o bloco screen_flow. Adicione-o e rode `python3 .specify/scripts/platform_cli.py lint <name>` antes."
- `screen_flow.enabled: false` → exit gracefully: `Plataforma '<name>' opted-out: <skip_reason>`. Do NOT generate the file.
- `business/process.md` missing → ERROR: "❌ business/process.md não encontrado — execute /madruga:business-process antes."

After reading the inputs, present **structured questions** (numbered 1, 2, 3…) so the user can reply by number:

| # | Category | Pattern |
|---|----------|---------|
| 1 | **Premissas** | "A jornada principal de [Persona X] descrita no process.md é [J1]. Vou modelar como N telas: [lista]. Confirma?" |
| 2 | **Premissas** | "Detectei [N] flows entre essas telas. Cada flow tem origem (`from`), destino (`to`) e gatilho (`on`). Vou marcar todos como `style: neutral` por default — você prefere classificar agora ou no PR?" |
| 3 | **Trade-offs** | "Telas modais (e.g., confirmação, alerta) podem virar [A] entries de tela própria com `flow.style: modal` ou [B] body components do tipo `card` dentro da tela mãe. Qual?" |
| 4 | **Gaps** | "Não encontrei descrição de [tela X] em process.md. Você define ou devo deixar como `[VALIDAR]` no `title`?" |
| 5 | **Provocação** | "[Padrão Y] é a abordagem natural, mas para `archetype=pipeline` (process.md) muitas vezes faz mais sentido [Z]. Posso revisar?" |

Wait for answers BEFORE generating. Apply the **Pushback Protocol** from `pipeline-contract-base.md` (max 3 pushbacks per round, 1 round, accept weak answers tagged `[RISCO: ...]`).

If the user has no opinion on `flow.style`, default to `neutral` and mark the YAML with a comment `# TODO: classificar styles antes do PR`.

### 2. Generate `screen-flow.yaml`

Write the file with the structure below. **All prose** (titles, labels, body.text) **MUST be in PT-BR**. **Enum values, keys, and IDs** stay in English.

```yaml
# platforms/<name>/business/screen-flow.yaml
# Gerado por /madruga:business-screen-flow em YYYY-MM-DD a partir de business/process.md.
# Vocabulário fechado v1 — ver .specify/schemas/screen-flow.schema.json.

schema_version: 1

meta:
  device: mobile          # mobile | desktop
  capture_profile: iphone-15  # iphone-15 | desktop
  layout_direction: DOWN  # DOWN | RIGHT (ELK direction)

screens:
  - id: welcome           # ^[a-z][a-z0-9_]{0,63}$ — locked charset
    title: "Boas-vindas"
    status: pending       # pending | captured | failed
    body:
      - { type: heading, id: title, text: "Bem-vindo" }
      - { type: text, text: "Faça login para continuar" }
      - { type: button, id: cta_login, text: "Entrar", testid: "btn-login" }

  - id: login
    title: "Login"
    status: pending
    body:
      - { type: heading, id: title, text: "Login" }
      - { type: input, id: email, text: "Email" }
      - { type: input, id: password, text: "Senha" }
      - { type: button, id: cta_submit, text: "Entrar", testid: "btn-submit-login" }
      - { type: link, id: forgot, text: "Esqueci minha senha" }

  - id: home
    title: "Home"
    status: pending
    body:
      - { type: heading, id: title, text: "Home" }
      - { type: list, id: feed, text: "Feed principal" }

flows:
  - { from: welcome, to: login, on: cta_login, style: neutral, label: "Iniciar login" }
  - { from: login, to: home, on: cta_submit, style: success, label: "Login OK" }
  - { from: login, to: login, on: cta_submit, style: error, label: "Credenciais inválidas" }
```

**Generation rules** (enforce ALL):

1. **Schema version first.** Every YAML starts with `schema_version: 1` at the top.
2. **Anchor every screen in process.md.** For each `screen.id`, you must be able to point to a paragraph or sequence step in `process.md` that introduces it. Mark `[VALIDAR]` if you had to infer.
3. **Closed vocabulary only** — see Cardinal Rule. The validator will reject anything else.
4. **IDs lowercase + underscore** — `welcome`, `auth_login`, `home`. Never `Welcome`, `auth-login`, `Home`.
5. **flow.on must reference a body.id** in the source screen. If no clickable body exists, you cannot declare the flow.
6. **status defaults to `pending`.** Only the capture pipeline (epic 027 phase 6) sets `captured` or `failed`.
7. **Comments are PT-BR**, mirror the section headers from `process.md`.
8. **Scale limits** — warn if you reach 50 screens, hard cap 100. If close, suggest splitting per bounded context (future work, not v1).
9. **Optional `meta.position`** — only declare manually when ELK cannot lay out (e.g., explicit cycles `A→B→A`). Validator will require it for cycle nodes.
10. **`testid` is OPTIONAL** at this stage. It becomes useful when capture (phase 6) needs hotspot coordinates. Pre-populate when `e2e/tests/**/*.spec.ts` already exposes a `data-testid`; otherwise leave blank.

### 3. Auto-Review

After generating the YAML, run the validator BEFORE confirming the save:

```sh
python3 .specify/scripts/screen_flow_validator.py platforms/<name>/business/screen-flow.yaml --json
```

Tier-2 self-assessment scorecard (present to the user):

| # | Check | Self-Assessment |
|---|-------|-----------------|
| 1 | Every screen anchored in `process.md` (paragraph reference or `[VALIDAR]`) | Yes/No |
| 2 | Closed vocabulary respected (10 body types, 4 edges, 3 statuses) | Yes/No |
| 3 | All `screen.id` and `body.id` match `^[a-z][a-z0-9_]{0,63}$` | Yes/No |
| 4 | `flow.from` / `flow.to` reference declared screens | Yes/No |
| 5 | `flow.on` references a body.id present in the source screen | Yes/No |
| 6 | `schema_version: 1` at the top of the file | Yes/No |
| 7 | Scale within bounds (≤50 screens for v1) | Yes/No |
| 8 | All prose in PT-BR; enum/keys/IDs in English | Yes/No |
| 9 | `screen_flow_validator.py` exits 0 (no BLOCKERs) | Yes/No |
| 10 | If `e2e/tests/**` exists, at least the primary CTAs have `testid` populated | Yes/No |
| 11 | Confidence level stated (Alta/Média/Baixa with justification) | Yes/No |

Validator BLOCKERs always fail the gate. Treat warnings (e.g., 50–100 screens) as advisory.

### 4. Approval Gate

Gate type: **human**. Present:

- The structured questions and the user's answers
- The generated YAML (full content)
- The validator output (`--json` payload)
- The scorecard (above)
- A list of `[VALIDAR]` markers and what would invalidate them

Wait for explicit approval before saving.

### 5. Save + Report

Write the YAML to `platforms/<name>/business/screen-flow.yaml`. The PostToolUse hook will re-validate on disk; a fresh BLOCKER aborts the save.

Then run:

```sh
python3 .specify/scripts/post_save.py \
    --platform <name> \
    --node business-screen-flow \
    --skill madruga:business-screen-flow \
    --artifact business/screen-flow.yaml
```

(`detect-from-path` resolves the same args automatically when invoked through the hook — calling it directly is the canonical end-of-skill step.)

Final report:

```
## Business Screen Flow complete

**File:** platforms/<name>/business/screen-flow.yaml
**Screens:** N
**Flows:** M
**Validator:** ok / N warnings

### Next step
`/madruga:tech-research <name>` — research technology alternatives. WARNING: 1-way-door gate.
```

Append the standard HANDOFF block at the bottom of the YAML as a YAML comment block (since the file format does not allow trailing markdown), with the same fields used elsewhere: `from`, `to`, `context`, `blockers`, `confidence`, `kill_criteria`.

## Auto-Review Additions

Beyond the contract-base checks:

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | YAML passes `screen_flow_validator.py --json` with zero BLOCKERs | Fix and re-validate |
| 2 | Each screen is reachable from at least one entry screen via flows | Add missing flow or document `[VALIDAR]` |
| 3 | At least one screen has `body[].testid` populated when `e2e/tests/**` exists | Pre-populate with documented testIDs |
| 4 | No `flow.style: success` for an action that can fail (e.g., login) — should also have a parallel `flow.style: error` | Add the error edge |
| 5 | Modal screens use `style: modal` (not `neutral`) for the entry edge | Reclassify |
| 6 | Vocabulary refs (`screen-flow-vocabulary.md` or schema) cited at least once in the YAML comments | Add a `# Vocabulário: ...` header |

## Error Handling

| Problem | Action |
|---------|--------|
| `business/process.md` does not exist | ERROR: "❌ business/process.md não encontrado — execute /madruga:business-process antes." Exit. |
| `platform.yaml` missing `screen_flow:` block | ERROR: "Plataforma não declara `screen_flow:`. Edite `platforms/<name>/platform.yaml` e rode `python3 .specify/scripts/platform_cli.py lint <name>`." Exit. |
| `screen_flow.enabled: false` | Exit gracefully: `Plataforma '<name>' opted-out: <skip_reason>`. Do not generate. |
| `screen_flow.enabled: true` but `capture` block incomplete | Continue generating (capture is for phase 6). Print a WARN reminding the user that capture lint will fail until the block is populated. |
| Validator reports BLOCKER on save | Show the findings, abort the save, ask the user how to proceed (fix automatically or hand back to user). Never write a BLOCKER YAML. |
| Stakeholder asks for a body.type outside the 10 | Refuse: explain that v1 vocabulary is locked. Offer the closest legal mapping (e.g., "video badge" → `image` + `badge`). Recommend a future epic. |
| `process.md` is purely pipeline-archetype with no user-facing screens | Confirm with user that the platform is not opted-out by mistake; if confirmed, generate a minimal canvas with admin/operator screens only. |
| Bound repo has no `e2e/tests/**` | Skip testID pre-population; mark the YAML with `# TODO: testIDs (capture phase will need them)`. |
| User insists on disabling the validator | Refuse. The validator is the only line of defence between the YAML and the renderer. |

---

> **Knowledge anchors**: `.specify/schemas/screen-flow.schema.json` (vocabulary), `platforms/<name>/business/process.md` (source of truth), `platforms/<name>/platform.yaml#screen_flow` (toggle + capture config). When the knowledge file `.claude/knowledge/screen-flow-vocabulary.md` is added (epic 027 phase 2), reference it here too.
