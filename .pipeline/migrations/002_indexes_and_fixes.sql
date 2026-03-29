-- 002_indexes_and_fixes.sql — Additional indexes for status queries

CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_status ON pipeline_nodes(platform_id, status);
CREATE INDEX IF NOT EXISTS idx_epic_nodes_status ON epic_nodes(platform_id, epic_id, status);
