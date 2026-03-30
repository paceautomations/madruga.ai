-- 003a_decisions_memory.sql — Expand decisions table + add memory_entries + decision_links
-- Supports: BD as source of truth for decisions and memory (epic 009)
-- Split from 003_decisions_memory.sql: this file contains safe DDL (no FTS5 dependency)

-- ══════════════════════════════════════
-- Expand decisions table (5 new nullable columns)
-- Note: ALTER TABLE ADD COLUMN in SQLite does not support CHECK constraints
-- ══════════════════════════════════════

ALTER TABLE decisions ADD COLUMN content_hash TEXT;
ALTER TABLE decisions ADD COLUMN decision_type TEXT;
ALTER TABLE decisions ADD COLUMN context TEXT;
ALTER TABLE decisions ADD COLUMN consequences TEXT;
ALTER TABLE decisions ADD COLUMN tags_json TEXT DEFAULT '[]';

-- ══════════════════════════════════════
-- Decision links (cross-references between decisions)
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS decision_links (
    from_decision_id TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    to_decision_id   TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    link_type        TEXT NOT NULL
                     CHECK (link_type IN ('supersedes', 'depends_on', 'related', 'contradicts', 'amends')),
    PRIMARY KEY (from_decision_id, to_decision_id, link_type)
);

CREATE INDEX IF NOT EXISTS idx_decision_links_to ON decision_links(to_decision_id);

-- ══════════════════════════════════════
-- Memory entries
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS memory_entries (
    memory_id   TEXT PRIMARY KEY,
    platform_id TEXT REFERENCES platforms(platform_id) ON DELETE CASCADE,
    type        TEXT NOT NULL
                CHECK (type IN ('user', 'feedback', 'project', 'reference')),
    name        TEXT NOT NULL,
    description TEXT,
    content     TEXT NOT NULL,
    source      TEXT,
    file_path   TEXT,
    content_hash TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(type);
CREATE INDEX IF NOT EXISTS idx_memory_platform ON memory_entries(platform_id);
CREATE INDEX IF NOT EXISTS idx_memory_hash ON memory_entries(content_hash);

-- ══════════════════════════════════════
-- Additional indexes on decisions
-- ══════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_decisions_hash ON decisions(content_hash);
