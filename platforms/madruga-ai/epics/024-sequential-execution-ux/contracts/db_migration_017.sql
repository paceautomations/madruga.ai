-- Migration 017: Add 'queued' to epics.status CHECK constraint
-- Pattern: rec-table (SQLite cannot ALTER CHECK constraints in place)
-- Precedent: .specify/migrations/009_add_drafted_status.sql
-- Epic: 024-sequential-execution-ux
-- Author: planning phase (spec.md FR-006, decisions.md #2, data-model.md §3)
--
-- Idempotency guard (executed by the migration runner in db_pipeline.py, NOT by this SQL):
--   PRAGMA user_version  -->  if >= 17, skip this file entirely.
--
-- Rollback: run 017_add_queued_status_rollback.sql (NOT created by this epic — rollback
--           is manual via rec-table back to the pre-017 CHECK constraint).

BEGIN;

PRAGMA foreign_keys = OFF;

-- 1. Create the new table with the updated CHECK constraint.
CREATE TABLE epics_new (
    epic_id      TEXT NOT NULL,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'proposed'
                 CHECK (status IN ('proposed', 'drafted', 'queued', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    priority     INTEGER,
    branch_name  TEXT,
    file_path    TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    delivered_at TEXT,
    PRIMARY KEY (platform_id, epic_id)
);

-- 2. Copy all existing rows. All pre-017 statuses are members of the new CHECK set,
--    so this copy cannot fail on constraint violation.
INSERT INTO epics_new (
    epic_id, platform_id, title, status, priority, branch_name, file_path,
    created_at, updated_at, delivered_at
)
SELECT
    epic_id, platform_id, title, status, priority, branch_name, file_path,
    created_at, updated_at, delivered_at
FROM epics;

-- 3. Drop the old table. This also drops its indexes.
DROP TABLE epics;

-- 4. Rename new table to current name.
ALTER TABLE epics_new RENAME TO epics;

-- 5. Recreate indexes (previous schema had these two).
CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_epics_status   ON epics(status);

PRAGMA foreign_keys = ON;

-- 6. Bump schema version marker. Migration runner uses PRAGMA user_version
--    as the bookmark to skip already-applied migrations.
PRAGMA user_version = 17;

COMMIT;
