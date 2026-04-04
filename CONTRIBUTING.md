# Contributing to madruga.ai

Thank you for your interest in contributing. This document covers the rules and conventions for submitting changes to this repository.

---

## PR Rules

- **One thing per PR.** Each pull request should address a single concern — one bug fix, one feature, one refactor. Do not bundle unrelated changes.
- **AI-generated code is welcome** but must be clearly marked. Use the `Co-Authored-By` trailer in your commit message:
  ```
  Co-Authored-By: Madruga
  ```
- **Keep PRs reviewable.** If a change touches more than 10 files or 500 lines, consider splitting it into smaller PRs.
- **Fill out the PR template.** Every PR uses the repository's pull request template. Complete all sections — especially Security Impact and Test Plan.

---

## Commit Conventions

All commit messages must be in **English** and use one of these prefixes:

| Prefix | When to use |
|--------|------------|
| `feat:` | New feature or capability |
| `fix:` | Bug fix |
| `chore:` | Maintenance, dependencies, CI, tooling |
| `merge:` | Merge commits |

Examples:
```
feat: add --impact-of flag to skill-lint.py
fix: correct knowledge graph regex for .yaml files
chore: update ci.yml with security-scan job
merge: epic/madruga-ai/019-ai-infra-as-code into main
```

Keep the first line under 72 characters. Use the commit body for details when needed.

---

## Before-you-PR Checklist

Run all of these locally before opening a pull request:

```bash
make test          # pytest — all tests must pass
make lint          # platform structure validation
make ruff          # Python lint and format check
```

If any command fails, fix the issue before pushing. CI will run the same checks and block the merge on failure.

For auto-fixing ruff issues:
```bash
make ruff-fix
```

---

## Skill Editing Policy

Skills (`.claude/commands/`) and knowledge files (`.claude/knowledge/`) must **always** be edited through the management skill:

```
/madruga:skills-mgmt edit <skill-name>
/madruga:skills-mgmt create <skill-name>
/madruga:skills-mgmt lint
/madruga:skills-mgmt audit
```

**Never edit these files directly.** Direct edits bypass validation — frontmatter checks, handoff chain verification, archetype compliance, and deduplication detection.

If you need to update a knowledge file, use `/madruga:skills-mgmt` and then run impact analysis to see which skills are affected:

```bash
python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/<filename>
```

---

## AI Code Review

AI-generated code receives the **same review rigor** as human-written code. There are no shortcuts:

- All acceptance scenarios from the spec must be verified
- Tests must cover the implemented behavior (TDD preferred)
- Security scan must pass (no `eval()`, `exec()`, hardcoded secrets)
- Skill-lint must pass for any AI instruction file changes
- Code owner approval is required for changes to `.claude/`, `CLAUDE.md`, and `skill-lint.py`

The `judge` skill runs a 4-persona technical review on implemented code. The `qa` skill performs static analysis, test execution, and code review. Both are part of the standard epic cycle and apply equally to AI-generated and human-written code.

---

## Dependency Policy

- Prefer Python stdlib over external libraries
- The only approved external Python dependency is `pyyaml`
- New dependencies require justification and documentation
- Lock files must be committed when dependencies change

---

## Questions?

If you are unsure about any convention, run `/madruga:getting-started` for an interactive onboarding walkthrough, or check `CLAUDE.md` for the full project reference.
