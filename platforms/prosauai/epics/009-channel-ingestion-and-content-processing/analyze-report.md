# Specification Analysis Report — Epic 009

**Epic**: Channel Ingestion Normalization + Content Processing
**Branch**: `epic/prosauai/009-channel-ingestion-and-content-processing`
**Date**: 2026-04-19
**Artifacts**: spec.md (32 FR, 16 SC, 7 US), plan.md, tasks.md (164 tasks, 11 phases)
**Mode**: READ-ONLY consistency audit (pre-implement)

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | **CRITICAL** | tasks.md T010 + T104 | `ContentBlock` declared `frozen=True` in T010, but T104 says "Update `block.text = result.text_representation`". Frozen Pydantic models reject attribute mutation → runtime `ValidationError` at pipeline step. T104 footnote ("or pass via sidecar field in ConversationRequest if frozen prevents") acknowledges the conflict but defers the decision. | Resolve before PR-A: either (a) drop `frozen=True` on `ContentBlock` and document invariant in docstring + test; or (b) define a sidecar `ProcessedBlock` list on `ConversationRequest` + update data-model.md §2. Add explicit task instead of "or" clause. |
| C1 | Coverage Gap | HIGH | spec.md SC-002; tasks.md Phase 5 | SC-002 requires image p95 < 9s end-to-end, but no benchmark task exists for images (audio has T094, image has none). | Add `tests/benchmarks/test_image_e2e.py` task mirroring T094, gated on SC-002. |
| C2 | Coverage Gap | HIGH | spec.md SC-003; tasks.md Phase 7 | SC-003 requires document p95 < 10s, no benchmark task. Local extraction is fast so risk is low, but the SC has no enforcing test. | Add document benchmark task (or explicitly waive in plan Complexity Tracking with justification). |
| C3 | Coverage Gap | MEDIUM | spec.md FR-027; plan.md Risk R4 | FR-027 ("no raw bytes persisted") is asserted as constraint. Plan.md R4 mitigation promises "CI regex bloqueante" to search for `open(...).write` in processors, but no task creates this lint/CI rule. | Add Phase 10 task: "Add ruff/pre-commit rule or CI grep guard rejecting `open(..., 'wb')` / `Path.write_bytes` inside `apps/api/prosauai/processors/`". |
| C4 | Coverage Gap | MEDIUM | spec.md FR-032 | FR-032: "Cada marker de fallback MUST ser registrado no trace (`content_process.output.marker`)". No unit/integration test asserts marker field reaches trace step output. | Add assertion in T064 (budget fallback) and a new unit test in test_content_process_step.py checking `output.marker == "[budget_exceeded]"`. |
| A1 | Ambiguity | MEDIUM | plan.md Project Structure vs tasks.md T195 | Plan references `apps/api/prosauai/pipeline.py` (module file). Tasks create `apps/api/prosauai/pipeline/steps/content_process.py` and wire in `pipeline/__init__.py` (package). SC-013 gate test T195 checks `git diff ... pipeline.py` — if pipeline becomes a package, the gate would miss changes in `pipeline/__init__.py`. | Normalize: update T195 to `pipeline/` (directory) and `pipeline.py` (file) for full coverage; or commit to package form and update plan.md structure diagram to match. |
| A2 | Ambiguity | LOW | spec.md FR-017 + plan.md "feature flag reload" | FR-017 says poll 60s. plan.md Assumptions/Technical Context adds "min 10" env bound. Spec does not define behavior when operator sets interval < 10 or reload fails mid-parse. | Tighten FR-017: add "parse-first-then-swap; on parse error, retain previous in-memory registry and emit `config.reload.error` metric." (T072 already implements this; move the invariant into spec.) |
| A3 | Ambiguity | LOW | spec.md FR-023 (circuit breaker) | Breaker state is worker-local (contracts/content-processor.md §8, T078). Spec FR-023 does not disclose that two workers may observe different breaker states, so effective thresholds scale with worker count. | Add one-line note to FR-023 or Assumptions: "Breaker state is per-worker; aggregate threshold scales linearly with worker count." |
| U1 | Underspecification | LOW | spec.md FR-026 + tasks.md T122/T125 | "Camada de mascaramento PII existente" referenced but spec does not list which PII classes are covered. SC-012 implicitly tests CPF, card, address, email, telephone; coverage of RG, CNH, plate, CNPJ is unstated. | Spec: enumerate covered PII classes explicitly in FR-026 Key Entities addendum (reuse list from output_guard module). |
| D1 | Duplication | LOW | pitch.md "Captured Decisions" (22 items) vs decisions.md | Both files contain the same 22 decisions. Expected given the seed-from-pitch pattern, but any future edit risks drift. | Add a single-line note at top of pitch.md Captured Decisions: "Authoritative source: decisions.md. This copy is a snapshot at epic start." |
| I2 | Inconsistency | LOW | pitch.md §Dependencies "ADR-036 reservado" vs plan.md ADR list | Pitch reserves ADR-036 for follow-ups; plan.md lists ADRs 030-035 only (no 036). Not a blocker, just informational drift. | Either add ADR-036 placeholder to plan.md roadmap, or drop the reservation from pitch. |
| U2 | Underspecification | LOW | spec.md SC-016 cost projection accuracy | "Erro de projeção ≤10% após 7 dias" — the metric is measurable but the comparison method (observed vs projected) is not defined (moving avg? linear extrapolation?). | Spec: add "Methodology: `(projected_monthly - observed_monthly) / observed_monthly`, projection = `spent_day_1..7 / 7 * 30`." |
| A4 | Ambiguity | LOW | tasks.md T104 "sidecar field" | T104 introduces a new concept ("sidecar field in ConversationRequest if frozen prevents") that is not defined in data-model.md. If chosen as solution for I1, it is underspecified. | Upstream to data-model.md: define `ConversationRequest.processed_content: dict[block_idx, ProcessedContent]` and reference it explicitly. |

**Total**: 12 findings (1 CRITICAL, 2 HIGH, 3 MEDIUM, 6 LOW). Overflow: 0.

---

## Coverage Summary (FR → Task)

FR-by-FR mapping (abridged; full mapping in section below):

| FR | Has Task? | Task IDs | Notes |
|----|-----------|----------|-------|
| FR-001 multi-channel webhooks | Yes | T041, T204 | — |
| FR-002 canonical normalize | Yes | T010, T037, T203 | — |
| FR-003 new-channel via adapter only | Yes | T195 (SC-013) | Test-only gate; no implementation task because inversion is a non-action |
| FR-004 idempotency sha256 | Yes | T011, T037, T203 | — |
| FR-005 webhook alias | Yes | T042, T044 | — |
| FR-006 ContentBlock kinds | Yes | T010 | — |
| FR-007 processor → text_representation | Yes | T018, T027 | — |
| FR-008 audio transcription | Yes | T101 | — |
| FR-009 image description (detail mode) | Yes | T121 | — |
| FR-010 document extraction | Yes | T161 | — |
| FR-011 unsupported kinds | Yes | T175, T184 | — |
| FR-012 multi-message flush | Yes | T046, T093 | — |
| FR-013 trace content_process step | Yes | T029, T106, T124, T163 | — |
| FR-014 media_analyses persist | Yes | T021, T105, T140 | — |
| FR-015 processor_usage_daily | Yes | T074, T076 | — |
| FR-016 old traces compat | Yes | T025, T026 | — |
| FR-017 feature flags granular | Yes | T070-T073 | See A2 |
| FR-018 budget exceeded fallback | Yes | T064, T076, T081 | — |
| FR-019 feature disabled fallback | Yes | T060, T081 | — |
| FR-020 reject >25MB | Yes | T101 | — |
| FR-021 base64 inline | Yes | T037, T101 | — |
| FR-022 cache policy | Yes | T063, T077 | — |
| FR-023 circuit breaker | Yes | T062, T078 | See A3 |
| FR-024 retry with jitter | Yes | T101 | Retry logic embedded in AudioProcessor; no dedicated retry-utility test |
| FR-025 hallucination filter | Yes | T102 | — |
| FR-026 PII mask | Yes | T122, T125 | See U1 |
| FR-027 no raw bytes | **Partial** | T101, T121 (implicit) | See C3 — no CI/lint guard |
| FR-028 retention 14d/90d | Yes | T024 | — |
| FR-029 webhook auth | Yes | T036, T192, T202 | — |
| FR-030 zero regression | Yes | T050, T222 | — |
| FR-031 marker + LLM fallback | Yes | T081 | — |
| FR-032 marker in trace | **Partial** | T106, T124 | See C4 — no explicit assertion |

**Coverage**: 30/32 FRs fully covered + 2 partial = **93.75%** explicit.

SC-by-SC mapping:

| SC | Has Gating Task? | Task IDs |
|----|------------------|----------|
| SC-001 audio p95 <8s | Yes | T094 |
| SC-002 image p95 <9s | **NO** (see C1) | — |
| SC-003 document p95 <10s | **NO** (see C2) | — |
| SC-004 zero silent drops | Yes | T176 |
| SC-005 trace visibility | Yes | T130 |
| SC-006 admin diag <5min | Post-launch UX claim | — |
| SC-007 cache hit ≥30% | Post-launch metric | — |
| SC-008 budget graceful | Yes | T064 |
| SC-009 text latency ≤baseline+5ms | Yes | T051 |
| SC-010 173+191 tests | Yes | T050, T222 |
| SC-011 hallucination ≤2% | Post-launch sampling | Methodology OK |
| SC-012 zero PII leak | Unit + post-launch | T125 + sampling |
| SC-013 MetaCloud diff zero | Yes | T195 |
| SC-014 MetaCloud canonical valid | Yes | T193, T201 |
| SC-015 kill switch <2min | Yes | T065 |
| SC-016 cost projection ±10% | Partial | T220 (projection only); see U2 |

---

## Constitution Alignment Issues

None. Plan.md §Constitution Check documents all 9 principles as ✅ with justifications. No MUST principle is violated.

---

## Unmapped Tasks

Scanned T001-T224 + T1100-T1105. All tasks trace to at least one FR, SC, or structural/governance concern (Setup/Foundational/Polish/Smoke). Zero unmapped tasks.

---

## Metrics

- **Total Functional Requirements**: 32 (FR-001..FR-032)
- **Total Success Criteria**: 16 (SC-001..SC-016)
- **Total User Stories**: 7 (US1..US7)
- **Total Tasks**: 164 (counted via `- [ ] T` prefix)
- **Coverage** (FR with ≥1 task, partial counted as 0.5): (30 + 2×0.5)/32 = **96.9%**
- **Ambiguity Count**: 4 (A1..A4)
- **Duplication Count**: 1 (D1)
- **Critical Issues**: 1 (I1)
- **Inconsistencies**: 2 (I1, I2)
- **Coverage gaps**: 4 (C1..C4)
- **Underspecification**: 2 (U1, U2)

---

## Next Actions

### Must resolve before `/speckit.implement` (blocks PR-A)

1. **I1 (CRITICAL)** — Decide the frozen-ContentBlock vs. mutation conflict. Recommended: keep `frozen=True` on ContentBlock (immutability is a stated invariant in data-model), and add `ConversationRequest.processed_content: dict[int, ProcessedContent]` sidecar. Update T010, T032, T104, data-model.md §2.4.

### Should resolve before PR-B merge

2. **C1 + C2** — Add image + document benchmark tasks (SC-002/SC-003 gates).
3. **C3** — Add CI regex/lint task in Phase 10 enforcing "no raw bytes write" inside `processors/`.
4. **C4** — Strengthen marker-in-trace assertions (extend T031 + T064).

### Nice-to-have (can defer to PR-C or epic 010 retrospective)

5. **A1** — Normalize pipeline path reference across plan/tasks/T195.
6. **A2, A3, U1, U2** — Tighten spec wording (small edits).
7. **D1, I2** — Housekeeping notes in pitch.md.

### Suggested commands

- For I1 fix: `/speckit.plan` re-invocation is overkill; a scoped spec + data-model edit suffices. Manual edit to data-model.md §2.4 + tasks.md T104 + T010 docstring.
- For C1/C2: append tasks directly into `tasks.md` Phase 5 and Phase 7 respectively.
- For C3: add to Phase 10 Polish.
- Re-run `/speckit.analyze` after fixes to verify resolution.

---

## Remediation Offer

Would you like me to draft concrete edits for the top 4 issues (I1, C1, C2, C3)? The changes would touch:
- `data-model.md` §2.4 (add `processed_content` sidecar)
- `tasks.md` T010, T032, T104 (resolve frozen conflict); Phase 5 (+1 benchmark task); Phase 7 (+1 benchmark task); Phase 10 (+1 CI guard task)
- `spec.md` FR-027 (no-op if we choose not to add CI guard)

No edits applied yet. Awaiting approval.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "12 findings: 1 CRITICAL (frozen ContentBlock vs mutation in T104), 2 HIGH (missing image/document perf benchmarks for SC-002/SC-003), 3 MEDIUM (raw-bytes CI guard FR-027, marker-in-trace assertion FR-032, pipeline path ambiguity). FR coverage 96.9%, no constitution violations, no unmapped tasks. Recommend resolving I1 before PR-A coding begins."
  blockers:
    - "I1: ContentBlock frozen=True conflicts with T104 mutation — must pick sidecar vs drop-frozen before PR-A."
  confidence: Alta
  kill_criteria: "Report invalidated if spec/plan/tasks are edited after this analysis without re-running /speckit.analyze."
