### T001 — DONE
- Verify `claude -p --output-format json` actual output fields by running a test dispatch and inspecting stdout JSON structure (document in `platforms/madruga-ai/epics/021-pipeline-intelligence/research
- Files: platforms/madruga-ai/epics/021-pipeline-intelligence/research.md
- Tokens in/out: 15/7295

### T002 — DONE
- Reviewed test_dag_executor.py (1498 LOC, ~55 tests) + conftest.py
- Files: .specify/scripts/tests/test_dag_executor.py, .specify/scripts/tests/conftest.py
- Tokens in/out: N/A (read-only review)

### T002 — DONE
- Review existing test coverage in `.specify/scripts/tests/test_dag_executor.py` to understand test patterns and fixtures already available
- Files: .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 13/2766

### T003 — DONE
- [P] [US1] Write test for `parse_claude_output()` with real claude JSON output in `.specify/scripts/tests/test_cost_tracking.py` — test correct field extraction, missing fields, malformed JSON, empty s
- Files: .specify/scripts/tests/test_cost_tracking.py
- Tokens in/out: 13/6414

### T004 — DONE
- [P] [US1] Write test verifying `complete_run()` updates metric columns in `.specify/scripts/tests/test_cost_tracking.py` — mock DB, assert UPDATE includes tokens_in/out/cost_usd/duration_ms
- Files: .specify/scripts/tests/test_cost_tracking.py
- Tokens in/out: 32/9189

### T005 — DONE
- [US1] Update `parse_claude_output()` in `.specify/scripts/dag_executor.py` to match actual `claude -p --output-format json` field names (based on T001 findings) — adjust `usage.input_tokens` → correct
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 7/864

### T006 — DONE
- [US1] Add `cost_usd` calculation if not provided by claude output — compute from token counts using model pricing in `.specify/scripts/dag_executor.py` (fallback: `tokens_in * 0.003/1000 + tokens_out 
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 17/4018

### T007 — DONE
- [US1] Verify portal "Cost" tab in `portal/` renders data from populated `pipeline_runs` rows — confirm React components from epic 017 read `cost_usd` column correctly (read-only check, no code change 
- Tokens in/out: 7/1911

### T008 — DONE
- [P] [US2] Write test for `_check_hallucination()` function in `.specify/scripts/tests/test_hallucination_guard.py` — test zero tool calls → True, nonzero → False, malformed JSON → False, missing field
- Files: .specify/scripts/tests/test_hallucination_guard.py
- Tokens in/out: 13/4516

### T009 — DONE
- [P] [US2] Write test verifying hallucination check is called after dispatch in `.specify/scripts/tests/test_hallucination_guard.py` — mock dispatch returning zero-tool-call JSON, assert warning logged
- Files: .specify/scripts/tests/test_hallucination_guard.py
- Tokens in/out: 19/5192

### T010 — DONE
- [US2] Add `_check_hallucination(stdout: str) -> bool` function to `.specify/scripts/dag_executor.py` — parse JSON, check `tool_use_count` or equivalent field from claude output, return True if zero to
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 10/1734

### T011 — DONE
- [US2] Integrate hallucination check in sync execution loop at `.specify/scripts/dag_executor.py` (after line ~1302 where `metrics = parse_claude_output(stdout)`) — call `_check_hallucination(stdout)`,
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 14/2618

### T012 — DONE
- [US2] Integrate hallucination check in async execution loop at `.specify/scripts/dag_executor.py` (after line ~1812) — same pattern as T011
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 13/3476

### T013 — DONE
- [US2] Add hallucination guard to Tier 1 auto-review table in `.claude/knowledge/pipeline-contract-base.md` — add row 0: "Agent made at least 1 tool call during generation?" with action "WARNING — outp
- Files: .claude/knowledge/pipeline-contract-base.md
- Tokens in/out: 7/1123

### T014 — DONE
- [P] [US3] Write test for `--quick` DAG parsing in `.specify/scripts/tests/test_dag_executor.py` — verify `parse_dag()` or equivalent returns only 3 nodes (specify, implement, judge) when `mode="quick"
- Files: .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 13/3899

### T015 — DONE
- [P] [US3] Write test for quick-fix node dependencies in `.specify/scripts/tests/test_dag_executor.py` — verify implement depends on specify, judge depends on implement
- Files: .specify/scripts/tests/test_dag_executor.py
- Tokens in/out: 8/2000

### T016 — DONE
- [US3] Create `/quick-fix` skill markdown at `.claude/commands/madruga/quick-fix.md` (~80–120 LOC) — frontmatter with `gate: human`, persona as pragmatic engineer, instructions to collect bug descripti
- Files: .claude/commands/madruga/quick-fix.md
- Tokens in/out: 595/5316

### T017 — DONE
- [US3] Add `quick_cycle` node list to `platforms/madruga-ai/platform.yaml` under `pipeline.epic_cycle` — 3 nodes: specify (gate: human), implement (gate: auto), judge (gate: auto-escalate) with correct
- Files: platforms/madruga-ai/platform.yaml
- Tokens in/out: 7/971

### T018 — DONE
- [US3] Add `--quick` CLI flag to argparse in `.specify/scripts/dag_executor.py` — new argument `--quick` (boolean flag), passed through to DAG loading
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 22/4114

### T019 — DONE
- [US3] Implement quick mode DAG loading in `.specify/scripts/dag_executor.py` — when `--quick` is set, read `quick_cycle` nodes from platform.yaml instead of `epic_cycle`, build reduced DAG with only s
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 8/1401

### T020 — DONE
- [US3] Update `build_dispatch_cmd()` in `.specify/scripts/dag_executor.py` to pass quick-fix context in system prompt when `--quick` mode is active — inform the skill it's in fast-lane mode, scope rest
- Files: .specify/scripts/dag_executor.py
- Tokens in/out: 23/5532

### T021 — DONE
- [US4] Add `roadmap-reassess` optional node to `platforms/madruga-ai/platform.yaml` under `pipeline.epic_cycle.nodes` — id: roadmap-reassess, skill: madruga:roadmap, depends: [reconcile], gate: auto, o
- Files: platforms/madruga-ai/platform.yaml, pipeline.epic_cycle.nodes
- Tokens in/out: 14/1991

### T022 — DONE
- [US4] Document `roadmap-reassess` node in `.claude/knowledge/pipeline-dag-knowledge.md` — add row to L2 table (step 12), explain optional behavior and skip condition
- Files: .claude/knowledge/pipeline-dag-knowledge.md
- Tokens in/out: 9/1249

### T023 — DONE
- [US4] Verify `dag_executor.py` handles `skip_condition` and `optional: true` correctly for the new node — trace existing skip_condition logic to confirm "epic.appetite <= '2w'" pattern is supported (m
- Files: dag_executor.py
- Tokens in/out: 6/1724

### T024 — DONE
- [P] Run `make test` — all existing + new tests pass
- Tokens in/out: 7/494

### T025 — DONE
- [P] Run `make ruff` — no lint errors in modified files
- Tokens in/out: 6/215

### T026 — DONE
- [P] Run `python3 .specify/scripts/skill-lint.py --skill madruga:quick-fix` — validate new skill frontmatter and structure
- Tokens in/out: 20/2632

### T027 — DONE
- Verify `python3 .specify/scripts/platform_cli.py lint madruga-ai` passes — platform YAML valid with new nodes
- Tokens in/out: 10/1064

### T028 — DONE
- Update `platforms/madruga-ai/epics/021-pipeline-intelligence/pitch.md` acceptance criteria checkboxes based on implementation status
- Files: platforms/madruga-ai/epics/021-pipeline-intelligence/pitch.md
- Tokens in/out: 13/1835

