---
id: 019
title: "AI Infrastructure as Code"
status: shipped
priority: P1
depends_on: []
blocks: []
updated: 2026-04-05
delivered_at: 2026-04-05
---
# Epic 019: AI Infrastructure as Code

## Problem

Qualquer commit em `.claude/` (22 skills, 7+ knowledge files, 4 rules, contracts) mergeia no main sem review obrigatorio. Um knowledge file renomeado silenciosamente quebra 5+ skills — e o CI nao detecta. Nao existe scan de seguranca para secrets hardcoded ou patterns perigosos. Nao ha como ver o blast radius de uma mudanca em AI instructions. Faltam SECURITY.md (trust model), CONTRIBUTING.md (regras de PR/AI code) e PR template — as 3 camadas de governanca mais basicas apos o CLAUDE.md.

O resultado: regressoes silenciosas em skills, sem auditoria de mudancas, e decisoes de seguranca implicitas.

## Solution

### T1. CODEOWNERS (5min)

Criar `.github/CODEOWNERS`:
```
# AI instruction infrastructure — require review on all changes
/.claude/                          @gabrielhamu
/CLAUDE.md                         @gabrielhamu
/platforms/*/CLAUDE.md             @gabrielhamu
/.specify/scripts/skill-lint.py    @gabrielhamu
```

Habilitar no GitHub: Settings > Branches > main > "Require review from Code Owners". Mitigacao solo-dev: "Allow administrators to bypass".

### T2. Security scan CI job (30min)

Novo job `security-scan` em `.github/workflows/ci.yml`:
```yaml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Check for dangerous patterns
      run: |
        PATTERNS='eval\(|exec\(|subprocess\.call\(.*shell=True|PRIVATE.KEY|password\s*=\s*["\x27][^"\x27]'
        if grep -rn -E "$PATTERNS" .specify/scripts/ --include='*.py'; then
          echo "::error::Dangerous patterns found in Python scripts"
          exit 1
        fi
    - name: Check for committed secrets
      run: |
        if find . -name '.env' -not -path './.git/*' -not -path './node_modules/*' | grep -q .; then
          echo "::error::.env file found in repository"
          exit 1
        fi
        if grep -rn -E '(sk-[a-zA-Z0-9]{20,}|AKIA[A-Z0-9]{16})' --include='*.py' --include='*.md' --include='*.yaml' .; then
          echo "::error::Potential API key found"
          exit 1
        fi
```

**Referencia:** RTK escaneia PRs por patterns perigosos (`Command::new("sh")`, `unsafe`, `.unwrap()`) e gera warnings no GitHub Step Summary.

### T3. `skill-lint.py --impact-of` (1h)

Estender `skill-lint.py` com flag `--impact-of <path>` que responde: "mudei este knowledge file, quais skills quebram?"

**Implementacao (~40-50 LOC adicionais):**

1. Nova funcao `build_knowledge_graph() -> dict[str, set[str]]`:
   - Escaneia cada `.md` em `COMMANDS_DIR` (ja definido em skill-lint.py)
   - Extrai referencias via regex: `\.claude/knowledge/([\w.-]+)`
   - Retorna mapa: `knowledge_filename → {skill_names}`

2. Nova funcao `cmd_impact_of(path: str)`:
   - Extrai filename do path
   - Consulta o grafo
   - Imprime tabela: skill name | archetype
   - Exit 0 (informacional, nao bloqueia CI)

3. Argparse: `--impact-of` como argumento opcional. Quando presente, pula lint normal e so roda impact analysis.

**Reutilizar:** `get_archetype()` e `COMMANDS_DIR` ja existentes em `skill-lint.py`.

**Grafo de dependencias atual (knowledge → skills):**

| Knowledge File | Skills Consumidores |
|---|---|
| `pipeline-contract-base.md` | **TODOS** os 22 pipeline/specialist skills |
| `pipeline-contract-business.md` | vision, solution-overview, business-process, platform-new |
| `pipeline-contract-engineering.md` | blueprint, domain-model, containers, context-map, adr |
| `pipeline-contract-planning.md` | epic-breakdown, roadmap |
| `likec4-syntax.md` | containers, domain-model |
| `pipeline-dag-knowledge.md` | business-process, pipeline |

### T4. CI gate `ai-infra` (1h)

Novo job `ai-infra` em `.github/workflows/ci.yml`:

```yaml
ai-infra:
  runs-on: ubuntu-latest
  if: github.event_name == 'pull_request'
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
    - name: Detect AI infra changes
      id: detect
      run: |
        FILES=$(git diff --name-only origin/${{ github.base_ref }}...HEAD)
        if echo "$FILES" | grep -qE '^(\.claude/|CLAUDE\.md|platforms/.*/CLAUDE\.md)'; then
          echo "changed=true" >> "$GITHUB_OUTPUT"
        else
          echo "changed=false" >> "$GITHUB_OUTPUT"
        fi
    - uses: actions/setup-python@v5
      if: steps.detect.outputs.changed == 'true'
      with:
        python-version: "3.11"
        cache: pip
        cache-dependency-path: requirements-dev.txt
    - run: pip install -r requirements-dev.txt
      if: steps.detect.outputs.changed == 'true'
    - name: Skill lint
      if: steps.detect.outputs.changed == 'true'
      run: python3 .specify/scripts/skill-lint.py
    - name: Impact analysis
      if: steps.detect.outputs.changed == 'true'
      run: |
        CHANGED=$(git diff --name-only origin/${{ github.base_ref }}...HEAD \
          | grep '^\.claude/knowledge/' || true)
        for f in $CHANGED; do
          echo "::group::Impact of $f"
          python3 .specify/scripts/skill-lint.py --impact-of "$f"
          echo "::endgroup::"
        done
```

**Pre-requisito:** Criar label `ai-infra` no repo:
```bash
gh label create ai-infra -c E8A317 -d "Changes to AI instruction files"
```

### T5. Documentation-change matrix no CLAUDE.md (30min)

Adicionar secao ao CLAUDE.md:

```markdown
## Documentation-Change Matrix

| Mudanca | Docs a atualizar |
|---------|-----------------|
| Nova skill (.claude/commands/) | pipeline-dag-knowledge.md, CLAUDE.md (skills list) |
| Novo script (.specify/scripts/) | CLAUDE.md (Essential commands) |
| Nova migration (.pipeline/migrations/) | CLAUDE.md (Active Technologies) |
| Nova plataforma (platforms/) | portal LikeC4Diagram.tsx (platformLoaders) |
| Novo knowledge file (.claude/knowledge/) | platform.yaml (knowledge section) |
```

### T6. Knowledge declarations em platform.yaml (2h)

Adicionar secao `knowledge:` ao `platforms/madruga-ai/platform.yaml` declarando quais knowledge files cada skill consome:

```yaml
knowledge:
  - file: pipeline-contract-base.md
    consumers: all-pipeline
  - file: pipeline-contract-business.md
    consumers: [vision, solution-overview, business-process, platform-new]
  - file: pipeline-contract-engineering.md
    consumers: [blueprint, domain-model, containers, context-map, adr]
  - file: pipeline-contract-planning.md
    consumers: [epic-breakdown, roadmap]
  - file: likec4-syntax.md
    consumers: [containers, domain-model]
```

Estender `skill-lint.py` com `lint_knowledge_declarations()`:
- Valida: arquivo declarado existe em `.claude/knowledge/`?
- Cross-check: referencia no body do skill que nao esta declarada → WARNING
- Resolve `all-pipeline` dinamicamente dos `pipeline.nodes[].id`

Atualizar template Copier: `.specify/templates/platform/template/platform.yaml.jinja`.

### T7. SECURITY.md (1.5h)

Criar `SECURITY.md` na raiz (GitHub reconhece e exibe na aba Security):

**Conteudo:**
- Trust model: single-operator, local execution, `claude -p` subprocess isolation
- Secret management: API keys via Claude Code CLI, `.env` no `.gitignore`, zero secrets no repo
- Vulnerability reporting: contato, prazo 48-72h, disclosure 90 dias
- AI-specific: skills nao acessam secrets, tool allowlist explicito, circuit breaker
- OWASP LLM Top 10 relevantes: prompt injection (mitigado por contract), output handling (auto-review)
- Dependency policy: stdlib + pyyaml only, lock files commitados

### T8. CONTRIBUTING.md (1h)

Criar `CONTRIBUTING.md`:

- PR rules: one thing per PR, AI-generated code welcome but marked
- Commit conventions: `feat:`, `fix:`, `chore:`, `merge:` — English
- Before-you-PR checklist: `make test && make lint && make ruff`
- Skill editing policy: always via `/madruga:skills-mgmt`, never direct
- AI code review: same rigor as human code

### T9. PR template (30min)

Criar `.github/pull_request_template.md`:

```markdown
## Summary

## Change type
- [ ] Bug fix
- [ ] Feature
- [ ] Refactor
- [ ] Docs
- [ ] AI infrastructure (skills/knowledge/rules)

## Security impact
- [ ] Handles user input?
- [ ] Modifies auth/permissions?
- [ ] Changes secret handling?
- [ ] Modifies AI instruction files?

## Test plan

## Risks and mitigations
```

## Rabbit Holes

- **Nao implementar label automation** — label `ai-infra` manual ou via actions/github-script. Nao criar bot complexo
- **SECURITY.md nao precisa de threat model completo** — isso seria `docs/security/threat-model.md` (scope futuro)
- **Knowledge declarations sao WARNING, nao BLOCKER** — backward compat com plataformas que nao declaram

## No-gos

- Mudancas nos scripts Python runtime (dag_executor, db.py) — isso e epic 018
- Pre-commit hooks (detect-secrets, shellcheck) — avaliar em epic futuro
- CodeQL SAST — complexo, avaliar separadamente
- Dependabot/Renovate — stdlib only, pouco valor agora

## Acceptance Criteria

- [ ] `.github/CODEOWNERS` existe e protege `.claude/`, `CLAUDE.md`
- [ ] CI job `security-scan` detecta `eval()` e API keys em PRs
- [ ] `python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/pipeline-contract-engineering.md` lista 5 skills
- [ ] CI job `ai-infra` roda skill-lint e impact analysis quando `.claude/` muda
- [ ] CLAUDE.md contem documentation-change matrix
- [ ] `platform.yaml` tem secao `knowledge:` com consumers
- [ ] `SECURITY.md` existe na raiz com trust model
- [ ] `CONTRIBUTING.md` existe com regras de PR e commit
- [ ] `.github/pull_request_template.md` existe com security assessment
- [ ] `make test` passa
- [ ] `make ruff` passa

## Implementation Context

### Arquivos a modificar
| Arquivo | Mudanca |
|---------|---------|
| `.github/workflows/ci.yml` | T2 (security-scan) + T4 (ai-infra job) |
| `.specify/scripts/skill-lint.py` | T3 (--impact-of) + T6 (knowledge declarations) |
| `CLAUDE.md` | T5 (documentation-change matrix) |
| `platforms/madruga-ai/platform.yaml` | T6 (knowledge section) |
| `.specify/templates/platform/template/platform.yaml.jinja` | T6 (knowledge template) |

### Arquivos a criar
| Arquivo | Estimativa |
|---------|-----------|
| `.github/CODEOWNERS` | ~5 linhas |
| `SECURITY.md` | ~200 linhas |
| `CONTRIBUTING.md` | ~80 linhas |
| `.github/pull_request_template.md` | ~25 linhas |

### Funcoes existentes a reutilizar
- `lint_knowledge_files()` em `skill-lint.py:173-195` — base para `build_knowledge_graph()`
- `get_archetype()` em `skill-lint.py` — classifica skills
- `COMMANDS_DIR`, `KNOWLEDGE_DIR` — paths ja definidos

### Decisoes
- **CODEOWNERS com bypass admin**: solo developer precisa de escape hatch para hotfixes
- **Security scan com regex simples**: nao usar tools pesados (detect-secrets, trivy) por enquanto
- **Knowledge declarations como WARNING**: nao BLOCKER, para backward compat

---

> **Source**: madruga_next_evolution.md S4, S5, A4, A5, A6, B6, B7
> **Benchmark**: RTK security scan, Ref_tech_Guide 6-layer governance, ai-instructions-as-infrastructure.md
