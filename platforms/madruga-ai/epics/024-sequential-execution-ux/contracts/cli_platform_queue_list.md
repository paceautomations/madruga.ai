# CLI Contract: `platform_cli.py queue-list`

**Phase**: P3
**File**: `.specify/scripts/platform_cli.py`
**Type**: New subcommand
**Spec reference**: FR-020

## Purpose

Inspect the current queue for a platform. Show all epics currently in `queued` status, in FIFO order (oldest first), with their queue position.

## Invocation

```bash
python3 .specify/scripts/platform_cli.py queue-list <platform>
python3 .specify/scripts/platform_cli.py queue-list <platform> --json
```

## Arguments

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `platform` | string | yes | Platform name. Must exist. |
| `--json` | flag | no | Output JSON instead of table. |

## Behavior

1. Validate platform exists (exit 2 if not).
2. Query: `SELECT epic_id, title, updated_at FROM epics WHERE platform_id=? AND status='queued' ORDER BY updated_at ASC, epic_id ASC`.
3. If no rows: print `No epics queued for platform {name}.` and exit 0.
4. Otherwise, print either a table or JSON.

## Table output format

```
Queue for platform prosauai (3 epics):

  #  Epic ID                    Title                           Queued at
  1  004-channel-webhook        Channel Webhook Integration     2026-04-10 14:23
  2  005-rate-limiting          Rate Limiting Middleware        2026-04-11 09:15
  3  006-dashboards             Observability Dashboards        2026-04-11 11:02
```

## JSON output format

```json
{
  "platform": "prosauai",
  "count": 3,
  "queue": [
    {"position": 1, "epic_id": "004-channel-webhook", "title": "...", "queued_at": "2026-04-10T14:23:47Z"},
    {"position": 2, "epic_id": "005-rate-limiting", "title": "...", "queued_at": "2026-04-11T09:15:32Z"},
    {"position": 3, "epic_id": "006-dashboards", "title": "...", "queued_at": "2026-04-11T11:02:18Z"}
  ]
}
```

## Side effects

None. Read-only query.

## Failure modes

| Condition | Exit code | Message |
|-----------|-----------|---------|
| Platform not found | 2 | Error: platform {name} not found. |
| DB read failure | 5 | Error: database read failed: {message} |

## Test cases

| Test | Given | When | Then |
|------|-------|------|------|
| empty queue | no queued epics | queue-list | "No epics queued" message, exit 0 |
| one queued | 1 queued | queue-list | table with 1 row, exit 0 |
| multiple queued | 3 queued, different updated_at | queue-list | FIFO ordering: oldest first |
| JSON output | 2 queued | queue-list --json | valid JSON, exit 0 |
| unknown platform | missing | queue-list foo | exit 2 |
