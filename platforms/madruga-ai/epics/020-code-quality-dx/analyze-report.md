# Specification Analysis Report — Epic 020: Code Quality & DX

**Generated**: 2026-04-04  
**Branch**: `epic/madruga-ai/020-code-quality-dx`  
**Artifacts analyzed**: spec.md, plan.md, tasks.md, data-model.md, quickstart.md, research.md  
**Constitution version**: 1.1.0

---

## Findings Table

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Constitution | CRITICAL | tasks.md:T008–T010, plan.md:§Logging contract | `_NDJSONFormatter` emits `{timestamp, level, message, logger}` — missing `correlation_id` and `context` fields required by Constitution §IX MUST schema | Add `"correlation_id": null` and `"context": {}` to formatter output; null/empty is acceptable for standalone CLI invocations but must be present for schema compliance |
| I1 | Inconsistency | HIGH | tasks.md:T006, tests/test_db_core.py:L1–95 | T006 says "Create `test_db_core.py`" but the file already exists with 9 tests, all importing from `db` (not `db_core`). Running T006 as written would clobber the existing file. | Change T006 verb from "Create" to "Update"; the task should add the 5 missing test cases and update imports to `db_core` while preserving the 9 existing tests |
| I2 | Inconsistency | HIGH | tasks.md:T015 | T015 is labeled "test `sync_memory.py`" but every test case exercises `import_memory_from_markdown()` and `export_memory_to_markdown()` — functions that live in `db.py` (db_decisions), **not** in `sync_memory.py`. The file being tested is misidentified. | Rename T015 to "test_db_decisions_memory.py" OR confirm the intent is to test memory round-trip through db_decisions; spec says "test `sync_memory.py`" (US6, SC-005) which needs reconciling |
| I3 | Inconsistency | HIGH | tasks.md:T011 | T011 carries `[US2]` label (Machine-Parseable Output) but it implements US3 (Memory Health Monitoring) | Fix label to `[US3]` |
| I4 | Inconsistency | MEDIUM | tasks.md:T013, tasks.md:§Dependencies | T013 is marked `[P]` (parallel) but modifies `platform_cli.py` — the same file as T008. The dependency section says "after T008". Running T013 in parallel with T008 causes merge conflicts on the same file. | Remove `[P]` marker from T013; add explicit dependency: T013 depends on T008 |
| I5 | Inconsistency | MEDIUM | tasks.md:T011 | Memory dir path hardcoded as absolute machine path `.claude/projects/-home-gabrielhamu-repos-paceautomations-madruga-ai/memory/` — breaks CI and any non-Linux workstation | Derive path dynamically: `Path(repo_root) / ".claude" / "projects" / <hashed_path> / "memory"` or discover via `find_memory_dirs()` already in `sync_memory.py` |
| A1 | Ambiguity | MEDIUM | spec.md:§Edge Cases | Edge case: "What if `--json` flag is passed and a fatal error occurs **before** logging is initialized?" — argparse errors go to stderr as plain text. T008–T010 call `_setup_logging(args.json)` after `parse_args()` but argparse failures precede that call. | Add explicit note in T008–T010 that argparse `SystemExit` tracebacks are acceptable on stderr (not stdout); or wrap `parse_args()` with try/except for JSON-mode error emission |
| D1 | Duplication | LOW | tasks.md:T008, T009, T010 | `_NDJSONFormatter` class is defined identically in three scripts. Plan.md notes this ("3 scripts × ~10 LOC = 30 LOC total") as intentional to avoid a new module dependency, but this is 30 LOC of pure duplication that will drift. | Acceptable per stated constraint (no new modules); add a comment `# Duplicated by design — no shared util module in this scripts dir` to each copy so future maintainers understand the intent |
| U1 | Underspecification | LOW | tasks.md:T012, spec.md:FR-007 | FR-007 requires `handoffs` NIT check for all archetypes. Current linter (line 247) only checks `pipeline` and `specialist`. T012 says "verify at line ~248 and widen if not" — deferring to runtime discovery rather than being explicit. | Add explicit instruction in T012: "extend the `if archetype in ('pipeline', 'specialist'):` block to `if archetype in ('pipeline', 'specialist', 'utility'):` for handoffs check" |
| U2 | Underspecification | LOW | plan.md:§Task breakdown | plan.md says `db_pipeline.py` ~550 LOC while pitch.md said ~500 LOC (31 symbols vs 29); data-model.md lists 31 symbols for db_pipeline.py but T002 says "29 symbols listed in data-model.md §1" — symbol count is inconsistent across artifacts | Authoritative count is data-model.md §1 (31 symbols per table); update T002 to reference "31 symbols" |

---

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 db split | ✅ | T001–T004 | 4 modules created |
| FR-002 re-export facade | ✅ | T005 | backward compat |
| FR-003 structured logging | ✅ | T008–T010 | 3 scripts covered |
| FR-004 --json flag | ✅ | T008–T010 | NDJSON mode |
| FR-005 memory dry-run default | ✅ | T011 | |
| FR-006 memory detections | ✅ | T011 | stale+dup+index |
| FR-007 skill linter | ✅ | T012 | gate+output-dir |
| FR-008 lru_cache | ✅ | T013 | |
| FR-009 test suites | ✅ | T014, T015 | ⚠ T015 source mismatch (I2) |
| FR-010 make test passes | ✅ | T016, T017 | |
| FR-011 ruff passes | ✅ | T016 | |
| SC-001 db modules < 900 LOC | ✅ | T001–T005 | |
| SC-002 NDJSON parseable | ✅ | T008 | ⚠ schema gap (C1) |
| SC-003 memory < 5s | ✅ | T011 | |
| SC-004 lint 100% detection | ✅ | T012 | |
| SC-005 make test green | ✅ | T016, T017 | |
| SC-006 zero regressions | ✅ | T005–T007 | |
| US1 maintainable db module | ✅ | T001–T007 | ⚠ T006 file exists (I1) |
| US2 machine-parseable output | ✅ | T008–T010 | ⚠ schema gap (C1) |
| US3 memory health monitoring | ✅ | T011 | ⚠ label error (I3) |
| US4 skill contract detection | ✅ | T012 | |
| US5 faster status queries | ✅ | T013 | ⚠ parallel conflict (I4) |
| US6 test coverage | ✅ | T014, T015 | ⚠ T015 module mismatch (I2) |

---

## Constitution Alignment Issues

| Principle | Status | Details |
|-----------|--------|---------|
| §I Pragmatism + simplicity | ✅ PASS | stdlib logging, flat modules, re-export facade — all minimal |
| §IV Fast Action + TDD | ✅ PASS | Tests defined (T006, T014, T015) before implementation |
| §VII TDD — tests before code | ✅ PASS | All task phases have test coverage tasks |
| §VIII Collaborative decisions | ✅ PASS | research.md documents 6 decisions with alternatives |
| §IX Observability + Logging | ❌ **CRITICAL** | `_NDJSONFormatter` schema is missing `correlation_id` and `context` fields mandated by §IX. The schema defined in plan.md §Logging contract emits `{timestamp, level, message, logger}` but §IX MUST requires `{timestamp, level, message, correlation_id, context}`. |

---

## Unmapped Tasks

None. All 17 tasks map to at least one FR/SC/US.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 11 |
| Total Success Criteria (buildable) | 6 |
| Total User Stories | 6 |
| Total Tasks | 17 |
| FR Coverage % | 100% |
| SC Coverage % | 100% |
| US Coverage % | 100% |
| Ambiguity Count | 1 |
| Duplication Count | 1 |
| Inconsistency Count | 5 |
| Constitution Violations | 1 (CRITICAL) |
| Critical Issues | 1 |
| High Issues | 3 |
| Medium Issues | 2 |
| Low Issues | 3 |

---

## Next Actions

### CRITICAL — Fix before `/speckit.implement`

**C1 — Constitution §IX schema**: The `_NDJSONFormatter` in tasks T008, T009, T010 must be updated to emit `correlation_id` and `context` fields. Recommended fix for the formatter's `format()` method:

```python
return json.dumps({
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    "level": record.levelname,
    "message": record.getMessage(),
    "logger": record.name,
    "correlation_id": None,   # null for standalone CLI invocations
    "context": {},            # empty dict; callers can extend via LogRecord.context
})
```

This is a one-line-per-script change to plan.md and tasks.md before implementation begins.

### HIGH — Fix before implementation

**I1 — test_db_core.py exists**: Update T006's description to say "Update" (not "Create") `test_db_core.py`. Add the 5 required new test cases to the existing 9 tests. Update imports from `db` → `db_core` for the connection/migration tests.

**I2 — T015 module mismatch**: `sync_memory.py` contains only `find_memory_dirs()`, `sync()`, `main()`. The functions tested in T015 (`import_memory_from_markdown`, `export_memory_to_markdown`) live in `db.py`. Decide and clarify before implementation:
- Option A: Rename test file to `test_db_decisions_memory.py` and confirm it covers db_decisions memory functions (aligns with data-model.md split)
- Option B: Keep `test_sync_memory.py` name but update test cases to exercise `sync_memory.sync()` end-to-end against a real memory directory fixture

**I3 — T011 label**: Change `[US2]` to `[US3]` in tasks.md for T011. (Trivial fix.)

### MEDIUM — Fix before implementation

**I4 — T013 parallel marker**: Remove `[P]` from T013. It modifies `platform_cli.py` concurrently with T008. Mark it sequential: T008 → T013.

**I5 — hardcoded memory dir**: Replace the hardcoded path in T011 with a dynamic resolution strategy using `sync_memory.find_memory_dirs()` (which already handles this) or by deriving from `Path(__file__).parent.parent.parent`.

### LOW — Optional improvements

- **D1**: Add `# Duplicated by design` comment to each `_NDJSONFormatter` copy (T008–T010)
- **U1**: Make T012's handoffs scope expansion explicit rather than deferred
- **U2**: Fix T002 symbol count to "31" to match data-model.md

---

## Remediation Offer

Would you like me to suggest concrete remediation edits for the top findings (C1 + I1 + I2 + I3 + I4 + I5)? These are the 6 issues that should be resolved before implementation begins. I can provide specific text changes for tasks.md and plan.md.
