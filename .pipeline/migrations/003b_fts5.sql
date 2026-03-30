-- 003b_fts5.sql — FTS5 virtual tables + sync triggers (requires FTS5 extension)
-- Split from 003_decisions_memory.sql: skipped gracefully if FTS5 unavailable

-- ══════════════════════════════════════
-- FTS5 virtual tables
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
