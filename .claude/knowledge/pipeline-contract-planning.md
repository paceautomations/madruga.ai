# Pipeline Contract — Planning Layer

Extends `pipeline-contract-base.md` for skills in the **planning** layer:
`roadmap` (L1 definition + sequencing) and `roadmap-reassess` (L2 reassess after each epic).

---

## Persona Directive

Your instinct is to CUT scope, not add. For every epic, ask: "What is the smallest version that proves the hypothesis?" If an epic feels too large, it should be split.

Sequence by dependency and risk: risky/uncertain epics first (learn early), mechanical/safe epics later.

## Layer Rules

1. **Problem before solution** — Every epic row in `planning/roadmap.md` has a 2-sentence problem statement from the user/business perspective. No features without a problem. Solution-space details (Rabbit Holes, Acceptance Criteria) live in the epic's `pitch.md`, generated later by `epic-context`.
2. **Dependencies are explicit** — If Epic B requires Epic A, declare it in the `Deps` column and the Dependencies Mermaid graph. No hidden coupling.
3. **MVP is the first shippable increment** — Not "feature-complete" but "valuable to at least one user". Mark which epics compose the MVP explicitly.
4. **"Não Este Ciclo" is mandatory** — Explicitly list what was considered but excluded, with the reason (data-backed, not "baixa prioridade") and the trigger that would bring it back. Cutting scope is as important as adding scope.
5. **Epic IDs are immutable once gated** — `roadmap` is 1-way-door. Once a row is approved, its NNN-slug is the identity consumed by all downstream skills. Renumbering later requires an explicit "Renumeração" note in the roadmap.
