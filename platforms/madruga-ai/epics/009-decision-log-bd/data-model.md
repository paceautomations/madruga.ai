# Data Model: BD como Source of Truth para Decisions + Memory

**Date**: 2026-03-29

## Entity Relationship Diagram

```
platforms 1──N decisions
platforms 1──N memory_entries
decisions N──N decisions (via decision_links)
decisions 1──N events (entity_type='decision')
memory_entries 1──N events (entity_type='memory')
epics 1──N decisions (optional, via epic_id)
```

## Entities

### decisions (MODIFIED — 5 new columns)

Existing columns preserved. New columns:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| content_hash | TEXT | YES | NULL | SHA-256 do markdown exportado |
| decision_type | TEXT | YES | NULL | CHECK (technology, architecture, process, integration, tradeoff) |
| context | TEXT | YES | NULL | "Por que" extraido de ## Contexto |
| consequences | TEXT | YES | NULL | Extraido de ## Consequencias |
| tags_json | TEXT | YES | '[]' | JSON array de tags |

**Identity**: `decision_id` (TEXT PK, hex random)
**Uniqueness**: `decision_id` global unique. Para ADRs formais: `(platform_id, number)` e unique de facto.
**Lifecycle**: proposed → accepted → superseded | deprecated

**ADR formal vs micro-decision**:
- ADR formal: `number IS NOT NULL` AND `skill = 'adr'`
- Micro-decision: `number IS NULL` AND `skill` indica a skill de origem

### decision_links (NEW)

| Column | Type | Nullable | Constraint |
|--------|------|----------|------------|
| from_decision_id | TEXT | NOT NULL | FK → decisions(decision_id) ON DELETE CASCADE |
| to_decision_id | TEXT | NOT NULL | FK → decisions(decision_id) ON DELETE CASCADE |
| link_type | TEXT | NOT NULL | CHECK (supersedes, depends_on, related, contradicts, amends) |

**Identity**: PK (from_decision_id, to_decision_id, link_type)
**Directionality**: from → to. "A supersedes B" means from=A, to=B.

### memory_entries (NEW)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| memory_id | TEXT | NOT NULL | — | PK, hex random |
| platform_id | TEXT | YES | NULL | FK → platforms. NULL = cross-platform |
| type | TEXT | NOT NULL | — | CHECK (user, feedback, project, reference) |
| name | TEXT | NOT NULL | — | Short name |
| description | TEXT | YES | NULL | One-line description |
| content | TEXT | NOT NULL | — | Full body |
| source | TEXT | YES | NULL | Origin (skill, session, manual) |
| file_path | TEXT | YES | NULL | Original/export file path |
| content_hash | TEXT | YES | NULL | SHA-256 for sync detection |
| created_at | TEXT | NOT NULL | now() | ISO 8601 |
| updated_at | TEXT | NOT NULL | now() | ISO 8601 |

**Identity**: `memory_id` (TEXT PK, hex random)
**Lifecycle**: Created → Updated → Deleted (hard delete, no soft delete)

### decisions_fts (NEW — FTS5 virtual table)

External content table synced from `decisions` via triggers.
Indexed columns: `title`, `context`, `consequences`

### memory_fts (NEW — FTS5 virtual table)

External content table synced from `memory_entries` via triggers.
Indexed columns: `name`, `description`, `content`

## State Transitions

### Decision Status
```
proposed → accepted (approved by human gate)
accepted → superseded (new decision replaces)
accepted → deprecated (no longer relevant)
proposed → deprecated (rejected before acceptance)
```

### Memory Entry
No formal states — CRUD lifecycle (create, read, update, delete).

## Validation Rules

| Entity | Rule |
|--------|------|
| Decision | `title` NOT NULL, `skill` NOT NULL |
| Decision | `number` must be unique per `platform_id` when NOT NULL |
| Decision | `decision_type` must be in enum when NOT NULL |
| Decision | `status` must be in (proposed, accepted, superseded, deprecated) |
| Decision Link | `from_decision_id` != `to_decision_id` (no self-links) |
| Decision Link | `link_type` must be in enum |
| Memory | `type` must be in (user, feedback, project, reference) |
| Memory | `name` NOT NULL, `content` NOT NULL |

## Data Volume Estimates

| Entity | Current | 6-month projection |
|--------|---------|-------------------|
| decisions | 19 (Fulano ADRs) | ~50-80 (ADRs + micro-decisions across platforms) |
| decision_links | 0 | ~20-40 |
| memory_entries | ~5 (current .claude/memory/) | ~30-50 |
| events | ~0 (unused) | ~200+ (every decision/memory operation) |
