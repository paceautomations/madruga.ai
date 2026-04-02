# AI Instructions as Infrastructure

> Referência: "Patterns for Reducing Friction in AI-Assisted Development" — Rahul Garg, Principal Engineer na Thoughtworks (série no site do Martin Fowler).

## Problema

Instruções de IA (CLAUDE.md, knowledge files, skills) são infraestrutura crítica que governa a qualidade de todo output do pipeline. Hoje, qualquer push pode mudar silenciosamente um contract que afeta 22 skills. Não existe: proteção de review, detecção de blast radius, nem declaração explícita de dependências knowledge→skill.

## O que já funciona

| Pattern do artigo | O que temos |
|---|---|
| Versionado no repo | CLAUDE.md, `.claude/knowledge/`, `.claude/commands/` |
| Generation-time enforcement | Skills com contract uniforme (6 steps) |
| Review-time gate | `/madruga:judge` (4 personas + veredito) |
| Composição flexível | Skills single-purpose, knowledge on-demand |
| Role definition | Personas em `.claude/knowledge/personas/` |
| Lint de skills | `skill-lint.py` (frontmatter, handoff chain, orphan detection) |

## Outcome esperado

Mudanças em instruções passam por review obrigatório, CI detecta e mostra blast radius automaticamente, dependências knowledge→skill são declarativas e lintáveis.

---

## Deliverable 1: CODEOWNERS (5 min)

### O que
Criar `/.github/CODEOWNERS` para exigir review em PRs que tocam a superfície de instruções.

### Por quê
Sem CODEOWNERS, um PR que edita `pipeline-contract-engineering.md` (remove a validação de LikeC4 build) mergeia silenciosamente. As próximas 5 execuções de `/containers` e `/domain-model` pularão validação sem ninguém notar. CODEOWNERS garante que pelo menos um humano veja a mudança antes do merge.

### Impacto esperado nos outputs
- **Antes**: Qualquer commit em `.claude/` mergeia sem review → regressão silenciosa em skills
- **Depois**: PR bloqueado até owner aprovar → regressões detectadas antes do merge

### Implementação

**Criar** `/.github/CODEOWNERS`:
```
# AI instruction infrastructure
/.claude/                          @gabrielhamu
/CLAUDE.md                         @gabrielhamu
/platforms/*/CLAUDE.md             @gabrielhamu
/.specify/scripts/skill-lint.py    @gabrielhamu
```

**Configurar** (manual, 1 click): Settings > Branches > main > "Require review from Code Owners".

### Risco
Solo developer bloqueado em hot fixes → Mitigação: "Allow administrators to bypass" no branch protection.

---

## Deliverable 2: CI Gate `ai-infra` (~30 min)

### O que
Novo job `ai-infra` no CI que: (a) detecta se o PR toca instruções, (b) adiciona label `ai-infra`, (c) roda `skill-lint.py`, (d) mostra blast radius por knowledge file alterado.

### Por quê
CODEOWNERS diz **quem** revisa. O CI gate diz **o que quebrou**. Exemplo: PR renomeia `pipeline-contract-planning.md` para `pipeline-contract-plan.md`. Os 2 skills que referenciam o nome antigo têm referências quebradas. `skill-lint.py` já detecta isso como BLOCKER — mas hoje não roda no CI para mudanças em `.claude/`.

### Impacto esperado nos outputs
- **Antes**: Referências quebradas em knowledge files passam CI verde → skills falham em runtime
- **Depois**: CI falha com "BLOCKER: knowledge file X not referenced" → dev corrige antes do merge
- **Bônus**: Label `ai-infra` permite auditar frequência de mudanças em instruções

### Implementação

**Modificar** `/.github/workflows/ci.yml` — adicionar job:

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

      - name: Label PR
        if: steps.detect.outputs.changed == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.issues.addLabels({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              labels: ['ai-infra']
            });

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

**Pré-requisito**: Criar label `ai-infra` no repo:
```bash
gh label create ai-infra -c E8A317 -d "Changes to AI instruction files"
```

---

## Deliverable 3: `skill-lint.py --impact-of` (~1h)

### O que
Flag `--impact-of <path>` que, dado um knowledge file, imprime todos os skills que o consomem (direto) com archetype.

### Por quê
Já existe detecção de orphan knowledge (linhas 173-195 de `skill-lint.py`). Falta a pergunta inversa: "mudei `pipeline-contract-engineering.md`, o que quebra?". Hoje requer grep manual. O CI gate (deliverable 2) chama `--impact-of` automaticamente para cada knowledge file alterado no PR.

### Impacto esperado nos outputs
- **Antes**: Reviewer vê diff do knowledge file mas não sabe quais skills afeta → review superficial
- **Depois**: CI log mostra "pipeline-contract-engineering.md → 5 skills: blueprint, domain-model, containers, context-map, adr" → review focado

### Implementação

**Modificar** `.specify/scripts/skill-lint.py`:

1. Nova função `build_knowledge_graph() -> dict[str, set[str]]`:
   - Escaneia cada `.md` em `COMMANDS_DIR`
   - Extrai referências via regex: `\.claude/knowledge/([\w.-]+)`
   - Retorna mapa: knowledge_filename → {skill_names}

2. Nova função `cmd_impact_of(path: str)`:
   - Extrai filename do path
   - Consulta o grafo
   - Imprime tabela: skill name | archetype
   - Exit 0 (informacional, não bloqueia CI)

3. Argparse: `--impact-of` como argumento opcional
   - Quando presente, pula lint normal e só roda impact analysis

~40-50 linhas adicionais. Reutiliza `get_archetype()` e `COMMANDS_DIR` existentes.

### Exemplo de output
```
## Impact Analysis: pipeline-contract-engineering.md

| Skill | Archetype |
|-------|-----------|
| adr | pipeline |
| blueprint | pipeline |
| containers | pipeline |
| context-map | pipeline |
| domain-model | pipeline |

**Total: 5 skills affected**
```

### Grafo de dependências atual (knowledge → skills)

| Knowledge File | Skills Consumidores |
|---|---|
| `pipeline-contract-base.md` | **TODOS** os 22 pipeline/specialist skills |
| `pipeline-contract-business.md` | vision, solution-overview, business-process, platform-new |
| `pipeline-contract-engineering.md` | blueprint, domain-model, containers, context-map, adr |
| `pipeline-contract-planning.md` | epic-breakdown, roadmap |
| `likec4-syntax.md` | containers, domain-model |
| `pipeline-dag-knowledge.md` | business-process, pipeline |
| `qa-template.md` | qa |
| `judge-config.yaml` | judge |
| `judge-knowledge.md` | judge |
| `decision-classifier-knowledge.md` | judge |

---

## Deliverable 4: Knowledge Declaration em `platform.yaml` (~1.5h)

### O que
Seção `knowledge` no `platform.yaml` declarando explicitamente quais knowledge files cada skill consome. Cross-check automático no lint.

### Por quê
Hoje o mapa knowledge→skill é inferido por grep no corpo das skills. Funciona, mas é frágil: uma referência refatorada, um typo, ou um novo formato de referência quebra silenciosamente. Declarar explicitamente torna o grafo de dependências versionável, reviewável, e lintável como first-class citizen.

**Exemplo concreto**: Dev cria `pipeline-contract-observability.md`, referencia em `blueprint.md`, esquece de declarar. `skill-lint.py` flagga: "WARNING: blueprint references pipeline-contract-observability.md but not declared in platform.yaml".

### Impacto esperado nos outputs
- **Antes**: Knowledge files adicionados/removidos sem atualizar consumidores → drift silencioso
- **Depois**: Declaração obrigatória + cross-check automático → dependências sempre atualizadas
- **Bônus**: `--impact-of` usa declarações como fonte autoritativa (mais preciso que grep)

### Implementação

**1. Schema** — adicionar após `build:` e antes de `pipeline:` nos `platform.yaml`:

```yaml
knowledge:
  - file: pipeline-contract-base.md
    consumers: all-pipeline    # shorthand: todos os IDs em pipeline.nodes
  - file: pipeline-contract-business.md
    consumers: [vision, solution-overview, business-process, platform-new]
  - file: pipeline-contract-engineering.md
    consumers: [blueprint, domain-model, containers, context-map, adr]
  - file: pipeline-contract-planning.md
    consumers: [epic-breakdown, roadmap]
  - file: likec4-syntax.md
    consumers: [containers, domain-model]
  - file: pipeline-dag-knowledge.md
    consumers: [business-process, pipeline]
  - file: qa-template.md
    consumers: [qa]
  - file: judge-config.yaml
    consumers: [judge]
  - file: judge-knowledge.md
    consumers: [judge]
  - file: decision-classifier-knowledge.md
    consumers: [judge]
```

**2. Arquivos a modificar**:
- `platforms/madruga-ai/platform.yaml` — add `knowledge:` section
- `platforms/fulano/platform.yaml` — add `knowledge:` section
- `.specify/templates/platform/template/platform.yaml.jinja` — add `knowledge:` section com defaults

**3. Lint integration** — nova função `lint_knowledge_declarations()` em `skill-lint.py`:
- Carrega `knowledge` de cada `platform.yaml`
- Valida: arquivo declarado existe em `.claude/knowledge/`?
- Cross-check: referência no body do skill que não está declarada → WARNING
- Declaração sem referência no body → NIT
- Resolve `all-pipeline` dinamicamente de `pipeline.nodes[].id`

**4. Upgrade `build_knowledge_graph()`** (do deliverable 3):
- Se `platform.yaml` tem `knowledge`, usa como fonte autoritativa
- Fallback para grep quando a seção não existe (backward compat)

~50 linhas adicionais em `skill-lint.py`.

---

## Ordem de Implementação

```
D3 (--impact-of)  →  D4 (knowledge yaml)  →  D1 (CODEOWNERS)  →  D2 (CI gate)
     1h                   1.5h                    5min                30min
```

**Razão**: D3 é pré-requisito para D2 (CI chama `--impact-of`). D4 melhora a precisão do D3. D1 é independente mas faz sentido antes de D2. D2 depende de D1+D3 existirem.

---

## Verificação End-to-End

1. **D3**: `python3 .specify/scripts/skill-lint.py --impact-of .claude/knowledge/pipeline-contract-engineering.md` → deve listar 5 skills
2. **D4**: `python3 .specify/scripts/skill-lint.py` → sem WARNINGs novos (cross-check passes)
3. **D1**: `cat .github/CODEOWNERS` → regras corretas
4. **D2**: Criar PR que toca `.claude/knowledge/` → CI roda job `ai-infra`, label aparece, impact analysis no log
5. **Regressão**: `python3 -m pytest .specify/scripts/tests/ -v` → todos os testes existentes passam

---

## Arquivos Críticos

| Arquivo | Ação |
|---------|------|
| `.specify/scripts/skill-lint.py` | Modificar (D3 + D4) |
| `.github/workflows/ci.yml` | Modificar (D2) |
| `.github/CODEOWNERS` | Criar (D1) |
| `platforms/madruga-ai/platform.yaml` | Modificar (D4) |
| `platforms/fulano/platform.yaml` | Modificar (D4) |
| `.specify/templates/platform/template/platform.yaml.jinja` | Modificar (D4) |

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Solo developer bloqueado em hot fixes (CODEOWNERS) | "Allow administrators to bypass" no branch protection |
| `knowledge` section em `platform.yaml` drifta das referências reais | Cross-check lint detecta automaticamente (WARNING, não BLOCKER) |
| `all-pipeline` shorthand fica stale com novos skills | Resolvido dinamicamente de `pipeline.nodes[].id` no lint |
| Grep-based inference falha com novo formato de referência | Declaração em `platform.yaml` (D4) é a fonte autoritativa de longo prazo |
