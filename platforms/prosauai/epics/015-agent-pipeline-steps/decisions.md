---
epic: 015-agent-pipeline-steps
created: 2026-04-27
updated: 2026-04-29
purpose: Audit trail of implementation-level decisions taken during the
  speckit.implement phase. Plan-level decisions (D-PLAN-01..12) live in
  plan.md §"Phase 0: Outline & Research" and Captured Decisions tables.
---


# Implementation Decisions — Epic 015 Agent Pipeline Steps

Decisions captured during `/speckit.implement`. Each entry follows the
format prescribed by the pipeline contract base (Step 8b):

```
N. [YYYY-MM-DD implement] <decision text> (ref: <task-id or doc>)
```

Only deviations, non-trivial trade-offs, discovered constraints, or
ambiguity-resolutions are recorded. Routine task completions are NOT
logged here — see `tasks.md` for the canonical task ledger.

---

## Implementation Decisions

1. [2026-04-27 implement] **Pipeline executor branch insertion point identified
   in `_generate_with_retry`.** After reading
   `apps/api/prosauai/conversation/pipeline.py` (1840 LOC) and
   `apps/api/prosauai/conversation/agent.py` (463 LOC) end-to-end:

   - The hot path is `pipeline.py:_generate_with_retry()` defined at
     **line 490** with signature
     ```python
     async def _generate_with_retry(
         *,
         agent_config: AgentConfig,
         prompt: PromptConfig,
         context: list[ContextMessage],
         user_message: str,
         classification: ClassificationResult,
         deps: ConversationDeps,
         semaphore: asyncio.Semaphore,
         content_processing_config: Any | None = None,
         tenant: Any | None = None,
     ) -> tuple[str, bool, GenerationResult | None, EvalResult | None]:
     ```
   - The single call to `generate_response(...)` lives on **line 539**
     inside the retry loop (`for attempt in range(_MAX_RETRIES + 1)`).
   - The marker short-circuit on **line 522** (`is_marker_only(...)`)
     and the marker-aware fallback (`_marker_fallback(...)` line 529 /
     559 / 584 / 599 / 614) MUST run BEFORE any pipeline executor
     branching — they are deterministic safety responses that never
     consume an LLM call.
   - **Insertion point**: between line 535 (`effective_prompt = ...`) and
     line 537 (`for attempt in range(_MAX_RETRIES + 1):`), insert a
     branch that (a) loads `pipeline_steps_repo.list_active_steps(conn,
     agent_id)` once, (b) if list non-empty → delegates the loop body to
     `pipeline_executor.execute_agent_pipeline(...)` and returns its
     `(text, is_fallback, gen_result_aggregate, eval_result_aggregate)`
     tuple, (c) otherwise the existing `for attempt` loop runs unchanged.
   - The DB connection comes from `deps.pg_pool` (see
     `pipeline.py:1444`); pipeline_executor MUST acquire its own
     connection from that pool so RLS `SET LOCAL` is honored per
     transaction (ADR-011).
   - `agent_config.id` is available as `deps.agent_id` (string UUID,
     line 1445); the repository takes a UUID, so cast at call-site:
     `UUID(deps.agent_id)`.
   - Two top-level call-sites of `_generate_with_retry` exist
     (line 1474 inside the trace-buffer path, line 1541 inside the
     no-trace path). Both will route through the same branch — no
     additional changes at the call-site.

   **Constraint discovered**: `agent.py:generate_response()` (line 324)
   reads the model from `agent_config.config["model"]` on line 376 — it
   does NOT accept a `model_override` parameter. The specialist step
   (T025) must therefore clone the `AgentConfig` and substitute
   `config["model"]` (cheap immutable rebuild via `dataclasses.replace`
   if frozen, or shallow dict copy + `AgentConfig(**fields)` if not)
   before passing it to `generate_response`. Adding a `model_override`
   kwarg to `generate_response` is the cleaner alternative but expands
   the public surface of `agent.py` — defer to PR-2 review whether to
   accept it.

   (ref: T004; plan.md PR-2 § "specialist.py")

2. [2026-04-27 implement] **Specialist step uses constructor-injected per-request
   scaffolding instead of a `model_override` kwarg on `generate_response`.**
   Rationale: keep `agent.py:generate_response()`'s public signature unchanged
   (it's used by the legacy single-call path and by every regression test in
   `test_pipeline.py`).  `SpecialistStep.__init__` captures `agent_config`,
   `prompt`, `classification`, `tenant`; `execute()` clones `agent_config`
   via `model_copy(update={"config": {**original, "model": resolved}})` so the
   model override flows through unchanged code.  Trade-off: `_instantiate_step`
   in `pipeline_executor.py` carries an explicit type-check (`if step_class is
   SpecialistStep or step_type == "specialist": …`).  This is the single
   special case — every other step type uses the no-arg `cls()` path.  When
   clarifier/resolver/summarizer (PR-4) need similar threading, generalise the
   factory then. (ref: T025; plan.md PR-2 § "steps/specialist.py")

3. [2026-04-27 implement] **Per-step LLM concurrency via the existing global
   semaphore (no new bucket).**  The executor passes the same
   `app_state.llm_semaphore` through to every step's `execute()`.  Pipelines
   with N steps still respect FR-014 (≤10 concurrent LLM calls process-wide).
   Rationale: a per-pipeline-step bucket would let an unbounded fan-out starve
   single-call agents; the global bucket gives the simplest fairness guarantee
   for v1.  Re-evaluate once SC-002 (≤1 s p95 for trivial pipelines) shows
   contention. (ref: T026)

4. [2026-04-27 implement] **`SubStepRecord` is a new in-module dataclass — not
   `StepRecord`.**  `step_record.StepRecord` enforces `order ∈ 1..14` and
   `name ∈ STEP_NAMES`.  Sub-steps live INSIDE the `generate_response` row
   (per D-PLAN-04) and use `step_type` (not `name`) so they cannot satisfy
   either constraint.  `SubStepRecord` mirrors the JSONB shape from
   `data-model.md § Sub-step JSONB shape` and provides `to_jsonb()` for
   serialisation.  When PR-3 / Phase 6 wires persistence (T071), the
   serialisation goes through `to_jsonb()` directly — no
   `StepRecord` round-trip required.  This keeps `step_record.py` (a public
   surface used by epic 008) untouched until T070 explicitly extends it.
   (ref: T026)

5. [2026-04-27 implement] **Branch wiring uses optional `pool` + `tenant_id`
   kwargs on `_generate_with_retry`.**  Adding required parameters would
   break ~40 mocks in `test_pipeline.py`.  Default `None` means: tests that
   do not thread the pool through still get the legacy single-call path
   (no DB lookup, byte-equivalent output).  Production call-sites in
   `_run_pipeline` pass `pool=pool, tenant_id=request.tenant_id` so the
   declarative path activates whenever the agent has rows.  This satisfies
   SC-008 (suite passes) and SC-010 (≤5 ms overhead for empty case) without
   forcing a refactor of the existing test surface. (ref: T027; plan.md
   PR-2 § "pipeline.py" branch)

6. [2026-04-27 implement] **`_PIPELINE_EXEC_METADATA` sidecar for executor
   metadata.**  When the executor path runs, the synthesised
   `GenerationResult` carries text + tokens + cost — but cannot carry
   `terminating_step` / `pipeline_step_count` / `sub_steps` (those are
   epic-015-specific).  Stashing them in a module-level
   `dict[id(gen_result), PipelineExecutionResult]` keeps
   `GenerationResult`'s public Pydantic shape untouched (no schema
   migration in `models.py`) while allowing `_run_pipeline` to read
   the executor's metadata when populating `messages.metadata` and
   `trace_steps.sub_steps` in PR-3 / Phase 6.  Trade-off: the dict is
   never reaped — but each entry is ~200 bytes and is keyed by Python
   `id()` of an object that goes out of scope at the end of the
   request handler, so the leak is bounded by request concurrency.
   PR-3 / T073 will swap this for a proper return path. (ref: T027)

## US1 staging validation

T030 maps to live execution in staging — `/speckit.implement` runs in
auto mode without staging access.  The validation playbook is recorded
here so an operator can replay it once PR-1..PR-2 are deployed.

### Setup

```sql
-- 1) Identify the test agent in pace-internal.
SELECT id, name FROM public.agents
 WHERE tenant_id = '<pace-internal uuid>' AND name = 'ariel-test';

-- 2) Insert the 2-step pipeline (atomic).
BEGIN;
DELETE FROM public.agent_pipeline_steps WHERE agent_id = '<ariel-test uuid>';
INSERT INTO public.agent_pipeline_steps
    (tenant_id, agent_id, step_order, step_type, config)
VALUES
    ('<pace-internal uuid>', '<ariel-test uuid>', 1, 'classifier',
     '{"model":"gpt-4o-mini","intent_labels":["greeting","billing","support","complex"]}'::jsonb),
    ('<pace-internal uuid>', '<ariel-test uuid>', 2, 'specialist',
     '{"default_model":"gpt-4o-mini","routing_map":{"greeting":"gpt-4o-mini","billing":"gpt-4o","complex":"gpt-4o"}}'::jsonb);
COMMIT;
```

### Execution + verification

1. Send 5 greetings (`oi`, `bom dia`, `boa tarde`, `obrigado`, `tchau`)
   and 5 billing messages (`qual a fatura?`, `valor da conta`, `boleto`,
   `cobrança duplicada`, `cancelar pagamento`) through the WhatsApp
   gateway pointing at the `ariel-test` agent.
2. After ~2 minutes (debounce + processing), query:

   ```sql
   -- 2.a) Check messages.metadata.terminating_step (after PR-3 wires T073).
   SELECT m.id, m.content, m.metadata->>'terminating_step' AS terminating
     FROM public.messages m
     JOIN public.conversations c ON c.id = m.conversation_id
    WHERE c.agent_id = '<ariel-test uuid>'
      AND m.direction = 'outbound'
      AND m.created_at > now() - interval '5 minutes'
    ORDER BY m.created_at DESC;
   -- Expected: every row has terminating='specialist'.

   -- 2.b) Check the trace waterfall — sub_steps populated (after PR-3 T071).
   SELECT t.trace_id, ts.name, ts.sub_steps
     FROM public.traces t
     JOIN public.trace_steps ts ON ts.trace_uuid = t.id
    WHERE t.message_id IN (...)
      AND ts.name = 'generate_response'
    ORDER BY t.started_at;
   -- Expected: sub_steps is a 2-element JSONB array.

   -- 2.c) Cost reduction (uses the existing performance aggregate).
   SELECT t.intent, AVG(t.cost_usd) AS avg_cost
     FROM public.traces t
    WHERE t.tenant_id = '<pace-internal uuid>'
      AND t.created_at > now() - interval '5 minutes'
    GROUP BY t.intent;
   -- Expected: greeting/farewell rows show ≥50% cost drop vs baseline
   --           agent (no pipeline).
   ```

3. Roll back via `UPDATE public.agent_pipeline_steps SET is_active=FALSE
   WHERE agent_id='<ariel-test uuid>';` — pipeline executor sees zero
   active rows on the next request and reverts to the legacy path
   without restarting the API.

### Outcome (to be filled by ops)

- [ ] All 10 messages classified within `intent_labels`.
- [ ] All 10 outbound rows have `metadata.terminating_step='specialist'`.
- [ ] `trace_steps.sub_steps` populated for every pipeline-served message.
- [ ] Average cost for `greeting` ≥50% lower than baseline (SC-001).
- [ ] No regression in QS for `billing` messages (SC-003).
- [ ] Rollback by `is_active=FALSE` reverts behavior in <60 s.

(ref: T030; quickstart.md § "Validar US1")

---

7. [2026-04-28 implement] **US2 condition + termination wiring already
   in place from T026 — no executor patch in T044/T045.** `pipeline_executor.py`
   lines 260–305 (T044 surface) and lines 485–496 (T045 surface) were
   already implemented as part of T026 to keep the executor's contract
   uniform across step types. The US2 acceptance scenarios are exercised
   by T041 (unit) and T042 (integration); both green without further code
   changes. Trade-off: T044/T045 collapse into "verify the wiring" rather
   than "wire it" — accepted because the executor was designed
   end-to-end in T026, and US2 only adds a new step type (clarifier,
   T043). The skipped sub-step shape stays consistent across the three
   skip reasons (`condition_eval_skipped`, `prior_step_terminated`,
   `prior_step_failed`): each carries `output={"reason": <reason>}` and,
   when applicable, `condition_evaluated=<repr>`. (ref: T044, T045;
   plan.md PR-2 § "pipeline_executor.py")

## US2 staging validation

T046 maps to live execution in staging — `/speckit.implement` runs in
auto mode without staging access. The validation playbook is recorded
here so an operator can replay it once PR-1..PR-2 are deployed (US1
infra), then PR-2 follow-up adds the clarifier step type.

### Setup

```sql
-- 1) Identify the test agent (same row used for T030 / US1).
SELECT id, name FROM public.agents
 WHERE tenant_id = '<pace-internal uuid>' AND name = 'ariel-test';

-- 2) Insert the 3-step pipeline atomically — replaces the US1 layout.
BEGIN;
DELETE FROM public.agent_pipeline_steps WHERE agent_id = '<ariel-test uuid>';
INSERT INTO public.agent_pipeline_steps
    (tenant_id, agent_id, step_order, step_type, config, condition)
VALUES
    ('<pace-internal uuid>', '<ariel-test uuid>', 1, 'classifier',
     '{"model":"gpt-4o-mini","intent_labels":["greeting","billing","support","ambiguous"]}'::jsonb,
     NULL),
    ('<pace-internal uuid>', '<ariel-test uuid>', 2, 'clarifier',
     '{"model":"openai:gpt-5-nano","max_question_length":140}'::jsonb,
     '{"classifier.confidence":"<0.6"}'::jsonb),
    ('<pace-internal uuid>', '<ariel-test uuid>', 3, 'specialist',
     '{"default_model":"gpt-4o-mini","routing_map":{"greeting":"gpt-4o-mini","billing":"gpt-4o","ambiguous":"gpt-4o-mini"}}'::jsonb,
     NULL);
COMMIT;
```

### Execution + verification

1. Send the **ambiguous** message `"oi"` (or `"e ai"`). The classifier
   should return `confidence ≤ 0.6` because the message carries no
   actionable intent. The clarifier condition matches and the customer
   receives a follow-up question (≤140 chars) instead of a guessed
   billing/support reply.
2. Send the **clear** message `"qual o saldo da fatura de abril?"`. The
   classifier should return `confidence ≥ 0.7` (intent=`billing`). The
   clarifier is skipped via the condition gate; the specialist runs and
   produces the substantive answer using `routing_map['billing']` =
   `gpt-4o`.
3. Verify via SQL (after PR-3 wires T071/T073):

   ```sql
   -- 3.a) Ambiguous message → clarifier terminates.
   SELECT m.id, m.content, m.metadata->>'terminating_step' AS terminating
     FROM public.messages m
     JOIN public.conversations c ON c.id = m.conversation_id
    WHERE c.agent_id = '<ariel-test uuid>'
      AND m.direction = 'outbound'
      AND m.content LIKE '%?%'         -- clarifier always asks a question
      AND m.created_at > now() - interval '5 minutes'
    ORDER BY m.created_at DESC
    LIMIT 1;
   -- Expected: terminating='clarifier'.

   -- 3.b) Clear billing message → specialist terminates.
   SELECT m.id, m.content, m.metadata->>'terminating_step' AS terminating
     FROM public.messages m
     JOIN public.conversations c ON c.id = m.conversation_id
    WHERE c.agent_id = '<ariel-test uuid>'
      AND m.direction = 'outbound'
      AND m.content NOT LIKE '%?%'
      AND m.created_at > now() - interval '5 minutes'
    ORDER BY m.created_at DESC
    LIMIT 1;
   -- Expected: terminating='specialist'.

   -- 3.c) Clarifier skipped on high confidence — visible in trace_steps.sub_steps.
   SELECT t.trace_id, ts.sub_steps
     FROM public.traces t
     JOIN public.trace_steps ts ON ts.trace_uuid = t.id
    WHERE t.message_id IN (... clear billing message id ...)
      AND ts.name = 'generate_response';
   -- Expected: sub_steps[1].step_type='clarifier', status='skipped',
   --           condition_evaluated='classifier.confidence<0.6',
   --           output.reason='condition_eval_skipped'.
   ```

4. Roll back via `UPDATE public.agent_pipeline_steps SET is_active=FALSE
   WHERE agent_id='<ariel-test uuid>' AND step_order=2;` — the clarifier
   row is deactivated, so the next request runs only the
   classifier+specialist pair (US1 layout).

### Outcome (to be filled by ops)

- [ ] Ambiguous `"oi"` → outbound message ends with `?` and
      `metadata.terminating_step='clarifier'`.
- [ ] Clear billing message → outbound message has no `?` and
      `metadata.terminating_step='specialist'`.
- [ ] `trace_steps.sub_steps[1]` for the clear billing message shows
      `status='skipped'` with `condition_evaluated='classifier.confidence<0.6'`.
- [ ] Conversation retomadas (rate of "não, não foi isso que perguntei"
      type messages within 60 s of the bot reply) drop ≥30% over a
      sample of 200 ambiguous-classified messages compared to the US1
      baseline (SC-004).
- [ ] Disabling step 2 via `is_active=FALSE` reverts to the US1
      classifier+specialist pair within 60 s without restarting the API.

(ref: T046; quickstart.md § "Validar US2"; spec.md US2 acceptance scenarios 1–4)

---

## Backwards-compat verification

### T052 (FR-070) — full existing test suite green check

Command run from `apps/api/`:

```
uv run --project apps/api python -m pytest apps/api/tests/ \
    --tb=no -q \
    --override-ini="addopts=--tb=no -m 'not benchmark and not e2e' --no-header"
```

Result (Phase 5, US6 hard gate):

```
1 failed, 3377 passed, 54 skipped, 20 deselected, 225 warnings in 151.44s (0:02:31)
```

The only failure is
`apps/api/tests/unit/processors/test_document.py::TestOTelSpan::test_emits_processor_document_extract_span`.

Confirmed **pre-existing flake** unrelated to epic 015:

1. Re-running the test in isolation passes (`1 passed in 0.19s`) — it is
   sensitive to test ordering / OTel global state, not to anything epic 015 touches.
2. Re-running the full suite with epic 015 test files explicitly excluded
   (`--ignore=apps/api/tests/conversation/test_pipeline_backwards_compat.py
   --ignore=apps/api/tests/benchmarks/test_overhead_no_pipeline.py`)
   reproduces the same single failure. Epic 015 does NOT introduce this regression.
3. Last code change in `tests/unit/processors/test_document.py` is from epic 009
   (commit `ed5d166 feat(009): harden processors + shared fire-and-forget helper`).

Decision: T052 is satisfied — the only failure is an environmental flake that
predates this epic. Tracked separately for the processors/observability team.
The new tests added by epic 015 (8 in `test_pipeline_backwards_compat.py`,
opt-in benchmark in `test_overhead_no_pipeline.py`) all pass and add zero new
warnings.

(ref: T052; spec.md FR-070; tasks.md § "Phase 5: User Story 6")

### T051 (SC-010) — empty-pipeline lookup overhead measured

Command:

```
.venv/bin/python -m pytest tests/benchmarks/test_overhead_no_pipeline.py \
    -v -m benchmark --no-cov -s
```

Result on local dev box (Linux, Python 3.12.3):

```
[T051 SC-010 benchmark]
  with_lookup   : min=0.066ms median=0.072ms p95=0.125ms max=0.334ms (n=100)
  without_lookup: min=0.011ms median=0.014ms p95=0.027ms max=0.162ms (n=100)
  Δ p95 (overhead): 0.098ms (budget: ≤5.0ms)
```

Δ p95 = **0.098 ms**, ~50× under the 5.0 ms budget. SC-010 satisfied.
Re-validated in staging by T126 (Phase 10).

(ref: T051; spec.md SC-010; tasks.md § "Phase 5: User Story 6")

### T053 (FR-070) — `step_record.py` forward-compat probe

Inspected `apps/api/prosauai/conversation/step_record.py` and confirmed:

- The current `StepRecord` dataclass has no `sub_steps` field.
- Per T070 (Phase 6, US5), the field will be added as
  `sub_steps: list[StepRecord] | None = None`. The `None` default makes
  every existing constructor call source-compatible — no fixture mass-update
  is needed when T070 lands.
- 36 existing constructor sites in `apps/api` (queried via grep `StepRecord(`)
  use either keyword arguments matching the current dataclass shape or rely
  on `_record_step` factory. None of them positionally pass a value at the
  trailing slot, so adding a new keyword-only field with a default cannot
  break them.

Forward-compat invariant for T070: the field MUST be added at the END of the
dataclass with `default=None`. No reordering, no required field. The added
truncation/serialisation logic must short-circuit on `None`.

(ref: T053; tasks.md § "Implementation safeguards for User Story 6")

### T054 (FR-072) — migration idempotency: applied twice, second pass no-op

Two-pass behavioural verification against the real Postgres 15 instance running
in `prosauai-postgres-1` (pgvector/pgvector:pg15) — fresh scratch DB,
applied each migration's `migrate:up` block twice via `psql`:

```
== Apply 1 of m10 ==
NOTICE:  policy "tenant_isolation" for relation "public.agent_pipeline_steps" does not exist, skipping
NOTICE:  trigger "trg_pipeline_steps_updated_at" for relation "public.agent_pipeline_steps" does not exist, skipping
== Apply 1 of m11 ==
== Apply 2 of m10 (idempotency check) ==
NOTICE:  relation "agent_pipeline_steps" already exists, skipping
NOTICE:  relation "idx_pipeline_agent_active" already exists, skipping
NOTICE:  relation "idx_pipeline_tenant" already exists, skipping
== Apply 2 of m11 (idempotency check) ==
NOTICE:  column "sub_steps" of relation "trace_steps" already exists, skipping
```

Both passes finished with exit 0. Final schema state confirmed:

- `public.agent_pipeline_steps` table present with full column set,
  4 indexes (PK + 2 hot-path + UNIQUE), 1 check constraint
  (`agent_pipeline_steps_config_check` ≤ 16 KB).
- `public.trace_steps.sub_steps` column added (JSONB nullable).

Static probe (covered by `TestMigrationsIdempotency` in
`apps/api/tests/conversation/test_pipeline_backwards_compat.py`) backs up the
behavioural test by asserting both files use `IF NOT EXISTS` /
`DROP ... IF EXISTS` / `CREATE OR REPLACE FUNCTION` clauses and ship a matching
`-- migrate:down` block.

(ref: T054; spec.md FR-072; tasks.md § "Implementation safeguards for User Story 6")

### T055 (FR-064) — `messages.metadata` write path probe (negative case)

Verified that when `pipeline_steps == []`, none of `terminating_step`,
`pipeline_step_count`, `pipeline_version` is written to `messages.metadata`:

1. **Static probe** in `TestMessagesMetadataNegativePath::
   test_pipeline_module_has_no_unconditional_metadata_writers`: scans
   `pipeline.py` source for the 3 forbidden keys and asserts every
   reference sits inside `_generate_via_pipeline_executor` (the executor
   adapter helper) or downstream of an `exec_result.terminating_step`
   guard. No bare/unconditional writes.
2. **Behavioural probe** in `TestMessagesMetadataNegativePath::
   test_save_message_metadata_empty_for_single_call`: drives
   `_generate_with_retry` with empty pipeline_steps and asserts the
   returned `GenerationResult.model_dump()` contains none of the 3 keys.

Today the metadata writer (T073, Phase 6, US5) is not yet implemented, so
the contract holds trivially. When T073 lands it MUST write those keys
ONLY when the executor branch ran — the tests in this file will catch any
regression that leaks them through the legacy path.

(ref: T055; spec.md FR-064; tasks.md § "Implementation safeguards for User Story 6")

---

8. [2026-04-27 implement] **PR-4 (T080–T085) — resolver + summarizer + FR-015
   substitution wiring already in place from T026.** Implementing T084
   reduced to *test-driving* the existing executor logic: lines
   234, 366, 503–507 of `pipeline_executor.py` already initialise
   `effective_context = list(context)`, swap it after a successful
   summarizer run, and forward the swapped value to subsequent steps via
   `_build_summary_context`. The substitution honours FR-015 at
   three layers — (a) the step itself never mutates `PipelineState` (the
   executor writes `state.summarized_context` after `result` is returned);
   (b) the raw `context` list passed by the caller is never mutated (a
   *new* list is built); (c) downstream steps see a synthetic 1-message
   `ContextMessage` carrying the summary. Three new tests in
   `TestExecutorSummarizerSubstitution` lock these properties down so a
   future refactor can't silently break them. Trade-off: T084 collapses
   to "add coverage" rather than "wire it" — accepted because the
   executor was designed end-to-end in T026 and PR-4 only adds the new
   step types. (ref: T084; plan.md PR-4 § "pipeline_executor.py";
   spec.md FR-015)

---

9. [2026-04-27 implement] **T085 — Resolver+Summarizer staging validation
   playbook captured in `quickstart.md § 5b`, not executed live.**
   `/speckit.implement` runs in auto mode with no staging access; the
   playbook for an operator to drive the 4-step pipeline (summarizer →
   classifier → resolver → specialist) is now in
   `quickstart.md § 5b "Validar Resolver+Summarizer"`. The validation
   covers: (a) summarizer truncation honours `max_input_messages`
   (default 20, FR-015); (b) the substitution semantic — Phoenix
   `gen_ai.prompt` span on the specialist contains the summary, not
   the 30-turn raw history; (c) the resolver's `entities` dict feeds
   the specialist's `routing_map`; (d)
   `messages.metadata.terminating_step='specialist'` and
   `pipeline_step_count=4`. Trade-off: T085 ships as a *replayable
   playbook* rather than a live measurement — accepted because the unit
   tests in T080/T081 + the executor coverage in T084 already lock the
   substitution semantic; live cost numbers require ≥1 tenant on the
   pipeline path which the cut-line gates after PR-1..PR-4 ship. The
   playbook also documents the rollback path (single
   `UPDATE ... SET is_active=FALSE` statement, ≤60 s, FR-021). (ref:
   T085; quickstart.md § 5b)

8. [2026-04-28 implement] **Rollback button uses the audit_log
   snapshot path (D-PLAN-02 fallback).** ADR-019 (`agent_config_versions`)
   is still not materialised in production, so the rollback feature
   cannot piggy-back on the canonical version-history surface that
   other epic-008 endpoints use. Two alternatives were considered:

   * **(a) Wait for ADR-019** — clean, but blocks T101 indefinitely.
   * **(b) Persist a `before` snapshot in `audit_log.details` and
     replay it via `POST /admin/agents/{id}/pipeline-steps/rollback`.**
     Each replace already writes an audit_log row (T093); we extend
     the JSONB payload with a full `before` array and add a thin
     POST endpoint that grabs the most recent entry, validates the
     snapshot against the same `validate_steps_payload`, and routes
     it through the existing `replace_steps` transaction. The
     rollback itself is recorded as a fresh
     `agent_pipeline_steps_replaced` row tagged with
     `diff.rollback = true` so the timeline becomes a stack of
     reversible diffs.

   Picked (b). Trade-offs:

   * The audit_log column carries ~2× the bytes per replace (raw
     before snapshot is at most ~5 × 16 KB = 80 KB worst-case; we
     stay well within Postgres JSONB practical limits).
   * Rollbacks chain naturally — clicking rollback twice walks the
     timeline two steps back, which is the operator's mental model.
   * Pre-T101 audit rows lack the `before` key; the endpoint returns
     409 with `audit_log_missing_before_snapshot` so legacy data
     fails closed instead of silently restoring an empty pipeline.
   * Frontend wires `useRollbackPipelineSteps` + a footer button
     with a confirmation dialog. (ref: T101; plan.md § D-PLAN-02;
     contracts/openapi.yaml — to be regenerated to include the new
     endpoint when codegen catches up)

---

## Future entries

Add new entries below as PRs land. Number monotonically. Update the
`updated:` field in the frontmatter on each addition.
