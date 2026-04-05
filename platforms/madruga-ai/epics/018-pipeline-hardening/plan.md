# Implementation Plan: Pipeline Hardening & Safety

**Branch**: `epic/madruga-ai/018-pipeline-hardening` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/018-pipeline-hardening/spec.md`

## Summary

Harden the DAG pipeline executor and supporting scripts by replacing manual `conn.close()` with context managers, adding fail-closed gate validation, enforcing a dispatch circuit breaker per skill, sanitizing all user-provided paths/names, validating DAG inputs via dataclasses, introducing a typed error hierarchy, and handling SIGINT for graceful shutdown. All changes target 4 existing Python scripts (dag_executor, ensure_repo, platform_cli, post_save) plus one new `errors.py` module (~30 LOC).

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only + pyyaml)
**Primary Dependencies**: pyyaml (only external dep), sqlite3 (stdlib), subprocess, signal, dataclasses
**Storage**: SQLite WAL mode (`.pipeline/madruga.db`) via `db.py` — `_ClosingConnection` context manager already implemented
**Testing**: pytest (`make test` — 43+ existing test files in `.specify/scripts/tests/`)
**Target Platform**: Linux (WSL2), CLI tooling
**Project Type**: CLI pipeline executor / internal tooling
**Performance Goals**: N/A — correctness and safety focus
**Constraints**: stdlib-only (no Pydantic), no SQLite schema changes, no portal/skill changes
**Scale/Scope**: 4 scripts modified (~3,200 LOC total), 1 new module (~30 LOC), ~90 LOC new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Pragmatism Above All | PASS | Applying proven patterns (context managers, dataclasses, signal handlers) — no new abstractions |
| II | Automate Repetitive Tasks | PASS | Automating safety checks that were previously manual/missing |
| III | Structured Knowledge | PASS | Error hierarchy makes failures self-documenting |
| IV | Fast Action | PASS | 7 well-defined tasks, all mechanical — no design decisions needed |
| V | Alternatives & Trade-offs | PASS | Key decision (dataclasses vs Pydantic) already resolved in ADR — stdlib only |
| VI | Brutal Honesty | PASS | Pitch accurately identifies real bugs (gate typo, conn leaks, no SIGINT) |
| VII | TDD | PASS | New tests for validation/security/errors; existing 43+ tests must stay green |
| VIII | Collaborative Decision | PASS | No architectural decisions — applying established patterns |
| IX | Observability & Logging | PASS | Gate validation logs warnings; error hierarchy enables structured error reporting |

**Gate result: PASS** — No violations. All changes are mechanical application of proven patterns.

## Project Structure

### Documentation (this feature)

```text
platforms/madruga-ai/epics/018-pipeline-hardening/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── spec.md              # Feature specification
└── checklists/          # Epic checklists
```

### Source Code (repository root)

```text
.specify/scripts/
├── errors.py                    # NEW: typed error hierarchy (~30 LOC)
├── dag_executor.py              # MODIFY: T1+T2+T3+T5+T7 (1,649 LOC)
├── ensure_repo.py               # MODIFY: T4b+T6 (161 LOC)
├── platform_cli.py              # MODIFY: T4a+T6 (889 LOC)
├── post_save.py                 # MODIFY: T6 (506 LOC)
├── db.py                        # READ-ONLY: _ClosingConnection reference
└── tests/
    ├── test_dag_executor.py     # MODIFY: add gate validation + circuit breaker tests
    ├── test_platform.py         # MODIFY: add path security tests
    ├── test_errors.py           # NEW: error hierarchy tests (~50 LOC)
    └── test_path_security.py    # NEW: path traversal + injection tests (~40 LOC)
```

**Structure Decision**: No new directories or structural changes. All modifications are to existing scripts in `.specify/scripts/`. One new module (`errors.py`) and two new test files.
