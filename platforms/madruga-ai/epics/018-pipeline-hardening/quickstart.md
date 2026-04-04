# Quickstart: Pipeline Hardening & Safety

**Epic**: 018-pipeline-hardening
**Branch**: `epic/madruga-ai/018-pipeline-hardening`

## Prerequisites

- Python 3.11+
- `make test` passes on current main
- `make ruff` passes on current main

## Development Setup

```bash
# Already on the correct branch
git branch --show-current  # epic/madruga-ai/018-pipeline-hardening

# Run existing tests to verify baseline
make test

# Run linting
make ruff
```

## Implementation Order

The 7 tasks have natural dependencies — implement in this order:

1. **T6: Error hierarchy** (`errors.py`) — create first, all other tasks depend on it
2. **T5: Input validation dataclasses** — uses errors from T6
3. **T2: Fail-closed gate validation** — uses `VALID_GATES` from T5/T6
4. **T4: Path security** — uses validation functions from T6
5. **T1: Context managers** — independent but easier after T6 (error types available)
6. **T3: Circuit breaker threshold** — single constant change
7. **T7: Graceful shutdown** — depends on T1 (context managers ensure cleanup)

## Key Files

```bash
# Files to modify
vim .specify/scripts/dag_executor.py    # 1,649 LOC — main target
vim .specify/scripts/ensure_repo.py     # 161 LOC
vim .specify/scripts/platform_cli.py    # 889 LOC
vim .specify/scripts/post_save.py       # 506 LOC

# File to create
vim .specify/scripts/errors.py          # ~30 LOC

# Tests to create/modify
vim .specify/scripts/tests/test_errors.py
vim .specify/scripts/tests/test_path_security.py
vim .specify/scripts/tests/test_dag_executor.py  # add gate validation tests
vim .specify/scripts/tests/test_platform.py      # add name validation tests
```

## Verification

```bash
# After each task
make test    # all 43+ existing tests must pass
make ruff    # linting must pass

# Specific test runs
python3 -m pytest .specify/scripts/tests/test_errors.py -v
python3 -m pytest .specify/scripts/tests/test_path_security.py -v
python3 -m pytest .specify/scripts/tests/test_dag_executor.py -v -k "gate"
```

## Key Patterns to Follow

### Context Manager (T1)
```python
# Before (BAD — leak risk)
conn = get_conn()
# ... 90 lines ...
conn.close()

# After (GOOD — auto-cleanup)
with get_conn() as conn:
    # ... 90 lines ...
    # conn.close() called automatically
```

### Error Hierarchy (T6)
```python
# Before (BAD — generic)
raise SystemExit("ERROR: No pipeline.nodes section")

# After (GOOD — typed)
raise ValidationError("No pipeline.nodes section in platform.yaml")
```

### Gate Validation (T2)
```python
# In Node.__post_init__
if self.gate not in VALID_GATES:
    log.warning("Unknown gate '%s' for node '%s' — treating as 'human'", self.gate, self.id)
    object.__setattr__(self, "gate", "human")
```
