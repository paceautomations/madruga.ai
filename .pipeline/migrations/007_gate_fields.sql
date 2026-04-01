-- 007_gate_fields.sql — Add gate state tracking to pipeline_runs
-- Supports human gate pause/resume for DAG executor (epic 013)

ALTER TABLE pipeline_runs ADD COLUMN gate_status TEXT
    CHECK (gate_status IN ('waiting_approval', 'approved', 'rejected'));

ALTER TABLE pipeline_runs ADD COLUMN gate_notified_at TEXT;

ALTER TABLE pipeline_runs ADD COLUMN gate_resolved_at TEXT;

CREATE INDEX IF NOT EXISTS idx_runs_gate_status ON pipeline_runs(gate_status);
