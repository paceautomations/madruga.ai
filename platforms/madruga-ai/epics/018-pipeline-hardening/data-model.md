# Data Model: Pipeline Hardening & Safety

**Date**: 2026-04-04
**Epic**: 018-pipeline-hardening

---

## Entities

### 1. Node (Modified — NamedTuple → Dataclass)

**Current**: `NamedTuple` at `dag_executor.py:454-462`, no validation.
**New**: `dataclass(frozen=True, slots=True)` with `__post_init__` validation.

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `id` | `str` | required | Non-empty |
| `skill` | `str` | required | Non-empty |
| `outputs` | `list[str]` | `[]` | None |
| `depends` | `list[str]` | `[]` | None |
| `gate` | `str` | `"auto"` | Must be in `VALID_GATES`; unknown → `"human"` with warning |
| `layer` | `str` | `""` | None |
| `optional` | `bool` | `False` | None |
| `skip_condition` | `str \| None` | `None` | None |

**Invariants**:
- `id` and `skill` are never empty (enforced in `__post_init__`)
- `gate` is always a member of `VALID_GATES` after construction (coerced in `__post_init__`)
- Immutable after construction (`frozen=True`)

---

### 2. Error Hierarchy (New — `errors.py`)

```
MadrugaError (base)
├── ValidationError          # Input validation failures
├── PipelineError            # DAG structural / execution errors
│   ├── DispatchError        # Skill dispatch failures (claude -p)
│   └── GateError            # Gate evaluation errors
```

| Class | Raised By | Caught By | Previous Pattern |
|-------|-----------|-----------|-----------------|
| `ValidationError` | `parse_dag()`, `_load_repo_binding()`, platform name validators | `main()` → `sys.exit(1)` | `raise SystemExit(...)` |
| `PipelineError` | `topological_sort()` (cycle, unknown dep) | `main()` → `sys.exit(1)` | `raise SystemExit(...)` |
| `DispatchError` | `dispatch_node()`, `dispatch_with_retry()` | `run_pipeline()` loop | `return (False, msg, None)` |
| `GateError` | Gate evaluation in pipeline loop | `run_pipeline()` loop | `log.error + return` |

---

### 3. Validation Functions (New — in `errors.py`)

| Function | Input | Validates | Raises |
|----------|-------|-----------|--------|
| `validate_platform_name(name)` | `str` | `^[a-z][a-z0-9-]*$`, non-empty | `ValidationError` |
| `validate_path_safe(path)` | `str` | No `..` segments | `ValidationError` |
| `validate_repo_component(value, label)` | `str` | `^[a-zA-Z0-9._-]+$`, non-empty | `ValidationError` |

---

### 4. Constants (Modified — `dag_executor.py`)

| Constant | Current | New | Reason |
|----------|---------|-----|--------|
| `VALID_GATES` | _(implicit)_ | `frozenset({"auto", "human", "1-way-door", "auto-escalate"})` | Explicit canonical set for validation |
| `CB_MAX_FAILURES` | `5` | `3` | Faster circuit break per pitch spec |

---

## State Transitions

### CircuitBreaker (Existing — threshold change only)

```
closed --[3 failures]--> open --[300s]--> half-open --[1 success]--> closed
                                          half-open --[1 failure]--> open
```

### Pipeline Execution with SIGINT

```
running --[SIGINT]--> terminating_subprocess --> print_resume_hint --> sys.exit(130)
running --[exception]--> context_manager_exit --> connection_closed --> propagate
running --[success]--> context_manager_exit --> connection_closed --> return 0
```

---

## Files Modified / Created

| File | Entity Changes |
|------|---------------|
| `.specify/scripts/errors.py` | NEW: `MadrugaError`, `ValidationError`, `PipelineError`, `DispatchError`, `GateError`, validation functions |
| `.specify/scripts/dag_executor.py` | `Node` NamedTuple → dataclass; `VALID_GATES` constant; `CB_MAX_FAILURES` 5→3; context managers; SIGINT handler; `SystemExit` → typed errors |
| `.specify/scripts/ensure_repo.py` | `SystemExit` → `ValidationError`; repo component validation |
| `.specify/scripts/platform_cli.py` | Platform name validation at all entry points; `sys.exit` → `ValidationError` in validation paths; context managers for gate commands |
| `.specify/scripts/post_save.py` | Import `errors.py` types for future use (minimal change — already clean) |
