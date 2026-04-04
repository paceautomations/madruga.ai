# Research: Code Quality & DX — Epic 020

**Generated**: 2026-04-04  
**Branch**: `epic/madruga-ai/020-code-quality-dx`

---

## Decision 1: db.py Split Strategy

**Decision**: Split `db.py` (2,268 LOC) into 4 focused modules with a re-export facade in `db.py`.

**Rationale**:
- 2,268 lines with 6 distinct responsibilities creates cognitive load and merge conflict risk
- Python module system makes file-level splits natural — each module is a discoverable unit
- Re-export facade (`from db_core import *; from db_pipeline import *; ...`) preserves 100% backward compat with zero caller changes
- `_check_fts5()` global state must remain in `db_core.py` (the leaf module) to avoid initialization races

**Import dependency graph** (verified by reading db.py):
- `db_core.py`: leaf — imports only from stdlib + config + errors (no cross-module deps)
- `db_pipeline.py` → `db_core` (get_conn, transaction, migrate)
- `db_decisions.py` → `db_core` (get_conn, transaction, _fts5_search, _check_fts5)
- `db_observability.py` → `db_core` (get_conn, transaction)
- `db.py` (facade) → all 4 modules via `*` re-exports

**Alternatives considered**:
- A: Keep db.py as monolith — rejected (status quo, fails the 600-line target)
- B: Split by layer (read/write) instead of concern — rejected (creates cross-cutting complexity)
- C: Use a package `db/` with `__init__.py` — rejected (breaks `from db import X` without added value)

---

## Decision 2: Structured Logging Strategy

**Decision**: Use Python stdlib `logging` module with consistent `basicConfig` format. No new external dependencies.

**Rationale**:
- `structlog` is explicitly out of scope (no new deps per pitch + spec)
- stdlib `logging` supports both human-readable (levelname prefix) and JSON-formatted output
- NDJSON mode: custom `logging.Formatter` that serializes the `LogRecord` to JSON — no third-party needed
- Pattern already consistent with Constitution §IX (structured format with `level`, `message`, `timestamp`)

**Existing print patterns to replace** (confirmed in platform_cli.py):
- `print(f"  [ok] {msg}")` → `log.info(msg)` 
- `print(f"  [warn] {msg}")` → `log.warning(msg)`
- `print(f"  [error] {msg}")` → `log.error(msg)`
- `print(f"\n=== {name} ===")` — these are user-facing table headers → KEEP as print or emit as structured data in JSON mode

**Key rule**: `print()` is acceptable ONLY for final user-visible output (tables, formatted reports). All internal operation messages go through `log.*()`.

**JSON formatter** (stdlib-only pattern):
```python
import json, logging, datetime

class _NDJSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        })
```

**Alternatives considered**:
- A: `structlog` — rejected (external dep, out of scope)
- B: Manual print-to-stderr + stdout for JSON — rejected (bypasses logging system)
- C: Keep mixed print/log — rejected (CI parsability failure)

---

## Decision 3: Memory Consolidation — Stale Detection Algorithm

**Decision**: Use file `mtime` (modification time) as primary staleness signal; description word-overlap for contradiction detection.

**Rationale**:
- `mtime` is always available via `pathlib.Path.stat().st_mtime` — no frontmatter date parsing required
- Frontmatter `---` blocks may or may not have an `updated:` field — mtime is the reliable fallback
- Contradiction detection: same `type` + Jaccard similarity of description tokens > 0.4 threshold
- No semantic embeddings (out of scope); pure string similarity is sufficient for the use case

**Edge case: malformed frontmatter**:
- Use `try/except yaml.YAMLError` around each file parse
- On failure: skip file, append to `unparseable_files` list in report

**MEMORY.md line count check**:
- Read MEMORY.md, count lines
- ≥200: CRITICAL (silent failure risk)
- ≥180: WARNING (approaching limit)
- <180: OK

**Alternatives considered**:
- A: Parse `updated:` frontmatter field — rejected (not consistently present in all entries)
- B: Semantic similarity via embeddings — rejected (no API calls, no deps)
- C: Git blame for last-modified date — rejected (adds subprocess dependency, fragile)

---

## Decision 4: skill-lint.py — Which Checks to Add

**Decision**: Add 5 new checks to `lint_single_skill()` loop in `skill-lint.py`. Reuse existing `add()` helper pattern.

**Confirmed existing state** (read skill-lint.py):
- `## Output Directory` check at line 276 already exists for `pipeline` archetype skills
- `handoffs` check at line 248 already exists
- `pipeline-contract-base` reference check at line 267 already exists
- **Gap**: `gate` value validation against canonical set is NOT currently implemented
- **Gap**: `## Output Directory` check only applies to `pipeline` archetype, not all skills

**Checks to add**:

| Check | Severity | Location in lint_single_skill() | Status |
|-------|----------|--------------------------------|--------|
| `gate` value canonical validation | ERROR | After frontmatter parse | NEW |
| `## Output Directory` for ALL skill archetypes | WARNING | Body section checks | EXTEND (currently pipeline-only) |
| `handoffs` presence for all archetypes | NIT | Already exists, extend scope | VERIFY SCOPE |

**VALID_GATES already defined** in `errors.py`:
```python
VALID_GATES = frozenset({"auto", "human", "1-way-door", "auto-escalate"})
```
Import from `errors.py` — do not redefine.

**Alternatives considered**:
- A: Rewrite skill-lint.py with new architecture — rejected (rabbit hole, out of scope)
- B: Add checks in a separate linter script — rejected (duplication)

---

## Decision 5: lru_cache Scope and Invalidation

**Decision**: Apply `@lru_cache(maxsize=None)` to `_discover_platforms()` only. Skip `_load_manifest()` (called with different path args — cache keyed by arg is safe but callers pass mutable state).

**Confirmed**: `_discover_platforms()` (line 74 of platform_cli.py) takes no arguments → perfect lru_cache target. Called at lines 119, 195, 329, 504, 547.

**Invalidation**: Call `_discover_platforms.cache_clear()` after `new` and `sync` subcommands (these modify the platforms directory).

**Alternatives considered**:
- A: Cache `_load_manifest()` too — deferred (takes Path arg, cache is safe but adds complexity for marginal gain)
- B: Manual module-level dict — rejected (lru_cache is cleaner, stdlib)

---

## Decision 6: Test Strategy for vision-build.py and sync_memory.py

**Decision**: Use `unittest.mock.patch` for subprocess and filesystem isolation. Tests live in `.specify/scripts/tests/`.

**vision-build.py test targets** (read source):
- `validate_model()` — check LikeC4 JSON structure
- `export_json()` — mock `subprocess.run` returning JSON
- `export_png()` — mock subprocess.run raising FileNotFoundError (missing likec4 CLI)
- `_containers_table()`, `_domains_table()`, `_integrations_table()`, `_ddd_relations_table()` — pure functions, no mocking needed
- `update_markdown()` — temp file fixture

**sync_memory.py test targets** (169 LOC file):
- `import_memory_from_markdown()` — temp file with frontmatter
- `export_memory_to_markdown()` — DB roundtrip
- Round-trip: import → DB → export → compare
- Frontmatter type preservation (user/feedback/project/reference)
- MEMORY.md index update

**Alternatives considered**:
- A: Integration tests hitting real filesystem/DB — too slow for unit layer; use where appropriate
- B: Separate test fixtures file — not needed for <300 LOC test files
