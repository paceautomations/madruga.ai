# Smoke Test Runbook — Pipeline Instrumentation (PR 2)

**Task**: T030
**Status**: DEFERRED (requires 24h of real traffic in staging)
**Success Criteria**:
- SC-006: overhead p95 < 10ms vs. baseline
- SC-007: zero delivery failures (A/B window)
- Traces + trace_steps populated end-to-end for every processed message

## Scope

Validate in staging that the `Pipeline.execute()` refactor (T026–T028)
and the `persist_trace_fire_and_forget()` path (T025) do not regress the
message-delivery path nor breach the observability budget. The offline
test suite (`pytest apps/api/tests/` — T029) covers correctness of the
instrumented code paths; this runbook covers behavior under sustained
real traffic.

## Pre-conditions

- Branch `epic/prosauai/008-admin-evolution` deployed to staging.
- Staging DB running migrations up to `20260420000004` (T010–T014).
- Ariel tenant receiving WhatsApp traffic at near-prod volume
  (~5k msgs/day reference from CLAUDE.md).
- `retention_cron` disabled during the window, or window set before
  `TRACE_RETENTION_DAYS` kicks in.
- OTel SDK active (epic 002 — pre-condition of R2).

## Procedure (48h window preferred; 24h minimum per T030)

### Step 1 — Baseline capture (12h, instrumentation OFF)

Set env flag to short-circuit `persist_trace_fire_and_forget()`:

```bash
# apps/api deployment
export TRACE_PERSIST_ENABLED=false
# restart api pod
```

Capture baseline for 12h:

```bash
# OTel / Phoenix — export p95 latency of the parent pipeline span
psql "$DATABASE_URL_ADMIN" <<'SQL'
-- If Phoenix is the sink, query via Phoenix API instead.
-- Otherwise, use OTel collector aggregate (prom_metrics):
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
  count(*) AS n
FROM public.messages
WHERE created_at > now() - '12 hours'::interval
  AND tenant_id = (SELECT id FROM tenants WHERE slug = 'pace-internal')
  AND role = 'ai_assistant';
SQL
```

Record: `baseline_p50`, `baseline_p95`, `baseline_p99`, `baseline_n`.

### Step 2 — Instrumented capture (12h, instrumentation ON)

```bash
export TRACE_PERSIST_ENABLED=true
# restart api pod
```

Wait 12h. Capture same metrics as Step 1. Record:
`instrumented_p50`, `instrumented_p95`, `instrumented_p99`,
`instrumented_n`.

### Step 3 — Delivery-failure audit (both windows)

```bash
# Count delivery failures in each window
psql "$DATABASE_URL_ADMIN" <<'SQL'
SELECT
  CASE WHEN created_at < (now() - '12 hours'::interval) THEN 'baseline' ELSE 'instrumented' END AS window,
  count(*) FILTER (WHERE status = 'failed') AS failures,
  count(*) AS total
FROM public.messages
WHERE created_at > now() - '24 hours'::interval
  AND role = 'ai_assistant'
GROUP BY window;
SQL
```

Expected: `failures = 0` in both windows (SC-007 — fire-and-forget must
never block delivery).

### Step 4 — Trace coverage audit (instrumented window only)

```bash
psql "$DATABASE_URL_ADMIN" <<'SQL'
-- Every ai_assistant message should have a trace row
WITH msg_count AS (
  SELECT count(*) AS n
  FROM public.messages
  WHERE role = 'ai_assistant'
    AND created_at > (now() - '12 hours'::interval)
),
trace_count AS (
  SELECT count(*) AS n
  FROM public.traces
  WHERE started_at > (now() - '12 hours'::interval)
),
step_count AS (
  SELECT count(*) AS n, avg(cnt) AS avg_steps
  FROM (
    SELECT trace_uuid, count(*) AS cnt
    FROM public.trace_steps
    WHERE started_at > (now() - '12 hours'::interval)
    GROUP BY trace_uuid
  ) s
)
SELECT
  (SELECT n FROM msg_count)   AS messages,
  (SELECT n FROM trace_count) AS traces,
  (SELECT n FROM step_count)  AS traces_with_steps,
  (SELECT avg_steps FROM step_count) AS avg_steps_per_trace;
SQL
```

Expected:
- `traces / messages >= 0.98` (allow ≤2% loss to fire-and-forget under
  extreme DB load — fail-closed would be worse per R3)
- `avg_steps_per_trace` between 10 and 12 (some steps may legitimately
  skip, e.g. `output_guard` when PII-check disabled)

### Step 5 — Overhead computation

```
overhead_p50 = instrumented_p50 - baseline_p50
overhead_p95 = instrumented_p95 - baseline_p95
overhead_p99 = instrumented_p99 - baseline_p99
```

**Gate** (SC-006): `overhead_p95 < 10 ms`.

If the gate fails, diagnose:
1. Is `persist_trace_fire_and_forget()` actually fire-and-forget?
   → Check for `await` before `asyncio.create_task` in `pipeline.py`.
2. Is JSONB truncation happening in the request path?
   → Should be inside `persist_trace`, post-handoff.
3. Are StepRecord captures blocking?
   → Decorator should be zero-cost (append to in-memory list only).

## Abort criteria (pull rollback immediately)

- Any delivery failure attributable to instrumentation in the
  instrumented window (Step 3 shows `failures > 0` with matching log
  lines in api.log referencing `trace_persist`).
- `overhead_p95 > 25 ms` (2.5× the budget — indicates a coding defect,
  not a tuning issue).
- Trace coverage `< 0.90` (Step 4 — points at a bug in the decorator or
  the fire-and-forget wrapper).

Rollback: set `TRACE_PERSIST_ENABLED=false`, restart api pod, open
incident, revert relevant commits from PR 2 if the defect cannot be
hotfixed within 1 hour.

## Recording results

When executed in staging, append below:

```text
[YYYY-MM-DD] Baseline window:       p50=__ ms  p95=__ ms  p99=__ ms  n=____
[YYYY-MM-DD] Instrumented window:   p50=__ ms  p95=__ ms  p99=__ ms  n=____
[YYYY-MM-DD] Overhead:              Δp50=__ ms Δp95=__ ms Δp99=__ ms
[YYYY-MM-DD] Delivery failures:     baseline=__  instrumented=__
[YYYY-MM-DD] Trace coverage:        traces=__/msgs=__ (__%)  avg_steps=__
[YYYY-MM-DD] Gate SC-006 (p95<10ms):   PASS | FAIL
[YYYY-MM-DD] Gate SC-007 (zero fails): PASS | FAIL
```

## Why this task is DEFERRED in the autonomous pipeline

T030 requires observing sustained real traffic for at least 24 hours.
The autonomous dispatch loop cannot wait that long, and synthetic
traffic would not reproduce the concurrency/shape of real Evolution API
webhooks. The offline test suite (T029 — `pytest apps/api/tests/`)
covers correctness of:

- `StepRecord` truncation and state transitions (T024).
- `persist_trace_fire_and_forget` failure isolation (T025).
- Routing persistence fire-and-forget shape (T040, T043).
- Existing pipeline epics 004 + 005 regression gate (T029).

Staging smoke execution will be coordinated by the deploy owner when
the branch is pushed to the staging environment. This runbook is the
contract.
