# Implementation Plan: Code Quality & DX

**Branch**: `epic/madruga-ai/020-code-quality-dx` | **Date**: 2026-04-04 | **Spec**: `spec.md`  
**Input**: Feature specification from `platforms/madruga-ai/epics/020-code-quality-dx/spec.md`

---

## Summary

Split the 2,268-line `db.py` monolith into 4 focused modules with a backward-compatible re-export facade. Standardize all script output through stdlib `logging` with an optional `--json` NDJSON mode. Add a memory consolidation tool, extend the skill linter with gate-value validation, apply `lru_cache` to platform discovery, and add test coverage for the two previously untested scripts (`vision-build.py`, `sync_memory.py`). No schema changes. No new external dependencies.

---

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: stdlib only (sqlite3, pathlib, json, logging, functools, unittest.mock) + pyyaml  
**Storage**: SQLite WAL mode — `.pipeline/madruga.db` — no schema changes  
**Testing**: pytest (existing framework, `make test`)  
**Target Platform**: Linux / macOS developer workstation + CI  
**Project Type**: CLI tool suite (Python scripts)  
**Performance Goals**: `memory_consolidate.py` completes in <5s on ≤50 files (SC-003)  
**Constraints**: Zero new external dependencies; all existing `from db import X` callers unchanged  
**Scale/Scope**: 7 files to create, 5 files to modify; ~2,200 LOC net change

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism — simplest solution | PASS | Re-export facade is the simplest backward-compat approach |
| IV. Fast Action + TDD | PASS | Tests defined before implementation (spec has scenarios) |
| VII. TDD — write tests before code | PASS | T6 tests defined; all tasks have acceptance criteria |
| VIII. Collaborative decisions | PASS | All 6 decisions documented in research.md with alternatives |
| IX. Observability & logging | PASS | T2 is the primary deliverable; aligns with Constitution §IX |
| No new external deps | PASS | stdlib logging replaces structlog; no pip installs |

**Post-design re-check**: No violations. `functools.lru_cache` is stdlib. `json` formatter is stdlib. Memory consolidation uses only stdlib + pyyaml (already present).

---

## Project Structure

### Documentation (this epic)

```text
platforms/madruga-ai/epics/020-code-quality-dx/
├── pitch.md
├── spec.md
├── plan.md              ← this file
├── research.md          ← Phase 0 complete
├── data-model.md        ← Phase 1 complete
├── quickstart.md        ← Phase 1 complete
└── tasks.md             ← /speckit.tasks output (not yet generated)
```

### Source Code Changes

```text
.specify/scripts/
├── db.py                      MODIFY → 10-line re-export facade
├── db_core.py                 CREATE  ~400 LOC (connection, migration, FTS5)
├── db_pipeline.py             CREATE  ~550 LOC (platform/pipeline/run CRUD)
├── db_decisions.py            CREATE  ~820 LOC (decisions + memory)
├── db_observability.py        CREATE  ~280 LOC (traces + eval scores)
├── memory_consolidate.py      CREATE  ~200 LOC
├── platform_cli.py            MODIFY  +lru_cache, +--json, -print→log
├── dag_executor.py            MODIFY  +--json, -print→log
├── post_save.py               MODIFY  +--json, -print→log
├── skill-lint.py              MODIFY  +gate validation, +output-dir check
└── tests/
    ├── test_db_core.py        CREATE  ~150 LOC (replaces connection tests in test_db_crud.py)
    ├── test_db_pipeline.py    RENAME  test_db_crud.py → test_db_pipeline.py
    ├── test_vision_build.py   CREATE  ~180 LOC (≥5 test cases)
    └── test_sync_memory.py    CREATE  ~130 LOC (≥5 test cases)
```

**Structure Decision**: Flat script directory (existing pattern). No new packages. The db split uses module-level files (not a `db/` package) to preserve `from db import X` without changes.

---

## Complexity Tracking

No constitution violations. No complexity justification required.

---

## Phase 0: Research

**Status**: COMPLETE — see `research.md`

**Key decisions resolved**:
1. db.py split via flat modules + re-export facade (not package)
2. stdlib `logging` for structured output (no structlog)
3. File `mtime` for stale detection; Jaccard similarity for contradiction detection
4. Extend existing `lint_single_skill()` loop with 3 new checks; import `VALID_GATES` from `errors.py`
5. `lru_cache` on `_discover_platforms()` only (no-arg function, session-lifetime cache)
6. `unittest.mock.patch` for subprocess/filesystem isolation in new tests

---

## Phase 1: Design

**Status**: COMPLETE — see `data-model.md`, `quickstart.md`

### Module split ownership table

| Module | Symbols | Lines | Imports |
|--------|---------|-------|---------|
| `db_core.py` | 15 | ~400 | stdlib + config + errors |
| `db_pipeline.py` | 29 | ~550 | db_core + stdlib + yaml + config |
| `db_decisions.py` | 22 | ~820 | db_core + stdlib + yaml |
| `db_observability.py` | 8 | ~280 | db_core + stdlib |
| `db.py` (facade) | all (re-export) | ~10 | all 4 modules |

### Logging contract

```python
# Setup in each script's __main__ block:
import argparse, logging, json, datetime

class _NDJSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        })

def _setup_logging(json_mode: bool) -> None:
    handler = logging.StreamHandler()
    if json_mode:
        handler.setFormatter(_NDJSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)
```

**Placement**: Each script defines `_setup_logging()` locally (3 scripts × ~10 LOC = 30 LOC total). Not shared to avoid a new module dependency.

### Memory consolidation algorithm

```
1. Scan .claude/projects/.../memory/*.md
2. For each file:
   a. Parse frontmatter (yaml.safe_load) — on error: add to unparseable list
   b. Compute age: (today - Path.stat().st_mtime) in days
   c. If age > 90: add to stale list
3. For each pair of same-type files:
   a. Tokenize description fields
   b. Jaccard similarity = |A∩B| / |A∪B|
   c. If similarity > 0.4: add pair to possible_duplicates
4. Count MEMORY.md lines
5. Print report
6. If --apply: write [STALE] prefix to stale files
```

### Skill linter new checks (pseudocode)

```python
# In lint_single_skill(), after frontmatter parse:
from errors import VALID_GATES  # already available in same scripts/ dir

gate = fm.get("gate")
if gate and gate not in VALID_GATES:
    add("ERROR", f"Invalid gate value '{gate}'. Valid: {sorted(VALID_GATES)}")

# In body checks (extend from pipeline-only to all archetypes):
if "## Output Directory" not in body:
    add("WARNING", "Missing '## Output Directory' section")
```

---

## Phase 2: Implementation Tasks

**Next step**: `/speckit.tasks madruga-ai 020-code-quality-dx` to generate `tasks.md`

### Task breakdown preview

| ID | Task | LOC | Dependencies | Acceptance |
|----|------|-----|-------------|-----------|
| T1 | Split db.py into 4 modules + facade | ~2,060 | errors.py (VALID_GATES) | `from db import X` works; make test passes |
| T2 | Structured logging + --json flag | ~150 | T1 (scripts import from new db modules) | NDJSON parseable; human mode unchanged |
| T3 | memory_consolidate.py | ~200 | none | --dry-run produces report; --apply marks stale |
| T4 | skill-lint.py gate + output-dir checks | ~30 | errors.py (VALID_GATES) | Missing section → WARNING; invalid gate → ERROR |
| T5 | lru_cache on _discover_platforms() | ~10 | none | Cache hit on second call; cleared after `new`/`sync` |
| T6 | test_vision_build.py + test_sync_memory.py | ~310 | T1 (db modules for sync_memory tests) | ≥5 cases each; make test green |

**Estimated total**: ~2,760 LOC (new + modified)

---

## Constraints & Risks

| Risk | Mitigation |
|------|-----------|
| `*` re-exports may shadow names if two modules define the same symbol | Audit all symbols before split — no overlaps expected (each function is in exactly one category) |
| `_FTS5_AVAILABLE` global in db_core.py — must not be reset by multiple imports | Module-level singleton pattern is preserved; Python module cache ensures one copy |
| print() → log() conversion may break scripts that relied on stdout capture | Only internal messages converted; user-facing table output remains as print() |
| test_db_crud.py → test_db_pipeline.py rename may break CI discovery | Update pytest config if needed; use explicit test paths in Makefile |
| memory_consolidate.py mtime-based detection is timezone-naive | Use UTC consistently: `datetime.datetime.utcfromtimestamp(mtime)` |
