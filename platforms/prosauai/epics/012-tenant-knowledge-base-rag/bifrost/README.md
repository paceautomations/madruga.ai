# Bifrost extension — OpenAI embeddings provider (epic 012, T021-T024)

Cross-repo work coordinated for `paceautomations/bifrost`. The files in this
directory are **artifacts ready to be ported into the Bifrost repo**:

```
config/providers/openai-embeddings.toml      # → bifrost/config/providers/
adapters/openai_embeddings.go                # → bifrost/adapters/
db/migrations/00X_bifrost_spend_embeddings_index.sql  # → bifrost/db/migrations/
```

## Why a separate repo?

Bifrost is the Pace-internal LLM gateway (Go). It already proxies
`/v1/chat/completions` for the WhatsApp pipeline (epic 005) — adding a
new endpoint follows the same provider/adapter pattern. The repo is
managed by ops; the PR there is **coordinated** with this epic but can
merge on its own cadence (cut-line per plan.md: if Bifrost extension
takes >1 week, the API falls back to direct OpenAI calls and we
sacrifice SC-010 spend tracking temporarily).

## Order of operations

1. Apply `db/migrations/00X_bifrost_spend_embeddings_index.sql` to the
   Bifrost DB (idempotent — `CREATE INDEX IF NOT EXISTS`).
2. Drop `config/providers/openai-embeddings.toml` into
   `bifrost/config/providers/` and reload Bifrost.
3. Build + deploy the Go binary with `adapters/openai_embeddings.go`.
4. Smoke via curl (T024) — see quickstart.md Step 4.

## Smoke test (T024)

```bash
# Should return a 1536-dim embedding and write a row in bifrost_spend.
curl -sS -X POST "$BIFROST_URL/v1/embeddings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BIFROST_API_KEY" \
  -H "X-ProsaUAI-Tenant: pace-internal-staging" \
  -d '{
    "model": "text-embedding-3-small",
    "input": ["hello world from prosauai rag smoke"]
  }' | jq '.data[0].embedding | length'   # → 1536

# Verify spend tracking row landed:
psql "$BIFROST_DB_URL" -c "
  SELECT created_at, tenant_id, endpoint, prompt_tokens, total_cost_usd
  FROM bifrost_spend
  WHERE endpoint = 'embeddings'
  ORDER BY created_at DESC LIMIT 1;
"
```

## Cross-repo handoff

When the Bifrost PR merges, the prosauai API only needs the runtime
`BIFROST_BASE_URL` env var to point at the Bifrost host (already in
`prosauai/config.py`).  No additional code changes on the prosauai side
beyond what `BifrostEmbedder` already implements (T017).
