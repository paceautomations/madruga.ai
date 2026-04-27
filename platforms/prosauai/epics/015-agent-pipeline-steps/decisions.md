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

---

## Future entries

Add new entries below as PRs land. Number monotonically. Update the
`updated:` field in the frontmatter on each addition.
