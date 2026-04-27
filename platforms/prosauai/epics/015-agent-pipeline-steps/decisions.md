---
epic: 015-agent-pipeline-steps
created: 2026-04-27
updated: 2026-04-27
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

## Future entries

Add new entries below as PRs land. Number monotonically. Update the
`updated:` field in the frontmatter on each addition.
