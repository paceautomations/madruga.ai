-- 009_add_drafted_status.sql — Add 'drafted' to epics.status CHECK constraint
-- Supports --draft mode for epic-context (plan ahead without creating branch)
-- SQLite cannot ALTER CHECK constraints, so we recreate the table.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS epics_new;

CREATE TABLE epics_new (
    epic_id      TEXT NOT NULL,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'proposed'
                 CHECK (status IN ('proposed', 'drafted', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    appetite     TEXT,
    priority     INTEGER,
    branch_name  TEXT,
    file_path    TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    delivered_at TEXT,
    PRIMARY KEY (platform_id, epic_id)
);

INSERT INTO epics_new SELECT * FROM epics;

DROP TABLE epics;
ALTER TABLE epics_new RENAME TO epics;

CREATE INDEX IF NOT EXISTS idx_epics_platform ON epics(platform_id);
CREATE INDEX IF NOT EXISTS idx_epics_status ON epics(status);

PRAGMA foreign_keys = ON;
