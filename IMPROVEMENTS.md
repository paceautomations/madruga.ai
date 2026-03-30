# IMPROVEMENTS.md — madruga.ai Comprehensive Review

> Generated: 2026-03-30 | Reviewed by: 5-agent team (PM, Staff Engineer, Frontend Engineer, Architect, SRE)
> Methodology: End-to-end codebase review + benchmark against BMAD, GSD, and AI-driven SDLC best practices

---

## Executive Summary

madruga.ai is an **ambitious and well-structured** architecture documentation system with a strong pipeline DAG, solid DB layer, and unique LikeC4 integration. The system already surpasses most AI-driven documentation tools in pipeline orchestration depth.

**Key strengths:** 24-skill pipeline with gates, SQLite state tracking, Copier-based multi-platform template, LikeC4 architecture-as-code, auto-populated markdown tables.

**Critical gaps:** Portal is bare-bones, CI lacks portal build validation, several Fulano L1 docs haven't been generated yet, and there's no observability into pipeline health.

> **Review note:** This document was auto-reviewed by a Staff Engineer subagent. Corrections applied: B1 removed (false positive — `model/dist/` not tracked in git), B4 downgraded to WARNING, B2 reframed as tracking item, benchmark table made more honest, 2 missed issues added.

---

## Benchmarks: What Top Frameworks Do Better

### BMAD (Breakthrough Method for Agile AI-Driven Development) — 23.6k stars
- **9 specialized agent roles** (PM, Analyst, Architect, UX, Scrum Master, Dev, QA, Tech Writer, Master) each receiving only scoped artifacts — more formalized persona system than madruga's implicit skill personas
- **Three implementation tracks**: Quick Flow (bugs), Standard (MVPs), Enterprise (compliance) — madruga has one track
- **Artifact-driven handoffs** where each stage produces versioned documents as input for next agent
- **Structured prompt engineering** answering 5 questions: system context, requirements clarity, examples/anti-examples, acceptance criteria, edge cases
- **MCP integration** for real tooling (SonarQube, Jira, Playwright, GitHub, Figma)

### GSD (Get Stuff Done) — 23k stars
- **Solves "context rot"** by spawning fresh agent instances per task — madruga already does this per skill
- **Iron rule**: "A task must fit in one context window. If it cannot, it is two tasks."
- **Pre-inlined context injection**: Instead of agents spending tool calls reading files, dispatch prompts include relevant artifacts inline — saves tokens and provides immediate context
- **Hallucination guard**: Agents completing with zero tool calls are rejected as fabricated — cheap, high-value check
- **Cost tracking** per unit/phase/model with budget ceilings
- **Adaptive replanning** after each slice based on discovered information
- **Stuck detection** via sliding-window pattern recognition with retry-once-then-pause logic
- **Crash recovery**: Session reconstruction from surviving tool calls

### Gas Town (Steve Yegge) — Multi-Agent at Scale
- **Coordinates 20-30 parallel AI coding agents** across multiple projects
- **Three-tier persistence**: Beads (git-backed structured work items), Hooks (worktree storage surviving crashes), Seance (session discovery from JSONL event logs to query predecessor agent decisions)
- **Refinery**: Per-project merge queue with Bors-style bisecting verification gates — failed merges isolated and re-dispatched
- **Three-tier watchdog**: Daemon (3-min heartbeat), Boot (AI triage), Deacon (continuous patrol)
- **Structured escalation** with P0/P1/P2 severity routing

### OpenClaw — Local-First AI Assistant
- **Dual memory model**: Immutable JSONL audit log ("what happened") + curated MEMORY.md ("what matters") — separates history from knowledge
- **Semantic Snapshots** at pipeline stage boundaries for cost-efficient state transfer between agents
- **Session-to-session communication** for agent coordination without context pollution

### Architecture-as-Code Landscape
| Tool | Strengths | Weaknesses |
|------|-----------|------------|
| **LikeC4** (madruga's choice) | Custom vocabulary, multi-project, React components, live diagrams | Smaller ecosystem |
| **Structurizr** | Official C4 lineage, strong governance, export versatility | Less flexible, no React |
| **PlantUML C4** | Widely adopted, CI/CD friendly | Verbose, limited interactivity |
| **Mermaid C4** | Zero tooling, GitHub native rendering | Limited fidelity, no multi-project |

**Verdict**: LikeC4 remains the strongest choice for madruga's use case.

### Memory & Decision Management
- madruga.ai's dual memory system (filesystem + SQLite) is **ahead of most tools** except Gas Town's three-tier model
- **Gap**: No automatic memory pruning or staleness detection. Memories grow forever.
- **Gap**: No cost tracking per skill invocation
- **Gap**: No crash recovery beyond optional `/checkpoint`

---

## Priority 1 — BLOCKERS (Must Fix)

### B1. Migration 003 fails permanently on systems without FTS5
**Where:** `.pipeline/migrations/003_decisions_memory.sql`
**Impact:** The migration unconditionally creates FTS5 virtual tables. If FTS5 isn't compiled into the system's SQLite, `migrate()` rolls back — but `ALTER TABLE ... ADD COLUMN` statements that ran before the FTS5 lines may have already committed. On retry, the `ALTER TABLE` fails (duplicate column), creating an infinite failure loop. The `_check_fts5()` guard exists in Python but the SQL migration itself has no conditional logic.
**Fix:** Split migration 003 into `003a_decisions_memory.sql` (columns + tables) and `003b_fts5.sql` (FTS5, conditionally skipped in `migrate()` when `_check_fts5()` returns False).
**Effort:** 1-2 hours

### B2. SQL injection in bash script — unsanitized variable interpolation
**Where:** `.specify/scripts/bash/check-platform-prerequisites.sh`, lines ~281-316
**Impact:** `$PLATFORM`, `$PLATFORM_YAML`, `$EPIC`, `$SKILL` are interpolated directly into inline Python strings. A platform name containing a single-quote (e.g., `test'; import os; os.system('id')#`) allows arbitrary code execution. The status/skill blocks at lines 362+ correctly use `sys.argv` instead.
**Fix:** Pass all variables as `sys.argv` parameters instead of string interpolation. Replace `'$PLATFORM'` with `sys.argv[1]`.
**Effort:** 1 hour

### B3. FTS LIKE fallback has wrong filter logic (data leaks across platforms)
**Where:** `db.py`, `search_decisions()` and `search_memories()` LIKE fallback
**Impact:** `WHERE title LIKE ? OR context LIKE ? AND platform_id=?` — the `AND` binds tighter than `OR` in SQL, so title matches from **all platforms** leak through when filtering by platform_id.
**Fix:** Add parentheses: `WHERE (title LIKE ? OR context LIKE ?) AND platform_id=?`
**Effort:** 5 min

### B4. SSR adapter with no SSR need — wasted complexity
**Where:** `portal/astro.config.mjs` line 101 — `adapter: node({ mode: 'standalone' })`
**Impact:** Forces SSR and requires a Node.js server at runtime. But every page uses `getStaticPaths()` — this is a fully static site. The node adapter adds ~5MB to output, prevents deployment to free static hosting (Netlify, Vercel static, GitHub Pages), and introduces an unnecessary runtime dependency.
**Fix:** Remove `adapter: node({ mode: 'standalone' })` and the `@astrojs/node` dependency from `package.json`. Astro defaults to static output.
**Effort:** 5 min

### B5. Broken `useMemo` in LikeC4Diagram — diagrams re-mount on every render
**Where:** `portal/src/components/viewers/LikeC4Diagram.tsx` line 91
**Impact:** `viewPaths` is a plain object prop — new reference on every parent re-render. The `useMemo` dependency `[platform, viewId, viewPaths]` triggers every time, causing React to unmount and remount the entire LikeC4 diagram. This produces visible flicker and destroys internal diagram state (zoom, pan position).
**Fix:** Stabilize `viewPaths` — either JSON-stringify for comparison, use `useRef`, or move to a static lookup outside the component:
```tsx
const viewPathsKey = JSON.stringify(viewPaths);
const DiagramComponent = useMemo(() => { ... }, [platform, viewId, viewPathsKey]);
```
**Effort:** 15 min

### B6. L2 node count mismatch — post-implementation `analyze` missing from platform.yaml
**Where:** `platforms/fulano/platform.yaml` epic_cycle vs `pipeline-dag-knowledge.md`
**Impact:** The knowledge file documents 11 L2 steps (including post-implementation `speckit.analyze` between implement and verify). But `platform.yaml` only defines 10 nodes — the second `analyze` is missing entirely. Any tool querying `platform.yaml` for epic cycle status won't track post-implementation analysis. The Copier template also lacks it, so all future platforms inherit this gap.
**Fix:** Add a second analyze node (e.g., `id: analyze-post`, `depends: ["implement"]`) to `platform.yaml` epic_cycle. Update the Copier template to match.
**Effort:** 30 min

### B7. No portal build in CI
**Where:** `.github/workflows/ci.yml`
**Impact:** Portal build can silently break (broken imports, missing symlinks, Astro config errors) with no CI signal. Currently only lint + likec4 build + db tests + template tests are run.
**Fix:** Add a `portal-build` job:
```yaml
portal-build:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: "20" }
    - run: cd portal && npm ci && npm run build
```
**Effort:** 15 min

---

## Tracking — Fulano L1 Pipeline Progress

> **Note:** This is not a bug — the pipeline is designed to be incremental. These are the remaining L1 skills to execute.

**Missing artifacts:**
- `business/process.md` — run `/business-process fulano`
- `engineering/containers.md` — run `/containers fulano`
- `engineering/context-map.md` — run `/context-map fulano`
- `research/tech-alternatives.md` — run `/tech-research fulano`
- `planning/roadmap.md` — run `/roadmap fulano`

**Next step:** Run `/pipeline fulano` to see exact status and recommended next skill.

---

## Priority 2 — WARNINGS (Should Fix)

### W0. DB connections leak on exceptions — no context manager
**Where:** `db.py` and all callers — `conn = get_conn()` / `conn.close()` without `try/finally`
**Impact:** If any code between open and close raises, the connection leaks. Repeated leaks can exhaust SQLite's connection limit.
**Fix:** Make `get_conn()` return a context manager (using `contextlib.closing`), or add `__enter__`/`__exit__` methods.
**Effort:** 1 hour

### W0a. `conn.commit()` on every single write in db.py
**Where:** `db.py` — every `upsert_*`, `insert_*`, `delete_*` function calls `conn.commit()` individually
**Impact:** Code smell — `seed_from_filesystem()` does ~80 individual commits for 1 platform. At current scale (2 platforms, 13 nodes) this takes milliseconds thanks to WAL mode, but it's poor practice and will matter if scale increases.
**Fix:** Add optional transaction context manager pattern. Callers wrap related operations in `with transaction(conn):`.
**Effort:** 2-3 hours

### W0b. No `.gitignore` entry for `model/output/`
**Where:** `.gitignore` — missing `platforms/*/model/output/`
**Impact:** `vision-build.py` generates `likec4.json` into `model/output/`. This directory is not in `.gitignore` and could be accidentally committed (large JSON files).
**Fix:** Add `platforms/*/model/output/` to `.gitignore`
**Effort:** 2 min

### W0c. No concurrent DB access protection
**Where:** `db.py` — every script calls `get_conn()` independently
**Impact:** If two scripts run concurrently (e.g., CI parallel jobs, or user runs two Claude Code sessions), SQLite's single-writer lock may cause `SQLITE_BUSY` errors. The `busy_timeout=5000` helps but there's no retry logic.
**Fix:** For now, document the single-writer constraint. Long-term, consider a lock file or connection reuse pattern.
**Effort:** 30 min (docs) or 4 hours (retry logic)

### W1. REPO_ROOT defined 5 times across scripts
**Where:** `db.py:26`, `platform.py:29`, `post_save.py:50`, `sync_memory.py:41`, `vision-build.py:18`
**Impact:** If repo structure changes, must update 5 files. Already caused a subtle issue: `platform.py:402` computes memory dir as `REPO_ROOT / ".claude" / "projects"` but the actual auto-memory lives in `~/.claude/projects/-home-...-madruga-ai/memory/`.
**Fix:** Extract to a shared `config.py`:
```python
# .specify/scripts/config.py
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / ".pipeline" / "madruga.db"
PLATFORMS_DIR = REPO_ROOT / "platforms"
```
**Effort:** 1 hour

### W2. Pipeline DAG definition is duplicated: `platform.yaml` + `pipeline-dag-knowledge.md` + CLAUDE.md
**Where:**
- `platforms/fulano/platform.yaml` → `pipeline.nodes[]` with `depends_on`
- `.claude/knowledge/pipeline-dag-knowledge.md` → Full DAG definition
- `CLAUDE.md` → Pipeline table with dependencies
**Impact:** Three sources of truth for the same DAG. When a node is added/changed, all three must be updated manually. They can (and do) drift.
**Fix:** Make `platform.yaml` the single source of truth. Generate the knowledge file and CLAUDE.md table from it via script:
```bash
python3 .specify/scripts/platform.py export-dag fulano --format=markdown > .claude/knowledge/pipeline-dag-knowledge.md
```
**Effort:** 4-6 hours

### W3. Portal has no search functionality
**Where:** `portal/`
**Impact:** With N platforms × ~15 docs each, finding specific content requires manual navigation. Starlight has built-in Pagefind search but it's not enabled.
**Fix:** Starlight's Pagefind search is enabled by default — check if it's been accidentally disabled. If custom search is needed, add Algolia DocSearch or Pagefind with platform-scoped filtering.
**Effort:** 30 min (if just enabling built-in) or 4 hours (custom)

### W4. Portal has no pipeline dashboard
**Where:** Not implemented
**Impact:** The most valuable view for a platform owner — "where am I in the pipeline?" — requires running `/pipeline` in Claude Code. There's no visual dashboard.
**Fix:** Create `portal/src/pages/[platform]/pipeline.astro` that reads `platform.yaml` pipeline nodes, checks file existence, and renders a Mermaid DAG with color-coded status (green=done, gray=pending, red=blocked).
**Effort:** 8-12 hours

### W5. No automatic staleness detection for artifacts
**Where:** `db.py:get_stale_nodes()` exists but is never called automatically
**Impact:** When a dependency (e.g., `vision.md`) is updated, downstream nodes (`solution-overview.md`) become stale but nobody knows.
**Fix:** Add a `platform.py lint --check-stale` command that calls `get_stale_nodes()` and reports. Wire it into CI.
**Effort:** 2-3 hours

### W6. `vision-build.py` silently fails on missing LikeC4 CLI
**Where:** `vision-build.py:44-45` — `subprocess.run(["likec4", "build", ...], check=True)` will throw `FileNotFoundError` with an unhelpful message if `likec4` isn't installed.
**Fix:** Add a pre-check: `shutil.which("likec4") or sys.exit("Error: likec4 CLI not found. Install with: npm i -g likec4")`
**Effort:** 5 min

### W7. Portal `setup.sh` is still referenced but likely unnecessary
**Where:** `portal/package.json:6` → `"postinstall": "bash setup.sh"`
**Impact:** If `setup.sh` is missing, `npm install` fails. The symlinks are now managed by `platformSymlinksPlugin()` in `astro.config.mjs`, making `setup.sh` potentially redundant.
**Fix:** Verify `setup.sh` is still needed. If symlinks are fully handled by the Vite plugin, remove the postinstall hook.
**Effort:** 30 min

### W8. No test coverage for `vision-build.py` or `sync_memory.py`
**Where:** `.specify/scripts/tests/` — tests exist for db, platform, post_save, but NOT for vision-build or sync_memory
**Impact:** The LikeC4 JSON → markdown pipeline and memory sync are untested. Regressions will be silent.
**Fix:** Add `test_vision_build.py` with mock LikeC4 JSON data and `test_sync_memory.py`.
**Effort:** 4-6 hours

### W9. CI jobs lack dependency caching
**Where:** `.github/workflows/ci.yml` — 4 independent parallel jobs (lint, likec4, db-tests, templates)
**Impact:** Jobs already run in parallel (good), but each installs Python packages from scratch. No pip/npm caching. The `likec4` job runs `npx likec4 build` downloading the package every time.
**Fix:** Add `pip` caching and `node_modules` caching:
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
```
**Effort:** 30 min

### W9b. No `requirements-dev.txt` or `pyproject.toml` at root
**Where:** CI installs ad-hoc packages per job (`pip install pyyaml copier ruff`, `pip install pyyaml pytest`)
**Impact:** Drift between CI and local dev. Different jobs may install different versions.
**Fix:** Create `requirements-dev.txt` at repo root: `pyyaml>=6.0`, `copier>=9.4.0,<10`, `ruff>=0.4.0`, `pytest>=8.0`
**Effort:** 15 min

### W9c. No `ruff format --check` in CI
**Where:** `.github/workflows/ci.yml` lint job — only runs `ruff check`, not format check
**Impact:** CLAUDE.md says "Python code uses ruff for formatting and linting" but formatting is not enforced.
**Fix:** Add `ruff format --check .specify/scripts/` to lint job
**Effort:** 5 min

### W9d. Bash test not run in CI
**Where:** `.specify/scripts/bash/tests/test_base_dir.sh` exists but is never invoked by CI
**Impact:** SpecKit bash scripts (common.sh, create-new-feature.sh, check-prerequisites.sh) have zero automated test coverage.
**Fix:** Add bash test execution to CI, or convert key assertions to pytest.
**Effort:** 30 min

### W9e. Two template tests permanently skipped
**Where:** `.specify/templates/platform/tests/test_template.py` — `test_skip_if_exists_on_update` and `test_spec_syncs_on_update` are `@pytest.mark.skip`
**Impact:** These validate critical Copier `_skip_if_exists` contract. Without them, a template change could silently overwrite user-modified files on `copier update`.
**Fix:** Set up a git-tagged template fixture in CI to enable these tests.
**Effort:** 2-3 hours

### W9f. `templates` CI job has redundant inline validation
**Where:** `ci.yml` lines 61-76 do inline Python validation, then line 77 runs pytest which tests the same thing
**Fix:** Remove the inline validation — pytest covers it.
**Effort:** 10 min

### W10. Branch guard docs omit `clarify` and `analyze` from guarded skills list
**Where:** `.claude/knowledge/pipeline-contract-base.md` line 12
**Impact:** Branch guard lists 8 skills but omits `clarify` and `analyze`. Both are L2 epic cycle skills that run on feature branches and should have branch guards.
**Fix:** Update guard list to include all 10 L2 skills.
**Effort:** 5 min

### W10a. `clarify` dependency not reflected in platform.yaml — DAG knowledge is misleading
**Where:** `pipeline-dag-knowledge.md` shows epic-context → specify → clarify → plan (linear), but `platform.yaml` has `plan` depending on `["specify"]` not `["clarify"]`
**Impact:** Since `clarify` is optional, `plan` correctly skips it. But the knowledge file's linear representation misleads the LLM into thinking `clarify` must complete before `plan`.
**Fix:** Add note in DAG knowledge: "clarify is optional; plan depends on specify, not clarify."
**Effort:** 5 min

### W10b. QA skill `disable-model-invocation: true` may block pipeline flow
**Where:** `.claude/commands/madruga/qa.md` line 4
**Impact:** This flag means QA can only be invoked by the user directly, not by other skills. Could prevent automated progression from verify → qa in the pipeline.
**Fix:** Evaluate if this is intentional. If QA should be pipeline-invokable, remove the flag.
**Effort:** 5 min (decision) + 5 min (fix)

### W10c. Constitution references non-existent "AskQuestionTool"
**Where:** `.specify/memory/constitution.md` line 85
**Fix:** Replace with "ask the user directly" or remove the tool reference.
**Effort:** 2 min

### W10d. Platform loader map requires manual code changes
**Where:** `portal/src/components/viewers/LikeC4Diagram.tsx` lines 6-9
**Impact:** `platformLoaders` map is hardcoded to `fulano` and `madruga-ai`. Every new platform requires editing a TSX file. CLAUDE.md documents this, but it's a design smell.
**Fix:** Generate `platformLoaders` at build time from `discoverPlatforms()` via a Vite plugin that writes a virtual module.
**Effort:** 2-3 hours

### W10b. Sidebar toggle is fragile vanilla JS outside Astro's component model
**Where:** `portal/public/sidebar-toggle.js` — 173-line vanilla JS loaded via `<script defer>`
**Impact:** Not type-checked, no tree-shaking, race conditions with Starlight's DOM manipulation. Hardcoded section labels must stay in sync with `buildSidebar()`. Mobile behavior undefined.
**Fix:** Convert to an Astro island component with React, or at minimum make it a proper Astro `<script>` module.
**Effort:** 4-6 hours

### W10c. Fonts declared but never loaded
**Where:** `portal/src/styles/custom.css` lines 8-9 — `--sl-font: 'Inter'`, `--sl-font-mono: 'JetBrains Mono'`
**Impact:** No `@font-face` rules or Google Fonts imports. Browser silently falls back to system fonts. Declarations are misleading.
**Fix:** Either load the fonts (via `@fontsource/inter` npm package) or remove the declarations.
**Effort:** 15 min

### W10d. `@types/react` and `@types/react-dom` in `dependencies` instead of `devDependencies`
**Where:** `portal/package.json` lines 18-19
**Fix:** Move to `devDependencies`. Type packages are build-time only.
**Effort:** 2 min

### W11. `reseed_all` opens N connections + runs N migration scans
**Where:** `post_save.py`, `reseed_all()` — each `reseed()` call opens a new connection + runs `migrate()`
**Fix:** Open one connection, migrate once, pass conn to all reseed calls.
**Effort:** 30 min

### W11. DB stores absolute file_paths — breaks on different machines
**Where:** `db.py` — `str(file_path)` stores absolute paths like `/home/user/.claude/projects/.../memory/foo.md`
**Impact:** If repo is cloned to a different path, all file_path comparisons break. Affects `import_memory_from_markdown` and `import_adr_from_markdown`.
**Fix:** Store paths relative to REPO_ROOT.
**Effort:** 2-3 hours (need to update all callers)

### W12. YAML frontmatter in exports not properly escaped
**Where:** `db.py:599` (`export_decision_to_markdown`) and `db.py:826` (`export_memory_to_markdown`)
**Impact:** If title/name contains double-quotes or YAML special chars, the exported frontmatter becomes invalid YAML. E.g., `title: "Use "Redis" for cache"` breaks parsing.
**Fix:** Use `yaml.dump()` for frontmatter generation instead of f-strings.
**Effort:** 1 hour

### W13. Decisions export generates lossy markdown
**Where:** `db.py:571-622` — `export_decision_to_markdown()` generates fixed-format markdown that drops some fields
**Impact:** Round-tripping (import → export → import) loses data: `alternatives`, `rationale` from frontmatter, section ordering. The export uses hardcoded section names (`Contexto`, `Decisao`) that may not match the original.
**Fix:** Store the original markdown body in a `body` column and use it for export when available, falling back to template generation.
**Effort:** 3-4 hours

---

## Priority 3 — IMPROVEMENTS (Nice to Have)

### I1. Dream Frontend — Pipeline Status Dashboard
**What:** A real-time pipeline dashboard showing L1 + L2 progress for all platforms.
**Design:**
- Top: Platform selector cards with lifecycle badge and progress bar
- Middle: Interactive Mermaid/D3 DAG with color-coded nodes (click to navigate to artifact)
- Bottom: Recent activity feed (from `events` table)
- Sidebar: Decision timeline with links between ADRs
**Implementation:** Read `platform.yaml` + check file existence server-side, render as Astro page with React islands.
**Effort:** 2-3 days

### I2. Dream Frontend — Decision Timeline
**What:** Visual timeline of all ADRs across platforms, with links showing supersedes/relates-to relationships.
**Design:** Horizontal timeline, grouped by platform. Click ADR to see full text. Filter by status (accepted/deprecated/superseded).
**Implementation:** Query `decisions` + `decision_links` tables via API route, render with D3 or vis-timeline.
**Effort:** 1-2 days

### I3. Dream Frontend — Cross-Platform Search
**What:** Unified search across all platforms' docs, ADRs, epics, and engineering docs.
**Design:** Pagefind with custom facets: platform, doc type, status. Show snippets with highlighted matches.
**Implementation:** Starlight's Pagefind already indexes content. Add custom metadata attributes for filtering.
**Effort:** 4-8 hours

### I4. Dream Frontend — Interactive Architecture Diagrams with Detail Panels
**What:** When a user clicks an element in a LikeC4 diagram, show a slide-in panel with: element description, related ADRs, epic(s) that touch this component, container details (tech stack, deployment), source code links.
**Design:** LikeC4's `ReactLikeC4` already supports `enableElementDetails`. Extend with custom detail renderers. Build a `<DiagramDetailPanel>` React component querying a JSON index generated at build time from DB + markdown frontmatter. Panel slides in from the right, preserving diagram view.
**Effort:** 2-3 days (UI only, data integration later)

### I4b. Astro View Transitions for instant navigation
**What:** Add Astro's View Transitions API for smooth page-to-page navigation without full reloads. Platform switching becomes near-instant.
**Implementation:** Add `<ViewTransitions />` to head, `transition:animate` directives to layout. Test with LikeC4 React islands for re-mount correctness.
**Effort:** 4-8 hours

### I4c. Command palette (Cmd+K)
**What:** Quick jump to any platform, page, ADR, or epic by typing. Use lightweight `cmdk` library (3KB gzipped). Index all pages at build time into JSON manifest.
**Effort:** 4-8 hours

### I5. Auto-checkpoint after each pipeline skill
**What:** Automatically save STATE.md after every skill completes (not just when user runs `/checkpoint`).
**Implementation:** Add a post-save hook in `settings.local.json` that triggers checkpoint generation. Or make `post_save.py` also update STATE.md.
**Effort:** 2-4 hours

### I6. Pipeline orchestrator script
**What:** Instead of running skills manually one by one, a `python3 .specify/scripts/pipeline.py run fulano` that executes the entire pending pipeline in DAG order, pausing at human gates.
**Implementation:** Read `platform.yaml` DAG, topological sort, check which nodes are pending, execute in order. Auto-gate nodes proceed, human-gate nodes print "Approve? [y/n]".
**Effort:** 1-2 days

### I7. Memory pruning and health check
**What:** Detect stale memories (>90 days old, referencing deleted files, contradicting current code).
**Implementation:** `python3 .specify/scripts/platform.py memory-health` that checks each memory file against current repo state.
**Effort:** 4-6 hours

### I8. Git hooks for artifact validation
**What:** Pre-commit hook that validates: (a) AUTO markers haven't been manually edited, (b) platform.yaml schema is valid, (c) ADR frontmatter is complete.
**Implementation:** Python pre-commit hook using existing lint functions from `platform.py`.
**Effort:** 2-3 hours

### I9. Portal dark mode + responsive improvements
**What:** Starlight supports dark mode natively. Ensure custom CSS and LikeC4 diagrams render correctly in both modes. Improve mobile nav for deep sidebar trees.
**Implementation:** Test dark mode rendering, fix CSS variables in `custom.css`, add responsive breakpoints for diagram containers.
**Effort:** 4-8 hours

### I10. Unified CLI entrypoint
**What:** Replace multiple script invocations with a single `madruga` CLI:
```bash
madruga platform list          # instead of python3 .specify/scripts/platform.py list
madruga build fulano            # instead of python3 .specify/scripts/vision-build.py fulano
madruga db seed fulano          # instead of python3 .specify/scripts/post_save.py --reseed --platform fulano
madruga pipeline status fulano  # new: visual pipeline status in terminal
```
**Implementation:** Single `cli.py` with `argparse` subcommands delegating to existing modules.
**Effort:** 1 day

### I11. DB backup before migration
**What:** `migrate()` should copy the DB file before applying new migrations. SQLite `ALTER TABLE ADD COLUMN` is irreversible. If a migration fails mid-way, the DB can end up in a broken state.
**Implementation:** `shutil.copy2(DB_PATH, DB_PATH.with_suffix('.db.bak'))` before first pending migration.
**Effort:** 30 min

### I11b. DB migration testing in CI
**What:** Test that migrations apply cleanly on a fresh DB AND on a DB with existing data (upgrade path).
**Implementation:** Add `test_migrations.py` that: (1) applies all migrations fresh, (2) applies them incrementally, (3) verifies schema matches expected state.
**Effort:** 3-4 hours

### I12. LikeC4 model ↔ code drift detection
**What:** When the actual codebase adds/removes services, detect drift from the LikeC4 model.
**Implementation:** Parse `docker-compose.yml` or `Dockerfile` patterns, compare against LikeC4 elements. Report in `platform.py lint`.
**Effort:** 1-2 days (requires Fulano codebase to exist)

### I13. Portal API routes for pipeline data
**What:** Expose pipeline state via Astro API routes so the dashboard can query live data.
```
GET /api/platforms → list platforms
GET /api/platforms/fulano/pipeline → pipeline node status
GET /api/platforms/fulano/decisions → decision list
```
**Implementation:** Astro API routes in `portal/src/pages/api/` reading from SQLite DB.
**Effort:** 4-8 hours

### I14. Automated CLAUDE.md generation
**What:** Parts of CLAUDE.md (command list, pipeline table, file structure) can be auto-generated from the codebase instead of manually maintained.
**Implementation:** Script that reads `platform.yaml` nodes, `.claude/commands/` skill files, and repo structure to regenerate the relevant CLAUDE.md sections between AUTO markers.
**Effort:** 4-6 hours

### I15. Hallucination guard in auto-review (from GSD)
**What:** After any skill's artifact generation step, check if the agent made zero tool calls during generation. If so, reject the output as likely fabricated. Cheap, high-value check.
**Implementation:** Add to the auto-review contract step: count tool_use blocks in the generation phase. Zero calls = automatic rejection with re-prompt.
**Effort:** 1-2 hours

### I16. Pre-inline dependency artifacts in skill prompts (from GSD)
**What:** Currently skills run `check-platform-prerequisites.sh` and then read files via tool calls. Instead, the prerequisite script could output the content of dependency artifacts inline in the dispatch prompt, saving tool-call tokens and giving the agent immediate context.
**Implementation:** Modify prerequisite checker to `--inline-content` mode that outputs file contents, not just status.
**Effort:** 4-6 hours

### I17. Cost tracking per skill/epic (from GSD)
**What:** Track token usage per skill invocation in the SQLite DB (`pipeline_runs` table already has `tokens_in`, `tokens_out`, `cost_usd` columns). This enables budget visibility and identifies which skills are most expensive.
**Implementation:** The DB schema already supports this. Skills just need to report token counts in their `post_save.py` call or via a wrapper.
**Effort:** 2-4 hours

### I18. Adaptive replanning after each L2 epic (from GSD)
**What:** After completing an epic and merging to main, add a lightweight roadmap reassessment step: does the remaining roadmap still make sense given what was learned? Currently the roadmap is static after L1 node 13.
**Implementation:** Add an optional `roadmap-reassess` step after reconcile in the L2 cycle.
**Effort:** 4-6 hours (skill creation)

### I19. Structured escalation levels (from Gas Town)
**What:** Currently `auto-escalate` gate is binary (OK or escalate). Add severity routing: CRITICAL (blocks pipeline), HIGH (blocks this skill, workaround possible), MEDIUM (degraded but can proceed). Gives the human clearer triage.
**Implementation:** Extend gate metadata in platform.yaml and skill contracts.
**Effort:** 4-6 hours

### I20. Wave-based parallel task execution in speckit.implement (from GSD)
**What:** `speckit.implement` processes tasks sequentially. GSD groups independent tasks into waves that execute in parallel (via subagents), with dependent tasks in subsequent waves. Speeds execution and prevents ordering bugs.
**Implementation:** Parse `tasks.md` dependency graph, topological sort into waves, dispatch each wave's tasks as parallel subagents.
**Effort:** 1-2 days

### I21. Atomic git commits per task, not per epic (from GSD + Ralph Wiggum)
**What:** Both GSD and Ralph commit after each completed task, enabling `git bisect` and individual task revert. madruga.ai commits at the epic level after reconcile. Per-task commits make debugging, reviewing, and rollback dramatically easier.
**Implementation:** Modify `speckit.implement` to commit after each task completion, not just at the end.
**Effort:** 2-4 hours

### I22. Fast lane for small changes (from GSD /gsd:quick)
**What:** The 24-skill pipeline is comprehensive but heavy for bug fixes or small features. A "fast lane" would skip L1 and run a compressed L2: specify → implement → verify.
**Implementation:** Add a `--quick` flag or `/quick-fix` skill that runs a minimal cycle.
**Effort:** 4-6 hours

### I23. Developer onboarding script
**What:** No `make setup` or one-liner for new developers. Prerequisites (Node 20+, Python 3.11+, likec4, copier) are documented in CLAUDE.md but not validated automatically.
**Implementation:** `scripts/setup-dev.sh` that checks each prereq, reports what's missing, and offers to install.
**Effort:** 2-3 hours

### I16. Error boundary improvements in portal
**Where:** `LikeC4Diagram.tsx` error boundary shows generic Portuguese error message
**Fix:** Show the specific view ID that failed, suggest checking if the platform is registered in `platformLoaders`. Add retry button.
**Effort:** 1 hour

---

## Priority Matrix

| # | Issue | Severity | Effort | Impact | Priority Score |
|---|-------|----------|--------|--------|----------------|
| B1 | Migration 003 FTS5 failure loop | BLOCKER | 1-2 hrs | Critical | **P0** |
| B2 | SQL injection in bash script | BLOCKER | 1 hr | Critical (security) | **P0** |
| B3 | FTS LIKE fallback data leak | BLOCKER | 5 min | High (security) | **P0** |
| B4 | SSR adapter with no SSR need | BLOCKER | 5 min | High | **P0** |
| B5 | Broken useMemo — diagrams re-mount | BLOCKER | 15 min | High | **P0** |
| B6 | L2 analyze-post missing from platform.yaml | BLOCKER | 30 min | High | **P1** |
| B7 | No portal build in CI | BLOCKER | 15 min | High | **P0** |
| W0b | model/output not in gitignore | WARNING | 2 min | Medium | **P0** |
| W6 | vision-build missing CLI check | WARNING | 5 min | Medium | **P0** |
| W0 | DB connections leak on exceptions | WARNING | 1 hr | Medium | **P1** |
| W12 | YAML frontmatter not escaped | WARNING | 1 hr | Medium | **P1** |
| W0a | Per-function commits in db.py | WARNING | 2-3 hrs | Low (at current scale) | **P2** |
| W0c | No concurrent DB protection | WARNING | 30 min | Medium | **P2** |
| W1 | REPO_ROOT duplication | WARNING | 1 hr | Low | **P2** |
| W5 | No staleness detection | WARNING | 2-3 hrs | Medium | **P2** |
| W3 | No portal search | WARNING | 30 min | Medium | **P2** |
| W2 | DAG triple-definition | WARNING | 4-6 hrs | High | **P2** |
| W10 | reseed_all N connections | WARNING | 30 min | Low | **P2** |
| W11 | Absolute file_paths in DB | WARNING | 2-3 hrs | Medium | **P2** |
| W8 | Missing test coverage | WARNING | 4-6 hrs | Medium | **P3** |
| W10 | Lossy decision export | WARNING | 3-4 hrs | Low | **P3** |
| W4 | No pipeline dashboard | WARNING | 8-12 hrs | High | **P3** |
| I10 | Unified CLI | IMPROVE | 1 day | Medium | **P3** |
| I5 | Auto-checkpoint | IMPROVE | 2-4 hrs | Medium | **P3** |
| I1 | Pipeline dashboard | IMPROVE | 2-3 days | High | **P4** |
| I2 | Decision timeline | IMPROVE | 1-2 days | Medium | **P4** |
| I3 | Cross-platform search | IMPROVE | 4-8 hrs | Medium | **P4** |
| I6 | Pipeline orchestrator | IMPROVE | 1-2 days | High | **P4** |
| I8 | Git hooks validation | IMPROVE | 2-3 hrs | Medium | **P4** |
| I14 | Auto CLAUDE.md | IMPROVE | 4-6 hrs | Medium | **P4** |
| I11 | Migration testing | IMPROVE | 3-4 hrs | Low | **P5** |
| I13 | API routes | IMPROVE | 4-8 hrs | Medium | **P5** |
| I4 | Interactive diagrams | IMPROVE | 2-3 days | Medium | **P5** |
| I7 | Memory pruning | IMPROVE | 4-6 hrs | Low | **P5** |
| I9 | Dark mode fixes | IMPROVE | 4-8 hrs | Low | **P5** |
| I12 | Model-code drift | IMPROVE | 1-2 days | Medium | **P5** |
| I15 | Error boundary UX | IMPROVE | 1 hr | Low | **P5** |

---

## Recommended Execution Order

### Sprint 1 — Critical Fixes (1 day)
1. **B2** — Fix SQL injection in bash script (pass vars as sys.argv)
2. **B3** — Fix FTS LIKE fallback (add parentheses) — 5 min
3. **B4** — Remove SSR adapter from portal (switch to static) — 5 min
4. **B5** — Fix broken useMemo in LikeC4Diagram.tsx — 15 min
5. **B1** — Split migration 003 to handle missing FTS5
6. **B7** — Add portal build to CI
7. **W0b** — Add `model/output/` to `.gitignore`
8. **W6** — Add CLI pre-check to vision-build.py
9. **W10c** — Fix font declarations (load or remove)
10. **W10d** — Move @types to devDependencies
11. **W13** — Use yaml.dump() for frontmatter exports

### Sprint 2 — Foundation Fixes (2-3 days)
8. **B6** — Add post-implementation analyze node to platform.yaml + Copier template
9. **W0** — Add connection context manager to db.py
10. **W0a/W0c** — Transaction batching + concurrent access docs
11. **W1** — Extract shared config.py
12. **W5** — Add staleness detection to lint
13. **W10-W10c** — Fix branch guard docs, clarify dependency, QA flag, constitution ref
14. **W11** — Fix reseed_all to use single connection
15. Continue Fulano L1 pipeline (run remaining skills)

### Sprint 3 — Single Source of Truth (1 week)
10. **W2** — DAG defined once in platform.yaml, generated elsewhere
11. **W8** — Add missing test coverage
12. **W10** — Fix lossy decision round-tripping
13. **I14** — Auto-generate CLAUDE.md sections
14. **I10** — Unified CLI entrypoint

### Sprint 4 — Dream Frontend (1-2 weeks)
15. **W3** — Enable portal search
16. **W4/I1** — Pipeline status dashboard
17. **I2** — Decision timeline
18. **I3** — Cross-platform search with facets
19. **I13** — API routes for live data
20. **I9** — Dark mode + responsive polish

### Sprint 5 — Automation & Intelligence (1 week)
21. **I5** — Auto-checkpoint after skills
22. **I6** — Pipeline orchestrator script
23. **I8** — Git hooks for validation
24. **I7** — Memory pruning
25. **I11** — Migration upgrade testing
26. **I12** — Model ↔ code drift detection

---

## Benchmark Comparison Matrix

| Dimension | madruga.ai | BMAD (23.6k stars) | GSD (23k stars) | Gas Town | OpenClaw |
|-----------|-----------|-----|-----|----------|----------|
| **Pipeline model** | 24-skill DAG (L1+L2) | 4-phase sequential, 3 tracks | Milestone/Slice/Task tree | Convoy/Molecule workflows | 6-stage lane queues |
| **Context strategy** | Fresh subagent per skill | Scoped artifacts per persona | Fresh 200k window per task | Persistent hooks + seance | Semantic snapshots |
| **Memory** | SQLite + markdown + FTS5 | Artifact files only | STATE.md + disk state | Git-backed beads + JSONL | JSONL + MEMORY.md |
| **Decision tracking** | ADRs in DB with FTS5 + links | Implicit in artifacts | Decision registers in specs | Beads + escalation routing | Session history |
| **Quality gates** | 4 types (human/auto/1-way-door/auto-escalate) | Agent transition gates | 8-question parallel gates | Refinery merge queue | Pipeline stage checks |
| **Crash recovery** | Optional checkpoint | None documented | Session reconstruction from tool calls | Hooks + 3-tier watchdog | Lane queue replay |
| **Cost tracking** | Schema exists but unused | None | Per unit/phase/model with budgets | None | None |
| **Git strategy** | Epic branches, PR-per-epic | Not specified | Milestone branches, squash-merge | Worktrees per agent, refinery merge | Not SDLC-focused |
| **Scale target** | Solo to small team | Solo to team | Solo to small team | 20-30 parallel agents | Personal assistant |
| **Arch-as-code** | LikeC4 (DSL + React + portal) | None | None | None | None |

**Honest assessment:**
- madruga.ai has the **deepest pipeline** (24 skills, 2-level DAG) and is the **only framework with architecture-as-code** integration
- **BMAD** has better formalized persona orchestration (9 distinct roles) and three implementation tracks
- **GSD** has better context management (pre-inlined context, hallucination guards), cost tracking, and crash recovery
- **Gas Town** solves a different problem (parallel agent colonies) but its seance pattern and merge queue are applicable
- **Main gaps to close**: hallucination guard (from GSD), cost tracking (schema ready, just unused), auto-checkpoint (from GSD/OpenClaw), pre-inlined context injection (from GSD)

---

## Test Coverage Summary

| Component | Tests | CI Coverage | Verdict |
|-----------|-------|-------------|---------|
| DB layer (db.py) | 6 test files, ~40 tests | Yes (db-tests job) | Good |
| Copier template | 2 test files, ~15 tests | Yes (templates job) | Good, 2 skipped |
| platform.py | 1 test file, 5 tests | Yes (db-tests job) | Adequate |
| post_save.py | 1 test file, 5 tests | Yes (db-tests job) | Adequate |
| Bash scripts | 1 test file (manual) | **No** | Gap |
| vision-build.py | 0 tests | **No** | Gap |
| sync_memory.py | 0 tests | **No** | Gap |
| Portal build | 0 tests | **No** | Gap |
| LikeC4 models | build validation only | Yes (likec4 job) | Adequate |
| Ruff formatting | 0 checks | **No** | Gap |
