# Quickstart — Epic 015 Agent Pipeline Steps

**Audience**: dev/ops setting up a local environment, running tests, validating the 6 user stories end-to-end.

---

## 0. Prerequisites

- Repo `paceautomations/prosauai` cloned at `/home/gabrielhamu/repos/paceautomations/prosauai/`.
- Branch `epic/prosauai/015-agent-pipeline-steps` checked out.
- Docker (for postgres + redis containers).
- `uv` (Python package manager).
- `dbmate` (migrations).
- `pnpm` (frontend, only needed for PR-5/PR-6).

---

## 1. Local environment

```bash
cd /home/gabrielhamu/repos/paceautomations/prosauai
docker compose up -d postgres redis        # PG 15 + Redis 7
cd apps/api
uv sync                                    # install Python deps
dbmate up                                  # apply all migrations including 20260601000010 + 20260601000011
```

Verify:
```sql
\d public.agent_pipeline_steps               -- new table
\d public.trace_steps                        -- includes sub_steps JSONB column
SELECT * FROM pg_indexes WHERE tablename='agent_pipeline_steps';  -- 2 índices
```

---

## 2. Seed test agent (US1 path — via SQL, no admin UI required)

Pick an existing agent (e.g., `Ariel Bot` for tenant `pace-internal`):

```sql
-- 1. Get the agent_id and tenant_id
SELECT id AS agent_id, tenant_id, name FROM public.agents WHERE name='Ariel Bot';
-- => agent_id = <UUID_A>, tenant_id = <UUID_T>

-- 2. Set RLS context for the session
SET LOCAL app.current_tenant = '<UUID_T>';

-- 3. Insert 2 pipeline steps: classifier + specialist with routing_map
INSERT INTO public.agent_pipeline_steps
    (tenant_id, agent_id, step_order, step_type, config)
VALUES
    ('<UUID_T>', '<UUID_A>', 1, 'classifier', '{
        "model": "openai:gpt-5-nano",
        "intent_labels": ["greeting","simple_query","billing","ranking_query","complex"],
        "prompt_slug": "ariel-classifier-v1",
        "timeout_seconds": 15
     }'::jsonb),
    ('<UUID_T>', '<UUID_A>', 2, 'specialist', '{
        "default_model": "openai:gpt-5-mini",
        "routing_map": {
            "greeting": "openai:gpt-5-nano",
            "simple_query": "openai:gpt-5-nano",
            "billing": "openai:gpt-5-mini",
            "ranking_query": "openai:gpt-5-mini",
            "complex": "openai:gpt-5-mini"
        },
        "timeout_seconds": 30
     }'::jsonb);

-- 4. Confirm
SELECT step_order, step_type, config->>'model' AS model
FROM public.agent_pipeline_steps
WHERE agent_id='<UUID_A>' ORDER BY step_order;
```

---

## 3. Run the API

```bash
cd /home/gabrielhamu/repos/paceautomations/prosauai/apps/api
uv run uvicorn prosauai.main:app --reload --port 8050
# Health check
curl -s http://localhost:8050/health | jq .
```

---

## 4. Validate US1 — classifier+specialist cost reduction

Send a greeting via webhook simulator (or use admin "Send test message"):

```bash
# Replace tenant_slug and instance_id with real values
curl -X POST http://localhost:8050/webhook/evolution/<instance_id> \
    -H 'Content-Type: application/json' \
    -d '{"event":"messages.upsert","data":{"key":{"remoteJid":"5511999999999@s.whatsapp.net","fromMe":false},"message":{"conversation":"oi tudo bem?"}}}'
```

Then query the trace:

```sql
SELECT
    t.trace_id,
    ts.step_order,
    ts.name,
    ts.duration_ms,
    ts.sub_steps
FROM public.traces t
JOIN public.trace_steps ts ON ts.trace_id = t.trace_id
WHERE t.tenant_id='<UUID_T>'
  AND t.started_at > now() - interval '1 minute'
  AND ts.name = 'generate_response'
ORDER BY t.started_at DESC, ts.step_order
LIMIT 5;
```

**Expected**: `sub_steps` JSONB array with 2 elements:
- `{step_type:"classifier", model:"openai:gpt-5-nano", output:{intent:"greeting", confidence:0.9X}, status:"ok"}`
- `{step_type:"specialist", model:"openai:gpt-5-nano", output:{response_text:"...", ...}, status:"ok", terminating:true}`

Then send a billing message:
```bash
curl -X POST ... -d '{... "conversation":"qual a fatura desse mês?" ...}'
```

**Expected**: same 2 sub_steps but `specialist.model = "openai:gpt-5-mini"` (routed via `routing_map`).

---

## 5. Validate US2 — clarifier on low confidence

Add a clarifier between classifier and specialist:

```sql
-- Reorder: classifier=1, clarifier=2, specialist=3
DELETE FROM public.agent_pipeline_steps WHERE agent_id='<UUID_A>';

INSERT INTO public.agent_pipeline_steps (tenant_id, agent_id, step_order, step_type, config, condition) VALUES
    ('<UUID_T>', '<UUID_A>', 1, 'classifier', '{...same as before...}'::jsonb, NULL),
    ('<UUID_T>', '<UUID_A>', 2, 'clarifier',
        '{"model":"openai:gpt-5-nano","prompt_slug":"ariel-clarifier-v1","max_question_length":140}'::jsonb,
        '{"classifier.confidence":"<0.6"}'::jsonb),
    ('<UUID_T>', '<UUID_A>', 3, 'specialist', '{...same as before...}'::jsonb, NULL);
```

Send an ambiguous message:
```bash
curl -X POST ... -d '{... "conversation":"e ai" ...}'
```

**Expected** (assuming classifier returns `confidence=0.4`):
- `sub_steps[0]` = classifier ok, output `{intent:"...", confidence:0.4}`.
- `sub_steps[1]` = clarifier ok, output `{question_text:"Você pode me dar mais detalhes?"}`, `terminating:true`.
- `sub_steps[2]` = specialist `status:"skipped"`, output `{reason:"prior_step_terminating"}`.
- `messages.metadata.terminating_step = "clarifier"`.

Send a clear message:
```bash
curl -X POST ... -d '{... "conversation":"qual o ranking?" ...}'
```

**Expected** (assuming classifier returns `confidence=0.9`):
- `sub_steps[0]` = classifier ok.
- `sub_steps[1]` = clarifier `status:"skipped"`, `output:{condition_evaluated:"classifier.confidence < 0.6 (got 0.9)"}`.
- `sub_steps[2]` = specialist ok, terminating.

---

## 5b. Validar Resolver+Summarizer (US1 enrichment, PR-4 / T085)

Drives the 4-step pipeline `summarizer → classifier → resolver → specialist`
end-to-end. Validates that the summarizer compresses long histories before
the cheap classifier runs (FR-015) and that the resolver feeds structured
entities to the specialist.

Pre-conditions:

- A test agent with NO active rows in `public.agent_pipeline_steps`.
- A long-running conversation seeded with ≥30 messages (use the
  `tools/seed_long_conversation.py` helper or replay a real conversation
  via the inbox export feature in the admin UI).
- API binary running locally per § 3 above.

```sql
-- Replace the existing pipeline atomically — same agent, longer pipeline.
BEGIN;
DELETE FROM public.agent_pipeline_steps WHERE agent_id='<UUID_A>';

INSERT INTO public.agent_pipeline_steps
    (tenant_id, agent_id, step_order, step_type, config, condition)
VALUES
    ('<UUID_T>', '<UUID_A>', 1, 'summarizer',
        '{"model":"openai:gpt-5-nano","max_input_messages":20}'::jsonb,
        '{"context.message_count":">10"}'::jsonb),
    ('<UUID_T>', '<UUID_A>', 2, 'classifier',
        '{"model":"openai:gpt-5-nano","intent_labels":["greeting","billing","support","ranking_query","ambiguous"]}'::jsonb,
        NULL),
    ('<UUID_T>', '<UUID_A>', 3, 'resolver',
        '{"model":"openai:gpt-5-nano","tools_enabled":[]}'::jsonb,
        NULL),
    ('<UUID_T>', '<UUID_A>', 4, 'specialist',
        '{"default_model":"gpt-4o-mini","routing_map":{"greeting":"openai:gpt-5-nano","billing":"gpt-4o","ranking_query":"gpt-4o"}}'::jsonb,
        NULL);
COMMIT;
```

Send a message into the long-running conversation:

```bash
curl -X POST http://localhost:8050/webhook/evolution \
  -H "Content-Type: application/json" -H "X-Webhook-Secret: dev" \
  -d '{"tenant_id":"<UUID_T>","sender_phone":"+55119...","text":"e a fatura de abril?"}'
```

**Expected** (verify via SQL on `public.trace_steps` — wait ≤2 s for the
fire-and-forget persister to flush):

```sql
SELECT
    step_order,
    name,
    status,
    sub_steps -> 0 ->> 'step_type'  AS sub1_type,
    sub_steps -> 0 ->> 'status'     AS sub1_status,
    sub_steps -> 1 ->> 'step_type'  AS sub2_type,
    sub_steps -> 1 ->> 'status'     AS sub2_status,
    sub_steps -> 2 ->> 'step_type'  AS sub3_type,
    sub_steps -> 3 ->> 'step_type'  AS sub4_type,
    sub_steps -> 3 ->> 'terminating' AS sub4_terminating
FROM public.trace_steps
WHERE trace_id='<UUID_TRACE>' AND name='generate_response';
```

Expected row:

| col              | value           |
|------------------|-----------------|
| sub1_type        | `summarizer`    |
| sub1_status      | `ok`            |
| sub2_type        | `classifier`    |
| sub2_status      | `ok`            |
| sub3_type        | `resolver`      |
| sub4_type        | `specialist`    |
| sub4_terminating | `true`          |

Validation checklist for an operator running this against staging:

- [ ] `sub_steps[0]` (summarizer) `output.summary_text` is non-empty and
      ≤4 frases curtas.
- [ ] `sub_steps[0].output.message_count ≤ 20` (default cap honored;
      FR-015 truncation).
- [ ] `sub_steps[1]` (classifier) `output.intent` ∈ `intent_labels`.
- [ ] `sub_steps[2]` (resolver) `output.entities` is a JSON object
      (possibly empty if the LLM found no entities — both shapes are
      valid).
- [ ] `sub_steps[3]` (specialist) `output.intent_used` matches
      `sub_steps[1].output.intent` and the chosen `output.model` follows
      the `routing_map`.
- [ ] `messages.metadata.terminating_step = 'specialist'` and
      `pipeline_step_count = 4`.
- [ ] **Cost check**: aggregated cost for the 4-step run is *cheaper*
      than the equivalent single-call baseline because the summarizer
      shrinks the prompt for the specialist. Expected reduction:
      ≥20% on conversations with >20 turns (lower than the SC-001 -30%
      target because the resolver adds one cheap LLM call — operators
      tune `max_input_messages` to recover the gap).
- [ ] **Substitution check**: the specialist's prompt (visible via the
      Phoenix span attribute `gen_ai.prompt`) contains the summarizer
      summary, not the 30-turn raw history.

**Rollback** (single SQL statement, ≤60 s):

```sql
UPDATE public.agent_pipeline_steps SET is_active=FALSE WHERE agent_id='<UUID_A>';
```

The agent immediately reverts to the legacy single-call path (FR-021).

---

## 6. Validate US6 — backward compatibility (zero-pipeline regression)

Pick a different agent that has NO pipeline_steps:

```sql
SELECT id, name FROM public.agents WHERE id NOT IN (SELECT DISTINCT agent_id FROM public.agent_pipeline_steps);
-- Use one of these as the agent for the next test
```

Send a message via webhook. Query the trace:

```sql
SELECT step_order, name, status, sub_steps IS NULL AS substeps_null
FROM public.trace_steps WHERE trace_id='<UUID>' ORDER BY step_order;
```

**Expected**: row `name='generate_response'` has `sub_steps IS NULL`. All 12-13 top-level steps execute as before. `messages.metadata` does NOT contain `terminating_step` / `pipeline_step_count`.

Then run the full existing test suite:

```bash
cd /home/gabrielhamu/repos/paceautomations/prosauai/apps/api
uv run pytest tests/ -q
```

**Expected**: 100% pass (SC-008 hard gate).

---

## 7. Validate SC-010 — overhead p95 ≤5 ms (benchmark)

```bash
cd /home/gabrielhamu/repos/paceautomations/prosauai/apps/api
uv run pytest tests/benchmarks/test_overhead_no_pipeline.py -v
```

**Expected output**:
```
overhead_p95_ms = 1.4 (target ≤ 5.0)
overhead_p99_ms = 2.1
PASS
```

---

## 8. Validate US5 — Trace Explorer (only when PR-6 lands, P2)

```bash
cd /home/gabrielhamu/repos/paceautomations/prosauai/apps/admin
pnpm install
pnpm dev
# Open http://localhost:3000/admin/traces
```

- Filter by `tenant=pace-internal` and pick a recent trace.
- Click to expand → step `generate_response` shows accordion with N sub-rows (one per pipeline step).
- Each sub-row: duration bar, status icon, expandable input/output/model/tokens.

**Filter by `terminating_step=clarifier`** → list refreshes to show only traces where clarifier produced the final response.

---

## 9. Validate US3 — Admin UI (only when PR-5 lands, P2)

```bash
# Open http://localhost:3000/admin/agents
# Click "Ariel Bot" → tab "Pipeline"
```

- See list of 3 steps (classifier, clarifier, specialist).
- Click "Add step" → choose `summarizer` → fill form (model: `openai:gpt-5-nano`, max_input_messages: 20) → Save.
- See new step appended at order=4. Optionally drag to reorder.
- Audit log shows: `pipeline_step_added: summarizer at order 4 by gabrielhamu@gmail.com`.
- Try to add a 6th step → validation error 422 in UI: "Maximum 5 steps per agent".

---

## 10. Tear down

```bash
docker compose down -v   # remove containers AND volumes (drops DB)
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `INSERT INTO agent_pipeline_steps` returns 0 rows but no error | RLS blocked: missing `SET LOCAL app.current_tenant=...` | Set tenant context at session start. |
| `condition` JSONB key never matches even though path looks right | dotted path component name mismatch (e.g., `classifier.confidence` vs `classifier_confidence`) | Inspect `state.to_scope()` shape in `pipeline_executor.py` debug log. |
| Sub_steps is NULL but pipeline executed | Trace persistence (`fire_and_forget`) failed silently | Check structlog `trace_persist_failed` event; usually pool exhausted. |
| Test `test_pipeline_backwards_compat` fails because output not byte-equivalent | Mock LLM seed not propagated through executor branch | Ensure `pipeline_executor.execute_agent_pipeline` is NEVER called when `steps=[]`. |
| `validate_steps_payload` rejects valid `routing_map` model | Model name not in `pricing.PRICING_TABLE` (ADR-029) | Add the model to the constant or use a known model. |

---

## References

- Spec: [`spec.md`](./spec.md)
- Plan: [`plan.md`](./plan.md)
- Data model: [`data-model.md`](./data-model.md)
- Research (alternatives): [`research.md`](./research.md)
- API contracts: [`contracts/openapi.yaml`](./contracts/openapi.yaml)
