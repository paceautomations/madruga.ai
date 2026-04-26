# Bifrost Dashboards — Embeddings (epic 012, T080)

This dashboard ships alongside the `openai-embeddings` provider added in
epic 012 (PR-A, T021–T024). It surfaces the four signals operations
needs to triage RAG incidents fast: **traffic, latency, spend, and
back-pressure**.

| File | Datasource | Refresh |
|------|------------|---------|
| `dashboards/embeddings.json` | Prometheus + Bifrost Postgres | 30 s |

## Cross-repo handoff

Drop `bifrost/dashboards/embeddings.json` into the Bifrost repo at the
matching path; the ops Grafana provisioner picks it up via the
`bifrost-grafana-provisioner` ConfigMap. No code changes elsewhere — the
dashboard reads the same Prometheus metrics the chat-completions
provider already exports (`bifrost_request_duration_seconds_*`,
`bifrost_requests_rejected_total`) plus the SQL view over `bifrost_spend`.

## Panel reference

### 1. Embeddings — Requests per second (by status)
- **Query**: `sum by (status) (rate(bifrost_request_duration_seconds_count{endpoint="embeddings"}[1m]))`
- **Reads**: traffic shape and 4xx/5xx splits.
- **Alert hook**: spike of `status=503` correlates with circuit-breaker
  trips; cross-check panel 5.

### 2. Embeddings — Latency (p50/p95/p99)
- **Query**: `histogram_quantile(0.95, sum by (le) (rate(bifrost_request_duration_seconds_bucket{endpoint="embeddings"}[5m])))`
- **SLO**: p95 ≤ 1.5 s for synchronous upload paths (FR-017 + R3).
- **Alert hook**: page when p95 > 1.5 s for ≥5 min during business hours.

### 3. Embeddings — Cumulative spend per tenant (USD)
- **Query** (Postgres): `SELECT date_trunc('hour', created_at), tenant_slug, sum(total_cost_usd) FROM bifrost_spend WHERE endpoint = 'embeddings' AND $__timeFilter(created_at) GROUP BY 1, 2`.
- **Source of truth**: `bifrost_spend` populated transactionally only on
  upstream 2xx (FR-032). Reconciles vs OpenAI invoice via the audit
  script `apps/api/scripts/audit_bifrost_spend.py` (T079).
- **SC-010**: monthly diff vs invoice line MUST stay within 2 %.

### 4. Rate-limit usage — RPM (% of 3500)
- **Query**: `100 * (sum by (tenant) (rate(bifrost_request_duration_seconds_count{endpoint="embeddings"}[1m])) * 60) / 3500`
- **Thresholds**: green < 60 %, yellow 60–80 %, orange 80–95 %, red > 95 %.
- **Action at red**: re-embed CLI is likely running with too-large
  batches — drop `--batch-size` to 50 (default 100) or schedule outside
  business hours.

### 5. Embeddings — Rejected requests / sec (by reason)
- **Query**: `sum by (reason) (rate(bifrost_requests_rejected_total{endpoint="embeddings"}[1m]))`
- **Reasons**: `breaker_open`, `rate_limited`, `missing_tenant_header`.
- **Action**: any sustained `missing_tenant_header` rate is a config
  bug in the prosauai embedder client (it always sets the header) —
  page on-call.

## Smoke (after install)

```bash
# 1. Generate one embedding via Bifrost (any tenant slug works in staging).
curl -sS -X POST "$BIFROST_URL/v1/embeddings" \
  -H "Content-Type: application/json" \
  -H "X-ProsaUAI-Tenant: pace-internal-staging" \
  -d '{"model":"text-embedding-3-small","input":["hello dashboard"]}' >/dev/null

# 2. Within 30 s, the dashboard should show:
#    - panel 1: a 1-call/sec spike at status=200
#    - panel 2: a single-bucket latency point (~0.3 s)
#    - panel 3: a +$0.0000001 increment for tenant=pace-internal-staging
#    - panel 4: gauge moves to ~0.03 % then back to 0
#    - panel 5: nothing (no rejections expected)
```

## Maintenance

When OpenAI bumps the embeddings price (e.g. drops cost_per_1k_tokens to
$0.00001), update **only** `config/providers/openai-embeddings.toml` —
the dashboard reads the cost row from `bifrost_spend` so the change
propagates automatically. The audit script does the same.

## References

- spec.md FR-030, FR-031, FR-032, FR-033, SC-010
- plan.md §"Bifrost extension"
- bifrost/README.md (cross-repo handoff)
- ADR-042 (proposed)
