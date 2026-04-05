# Quickstart: Code Quality & DX — Epic 020

**Branch**: `epic/madruga-ai/020-code-quality-dx`

---

## Prerequisites

- Python 3.11+
- Epic 018 (pipeline hardening) merged — `errors.py` with `VALID_GATES` and typed error hierarchy must exist
- `.specify/scripts/` is the working directory for all script changes

---

## Task Execution Order

Tasks are ordered by dependency. Each task is independently verifiable.

```
T1: Split db.py → db_core + db_pipeline + db_decisions + db_observability + facade
T2: Structured logging (depends on T1 — scripts import from db modules)
T3: memory_consolidate.py (independent)
T4: skill-lint.py gate + Output Directory checks (independent)
T5: lru_cache on _discover_platforms() (independent)
T6: test_vision_build.py + test_sync_memory.py (independent)
```

---

## T1: Split db.py

```bash
# After split, verify facade works:
cd .specify/scripts
python3 -c "from db import get_conn, migrate, upsert_platform, insert_decision, create_trace; print('OK')"

# Run existing tests to confirm no regressions:
make test
```

**Key constraint**: `db.py` becomes a 10-line re-export facade. Every `from db import X` in existing scripts must continue to work.

**Verify callers** (these scripts import from db — none should need changes):
- `easter.py` — imports `cleanup_old_data`, `get_conn`, `migrate`, `get_traces`, etc.
- `dag_executor.py` — imports `insert_eval_score`, `complete_run`, `insert_run`, etc.
- `platform_cli.py` — imports `get_active_platform`, `get_conn`, etc.
- `ensure_repo.py` — imports `get_conn`, `get_local_config`
- `post_save.py` — imports from db

---

## T2: Structured Logging

```bash
# Test NDJSON output:
python3 .specify/scripts/platform_cli.py status --all --json | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]"
# Should produce no errors (every line is valid JSON)

# Test human mode unchanged:
python3 .specify/scripts/platform_cli.py status --all
# Should still produce human-readable output
```

**Rule**: `--json` flag must be added to `platform_cli.py`, `dag_executor.py`, `post_save.py`.

---

## T3: Memory Consolidation

```bash
# Dry run (default, safe — reads only):
python3 .specify/scripts/memory_consolidate.py --dry-run

# Apply mode (marks stale entries — no deletes):
python3 .specify/scripts/memory_consolidate.py --apply
```

---

## T4: Skill Linter

```bash
# Lint all skills:
python3 .specify/scripts/skill-lint.py

# Lint one skill:
python3 .specify/scripts/skill-lint.py --skill madruga/vision

# JSON output (for CI):
python3 .specify/scripts/skill-lint.py --json
```

**New checks that should fire**:
- Skills with `gate: invalid-value` → ERROR
- Skills missing `## Output Directory` section → WARNING

---

## T5: Memoization

```bash
# Verify cache works:
python3 -c "
from platform_cli import _discover_platforms
p1 = _discover_platforms()
p2 = _discover_platforms()
assert p1 is p2, 'Cache miss — function returned new object'
print('Cache hit confirmed')
"
```

---

## T6: New Tests

```bash
# Run new test files specifically:
cd .specify/scripts && python3 -m pytest tests/test_vision_build.py -v
cd .specify/scripts && python3 -m pytest tests/test_sync_memory.py -v

# Full suite:
make test
make ruff
```

---

## Final Verification Checklist

```bash
# 1. All imports work
python3 -c "from db import get_conn, migrate, upsert_platform, insert_decision, create_trace; print('facade OK')"

# 2. NDJSON output parseable
python3 .specify/scripts/platform_cli.py status madruga-ai --json | python3 -m json.tool --no-indent

# 3. Memory consolidation report runs
python3 .specify/scripts/memory_consolidate.py --dry-run

# 4. Skill linter extended checks
python3 .specify/scripts/skill-lint.py --json | python3 -m json.tool

# 5. Full test suite green
make test && make ruff
```
