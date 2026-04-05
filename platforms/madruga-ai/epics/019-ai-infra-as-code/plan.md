# Implementation Plan: AI Infrastructure as Code

**Branch**: `epic/madruga-ai/019-ai-infra-as-code` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `platforms/madruga-ai/epics/019-ai-infra-as-code/spec.md`

## Summary

Add governance, security scanning, impact analysis, and documentation layers to the AI instruction infrastructure (`.claude/` directory). The main code change is extending `skill-lint.py` with `--impact-of` flag and knowledge declaration validation (~80-100 LOC). Everything else is file creation (CODEOWNERS, SECURITY.md, CONTRIBUTING.md, PR template) and CI configuration (2 new jobs in ci.yml).

## Technical Context

**Language/Version**: Python 3.11+ (stdlib + pyyaml), YAML (GitHub Actions), Markdown  
**Primary Dependencies**: pyyaml (already in use), GitHub Actions (actions/checkout@v4, actions/setup-python@v5)  
**Storage**: N/A — no database changes, all file-based  
**Testing**: pytest (`make test`), ruff (`make ruff`)  
**Target Platform**: GitHub repository (CI/CD, branch protection)  
**Project Type**: Governance infrastructure / tooling extension  
**Performance Goals**: CI ai-infra job < 60 seconds  
**Constraints**: No new Python dependencies. No changes to runtime scripts (dag_executor, db.py). Warnings only for knowledge declarations (backward compat).  
**Scale/Scope**: 22 skills, 10 knowledge files, 1 CI workflow file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pre-Design | Post-Design | Notes |
|-----------|-----------|-------------|-------|
| I. Pragmatism | PASS | PASS | Simple regex over full SAST. File creation over complex automation. |
| II. Automate Repetitive | PASS | PASS | CI automates security + lint checks that were manual. |
| III. Structured Knowledge | PASS | PASS | Knowledge declarations make implicit deps explicit. |
| IV. Fast Action | PASS | PASS | 9 tasks, mostly file creation. 2w appetite. |
| V. Alternatives | PASS | PASS | research.md documents alternatives for each decision. |
| VI. Brutal Honesty | PASS | PASS | Pitch graph inaccuracies corrected in research.md. |
| VII. TDD | PASS | PASS | Tests for skill-lint.py extensions (build_knowledge_graph, lint_knowledge_declarations). |
| VIII. Collaborative Decision | PASS | PASS | No complex architectural decisions — all are straightforward. |
| IX. Observability | N/A | N/A | No runtime code changes. CI logs provide observability. |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this epic)

```text
platforms/madruga-ai/epics/019-ai-infra-as-code/
├── pitch.md             # Epic pitch (Shape Up)
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── quickstart.md        # Phase 1 output
```

### Source Code (repository root)

```text
.github/
├── CODEOWNERS                       # T1 — CREATE
├── pull_request_template.md         # T9 — CREATE
└── workflows/
    └── ci.yml                       # T2, T4 — MODIFY (add security-scan + ai-infra jobs)

.specify/scripts/
├── skill-lint.py                    # T3, T6 — MODIFY (~80-100 LOC added)
└── tests/
    └── test_skill_lint.py           # T3, T6 — CREATE or MODIFY (7 test functions)

platforms/madruga-ai/
└── platform.yaml                    # T6 — MODIFY (add knowledge: section)

.specify/templates/platform/template/
└── platform.yaml.jinja              # T6 — MODIFY (add knowledge: section template)

CLAUDE.md                            # T5 — MODIFY (add documentation-change matrix)
SECURITY.md                          # T7 — CREATE (~150-200 lines)
CONTRIBUTING.md                      # T8 — CREATE (~80 lines)
```

**Structure Decision**: No new directories. All changes extend existing files or create well-known GitHub convention files at repo root / `.github/`.

## Implementation Details

### T1. CODEOWNERS (CREATE `.github/CODEOWNERS`)

~5 lines. Standard GitHub CODEOWNERS syntax. Paths:
- `/.claude/` → `@gabrielhamu-srna`
- `/CLAUDE.md` → `@gabrielhamu-srna`
- `/platforms/*/CLAUDE.md` → `@gabrielhamu-srna`
- `/.specify/scripts/skill-lint.py` → `@gabrielhamu-srna`

**Manual step**: Enable "Require review from Code Owners" in GitHub branch protection for `main`. Enable "Allow administrators to bypass".

### T2. Security Scan CI Job (MODIFY `.github/workflows/ci.yml`)

New job `security-scan` with 2 steps:
1. **Dangerous patterns**: grep for `eval(`, `exec(`, `subprocess.call(...shell=True`, `PRIVATE.KEY`, `password=` assignments in `.specify/scripts/` Python files
2. **Committed secrets**: find `.env` files, grep for API key patterns (`sk-*`, `AKIA*`) across `.py`, `.md`, `.yaml`

Runs on all pushes and PRs (same trigger as existing jobs).

### T3. Impact Analysis (MODIFY `.specify/scripts/skill-lint.py`)

Add ~40-50 LOC:

1. **`build_knowledge_graph() -> dict[str, set[str]]`**:
   - Scan `COMMANDS_DIR/*.md` files
   - Regex: `\.claude/knowledge/([\w.-]+\.(?:md|yaml))`
   - Return: `{filename: {skill_names}}`

2. **`cmd_impact_of(path: str)`**:
   - Extract filename from path
   - Look up in knowledge graph
   - Print table: `| Skill | Archetype |` for each dependent skill
   - Exit 0 (informational)

3. **Argparse**: Add `--impact-of <path>` optional argument. When present, skip normal lint and run impact analysis only.

**Reuses**: `get_archetype()`, `COMMANDS_DIR` (both existing).

### T4. CI Gate `ai-infra` (MODIFY `.github/workflows/ci.yml`)

New job `ai-infra` (PR-only via `if: github.event_name == 'pull_request'`):
1. Checkout with `fetch-depth: 0`
2. Detect AI infra changes via `git diff --name-only` against base ref
3. Conditional steps (skip if no AI infra changes):
   - Setup Python 3.11 + install requirements-dev.txt
   - Run `skill-lint.py` (full lint)
   - Run `skill-lint.py --impact-of` for each changed knowledge file (using `::group::` for CI log formatting)

### T5. Documentation-Change Matrix (MODIFY `CLAUDE.md`)

Add `## Documentation-Change Matrix` section with a table mapping:
- New skill → pipeline-dag-knowledge.md, CLAUDE.md
- New script → CLAUDE.md (Essential commands)
- New migration → CLAUDE.md (Active Technologies)
- New platform → portal LikeC4Diagram.tsx
- New knowledge file → platform.yaml (knowledge section)

### T6. Knowledge Declarations (MODIFY `platform.yaml`, `skill-lint.py`, `platform.yaml.jinja`)

**platform.yaml**: Add `knowledge:` section with 6 entries (5 knowledge .md files + note that judge-config.yaml and qa-template.md are also tracked).

**skill-lint.py** add ~30-40 LOC:

1. **`lint_knowledge_declarations(platform_yaml_path: Path) -> list[dict]`**:
   - Parse `knowledge:` section from platform.yaml
   - Validate each declared file exists in `KNOWLEDGE_DIR`
   - Build knowledge graph (reuse `build_knowledge_graph()`)
   - Cross-check: skill references vs declarations → WARNING for undeclared
   - Resolve `all-pipeline` from `pipeline.nodes[].id`

2. **Integration**: Call from `main()` when `--skill` is not set and platform.yaml exists.

**platform.yaml.jinja**: Add optional `knowledge:` section with comment.

### T7. SECURITY.md (CREATE)

~150-200 lines covering:
- Trust model (single-operator, local execution, subprocess isolation)
- Secret management (CLI-injected, .env in .gitignore, zero secrets in repo)
- Vulnerability reporting (contact, 48-72h response, 90-day disclosure)
- AI-specific security (tool allowlist, contract-based prompt injection mitigation, auto-review)
- OWASP LLM Top 10 relevant items
- Dependency policy (stdlib + pyyaml, lock files committed)

### T8. CONTRIBUTING.md (CREATE)

~80 lines covering:
- PR rules (one thing per PR, AI-generated code marked)
- Commit conventions (feat:, fix:, chore:, merge: — English)
- Before-you-PR checklist (`make test && make lint && make ruff`)
- Skill editing policy (always via `/madruga:skills-mgmt`)
- AI code review standards

### T9. PR Template (CREATE `.github/pull_request_template.md`)

~25 lines with sections:
- Summary
- Change type (checkboxes: bug fix, feature, refactor, docs, AI infrastructure)
- Security impact (checkboxes: user input, auth, secrets, AI instruction files)
- Test plan
- Risks and mitigations

## Test Plan

### Unit Tests (`.specify/scripts/tests/test_skill_lint.py`)

| Test | Validates | FR |
|------|-----------|-----|
| `test_build_knowledge_graph` | Graph matches known references (spot-check 3+ files) | FR-004 |
| `test_impact_of_known_file` | Returns correct skill list for `pipeline-contract-engineering.md` (5 skills) | FR-004, FR-005 |
| `test_impact_of_unknown_file` | Returns empty list, no error | FR-004 |
| `test_lint_knowledge_declarations_valid` | No warnings for correctly declared files | FR-009 |
| `test_lint_knowledge_declarations_missing_file` | WARNING for nonexistent declared file | FR-009 |
| `test_lint_knowledge_declarations_undeclared_ref` | WARNING for skill reference not in declarations | FR-010 |
| `test_all_pipeline_resolution` | `all-pipeline` resolves to all L1 + L2 node IDs | FR-011 |

### Integration / Manual Verification

| Check | Method | FR |
|-------|--------|-----|
| CODEOWNERS blocks merge | Create test PR modifying `.claude/`, verify review required | FR-001 |
| Security scan catches eval() | Push test file with `eval()`, verify CI failure | FR-002 |
| Security scan catches API keys | Push test file with `sk-...` pattern, verify CI failure | FR-003 |
| ai-infra job skips on non-AI changes | Push PR without `.claude/` changes, verify skip | FR-007 |
| ai-infra job runs on AI changes | Push PR with `.claude/` changes, verify lint + impact runs | FR-006 |
| GitHub recognizes SECURITY.md | Check Security tab after merge | FR-012 |
| GitHub recognizes CONTRIBUTING.md | Check Contributing link on new PR | FR-013 |
| PR template pre-populates | Create new PR, verify form | FR-014 |

### Validation Gate

```bash
make test && make ruff
```

## Dependency Order

```
T1 (CODEOWNERS)          ─── independent
T2 (security-scan CI)    ─── independent
T3 (--impact-of)         ─── independent (Python only)
T4 (ai-infra CI)         ─── depends on T3
T5 (doc-change matrix)   ─── independent
T6 (knowledge decl.)     ─── depends on T3 (reuses build_knowledge_graph)
T7 (SECURITY.md)         ─── independent
T8 (CONTRIBUTING.md)     ─── independent
T9 (PR template)         ─── independent
```

**Optimal execution order**: T1 → T3 → T6 → T2 → T4 → T5 → T7 → T8 → T9 (or T1/T3/T5/T7/T8/T9 in parallel, then T6, then T2/T4).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Security scan false positives | Medium | Low | Regex tuned for assignment patterns. Easy to adjust. |
| CODEOWNERS blocks solo-dev workflow | Low | Medium | Admin bypass enabled. |
| Knowledge graph regex misses indirect refs | Low | Low | Documented limitation. Only direct `.claude/knowledge/` refs detected. |
| Copier template update breaks existing platforms | Low | Medium | Knowledge section is optional — platforms without it get no warnings. |

## Complexity Tracking

No constitution violations. No complexity justifications needed.
