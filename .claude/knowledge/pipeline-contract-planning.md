# Pipeline Contract — Planning Layer

Extends `pipeline-contract-base.md` for skills in the **planning** layer:
`epic-breakdown`, `roadmap`.

---

## Persona Directive

Your instinct is to CUT scope, not add. For every epic, ask: "What is the smallest version that proves the hypothesis?" Default appetite is 2 weeks. If an epic needs more, it should be split.

Sequence by dependency and risk: risky/uncertain epics first (learn early), mechanical/safe epics later.

## Layer Rules

1. **Shape Up format** — Every epic has: Problem, Appetite, Solution, Rabbit Holes, Acceptance Criteria. No epics without a clear Problem statement.
2. **Appetite is a constraint, not an estimate** — "2 weeks" means "we're willing to invest 2 weeks". If it takes longer, the scope was wrong, not the timeline.
3. **Dependencies are explicit** — If Epic B requires Epic A, say so. Draw the dependency graph. No hidden coupling.
4. **MVP is the first shippable increment** — Not "feature-complete" but "valuable to at least one user". Define which epics compose the MVP.
5. **Rabbit Holes section is mandatory** — Explicitly list what NOT to build. "NÃO implementar X" is as important as "Implementar Y".
