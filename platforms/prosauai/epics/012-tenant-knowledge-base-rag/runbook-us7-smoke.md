# US7 Smoke Runbook — Bifrost Spend Tracking + Circuit Breaker (T081)

**Epic**: 012-tenant-knowledge-base-rag
**Task**: T081 (Smoke quickstart Step 4 + 9 + breaker recovery)
**Owner**: Pace ops + RAG dev
**Estimate**: 20-30 min wall-clock (3 sub-smokes + dashboard verification)
**Status**: pending — requires Bifrost staging with epic 012 PR-A merged
and prosauai staging with PR-B merged (so Trace Explorer renders the new
spans)

## Why this exists

T078 (Go integration tests) and T079 (audit script) cover the wire
contract for spend tracking. T081 is the **end-to-end** check that
closes the US7 loop: a real upload through prosauai → Bifrost →
upstream OpenAI (or staging mock) lands a row in `bifrost_spend` with
the correct cost, the resulting trace shows `rag.cost_usd` on the span,
and the circuit breaker recovers cleanly when upstream comes back.

This runbook anchors the **SC-010 acceptance gate** (Bifrost spend
accuracy ≤2 % vs OpenAI invoice). Skipping it leaves the spend pipeline
unverified end-to-end and the dashboard untrusted.

## Pre-requisites

- Bifrost staging running with the epic 012 provider configured:
  `config/providers/openai-embeddings.toml` deployed and the index
  migration `00X_bifrost_spend_embeddings_index.sql` applied.
- prosauai staging API running with epic 012 PR-B (RAG admin endpoints
  + `BifrostEmbedder`). Tenant `pace-internal` (Ariel) has `rag.enabled
  = true` in `tenants.yaml`.
- Phoenix Trace Explorer reachable; admin user logged into the staging
  admin UI.
- Grafana provisioned with `bifrost/dashboards/embeddings.json` (T080).
- `psql` access to Bifrost DB (read-only role suffices for the asserts
  but the breaker test needs write access via the kill-switch endpoint).

## Sub-smoke 1 — Spend lands in `bifrost_spend` (Step 4 of `quickstart.md`)

1. Capture the current row count:
   ```bash
   PRE_COUNT=$(psql "$BIFROST_DB_URL" -t -A -c \
     "SELECT count(*) FROM bifrost_spend WHERE endpoint = 'embeddings';")
   ```
2. Upload a tiny `faq.md` via the prosauai admin API for tenant
   `pace-internal` (single section, ~500 bytes; produces ~3 chunks).
   The upload triggers exactly one Bifrost embeddings call (one batch
   ≤100 inputs).
3. Within 5 s, the count must increment by exactly 1:
   ```bash
   POST_COUNT=$(psql "$BIFROST_DB_URL" -t -A -c \
     "SELECT count(*) FROM bifrost_spend WHERE endpoint = 'embeddings';")
   test $((POST_COUNT - PRE_COUNT)) -eq 1
   ```
4. Inspect the new row:
   ```sql
   SELECT created_at, tenant_slug, endpoint, provider,
          prompt_tokens, total_tokens, total_cost_usd
     FROM bifrost_spend
    WHERE endpoint = 'embeddings'
    ORDER BY created_at DESC
    LIMIT 1;
   ```
   - `tenant_slug` MUST equal `pace-internal`
   - `provider` MUST equal `openai`
   - `total_tokens` MUST be > 0
   - `total_cost_usd` MUST equal `total_tokens * 0.00002 / 1000`
     (cost rule per `openai-embeddings.toml [cost]`).

**Pass**: row landed with the right tenant, provider, and a
6-decimal-accurate cost. **Fail**: investigate Bifrost logs for
`spend_decode_failed_total` counter.

## Sub-smoke 2 — Trace Explorer shows `rag.cost_usd` (Step 9 of `quickstart.md`)

1. From the admin UI inbox, send a WhatsApp simulator message to the
   `pace-internal` tenant: *"qual o horario de funcionamento?"*
2. Open Trace Explorer for the resulting message and unfold the span
   hierarchy under `agent.generate`.
3. Verify the spans match `quickstart.md` Step 9:
   ```
   agent.generate
   ├── tool_call.search_knowledge
   │   └── rag.search       attributes: rag.cost_usd > 0
   │       └── rag.embed    attributes: embed.cost_usd > 0
   └── llm.completion
   ```
4. The `rag.cost_usd` attribute on `rag.search` MUST be a positive
   float and MUST equal the `embed.cost_usd` on the nested `rag.embed`
   span (single batch of one query embedding).
5. Cross-check the cost against the matching `bifrost_spend` row from
   sub-smoke 1: the values must match to 8 decimals.

**Pass**: the cost flows from Bifrost → span → trace explorer. **Fail**:
inspect prosauai structlog for `rag_embed` events with `cost_usd=0`,
which indicate the upstream `usage` block was missing or unparseable.

## Sub-smoke 3 — Circuit breaker opens and recovers

This is the only destructive step in the runbook — schedule it for a
maintenance window on staging.

1. Force 5 consecutive upstream failures by either (a) revoking the
   staging OpenAI API key for 1 minute, (b) pointing `target_url`
   to an unreachable host via a temporary config patch, or (c) using
   the Bifrost `/admin/breaker/force-failure?count=5&endpoint=embeddings`
   debug hook if available.
2. Within 60 s, the Bifrost breaker for `endpoint=embeddings` MUST
   open. Verify via:
   ```bash
   curl -sS "$BIFROST_URL/internal/breaker/status?endpoint=embeddings" | jq .
   # → {"state":"OPEN","opens_at":"...","closes_at":"...+30s"}
   ```
3. While OPEN, any embedding call from prosauai MUST short-circuit to
   503 with body `{"error":"breaker_open"}`. Confirm via Grafana panel
   5 (rejected counter `reason=breaker_open`).
4. Restore the API key / `target_url`. Wait ~30 s for the breaker to
   transition to HALF_OPEN.
5. Trigger one successful embedding call (re-upload the tiny FAQ from
   sub-smoke 1 with a new `source_name` so the atomic-replace path is
   not exercised). The first call must succeed and the breaker must
   transition to CLOSED:
   ```bash
   curl -sS "$BIFROST_URL/internal/breaker/status?endpoint=embeddings" | jq .state
   # → "CLOSED"
   ```

**Pass**: breaker opens at 5 failures, stays OPEN for ~30 s, recovers
on a single half-open success. **Fail**: review Bifrost breaker config
in `openai-embeddings.toml [circuit_breaker]` and ensure
`failure_threshold = 5`, `failure_window_seconds = 60`,
`open_duration_seconds = 30`.

## Sub-smoke 4 — Audit script (T079) sanity

```bash
# Run the monthly rollup for the current month — should pick up rows
# from sub-smokes 1 and 3.
BIFROST_DB_URL="$BIFROST_DB_URL" python apps/api/scripts/audit_bifrost_spend.py \
  --month "$(date -u +%Y-%m)" --output /tmp/spend-current.csv

cat /tmp/spend-current.csv
# Must contain a row for tenant=pace-internal, endpoint=embeddings,
# provider=openai with total_cost_usd matching the SUM in the DB.
```

## Cleanup

- Remove the `faq.md` test documents from the staging tenant via the
  admin UI (cascades chunks + Storage).
- Re-enable the OpenAI API key if revoked.
- Confirm Grafana panels 3 and 4 return to baseline within 5 min.

## Sign-off

The smoke is **complete** when all four sub-smokes pass and the row
counts in `bifrost_spend` plus the trace attributes are consistent. Mark
T081 done in `tasks.md` and link this runbook in the PR description.

## Related

- T078 — `bifrost/tests/integration/test_embeddings_spend.go` (unit
  coverage for the same invariants).
- T079 — `apps/api/scripts/audit_bifrost_spend.py` (monthly invoice
  reconciliation).
- T080 — `bifrost/dashboards/embeddings.json` (live monitoring).
- spec FR-030, FR-031, FR-032, FR-033, SC-010.
- ADR-042 (proposed).
