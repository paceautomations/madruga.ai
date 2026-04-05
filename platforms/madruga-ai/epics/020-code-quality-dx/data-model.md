# Data Model: Code Quality & DX — Epic 020

**Generated**: 2026-04-04  
**Branch**: `epic/madruga-ai/020-code-quality-dx`

---

## Overview

This epic is a **code quality refactoring** — no schema changes, no new tables, no new external data stores. The "data model" here describes module boundaries, entity ownership, and the shape of new script outputs (memory consolidation report, logging events).

---

## 1. Module Boundary Map (db.py split)

### db_core.py — Connection & Infrastructure

**Owns**: Connection lifecycle, migration engine, FTS5 utilities, transaction context manager.

| Symbol | Type | Moved from |
|--------|------|-----------|
| `_check_fts5()` | function | db.py:44 |
| `_sanitize_fts5_query()` | function | db.py:61 |
| `_escape_like()` | function | db.py:66 |
| `_fts5_search()` | function | db.py:71 |
| `_now()` | function | db.py:123 |
| `_file_mtime_iso()` | function | db.py:127 |
| `_ClosingConnection` | class | db.py:152 |
| `get_conn()` | function | db.py:178 |
| `_BatchConnection` | class | db.py:195 |
| `transaction()` | contextmanager | db.py:219 |
| `_split_sql_statements()` | function | db.py:234 |
| `migrate()` | function | db.py:267 |
| `to_relative_path()` | function | db.py:352 |
| `compute_file_hash()` | function | db.py:363 |
| `_FTS5_AVAILABLE` | module global | db.py:38 |

**Imports**: stdlib only (`sqlite3`, `hashlib`, `json`, `pathlib`, `os`, `logging`, `contextlib`, `datetime`) + `config`, `errors`.  
**Exports**: All symbols above — re-exported by db.py facade.

---

### db_pipeline.py — Platform & Pipeline CRUD

**Owns**: Platform registry, pipeline node state, epic state, run tracking, gate management, stale node detection.

| Symbol | Type | Moved from |
|--------|------|-----------|
| `upsert_platform()` | function | db.py:374 |
| `get_platform()` | function | db.py:428 |
| `set_local_config()` | function | db.py:438 |
| `get_local_config()` | function | db.py:452 |
| `get_active_platform()` | function | db.py:458 |
| `resolve_repo_path()` | function | db.py:463 |
| `upsert_pipeline_node()` | function | db.py:496 |
| `get_pipeline_nodes()` | function | db.py:532 |
| `upsert_epic()` | function | db.py:545 |
| `get_epics()` | function | db.py:578 |
| `upsert_epic_node()` | function | db.py:591 |
| `get_epic_nodes()` | function | db.py:622 |
| `insert_run()` | function | db.py:1410 |
| `complete_run()` | function | db.py:1440 |
| `get_runs()` | function | db.py:1452 |
| `approve_gate()` | function | db.py:1465 |
| `reject_gate()` | function | db.py:1476 |
| `get_pending_gates()` | function | db.py:1487 |
| `get_resumable_nodes()` | function | db.py:1498 |
| `insert_event()` | function | db.py:1523 |
| `get_events()` | function | db.py:1549 |
| `get_stale_nodes()` | function | db.py:1572 |
| `repair_timestamps()` | function | db.py:1597 |
| `get_platform_status()` | function | db.py:1630 |
| `get_epic_status()` | function | db.py:1651 |
| `compute_epic_status()` | function | db.py:1673 |
| `_resolve_epic_outputs()` | function | db.py:1702 |
| `_is_valid_output()` | function | db.py:1707 |
| `seed_epic_nodes_from_disk()` | function | db.py:1728 |
| `seed_from_filesystem()` | function | db.py:1777 |
| `insert_provenance()` | function | db.py:1374 |
| `get_provenance()` | function | db.py:1397 |

**Imports**: `db_core` (get_conn, transaction, migrate, _now, _file_mtime_iso, to_relative_path, compute_file_hash) + stdlib + `yaml` + `config`.  
**Estimated LOC**: ~550

---

### db_decisions.py — Decisions & Memory

**Owns**: ADR/decision lifecycle, memory entries, FTS5 search on both, markdown import/export.

| Symbol | Type | Moved from |
|--------|------|-----------|
| `insert_decision()` | function | db.py:635 |
| `get_decisions()` | function | db.py:700 |
| `get_decisions_summary()` | function | db.py:722 |
| `insert_decision_link()` | function | db.py:780 |
| `get_decision_links()` | function | db.py:789 |
| `_parse_adr_markdown()` | function | db.py:822 |
| `import_adr_from_markdown()` | function | db.py:916 |
| `import_all_adrs()` | function | db.py:967 |
| `export_decision_to_markdown()` | function | db.py:980 |
| `sync_decisions_to_markdown()` | function | db.py:1098 |
| `search_decisions()` | function | db.py:1117 |
| `insert_memory()` | function | db.py:1134 |
| `get_memories()` | function | db.py:1177 |
| `update_memory()` | function | db.py:1194 |
| `delete_memory()` | function | db.py:1207 |
| `_parse_memory_markdown()` | function | db.py:1218 |
| `import_memory_from_markdown()` | function | db.py:1243 |
| `import_all_memories()` | function | db.py:1287 |
| `export_memory_to_markdown()` | function | db.py:1300 |
| `sync_memories_to_markdown()` | function | db.py:1331 |
| `search_memories()` | function | db.py:1346 |

**Imports**: `db_core` (get_conn, transaction, _fts5_search, _check_fts5, _now, to_relative_path) + stdlib + `yaml`.  
**Estimated LOC**: ~820

---

### db_observability.py — Traces & Eval Scores

**Owns**: Trace lifecycle, span tracking, eval score storage, stats queries, cleanup.

| Symbol | Type | Moved from |
|--------|------|-----------|
| `create_trace()` | function | db.py:2003 |
| `complete_trace()` | function | db.py:2023 |
| `get_traces()` | function | db.py:2055 |
| `get_trace_detail()` | function | db.py:2087 |
| `insert_eval_score()` | function | db.py:2118 |
| `get_eval_scores()` | function | db.py:2152 |
| `get_stats()` | function | db.py:2182 |
| `cleanup_old_data()` | function | db.py:2236 |

**Imports**: `db_core` (get_conn, transaction, _now) + stdlib.  
**Estimated LOC**: ~280

---

### db.py (re-export facade)

```python
"""
db.py — Re-export facade for backward compatibility.

All existing callers of `from db import X` continue to work unchanged.
New code should import directly from the appropriate submodule.
"""
from db_core import *          # noqa: F401, F403
from db_pipeline import *      # noqa: F401, F403
from db_decisions import *     # noqa: F401, F403
from db_observability import *  # noqa: F401, F403
```

**LOC**: ~10 lines

---

## 2. Log Event Shape

All internal script log events conform to this schema:

```python
# Human mode (default):
# "INFO platform_cli: Importing ADRs for platform 'madruga-ai'"

# JSON mode (--json flag):
{
  "timestamp": "2026-04-04T12:00:00.000Z",  # ISO 8601 UTC
  "level": "INFO",                            # DEBUG | INFO | WARNING | ERROR
  "message": "Importing ADRs for platform 'madruga-ai'",
  "logger": "platform_cli"                   # script name
}
```

**NDJSON**: one JSON object per line, no trailing comma, no array wrapper.

---

## 3. Memory Consolidation Report Shape

Output of `memory_consolidate.py --dry-run` (printed to stdout, not written to disk):

```
Memory Consolidation Report
============================
Scanned: 12 files
Date: 2026-04-04T12:00:00Z

STALE (>90 days without update):
  - project_sprint0_review.md (last modified: 2026-01-05, 89 days ago)
  - feedback_testing.md (last modified: 2025-12-01, 124 days ago)

POSSIBLE DUPLICATES (same type + overlapping description):
  - project_epic012.md ↔ project_epic012_learnings.md (type: project, similarity: 0.62)

INDEX HEALTH:
  - MEMORY.md: 187 lines (WARNING: approaching 200-line limit)

ACTIONS SUGGESTED:
  1. Review or delete: project_sprint0_review.md (stale)
  2. Review or delete: feedback_testing.md (stale)
  3. Consider merging: project_epic012.md + project_epic012_learnings.md
  4. Prune MEMORY.md to free up index capacity

Run with --apply to mark stale entries for review (adds [STALE] prefix to body).
```

**`--apply` mode**: Writes `[STALE - review by YYYY-MM-DD]` header to flagged files. Never deletes. Never merges automatically.

---

## 4. Skill Lint Check Extensions

New checks added to `lint_single_skill()` in `skill-lint.py`:

| Check ID | What is checked | How | Severity |
|----------|----------------|-----|---------|
| `gate-valid` | `frontmatter['gate']` in `VALID_GATES` | Import `VALID_GATES` from `errors.py` | ERROR |
| `output-dir` | Body contains `## Output Directory` section | Regex on all archetypes (extend from pipeline-only) | WARNING |
| `handoffs-present` | `frontmatter.get('handoffs')` is non-empty list | Already partly exists; ensure all archetypes covered | NIT |

**VALID_GATES** (from errors.py, already defined):
```python
frozenset({"auto", "human", "1-way-door", "auto-escalate"})
```

---

## 5. Test File Inventories

### test_db_core.py (new)
Tests covering: connection lifecycle (`_ClosingConnection`), migration idempotency, `transaction()` rollback, `_check_fts5()` caching, `_fts5_search()` LIKE fallback.

### test_db_pipeline.py (renamed from test_db_crud.py)
Tests covering: `upsert_platform`, `upsert_pipeline_node`, `upsert_epic`, `insert_run`/`complete_run`, `get_pending_gates`, `compute_epic_status`, `get_stale_nodes`.

### test_vision_build.py (new, ≥5 cases)
| # | Test | Mock |
|---|------|------|
| 1 | `_containers_table()` with minimal JSON | None |
| 2 | `_domains_table()` with minimal JSON | None |
| 3 | `update_markdown()` round-trip | tmp_path fixture |
| 4 | `export_json()` success path | `subprocess.run` returning JSON |
| 5 | `export_png()` with missing CLI | `subprocess.run` raising `FileNotFoundError` |
| 6 | `validate_model()` with invalid dir | `subprocess.run` returning returncode=1 |

### test_sync_memory.py (new, ≥5 cases)
| # | Test | Mock |
|---|------|------|
| 1 | `import_memory_from_markdown()` basic frontmatter | tmp_path + in-memory DB |
| 2 | Type preservation: all 4 types round-trip | in-memory DB |
| 3 | `export_memory_to_markdown()` produces valid frontmatter | in-memory DB |
| 4 | Full round-trip: import → export → compare | in-memory DB |
| 5 | Malformed frontmatter: skip gracefully | tmp_path |
| 6 | MEMORY.md index update after export | tmp_path |
