-- 018_commits_reconciled.sql — Reverse-Reconcile drift tracking
-- Adds reconciled_at watermark + extends source CHECK to include 'external-fetch'.
-- SQLite cannot ALTER CHECK constraints, so we recreate the table.
-- Pattern: identical to 017_add_queued_status.sql.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS commits_new;

CREATE TABLE commits_new (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sha            TEXT NOT NULL UNIQUE,
    message        TEXT NOT NULL,
    author         TEXT NOT NULL,
    platform_id    TEXT NOT NULL,
    epic_id        TEXT,
    source         TEXT NOT NULL DEFAULT 'hook'
                   CHECK (source IN ('hook', 'backfill', 'manual', 'reseed', 'external-fetch')),
    committed_at   TEXT NOT NULL,
    files_json     TEXT NOT NULL DEFAULT '[]',
    reconciled_at  TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

INSERT INTO commits_new (id, sha, message, author, platform_id, epic_id, source, committed_at, files_json, reconciled_at, created_at)
SELECT id, sha, message, author, platform_id, epic_id, source, committed_at, files_json, NULL, created_at
FROM commits;

DROP TABLE commits;
ALTER TABLE commits_new RENAME TO commits;

CREATE INDEX IF NOT EXISTS idx_commits_platform ON commits(platform_id);
CREATE INDEX IF NOT EXISTS idx_commits_epic ON commits(epic_id);
CREATE INDEX IF NOT EXISTS idx_commits_committed_at ON commits(committed_at);
CREATE INDEX IF NOT EXISTS idx_commits_reconciled_pending ON commits(platform_id) WHERE reconciled_at IS NULL;

PRAGMA foreign_keys = ON;
