# Research: AI Infrastructure as Code

**Epic**: 019-ai-infra-as-code  
**Date**: 2026-04-04  
**Status**: Complete

## R1. CODEOWNERS Syntax and GitHub Branch Protection

**Decision**: Use GitHub CODEOWNERS file with `@gabrielhamu-srna` as owner for `.claude/`, `CLAUDE.md`, platform-specific `CLAUDE.md`, and `skill-lint.py`.

**Rationale**: GitHub natively supports CODEOWNERS. When branch protection requires code owner review, any PR touching matched paths must be approved by the designated owner. Admin bypass is configurable via "Allow administrators to bypass" setting.

**Alternatives considered**:
1. **CODEOWNERS (chosen)** — zero code, native GitHub integration, immediate effect
2. **GitHub Actions approval gate** — custom workflow that blocks merge. More flexible but adds CI complexity and maintenance burden
3. **Branch protection with required reviewers (no CODEOWNERS)** — requires review on ALL files, not just AI infra paths. Too broad for solo-dev

**Key findings**:
- CODEOWNERS path patterns: leading `/` anchors to repo root, `*` for single-level glob, `**` for recursive
- `/.claude/` matches all files recursively under `.claude/`
- `platforms/*/CLAUDE.md` matches any platform's CLAUDE.md
- Solo-dev mitigation: "Allow administrators to bypass required reviews" in branch protection settings

## R2. Security Scanning Regex Patterns

**Decision**: Use grep-based regex patterns for dangerous code patterns and secrets detection. No external tools (detect-secrets, trivy, gitleaks).

**Rationale**: The repo uses stdlib + pyyaml only. Adding a full SAST tool is disproportionate for the current codebase size. Simple regex catches the most common and dangerous patterns with zero dependencies.

**Alternatives considered**:
1. **grep regex (chosen)** — zero dependencies, fast, catches common patterns, easy to extend
2. **detect-secrets (Yelp)** — Python package, entropy-based detection. Better for secrets but adds dependency and complexity
3. **gitleaks** — Go binary, git history scanning. Overkill for current scope (we only need per-PR scanning)
4. **trufflehog** — Similar to gitleaks with more detectors. Same overkill concern

**Key findings**:
- Dangerous patterns regex: `eval\(|exec\(|subprocess\.call\(.*shell=True|PRIVATE.KEY|password\s*=\s*["'][^"']`
- API key patterns: `sk-[a-zA-Z0-9]{20,}` (OpenAI/Anthropic style), `AKIA[A-Z0-9]{16}` (AWS)
- `.env` file detection via `find` (not grep)
- Scope: `.specify/scripts/` for dangerous patterns, repo-wide for secrets (excluding `.git/`, `node_modules/`)
- False positive risk: `password\s*=\s*` in comments. Mitigation: regex requires assignment operator + quoted value, not bare mentions

## R3. Knowledge Dependency Graph — Actual vs Pitch

**Decision**: The impact analysis implementation must use runtime scanning (regex on skill files), not the static graph from the pitch, because the pitch graph has inaccuracies.

**Rationale**: Verified by scanning all 22 skill files. The actual dependency graph differs from the pitch in several places.

**Actual dependency graph** (verified 2026-04-04):

| Knowledge File | Actual Consumers |
|---|---|
| `pipeline-contract-base.md` | adr, blueprint, business-process, checkpoint, codebase-map, containers, context-map, domain-model, epic-breakdown, epic-context, judge, pipeline, platform-new, qa, reconcile, roadmap, skills-mgmt, solution-overview, tech-research, vision (20 skills) |
| `pipeline-contract-business.md` | business-process, platform-new, solution-overview, vision (4 skills) |
| `pipeline-contract-engineering.md` | adr, blueprint, containers, context-map, domain-model (5 skills) |
| `pipeline-contract-planning.md` | epic-breakdown, roadmap (2 skills) |
| `likec4-syntax.md` | containers, domain-model (2 skills) |
| `pipeline-dag-knowledge.md` | business-process (1 skill — NOT pipeline as pitch claims) |
| `judge-config.yaml` | judge (1 skill) |
| `qa-template.md` | qa (1 skill) |
| `commands.md` | none (referenced from CLAUDE.md, not from skills) |
| `decision-classifier-knowledge.md` | none (may be referenced indirectly or orphaned) |

**Pitch inaccuracies corrected**:
- `pipeline-dag-knowledge.md`: pitch claims consumers are `business-process, pipeline` → actual is only `business-process`
- `pipeline-contract-base.md`: pitch says "ALL 22" → actual is 20 (missing: getting-started, verify)
- Pitch omits `judge-config.yaml` and `qa-template.md` entirely

## R4. GitHub Actions — CI Job Design for AI Infra Gate

**Decision**: Conditional CI job that detects changes to AI infra paths and runs skill-lint + impact analysis only when relevant files change.

**Rationale**: The ai-infra job should not slow down unrelated PRs. Using `git diff` to detect changes and conditional steps (`if:`) to skip expensive operations is the standard GitHub Actions pattern.

**Alternatives considered**:
1. **Conditional job with git diff (chosen)** — runs only when needed, clear skip signal
2. **paths filter on workflow trigger** — `on.pull_request.paths: ['.claude/**']`. Simpler but creates a separate workflow file. Harder to add to existing `ci.yml`
3. **Always run, fail silently** — wastes CI minutes on irrelevant PRs

**Key findings**:
- `git diff --name-only origin/${{ github.base_ref }}...HEAD` gives accurate changed file list in PR context
- `actions/checkout@v4` with `fetch-depth: 0` needed for full git history in diff
- Impact analysis is informational (exit 0) — it annotates CI logs but never blocks
- `::group::` / `::endgroup::` for collapsible CI log sections

## R5. Knowledge Declarations — platform.yaml Schema Extension

**Decision**: Add `knowledge:` top-level key to `platform.yaml` with `file` + `consumers` structure. Support `all-pipeline` shorthand resolved dynamically.

**Rationale**: Makes implicit knowledge dependencies explicit and machine-readable. Warnings only (not blockers) to maintain backward compatibility.

**Alternatives considered**:
1. **platform.yaml `knowledge:` section (chosen)** — co-located with pipeline definition, single source of truth
2. **Separate `knowledge-graph.yaml`** — cleaner separation but adds a file that must stay in sync
3. **Inline in each skill's frontmatter** — distributed, harder to get a global view, requires skill editing (policy: via skills-mgmt only)

**Key findings**:
- `all-pipeline` resolves to all `pipeline.nodes[].id` from the same `platform.yaml`
- Cross-check: scan skill body for `.claude/knowledge/<filename>` references, compare against declared consumers
- Undeclared reference → WARNING (not BLOCKER)
- Missing declared file → WARNING (not BLOCKER)
- Copier template update: add optional `knowledge:` section with comment explaining format

## R6. Governance Documents — GitHub Recognition

**Decision**: Create `SECURITY.md` (repo root), `CONTRIBUTING.md` (repo root), `.github/pull_request_template.md`.

**Rationale**: GitHub automatically recognizes these files and surfaces them in UI:
- `SECURITY.md` → Security tab ("Security policy")
- `CONTRIBUTING.md` → "Contributing guidelines" link on PR creation page
- `.github/pull_request_template.md` → Pre-populates PR description

**Key findings**:
- `SECURITY.md` can also live in `.github/` or `docs/` — repo root is most visible
- `CONTRIBUTING.md` same — repo root preferred
- PR template supports multiple templates via `.github/PULL_REQUEST_TEMPLATE/` directory — single template is sufficient for now
- Content: English (per CLAUDE.md convention: "Docs, comments and code in English")
