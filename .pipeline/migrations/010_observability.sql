-- 010_observability.sql — Observability, Tracing & Evals (Epic 017)
-- Adds traces table (groups pipeline_runs as spans), eval_scores table,
-- and links pipeline_runs to traces via trace_id FK.

-- Trace: groups spans (pipeline_runs) from a complete pipeline execution
CREATE TABLE IF NOT EXISTS traces (
    trace_id       TEXT PRIMARY KEY,
    platform_id    TEXT NOT NULL,
    epic_id        TEXT,
    mode           TEXT NOT NULL DEFAULT 'l1'
                   CHECK (mode IN ('l1', 'l2')),
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    total_nodes    INTEGER DEFAULT 0,
    completed_nodes INTEGER DEFAULT 0,
    total_tokens_in  INTEGER,
    total_tokens_out INTEGER,
    total_cost_usd   REAL,
    total_duration_ms INTEGER,
    started_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT,
    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id)
);

-- Link pipeline_runs (spans) to parent trace
ALTER TABLE pipeline_runs ADD COLUMN trace_id TEXT REFERENCES traces(trace_id);

-- Eval scores: 4 dimensions per evaluated node
CREATE TABLE IF NOT EXISTS eval_scores (
    score_id     TEXT PRIMARY KEY,
    trace_id     TEXT,
    platform_id  TEXT NOT NULL,
    epic_id      TEXT,
    node_id      TEXT NOT NULL,
    run_id       TEXT,
    dimension    TEXT NOT NULL
                 CHECK (dimension IN ('quality', 'adherence_to_spec',
                        'completeness', 'cost_efficiency')),
    score        REAL NOT NULL CHECK (score >= 0 AND score <= 10),
    metadata     TEXT,
    evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id),
    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id),
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

-- Persist output size for FR-012 quantitative metrics (U2 fix)
ALTER TABLE pipeline_runs ADD COLUMN output_lines INTEGER;

-- Indices for frequent queries
CREATE INDEX IF NOT EXISTS idx_traces_platform ON traces(platform_id);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_started ON traces(started_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_trace ON pipeline_runs(trace_id);
CREATE INDEX IF NOT EXISTS idx_eval_scores_trace ON eval_scores(trace_id);
CREATE INDEX IF NOT EXISTS idx_eval_scores_node ON eval_scores(platform_id, node_id);
CREATE INDEX IF NOT EXISTS idx_eval_scores_run ON eval_scores(run_id);
