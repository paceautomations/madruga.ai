---
description: Test apps like a human QA — navigate, observe, and diagnose bugs via Playwright
disable-model-invocation: true
argument-hint: "[URL] or [explore <URL>] or [setup] or [heal]"
arguments:
  - name: target
    description: "URL, 'explore <URL>', 'setup [name]', or 'heal'"
    required: false
handoffs:
  - label: Reconcile Documentation
    agent: madruga/reconcile
    prompt: "QA complete. Reconcile documentation — qa may have healed code that creates drift."
---

# QA — Human-Like QA via Playwright

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Test web applications the way a human QA would: navigate, interact, observe visually, diagnose bugs, and fix them. Fully automatic pipeline after a feature is built.

## Usage

- `/qa` — Auto-detect feature (git diff), generate scenarios, test, fix, report
- `/qa http://localhost:3000` — Test a specific URL with the full pipeline
- `/qa explore http://localhost:3000` — Free exploratory navigation (no plan)
- `/qa setup` — Generate a knowledge file for the current project (interactive)
- `/qa setup resenhai-expo` — Generate knowledge with a specific name
- `/qa heal` — Re-enter the heal loop for findings from the current session

## Prerequisites

- Playwright MCP configured (browser_navigate, browser_snapshot, browser_take_screenshot, etc.)
- App running at an accessible URL (localhost or staging)
- `.claude/knowledge/qa-template.md` — template for generating project knowledge
- `.claude/knowledge/qa-<project>.md` — (OPTIONAL) project-specific context. Created via `/qa setup`

---

## Instructions

### 0. Bootstrap and Auto-Detect

1. **Parse arguments:**
   - `$ARGUMENTS` contains "setup": go to Phase Setup
   - `$ARGUMENTS` contains "explore": exploratory mode, skip to Phase 3
   - `$ARGUMENTS` contains "heal": go to Phase 4 (requires FAIL findings in the current session; if none exist, respond "Run `/qa` first")
   - `$ARGUMENTS` contains a URL (http/https): use as base_url
   - `$ARGUMENTS` is empty: default mode (full pipeline)

2. **Search for project knowledge (optional):**
   ```
   Glob .claude/knowledge/qa-*.md
   ```
   - Filter: ignore `qa-template.md` (it is the template)
   - If file(s) found: read the most relevant one (match by current directory/repo name)
   - If NOT found: proceed without it — infer everything from the diff (zero config)

3. **If project knowledge exists, extract:**
   - `base_url` from the Environments table
   - Credentials from the Auth table
   - P0-P2 Journeys as S1 scenarios for Phase 1
   - Screens & Pages to set viewports per route
   - Business Rules to inform judgment in Phase 3g
   - Known Issues to filter from findings

4. **Auto-detect the built feature:**
   ```bash
   git log main..HEAD --oneline
   git diff main...HEAD
   ```

5. **Determine base_url (if not from knowledge):**
   - If an explicit URL was passed in args: use it directly
   - Infer from the diff: look for `PORT`, `localhost`, `baseURL`, `NEXT_PUBLIC_`, `VITE_` in the code
   - If unable to determine: **AskUserQuestion** — "What URL is the app running at?"

---

### Phase Setup — Generate Project Knowledge

**Trigger:** `/qa setup` or `/qa setup <name>`

1. **Read the template:** `.claude/knowledge/qa-template.md`

2. **Explore the project automatically:**
   - `package.json` / `requirements.txt` — stack, scripts (dev, start, seed)
   - `.env` / `.env.local` / `docker-compose.yml` — URLs, ports, credentials
   - `README.md` — setup instructions
   - Routes (search for router, routes, pages/) — app screens
   - Folder structure — architecture

3. **Pre-fill the template** with inferred data (App, Environments, stack, detected routes)

4. **AskUserQuestion** to complete sections requiring human input:
   ```
   I detected the following from the project:
   - Stack: [inferred]
   - URL: [inferred]
   - Routes: [list]

   I need you to provide:
   1. Test credentials (email/password per role)
   2. 3-5 critical app journeys (e.g., login -> dashboard -> create order)
   3. Business rules I should know (e.g., minimum price, item limits)
   4. Known bugs I should NOT report
   5. Primary viewport for each screen (mobile/desktop/responsive)
   ```

5. **Save** to `.claude/knowledge/qa-<name>.md`
   - Name: kebab-case of the project or `$ARGUMENTS`

6. **Confirm:** "Knowledge created. The next `/qa` run will use it automatically."

---

### 1. Scenario Planning (automatic)

**Does NOT request approval — generates and proceeds.**

**Scenario sources (in priority order):**

1. **Journeys from knowledge** (if available): P0-P2 become S1/S2 scenarios automatically
2. **Screens from knowledge** (if available): each screen becomes a navigation scenario with the correct viewport
3. **Git diff**: apply the heuristics below for additional scenarios

**Scenario heuristics from the diff:**

| Pattern in diff | Generated scenarios |
|-----------------|---------------------|
| New route/page (route, page, view) | Happy path + 404 + unauthorized + empty state |
| Form/input (form, input, field, textarea) | Valid input + empty fields + invalid input + submit error |
| API endpoint (get, post, put, delete) | Success + 4xx/5xx error + loading state |
| Auth (login, logout, session, token) | Valid login + wrong password + expired session |
| List/table (list, table, grid) | Empty + few items + filter/search |
| CSS/responsive (media query, breakpoint) | Desktop 1280px + mobile 375px |
| Upload (file, upload, attachment) | Valid + too large + invalid type |
| Delete/remove (delete, remove, destroy) | Confirm + cancel deletion |
| Modal/dialog (modal, dialog, popup) | Open + close + submit inside |

**Automatic priority assignment:**

| Type | Priority |
|------|----------|
| Happy path of core feature | S1 |
| Error handling in main journey | S1 |
| Input validation | S2 |
| Empty states and edge cases | S2 |
| Responsiveness | S3 |
| Cosmetic | S4 |

**Limit to 15 scenarios max** — prioritize S1 and S2.

**Display in chat (informational, does NOT block):**
```
📋 Test Plan — [feature] (N scenarios: X S1, Y S2, Z S3)
| # | Journey | Scenario | Prio |
Starting tests...
```

If there is no diff AND no knowledge: **AskUserQuestion** — "What do you want to test?"

---

### 2. DB/State Staging (smart auto)

**With project knowledge:** use documented credentials and seed commands. Zero questions.

**Without project knowledge:**
- Auth: search `.env`, `.env.local`, `docker-compose.yml`, `seed*.py`, `fixtures/`
  - If found: use automatically
  - If NOT found: **AskUserQuestion** — request test credentials
- Seed: infer the command or ask

**Principle: only ask for what cannot be inferred.**

---

### 3. Execute Tests

**Snapshot vs. screenshot rule:**
- Snapshot (accessibility tree) = ALWAYS first. Fast (2-5KB). Answers: does the element exist? text? state?
- Screenshot (vision) = ONLY when: scenario is Visual/Responsive, unexpected snapshot state, or FAIL detected

**Proactive curiosity (MANDATORY):**
After each snapshot, analyze ALL visible interactive elements (buttons, links, tabs, menus, toggles, dropdowns, clickable cards). For each element within the test scope:
- If never tested: create an on-the-fly mini-scenario and test it (click -> snapshot -> judge)
- If appears relevant but outside direct scope: register as a "discovery" and test quickly (1 click + snapshot)
- If clearly out of scope (e.g., external link, generic footer): ignore

**Principle:** Act like a curious QA, not a mechanical script. If you see 5 buttons on the screen and only 1 is in the plan, test the other 4 too if they make sense. Ask yourself: "What happens if I click here?" — and click. Register additional findings with the tag `[EXPLORATORY]`.

For each scenario:

#### 3a. Navigate
```
mcp__playwright__browser_navigate -> base_url + route
```
**Viewport** (priority order):
1. If knowledge has Screens: use the viewport from the table. Mobile-first -> 375x812. Responsive -> test BOTH.
2. If the scenario has a specific viewport: `mcp__playwright__browser_resize`
3. Default: 1280x720

#### 3b. Snapshot BEFORE (conditional)
Take a snapshot BEFORE only if the scenario involves a state transition (form submit, click that changes page). For "page loads correctly" scenarios, the AFTER snapshot is sufficient.
```
mcp__playwright__browser_snapshot
```

#### 3c. Act
- `browser_fill_form` — fill forms
- `browser_click` — buttons, links (ref from snapshot)
- `browser_type` — specific fields
- `browser_select_option` — dropdowns
- `browser_wait_for` — after async actions
- `browser_handle_dialog` — unexpected dialogs

#### 3d. Snapshot AFTER
```
mcp__playwright__browser_snapshot
```
Compare: new elements? Disappeared? Text changed?

#### 3e. Check errors (conditional)
Check console/network ONLY when: the AFTER snapshot shows an unexpected state, the scenario involves API calls, or a suspected FAIL.
```
mcp__playwright__browser_console_messages
mcp__playwright__browser_network_requests
```

#### 3f. Screenshot (CONDITIONAL)
Take ONLY if: scenario is Visual/Responsive, unexpected snapshot, or FAIL.
```
mcp__playwright__browser_take_screenshot -> fullPage: true
```

**Analyze with vision using the appropriate template:**

**Layout:** Check: broken layout? Sections visible? Text legible? Consistent colors? Spacing?

**Form (post-action):** Check: error/success feedback? Validation positioned correctly? Correct state? Correct buttons?

**Data display:** Check: data present? No NaN/undefined/null? Alignment? Headers? Empty state handled?

**Responsive:** Check: stacks correctly? Text legible without zoom? Touch targets 44px? Menu accessible? No overflow?

**Before/After:** Expected change occurred? Unexpected change? Adequate visual feedback?

#### 3g. Judge

**Severity:**
- **S1 Critical** — Blocks usage. Crash, data loss, core broken, security (prevents completing the journey)
- **S2 High** — Degrades experience. Workaround possible but poor (completes with friction)
- **S3 Medium** — Minor bug. Core OK but unexpected (user notices but is not impacted)
- **S4 Low** — Cosmetic. Spacing, color, typo (only QA notices)

**Status:**
- **PASS** — correct behavior
- **FAIL (S1-S4)** — deviation from expected
- **WARN** — functionally OK but suboptimal (console warnings, performance)
- **SKIP** — not testable (timeout, auth wall, missing feature)

**With knowledge:** business rules inform judgment. Known issues are filtered out (do not become FAILs).

#### Progress in chat
```
✅ #1 Login happy path — PASS
❌ #2 Login wrong password — FAIL (S2) — no error message
⚠️ #3 Dashboard mobile — WARN — console: React key warning
⏭️ #4 File upload — SKIP — feature missing
```

#### 3h. Curiosity between scenarios
After completing a scenario, BEFORE moving to the next:
1. Review the current snapshot — are there interactive elements not covered by the plan?
2. For each relevant untested element:
   - Click -> snapshot -> judge (mini-scenario, ~30s)
   - If FAIL: register as a finding with the `[EXPLORATORY]` tag and normal severity
   - If PASS: register as `✅ [EXPLORATORY] #N.X: [description] — PASS`
3. Limit to 3 exploratory mini-scenarios per main scenario (avoid explosion)
4. If you discover an entire unmapped area (e.g., modal with complex form), create additional S2 scenarios

#### Exploratory mode (`explore`)
If `explore` mode is active (Phase 0 routed directly here):
- There are NO predefined scenarios. Navigate organically via the snapshot.
- **MAXIMUM curiosity**: click on EVERYTHING that looks interactive. Each page = complete inventory of elements.
- Explore: menus, forms, buttons, internal pages, tabs, toggles, dropdowns, cards.
- For each element: click -> observe -> judge. Skip nothing visible.
- Create on-the-fly scenarios based on what you see.
- Stop after 15-20 scenarios or complete coverage of visible elements.

---

### 4. Heal Loop

**Enters AUTOMATICALLY** if there are FAILs. Fixes without asking for permission.

For each FAIL (S1 first):

#### 4a. Analyze root cause

| Pattern | Probable cause | Where to look |
|---------|---------------|---------------|
| "undefined"/"null" rendered | Missing field in API or prop | Handler -> serializer -> component |
| Blank page | Route not registered or guard | Router -> middleware -> component |
| Console 401/403 | Expired token, permission | Auth middleware -> token -> headers |
| Console CORS | Backend config | CORS allowed origins |
| Console 404 API | Missing endpoint or wrong URL | API routes -> frontend URL |
| Form has no effect | Handler not wired | onClick/onSubmit in component |
| Infinite loading | Promise not resolving | Async handler -> error handling |
| React key warning | Missing key in .map() | Component with list |
| Redirect loop | Guard always true | Auth guard -> redirect logic |

#### 4b. Locate code
Use Grep + Read on relevant files (route, component, handler).
**Read BEFORE modifying.**

#### 4c. Apply fix
Use the Edit tool. Report: `🔧 Fixing #N: [description] in [file:line]`

#### 4d. Retest
Re-execute ONLY the failed scenario.

#### 4e. Judge
- PASS: `🔧 #N HEALED (X iter) — fix in [file:line]`
- FAIL + iter<5: return to 4a
- FAIL + iter>=5: `❌ #N UNRESOLVED after 5 attempts`

---

### 5. Report

```markdown
## QA Report — [feature/URL]
**Date:** DD/MM/YYYY | **Branch:** [branch] | **URL:** [url]
**Scenarios:** N | **Success rate:** X% (PASS + HEALED / total)

### Summary
| Status | Count |
|--------|-------|
| ✅ PASS | N |
| 🔧 HEALED | N |
| ⚠️ WARN | N |
| ❌ UNRESOLVED | N |
| ⏭️ SKIP | N |

### Findings
#### [S?] #N: [Journey] — [Scenario]
**Expected:** ... **Observed:** ... **Evidence:** ... **Status:** HEALED/UNRESOLVED

### Files Changed
| File | Line | Change |

### Lessons Learned
```

---

### 6. Persist

1. Determine save path:
   - **In epic context**: `platforms/<name>/epics/<NNN>/qa-report.md`
   - **Standalone**: `platforms/<name>/qa-reports/YYYY-MM-DD-<slug>.md`
2. Create directory if it does not exist, then save with frontmatter:
   ```yaml
   ---
   type: qa-report
   date: YYYY-MM-DD
   feature: "[name]"
   url: "[url]"
   branch: "[branch]"
   scenarios_total: N
   pass_rate: "X%"
   ---
   ```
3. Confirm: `Report saved: platforms/<name>/epics/<NNN>/qa-report.md`

---

## Error Handling

| Problem | Action |
|---------|--------|
| Browser not installed | `browser_install`, retry |
| URL not responding | Report: "App not running. Start the server?" |
| Scenario timeout (>30s) | SKIP + screenshot + console |
| App crash | Console + screenshot, S1 FAIL, reload |
| Unexpected dialog/popup | `browser_handle_dialog` dismiss |
| Flaky (fail -> pass on retest) | WARN tag "flaky" |
| Empty page in snapshot | `browser_wait_for` 2s, retry, SKIP if it persists |

## Example — Typical Post-Feature Usage

```
> /qa

📋 Test Plan — Dashboard (8 scenarios: 3 S1, 3 S2, 2 S3)

✅ #1 Dashboard loads — PASS
❌ #2 Date filter — FAIL (S2)
✅ #3 Pagination — PASS
⚠️ #4 Mobile 375px — WARN — button cut off

🔧 Fixing #2: missing handler in Dashboard.tsx:89
🔧 #2 HEALED (1 iter)

## QA Report — Dashboard
Success rate: 100% (7 PASS + 1 HEALED) | WARN: 1
Report saved: platforms/fulano/epics/001-channel-pipeline/qa-report.md
```

---
handoff:
  from: qa
  to: reconcile
  context: "QA concluido. Reconcile deve verificar drift causado pelo heal loop."
  blockers: []
