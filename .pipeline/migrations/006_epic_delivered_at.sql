-- 006_epic_delivered_at.sql — Add delivered_at to epics table
ALTER TABLE epics ADD COLUMN delivered_at TEXT;
CREATE INDEX IF NOT EXISTS idx_epics_delivered_at ON epics(delivered_at);
