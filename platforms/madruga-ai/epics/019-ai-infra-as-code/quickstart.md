# Quickstart: AI Infrastructure as Code

**Epic**: 019-ai-infra-as-code  
**Date**: 2026-04-04

## Prerequisites

- Python 3.11+
- pyyaml (`pip install pyyaml`)
- GitHub CLI (`gh`) for label creation
- Repository admin access (for branch protection settings)

## Verification Commands

After implementation, verify each component:

### T1. CODEOWNERS
```bash
# File exists and has correct patterns
cat .github/CODEOWNERS
# Manual: Settings > Branches > main > Require review from Code Owners
```

### T2. Security Scan
```bash
# Test dangerous pattern detection (should find eval)
echo 'eval("code")' > /tmp/test_eval.py
grep -rn -E 'eval\(|exec\(' /tmp/test_eval.py
rm /tmp/test_eval.py

# Test secret detection (should find fake key)
echo 'key = "sk-abcdefghijklmnopqrstuvwxyz"' > /tmp/test_secret.py
grep -rn -E 'sk-[a-zA-Z0-9]{20,}' /tmp/test_secret.py
rm /tmp/test_secret.py
```

### T3. Impact Analysis
```bash
# Should list 5 skills (adr, blueprint, containers, context-map, domain-model)
python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/pipeline-contract-engineering.md

# Should list 20 skills
python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/pipeline-contract-base.md

# Should list 0 skills (not referenced by any skill)
python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/commands.md
```

### T4. CI Gate (test locally)
```bash
# Simulate detection of AI infra changes
git diff --name-only origin/main...HEAD | grep -E '^(\.claude/|CLAUDE\.md|platforms/.*/CLAUDE\.md)' || echo "No AI infra changes"

# Run skill lint (same as CI would)
python3 .specify/scripts/skill-lint.py
```

### T5. Documentation-Change Matrix
```bash
# Verify matrix exists in CLAUDE.md
grep -c "Documentation-Change Matrix" CLAUDE.md
```

### T6. Knowledge Declarations
```bash
# Verify knowledge section in platform.yaml
python3 -c "import yaml; d=yaml.safe_load(open('platforms/madruga-ai/platform.yaml')); print(d.get('knowledge', 'MISSING'))"

# Run full lint (includes knowledge declaration validation)
python3 .specify/scripts/skill-lint.py
```

### T7-T9. Governance Documents
```bash
# All files exist
ls -la SECURITY.md CONTRIBUTING.md .github/pull_request_template.md
```

### Full Validation
```bash
make test && make ruff
```

## File Map

| File | Action | Task |
|------|--------|------|
| `.github/CODEOWNERS` | CREATE | T1 |
| `.github/workflows/ci.yml` | MODIFY | T2, T4 |
| `.specify/scripts/skill-lint.py` | MODIFY | T3, T6 |
| `CLAUDE.md` | MODIFY | T5 |
| `platforms/madruga-ai/platform.yaml` | MODIFY | T6 |
| `.specify/templates/platform/template/platform.yaml.jinja` | MODIFY | T6 |
| `SECURITY.md` | CREATE | T7 |
| `CONTRIBUTING.md` | CREATE | T8 |
| `.github/pull_request_template.md` | CREATE | T9 |

## Test Strategy

- **skill-lint.py extensions** (T3, T6): Unit tests in `.specify/scripts/tests/test_skill_lint.py`
  - `test_build_knowledge_graph()` — verify graph matches known references
  - `test_cmd_impact_of_known_file()` — verify correct skills listed
  - `test_cmd_impact_of_unknown_file()` — verify empty result, no error
  - `test_lint_knowledge_declarations_valid()` — no warnings when all declared
  - `test_lint_knowledge_declarations_missing_file()` — WARNING for nonexistent file
  - `test_lint_knowledge_declarations_undeclared_ref()` — WARNING for undeclared reference
  - `test_all_pipeline_resolution()` — verify `all-pipeline` resolves to correct node set
- **CI jobs** (T2, T4): Verified by pushing a PR with test patterns (manual)
- **Static files** (T1, T7, T8, T9): File existence + content section checks
- **Validation**: `make test && make ruff` must pass
