# Feature Specification: AI Infrastructure as Code

**Feature Branch**: `epic/madruga-ai/019-ai-infra-as-code`  
**Created**: 2026-04-04  
**Status**: Draft  
**Input**: User description: "AI Infrastructure as Code — governance, security scanning, impact analysis, and documentation for AI instruction files"

## User Scenarios & Testing

### User Story 1 - Mandatory Review on AI Instruction Changes (Priority: P1)

As a platform operator, I want all changes to AI instruction files (skills, knowledge, rules, contracts) to require review before merging to main, so that silent regressions from renamed or broken files are caught before they affect the pipeline.

**Why this priority**: AI instruction files are the foundation of the entire pipeline. A single broken reference silently degrades multiple skills. This is the highest-impact, lowest-effort governance layer.

**Independent Test**: Submit a PR that modifies a file under `.claude/` and verify that merging is blocked until a designated reviewer approves.

**Acceptance Scenarios**:

1. **Given** a PR modifying any file under `.claude/`, **When** no code owner has approved, **Then** the PR cannot be merged to main.
2. **Given** a PR modifying `CLAUDE.md` at the repo root, **When** no code owner has approved, **Then** the PR cannot be merged to main.
3. **Given** a PR modifying files outside `.claude/` and `CLAUDE.md`, **When** submitted, **Then** no code owner review is required for those files.
4. **Given** the operator is a repository admin, **When** an urgent hotfix is needed, **Then** they can bypass the code owner requirement.

---

### User Story 2 - Security Scanning for Dangerous Patterns (Priority: P1)

As a platform operator, I want CI to automatically scan for dangerous code patterns and committed secrets on every PR, so that security vulnerabilities and leaked credentials are caught before reaching main.

**Why this priority**: Security is a non-negotiable baseline. Dangerous patterns like `eval()` and hardcoded API keys can cause catastrophic damage if merged undetected.

**Independent Test**: Submit a PR containing a file with `eval()` or a fake API key pattern and verify CI fails with a clear error message.

**Acceptance Scenarios**:

1. **Given** a PR that adds a Python file containing `eval()`, **When** CI runs, **Then** the security scan job fails with an error identifying the file and line.
2. **Given** a PR that adds a file containing an API key pattern (e.g., `sk-` followed by 20+ alphanumeric characters), **When** CI runs, **Then** the security scan job fails with an error identifying the potential key.
3. **Given** a PR that adds a `.env` file to the repository, **When** CI runs, **Then** the security scan job fails.
4. **Given** a PR with no dangerous patterns or secrets, **When** CI runs, **Then** the security scan job passes.

---

### User Story 3 - Impact Analysis for Knowledge File Changes (Priority: P1)

As a platform operator, I want to see which skills are affected when I change a knowledge file, so that I can assess the blast radius before merging.

**Why this priority**: Knowledge files are referenced by multiple skills. Without impact visibility, a rename or deletion silently breaks dependent skills with no warning.

**Independent Test**: Run the impact analysis tool against a known knowledge file and verify it lists the correct dependent skills.

**Acceptance Scenarios**:

1. **Given** a knowledge file referenced by 5 skills, **When** I run impact analysis on that file, **Then** all 5 dependent skills are listed with their archetypes.
2. **Given** a knowledge file referenced by no skills, **When** I run impact analysis, **Then** an empty result is returned (no error).
3. **Given** a PR that modifies a knowledge file, **When** CI runs the ai-infra job, **Then** the impact analysis output appears in the CI log for that file.

---

### User Story 4 - CI Gate for AI Instruction Changes (Priority: P2)

As a platform operator, I want CI to automatically run skill linting and impact analysis when AI instruction files change in a PR, so that broken skills and undeclared dependencies are caught before merging.

**Why this priority**: Combines skill-lint (existing) with impact analysis (new) into a single CI gate. Depends on T3 being implemented first.

**Independent Test**: Submit a PR that modifies a file under `.claude/` and verify that skill-lint and impact analysis run automatically in CI.

**Acceptance Scenarios**:

1. **Given** a PR that modifies files under `.claude/`, **When** CI runs, **Then** the ai-infra job runs skill-lint on all skills.
2. **Given** a PR that modifies files under `.claude/knowledge/`, **When** CI runs, **Then** the ai-infra job runs impact analysis on each changed knowledge file.
3. **Given** a PR that modifies only files outside `.claude/` and `CLAUDE.md`, **When** CI runs, **Then** the ai-infra job detects no AI infra changes and skips lint/impact analysis.

---

### User Story 5 - Knowledge Dependency Declarations (Priority: P2)

As a platform operator, I want to declare which knowledge files each skill consumes in `platform.yaml`, so that dependency validation can catch undeclared or missing references.

**Why this priority**: Makes the implicit dependency graph explicit and machine-readable. Enables automated validation but is not blocking for CI (warnings only).

**Independent Test**: Add a knowledge declaration to `platform.yaml`, then run skill-lint to verify it validates the declared file exists and cross-checks against actual references in skills.

**Acceptance Scenarios**:

1. **Given** a knowledge file declared in `platform.yaml` that exists in `.claude/knowledge/`, **When** skill-lint runs, **Then** no warning is generated.
2. **Given** a knowledge file declared in `platform.yaml` that does not exist, **When** skill-lint runs, **Then** a WARNING is generated (not a blocker).
3. **Given** a skill that references a knowledge file not declared in `platform.yaml`, **When** skill-lint runs, **Then** a WARNING is generated for the undeclared dependency.

---

### User Story 6 - Governance Documentation (Priority: P2)

As a platform operator or contributor, I want SECURITY.md, CONTRIBUTING.md, and a PR template to exist in the repository, so that security practices, contribution rules, and PR expectations are documented and enforceable.

**Why this priority**: These are the three basic governance documents after CLAUDE.md. They set expectations for any future contributor and are recognized by GitHub's UI.

**Independent Test**: Verify each file exists, is recognized by GitHub (Security tab, Contributing guidelines link, PR form pre-population), and contains the expected sections.

**Acceptance Scenarios**:

1. **Given** the repository, **When** a user visits the GitHub Security tab, **Then** SECURITY.md content is displayed with trust model and vulnerability reporting instructions.
2. **Given** a new contributor, **When** they visit the Contributing link on GitHub, **Then** CONTRIBUTING.md displays PR rules, commit conventions, and the before-you-PR checklist.
3. **Given** a user creating a new PR, **When** they open the PR form, **Then** the PR template pre-populates with change type, security impact, test plan, and risk sections.

---

### User Story 7 - Documentation-Change Matrix (Priority: P3)

As a platform operator, I want a reference matrix in CLAUDE.md that tells me which documentation to update when I make certain types of changes, so that I never forget to update dependent docs.

**Why this priority**: Nice-to-have reference that reduces documentation drift. Low effort, incremental value.

**Independent Test**: Read the matrix in CLAUDE.md and verify it covers the common change scenarios (new skill, new script, new migration, new platform, new knowledge file).

**Acceptance Scenarios**:

1. **Given** CLAUDE.md, **When** I look for the documentation-change matrix, **Then** I find a table mapping change types to required documentation updates.
2. **Given** I add a new skill, **When** I consult the matrix, **Then** it tells me to update `pipeline-dag-knowledge.md` and `CLAUDE.md`.

---

### Edge Cases

- What happens when a skill references a knowledge file using an alias or indirect path (e.g., via a variable)? Impact analysis only detects direct regex matches and documents this limitation.
- What happens when `platform.yaml` declares `all-pipeline` as consumers? The system resolves this dynamically from the pipeline node list at lint time.
- What happens when the security scan encounters a false positive (e.g., the word "password" in a comment)? The regex patterns are tuned to match assignment patterns, not bare mentions.
- What happens when CI runs on a branch with no `.claude/` changes? The ai-infra job detects no changes and exits early (skip, not fail).

## Requirements

### Functional Requirements

- **FR-001**: Repository MUST enforce code owner review for all changes to AI instruction files (`.claude/`, `CLAUDE.md`, platform-specific `CLAUDE.md` files) before merging to main.
- **FR-002**: CI MUST scan all PRs for dangerous code patterns (`eval()`, `exec()`, `subprocess.call()` with `shell=True`, hardcoded private keys, password assignments).
- **FR-003**: CI MUST scan all PRs for committed secrets (`.env` files, API key patterns matching `sk-*` and `AKIA*`).
- **FR-004**: The skill-lint tool MUST support an `--impact-of <path>` flag that lists all skills that reference the given knowledge file.
- **FR-005**: Impact analysis MUST display skill name and archetype for each dependent skill.
- **FR-006**: CI MUST run skill-lint and impact analysis automatically when AI instruction files change in a PR.
- **FR-007**: CI ai-infra job MUST skip lint and impact analysis when no AI instruction files are changed.
- **FR-008**: `platform.yaml` MUST support a `knowledge:` section declaring knowledge files and their consumer skills.
- **FR-009**: Skill-lint MUST validate that declared knowledge files exist on disk.
- **FR-010**: Skill-lint MUST warn (not block) when a skill references a knowledge file not declared in `platform.yaml`.
- **FR-011**: The `all-pipeline` consumer shorthand MUST resolve dynamically from pipeline node definitions.
- **FR-012**: Repository MUST contain a SECURITY.md with trust model, secret management policy, vulnerability reporting process, and AI-specific security considerations.
- **FR-013**: Repository MUST contain a CONTRIBUTING.md with PR rules, commit conventions, testing checklist, and skill editing policy.
- **FR-014**: Repository MUST contain a PR template with change type classification, security impact assessment, test plan, and risk sections.
- **FR-015**: CLAUDE.md MUST contain a documentation-change matrix mapping change types to required documentation updates.
- **FR-016**: The Copier platform template MUST include the `knowledge:` section in `platform.yaml.jinja`.

### Key Entities

- **Knowledge File**: A markdown file in `.claude/knowledge/` that provides reference information consumed by one or more skills. Key attributes: filename, path, consumer list.
- **Skill**: A markdown file in `.claude/commands/` that defines an AI pipeline step. Key attributes: name, archetype, knowledge references.
- **Knowledge Graph**: A computed dependency map from knowledge files to the skills that reference them. Used for impact analysis.
- **Knowledge Declaration**: An entry in `platform.yaml` under the `knowledge:` section that explicitly declares a knowledge file and its consumers.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of PRs modifying AI instruction files require code owner approval before merge (verified by GitHub branch protection).
- **SC-002**: CI detects and blocks 100% of PRs containing known dangerous patterns (`eval()`, hardcoded API keys, `.env` files) within scanned file types.
- **SC-003**: Impact analysis correctly identifies all directly referencing skills for any given knowledge file (verified against the known dependency graph with 0 false negatives).
- **SC-004**: CI ai-infra job completes in under 60 seconds for PRs with AI instruction changes.
- **SC-005**: All three governance documents (SECURITY.md, CONTRIBUTING.md, PR template) are recognized and displayed by GitHub in their respective UI locations.
- **SC-006**: `make test` and `make ruff` pass with all new changes included.

## Assumptions

- The repository is hosted on GitHub, which supports CODEOWNERS, branch protection rules, and recognition of SECURITY.md/CONTRIBUTING.md files.
- The operator is the sole developer (solo-dev) and needs admin bypass for hotfixes on code owner rules.
- The security scan uses simple regex patterns, not a full SAST tool. It catches common patterns but may miss obfuscated secrets.
- Knowledge file references in skills use the pattern `.claude/knowledge/<filename>` — indirect or programmatic references are not detected by impact analysis.
- `skill-lint.py` already exists with `COMMANDS_DIR`, `KNOWLEDGE_DIR`, `get_archetype()`, and `lint_knowledge_files()` functions that can be extended.
- Knowledge declarations in `platform.yaml` are validated as warnings, not blockers, to maintain backward compatibility with platforms that do not declare them.
- No changes to runtime Python scripts (dag_executor.py, db.py) are in scope — those belong to epic 018.
- Pre-commit hooks, CodeQL, and Dependabot/Renovate are explicitly out of scope.
