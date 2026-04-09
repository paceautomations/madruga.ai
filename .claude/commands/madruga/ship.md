---
description: "Stage, validate, commit, and push changes — smart staging, CI checks, auto-generated messages"
arguments:
  - name: message
    description: "Optional commit message override"
    required: false
argument-hint: "[commit message]"
---

# Ship — Commit + Push

Utility skill. Stage safe files, run CI checks, auto-generate a conventional commit message, commit, and push. No confirmations — detect problems, not ask questions.

## Cardinal Rule: NEVER Stage Sensitive Files

Never `git add -A` or `git add .`. Always stage files individually. Block patterns: `.env*`, `*.key`, `*.pem`, `*.p12`, `credentials*`, `*secret*`, `*token*`, `service-account*`.

## Usage

- `/ship` — Auto-detect changes, generate message, commit, push
- `/ship fix auth token refresh` — Use provided text as commit summary

## Instructions

### 1. Analyze Working Tree

Run these commands and collect results:
```bash
git status --porcelain
git diff --stat
git diff --cached --stat
git branch --show-current
git remote -v
```

If **no changes** (working tree clean, nothing staged, no untracked): stop with "Nothing to ship."

### 2. Sensitive File Scan

Check ALL changed and untracked files against block patterns:
- `.env`, `.env.*`
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- `credentials*`, `service-account*`
- `*secret*`, `*token*` (in filename, not content)
- `*.db-wal`, `*.db-shm`

**If matches found**: warn the user with the list of blocked files and proceed with remaining safe files.
**If ALL files are sensitive**: stop with "All changed files match sensitive patterns. Nothing safe to ship."

### 3. Smart Stage

Stage each safe file individually:
```bash
git add <file1>
git add <file2>
# ... one per file, never git add -A
```

Include both modified tracked files and untracked files that pass the sensitive scan.

### 4. CI Checks

Run the shared CI validation script:
```bash
bash .specify/scripts/bash/ci-checks.sh --fast --json
```

Parse the JSON result.

**If all suites pass** → proceed to step 5.

**If any suite fails** → spawn a diagnostic subagent:

```
CI checks failed before push. Diagnose and fix.

## Failed Suites
<for each failed suite: name + raw output from the JSON>

## Context
Branch: <current branch>
Staged files: <list from git diff --cached --name-only>

## Task
1. Identify the root cause of each failure
2. For each failure, present:
   - **Problem**: what broke
   - **Root cause**: why it broke  
   - **Alternatives** (2-3 options with pros/cons)
   - **Recommendation** based on codebase context
3. Implement the recommended fix
4. Re-run: bash .specify/scripts/bash/ci-checks.sh --fast --json
5. Report results back
```

After the subagent returns:
- If fixed → re-stage any changed files, proceed to step 5
- If still failing → stop and report the failures to the user with the diagnostic analysis

### 5. Generate Commit Message

Analyze `git diff --cached` to determine:

**Prefix detection** (from CLAUDE.md convention):
- New files/features → `feat:`
- Bug fixes, corrections → `fix:`
- Refactoring, cleanup, deps, CI, docs → `chore:`
- Branch merges → `merge:`

**Message format**: `<prefix> <summary> — <details>`

- If user provided the `message` argument → use it as summary, still auto-detect prefix
- If no argument → generate summary from the diff (what changed, not how)
- Keep summary under 72 chars
- Add body with details if the change touches 3+ files

**Always append** (in commit body):
```
Co-Authored-By: Madruga
```

### 6. Commit

Create the commit using a heredoc for proper formatting:
```bash
git commit -m "$(cat <<'EOF'
<prefix> <summary> — <details>

Co-Authored-By: Madruga
EOF
)"
```

The existing `post-commit` hook fires automatically (registers in SQLite DB). No manual DB call needed.

### 7. Push + Report

Push to remote:
```bash
# If upstream exists:
git push

# If no upstream (new branch):
git push -u origin <branch-name>
```

**If push fails** (remote diverged): attempt `git pull --rebase` then retry push once. If still failing, stop and report.

**Final report**:
```
## Shipped

**Branch:** <branch>
**Commit:** <short-sha> <message>
**Files:** <N> changed (+<additions> -<deletions>)
**CI:** all suites passed
**Pushed to:** origin/<branch>
```

## Error Handling

| Issue | Action |
|-------|--------|
| Nothing to commit | Stop: "Nothing to ship." |
| All files sensitive | Stop: list blocked files |
| CI checks fail + subagent can't fix | Stop: show diagnostic with root cause analysis |
| Push rejected (diverged) | `git pull --rebase` + retry once |
| Push rejected (permissions) | Stop: show error, suggest checking remote access |
| No git remote | Stop: "No remote configured." |
