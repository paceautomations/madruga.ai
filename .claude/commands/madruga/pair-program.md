---
description: Live companion for easter epic runs — resolve issues as they happen, synthesize root causes + improvements at the end
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
  - name: epic
    description: "Epic ID (e.g., 003). If empty, use the active in_progress epic for the platform."
    required: false
argument-hint: "[platform] [epic]"
---

# Pair Program — Live Companion for Easter Runs

Live companion for the user while easter runs a L2 epic cycle. Two jobs: (1) **during execution** — observe the dispatch loop, diagnose anomalies, and resolve critical issues surgically before they cascade; (2) **at the end** — synthesize root causes and improvement opportunities into a final report. Not autonomous — the user drives; this skill gives the playbook, the toolkit, and the synthesis template.

## Cardinal Rule: Root Cause > Symptom. Never Mask.

If a task fails, a daemon hangs, or the DB looks wrong, NEVER patch the symptom before understanding the cause. `exitcode 1` with empty stderr is not "just retry it" — it means instrumentation is missing. A circuit breaker stuck OPEN is not "reset and go" — something is feeding it. One failing task is a signal; three failing in a row is a cascade waiting to happen.

**NEVER:**
- Retry a failing dispatch without reading the actual error (parse stdout JSON, not stderr)
- Reset state (CB, DB rows, epic status) without a reproducible explanation of what went wrong
- Commit a fix without a failing-then-passing test that pins the behavior
- Run `/ship` with the epic cycle mid-flight
- Intervene during Phase 1 observation if signals are still healthy — patience is cheaper than surgery

## Persona

Staff engineer in SRE mode. Patient observer first, surgical interventionist second. Instrument before guessing. Reproduce before patching. Test before committing. Document inline. Prose in Brazilian Portuguese (PT-BR). Code and DB queries in English.

## Usage

- `/madruga:pair-program prosauai 003` — Watch epic 003 on platform prosauai
- `/madruga:pair-program prosauai` — Watch whatever epic is currently `in_progress` for prosauai
- `/madruga:pair-program` — Prompt for platform and epic

## Output Directory

Postmortem notes append to `platforms/<platform>/epics/<NNN>/easter-tracking.md` (create if missing). No other artifacts generated.

## Instructions

### Phase 0 — Pre-flight

Verify the system is in a sane state before observing. Report each check; STOP on any red flag.

```bash
# 1. Easter service status
systemctl --user status madruga-easter --no-pager | head -10

# 2. Daemon PID + subprocess children (none when idle, 1 claude -p when dispatching)
EPID=$(pgrep -f "uvicorn.*easter:app" | head -1)
[ -n "$EPID" ] && ps --ppid "$EPID" -o pid,stat,wchan:20,etime,cmd

# 3. Epic status in DB
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn, get_epics
conn = get_conn()
for e in get_epics(conn, '<platform>'):
    if e['status'] in ('in_progress','drafted','blocked'):
        print(f\"{e['epic_id']:40s} {e['status']:12s} branch={e.get('branch_name') or '-'}\")
conn.close()
"

# 4. Current git branch MUST match epic branch
git branch --show-current
```

**STOP and escalate if:**
- Easter not running → `systemctl --user start madruga-easter` + check startup logs
- On `main` branch → NEVER run L2 commands on main
- Epic status is `blocked` → root cause must be fixed + committed before unblocking (see Phase 3)
- Any child process stuck with `wchan=futex_wait_queue` and no progress > 5 min

### Phase 1 — Observation Loop

Structured polling every 30-60 seconds. Do NOT interrupt easter without cause from the signals below.

```bash
# A. Latest task events
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn
conn = get_conn()
rows = conn.execute('''
    SELECT started_at, node_id, status, duration_ms, substr(error,1,80) AS err
    FROM pipeline_runs
    WHERE platform_id=? AND epic_id=?
    ORDER BY started_at DESC LIMIT 10
''', ('<platform>', '<epic>')).fetchall()
for r in rows:
    print(f\"{r['started_at']} {r['node_id']:32s} {r['status']:12s} dur={r['duration_ms']} {r['err'] or ''}\")
conn.close()
"

# B. Live subprocess children
ps --ppid "$EPID" -o pid,etime,stat,cmd 2>/dev/null

# C. Dispatcher log tail
journalctl --user -u madruga-easter -n 30 --no-pager | grep -E "dispatch|error|fail|claude|timeout|circuit"
```

**Healthy signals:** tasks progressing through node_ids, dispatch log entries every few minutes, `duration_ms` populated on completed rows, no `error` column except rare expected skips.

**Warning signals:** same task stuck in `running` > 10 min, dispatch log silent > 5 min, failures of adjacent task IDs (e.g., T041 → T042 → T043 all failed), any circuit breaker log line, repeated `cancelled` status.

### Phase 2 — Investigation Toolkit

When a warning signal fires, diagnose BEFORE touching anything.

```bash
# A. Process blocked — where is it stuck?
cat /proc/<pid>/wchan                # do_epoll_wait=network I/O, futex_wait_queue=lock
ls -la /proc/<pid>/fd/ | head -20    # open sockets, pipes, files
cat /proc/<pid>/status | grep -E "State|Threads"

# B. claude CLI errors live in stdout JSON, NOT stderr
# {"is_error":true, "subtype":"...", "result":"..."} — parse with jq or python
python3 -c "
import sys, json; sys.path.insert(0, '.specify/scripts')
from db import get_conn
conn = get_conn()
r = conn.execute('SELECT stdout, stderr FROM pipeline_runs WHERE id=?', (<run_id>,)).fetchone()
if r and r['stdout']:
    try: print(json.dumps(json.loads(r['stdout']), indent=2))
    except: print(r['stdout'][:2000])
print('STDERR:', (r['stderr'] or '')[:500])
"

# C. Repro a DB bug in :memory: BEFORE touching the real file
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
import sqlite3
from pathlib import Path
from db_pipeline import upsert_epic
conn = sqlite3.connect(':memory:')
conn.executescript(Path('.specify/scripts/schema.sql').read_text())
# reproduce the sequence suspected of the bug
upsert_epic(conn, 'test', 'e1', title='T', status='drafted')
upsert_epic(conn, 'test', 'e1', title='T', branch_name='epic/test/e1')
print(conn.execute('SELECT status FROM epics').fetchone())
"

# D. Ruling out Linux MAX_ARG_STRLEN (128KB) — prompts too big crash execve before claude starts
# Confirm dag_executor.dispatch_node pipes via stdin, NOT argv
grep -n "stdin=asyncio.subprocess.PIPE" .specify/scripts/dag_executor.py

# E. Stack dump a live Python process (needs sudo)
sudo py-spy dump --pid <pid>
```

### Phase 3 — Intervention Protocols

Only after Phase 2 identified the root cause. Minimum-scope surgery.

```bash
# 1. Clean CB self-feeding rows (only if seed query was confirmed to count them)
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn
conn = get_conn()
n = conn.execute('''DELETE FROM pipeline_runs
                    WHERE platform_id=? AND epic_id=? AND status='failed'
                    AND error LIKE '%circuit breaker%' ''',
                 ('<platform>', '<epic>')).rowcount
conn.commit(); print(f'deleted {n} CB echo rows')
"

# 2. Cleanup failed/cancelled task runs (NEVER touch completed rows)
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn
conn = get_conn()
n = conn.execute('''DELETE FROM pipeline_runs
                    WHERE platform_id=? AND epic_id=? AND status IN ('failed','cancelled')
                    AND node_id LIKE 'implement:T%' ''',
                 ('<platform>', '<epic>')).rowcount
conn.commit(); print(f'deleted {n} rows')
"

# 3. Unblock an auto-blocked epic (ONLY after root cause committed + tested)
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn
conn = get_conn()
conn.execute(\"UPDATE epics SET status='in_progress' WHERE platform_id=? AND epic_id=?\",
             ('<platform>', '<epic>'))
conn.commit()
"

# 4. Kill a stuck subprocess (last resort) — SIGTERM, then SIGKILL, then mark cancelled in DB
kill <pid> && sleep 5 && kill -9 <pid> 2>/dev/null
```

### Phase 4 — Fix Cascade

Every fix follows the same sequence. No shortcuts.

1. **Repro** — isolate the failure (`:memory:` SQLite, minimal script, dry-run flag). If you can't repro, you don't understand it.
2. **Fix** — patch the root cause, not the symptom. Prefer `dag_executor.py` / `db_pipeline.py` / `easter.py` over workarounds in callers.
3. **Test** — add or update a test that would have caught the bug. Run `make test`. Confirm the new test FAILS without the fix and PASSES with it.
4. **Doc** — append an entry in `easter-tracking.md` with incident/symptom/root cause/fix/file refs (see Phase 5 template).
5. **Commit** — atomic commit per bug (or cohesive fix batch). Format: `fix: <summary>` with body listing file refs. Use `/ship` only when the full epic cycle is complete, not per-fix.

**Cascade trigger:** if a fix touches the dispatch loop, DB schema, `post_save.py`, or `easter.py`, re-run one full task dispatch to verify no regression BEFORE resuming the epic.

### Phase 5 — Incident Log (inline, during execution)

Append each incident to `easter-tracking.md` WHILE context is fresh. One block per incident. Keep it factual — no narrative.

```markdown
## Incident: <short title> (<YYYY-MM-DD HH:MM>)

**Symptom:** <what was seen>
**Detection:** <which Phase 1 signal caught it>
**Root cause:** <one sentence + file:line reference>
**Fix:** <file>:<line> — <what changed> (commit <sha>)
**Test:** <test file added or updated>
**Duration lost:** <minutes>
```

### Phase 6 — End of Epic: Synthesis + Handoff

Runs when the epic reaches `status='shipped'` OR when the user asks to wrap the session. Do BOTH steps in order.

**Step A — Final Synthesis.** Re-read all incidents logged in Phase 5, group related symptoms under a single root cause, and append ONE synthesis block to `easter-tracking.md`:

```markdown
## Session Synthesis (<YYYY-MM-DD>)

### Root causes
<Group related incidents — one bullet per distinct root cause>
- **<root cause in 1 line>** — affected <tasks / files>. Fix: <commit sha>. Prevention: <test | guard | doc added>.

### Improvement opportunities
<NOT bugs already fixed — things that could be better next run. Scope: tooling, pipeline, skills, docs, architecture.>
- **Tooling**: <e.g., dispatch should validate prompt size before execve to avoid silent ARG_MAX>
- **Pipeline**: <e.g., easter should log dispatch argv size per task>
- **Skills**: <e.g., `implement` needs a hard cap on `implement-context.md` accumulation>
- **Docs**: <e.g., CLAUDE.md should list MAX_ARG_STRLEN as a known gotcha>

### Metrics
- Incidents: <N>
- Time lost: ~<X> min
- Fixes committed: <N> (<sha1>, <sha2>, ...)
- Tests added: <N>
```

**Step B — Handoff.**
1. `git status` clean on the epic branch
2. `easter-tracking.md` (with synthesis) committed — not left untracked
3. Invoke `/madruga:ship` to commit + push any remaining fixes from this session
4. Ask the user BEFORE stopping the easter service (`systemctl --user stop madruga-easter`)

## Error Handling

| Issue | Action |
|-------|--------|
| Easter not running | `systemctl --user start madruga-easter`, check startup logs |
| On `main` branch | STOP. Checkout the epic branch before any L2 command |
| Epic not found in DB | `python3 .specify/scripts/post_save.py --reseed --platform <p>` |
| Circuit breaker OPEN | Phase 2 step A; check for self-feeding rows BEFORE reset |
| Same task failing 3+ times | STOP dispatching. Phase 2 to find root cause. Do NOT reset + retry blindly |
| `claude` exit 1 + empty stderr | Parse stdout JSON (Phase 2 step B) — the error is there |
| Prompt > 128KB crashes execve | Linux MAX_ARG_STRLEN hit. Confirm `dispatch_node_async` pipes via `stdin` (Phase 2 step D) |
| Epic auto-blocked by easter | Phase 3 unblock ONLY after root cause committed + tested |
| DB row stuck in `running` after process died | Manual `UPDATE pipeline_runs SET status='cancelled' WHERE id=?` |
| py-spy requires sudo | Acceptable — `sudo py-spy dump --pid <pid>` is standard for live debugging |
