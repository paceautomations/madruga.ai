### T001 — DONE
- Create migration file `.pipeline/migrations/014_commits.sql` with CREATE TABLE commits (id, sha UNIQUE, message, author, platform_id, epic_id nullable, source DEFAULT 'hook', committed_at, files_json,
- Files: .pipeline/migrations/014_commits.sql
- Tokens in/out: 9/1930

### T002 — DONE
- Verify migration applies cleanly by running `python3 -c "from .specify.scripts.db_core import migrate; migrate()"` against a fresh DB copy
- Tokens in/out: 9/3371

### T003 — DONE
- [P] Write tests for `insert_commit()` in `.specify/scripts/tests/test_db_pipeline.py` — test single insert, duplicate SHA (INSERT OR IGNORE), multi-platform commit creates multiple rows, NULL epic_id 
- Files: .specify/scripts/tests/test_db_pipeline.py
- Tokens in/out: 10/3869

### T004 — DONE
- [P] Write tests for query functions in `.specify/scripts/tests/test_db_pipeline.py` — `get_commits_by_epic()` returns correct commits, `get_commits_by_platform()` filters by platform, `get_adhoc_commi
- Files: .specify/scripts/tests/test_db_pipeline.py
- Tokens in/out: 11/4739

### T005 — DONE
- Implement `insert_commit(conn, sha, message, author, platform_id, epic_id, source, committed_at, files_json)` in `.specify/scripts/db_pipeline.py` — uses INSERT OR IGNORE for idempotency, files_json s
- Files: .specify/scripts/db_pipeline.py
- Tokens in/out: 17/3191

### T006 — DONE
- Implement `get_commits_by_epic(conn, epic_id, platform_id=None)` in `.specify/scripts/db_pipeline.py` — returns list of dicts ordered by committed_at DESC
- Files: .specify/scripts/db_pipeline.py
- Tokens in/out: 13/2368

### T007 — DONE
- [P] Implement `get_commits_by_platform(conn, platform_id, limit=100, offset=0)` in `.specify/scripts/db_pipeline.py` — paginated, ordered by committed_at DESC
- Files: .specify/scripts/db_pipeline.py
- Tokens in/out: 11/2098

### T008 — DONE
- [P] Implement `get_adhoc_commits(conn, platform_id=None, limit=100)` in `.specify/scripts/db_pipeline.py` — WHERE epic_id IS NULL, optional platform filter
- Files: .specify/scripts/db_pipeline.py
- Tokens in/out: 13/2286

### T009 — DONE
- Run tests from T003-T004 and verify all pass (Red→Green)
- Tokens in/out: 6/998

### T010 — DONE
- [P] [US1] Write integration test in `.specify/scripts/tests/test_db_pipeline.py` — insert 5 commits (3 for epic-012, 2 ad-hoc), verify `get_commits_by_epic('012-...')` returns exactly 3, verify `get_a
- Files: .specify/scripts/tests/test_db_pipeline.py
- Tokens in/out: 9/2331

### T011 — DONE
- [P] [US1] Write integration test for empty epic query in `.specify/scripts/tests/test_db_pipeline.py` — query non-existent epic returns empty list without error
- Files: .specify/scripts/tests/test_db_pipeline.py
- Tokens in/out: 7/1731

### T012 — DONE
- [US1] Add `get_commit_stats(conn, platform_id=None)` in `.specify/scripts/db_pipeline.py` — returns dict with total_commits, commits_per_epic (dict), adhoc_count, adhoc_percentage for portal stats (FR
- Files: .specify/scripts/db_pipeline.py
- Tokens in/out: 9/1722

### T013 — DONE
- [US1] Run tests from T010-T011 and verify all pass
- Tokens in/out: 4/440

### T014 — DONE
- [P] [US2] Write tests for platform detection logic in `.specify/scripts/tests/test_hook_post_commit.py` — branch `epic/prosauai/007-foo` → platform `prosauai`; file paths `platforms/prosauai/x.md` → p
- Files: .specify/scripts/tests/test_hook_post_commit.py, platforms/prosauai/x.md
- Tokens in/out: 10/2968

### T015 — DONE
- [P] [US2] Write tests for epic detection logic in `.specify/scripts/tests/test_hook_post_commit.py` — branch `epic/madruga-ai/023-commit-traceability` → epic `023-commit-traceability`; tag `[epic:015]
- Files: .specify/scripts/tests/test_hook_post_commit.py
- Tokens in/out: 8/2502

### T016 — DONE
- [P] [US2] Write tests for multi-platform commit handling in `.specify/scripts/tests/test_hook_post_commit.py` — commit touching `platforms/X/` and `platforms/Y/` generates 2 rows, one per platform
- Files: .specify/scripts/tests/test_hook_post_commit.py
- Tokens in/out: 13/3551

### T017 — DONE
- [P] [US2] Write test for hook error handling in `.specify/scripts/tests/test_hook_post_commit.py` — DB failure (locked, missing) does not raise exception, logs to stderr
- Files: .specify/scripts/tests/test_hook_post_commit.py
- Tokens in/out: 8/2686

### T018 — DONE
- [US2] Create `.specify/scripts/hook_post_commit.py` with `parse_branch(branch_name)` function that returns `(platform_id, epic_id)` tuple from branch pattern `epic/<platform>/<NNN-slug>`
- Files: .specify/scripts/hook_post_commit.py
- Tokens in/out: 7/1795

### T019 — DONE
- [US2] Add `detect_platforms_from_files(file_list)` function in `.specify/scripts/hook_post_commit.py` — scans file paths for `platforms/<X>/` pattern, returns set of platform_ids, fallback `madruga-ai
- Files: .specify/scripts/hook_post_commit.py
- Tokens in/out: 8/1614

### T020 — DONE
- [US2] Add `parse_epic_tag(message)` function in `.specify/scripts/hook_post_commit.py` — extracts `[epic:NNN]` tag from commit message, returns epic slug or None
- Files: .specify/scripts/hook_post_commit.py
- Tokens in/out: 8/1403

### T021 — DONE
- [US2] Add `get_head_info()` function in `.specify/scripts/hook_post_commit.py` — runs `git log -1 --format=%H%n%s%n%an%n%aI` and `git diff-tree --no-commit-id --name-only -r HEAD` via subprocess, retu
- Files: .specify/scripts/hook_post_commit.py
- Tokens in/out: 10/2169

### T022 — DONE
- [US2] Implement `main()` in `.specify/scripts/hook_post_commit.py` — orchestrates: get_head_info → parse_branch → detect_platforms → parse_epic_tag → insert_commit per platform; wrap in try/except for
- Files: .specify/scripts/hook_post_commit.py
- Tokens in/out: 12/2622

### T023 — DONE
- [US2] Create installable hook script at `.specify/scripts/git-hooks/post-commit` (shell wrapper that calls `python3 .specify/scripts/hook_post_commit.py`)
- Tokens in/out: 7/1011

### T024 — DONE
- [US2] Add `install-hooks` target in `Makefile` — copies `.specify/scripts/git-hooks/post-commit` to `.git/hooks/post-commit` and sets executable permission
- Tokens in/out: 9/1220

### T025 — DONE
- [US2] Run tests from T014-T017 and verify all pass
- Tokens in/out: 4/552

### T026 — DONE
- [P] [US3] Create JSON export function `export_commits_json(output_path)` in `.specify/scripts/post_save.py` — queries all commits from DB, writes to `portal/src/data/commits-status.json` with structur
- Files: .specify/scripts/post_save.py, portal/src/data/commits-status.json
- Tokens in/out: 17/3748

### T027 — DONE
- [P] [US3] Write test for `export_commits_json()` in `.specify/scripts/tests/test_post_save.py` — verify JSON structure, verify empty DB produces valid empty JSON
- Files: .specify/scripts/tests/test_post_save.py
- Tokens in/out: 12/3311

### T028 — DONE
- [US3] Integrate `export_commits_json()` call into `_refresh_portal_status()` in `.specify/scripts/post_save.py` — called alongside existing pipeline-status.json export
- Files: .specify/scripts/post_save.py
- Tokens in/out: 8/953

### T029 — DONE
- [US3] Create `portal/src/components/changes/ChangesTab.tsx` — React component with: table (SHA as GitHub link, message, platform, epic/"ad-hoc", date), client-side filters (platform, epic, type, date 
- Files: portal/src/components/changes/ChangesTab.tsx
- Tokens in/out: 19/7268

### T030 — DONE
- [US3] Add "Changes" tab button and panel to `portal/src/pages/[platform]/control-panel.astro` — new tab button with `data-tab="changes"`, new panel div importing `ChangesTab` with `client:visible`, up
- Tokens in/out: 10/2574

### T031 — DONE
- [US3] Update `make status-json` target in `Makefile` to also generate `commits-status.json`
- Files: commits-status.json
- Tokens in/out: 8/1098

### T032 — DONE
- [P] [US4] Write tests for merge-based epic detection in `.specify/scripts/tests/test_backfill_commits.py` — mock `git log --merges` output, verify epic extraction from merge commit messages referencin
- Files: .specify/scripts/tests/test_backfill_commits.py
- Tokens in/out: 16/6365

### T033 — DONE
- [P] [US4] Write test for pre-006 commit classification in `.specify/scripts/tests/test_backfill_commits.py` — commits in range 5f62946..d6befe0 are linked to epic `001-inicio-de-tudo`
- Files: .specify/scripts/tests/test_backfill_commits.py
- Tokens in/out: 12/3907

### T034 — DONE
- [P] [US4] Write test for idempotency in `.specify/scripts/tests/test_backfill_commits.py` — run backfill twice, verify zero duplicate rows (count unchanged)
- Files: .specify/scripts/tests/test_backfill_commits.py
- Tokens in/out: 12/4840

### T035 — DONE
- [US4] Create `.specify/scripts/backfill_commits.py` with `get_merge_commits()` function — runs `git log main --merges --format=%H%n%s%n%P` to identify merge commits from epic branches
- Files: .specify/scripts/backfill_commits.py
- Tokens in/out: 10/2925

### T036 — DONE
- [US4] Add `get_epic_commits_from_merge(merge_sha)` function in `.specify/scripts/backfill_commits.py` — runs `git log <merge>^..<merge> --format=%H%n%s%n%an%n%aI` and `git diff-tree --no-commit-id --n
- Files: .specify/scripts/backfill_commits.py
- Tokens in/out: 12/2269

### T037 — DONE
- [US4] Add `get_direct_main_commits()` function in `.specify/scripts/backfill_commits.py` — runs `git log --no-merges --first-parent main --format=%H%n%s%n%an%n%aI` for ad-hoc commits
- Files: .specify/scripts/backfill_commits.py
- Tokens in/out: 14/2570

### T038 — DONE
- [US4] Add `classify_pre006(sha, cutoff_sha='d6befe0')` function in `.specify/scripts/backfill_commits.py` — returns epic `001-inicio-de-tudo` for commits before cutoff, None otherwise
- Files: .specify/scripts/backfill_commits.py
- Tokens in/out: 21/3865

### T039 — DONE
- [US4] Implement `main()` in `.specify/scripts/backfill_commits.py` with argparse — orchestrates: merge commits → epic commits → direct main commits → classify_pre006 → insert_commit per entry; uses IN
- Files: .specify/scripts/backfill_commits.py
- Tokens in/out: 13/4216

### T040 — DONE
- [US4] Run tests from T032-T034 and verify all pass
- Tokens in/out: 6/804

### T041 — DONE
- [P] [US5] Write test for reseed commit sync in `.specify/scripts/tests/test_post_save.py` — insert 3 commits, delete 1, run reseed, verify all 3 present again
- Files: .specify/scripts/tests/test_post_save.py
- Tokens in/out: 15/4043

### T042 — DONE
- [P] [US5] Write test for reseed idempotency in `.specify/scripts/tests/test_post_save.py` — reseed with all commits present, verify no duplicates or errors
- Files: .specify/scripts/tests/test_post_save.py
- Tokens in/out: 9/4543

### T043 — DONE
- [US5] Add `sync_commits(conn, platform_id)` function in `.specify/scripts/post_save.py` — runs `git log --format=%H%n%s%n%an%n%aI` + file detection, calls `insert_commit()` for each (INSERT OR IGNORE 
- Files: .specify/scripts/post_save.py
- Tokens in/out: 14/5697

### T044 — DONE
- [US5] Integrate `sync_commits()` into the `reseed(platform)` function in `.specify/scripts/post_save.py` — called after existing node seeding, reuses platform detection logic from hook
- Files: .specify/scripts/post_save.py
- Tokens in/out: 9/1571

### T045 — DONE
- [US5] Run tests from T041-T042 and verify all pass
- Tokens in/out: 4/481

### T046 — DONE
- [P] Verify hook performance — time execution of `hook_post_commit.py` on 3 sample commits, confirm <500ms (FR-017)
- Files: hook_post_commit.py
- Tokens in/out: 9/3333

### T047 — DONE
- [P] Add `install-hooks` instructions to repository README or Makefile help target
- Tokens in/out: 17/2778

### T048 — DONE
- Run `make ruff` and fix any linting issues in new files (hook_post_commit.py, backfill_commits.py)
- Tokens in/out: 11/2396

### T050 — DONE
- Execute backfill against real repository and verify epic 001 has 21 commits linked (SC-003)
- Tokens in/out: 10/2185

