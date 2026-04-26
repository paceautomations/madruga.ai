-- migrate:up
-- Bifrost extension: add index supporting embeddings spend lookups (epic 012, T023).
--
-- The Bifrost ``bifrost_spend`` table already accepts an ``endpoint`` TEXT
-- column (validated against the existing rows; no CHECK constraint). The
-- new ``embeddings`` value lands automatically; this migration only adds
-- the (tenant_id, endpoint, created_at) index so:
--
--   * Performance AI dashboards (epic 008) can pull "embedding spend per
--     tenant in last 24 h" without a sequential scan.
--   * SC-010 audits diff "Bifrost-side total" vs "OpenAI invoice line"
--     in <100 ms even with 30 days of history.
--
-- Idempotent: ``CREATE INDEX IF NOT EXISTS``. Safe to re-run.
--
-- References:
--   - spec.md FR-032, SC-010
--   - plan.md §"Bifrost extension"

CREATE INDEX IF NOT EXISTS bifrost_spend_tenant_endpoint_created_at_idx
    ON bifrost_spend (tenant_id, endpoint, created_at DESC);

COMMENT ON INDEX bifrost_spend_tenant_endpoint_created_at_idx IS
    'Epic 012 — supports per-tenant embedding spend rollups + invoice reconciliation.';

-- migrate:down
DROP INDEX IF EXISTS bifrost_spend_tenant_endpoint_created_at_idx;
