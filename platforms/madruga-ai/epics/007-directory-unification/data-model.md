# Data Model: Directory Unification

## Existing Entities (no changes needed)

### epic_nodes (SQLite — already in 001_initial.sql)

```sql
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
```

**Valid node_id values** (epic cycle): `epic-context`, `specify`, `clarify`, `plan`, `tasks`, `analyze`, `implement`, `verify`, `qa`, `reconcile`

**Status transitions**:
```
pending → done (skill completed successfully)
pending → skipped (optional node, conditions met to skip)
pending → blocked (dependency not met)
done → stale (dependency re-executed after this node)
```

### HandoffBlock (YAML in artifact footer — not in DB)

```yaml
---
handoff:
  from: string       # Current skill ID (e.g., "epic-context")
  to: string         # Next skill ID (e.g., "specify")
  context: string    # Free text — decisions, constraints, key info for next skill
  blockers: string[] # List of unresolved impediments (empty if none)
```

Not persisted in SQLite. Lives in the generated artifact file. Read by the next skill as context.

### epic_cycle (YAML in platform.yaml — not in DB)

```yaml
epic_cycle:
  nodes:
    - id: string          # Node ID (e.g., "epic-context")
      skill: string       # Skill reference (e.g., "madruga:epic-context")
      outputs: string[]   # Template paths with {epic} placeholder
      depends: string[]   # Node IDs this depends on
      gate: string        # human | auto | 1-way-door | auto-escalate
      optional: boolean   # Default false
      skip_condition: string  # When to skip optional nodes
```

Declared in `platform.yaml`, read by `check-platform-prerequisites.sh --epic`. The `{epic}` placeholder is resolved to `epics/<NNN-slug>/` at runtime.

## Existing db.py Functions (already implemented)

| Function | Table | Purpose |
|----------|-------|---------|
| `upsert_epic_node()` | epic_nodes | Create/update epic cycle node status |
| `get_epic_nodes()` | epic_nodes | List all nodes for an epic |
| `get_epic_status()` | epic_nodes | Summary counts (done/pending/blocked) |
| `upsert_epic()` | epics | Create/update epic record |
| `get_epics()` | epics | List all epics for a platform |

**No new db.py functions needed.** All CRUD operations for L2 are already implemented.
