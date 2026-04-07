-- 012_performance_indexes.sql — Composite indexes for gate queries and eval dedup

-- Easter dag_scheduler polls gates by (platform_id, gate_status) every 15s
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_gate_status
    ON pipeline_runs (platform_id, gate_status, epic_id);

-- dag_executor resume checks approved gates per (platform_id, node_id, gate_status)
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_node_gate
    ON pipeline_runs (platform_id, node_id, gate_status);

-- eval_scores dedup check: (run_id, dimension)
CREATE INDEX IF NOT EXISTS idx_eval_scores_run_dimension
    ON eval_scores (run_id, dimension);
