-- Index for /api/stats and /api/runs queries that filter by platform_id + started_at
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_platform_started
    ON pipeline_runs (platform_id, started_at);
