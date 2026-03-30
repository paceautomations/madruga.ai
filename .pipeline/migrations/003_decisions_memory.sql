-- 003_decisions_memory.sql — Expand decisions table + add memory_entries + decision_links + FTS5
-- Supports: BD as source of truth for decisions and memory (epic 009)

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

-- ══════════════════════════════════════
-- FTS5 virtual tables + sync triggers
-- (These require FTS5 support in SQLite — skipped gracefully if unavailable)
-- ══════════════════════════════════════

CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
    title, context, consequences, content='decisions', content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    name, description, content, content='memory_entries', content_rowid='rowid'
);

-- Triggers to keep FTS in sync with decisions table

CREATE TRIGGER decisions_fts_insert AFTER INSERT ON decisions BEGIN
    INSERT INTO decisions_fts(rowid, title, context, consequences)
    VALUES (NEW.rowid, NEW.title, NEW.context, NEW.consequences);
END;

CREATE TRIGGER decisions_fts_delete BEFORE DELETE ON decisions BEGIN
    INSERT INTO decisions_fts(decisions_fts, rowid, title, context, consequences)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.context, OLD.consequences);
END;

CREATE TRIGGER decisions_fts_update AFTER UPDATE ON decisions BEGIN
    INSERT INTO decisions_fts(decisions_fts, rowid, title, context, consequences)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.context, OLD.consequences);
    INSERT INTO decisions_fts(rowid, title, context, consequences)
    VALUES (NEW.rowid, NEW.title, NEW.context, NEW.consequences);
END;

-- Triggers to keep FTS in sync with memory_entries table

CREATE TRIGGER memory_fts_insert AFTER INSERT ON memory_entries BEGIN
    INSERT INTO memory_fts(rowid, name, description, content)
    VALUES (NEW.rowid, NEW.name, NEW.description, NEW.content);
END;

CREATE TRIGGER memory_fts_delete BEFORE DELETE ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, name, description, content)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.description, OLD.content);
END;

CREATE TRIGGER memory_fts_update AFTER UPDATE ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, name, description, content)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.description, OLD.content);
    INSERT INTO memory_fts(rowid, name, description, content)
    VALUES (NEW.rowid, NEW.name, NEW.description, NEW.content);
END;
