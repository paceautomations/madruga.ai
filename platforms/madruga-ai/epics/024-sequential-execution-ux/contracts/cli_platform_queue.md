# CLI Contract: `platform_cli.py queue`

**Phase**: P3
**File**: `.specify/scripts/platform_cli.py`
**Type**: New subcommand
**Spec reference**: FR-007, FR-020, SC-008

## Purpose

Mark a drafted epic as `queued` — the next in line to be auto-promoted to `in_progress` when the platform's running slot becomes free.

## Invocation

```bash
python3 .specify/scripts/platform_cli.py queue <platform> <epic-id>
```

Also exposed via the `/madruga:epic-context --queue <platform> <epic>` skill in a future skill-edit (outside the scope of this epic's code changes; this epic only provides the CLI surface).

## Arguments

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `platform` | string | yes | Platform name as registered in `platforms.platform_id`. Must exist. |
| `epic-id` | string | yes | Epic identifier (e.g., `004-channel-webhook`). Must exist in the platform and be in `drafted` status. |

## Preconditions

- The epic exists: `SELECT 1 FROM epics WHERE platform_id = ? AND epic_id = ?` returns a row.
- The epic is in `drafted` status. If it is in any other status, fail with a clear error.
- The platform has `repo.isolation: branch` set in its `platform.yaml` OR explicit `--force` flag (not in scope for P3 — Camada 2 keeps the surface minimal; opt-in check lives in the promotion hook, not in the queue command).

## Behavior

1. Read `platform.yaml` to validate platform exists. If not, exit 2 with error.
2. Open DB with WAL + write lock (`db_write_lock()` from `db_core.py`).
3. Query current status. If not `drafted`, exit 3 with clear error: `"Cannot queue epic {epic_id}: current status is {status}, expected 'drafted'."`
4. `UPDATE epics SET status='queued', updated_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE platform_id=? AND epic_id=?` — atomic write under the write lock.
5. Emit structured log: `{event: queue_command_invoked, platform, epic_id, operator: os.environ.get('USER')}`.
6. Print confirmation: `✓ Epic {epic_id} queued for platform {platform}. Position in queue: {N}.` where N is `COUNT(*)` over queued epics for that platform.
7. Exit 0.

## Failure modes

| Condition | Exit code | Message |
|-----------|-----------|---------|
| Platform not found | 2 | `Error: platform {name} not found.` |
| Epic not found | 2 | `Error: epic {id} not found for platform {name}.` |
| Epic not in drafted status | 3 | `Error: cannot queue epic {id}: current status is {status}, expected 'drafted'.` |
| DB write lock contention | 4 | `Error: database is busy, try again.` |
| DB constraint violation (shouldn't happen if preconditions pass) | 5 | `Error: database constraint violation: {message}` |

## Side effects

- Writes one row UPDATE to `epics`.
- Emits one INFO-level log entry.
- Does NOT touch git, does NOT create branches, does NOT notify any external system.

## Idempotency

Non-idempotent. Running `queue <p> <e>` twice on an already-queued epic returns exit 3 (not in drafted status). This is intentional — operator clarity over idempotency.

## Test cases (to be implemented in P3)

| Test | Given | When | Then |
|------|-------|------|------|
| happy path | epic in drafted | queue command | status='queued', exit 0 |
| already queued | epic in queued | queue command | exit 3, unchanged |
| in_progress | epic in in_progress | queue command | exit 3, unchanged |
| unknown platform | platform missing | queue command | exit 2 |
| unknown epic | epic missing | queue command | exit 2 |
| DB lock contention | DB busy | queue command | exit 4 after retry |
