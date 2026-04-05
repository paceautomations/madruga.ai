# Research: Pipeline Hardening & Safety

**Date**: 2026-04-04
**Epic**: 018-pipeline-hardening
**Status**: Complete

---

## R1. Context Manager Migration — Connection Leak Analysis

### Current State (Evidence)

**`dag_executor.py`**: Two pipeline functions use raw `conn = get_conn()` with manual `conn.close()` at every exit point:

- **`run_pipeline_async()`** (line 924): 9 separate `conn.close()` calls at lines 958, 999, 1020, 1051, 1082, 1126, 1169, 1198. No `try/finally` wrapper. Any unhandled exception between line 924 and the nearest `conn.close()` leaks the connection.
- **`run_pipeline()`** (line 1375): 8 separate `conn.close()` calls at lines 1395, 1438, 1453, 1477, 1521, 1563, 1591. Same leak risk.

**`platform_cli.py`**: Three gate commands use bare pattern:
- `cmd_gate_approve()` (lines 848/854)
- `cmd_gate_reject()` (lines 861/867)
- `cmd_gate_list()` (lines 874/876)
All other commands already use `with get_conn() as conn:`.

**`post_save.py`**: One bare pattern in `detect_from_path()` (lines 404/409) inside `try/except Exception`. All other uses are context managers.

**`ensure_repo.py`**: One bare pattern in `_resolve_repos_base()` (lines 60/62) inside `try/except Exception`.

### Decision: Use `with get_conn() as conn:` everywhere

**Rationale**: `_ClosingConnection` in `db.py` (lines 152-175) already implements `__enter__`/`__exit__`. `__enter__` returns the raw `sqlite3.Connection` (not `self`), so `with get_conn() as conn:` binds `conn` to the raw connection — transparent to all downstream code. `__exit__` calls `conn.close()` unconditionally, including on exceptions.

**Migration pattern for pipeline functions**: Replace the bare `conn = get_conn()` with `with get_conn() as conn:`, indent the body, and remove all manual `conn.close()` calls. Early returns work correctly inside `with` blocks.

**Alternatives considered**:
1. `try/finally` wrapper around existing code — more invasive, same effect, less idiomatic
2. Refactor pipeline functions into smaller units — out of scope (rabbit hole)

---

## R2. Fail-Closed Gate Validation

### Current State (Evidence)

`parse_dag()` (line 503) reads gates via `n.get("gate", "auto")` with no validation. The recognized set in the system:
- `HUMAN_GATES = frozenset({"human", "1-way-door"})` (line 48) — checked with `if node.gate in HUMAN_GATES`
- `"auto-escalate"` — handled by `_handle_auto_escalate()` (lines 581-620)
- `"auto"` — implicit default (anything not in HUMAN_GATES and not "auto-escalate")

**Bug**: A typo like `gate: "humam"` silently acts as `"auto"` — the node executes without human approval. This is a safety-critical defect.

### Decision: Validate against canonical set, fail-closed to `human`

```python
VALID_GATES = frozenset({"auto", "human", "1-way-door", "auto-escalate"})
```

In `parse_dag()`, after reading the gate value:
- If gate not in `VALID_GATES`: log WARNING identifying the node and invalid value, set gate to `"human"`.
- If gate is empty string: treat as default `"auto"` (existing behavior).

**Rationale**: Fail-closed is the standard safety pattern. A misspelled gate MUST require human approval, not bypass it. Claude Code itself uses fail-closed defaults (`isConcurrencySafe: false`, `isReadOnly: false`).

**Alternatives considered**:
1. Fail-open (current behavior) — unacceptable for safety
2. Raise error and halt pipeline — too disruptive; a warning + safe default is sufficient
3. Case-insensitive matching — rejected; all existing gates are lowercase, adding case normalization adds complexity without value

---

## R3. Circuit Breaker for Dispatch

### Current State (Evidence)

`CircuitBreaker` class (lines 626-669) exists with `CB_MAX_FAILURES=5` and `CB_RECOVERY_SECONDS=300`. It tracks **global** consecutive failures across all skills, not per-skill. One instance per pipeline run (created at lines 962, 1399).

`dispatch_with_retry()` (lines 730-760) retries with backoffs `[0, 5, 10, 20]` = 4 total attempts. If all fail, it calls `breaker.record_failure()` once (not per-attempt).

### Decision: Reduce threshold from 5 to 3 for the global circuit breaker

The pitch calls for "3 consecutive failures of the SAME skill" but the existing breaker is global (tracks all skills). Changing to per-skill tracking would require a `dict[str, CircuitBreaker]` — more complexity than needed.

**Revised approach**: Lower `CB_MAX_FAILURES` from 5 to 3. The global breaker already serves the purpose: after 3 consecutive dispatch failures (regardless of which skill), the pipeline stops retrying. In practice, the DAG executes skills sequentially, so 3 global failures almost always means the same skill failed 3 times.

**Rationale**: Simpler change, reuses existing infrastructure, achieves the same safety goal.

**Alternatives considered**:
1. Per-skill circuit breaker (dict of breakers) — over-engineering for sequential execution
2. Keep threshold at 5 — too generous; 3 failures is sufficient evidence of a broken skill
3. Disable retries entirely after first failure — too aggressive; transient failures are real

---

## R4. Path Security

### Current State (Evidence)

**Platform name validation**: Only `cmd_new()` in `platform_cli.py` (line 153) validates names with `re.match(r"^[a-z][a-z0-9-]*$", name)`. All other commands (`use`, `lint`, `status`, `gate`) accept any string.

**Repo org/name validation**: `ensure_repo.py` `_load_repo_binding()` (lines 21-44) reads `org` and `repo_name` from YAML without validation. These are interpolated into `ssh_url = f"git@github.com:{org}/{repo_name}.git"` (line ~100) and passed to `subprocess.run(["git", "clone", ssh_url, ...])`. While `subprocess.run` with a list (not `shell=True`) avoids shell injection, a malicious org/name could still cause unexpected Git behavior.

**Path traversal**: No explicit `..` blocking anywhere in the codebase.

### Decision: Centralized validation functions in `errors.py`

Create two validation functions alongside the error classes:

```python
PLATFORM_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPO_COMPONENT_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

def validate_platform_name(name: str) -> None:
    if not name or not PLATFORM_NAME_RE.match(name):
        raise ValidationError(f"Invalid platform name '{name}'. Use lowercase alphanumeric and hyphens, starting with alphanumeric.")

def validate_path_safe(path: str) -> None:
    if ".." in path.split(os.sep) or ".." in path.split("/"):
        raise ValidationError(f"Path traversal detected in '{path}'.")
```

Apply at entry points:
- `platform_cli.py`: all commands that accept a platform name
- `ensure_repo.py`: `_load_repo_binding()` for org/name
- `dag_executor.py`: `main()` for `--platform` arg

**Note**: The pitch allows platform names starting with a digit (`^[a-z0-9]`), while the existing `cmd_new()` regex requires starting with a letter (`^[a-z]`). We align with the existing stricter pattern: `^[a-z][a-z0-9-]*$` — starting with a letter. This avoids introducing platform names that `cmd_new` would reject.

**Alternatives considered**:
1. Validate only at `cmd_new` — insufficient; other entry points (CLI, easter) bypass `cmd_new`
2. Allow Unicode in names — out of scope per spec assumptions
3. Block at filesystem level only — insufficient; doesn't catch injection in Git URLs

---

## R5. Input Validation with Dataclasses

### Current State (Evidence)

`Node` is a `NamedTuple` (lines 454-462) with no validation. `parse_dag()` (line 499) accesses `n["id"]` and `n["skill"]` via dict indexing — a `KeyError` is raised if missing, but with no context about which node or which field.

### Decision: Convert Node from NamedTuple to dataclass with `__post_init__`

```python
@dataclass(frozen=True, slots=True)
class Node:
    id: str
    skill: str
    outputs: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    gate: str = "auto"
    layer: str = ""
    optional: bool = False
    skip_condition: str | None = None

    def __post_init__(self):
        if not self.id:
            raise ValidationError("Node.id is required")
        if not self.skill:
            raise ValidationError("Node.skill is required")
        if self.gate not in VALID_GATES:
            log.warning("Unknown gate '%s' for node '%s' — treating as 'human'", self.gate, self.id)
            object.__setattr__(self, "gate", "human")
```

Using `frozen=True` + `slots=True` for immutability (like NamedTuple) and memory efficiency. `object.__setattr__` is needed to mutate a frozen dataclass in `__post_init__`.

**Impact on existing code**: `Node` was a `NamedTuple` — both support attribute access (`node.id`) and unpacking. The only risk is code that uses `Node._asdict()` or tuple indexing. Search for these patterns before implementation.

**PlatformConfig dataclass**: Create a minimal validation wrapper for the fields read from `platform.yaml` in `parse_dag()` and `ensure_repo.py`. Fields: `name`, `repo_org`, `repo_name`, `pipeline_nodes`.

**Alternatives considered**:
1. Keep NamedTuple + add validation in `parse_dag()` — works but duplicates validation logic
2. Use Pydantic — rejected per stdlib-only ADR
3. Use `attrs` — rejected; external dependency

---

## R6. Error Hierarchy

### Current State (Evidence)

Error patterns across the 4 scripts:
- `dag_executor.py`: 4x `raise SystemExit(...)` (lines 483, 487, 525, 542), 2x `sys.exit()` (lines 1624, 1635)
- `ensure_repo.py`: 3x `raise SystemExit(...)` (lines 25, 32, 37)
- `platform_cli.py`: 15+ `sys.exit()` calls for various error conditions
- `post_save.py`: 0 `raise SystemExit`; uses `parser.error()` (argparse) and regular exceptions

### Decision: Typed hierarchy in `errors.py`, gradual migration

```python
class MadrugaError(Exception):
    """Base for all madruga.ai errors."""

class PipelineError(MadrugaError):
    """DAG structural errors: cycles, missing nodes, dispatch failures."""

class ValidationError(MadrugaError):
    """Input validation: invalid YAML, missing fields, bad platform names."""

class DispatchError(PipelineError):
    """Skill dispatch failures via claude -p subprocess."""

class GateError(PipelineError):
    """Gate evaluation errors: timeout, rejection, invalid type."""
```

**Migration scope** (this epic):
- `dag_executor.py`: Replace 4 `raise SystemExit` in `parse_dag`/`topological_sort` with `PipelineError`/`ValidationError`. Keep `sys.exit()` in `main()` (that's the correct pattern for CLI entry points).
- `ensure_repo.py`: Replace 3 `raise SystemExit` with `ValidationError`.
- `platform_cli.py`: Replace `sys.exit(1)` in validation paths with `ValidationError`. Keep `sys.exit()` in `main()` and argparse paths.
- `post_save.py`: Already clean — no changes needed.

**Entry points** (`main()` functions) catch `MadrugaError` and convert to `sys.exit(1)` with the error message. This preserves CLI behavior while making errors programmatically distinguishable.

**Alternatives considered**:
1. Single `MadrugaError` without subtypes — insufficient for programmatic error handling
2. Error codes (enum) instead of hierarchy — less Pythonic, harder to catch selectively
3. Full migration of all `sys.exit` calls — out of scope; `main()` entry points correctly use `sys.exit`

---

## R7. Graceful Shutdown (SIGINT)

### Current State (Evidence)

Zero signal handling in `dag_executor.py`. No imports of `signal` module. `KeyboardInterrupt` propagates unhandled through `asyncio.run()`, leaking connections and leaving subprocesses orphaned.

### Decision: SIGINT handler + `_active_process` tracking

For the **sync path** (`run_pipeline`):
```python
_active_process: subprocess.Popen | None = None

def _handle_sigint(sig, frame):
    if _active_process:
        _active_process.terminate()
        _active_process.wait(timeout=5)
    log.info("Interrupted. Resume with: --resume")
    sys.exit(130)
```

For the **async path** (`run_pipeline_async`):
- Use `asyncio.create_subprocess_exec` which returns `asyncio.subprocess.Process`. Store reference in a module-level variable.
- SIGINT in asyncio raises `KeyboardInterrupt` which cancels the current task. Wrap the main loop in `try/except KeyboardInterrupt` to terminate the subprocess and print the resume hint.

**Connection cleanup**: With context managers (T1), `__exit__` fires automatically on `sys.exit(130)` or `KeyboardInterrupt`, so no explicit `conn.close()` needed in the signal handler.

**Alternatives considered**:
1. `atexit` handler — doesn't run on `sys.exit()` from signal handlers, unreliable
2. Handle both SIGINT and SIGTERM — SIGTERM out of scope per spec assumptions
3. Complex orchestrated shutdown (like Claude Code's 6-stage) — over-engineering for a CLI tool

---

## R8. Existing CircuitBreaker vs New Dispatch Breaker

### Analysis

The existing `CircuitBreaker` (lines 626-669) is a proper 3-state machine (closed/open/half-open) with recovery timeout. The pitch proposes a simpler "3 failures = disable" without recovery.

### Decision: Modify existing CircuitBreaker constants, don't create a new one

Change `CB_MAX_FAILURES = 5` → `CB_MAX_FAILURES = 3`. The recovery mechanism (half-open after 300s) is a bonus — it allows the pipeline to retry if resumed later. No need to create a parallel mechanism.

**Rationale**: The existing class is well-tested (tests in `test_dag_executor.py`). Changing one constant is lower risk than adding new code.

---

## R9. Node NamedTuple → Dataclass Impact Analysis

### Evidence

Searched for `Node` usage patterns that would break:
- `Node(...)` construction: Used in `parse_dag()` (line 497) with keyword args — works with dataclass
- `node.id`, `node.skill`, etc.: Attribute access — works with dataclass
- `_asdict()`: Not found in codebase
- Tuple unpacking: Not found in codebase
- `isinstance(node, tuple)`: Not found in codebase

**Conclusion**: Migration from `NamedTuple` to `dataclass(frozen=True, slots=True)` is safe. No breaking usage patterns found.

---

## Summary of Decisions

| # | Decision | Rationale | Alternative Rejected |
|---|----------|-----------|---------------------|
| R1 | `with get_conn() as conn:` everywhere | `_ClosingConnection` already supports it | `try/finally` wrapper |
| R2 | Unknown gate → `human` (fail-closed) | Safety-critical; typo must not bypass approval | Fail-open, raise error |
| R3 | Lower `CB_MAX_FAILURES` from 5 to 3 | Reuses existing tested code | Per-skill breaker dict |
| R4 | Centralized validation in `errors.py` | Single source of truth for validation rules | Per-script validation |
| R5 | `Node` NamedTuple → `dataclass(frozen=True)` | Validation via `__post_init__`, immutability preserved | Keep NamedTuple + external validation |
| R6 | Typed error hierarchy in `errors.py` | Programmatic error distinction, clean CLI behavior | Single error class, error codes |
| R7 | SIGINT handler + `try/except KeyboardInterrupt` | Context managers handle cleanup; handler terminates subprocess | `atexit`, multi-signal |
| R8 | Modify existing CB constants, not new class | Lower risk, already tested | New parallel mechanism |
| R9 | NamedTuple → dataclass is safe | No breaking usage patterns found in codebase | N/A |
