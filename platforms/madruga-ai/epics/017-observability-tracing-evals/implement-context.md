### T023 — DONE
- [US5] Add `cleanup_old_data(conn, days=90) -> dict` to `.specify/scripts/db.py` — 3 sequential DELETEs in single transaction per R6: eval_scores, pipeline_runs (WHERE trace_id IN stale traces), traces
- Files: .specify/scripts/db.py
- Tokens in/out: 7/519

### T024 — DONE
- [P] [US5] Create `.specify/scripts/observability_export.py` (~80 LOC) — `export_csv(conn, platform_id, entity, days) -> str` where entity is 'traces', 'spans', or 'evals'. Query appropriate table, wri
- Files: .specify/scripts/observability_export.py
- Tokens in/out: 6/1286

### T025 — DONE
- [US5] Add GET `/api/export/csv` endpoint to `.specify/scripts/daemon.py` per contracts/daemon-api.md. Requires `platform_id` and `entity` (traces|spans|evals), optional `days` (default 90). Returns te
- Files: .specify/scripts/daemon.py
- Tokens in/out: 9/1355

### T026 — DONE
- [US5] Add retention cleanup periodic task to `.specify/scripts/daemon.py` — `retention_cleanup(conn, shutdown_event, interval=86400)` in daemon TaskGroup. Calls db.cleanup_old_data(conn, days=90). Log
- Files: .specify/scripts/daemon.py
- Tokens in/out: 9/1057

### T027 — DONE
- [P] [US5] Write tests for CSV export in `.specify/scripts/tests/test_observability_export.py` — test export_csv for each entity type (traces, spans, evals): verify CSV headers match schema, rows match
- Files: .specify/scripts/tests/test_observability_export.py
- Tokens in/out: 8/2677

### T028 — DONE
- [US5] Add cleanup DB tests to `.specify/scripts/tests/test_db_observability.py` — test cleanup_old_data removes records older than 90 days, preserves recent records, returns correct deleted counts per
- Files: .specify/scripts/tests/test_db_observability.py
- Tokens in/out: 6/2585

### T029 — DONE
- Verify all edge cases from spec in relevant test files: interrupted pipeline run registers partial trace with status "cancelled", node without JSON output registers tokens/cost as NULL without impacti
- Tokens in/out: 23/7980

### T030 — DONE
- Run quickstart.md end-to-end validation: apply migration, start daemon, start portal, execute pipeline run, verify trace/spans/evals in DB and portal, export CSV, verify CORS
- Tokens in/out: 21/8869

