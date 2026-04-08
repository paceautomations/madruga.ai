-- Add dispatch_log column to pipeline_runs for debugging dispatch output
ALTER TABLE pipeline_runs ADD COLUMN dispatch_log TEXT;
