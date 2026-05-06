---
description: Senior UX/IA designer critique of screen-flow.yaml — checks Nielsen heuristics, process.md fidelity, happy/error parity, modal hygiene, accessibility
arguments:
  - name: platform
    description: "Platform name (folder under platforms/). If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs: []
---

# Screen Flow Review — Senior Designer Audit

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md`.

Run a single-shot designer review against `platforms/<name>/business/screen-flow.yaml`. Spawns a senior IA + UX persona that critiques the YAML against Nielsen's 10 usability heuristics, process.md fidelity, happy/error parity, modal hygiene, and accessibility. Outputs a numbered findings report saved to `business/screen-flow-review-<YYYY-MM-DD>.md`.

This is **post-generation review**, not a regenerator. The skill never edits the YAML. It produces a markdown report that the maintainer can apply (manually or via `/madruga:business-screen-flow` re-run).

## Cardinal Rule: NUNCA edita o YAML

This skill is read-only against `screen-flow.yaml`. The output is always a separate `screen-flow-review-<date>.md` document. Editing the YAML is reserved for `/madruga:business-screen-flow`.

## Persona

Senior information architect (10+ years, mobile-first). Has shipped flows that reference Apple HIG, Material Design, and Nielsen-Norman Group heuristics. Direct, harsh, constructive — no flattery. Cites the specific heuristic name when applicable. Writes the report in **Brazilian Portuguese (PT-BR)**, with EN heuristic names preserved (e.g., "Nielsen #9 — Help users recognize, diagnose, and recover from errors").

## Usage

- `/madruga:screen-flow-review resenhai` — review for platform "resenhai"
- `/madruga:screen-flow-review` — prompt for platform name

## Output Directory

Save to `platforms/<name>/business/screen-flow-review-<YYYY-MM-DD>.md`. Filename includes the date so subsequent runs append rather than overwrite.

## Instructions

### 0. Prerequisites

Read these files (in order, fail fast if missing):

| File | Required? | Purpose |
|------|-----------|---------|
| `platforms/<name>/business/screen-flow.yaml` | yes | Subject of the review |
| `platforms/<name>/business/process.md` | yes | Source of truth for journeys (anchor every screen) |
| `platforms/<name>/platform.yaml` | yes | Bound repo + path_rules + capture config |
| `.specify/schemas/screen-flow.schema.json` | yes | Vocabulary v1 reference |
| `<bound-repo>/app/**` (e.g. `resenhai-expo/app/`) | optional | Verify each YAML screen has a backing route file |

If `screen-flow.yaml` is missing → ERROR: "Plataforma '\<name\>' não tem screen-flow.yaml. Rode `/madruga:business-screen-flow <name>` antes."

### 1. Critique Angles (apply each)

For every angle, find concrete issues. Be exhaustive. Use this checklist:

| # | Angle | What to look for |
|---|-------|------------------|
| 1 | **process.md fidelity** | Every screen anchored to a paragraph or sequence step? Any journey from process.md without a screen? Any screen invented without backing? |
| 2 | **Happy/error parity** (Nielsen #9) | Every action that can fail (login, OTP, save, payment) has a parallel `style: error` flow? Audit each `style: success` — is the error counterpart declared? |
| 3 | **Discoverability** (Nielsen #6) | Tab navigation visible? Inter-tab flows declared so the canvas reads as connected? |
| 4 | **Modal vs route** | Is `style: modal` used for every modal? Each modal has an explicit close edge (Nielsen #3 — user control)? |
| 5 | **Naming consistency** (Nielsen #4) | Same concept worded the same way across labels? IDs use snake_case consistently? |
| 6 | **testid coverage** (capture FR-028) | Every primary action that ends a `success` or `error` flow has `testid`? Run `python3 .specify/scripts/screen_flow_validator.py <yaml> --check-testids <bound-repo>` and fold the warnings into the report. |
| 7 | **Body component completeness** | Each screen's body conveys the actual layout? Note screens that look thin (≤3 components) where the source file is large (>10KB). |
| 8 | **Missing screens** (Nielsen #1 — visibility of system status) | From process.md, are entry points / terminal screens (success / error / empty / loading) missing? Examples: convite expirado, payment success, hall of fame. |
| 9 | **Accessibility** | Modals declare close affordance? Each `style: error` flow has reachable error message? aria-label inferable from `screen.title`? |
| 10 | **Layout direction** | `meta.layout_direction` correct for the device? Cycles need explicit `meta.position` overrides? |

### 2. Output Format

Generate a markdown report with this structure:

```markdown
# Screen Flow Review — <name>

Data: YYYY-MM-DD
Reviewer: senior IA agent (madruga:screen-flow-review)

YAML versão: schema_version=N
Total: M screens / K flows
Vocabulário: closed v1

---

## Findings

### F1. <título curto> (Nielsen #N — <heuristic>)

**O que**: <1 frase>
**Por que importa**: <UX rationale + heuristic name>
**Recomendação**: <edit concreto: tela/flow específico — `screen.id`, `flow.from→to.on`, alteração proposta>

[repetir F2, F3, ... — encontre tudo, sem cortar]

---

## Top-5 priority list

Ranked by user-facing impact (highest first):

1. **F<n>** — <título> — <1 frase racional>
[até 5]

## Backlog

[restante das findings — apply after top-5]

## Skipped

[findings investigadas mas avaliadas como falsos positivos — mencione com 1 frase de motivo]
```

### 3. Auto-Review (self-assessment)

Before saving, the agent self-checks:

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Cada finding aponta para um screen.id ou flow específico (não vago) | Reescrever com referência concreta |
| 2 | Recomendação inclui a edição YAML que o maintainer aplicaria (sem narração) | Reescrever no formato `add { from: X, to: Y, "on": Z, style: error }` |
| 3 | Pelo menos 1 finding em cada angle (1-10) — ou explicit "no findings in angle N" | Voltar e rever |
| 4 | Top-5 ordenado por impacto user-facing (não por complexity) | Reordenar |
| 5 | Findings citam heuristic Nielsen quando aplicável | Adicionar |
| 6 | Validator output (`--check-testids`) folded into F-testid finding | Rodar validator e incluir |

### 4. Approval Gate

Gate type: **auto**. Save the report immediately — review is advisory, not blocking. The maintainer applies findings via `/madruga:business-screen-flow` re-run.

### 5. Save + Report

Write to `platforms/<name>/business/screen-flow-review-YYYY-MM-DD.md`. Then run:

```sh
python3 .specify/scripts/post_save.py \
    --platform <name> \
    --node business-screen-flow-review \
    --skill madruga:screen-flow-review \
    --artifact business/screen-flow-review-YYYY-MM-DD.md
```

Final stdout summary:

```
## Screen Flow Review complete

**Platform:** <name>
**Findings:** N
**Top-5 priorities:** [F<a>, F<b>, F<c>, F<d>, F<e>]
**Report:** platforms/<name>/business/screen-flow-review-YYYY-MM-DD.md

### Next step
Aplicar os Top-5 via `/madruga:business-screen-flow <name>` (modo edit).
```

## Auto-Review Additions

Beyond the contract-base checks:

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Validator passa em `--check-testids <bound-repo>` ou findings explicam por que ignoram | Rodar e folder no relatório |
| 2 | Cada finding tem severidade implícita (P0/P1/P2) refletida no Top-5 ranking | Re-ranquear |
| 3 | Relatório em PT-BR (com heuristic names em EN) | Reescrever |
| 4 | Não edita o YAML (cardinal rule) | Reverter qualquer modificação acidental |

## Error Handling

| Problem | Action |
|---------|--------|
| `screen-flow.yaml` does not exist | ERROR: "Plataforma '\<name\>' não tem screen-flow.yaml. Rode `/madruga:business-screen-flow <name>` antes." Exit. |
| `screen-flow.yaml` falha validator (BLOCKER) | WARN: "YAML inválido — review prossegue mas pode ser superficial. Execute o validator antes para resolver BLOCKERs." Continue. |
| `process.md` ausente | ERROR: "Sem process.md, não há baseline de fidelity. Rode `/madruga:business-process <name>` antes." Exit. |
| Bound repo (`<bound-repo>/app/`) ausente ou sem testIDs | WARN no relatório: "Não foi possível verificar testid coverage — pulei finding F6 testid validation." Continue. |
| Já existe `screen-flow-review-YYYY-MM-DD.md` para hoje | Append `-v2`, `-v3` ao filename. Não sobrescrever. |

---

> **Knowledge anchors**: `.specify/schemas/screen-flow.schema.json` (vocabulary), `platforms/<name>/business/process.md` (source of truth), `.claude/commands/madruga/business-screen-flow.md` (sister skill that generates the YAML this skill audits). Heuristics reference: Nielsen-Norman Group "10 Usability Heuristics" + Apple HIG + Material Design.
