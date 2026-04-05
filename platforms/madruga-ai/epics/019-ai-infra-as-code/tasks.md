# Tasks: AI Infrastructure as Code

**Input**: Design documents from `platforms/madruga-ai/epics/019-ai-infra-as-code/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Included — plan.md defines 7 unit tests for `skill-lint.py` extensions and constitution requires TDD (Principle VII).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **skill-lint.py extensions**: `.specify/scripts/skill-lint.py`
- **Tests**: `.specify/scripts/tests/test_skill_lint.py`
- **CI workflow**: `.github/workflows/ci.yml`
- **Governance docs**: repo root (`SECURITY.md`, `CONTRIBUTING.md`) and `.github/`
- **Platform config**: `platforms/madruga-ai/platform.yaml`
- **Copier template**: `.specify/templates/platform/template/platform.yaml.jinja`

---

## Phase 1: Setup

**Purpose**: No project initialization needed — this epic extends existing tools and creates convention files. Skip to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `build_knowledge_graph()` is the core function reused by US3 (impact analysis), US4 (CI gate), and US5 (knowledge declarations). Must be implemented first.

**CRITICAL**: US3, US4, and US5 cannot proceed without this phase.

- [X] T001 Implement `build_knowledge_graph()` function in `.specify/scripts/skill-lint.py` — scan all `.md` files in `COMMANDS_DIR`, extract `.claude/knowledge/([\w.-]+\.(?:md|yaml))` references via regex, return `dict[str, set[str]]` mapping knowledge filename to set of skill names. Reuse existing `COMMANDS_DIR` constant
- [X] T002 Write test `test_build_knowledge_graph` in `.specify/scripts/tests/test_skill_lint.py` — verify graph matches known references: `pipeline-contract-engineering.md` maps to 5 skills (adr, blueprint, containers, context-map, domain-model), `pipeline-contract-base.md` maps to 20 skills, `commands.md` maps to 0 skills. Use actual files on disk (no mocks for file scanning)

**Checkpoint**: `build_knowledge_graph()` returns accurate dependency map. Tests pass via `make test`.

---

## Phase 3: User Story 3 - Impact Analysis for Knowledge File Changes (Priority: P1)

**Goal**: Enable `python3 .specify/scripts/skill-lint.py --impact-of <path>` to show which skills break when a knowledge file changes.

**Independent Test**: `python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/pipeline-contract-engineering.md` lists 5 skills with archetypes.

### Tests for User Story 3

- [X] T003 [P] [US3] Write test `test_impact_of_known_file` in `.specify/scripts/tests/test_skill_lint.py` — call `cmd_impact_of("pipeline-contract-engineering.md")` and verify it returns/prints 5 skills (adr, blueprint, containers, context-map, domain-model) each with archetype "pipeline"
- [X] T004 [P] [US3] Write test `test_impact_of_unknown_file` in `.specify/scripts/tests/test_skill_lint.py` — call `cmd_impact_of("nonexistent-file.md")` and verify it returns empty result without error (exit 0)

### Implementation for User Story 3

- [X] T005 [US3] Implement `cmd_impact_of(path: str)` function in `.specify/scripts/skill-lint.py` — extract filename from path, look up in `build_knowledge_graph()`, print table with columns `| Skill | Archetype |` using `get_archetype()`. Exit 0 (informational, never blocks CI)
- [X] T006 [US3] Add `--impact-of <path>` argparse argument to `main()` in `.specify/scripts/skill-lint.py` — when present, skip normal lint flow and run only `cmd_impact_of()`. Mutually exclusive with `--skill`

**Checkpoint**: `python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/pipeline-contract-engineering.md` lists 5 skills. `make test && make ruff` pass.

---

## Phase 4: User Story 1 - Mandatory Review on AI Instruction Changes (Priority: P1)

**Goal**: All changes to `.claude/`, `CLAUDE.md`, and platform `CLAUDE.md` files require code owner review before merge.

**Independent Test**: Submit a PR modifying a file under `.claude/` and verify merge is blocked without code owner approval.

### Implementation for User Story 1

- [X] T007 [P] [US1] Create `.github/CODEOWNERS` with 4 path rules: `/.claude/ @gabrielhamu-srna`, `/CLAUDE.md @gabrielhamu-srna`, `/platforms/*/CLAUDE.md @gabrielhamu-srna`, `/.specify/scripts/skill-lint.py @gabrielhamu-srna`. Include header comment explaining purpose

**Manual step** (not a task — document in PR): Enable "Require review from Code Owners" in GitHub Settings > Branches > main. Enable "Allow administrators to bypass".

**Checkpoint**: `.github/CODEOWNERS` exists with correct patterns.

---

## Phase 5: User Story 2 - Security Scanning for Dangerous Patterns (Priority: P1)

**Goal**: CI automatically detects dangerous code patterns (`eval()`, `exec()`, hardcoded API keys, `.env` files) and blocks PRs.

**Independent Test**: Push a test file with `eval()` and verify CI fails with a clear error.

### Implementation for User Story 2

- [X] T008 [P] [US2] Add `security-scan` job to `.github/workflows/ci.yml` — Step 1: grep for dangerous patterns (`eval\(|exec\(|subprocess\.call\(.*shell=True|PRIVATE.KEY|password\s*=\s*["'][^"']`) in `.specify/scripts/` Python files. Step 2: find `.env` files (excluding `.git/`, `node_modules/`), grep for API key patterns (`sk-[a-zA-Z0-9]{20,}`, `AKIA[A-Z0-9]{16}`) across `.py`, `.md`, `.yaml` files. Use `actions/checkout@v4`. Runs on both push and PR (same triggers as existing jobs)

**Checkpoint**: CI workflow has `security-scan` job. `make ruff` passes (YAML only, no Python changes).

---

## Phase 6: User Story 4 - CI Gate for AI Instruction Changes (Priority: P2)

**Goal**: CI automatically runs skill-lint and impact analysis when AI instruction files change in a PR.

**Independent Test**: Push a PR modifying `.claude/` and verify skill-lint and impact analysis run in CI logs.

**Depends on**: Phase 3 (US3 — `--impact-of` must exist)

### Implementation for User Story 4

- [X] T009 [US4] Add `ai-infra` job to `.github/workflows/ci.yml` — PR-only (`if: github.event_name == 'pull_request'`). Steps: (1) checkout with `fetch-depth: 0`, (2) detect AI infra changes via `git diff --name-only origin/${{ github.base_ref }}...HEAD` matching `^(\.claude/|CLAUDE\.md|platforms/.*/CLAUDE\.md)`, (3) conditional setup-python 3.11 + pip install, (4) run `skill-lint.py` full lint, (5) run `skill-lint.py --impact-of` for each changed knowledge file with `::group::` log formatting. All steps after detection conditional on `steps.detect.outputs.changed == 'true'`

**Checkpoint**: CI workflow has `ai-infra` job that conditionally runs lint + impact. YAML valid.

---

## Phase 7: User Story 5 - Knowledge Dependency Declarations (Priority: P2)

**Goal**: Declare knowledge file consumers in `platform.yaml` and validate with skill-lint.

**Independent Test**: Run `python3 .specify/scripts/skill-lint.py` and verify no warnings for correctly declared knowledge files, warnings for undeclared references.

**Depends on**: Phase 2 (`build_knowledge_graph()`)

### Tests for User Story 5

- [X] T010 [P] [US5] Write test `test_lint_knowledge_declarations_valid` in `.specify/scripts/tests/test_skill_lint.py` — create a temp platform.yaml with correctly declared knowledge files, verify `lint_knowledge_declarations()` returns no warnings
- [X] T011 [P] [US5] Write test `test_lint_knowledge_declarations_missing_file` in `.specify/scripts/tests/test_skill_lint.py` — declare a nonexistent file in temp platform.yaml, verify WARNING is generated (not BLOCKER)
- [X] T012 [P] [US5] Write test `test_lint_knowledge_declarations_undeclared_ref` in `.specify/scripts/tests/test_skill_lint.py` — create temp platform.yaml missing a known declaration, verify WARNING for undeclared dependency
- [X] T013 [P] [US5] Write test `test_all_pipeline_resolution` in `.specify/scripts/tests/test_skill_lint.py` — verify `all-pipeline` shorthand resolves dynamically to all L1 + L2 node IDs from `pipeline.nodes[]` and `pipeline.epic_cycle.nodes[]` in platform.yaml

### Implementation for User Story 5

- [X] T014 [US5] Implement `lint_knowledge_declarations(platform_yaml_path: Path) -> list[dict]` in `.specify/scripts/skill-lint.py` — parse `knowledge:` section from platform.yaml, validate each declared file exists in `KNOWLEDGE_DIR`, build knowledge graph via `build_knowledge_graph()`, cross-check skill body references vs declarations (WARNING for undeclared), resolve `all-pipeline` dynamically from `pipeline.nodes[].id` and `pipeline.epic_cycle.nodes[].id`. Return list of finding dicts (severity: WARNING only, never BLOCKER)
- [X] T015 [US5] Integrate `lint_knowledge_declarations()` into `main()` in `.specify/scripts/skill-lint.py` — call when `--skill` is not set, `--impact-of` is not set, and a `platforms/madruga-ai/platform.yaml` exists. Append findings to `all_findings`
- [X] T016 [US5] Add `knowledge:` section to `platforms/madruga-ai/platform.yaml` — declare 8 knowledge files with consumers per research.md verified graph: `pipeline-contract-base.md` (all-pipeline), `pipeline-contract-business.md` ([business-process, platform-new, solution-overview, vision]), `pipeline-contract-engineering.md` ([adr, blueprint, containers, context-map, domain-model]), `pipeline-contract-planning.md` ([epic-breakdown, roadmap]), `likec4-syntax.md` ([containers, domain-model]), `pipeline-dag-knowledge.md` ([business-process]), `judge-config.yaml` ([judge]), `qa-template.md` ([qa])
- [X] T017 [US5] Add optional `knowledge:` section to `.specify/templates/platform/template/platform.yaml.jinja` — include YAML comment explaining format and `all-pipeline` shorthand. Section should be commented out or empty by default for new platforms

**Checkpoint**: `python3 .specify/scripts/skill-lint.py` runs knowledge declaration validation. `make test && make ruff` pass.

---

## Phase 8: User Story 6 - Governance Documentation (Priority: P2)

**Goal**: Create SECURITY.md, CONTRIBUTING.md, and PR template recognized by GitHub.

**Independent Test**: Verify files exist and contain required sections (`ls SECURITY.md CONTRIBUTING.md .github/pull_request_template.md`).

### Implementation for User Story 6

- [X] T018 [P] [US6] Create `SECURITY.md` at repo root (~150-200 lines) — sections: Trust Model (single-operator, local execution, `claude -p` subprocess isolation), Secret Management (CLI-injected API keys, `.env` in `.gitignore`, zero secrets in repo), Vulnerability Reporting (contact, 48-72h response, 90-day disclosure), AI-Specific Security (tool allowlist, contract-based prompt injection mitigation, auto-review, circuit breaker), OWASP LLM Top 10 relevant items (prompt injection, output handling), Dependency Policy (stdlib + pyyaml, lock files committed). English per CLAUDE.md convention
- [X] T019 [P] [US6] Create `CONTRIBUTING.md` at repo root (~80 lines) — sections: PR Rules (one thing per PR, AI-generated code welcome but must be marked), Commit Conventions (`feat:`, `fix:`, `chore:`, `merge:` — English), Before-you-PR Checklist (`make test && make lint && make ruff`), Skill Editing Policy (always via `/madruga:skills-mgmt`, never direct edits), AI Code Review (same rigor as human code). English per CLAUDE.md convention
- [X] T020 [P] [US6] Create `.github/pull_request_template.md` (~25 lines) — sections: Summary (free text), Change Type (checkboxes: Bug fix, Feature, Refactor, Docs, AI infrastructure), Security Impact (checkboxes: Handles user input, Modifies auth/permissions, Changes secret handling, Modifies AI instruction files), Test Plan (free text), Risks and Mitigations (free text)

**Checkpoint**: All 3 governance files exist. GitHub will recognize them after merge to main.

---

## Phase 9: User Story 7 - Documentation-Change Matrix (Priority: P3)

**Goal**: Add a reference table to CLAUDE.md mapping change types to required documentation updates.

**Independent Test**: `grep "Documentation-Change Matrix" CLAUDE.md` returns a match.

### Implementation for User Story 7

- [X] T021 [US7] Add `## Documentation-Change Matrix` section to `CLAUDE.md` — table with 5 rows: (1) New skill (`.claude/commands/`) → update `pipeline-dag-knowledge.md`, `CLAUDE.md` skills list; (2) New script (`.specify/scripts/`) → update `CLAUDE.md` Essential commands; (3) New migration (`.pipeline/migrations/`) → update `CLAUDE.md` Active Technologies; (4) New platform (`platforms/`) → update portal `LikeC4Diagram.tsx` (platformLoaders); (5) New knowledge file (`.claude/knowledge/`) → update `platform.yaml` knowledge section. Insert after "## Gotchas" section

**Checkpoint**: CLAUDE.md contains documentation-change matrix.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all user stories.

- [X] T022 Run `make test` and fix any failures across all new code
- [X] T023 Run `make ruff` and fix any lint/format issues in `.specify/scripts/skill-lint.py` and `.specify/scripts/tests/test_skill_lint.py`
- [X] T024 Run quickstart.md verification commands — validate T3 impact analysis output, T6 knowledge declarations, governance file existence
- [X] T025 Run `python3 .specify/scripts/post_save.py --platform madruga-ai --node specify --skill speckit.tasks --artifact platforms/madruga-ai/epics/019-ai-infra-as-code/tasks.md --epic 019-ai-infra-as-code` to register artifact in DB

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: No dependencies — `build_knowledge_graph()` is the core building block
- **Phase 3 (US3)**: Depends on Phase 2 — uses `build_knowledge_graph()`
- **Phase 4 (US1)**: No dependencies — CODEOWNERS is a standalone file
- **Phase 5 (US2)**: No dependencies — CI YAML only
- **Phase 6 (US4)**: Depends on Phase 3 — CI gate uses `--impact-of`
- **Phase 7 (US5)**: Depends on Phase 2 — reuses `build_knowledge_graph()`
- **Phase 8 (US6)**: No dependencies — standalone file creation
- **Phase 9 (US7)**: No dependencies — CLAUDE.md edit
- **Phase 10 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (P1)**: Independent — can start after Phase 2 or in parallel with it
- **US2 (P1)**: Independent — can start after Phase 2 or in parallel with it
- **US3 (P1)**: Depends on Phase 2 (`build_knowledge_graph`) — BLOCKS US4 and US5
- **US4 (P2)**: Depends on US3 (`--impact-of` flag must exist)
- **US5 (P2)**: Depends on Phase 2 (`build_knowledge_graph`) — can run in parallel with US3/US4
- **US6 (P2)**: Independent — all file creation, no code dependencies
- **US7 (P3)**: Independent — CLAUDE.md edit only

### Within Each User Story

- Tests written FIRST, verified to fail before implementation
- Core functions before CLI integration
- Implementation before CI integration

### Parallel Opportunities

- **Phase 2 tasks**: T001, T002 are sequential (function then test)
- **Phase 3**: T003, T004 can run in parallel (separate test functions)
- **Phase 4 + Phase 5 + Phase 8 + Phase 9**: All can run in parallel with each other (different files, no dependencies)
- **Phase 7 tests**: T010, T011, T012, T013 can all run in parallel
- **Phase 8**: T018, T019, T020 can all run in parallel (different files)
- **Phase 10**: T022, T023 sequential; T024 after both pass

---

## Parallel Example: Phases 4 + 5 + 8 + 9

```bash
# After Phase 2+3 are complete, launch these in parallel:
Task: T007 [US1] Create .github/CODEOWNERS
Task: T008 [US2] Add security-scan job to .github/workflows/ci.yml
Task: T018 [US6] Create SECURITY.md
Task: T019 [US6] Create CONTRIBUTING.md
Task: T020 [US6] Create .github/pull_request_template.md
Task: T021 [US7] Add documentation-change matrix to CLAUDE.md
```

## Parallel Example: Phase 7 Tests

```bash
# All test functions target the same file but are independent:
Task: T010 [US5] test_lint_knowledge_declarations_valid
Task: T011 [US5] test_lint_knowledge_declarations_missing_file
Task: T012 [US5] test_lint_knowledge_declarations_undeclared_ref
Task: T013 [US5] test_all_pipeline_resolution
```

---

## Implementation Strategy

### MVP First (P1 User Stories Only)

1. Complete Phase 2: Foundational (`build_knowledge_graph`)
2. Complete Phase 3: US3 (Impact Analysis)
3. Complete Phase 4: US1 (CODEOWNERS)
4. Complete Phase 5: US2 (Security Scan CI)
5. **STOP and VALIDATE**: `make test && make ruff`, verify `--impact-of` output
6. P1 stories deliver: code owner review, security scanning, impact analysis

### Incremental Delivery

1. Phase 2 + 3 → Impact analysis works (`--impact-of`) → Core value delivered
2. Phase 4 + 5 → CODEOWNERS + security scan → Governance baseline
3. Phase 6 → CI gate → Automated enforcement
4. Phase 7 → Knowledge declarations → Explicit dependency tracking
5. Phase 8 → Governance docs → Contributor onboarding
6. Phase 9 → Doc-change matrix → Drift prevention reference
7. Phase 10 → Polish → All checks pass

### Critical Path

```
T001 → T002 → T005 → T006 → T009 (CI gate depends on --impact-of)
                  ↓
            T014 → T015 → T016 (knowledge declarations reuse build_knowledge_graph)
```

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- `skill-lint.py` changes: ~80-100 LOC added (T001 + T005 + T006 + T014 + T015)
- Governance docs (T18-T20): English per CLAUDE.md convention
- Knowledge declarations: WARNING severity only, never BLOCKER (backward compat)
- Security scan: simple regex, no external tools (per research.md R2 decision)
- All CI jobs use existing `actions/checkout@v4` and `actions/setup-python@v5`
