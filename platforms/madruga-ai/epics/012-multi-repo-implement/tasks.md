# Tasks: Multi-repo Implement

**Input**: Design documents from `platforms/madruga-ai/epics/012-multi-repo-implement/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-commands.md

**Tests**: Included per constitution principle VII (TDD).

**Organization**: Tasks grouped by user story. US1-US3 are P1 (critical path), US4 is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)
- Exact file paths included

---

## Phase 1: Setup

**Purpose**: Create file structure for new scripts

- [x] T001 Create empty script files with docstrings and `if __name__` boilerplate: `.specify/scripts/ensure_repo.py`, `.specify/scripts/worktree.py`, `.specify/scripts/implement_remote.py`
- [x] T002 [P] Create empty test files: `tests/test_ensure_repo.py`, `tests/test_worktree.py`, `tests/test_implement_remote.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared utilities that all user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add helper `_load_repo_binding(name: str) -> dict` in `.specify/scripts/ensure_repo.py` that reads `platforms/<name>/platform.yaml` and returns `{org, name, base_branch, epic_branch_prefix}` with validation (error if `repo:` block missing). Use `yaml.safe_load` + `pathlib.Path`.
- [x] T004 [P] Add helper `_is_self_ref(repo_name: str) -> bool` in `.specify/scripts/ensure_repo.py` that returns `True` if `repo_name == "madruga.ai"`. Returns current repo root path via `REPO_ROOT = Path(__file__).resolve().parents[2]`.
- [x] T005 [P] Add helper `_resolve_repos_base() -> Path` in `.specify/scripts/ensure_repo.py` that reads `repos_base_dir` from `local_config` table in DB (via `db.get_local_config`), defaults to `Path.home() / "repos"`. Wrap DB access in try/except so ensure_repo works even if DB is not initialized (fallback to default directly). Expand user.
- [x] T006 [P] Configure `logging.getLogger(__name__)` in all three new scripts with format: `%(levelname)s: %(message)s`. Accept `-v` flag for DEBUG level.

**Checkpoint**: Foundation ready — shared helpers available for all stories

---

## Phase 3: User Story 1 — Clonar Repositorio Externo (Priority: P1) MVP

**Goal**: `platform.py ensure-repo <name>` clona ou atualiza repositorio externo automaticamente

**Independent Test**: `python3 .specify/scripts/platform.py ensure-repo prosauai` → repo existe em `~/repos/paceautomations/prosauai-api/`

### Tests for User Story 1

- [x] T007 [P] [US1] Write test `test_self_ref_returns_repo_root` in `tests/test_ensure_repo.py` — verify self-ref detection returns REPO_ROOT without calling git
- [x] T008 [P] [US1] Write test `test_clone_ssh_success` in `tests/test_ensure_repo.py` — mock `subprocess.run` for `git clone git@github.com:org/name.git`, verify called with correct args and path
- [x] T009 [P] [US1] Write test `test_clone_ssh_fail_https_fallback` in `tests/test_ensure_repo.py` — mock SSH clone failing (returncode=128), verify HTTPS retry `https://github.com/org/name.git`
- [x] T010 [P] [US1] Write test `test_existing_repo_fetches` in `tests/test_ensure_repo.py` — create temp dir with `.git/`, verify `git fetch --all --prune` called instead of clone
- [x] T011 [P] [US1] Write test `test_partial_clone_reclones` in `tests/test_ensure_repo.py` — create temp dir without `.git/`, verify dir removed and clone executed
- [x] T012 [P] [US1] Write test `test_locking_creates_lockfile` in `tests/test_ensure_repo.py` — verify `fcntl.flock` called on `{path}.lock` file

### Implementation for User Story 1

- [x] T013 [US1] Implement `ensure_repo(platform_name: str) -> Path` in `.specify/scripts/ensure_repo.py` — full flow per contract: load binding → self-ref check → resolve path → validate `.git` → clone SSH/HTTPS or fetch → locking via `fcntl.flock` → return path. Log each step at INFO.
- [x] T014 [US1] Add `ensure-repo` subcommand to `.specify/scripts/platform.py` — add parser `sub.add_parser("ensure-repo", ...)` with `name` argument, implement `cmd_ensure_repo(name)` that calls `ensure_repo.ensure_repo(name)` and prints the resulting path
- [x] T015 [US1] Run tests for US1 and verify all pass

**Checkpoint**: `platform.py ensure-repo prosauai` works end-to-end

---

## Phase 4: User Story 2 — Criar Worktree para Epic (Priority: P1)

**Goal**: `platform.py worktree <name> <epic>` cria worktree isolado com branch correta

**Independent Test**: `python3 .specify/scripts/platform.py worktree prosauai 001-channel-pipeline` → worktree exists with correct branch

### Tests for User Story 2

- [x] T016 [P] [US2] Write test `test_create_worktree_new_branch` in `tests/test_worktree.py` — mock `subprocess.run`, verify `git worktree add {path} -b {branch} origin/{base}` called with correct paths
- [x] T017 [P] [US2] Write test `test_reuse_existing_worktree` in `tests/test_worktree.py` — create temp worktree dir, verify function returns path without calling git worktree add
- [x] T018 [P] [US2] Write test `test_cleanup_worktree` in `tests/test_worktree.py` — verify `git worktree remove` + `git branch -d` called in sequence
- [x] T019 [P] [US2] Write test `test_self_ref_skips_worktree` in `tests/test_worktree.py` — verify self-ref platform returns REPO_ROOT without creating worktree
- [x] T020 [P] [US2] Write test `test_branch_already_on_remote` in `tests/test_worktree.py` — mock `git branch -r` showing remote branch exists, verify `git worktree add {path} {branch}` (without -b)

### Implementation for User Story 2

- [x] T021 [US2] Implement `create_worktree(platform_name: str, epic_slug: str) -> Path` in `.specify/scripts/worktree.py` — load binding → self-ref check → ensure_repo (call US1) → resolve worktree path `{base}/{name}-worktrees/{slug}/` → check existing → `git fetch origin` → `git worktree add` (new or existing branch) → return path
- [x] T022 [US2] Implement `cleanup_worktree(platform_name: str, epic_slug: str) -> None` in `.specify/scripts/worktree.py` — resolve paths → `git worktree remove {path}` → `git branch -d {branch}` → remove dir if remaining
- [x] T023 [US2] Add `worktree` subcommand to `.specify/scripts/platform.py` — parser with `name` + `epic_slug` args, calls `worktree.create_worktree(name, slug)`, prints path
- [x] T024 [US2] Add `worktree-cleanup` subcommand to `.specify/scripts/platform.py` — parser with `name` + `epic_slug` args, calls `worktree.cleanup_worktree(name, slug)`
- [x] T025 [US2] Run tests for US2 and verify all pass

**Checkpoint**: `platform.py worktree prosauai 001-channel-pipeline` creates isolated worktree

---

## Phase 5: User Story 3 — Implementar em Repositorio Externo (Priority: P1)

**Goal**: `implement_remote.py --platform prosauai --epic 001-channel-pipeline` orquestra ensure → worktree → prompt → claude -p

**Independent Test**: Run with `--dry-run` and verify composed prompt contains spec+plan+tasks content

### Tests for User Story 3

- [x] T026 [P] [US3] Write test `test_compose_prompt_all_artifacts` in `tests/test_implement_remote.py` — create temp epic dir with context.md, spec.md, plan.md, tasks.md, verify prompt contains all 4 with headers in correct order
- [x] T027 [P] [US3] Write test `test_compose_prompt_missing_optional` in `tests/test_implement_remote.py` — create temp dir without context.md, verify prompt still works with spec+plan+tasks
- [x] T028 [P] [US3] Write test `test_compose_prompt_truncates_large_context` in `tests/test_implement_remote.py` — create context.md > 100KB, verify truncated while spec+plan+tasks preserved
- [x] T029 [P] [US3] Write test `test_invoke_claude_correct_args` in `tests/test_implement_remote.py` — mock subprocess.run, verify `claude -p` called with `--cwd={worktree_path}` and prompt
- [x] T030 [P] [US3] Write test `test_timeout_returns_exit_3` in `tests/test_implement_remote.py` — mock subprocess.run raising TimeoutExpired, verify exit code 3
- [x] T031 [P] [US3] Write test `test_self_ref_skips_clone_worktree` in `tests/test_implement_remote.py` — verify self-ref platform invokes claude -p with cwd=REPO_ROOT

### Implementation for User Story 3

- [x] T032 [US3] Implement `compose_prompt(platform_name: str, epic_slug: str) -> str` in `.specify/scripts/implement_remote.py` — read artifacts from `platforms/<name>/epics/<slug>/` in order (context → spec → plan → tasks), add markdown headers, truncate context.md if total > 100KB
- [x] T033 [US3] Implement `run_implement(platform_name: str, epic_slug: str, timeout: int, dry_run: bool) -> int` in `.specify/scripts/implement_remote.py` — ensure_repo → create_worktree → compose_prompt → if dry_run print prompt and return 0 → else subprocess.run `claude -p` with --cwd and timeout → return exit code
- [x] T034 [US3] Add argparse CLI in `.specify/scripts/implement_remote.py` `__main__` block — `--platform`, `--epic`, `--timeout` (default from `MADRUGA_IMPLEMENT_TIMEOUT` env or 1800), `--dry-run` flag
- [x] T035 [US3] Run tests for US3 and verify all pass

**Checkpoint**: `implement_remote.py --platform prosauai --epic 001 --dry-run` shows composed prompt

---

## Phase 6: User Story 4 — Criar PR no Repositorio Externo (Priority: P2)

**Goal**: Push branch e criar PR no repositorio correto via `gh pr create`

**Independent Test**: After implementation commits exist in worktree, push + PR creation succeeds

### Tests for User Story 4

- [x] T036 [P] [US4] Write test `test_push_and_create_pr` in `tests/test_implement_remote.py` — mock subprocess.run, verify `git push -u origin {branch}` then `gh pr create --base {base_branch}` called with cwd=worktree
- [x] T037 [P] [US4] Write test `test_pr_already_exists` in `tests/test_implement_remote.py` — mock `gh pr create` failing with "already exists", verify function returns existing PR URL via `gh pr view --json url`
- [x] T038 [P] [US4] Write test `test_push_permission_error` in `tests/test_implement_remote.py` — mock git push failing, verify clear error message

### Implementation for User Story 4

- [x] T039 [US4] Implement `create_pr(worktree_path: Path, branch: str, base_branch: str, title: str) -> str` in `.specify/scripts/implement_remote.py` — `git push -u origin {branch}` with cwd=worktree → `gh pr create --base {base_branch} --title {title} --body "..."` → return PR URL. Handle existing PR (detect and return URL).
- [x] T040 [US4] Add `--create-pr` flag to `implement_remote.py` CLI — after successful claude -p, optionally push + create PR
- [x] T041 [US4] Run tests for US4 and verify all pass

**Checkpoint**: Full flow works: ensure → worktree → implement → PR

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration, docs, and final validation

- [x] T042 [P] Add ensure_repo, worktree, implement_remote to `.specify/scripts/` ruff config (if needed) and run `ruff check` + `ruff format` on all new files
- [x] T043 Run full integration test: `implement_remote.py --platform madruga-ai --epic 012-multi-repo-implement --dry-run` to verify self-ref path works end-to-end
- [x] T044 Run quickstart.md validation — execute each command from quickstart.md and verify outputs match
- [x] T045 Update `platforms/madruga-ai/epics/012-multi-repo-implement/plan.md` handoff section to reflect completion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1 Clone)**: Depends on Phase 2 — **MVP**
- **Phase 4 (US2 Worktree)**: Depends on Phase 3 (uses ensure_repo)
- **Phase 5 (US3 Implement)**: Depends on Phase 4 (uses create_worktree)
- **Phase 6 (US4 PR)**: Depends on Phase 5 (PR after implement)
- **Phase 7 (Polish)**: Depends on all prior phases

### User Story Dependencies

```
US1 (Clone) ← US2 (Worktree) ← US3 (Implement) ← US4 (PR)
```

Stories are sequential (each builds on the previous). This is inherent to the domain — you must clone before creating a worktree, worktree before implementing, implement before PR.

### Within Each User Story

- Tests written FIRST (Red)
- Implementation makes tests pass (Green)
- Verify checkpoint before next story

### Parallel Opportunities

- **Phase 1**: T001 and T002 in parallel
- **Phase 2**: T004, T005, T006 in parallel (after T003)
- **US1 Tests**: T007–T012 all in parallel
- **US2 Tests**: T016–T020 all in parallel
- **US3 Tests**: T026–T031 all in parallel
- **US4 Tests**: T036–T038 all in parallel
- **Phase 7**: T042 in parallel with T043

---

## Parallel Example: User Story 1

```bash
# Launch all tests in parallel:
Task: T007 "test_self_ref_returns_repo_root in tests/test_ensure_repo.py"
Task: T008 "test_clone_ssh_success in tests/test_ensure_repo.py"
Task: T009 "test_clone_ssh_fail_https_fallback in tests/test_ensure_repo.py"
Task: T010 "test_existing_repo_fetches in tests/test_ensure_repo.py"
Task: T011 "test_partial_clone_reclones in tests/test_ensure_repo.py"
Task: T012 "test_locking_creates_lockfile in tests/test_ensure_repo.py"

# Then implement (sequential):
Task: T013 "ensure_repo() in .specify/scripts/ensure_repo.py"
Task: T014 "ensure-repo subcommand in platform.py"
Task: T015 "Run and verify all US1 tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational helpers
3. Complete Phase 3: US1 — Clone repo
4. **STOP and VALIDATE**: `platform.py ensure-repo prosauai` works

### Incremental Delivery

1. Setup + Foundational → Helpers ready
2. US1 (Clone) → Test → **MVP: repos can be cloned**
3. US2 (Worktree) → Test → **Isolated epic environments**
4. US3 (Implement) → Test → **End-to-end remote implementation**
5. US4 (PR) → Test → **Full automation: implement + PR**
6. Polish → Final validation

### LOC Budget

| Script | Est. LOC | Actual LOC | Stories |
|--------|----------|------------|---------|
| ensure_repo.py | ~80 | 161 | US1 |
| worktree.py | ~60 | 177 | US2 |
| implement_remote.py | ~120 | 220 | US3, US4 |
| platform.py changes | ~40 | 46 | US1, US2 |
| **Total** | **~300** | **604** (~460 excl. CLI boilerplate) | NFR-003 compliant |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Sequential story dependency is domain-inherent (clone → worktree → implement → PR)
- Commit after each task or logical group
- `fcntl.flock` only works on Linux/macOS — acceptable per research.md R3
- Prompt size guard: truncate context.md first if > 100KB, never truncate tasks.md
