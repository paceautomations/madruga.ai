-- 001_initial.sql — SQLite Foundation for madruga.ai pipeline
-- Creates 8 core tables + indexes for pipeline state tracking

PRAGMA foreign_keys = ON;

-- ══════════════════════════════════════
-- Core entities
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS platforms (
    platform_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    title       TEXT,
    lifecycle   TEXT NOT NULL DEFAULT 'design'
                CHECK (lifecycle IN ('design', 'development', 'production', 'deprecated')),
    repo_path   TEXT NOT NULL,
    metadata    TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS epics (
    epic_id     TEXT NOT NULL,
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    appetite    TEXT,
    priority    INTEGER,
    branch_name TEXT,
    file_path   TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (platform_id, epic_id)
);

-- ══════════════════════════════════════
-- DAG Level 1: Platform pipeline nodes
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS pipeline_nodes (
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    node_id      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'done', 'stale', 'blocked', 'skipped')),
    output_hash  TEXT,
    input_hashes TEXT DEFAULT '{}',
    output_files TEXT DEFAULT '[]',
    completed_at TEXT,
    completed_by TEXT,
    line_count   INTEGER,
    PRIMARY KEY (platform_id, node_id)
);

-- ══════════════════════════════════════
-- DAG Level 2: Epic cycle nodes
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS epic_nodes (
    platform_id  TEXT NOT NULL,
    epic_id      TEXT NOT NULL,
    node_id      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'done', 'stale', 'blocked', 'skipped')),
    output_hash  TEXT,
    completed_at TEXT,
    completed_by TEXT,
    PRIMARY KEY (platform_id, epic_id, node_id),
    FOREIGN KEY (platform_id, epic_id) REFERENCES epics(platform_id, epic_id) ON DELETE CASCADE
);

-- ══════════════════════════════════════
-- Decisions (ADR registry + decision log)
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS decisions (
    decision_id         TEXT PRIMARY KEY,
    platform_id         TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    epic_id             TEXT,
    skill               TEXT NOT NULL,
    slug                TEXT,
    title               TEXT NOT NULL,
    number              INTEGER,
    status              TEXT NOT NULL DEFAULT 'accepted'
                        CHECK (status IN ('accepted', 'superseded', 'deprecated', 'proposed')),
    superseded_by       TEXT REFERENCES decisions(decision_id),
    source_decision_key TEXT,
    file_path           TEXT,
    decisions_json      TEXT DEFAULT '[]',
    assumptions_json    TEXT DEFAULT '[]',
    open_questions_json TEXT DEFAULT '[]',
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════
-- Artifact provenance
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS artifact_provenance (
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    file_path    TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    epic_id      TEXT,
    output_hash  TEXT,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (platform_id, file_path)
);

-- ══════════════════════════════════════
-- Pipeline runs (tracking)
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    epic_id      TEXT,
    node_id      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    agent        TEXT,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    cost_usd     REAL,
    duration_ms  INTEGER,
    error        TEXT,
    started_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    completed_at TEXT
);

-- ══════════════════════════════════════
-- Events (audit log, append-only)
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id TEXT REFERENCES platforms(platform_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    action      TEXT NOT NULL,
    actor       TEXT DEFAULT 'system',
    payload     TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════
-- Indexes
-- ══════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_epics_platform ON epics(platform_id);
CREATE INDEX IF NOT EXISTS idx_epics_status ON epics(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_platform ON pipeline_nodes(platform_id);
CREATE INDEX IF NOT EXISTS idx_epic_nodes_epic ON epic_nodes(platform_id, epic_id);
CREATE INDEX IF NOT EXISTS idx_decisions_platform ON decisions(platform_id);
CREATE INDEX IF NOT EXISTS idx_decisions_epic ON decisions(epic_id);
CREATE INDEX IF NOT EXISTS idx_provenance_platform ON artifact_provenance(platform_id);
CREATE INDEX IF NOT EXISTS idx_runs_platform ON pipeline_runs(platform_id);
CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_events_platform ON events(platform_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
