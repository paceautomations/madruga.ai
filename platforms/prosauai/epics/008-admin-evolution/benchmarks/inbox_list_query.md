# Benchmark — Inbox List Query

**Task**: T055
**Status**: DEFERRED (requires real 10k-conversation dataset in staging)
**Success Criterion**: p95 < 100ms on dataset of 10k conversations (SC-005)

## Query under test

The conversation list endpoint (future PR 5 — US1/T110) will issue the
following query shape against `pool_admin`:

```sql
EXPLAIN ANALYZE
SELECT
  c.id,
  c.tenant_id,
  c.customer_id,
  c.status,
  c.intent_current,
  c.intent_confidence,
  c.quality_score_avg,
  c.last_message_id,
  c.last_message_at,
  c.last_message_preview,
  cs.sla_breach_at
FROM public.conversations c
LEFT JOIN public.conversation_states cs ON cs.conversation_id = c.id
WHERE c.tenant_id = $1
ORDER BY c.last_message_at DESC NULLS LAST
LIMIT 50;
```

Cursor pagination variant (subsequent pages):

```sql
... WHERE c.tenant_id = $1
    AND (c.last_message_at, c.id) < ($cursor_ts, $cursor_id)
ORDER BY c.last_message_at DESC NULLS LAST, c.id DESC
LIMIT 50;
```

## Supporting index (from migration T013)

```sql
CREATE INDEX idx_conversations_tenant_last_msg
  ON public.conversations (tenant_id, last_message_at DESC NULLS LAST);
```

## Expected plan (10k conversations per tenant)

```text
Limit  (cost=0.42..X.XX rows=50 width=XXX) (actual time=0.XX..0.XX rows=50 loops=1)
  ->  Index Scan using idx_conversations_tenant_last_msg on conversations c
        (cost=0.42..Y.YY rows=ZZZZ width=XXX)
        (actual time=0.0X..0.XX rows=50 loops=1)
        Index Cond: (tenant_id = $1)
  ->  [... LEFT JOIN to conversation_states by PK ...]
Planning Time: < 1 ms
Execution Time: < 50 ms  (target p95 < 100 ms)
```

## How to run (staging)

Prerequisite: populate staging with ≥10k conversations per tenant via
`scripts/seed_dataset.py` or real replica clone.

```bash
psql "$DATABASE_URL_ADMIN" <<'SQL'
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT c.id, c.tenant_id, c.customer_id, c.status,
       c.intent_current, c.intent_confidence, c.quality_score_avg,
       c.last_message_id, c.last_message_at, c.last_message_preview,
       cs.sla_breach_at
FROM public.conversations c
LEFT JOIN public.conversation_states cs ON cs.conversation_id = c.id
WHERE c.tenant_id = '<tenant-uuid>'
ORDER BY c.last_message_at DESC NULLS LAST
LIMIT 50;
SQL
```

Repeat 100× and compute p95. Record output here once dataset is available.

## Fallback if p95 > 100ms

If the index-only plan is not chosen (e.g. because `last_message_at` NULLs
dominate for a fresh tenant), options:

1. Add a composite covering index including the non-key columns needed:
   `CREATE INDEX ... ON conversations (tenant_id, last_message_at DESC NULLS LAST) INCLUDE (customer_id, status, intent_current, last_message_preview);`
2. Split `NULL` last_message_at rows into a partial index.
3. Denormalize `sla_breach_at` onto `conversations` to avoid the LEFT JOIN.

## Recording results

When executed, append the actual plan + p95 measurement below.

```text
[YYYY-MM-DD] Measured p95: __ ms (n=100, dataset: 10.2k conversations, tenant=pace-internal)
Plan: <paste EXPLAIN ANALYZE JSON>
```
