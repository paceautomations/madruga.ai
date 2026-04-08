-- 014_commits.sql — Commit Traceability (Epic 023)
-- Tracks git commits linked to platforms and epics for full change visibility.

CREATE TABLE IF NOT EXISTS commits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sha          TEXT NOT NULL UNIQUE,
    message      TEXT NOT NULL,
    author       TEXT NOT NULL,
    platform_id  TEXT NOT NULL,
    epic_id      TEXT,
    source       TEXT NOT NULL DEFAULT 'hook'
                 CHECK (source IN ('hook', 'backfill', 'manual', 'reseed')),
    committed_at TEXT NOT NULL,
    files_json   TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Indexes for frequent query patterns
CREATE INDEX IF NOT EXISTS idx_commits_platform ON commits(platform_id);
CREATE INDEX IF NOT EXISTS idx_commits_epic ON commits(epic_id);
CREATE INDEX IF NOT EXISTS idx_commits_committed_at ON commits(committed_at);
