# Implementation Plan: Atomic Skills DAG Pipeline

**Branch**: `001-atomic-skills-dag-pipeline` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-atomic-skills-dag-pipeline/spec.md`

## Summary

Build 17 new skills + adapt 3 existing skills + create infrastructure (bash script, knowledge file, YAML schema, Copier templates) to enable incremental platform documentation via atomic skills orchestrated by a DAG declared in `platform.yaml`. Each skill follows a uniform 6-step contract (prerequisites → context+question → generate → auto-review → gate → save+report) and chains to the next via handoffs. Status is filesystem-derived (artifact exists = done). Four gate types control approval flow.

## Technical Context

**Language/Version**: Bash 5.x (script), Markdown (skills), YAML (schema), Python 3.11+ (YAML parsing in script)
**Primary Dependencies**: Claude Code custom commands system, `python3` with `pyyaml`, existing `.specify/scripts/bash/common.sh`
**Storage**: Filesystem only — artifacts are markdown/LikeC4 files, status derived from file existence
**Testing**: `bash -n` (syntax), `python3 -c yaml.safe_load` (YAML validity), grep (section presence), manual invocation (skill behavior)
**Target Platform**: Linux/macOS (WSL2 included) with Claude Code CLI
**Project Type**: Documentation tooling — Claude Code custom commands (`.md` prompts) + bash scripts + YAML configs
**Performance Goals**: N/A — skills are interactive prompt-based, not a service
**Constraints**: Each skill must be self-contained (no shared state between skills), filesystem is source of truth, skills must work both standalone (manual) and orchestrated (daemon future)
**Scale/Scope**: 14 DAG nodes, 20 skills total (17 new + 3 adapted), ~25 files to create/modify

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism | PASS | Skills are markdown files — simplest possible implementation. No service, no database. |
| II. Automate | PASS | `check-platform-prerequisites.sh` automates dependency validation. Pipeline-status automates visibility. |
| III. Structured Knowledge | PASS | Pipeline DAG makes knowledge structure explicit. Knowledge file documents contracts. |
| IV. Fast Action | PASS | Skills can be created and tested individually. No big-bang deployment needed. |
| V. Alternatives | PASS | Every skill must present ≥2 alternatives per decision (FR-014). Built into the contract. |
| VI. Brutal Honesty | PASS | Skills challenge assumptions via structured questions (FR-012). [VALIDAR] marks unknowns. |
| VII. TDD | PARTIAL | Skills are prompts, not code. TDD applies to the bash script (syntax check, output validation). Skills themselves are tested by invocation. |
| VIII. Collaborative Decision | PASS | Gate system ensures human approval at decision points. 1-way-door gates for irreversible decisions. |
| IX. Observability | N/A | Skills produce artifacts (files), not logs. The pipeline-status serves as the "observability" layer. |

**Verdict**: PASS — no violations. TDD partially applicable (bash script only).

## Project Structure

### Documentation (this feature)

```text
specs/001-atomic-skills-dag-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0: DAG patterns, skill engineering, ADR/DDD/Shape Up research
├── data-model.md        # Phase 1: platform.yaml schema, skill contract, gate types
├── contracts/
│   └── check-platform-prerequisites-cli.md  # CLI interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
.specify/
├── scripts/bash/
│   └── check-platform-prerequisites.sh     # NEW — DAG validator + status reporter
└── templates/platform/
    ├── copier.yml                           # MODIFIED — new _skip_if_exists entries
    └── template/
        ├── platform.yaml.jinja              # MODIFIED — add pipeline: section
        ├── business/
        │   └── process.md.jinja             # NEW — business process template
        ├── engineering/
        │   └── folder-structure.md.jinja    # NEW — folder architecture template
        ├── planning/
        │   ├── .gitkeep                     # NEW
        │   └── roadmap.md.jinja             # NEW — roadmap template
        └── research/
            ├── codebase-context.md.jinja    # NEW — brownfield analysis template
            └── tech-alternatives.md.jinja   # NEW — tech research template

.claude/
├── commands/madruga/
│   ├── vision-one-pager.md                  # MODIFIED — add prerequisites + handoffs
│   ├── solution-overview.md                 # MODIFIED — add prerequisites + handoffs
│   ├── platform-new.md                      # MODIFIED — add handoff to vision
│   ├── business-process.md                  # NEW
│   ├── codebase-map.md                      # NEW
│   ├── tech-research.md                     # NEW
│   ├── adr-gen.md                           # NEW
│   ├── blueprint.md                         # NEW
│   ├── folder-arch.md                       # NEW
│   ├── domain-model.md                      # NEW
│   ├── containers.md                        # NEW
│   ├── context-map.md                       # NEW
│   ├── epic-breakdown.md                    # NEW
│   ├── roadmap.md                           # NEW
│   ├── discuss.md                           # NEW
│   ├── verify.md                            # NEW
│   ├── checkpoint.md                        # NEW
│   ├── reconcile.md                         # NEW
│   ├── pipeline-status.md                   # NEW
│   └── pipeline-next.md                     # NEW
└── knowledge/
    └── pipeline-dag-knowledge.md            # NEW — canonical DAG, contracts, examples
```

**Structure Decision**: No `src/` or `tests/` directories — this feature produces markdown skills (`.claude/commands/`), bash scripts (`.specify/scripts/`), YAML configs (`.specify/templates/`), and a knowledge file (`.claude/knowledge/`). All follow existing repo conventions.

## Complexity Tracking

No violations. All artifacts follow existing patterns (skills follow vision-one-pager pattern, script follows check-prerequisites pattern, templates follow existing .jinja pattern).
