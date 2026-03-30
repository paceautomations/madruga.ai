-- 005_platform_repo.sql — Platform-repo binding + local config
-- Adds repo/branch/tags fields to platforms table and machine-local config table.

-- ══════════════════════════════════════
-- Expand platforms table with repo info
-- ══════════════════════════════════════

ALTER TABLE platforms ADD COLUMN repo_org TEXT;
ALTER TABLE platforms ADD COLUMN repo_name TEXT;
ALTER TABLE platforms ADD COLUMN base_branch TEXT DEFAULT 'main';
ALTER TABLE platforms ADD COLUMN epic_branch_prefix TEXT;
ALTER TABLE platforms ADD COLUMN tags_json TEXT DEFAULT '[]';

-- ══════════════════════════════════════
-- Machine-local configuration
-- Not committed to git (lives inside .pipeline/madruga.db which is gitignored)
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS local_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
