# CLI Contract: `platform_cli.py dequeue`

**Phase**: P3
**File**: `.specify/scripts/platform_cli.py`
**Type**: New subcommand
**Spec reference**: FR-021

## Purpose

Remove an epic from the queue, reverting it to `drafted`. Used when an operator changes their mind about ordering or wants to pause an epic that was mistakenly queued.

## Invocation

```bash
python3 .specify/scripts/platform_cli.py dequeue <platform> <epic-id>
```

## Arguments

Identical to `queue` subcommand.

## Preconditions

- Epic exists and is in `queued` status. If in any other status, fail with exit 3.

## Behavior

1. Read `platform.yaml` to validate platform. Fail with exit 2 if missing.
2. Open DB with write lock.
3. Query current status. If not `queued`, exit 3 with message: `"Cannot dequeue epic {id}: current status is {status}, expected 'queued'."`
4. `UPDATE epics SET status='drafted', updated_at=... WHERE platform_id=? AND epic_id=?`.
5. Emit structured log: `{event: dequeue_command_invoked, platform, epic_id, operator}`.
6. Print confirmation: `✓ Epic {id} dequeued. Status reverted to drafted.`
7. Exit 0.

## Non-destructive guarantee

Dequeue NEVER deletes pitch.md, decisions.md, or any planning artifact. It only changes the row in `epics` — the files on disk are untouched. This matches FR-021: "without losing its pitch or decisions".

## Failure modes

| Condition | Exit code | Message |
|-----------|-----------|---------|
| Platform not found | 2 | Error: platform {name} not found. |
| Epic not found | 2 | Error: epic {id} not found. |
| Epic not in queued status | 3 | Error: cannot dequeue epic {id}: current status is {status}, expected 'queued'. |
| DB lock contention | 4 | Error: database is busy, try again. |

## Side effects

- Writes one row UPDATE to `epics`.
- Emits one INFO-level log entry.
- Does NOT delete files. Does NOT touch git.

## Test cases

| Test | Given | When | Then |
|------|-------|------|------|
| happy path | epic in queued | dequeue command | status='drafted', exit 0 |
| already drafted | epic in drafted | dequeue command | exit 3 |
| in_progress | epic running | dequeue command | exit 3 |
| files preserved | pitch/decisions exist | dequeue command | files unchanged on disk |
