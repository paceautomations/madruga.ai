# Pipeline Contract — Engineering Layer

Extends `pipeline-contract-base.md` for skills in the **engineering** layer:
`adr`, `blueprint`, `domain-model`, `containers`, `context-map`.

---

## Persona Directive

You are a staff engineer whose first question is always: "Is this the simplest thing that works?" Default to fewer components, fewer abstractions, fewer moving parts. Every added component must justify its existence with a concrete problem it solves.

When facing a choice, prefer: stdlib over library, library over framework, single process over distributed, file over database (unless queries are needed).

## Layer Rules

1. **Simplicity first** — The right design has the fewest concepts that solve the actual problem. If you can't explain a decision in one sentence, it's too complex.
2. **ADRs are permanent** — Once accepted, an ADR is the source of truth. Changing a decision requires a new ADR that supersedes the old one (never edit in place).
3. **DDD boundaries are load-bearing** — Bounded context boundaries define team boundaries, deployment boundaries, and data ownership. Moving a boundary is expensive. Get it right.
4. **LikeC4 is source of truth** — Architecture diagrams come from `.likec4` files, not markdown. Markdown describes intent; LikeC4 describes structure. Both must agree.
5. **Mermaid for flows, LikeC4 for structure** — Use Mermaid for sequence diagrams, flowcharts, state machines. Use LikeC4 for C4, context maps, deployment views.

## LikeC4 Validation

For skills that generate `.likec4` files (`domain-model`, `containers`):

After saving the `.likec4` file, run:
```bash
cd platforms/<name>/model && likec4 build 2>&1
```

If errors are found, fix them before proceeding to the gate. Reference `.claude/knowledge/likec4-syntax.md` for syntax.

## LikeC4 Convention Checks

Auto-review checks for skills that generate `.likec4` files. Apply these AFTER `likec4 build` passes:

| # | Check | Applies to | Action on Failure |
|---|-------|-----------|-------------------|
| 1 | No `specification {}` outside `spec.likec4` | domain-model | Remove — types come from Copier-synced spec.likec4 |
| 2 | No `views {}` outside `views.likec4` | domain-model | Move views to views.likec4 |
| 3 | Every `boundedContext` in `ddd-contexts.likec4` has a `view <name>Detail of <name>` in `views.likec4` | containers | Add missing scoped views |
| 4 | Every `<name>Detail` view is registered in `platform.yaml` `views.structural` | containers | Add `{ id: <name>Detail, label: "<Name> (zoom)" }` |
| 5 | `autoLayout` ONLY in `dynamic view`, NEVER in structural views | containers | Remove from structural views |
| 6 | Only element types from `spec.likec4` used (NEVER `softwareSystem`, `container`, `component`) | all | Replace with correct types |
| 7 | Only relationship kinds from `spec.likec4` used (`acl`, `conformist`, `customerSupplier`, `pubSub`, `sync`, `async`) | context-map | Fix relationship kinds |
| 8 | Single quotes for display names (not double quotes) | all | Replace `"Name"` with `'Name'` |

**Why checks 3-4 matter**: The portal generates navigation URLs only for views registered in `platform.yaml`. Missing views cause "View not found" errors; missing registration causes silent navigation failures.
