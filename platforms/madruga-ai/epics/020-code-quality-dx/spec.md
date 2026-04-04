# Feature Specification: Code Quality & Developer Experience

**Feature Branch**: `epic/madruga-ai/020-code-quality-dx`
**Created**: 2026-04-04
**Status**: Draft
**Input**: User description: "madruga-ai 020-code-quality-dx"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Maintainable Database Module (Priority: P1)

A developer working on pipeline features opens the database layer and immediately understands which file to edit without reading 2,268 lines of mixed concerns. Each module has a single responsibility, so a bug in decision storage does not require navigating observability code to find it.

**Why this priority**: The `db.py` monolith is the highest-risk file in the codebase. A 2,268-line file with 6 mixed responsibilities slows every contributor who touches storage logic and creates merge conflict risk. This is the structural foundation all other improvements depend on.

**Independent Test**: Can be validated by opening any of the 4 new modules and confirming it contains only its declared responsibility. All existing callers continue to work without modification.

**Acceptance Scenarios**:

1. **Given** a developer needs to fix a bug in how pipeline run statuses are computed, **When** they look for the relevant code, **Then** they find it in a single focused module (under 600 lines) without navigating unrelated code.
2. **Given** any existing script that does `from db import get_conn` or `from db import insert_decision`, **When** it runs after the split, **Then** it continues to work without any modification to the caller.
3. **Given** the test suite runs, **When** `make test` is executed, **Then** all tests pass including the re-named/new test modules covering each db layer.

---

### User Story 2 — Machine-Parseable Script Output (Priority: P1)

A CI pipeline consuming madruga scripts can extract structured events without writing fragile regex against human-readable strings. A developer debugging a failed run can see a clean event log grouped by severity rather than interspersed `print("[ok]")` noise.

**Why this priority**: CI parsability is a prerequisite for automated status dashboards and error alerting. Mixed `print()` / `log.*()` output makes the tooling unreliable as a programmatic interface and produces false-positive grep matches in log analysis.

**Independent Test**: Run `python3 platform_cli.py status --all --json` and pipe to a JSON processor — every line must be valid JSON with `level`, `message`, and `timestamp` fields.

**Acceptance Scenarios**:

1. **Given** a CI job runs `platform_cli.py status --all --json`, **When** it processes the output, **Then** every output line is valid NDJSON (one JSON object per line) with no plain-text lines mixed in.
2. **Given** any script is run without `--json`, **When** it performs an internal operation (not final user output), **Then** the message is emitted via the logging system (not raw `print()`), so severity level is visible.
3. **Given** an error occurs during script execution, **When** output is captured, **Then** the error event has `level: "ERROR"` in JSON mode and `ERROR` prefix in human mode.

---

### User Story 3 — Memory Health Monitoring (Priority: P2)

A developer can run a single command to discover which memory entries have become stale, which entries contradict each other, and whether the memory index is approaching its 200-line limit — all without manually reviewing dozens of markdown files.

**Why this priority**: Memory is only useful if it is accurate. Stale or contradictory memory misleads future conversations more than no memory at all. The 200-line hard limit on `MEMORY.md` makes overflow a silent failure risk.

**Independent Test**: Running `memory_consolidate.py --dry-run` produces a report listing stale entries, contradictions, and index line count. No files are modified in dry-run mode.

**Acceptance Scenarios**:

1. **Given** a memory file has not been updated in over 90 days, **When** `memory_consolidate.py --dry-run` runs, **Then** the report flags it as stale with the last-updated date.
2. **Given** two memory files of the same type have descriptions that overlap significantly, **When** the consolidation runs, **Then** the report suggests merging them.
3. **Given** `MEMORY.md` has 195 or more lines, **When** the consolidation runs, **Then** the report warns that the index is approaching the 200-line limit.
4. **Given** `--dry-run` mode is active (the default), **When** the script runs, **Then** no files are written or modified — only a report is printed.
5. **Given** `--apply` mode is requested, **When** the script runs, **Then** entries flagged as stale are marked for review in-place (not deleted).

---

### User Story 4 — Skill Contract Compliance Detection (Priority: P2)

A skill author runs the linter before committing and immediately learns whether their skill is missing required structural elements — before the gap causes a silent failure downstream in the pipeline.

**Why this priority**: Skills that drift from the 6-step contract cause inconsistent pipeline behavior that is hard to trace. Early detection at lint time is far cheaper than debugging a skill mid-execution.

**Independent Test**: Create a test skill without an `## Output Directory` section, run `skill-lint.py`, and confirm it reports a WARNING for that specific gap.

**Acceptance Scenarios**:

1. **Given** a skill file is missing the `## Output Directory` section, **When** `skill-lint.py` runs, **Then** a WARNING is reported for that skill identifying the missing section.
2. **Given** a skill's frontmatter has a `gate` value that is not in the canonical set (`human`, `auto`, `1-way-door`, `auto-escalate`), **When** `skill-lint.py` runs, **Then** an ERROR is reported.
3. **Given** a skill has all required contract elements, **When** `skill-lint.py` runs, **Then** no new warnings or errors are added beyond what was already reported.
4. **Given** `skill-lint.py --json` is run, **When** new contract check violations are present, **Then** they appear in the JSON output with `severity` field (`WARNING`, `ERROR`, or `NIT`).

---

### User Story 5 — Faster Repeated Status Queries (Priority: P3)

A developer running `platform_cli.py status --all` experiences noticeably faster execution on the second and subsequent calls within the same session, because platform discovery does not re-read the filesystem on every invocation.

**Why this priority**: This is a low-risk, one-hour quality-of-life improvement that directly reduces friction in the most commonly-used status workflow. It unblocks faster iteration in automation scripts that call status multiple times.

**Independent Test**: Instrument `_discover_platforms()` with a counter; call `status --all` twice in the same Python session and confirm the filesystem read happens only once.

**Acceptance Scenarios**:

1. **Given** `_discover_platforms()` has been called once during a session, **When** it is called again, **Then** the filesystem is not re-read — the cached result is returned.
2. **Given** a new platform is created during the same session (via `new` command), **When** `_discover_platforms()` is called afterward, **Then** the cache is cleared and the new platform is discovered.

---

### User Story 6 — Test Coverage for Untested Scripts (Priority: P3)

A developer modifying `vision-build.py` or `sync_memory.py` has automated tests that catch regressions immediately via `make test`, rather than discovering breakage manually or in CI.

**Why this priority**: These two scripts currently have zero automated tests despite performing critical operations (populating LikeC4 model markers and synchronizing memory state). Any change to them is a blind change.

**Independent Test**: Run `make test` and confirm tests for `vision-build.py` and `sync_memory.py` are executed and pass.

**Acceptance Scenarios**:

1. **Given** `test_vision_build.py` exists with at least 5 test cases, **When** `make test` runs, **Then** all vision-build tests pass.
2. **Given** `test_sync_memory.py` exists with at least 5 test cases, **When** `make test` runs, **Then** all sync-memory tests pass.
3. **Given** a test simulates missing external CLI tools (e.g., `likec4` not installed), **When** `vision-build.py --export-png` is called, **Then** it fails gracefully with a clear error message rather than an unhandled exception.
4. **Given** a memory file is exported and then re-imported, **When** the round-trip completes, **Then** no data is lost and frontmatter types (`user`, `feedback`, `project`, `reference`) are preserved exactly.

---

### Edge Cases

- What happens when `db.py` re-export facade is imported alongside a direct import from a split module (e.g., `from db import X` and `from db_pipeline import X` in the same file)? No conflicts or double-registration should occur.
- How does the memory consolidation script handle a memory file with a malformed frontmatter? It must skip the file and report it as unparseable rather than crashing.
- What if `MEMORY.md` already exceeds 200 lines when the consolidation script runs? The report must flag this as a critical issue (not just a warning).
- What if `--json` flag is passed to a script that encounters a fatal error before logging is initialized? The script must not emit plain-text tracebacks to stdout in JSON mode; errors must be captured and emitted as JSON events.
- What if `skill-lint.py` is run on a skill with a completely absent frontmatter block? The gate validation check must handle this gracefully (report ERROR without crashing).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The database layer MUST be split into 4 focused modules (`db_core`, `db_pipeline`, `db_decisions`, `db_observability`), each containing only its declared responsibility.
- **FR-002**: A re-export facade in `db.py` MUST ensure all existing `from db import ...` statements continue to work without modification.
- **FR-003**: All internal script operations MUST emit messages through the structured logging system rather than bare `print()` calls.
- **FR-004**: Scripts (`platform_cli.py`, `dag_executor.py`, `post_save.py`) MUST support a `--json` flag that switches output to NDJSON format (one JSON object per line).
- **FR-005**: The memory consolidation tool MUST operate in dry-run mode by default and MUST NOT delete or overwrite any files without explicit `--apply` flag.
- **FR-006**: The memory consolidation tool MUST detect entries older than 90 days, entries with description overlap of the same type, and index files approaching the 200-line limit.
- **FR-007**: The skill linter MUST validate the presence of `## Output Directory` section (WARNING), canonical `gate` values (ERROR), and `handoffs` frontmatter key (NIT).
- **FR-008**: Platform discovery functions MUST cache filesystem reads for the lifetime of a single script invocation, with explicit cache invalidation when the platform list changes.
- **FR-009**: Test suites for `vision-build.py` and `sync_memory.py` MUST exist with at least 5 test cases each.
- **FR-010**: The entire test suite (`make test`) MUST pass after all changes.
- **FR-011**: Ruff linting (`make ruff`) MUST pass with zero violations after all changes.

### Key Entities

- **Database Module**: One of four focused Python files replacing the monolith (`db_core`, `db_pipeline`, `db_decisions`, `db_observability`). Each has a single declared responsibility and clear import boundaries.
- **Re-export Facade**: The existing `db.py` retains its name and re-exports all public symbols from the 4 modules, preserving backward compatibility for all callers.
- **Memory Entry**: A markdown file with YAML frontmatter (`name`, `type`, `description`, body). Has a `type` (user/feedback/project/reference) and implicit last-modified date.
- **Memory Index**: `MEMORY.md` — a flat index of all memory entries, capped at 200 lines. Managed by the consolidation tool.
- **Skill Contract**: The 6-section structure every skill must follow, including `## Output Directory`, valid `gate` frontmatter, `handoffs`, and prerequisite references.
- **Log Event**: A structured record emitted by a script, containing at minimum `level`, `message`, and `timestamp`. In `--json` mode, serialized as a single-line JSON object.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can locate and read the full source for any single database concern (connections, pipeline CRUD, decisions, observability) in a file with fewer than 900 lines.
- **SC-002**: `platform_cli.py status --all --json` output can be processed by any JSON line-parser with 0 parse errors across all emitted lines.
- **SC-003**: Running `memory_consolidate.py --dry-run` completes and produces an actionable report in under 5 seconds on a repository with up to 50 memory files.
- **SC-004**: `skill-lint.py` detects 100% of skills missing `## Output Directory` and reports them as WARNINGs — validated by intentionally removing the section from a test skill.
- **SC-005**: `make test` achieves green status covering the 2 previously-untested scripts, with at least 5 test cases each — bringing total automated test coverage to include all scripts in `.specify/scripts/`.
- **SC-006**: Zero regressions: every script that was working before the changes continues to work identically (all existing imports, CLI flags, and output formats preserved for non-`--json` modes).

## Assumptions

- Epic 018 (pipeline hardening, including typed error hierarchy) is merged to main before this epic begins implementation, as `db.py` split depends on typed errors replacing `SystemExit`.
- The codebase uses only stdlib and `pyyaml` — no new external dependencies will be introduced (structlog is explicitly out of scope).
- Memory consolidation heuristics for "contradiction detection" use description-field similarity (same `type` + overlapping keywords) — semantic embedding is out of scope.
- `lru_cache` invalidation is only needed for the `new` and `sync` commands; all other script invocations are single-shot and benefit from session-lifetime caching without TTL.
- Existing tests in `test_db_decisions.py` and `test_db_observability.py` are retained as-is; only `test_db_crud.py` is renamed to `test_db_pipeline.py` and a new `test_db_core.py` is created.
- The `--json` flag in `--json` mode suppresses the human-readable format entirely; mixed-mode output is not required.
