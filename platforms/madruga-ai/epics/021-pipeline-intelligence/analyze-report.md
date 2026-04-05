# Specification Analysis Report — Epic 021: Pipeline Intelligence

**Date**: 2026-04-04
**Artifacts analyzed**: pitch.md, spec.md, plan.md, tasks.md
**Codebase cross-reference**: dag_executor.py (1937 LOC), db_pipeline.py, platform.yaml

---

## ⚠ Structural Anomaly

**spec.md and plan.md are stubs** — they contain Q&A session notes from incomplete sessions, not actual specifications or design artifacts. The tasks.md correctly identifies this (line 4: "spec.md and plan.md are stubs from Q&A sessions") and uses **pitch.md as the primary design document**.

This analysis treats pitch.md as the authoritative source of requirements and plan.md/spec.md as non-existent for cross-reference purposes.

---

## Findings Table

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Underspecification | CRITICAL | spec.md (entire) | spec.md is a stub — 8 lines of Q&A notes, not a feature specification. No functional requirements (FR-xxx), no success criteria (SC-xxx), no user stories with acceptance criteria. | Generate proper spec.md before implement, or formally adopt pitch.md as spec equivalent via a header note in tasks.md |
| A2 | Underspecification | CRITICAL | plan.md (entire) | plan.md is a stub — 11 lines of Q&A notes, not a design plan. No architecture decisions, no data model, no phase breakdown. | Generate proper plan.md before implement, or acknowledge pitch.md's "Solution" section as plan equivalent |
| B1 | Inconsistency | HIGH | pitch.md:L178, dag_executor.py | Pitch states dag_executor.py is "1,649 LOC" — actual is **1,937 LOC** (17% drift). Line references in tasks.md (e.g., "line 1302", "line 1812") may also be stale. | Update LOC count. Verify all line number references at implementation time (T001 setup) |
| B2 | Inconsistency | HIGH | tasks.md:L43-44, dag_executor.py:L1302,L1813 | tasks.md says cost tracking "Gap: field names may not match actual output" and T005 says "update parse_claude_output()". But `parse_claude_output()` is already called in **3 places** (lines 524, 1302, 1813) and passes metrics to `complete_run()`. The function exists and is wired. The real gap is only: **do the field names match actual `claude -p` JSON output?** T005 may be a no-op if T001 confirms field names match. | Clarify: T005 scope should be "validate + adjust field names IF needed", not "replicate in dispatch normal" (replication is already done) |
| B3 | Inconsistency | HIGH | pitch.md:L50, tasks.md:L44 | Pitch says "`_run_implement_tasks()` em `dag_executor.py:403-413`". Actual function is `run_implement_tasks()` (no leading underscore) at line 428, and the metric parsing is at line 524. | Fix function name reference. Cosmetic but indicates pitch was written against a stale snapshot |
| C1 | Ambiguity | HIGH | tasks.md:T010,T011,T012 | Hallucination guard checks `tool_use_count` field — but **this field doesn't exist in `dag_executor.py`** and its existence in `claude -p` JSON output is unverified. T001 only mentions verifying "output fields" for cost tracking, not tool call count. | Add explicit verification of tool-call-count field to T001 scope, or create a T001b for hallucination guard field discovery |
| C2 | Ambiguity | MEDIUM | tasks.md:T023, dag_executor.py:L1123-1130 | skip_condition is **never actually evaluated** — current code simply checks `if node.optional and node.skip_condition:` and **always skips** (lines 1123 and 1694). The string `"epic.appetite <= '2w'"` would be ignored; ANY truthy skip_condition causes skip. T023 says "trace existing skip_condition logic to confirm" but this is an understatement — an expression evaluator needs to be built. | Rewrite T023 as an implementation task: "Implement skip_condition evaluator or change approach to a boolean `skip: true/false` in platform.yaml" |
| C3 | Ambiguity | MEDIUM | pitch.md:L65, tasks.md:T013 | Pitch says hallucination guard action is "REJECT — output likely fabricated. Re-prompt". Tasks.md:T013 says "WARNING — output may be fabricated". User answered "warning + continua" in spec Q&A. **Contract doc should say WARNING, not REJECT**, matching the user decision. | Ensure T013 uses WARNING action, not REJECT from pitch |
| D1 | Coverage Gap | MEDIUM | pitch.md AC, tasks.md | Pitch acceptance criterion: "Portal tab 'Cost' (epic 017) mostra dados reais de custo". T007 is a "read-only check, no code change expected". If the portal DOESN'T render correctly, there's no task to fix it — only to observe the problem. | Add contingency: if T007 finds portal issues, a follow-up task should be created |
| D2 | Coverage Gap | MEDIUM | pitch.md:L149-150 | Pitch Rabbit Hole: "Hallucination guard pode ter false positives — skills que legitimamente nao precisam de tool calls. Configurar whitelist de skills isentos." **No task creates this whitelist.** | Add a task for whitelist configuration, or explicitly defer to future scope with a note |
| E1 | Duplication | LOW | tasks.md:T011,T012 | T011 (sync loop integration) and T012 (async loop integration) are identical logic in two code paths. The sync/async execution loops at lines 1123 and 1694 are near-identical. | Consider: could these be unified into a shared post-dispatch function? Would reduce duplication in both the codebase and the task list |
| F1 | Inconsistency | LOW | tasks.md:T016 risk note vs CLAUDE.md | tasks.md:L209 correctly notes "T16 skill creation: Must go through `/madruga:skills-mgmt create` per repo conventions". Good — but the task T016 description says "Create `/quick-fix` skill markdown" directly. | Ensure T016 implementation uses skills-mgmt, not direct file creation |
| F2 | Inconsistency | LOW | tasks.md summary table | Summary says "US1 (Cost Tracking): 5 tasks (T003–T007)" but T001 (setup/research for US1) and T002 (test pattern review) are also prerequisites. Effective US1 scope is 7 tasks. | Minor — summary is task-count by phase, not total effort. No action needed |
| G1 | Underspecification | LOW | tasks.md:T006 | Hardcoded pricing: "fallback: `tokens_in * 0.003/1000 + tokens_out * 0.015/1000` for Sonnet". Model pricing changes frequently. No mention of how to update these values or make them configurable. | Use a config dict or env var for model pricing. Or skip cost calculation entirely if claude output doesn't provide it (simpler) |

---

## Coverage Summary Table

| Requirement (from pitch.md AC) | Has Task? | Task IDs | Notes |
|-------------------------------|-----------|----------|-------|
| `pipeline_runs` populated with tokens/cost after dispatch | ✅ | T003-T007 | Well covered. T001 research is prerequisite |
| Zero tool calls → WARNING in log | ✅ | T008-T012 | Covered. Missing: tool_use_count field verification (C1) |
| `/quick-fix` skill exists | ✅ | T016 | Covered |
| `--quick` flag in dag_executor.py | ✅ | T014,T015,T017-T020 | Well covered |
| `roadmap-reassess` node optional in epic_cycle | ✅ | T021-T023 | Covered but skip_condition evaluator missing (C2) |
| Portal "Cost" tab shows real data | ⚠ Partial | T007 | Read-only check — no fix task if broken (D1) |
| `make test` passes | ✅ | T024 | Polish phase |
| `make ruff` passes | ✅ | T025 | Polish phase |
| Hallucination whitelist (Rabbit Hole) | ❌ | — | No task covers this (D2) |

---

## Constitution Alignment Issues

| Principle | Status | Detail |
|-----------|--------|--------|
| I. Pragmatism | ✅ OK | Solutions are appropriately simple (heuristics over ML, markdown skill over framework) |
| IV. Fast Action | ⚠ | spec.md and plan.md are stubs — proceeding with pitch-as-spec is pragmatic but unconventional |
| V. Alternatives/Trade-offs | ⚠ | tasks.md doesn't document alternatives for implementation decisions (e.g., skip_condition evaluator vs boolean flag) |
| VII. TDD | ✅ OK | Tasks follow Red-Green-Refactor pattern, tests before implementation |
| VIII. Collaborative Decision | ✅ OK | Q&A sessions documented (even though spec/plan are stubs) |
| IX. Observability | ✅ OK | Hallucination guard uses structured logging with WARNING level |

No CRITICAL constitution violations found.

---

## Unmapped Tasks

All tasks map to at least one pitch acceptance criterion. No orphan tasks detected.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Requirements (from pitch AC) | 8 |
| Total Tasks | 28 |
| Coverage % (requirements with ≥1 task) | 88% (7/8 — whitelist missing) |
| Ambiguity Count | 3 (C1, C2, C3) |
| Duplication Count | 1 (E1) |
| Critical Issues | 2 (A1, A2 — stub spec/plan) |
| High Issues | 4 (B1, B2, B3, C1) |
| Medium Issues | 3 (C2, D1, D2) |
| Low Issues | 4 (E1, F1, F2, G1) |

---

## Next Actions

### CRITICAL — Resolve before `/speckit.implement`

1. **A1+A2: Stub spec/plan** — Two options:
   - **(A) Accept pitch-as-spec**: Add a header to tasks.md formally declaring pitch.md as the authoritative spec+plan. This is pragmatic and sufficient given the pitch quality.
   - **(B) Generate proper spec/plan**: Run `/speckit.specify` and `/speckit.plan` to produce full artifacts. Adds ~2h but creates proper audit trail.
   - **Recommendation**: Option A — the pitch.md is exceptionally detailed (205 lines with code samples, file references, and acceptance criteria). Generating formal spec/plan would be largely duplicative.

2. **C1: Verify tool_use_count field** — Expand T001 scope to also verify what field in `claude -p` JSON tracks tool call count. Without this, T010-T012 cannot be implemented correctly.

### HIGH — Fix before or during implementation

3. **C2: skip_condition evaluator** — T023 underestimates this. Either:
   - Build a minimal expression evaluator (ast.literal_eval or simple string matching)
   - Simplify to `skip: true/false` controlled by the executor (evaluate appetite externally)
   - **Recommendation**: Evaluate appetite in dag_executor.py, pass boolean to Node.skip_condition

4. **B2: Clarify T005 scope** — parse_claude_output() is already wired in all 3 dispatch paths. T005 may be a no-op. Adjust description to "validate field names match, adjust only if T001 finds mismatches."

### MEDIUM — Address during implementation

5. **D2: Hallucination whitelist** — Add a task or explicitly defer to future scope.
6. **C3: WARNING vs REJECT** — Ensure contract doc uses WARNING per user decision.
7. **D1: Portal contingency** — Note that if T007 finds issues, a new task is needed.

---

## Confidence Assessment

**Confidence: Média**

**Justification**: The tasks.md is well-structured with clear dependencies and TDD approach. However, two foundational artifacts (spec.md, plan.md) are stubs, and three key assumptions are unverified: (1) claude JSON output field names, (2) tool_use_count field existence, (3) skip_condition evaluator capability. These could cause scope changes in 30% of tasks.

**Kill criteria**: If `claude -p --output-format json` does not expose token usage AND tool call count, both US1 and US2 require significant redesign (alternative: parse from conversation history or prompt claude to report usage).

---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "13 findings (2 CRITICAL, 4 HIGH, 3 MEDIUM, 4 LOW). CRITICALs are stub spec/plan (recommend accepting pitch-as-spec) and unverified tool_use_count field. Coverage 88%. Recommend resolving C1 (expand T001 scope) and C2 (skip_condition evaluator) before starting implementation."
  blockers: []
  confidence: Media
  kill_criteria: "If claude -p JSON output lacks token usage and tool call count fields, US1 and US2 need redesign."
