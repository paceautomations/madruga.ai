# Quickstart: Sequential Execution UX (end-to-end smoke test)

**Epic**: 024-sequential-execution-ux
**Audience**: Operator running the feature for the first time after all 6 phases ship.
**Prerequisites**: Phases P1–P6 implemented and merged; `.pipeline/madruga.db` at schema version 17.

This walkthrough exercises the complete feature path: opt a platform into the new isolation mode, queue two epics, enable the feature flag, and observe auto-promotion happen within the 60-second SLA. If everything below passes on first try, SC-001 through SC-008 are satisfied end-to-end.

---

## Step 0 — Environment prep

```bash
# Confirm schema version.
python3 -c "
import sqlite3
conn = sqlite3.connect('.pipeline/madruga.db')
print('user_version:', conn.execute('PRAGMA user_version').fetchone()[0])
# Expected: 17
"

# Confirm easter is currently stopped (we will start it mid-flow).
systemctl --user status madruga-easter || true
# Expected: inactive (or not running)

# Confirm the target platform (e.g., prosauai) has `repo.isolation: branch` set.
grep -A2 '^repo:' platforms/prosauai/platform.yaml
# Expected: isolation: branch under the repo: block
```

If the platform does NOT have `isolation: branch` yet, edit `platforms/prosauai/platform.yaml`:

```yaml
repo:
  name: prosauai
  org: paceautomations
  base_branch: develop
  epic_branch_prefix: "epic/prosauai/"
  isolation: branch      # <-- ADD THIS LINE
```

Commit the platform.yaml change on main (it's config, not code).

---

## Step 1 — Draft two epics for the test

Use the existing draft flow for two throwaway epics:

```bash
/madruga:epic-context --draft prosauai 900-queue-smoke-test-a
# Accept the generated pitch, minimal content
/madruga:epic-context --draft prosauai 901-queue-smoke-test-b
# Accept the generated pitch, minimal content
```

Verify both exist and are drafted:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('.pipeline/madruga.db')
rows = conn.execute(
    \"SELECT epic_id, status FROM epics WHERE platform_id='prosauai' AND epic_id LIKE '9%'\"
).fetchall()
print(rows)
# Expected: [('900-queue-smoke-test-a', 'drafted'), ('901-queue-smoke-test-b', 'drafted')]
"
```

---

## Step 2 — Queue both epics

```bash
python3 .specify/scripts/platform_cli.py queue prosauai 900-queue-smoke-test-a
# Expected stdout: ✓ Epic 900-queue-smoke-test-a queued for platform prosauai. Position in queue: 1.

python3 .specify/scripts/platform_cli.py queue prosauai 901-queue-smoke-test-b
# Expected stdout: ✓ Epic 901-queue-smoke-test-b queued for platform prosauai. Position in queue: 2.

python3 .specify/scripts/platform_cli.py queue-list prosauai
# Expected output: table with 2 rows, 900-a at position 1, 901-b at position 2
```

**What to verify**:
- Both epics transitioned to `queued` (check via `queue-list` and direct DB query)
- FIFO order matches the order of queue commands (900-a first because its `updated_at` is earlier)

---

## Step 3 — Start the first epic manually (bypass the hook for the first run)

The queue auto-promotion only triggers when a **running** epic finishes. For the first epic in the queue, someone has to start it. Use the normal flow:

```bash
python3 .specify/scripts/platform_cli.py dequeue prosauai 900-queue-smoke-test-a
# Epic back to drafted
/madruga:epic-context prosauai 900-queue-smoke-test-a
# Creates branch epic/prosauai/900-queue-smoke-test-a in prosauai main clone, sets status=in_progress
```

**What to verify**:
- Open `~/repos/paceautomations/prosauai` in your editor.
- Confirm the current branch is `epic/prosauai/900-queue-smoke-test-a` (NOT `develop`, NOT a worktree path).
- **This validates SC-001**: zero navigation to alternative directories — the active epic branch is visible in the main clone.

---

## Step 4 — Enable the feature flag

```bash
systemctl --user set-environment MADRUGA_QUEUE_PROMOTION=1
systemctl --user status madruga-easter
# Confirm inactive still

systemctl --user start madruga-easter
journalctl --user -u madruga-easter -f &
```

Watch the logs. Easter should:
1. Boot cleanly
2. Discover `900-queue-smoke-test-a` as `in_progress` in DB
3. Dispatch its L2 cycle

---

## Step 5 — Wait for the first epic to ship

Let the L2 cycle run. (For a smoke test epic with minimal content, this can complete in minutes. For a real epic, hours.) When it reaches `shipped` status:

1. The `dag_scheduler` removes 900-a from `_running_epics`
2. The auto-promotion hook fires (because `MADRUGA_QUEUE_PROMOTION=1`)
3. `promote_queued_epic('prosauai')` is called via `asyncio.to_thread`
4. `901-queue-smoke-test-b` is picked up (FIFO)
5. Branch `epic/prosauai/901-queue-smoke-test-b` is created (cascade from 900-a's tip OR from `origin/develop` if 900-a was already merged)
6. Draft artifacts are committed: `feat: promote queued epic 901-queue-smoke-test-b (cascade from develop)`
7. DB: `status='in_progress'`, `branch_name='epic/prosauai/901-queue-smoke-test-b'`
8. L2 cycle for 901-b begins automatically

**What to verify** (within 60 seconds of 900-a reaching `shipped`):

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('.pipeline/madruga.db')
print(conn.execute(
  \"SELECT epic_id, status FROM epics WHERE platform_id='prosauai' AND epic_id LIKE '9%'\"
).fetchall())
# Expected: [('900-queue-smoke-test-a', 'shipped'), ('901-queue-smoke-test-b', 'in_progress')]
"

# Editor confirms branch switched
cd ~/repos/paceautomations/prosauai
git branch --show-current
# Expected: epic/prosauai/901-queue-smoke-test-b
```

**This validates SC-002, SC-003, SC-006, SC-008**: auto-promotion fired within 60 seconds, end-to-end queue-two-walk-away worked in one attempt, backwards compatibility preserved (non-queue-related platforms unaffected), queue command was self-service.

---

## Step 6 — Deliberate failure test: dirty tree

Before the second epic ships:

1. In `~/repos/paceautomations/prosauai` (while on the 901-b branch), create an uncommitted change: `echo "dirt" >> README.md`
2. Manually trigger a re-promotion scenario (e.g., queue a third epic and let 901-b complete).
3. Observe the promotion attempt fail: the dirty-tree guard in `_checkout_epic_branch` detects the unstaged change and raises `DirtyTreeError`.
4. Verify in logs: `promotion_dirty_tree_blocked` event with the porcelain output in the structured log fields.
5. Verify in DB: the third epic is in `blocked` status.
6. Verify: a notification was delivered (or at minimum, recorded in the daemon logs if the notification channel is down).

**This validates SC-004 and SC-007**: 100% of dirty-tree failures result in `blocked` + visible failure.

Clean up: `git restore README.md` in the prosauai clone.

---

## Step 7 — Kill-switch reversibility test

```bash
# Measure: from "decide to disable" to "feature off"
time systemctl --user unset-environment MADRUGA_QUEUE_PROMOTION
time systemctl --user restart madruga-easter
# Both commands together: ≪ 30 seconds
```

After this, even if the queue has pending epics and running slots become free, the hook is a no-op. Check logs to confirm:

```bash
journalctl --user -u madruga-easter -f
# Expected: no 'auto_promotion_hook_result' events after restart
```

**This validates SC-005**: rollout reversible in under 30 seconds via env var toggle + daemon restart.

---

## Cleanup

```bash
# Remove the smoke-test epics
python3 .specify/scripts/platform_cli.py dequeue prosauai 901-queue-smoke-test-b 2>/dev/null || true
# Manually update DB: set both to cancelled, delete pitch files
rm -rf platforms/prosauai/epics/900-queue-smoke-test-a/
rm -rf platforms/prosauai/epics/901-queue-smoke-test-b/
python3 -c "
import sqlite3
conn = sqlite3.connect('.pipeline/madruga.db')
conn.execute(\"UPDATE epics SET status='cancelled' WHERE epic_id IN ('900-queue-smoke-test-a', '901-queue-smoke-test-b')\")
conn.commit()
"

# Re-enable the feature for real use
systemctl --user set-environment MADRUGA_QUEUE_PROMOTION=1
systemctl --user restart madruga-easter
```

---

## Success criteria summary

| SC | Verified in step | Pass condition |
|----|-------------------|----------------|
| SC-001 | Step 3 | Editor shows `epic/prosauai/...` branch at main clone path |
| SC-002 | Step 5 | Second epic transitions to in_progress within 60s of first shipping |
| SC-003 | Step 5 | End-to-end walk-away succeeds in one attempt |
| SC-004 | Step 6 | 100% dirty-tree → `blocked` with notification |
| SC-005 | Step 7 | Toggle-off round trip < 30s |
| SC-006 | Step 5 (implicit) | Non-queued platforms unaffected (verify by checking madruga-ai epics still run normally) |
| SC-007 | Steps 5 + 6 | Failures always reflected in DB within 60s |
| SC-008 | Step 2 | `queue <platform> <epic>` worked first try, no DB editing |

If all 8 criteria pass on first attempt, epic 024 is functionally complete and ready for `/madruga:qa` and `/madruga:reconcile`.
