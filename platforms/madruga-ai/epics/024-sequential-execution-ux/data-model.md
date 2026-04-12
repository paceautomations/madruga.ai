# Data Model: Sequential Execution UX

**Epic**: 024-sequential-execution-ux
**Date**: 2026-04-11
**Scope**: SQLite schema changes, state machine, indexing strategy for the new `queued` status.

---

## 1. Current `epics` table (pre-migration 017)

**Source of truth**: `.pipeline/madruga.db`, captured 2026-04-11:

```sql
CREATE TABLE "epics" (
    epic_id      TEXT NOT NULL,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'proposed'
                 CHECK (status IN ('proposed', 'drafted', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    priority     INTEGER,
    branch_name  TEXT,
    file_path    TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    delivered_at TEXT,
    PRIMARY KEY (platform_id, epic_id)
);

CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_epics_status   ON epics(status);
```

**Observations**:
- `status` is a TEXT column with a CHECK constraint — the very constraint migration 017 must modify.
- `updated_at` has a DEFAULT that fires **only on INSERT**, not on UPDATE. SQLite has no native ON UPDATE trigger; `db_pipeline.py` must explicitly set `updated_at = strftime(...)` on every `UPDATE epics SET status = ...`.
- `idx_epics_status` already exists — perfect for `WHERE status = 'queued'` queue lookup. No new index needed.
- Composite primary key `(platform_id, epic_id)` — scopes queues per platform automatically.

---

## 2. Target schema (post-migration 017)

**Only difference**: `queued` added to the CHECK constraint enum.

```sql
CREATE TABLE "epics" (
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

CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_epics_status   ON epics(status);
```

**No new columns**. No new tables. No new indexes.

---

## 3. Migration 017 — rec-table pattern

SQLite cannot `ALTER` a CHECK constraint in place. The migration follows the exact pattern of `009_add_drafted_status.sql`:

```sql
-- 017_add_queued_status.sql
-- Purpose: Add 'queued' to the epics.status CHECK constraint for auto-promotion queue.
-- Pattern: rec-table (SQLite cannot ALTER CHECK constraints).
-- Reference: Migration 009 (added 'drafted'), same structure.

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

-- 2. Copy all existing rows (order preserved, all statuses pass the new constraint).
INSERT INTO epics_new
SELECT epic_id, platform_id, title, status, priority, branch_name, file_path,
       created_at, updated_at, delivered_at
FROM epics;

-- 3. Drop the old table.
DROP TABLE epics;

-- 4. Rename new → current.
ALTER TABLE epics_new RENAME TO epics;

-- 5. Recreate indexes (DROP TABLE removed them).
CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_epics_status   ON epics(status);

PRAGMA foreign_keys = ON;

-- 6. Bump schema version marker.
PRAGMA user_version = 17;

COMMIT;
```

**Idempotency**: The migration is wrapped in a transaction and uses `CREATE TABLE epics_new` (not `CREATE TABLE IF NOT EXISTS ...`). If re-run after success, it will fail at step 1 with "table epics_new already exists" OR at step 4 with "table epics already exists" — neither leaves partial state because the transaction aborts.

**Safer re-run guard** (recommended for tooling that applies migrations idempotently):

```python
def migration_017_needs_apply(conn: sqlite3.Connection) -> bool:
    """Return True if migration 017 has not been applied yet."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return row[0] < 17
```

The migration runner uses `user_version` as the bookmark and skips already-applied migrations.

---

## 4. State machine

### 4.1 Current state machine (before migration 017)

```
┌─────────┐   operator action    ┌─────────┐  operator action  ┌─────────────┐
│proposed │─────────────────────>│ drafted │──────────────────>│ in_progress │
└─────────┘                      └─────────┘                    └─────────────┘
                                     │                                │
                                     │  cancel                         │
                                     ▼                                 ▼
                                ┌──────────┐                      ┌────────┐
                                │cancelled │                      │shipped │
                                └──────────┘                      └────────┘
                                                                       │
                                                                       │ (failure during L2)
                                                                       ▼
                                                                  ┌────────┐
                                                                  │blocked │
                                                                  └────────┘
```

### 4.2 New state machine (after epic 024)

```
┌─────────┐   operator action    ┌─────────┐     /epic-context          ┌─────────────┐
│proposed │─────────────────────>│ drafted │────────────────────────────>│ in_progress │
└─────────┘                      └─────────┘                              └─────────────┘
                                     │  ▲                                       │
                                     │  │ /dequeue (operator)                   │
                              /queue │  │                                       │
                                     ▼  │                                       │
                                 ┌────────┐                                     │
                                 │ queued │ ◄──────────── auto-promotion (hook) │
                                 └────────┘                                     │
                                     │                                          │
                                     │ auto-promotion                           ▼
                                     └──────────────────────────────>┌─────────────┐
                                                                     │ in_progress │
                                                                     └─────────────┘
                                                                           │
                                                              (as in 4.1)  ▼
                                                                     shipped / blocked
```

### 4.3 Transition table (complete)

| From | To | Trigger | Actor | Validation |
|------|----|---------|-------|------------|
| `proposed` | `drafted` | `/madruga:epic-context --draft` | Operator | Pitch.md exists |
| `drafted` | `in_progress` | `/madruga:epic-context` (normal mode) | Operator | On base branch |
| `drafted` | **`queued`** | `/madruga:epic-context --queue` OR `platform_cli.py queue <p> <e>` | Operator | Epic is in `drafted`; platform has `repo.isolation: branch` (if using new mode) |
| `drafted` | `cancelled` | Operator | Operator | — |
| **`queued`** | **`drafted`** | `platform_cli.py dequeue <p> <e>` | Operator | Epic is in `queued`; running slot free OR still in queue |
| **`queued`** | **`in_progress`** | Auto-promotion hook (easter.py) | System | `_running_epics` empty AND `MADRUGA_QUEUE_PROMOTION=1` AND no dirty tree AND git ops succeed |
| **`queued`** | **`blocked`** | Auto-promotion permanent failure | System | Retry budget exhausted OR dirty tree detected |
| `in_progress` | `shipped` | L2 cycle completion | System | All 12 L2 nodes completed |
| `in_progress` | `blocked` | L2 cycle failure | System | Skill failure after retries |
| `blocked` | `queued` | Operator re-enables | Operator | Manual intervention required — matches existing manual recovery from blocked |
| `blocked` | `drafted` | Operator reset | Operator | Manual |

**Invariants**:
- At most one epic per platform in `in_progress` at any time (sequential invariant, ADR-006, pitch.md §Applicable Constraints).
- An epic in `queued` cannot transition to `in_progress` except through the auto-promotion hook (FR-008). `compute_epic_status()` must treat `queued` as a no-auto-promote status, same as `drafted`/`blocked`/`cancelled`/`shipped`.
- No direct `proposed` → `queued` transition. Queue acts on drafted epics only (matches operator intuition: "I'm queuing something I've already drafted").

### 4.4 `compute_epic_status()` change

Current guard in `.specify/scripts/db_pipeline.py:917` (verified in Phase 0 exploration):

```python
if current_status in ("blocked", "cancelled", "shipped", "drafted"):
    return current_status, None
```

**Change**:

```python
if current_status in ("blocked", "cancelled", "shipped", "drafted", "queued"):
    return current_status, None
```

**Why**: `queued` epics must not be auto-promoted to `in_progress` by the node-completion inference logic. Only the explicit promotion hook may transition `queued` → `in_progress` (FR-008).

### 4.5 `_EPIC_STATUS_MAP` change

Current map in `db_pipeline.py` (line ~30, per pitch §Resolved Gray Area #6):

```python
_EPIC_STATUS_MAP = {
    "proposed": "proposed",
    "drafted": "drafted",
    "in_progress": "in_progress",
    "shipped": "shipped",
    "blocked": "blocked",
    "cancelled": "cancelled",
}
```

**Change**:

```python
_EPIC_STATUS_MAP = {
    "proposed": "proposed",
    "drafted": "drafted",
    "queued": "queued",
    "in_progress": "in_progress",
    "shipped": "shipped",
    "blocked": "blocked",
    "cancelled": "cancelled",
}
```

**Why**: `post_save.py --epic-status queued` must not be silently mapped to `None`. Without this entry, the CLI path that explicitly sets `queued` via post_save would corrupt the write.

---

## 5. Queue lookup query (FR-009)

**Query** used by `get_next_queued_epic(conn, platform_id)` in db_pipeline.py:

```sql
SELECT epic_id, platform_id, title, branch_name, updated_at
FROM epics
WHERE platform_id = ?
  AND status = 'queued'
ORDER BY updated_at ASC, epic_id ASC
LIMIT 1;
```

**Ordering rationale**:
- Primary: `updated_at ASC` — the epic that has been in `queued` status longest comes first (FIFO). This matches clarification Q3's answer: "time the epic most recently transitioned INTO the `queued` status".
- Secondary: `epic_id ASC` — deterministic tiebreaker if two epics are queued in the same second.

**Dependency**: `db_pipeline.py` MUST set `updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')` on every status UPDATE. This is a pre-existing invariant — verify in P2 when modifying `db_pipeline.py`. If the existing code relies on the INSERT default and never writes to `updated_at` on UPDATE, add the explicit write as part of P2.

**Index usage**: `idx_epics_status` already indexes `status`. The query is `WHERE platform_id = ? AND status = ?` — SQLite will use either `idx_epics_platform` or `idx_epics_status`. Given queue depth ≤ 3, performance is not a concern. No new index required.

---

## 6. Entity relationships

### 6.1 Epic ←→ Platform

Unchanged. `epics.platform_id` FKs to `platforms.platform_id`. Cascade-delete preserved.

### 6.2 Queue ←→ Epic

There is NO separate queue entity. The "queue" is a logical view: `SELECT * FROM epics WHERE platform_id = ? AND status = 'queued' ORDER BY updated_at ASC`. Each epic in the view is a queue entry. Queue depth per platform is `COUNT(*)` of that view.

### 6.3 Running slot ←→ Epic

There is NO separate running_slot entity. The "running slot" is `SELECT epic_id FROM epics WHERE platform_id = ? AND status = 'in_progress'` — sequential invariant means at most one row.

The in-memory `_running_epics: set[str]` in `easter.py` is the **runtime cache** of this query, kept in sync by the dispatch loop. The promotion hook reads `_running_epics` (not the DB) for performance — DB is authoritative on startup.

---

## 7. Migration test plan

Per `research.md` §R11–R12, the migration test is an integration test against a real SQLite temp file:

```python
def test_migration_017_preserves_existing_rows(tmp_path):
    """Migration 017 must preserve all existing epic rows across all statuses."""
    db_path = tmp_path / "test.db"
    # 1. Create DB at pre-017 schema (use migration 016 as base, or construct manually)
    # 2. INSERT one row per existing status: proposed, drafted, in_progress, shipped, blocked, cancelled
    # 3. Run migration 017
    # 4. Verify: all 6 rows still present, indexes recreated, user_version == 17
    # 5. Verify: INSERT with status='queued' succeeds (new enum value accepted)
    # 6. Verify: INSERT with status='nonsense' fails (CHECK still enforced)

def test_migration_017_idempotent(tmp_path):
    """Running migration 017 twice is safe (second run is a no-op via user_version guard)."""
    db_path = tmp_path / "test.db"
    # 1. Apply migration 017 once
    # 2. Verify user_version == 17
    # 3. Apply migration 017 again via the idempotency guard → no-op
    # 4. Verify schema unchanged, data unchanged, user_version still 17
```

---

## 8. Risks from this schema change

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Migration corrupts `.pipeline/madruga.db` | Very Low (rec-table is proven in migration 009) | Camada 1 backup, test on copy first, rollback via restore |
| `updated_at` not written on UPDATE causes wrong FIFO order | Medium | P2 explicit audit of `db_pipeline.py` UPDATE statements; add explicit `SET updated_at` where missing |
| Tests against temp DB drift from real schema | Low | Integration test uses the same migration file the production pipeline applies |
| `compute_epic_status` guard miss on `queued` causes auto-promotion to `in_progress` via node completion | Low (caught in unit test `test_compute_epic_status_queued_guard`) | TDD — test written before code |
| `_EPIC_STATUS_MAP` miss on `queued` causes silent `None` on post_save | Low (caught in unit test) | TDD |
| `post_save.py` writes to a drafted epic while this epic's planning session is running | Non-issue | Planning skills (specify/clarify/plan/tasks/analyze) do NOT call `post_save.py` (verified in Phase 0 exploration — zero grep matches) |

---

## 9. Summary

Schema change is minimal: **one CHECK constraint value added**. Two code changes in `db_pipeline.py`: **one list entry, one dict entry, one new function**. Everything else — queue lookup, FIFO ordering, state machine — is implemented in terms of the existing schema plus the new status value. No new tables, no new indexes, no new columns. This is the smallest possible data-model change that satisfies the feature.
