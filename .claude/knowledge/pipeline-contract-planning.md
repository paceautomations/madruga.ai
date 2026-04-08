# Pipeline Contract — Planning Layer

Extends `pipeline-contract-base.md` for skills in the **planning** layer:
`epic-breakdown`, `roadmap`.

---

## Persona Directive

Your instinct is to CUT scope, not add. For every epic, ask: "What is the smallest version that proves the hypothesis?" If an epic feels too large, it should be split.

Sequence by dependency and risk: risky/uncertain epics first (learn early), mechanical/safe epics later.

## Layer Rules

1. **Shape Up format** — Every epic has: Problem, Solution, Rabbit Holes, Acceptance Criteria. No epics without a clear Problem statement.
2. **Dependencies are explicit** — If Epic B requires Epic A, say so. Draw the dependency graph. No hidden coupling.
3. **MVP is the first shippable increment** — Not "feature-complete" but "valuable to at least one user". Define which epics compose the MVP.
4. **Rabbit Holes section is mandatory** — Explicitly list what NOT to build. "NÃO implementar X" is as important as "Implementar Y".
