-- 016_platform_lifecycle_building.sql
-- Add 'building' as a valid platform lifecycle value.
--
-- Context: epic/prosauai/002-observability reconcile transitioned the
-- prosauai platform from 'design' to 'building' (user-facing terminology for
-- "implementation in progress"), but the original CHECK constraint only
-- accepted {design, development, production, deprecated}. Any reseed after
-- that point failed with:
--
--   sqlite3.IntegrityError: CHECK constraint failed:
--     lifecycle IN ('design', 'development', 'production', 'deprecated')
--
-- SQLite does not allow ALTER TABLE ... DROP CONSTRAINT, so we use the
-- canonical "recreate + copy" migration pattern documented in the SQLite docs
-- (https://www.sqlite.org/lang_altertable.html#otheralter).

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

CREATE TABLE platforms_new (
    platform_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    title       TEXT,
    lifecycle   TEXT NOT NULL DEFAULT 'design'
                CHECK (lifecycle IN ('design', 'development', 'building', 'production', 'deprecated')),
    repo_path   TEXT NOT NULL,
    metadata    TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    repo_org           TEXT,
    repo_name          TEXT,
    base_branch        TEXT DEFAULT 'main',
    epic_branch_prefix TEXT,
    tags_json          TEXT DEFAULT '[]'
);

INSERT INTO platforms_new
SELECT platform_id, name, title, lifecycle, repo_path, metadata,
       created_at, updated_at, repo_org, repo_name, base_branch,
       epic_branch_prefix, tags_json
FROM platforms;

DROP TABLE platforms;
ALTER TABLE platforms_new RENAME TO platforms;

COMMIT;

PRAGMA foreign_keys = ON;
