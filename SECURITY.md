# Security Policy

This document describes the security model, practices, and reporting procedures for the madruga.ai platform — an architectural documentation system powered by AI-driven pipeline skills.

---

## Trust Model

### Single-Operator Architecture

madruga.ai is designed for **single-operator use**. There is no multi-tenant access, no shared server, and no user-facing authentication layer. The operator is the sole person who:

- Executes pipeline skills via the CLI
- Approves gate decisions (human, 1-way-door)
- Manages API keys and environment variables
- Merges code to the main branch

### Local Execution

All pipeline execution happens **locally on the operator's machine**. No code is sent to external servers beyond the AI model API calls required by Claude. Specifically:

- Skills execute as local markdown-driven prompts
- Scripts run as local Python processes
- SQLite database (`.pipeline/madruga.db`) is a local file in WAL mode
- The portal (Astro Starlight) runs as a local dev server

### Subprocess Isolation

AI-assisted execution uses `claude -p` as a subprocess with the following isolation boundaries:

- **Tool allowlist**: Each skill declares which tools it may use. The Claude Code harness enforces this allowlist — tools not in the list are blocked.
- **Working directory**: Subprocess execution is scoped to the repository root. File operations outside this boundary require explicit operator approval.
- **No network access by default**: Scripts use stdlib only (no outbound HTTP calls) unless explicitly required (e.g., `copier` for template sync).
- **No persistent state mutation without gates**: Skills with `human` or `1-way-door` gates pause for operator approval before writing artifacts.

---

## Secret Management

### CLI-Injected API Keys

API keys (e.g., `ANTHROPIC_API_KEY`) are injected via:

1. **Environment variables** set in the operator's shell profile
2. **`.env` files** that are listed in `.gitignore` and never committed

No secrets are hardcoded in source code, configuration files, or documentation.

### Zero Secrets in Repository

The repository enforces a strict zero-secrets policy:

- `.env` is in `.gitignore` at the repository root
- CI runs a `security-scan` job that detects:
  - `.env` files accidentally committed
  - API key patterns (`sk-*`, `AKIA*`) in Python, Markdown, and YAML files
  - Hardcoded password assignments in Python files
- Pre-merge review is required for all AI instruction file changes (`.claude/`, `CLAUDE.md`) via CODEOWNERS

### Key Rotation

If a key is suspected to be compromised:

1. Revoke the key immediately at the provider dashboard (Anthropic Console, AWS IAM, etc.)
2. Generate a new key
3. Update the local `.env` file
4. Audit `git log` for any accidental commits containing the old key
5. If found in git history, treat the key as compromised regardless of branch

---

## Vulnerability Reporting

### Contact

Report security vulnerabilities by email to the repository owner listed in `.github/CODEOWNERS`.

Do **not** open a public GitHub issue for security vulnerabilities.

### Response Timeline

| Action | Target |
|--------|--------|
| Acknowledgment of report | 48 hours |
| Initial assessment and severity classification | 72 hours |
| Fix deployed (critical/high severity) | 7 days |
| Fix deployed (medium/low severity) | 30 days |
| Public disclosure (after fix) | 90 days |

### Severity Classification

| Severity | Definition | Example |
|----------|-----------|---------|
| Critical | Active exploitation possible, data loss or unauthorized access | Committed API key in public branch |
| High | Exploitable with minimal effort, significant impact | `eval()` on untrusted input in a script |
| Medium | Requires specific conditions to exploit | Overly broad file permissions in a skill |
| Low | Minimal impact, defense-in-depth concern | Missing input validation on a CLI flag |

### Disclosure Policy

We follow a **90-day coordinated disclosure** policy:

1. Reporter submits vulnerability privately
2. We acknowledge and assess within 72 hours
3. We develop and test a fix
4. We notify the reporter before public disclosure
5. Public disclosure occurs 90 days after the initial report, or when the fix is deployed — whichever comes first

---

## AI-Specific Security

### Tool Allowlist

Every pipeline skill operates under a **contract-based tool allowlist**:

- Skills declare their permitted tools in the skill contract (frontmatter)
- The Claude Code harness enforces tool restrictions at runtime
- Unauthorized tool calls are blocked and logged
- The operator can override restrictions when explicitly needed (admin bypass)

### Prompt Injection Mitigation

madruga.ai mitigates prompt injection through a **layered contract architecture**:

1. **Pipeline contracts** (`pipeline-contract-base.md`, `pipeline-contract-engineering.md`, etc.) define behavioral boundaries per layer (business, research, engineering, planning)
2. **Persona directives** constrain each skill's behavior (e.g., "Your first question is always: Is this the simplest thing that works?")
3. **Cardinal rules** define what each skill NEVER does (negative constraints)
4. **Gate system** requires human approval for irreversible decisions (`human` and `1-way-door` gates)
5. **Auto-review checklists** validate output against structural requirements before saving

No user-supplied content is passed directly to skill prompts without going through the structured question framework (Assumptions, Trade-offs, Gaps, Challenge).

### Auto-Review

Every skill includes a mandatory auto-review step that checks:

| Check | Purpose |
|-------|---------|
| Every decision has >= 2 alternatives | Prevents single-option bias |
| Every assumption marked `[VALIDAR]` or backed by data | Prevents hallucinated claims |
| Best practices researched | Prevents stale recommendations |
| Trade-offs explicit with pros/cons | Prevents hidden costs |
| Verifiable sources with URLs | Prevents ungrounded assertions |

### Circuit Breaker

The pipeline includes multiple circuit-breaker mechanisms:

- **Gate pauses**: `human` and `1-way-door` gates halt execution until the operator explicitly approves
- **Auto-escalate gates**: Skills like `judge` automatically escalate to the operator when blockers are found
- **Prerequisite checks**: Each skill validates its input artifacts exist before executing — missing prerequisites halt the pipeline with a clear error
- **Timeout**: The daemon enforces a configurable execution timeout per skill invocation

---

## OWASP LLM Top 10 — Relevant Items

This section maps the [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) to madruga.ai's mitigations.

### LLM01: Prompt Injection

**Risk**: Malicious input manipulates LLM behavior to bypass instructions.

**Mitigations**:
- Contract-based architecture with layered behavioral constraints (see above)
- No external user input — single-operator model eliminates the primary attack vector
- Gate system requires human approval for all irreversible actions
- Skill cardinal rules define hard negative constraints

### LLM02: Insecure Output Handling

**Risk**: LLM output is trusted without validation.

**Mitigations**:
- Auto-review checklists validate structural correctness of every artifact
- `judge` skill runs 4-persona technical review on implemented code
- `qa` skill performs static analysis, code review, and test execution
- All artifacts are saved to version-controlled files — diffs are reviewable before commit

### LLM06: Sensitive Information Disclosure

**Risk**: LLM reveals secrets, PII, or internal system details.

**Mitigations**:
- Zero secrets in repository (enforced by CI security scan)
- API keys injected via environment variables, never in prompts or files
- `.env` excluded from version control via `.gitignore`
- No PII processed — the system handles architectural documentation only

### LLM08: Excessive Agency

**Risk**: LLM takes actions beyond its intended scope.

**Mitigations**:
- Tool allowlist per skill restricts available actions
- Gate system pauses execution for operator approval
- `claude -p` subprocess isolation limits file system access
- No network access by default — outbound calls require explicit configuration

---

## Dependency Policy

### Minimal Dependencies

madruga.ai follows a **stdlib-first** dependency policy:

| Layer | Dependencies | Rationale |
|-------|-------------|-----------|
| Python scripts | `stdlib` + `pyyaml` | Minimize supply chain attack surface |
| Portal | `astro`, `starlight`, `react` | Standard static site generator stack |
| CI | `actions/checkout@v4`, `actions/setup-python@v5` | Pinned GitHub Actions only |
| CLI tools | `likec4`, `copier` | Installed globally, not bundled |

### Lock Files

- `portal/package-lock.json` is committed to the repository
- Python dependencies use stdlib — no `requirements.txt` for runtime scripts
- Development dependencies (pytest, ruff) are pinned in `requirements-dev.txt`

### Dependency Updates

- Dependencies are reviewed manually before updating
- Major version bumps require an ADR (Architecture Decision Record) if they affect the pipeline
- GitHub Actions are pinned to specific versions (e.g., `@v4`), not floating tags

### Supply Chain Considerations

- No pre-install or post-install scripts in Python dependencies
- GitHub Actions are referenced by immutable version tags
- The Copier template is maintained in-repo (`.specify/templates/`), not pulled from external sources
- All skill and knowledge files are version-controlled markdown — no binary dependencies

---

## Security Checklist for Contributors

Before submitting a PR, verify:

- [ ] No secrets, API keys, or credentials in committed files
- [ ] No `.env` files included in the commit
- [ ] No use of `eval()`, `exec()`, or `subprocess.call()` with `shell=True`
- [ ] No hardcoded passwords or private keys
- [ ] AI instruction file changes (`.claude/`, `CLAUDE.md`) reviewed by code owner
- [ ] New dependencies justified and documented (prefer stdlib)
- [ ] Lock files updated if dependencies changed

---

## Scope and Limitations

This security policy covers the madruga.ai repository and its local execution environment. It does **not** cover:

- Security of the AI model API provider (Anthropic)
- Security of the operator's local machine or network
- Security of external repositories referenced via `platform.yaml` repo binding
- Compliance with specific regulatory frameworks (GDPR, SOC2, etc.)

For questions about security practices not covered here, contact the repository owner.
