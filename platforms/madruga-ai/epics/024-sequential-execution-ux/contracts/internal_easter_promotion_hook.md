# Internal Contract: easter.py promotion hook

**Phase**: P6 (FINAL — highest risk, goes last per Camada 2)
**File**: `.specify/scripts/easter.py`
**Type**: Additive — new code path inside existing `dag_scheduler` loop
**Spec reference**: FR-009, FR-010, FR-014, FR-017, FR-018

## Purpose

Trigger `promote_queued_epic(platform_id)` synchronously (via `asyncio.to_thread`) immediately after a running epic's slot becomes free inside the easter daemon's poll loop. Gated by the `MADRUGA_QUEUE_PROMOTION` env var.

## Insertion point

Inside `dag_scheduler()` in `easter.py`, immediately after the existing line:

```python
# ...existing code that discards the finished epic from the running set:
_running_epics.discard(epic_id)
```

Append:

```python
# --- BEGIN epic 024: auto-promotion hook ---
if os.environ.get("MADRUGA_QUEUE_PROMOTION", "0") == "1":
    try:
        # Only promote if the platform's slot is now empty.
        # (Sequential invariant: at most one epic per platform in_progress.)
        platform_has_running = any(
            ep in _running_epics for ep in _epics_for_platform(epic_platform_id)
        )
        if not platform_has_running:
            from platform_cli import promote_queued_epic  # lazy import
            result = await asyncio.to_thread(promote_queued_epic, epic_platform_id)
            logger.info(
                "auto_promotion_hook_result",
                platform=epic_platform_id,
                freed_epic=epic_id,
                result_status=result.status,
                promoted_epic=result.epic_id,
                duration_ms=result.duration_ms,
                attempts=result.attempts,
            )
    except Exception:
        # NEVER crash the poll loop. Log and move on; operator sees via ntfy.
        logger.exception(
            "promotion_hook_unhandled_exception",
            platform=epic_platform_id,
            freed_epic=epic_id,
        )
# --- END epic 024: auto-promotion hook ---
```

## Feature flag semantics

- **Default**: `MADRUGA_QUEUE_PROMOTION` is unset or set to "0" → the hook is a total no-op. Zero runtime behavior change. Zero risk of auto-sabotage even if code bugs exist.
- **Enabled**: operator explicitly exports `MADRUGA_QUEUE_PROMOTION=1` in the systemd unit environment, then restarts the daemon:

  ```bash
  systemctl --user set-environment MADRUGA_QUEUE_PROMOTION=1
  systemctl --user restart madruga-easter
  ```

- Env var is read on each poll iteration — no caching. Operator can flip the flag back off without daemon restart by unsetting and letting the next poll see the unset value.

## Guarantees (FR-010, FR-014)

- **Idempotency**: `promote_queued_epic` itself is idempotent (race detection via `AND status='queued'` in UPDATE). The hook calling it twice for the same freed slot produces at most one transition.
- **Sequential invariant**: The `platform_has_running` check is a defensive re-verification. The discard line above ALREADY removes this epic from `_running_epics`, so in the normal case `platform_has_running` is False. The check exists to prevent promotion when another concurrent dispatch slot is occupied by a different epic on the same platform.
- **Non-blocking**: `asyncio.to_thread` offloads the blocking git ops + DB writes to a thread pool. The poll loop continues to service other platforms immediately.
- **Failure isolation**: The bare `except Exception` around the entire hook ensures no hook failure can crash the poll loop (Principle IX requires observability, not crash semantics).

## Helper function: `_epics_for_platform`

Need a way to check "is any epic on this platform currently running?". Options:

1. Filter `_running_epics` by looking up platform per epic — requires a local dict `_epic_platform_map` maintained alongside `_running_epics`.
2. Query DB: `SELECT COUNT(*) FROM epics WHERE platform_id=? AND status='in_progress'`.

**Chosen**: Option 2 (DB query via `asyncio.to_thread`). Reason: `_running_epics` is already the runtime signal, but the authoritative answer is the DB. The DB query is cheap (indexed, <1ms), and it avoids a new in-memory mapping.

```python
async def _platform_has_running_epic(platform_id: str) -> bool:
    def _query():
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT 1 FROM epics WHERE platform_id=? AND status='in_progress' LIMIT 1",
                (platform_id,)
            ).fetchone()
            return row is not None
    return await asyncio.to_thread(_query)
```

Called at the beginning of the hook. If True, skip promotion entirely.

## Logging events (Principle IX)

| Event | Level | Condition |
|-------|-------|-----------|
| `auto_promotion_hook_result` | INFO | Hook ran, regardless of result |
| `promotion_hook_unhandled_exception` | ERROR | Exception caught by the safety net |
| `auto_promotion_skipped_flag_off` | DEBUG | env var unset (every poll iteration — noisy, demoted) |

## Restart semantics

- Changing `MADRUGA_QUEUE_PROMOTION` from off to on: requires daemon restart because `systemctl set-environment` only affects NEW processes. Procedure documented in quickstart.md.
- Changing from on to off without restart: next `os.environ.get` call returns the old cached value in the current process. In practice the cache is per-Python-process, and Python reads env at startup and updates don't propagate. So OFF → ON and ON → OFF both need restart. Caller should document this.

Wait — `os.environ.get` reads the live process env dict, which IS mutable at runtime. But `systemctl set-environment` only affects daemon-manager-spawned children; the running daemon's `os.environ` is NOT updated. So from the daemon's perspective, the env var is frozen at startup. Restart is required for any toggle. Document this in quickstart.md.

## Test cases (P6)

| Test | Given | When | Then |
|------|-------|------|------|
| flag off | env var unset | slot freed | hook is no-op, no call to promote_queued_epic |
| flag on + no queue | env var=1, queue empty | slot freed | promote called, returns no_queue, logged |
| flag on + queue has one | env var=1, 1 queued | slot freed | promote called, returns promoted, DB in_progress |
| flag on + running on platform | env var=1, another epic running | slot freed | promote skipped (sequential invariant) |
| promote raises unexpected | env var=1, promote raises KeyError | slot freed | hook catches, logs, poll loop continues |
| flag off then on | daemon restarted | slot freed | behavior matches flag=on |

## Rollback

Set `MADRUGA_QUEUE_PROMOTION=0` (or unset) in systemd user env, restart easter. The hook becomes a no-op instantly on next poll iteration after restart. No code revert needed.

```bash
systemctl --user unset-environment MADRUGA_QUEUE_PROMOTION
systemctl --user restart madruga-easter
```
