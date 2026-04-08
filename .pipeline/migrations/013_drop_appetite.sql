-- 013_drop_appetite.sql — Remove appetite column from epics table
-- Appetite section removed from epic pitch format.
-- SQLite cannot ALTER DROP COLUMN before 3.35, so we recreate the table.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS epics_new;

CREATE TABLE epics_new (
    epic_id      TEXT NOT NULL,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'proposed'
                 CHECK (status IN ('proposed', 'drafted', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    priority     INTEGER,
    branch_name  TEXT,
    file_path    TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    delivered_at TEXT,
    PRIMARY KEY (platform_id, epic_id)
);

INSERT INTO epics_new (epic_id, platform_id, title, status, priority, branch_name, file_path, created_at, updated_at, delivered_at)
    SELECT epic_id, platform_id, title, status, priority, branch_name, file_path, created_at, updated_at, delivered_at
    FROM epics;

DROP TABLE epics;
ALTER TABLE epics_new RENAME TO epics;

CREATE INDEX IF NOT EXISTS idx_epics_platform ON epics(platform_id);
CREATE INDEX IF NOT EXISTS idx_epics_status ON epics(status);

PRAGMA foreign_keys = ON;
