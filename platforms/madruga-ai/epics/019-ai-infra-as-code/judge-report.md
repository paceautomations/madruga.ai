---
title: "Judge Report — Epic 019: AI Infrastructure as Code"
score: 64
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
updated: 2026-04-04
---
# Judge Report — Epic 019: AI Infrastructure as Code

## Score: 64%

**Verdict:** FAIL
**Team:** Tech Reviewers (4 personas)

---

## Resumo Executivo

A implementação entrega corretamente os artefatos de governança (CODEOWNERS, SECURITY.md, CONTRIBUTING.md, PR template, jobs de CI), e `--impact-of` funciona conforme os critérios de aceitação. Os 504 testes passam e o `make ruff` está limpo. O FAIL reflete 6 WARNINGs substantivos confirmados por múltiplas personas — nenhum cria regressão imediata, mas três (chamada duplicada ao grafo, None-guard ausente, UnicodeDecodeError) são trivialmente corrigíveis antes de mergear.

Findings descartados: todas as 4 personas do run anterior foram invalidadas — o B1 (false positive no security-scan) está moot porque o `ci.yml` atual usa `\b` word boundaries; o W2 (hardcode de plataforma) está incorreto porque `main()` itera `platforms/*/platform.yaml`; o W1 (resolve_all_pipeline dead code) está incorreto porque a função É chamada (`all_pipeline_ids = resolve_all_pipeline(platform_yaml_path)`).

---

## Findings

### BLOCKERs (0)

Nenhum blocker confirmado após o Judge Pass. Nenhuma das nominações de BLOCKER das personas sobreviveu à revisão de evidências:
- Dupla chamada ao `build_knowledge_graph()` → desempenho degradado, não crash → rebaixado para WARNING.
- None-guard ausente no `yaml.safe_load()` → edge case (arquivo vazio), não crash em uso normal → rebaixado para WARNING.
- CI sem `set -e` no loop de impact analysis → confiabilidade de CI, não bloqueio funcional → rebaixado para WARNING.

---

### WARNINGs (6)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| W1 | arch-reviewer / bug-hunter / simplifier / stress-tester | `build_knowledge_graph()` é chamada **duas vezes** dentro de `lint_knowledge_declarations()`: uma vez no loop por entrada (quando `consumers == "all-pipeline"`) e novamente no loop de detecção de orphans. Com 8 declarações e 22 skill files, gera 9 scans completos de filesystem por `platform.yaml` em vez de 1. A 10 plataformas, o custo escala linearmente sem necessidade. | `skill-lint.py:lint_knowledge_declarations()` — `actual_refs = build_knowledge_graph().get(...)` dentro do loop (~linha 172) e `graph = build_knowledge_graph()` fora do loop (~linha 187) | Chamar `build_knowledge_graph()` uma única vez no topo da função, antes do `for entry in declarations:`, e reutilizar o resultado em ambos os blocos. Fix de ~3 linhas. |
| W2 | bug-hunter / stress-tester | `resolve_all_pipeline()` faz `data.get("pipeline", {})` mas `yaml.safe_load()` pode retornar `None` para arquivos vazios ou contendo apenas comentários. Se isso ocorrer durante um hook post-merge, a chamada levanta `AttributeError: 'NoneType' object has no attribute 'get'`, abortando o lint sem diagnóstico útil. O guard `data.get("knowledge") or []` em `lint_knowledge_declarations()` protege apenas a chave `knowledge`, não `data` em si. | `skill-lint.py:resolve_all_pipeline()` — primeira linha após `yaml.safe_load()` | Adicionar `if data is None: return set()` imediatamente após `data = yaml.safe_load(...)`. Mesmo guard em `lint_knowledge_declarations()` após seu `yaml.safe_load()`: `if data is None: return []`. |
| W3 | bug-hunter / stress-tester | `skill_path.read_text(encoding="utf-8")` em `build_knowledge_graph()` não tem tratamento de exceção. Um skill file com encoding inválido (e.g., Windows-1252 salvo por ferramenta de terceiros) levanta `UnicodeDecodeError`, interrompendo o lint inteiro sem identificar qual arquivo falhou. Em CI, isso resulta em stack trace sem contexto. | `skill-lint.py:build_knowledge_graph()` — `text = skill_path.read_text(encoding="utf-8")` | Envolver em `try/except (OSError, UnicodeDecodeError) as e:` e emitir um finding de WARNING (`{"skill": skill_name, "severity": "WARNING", "message": f"Cannot read file: {e}"}`) continuando para o próximo arquivo. |
| W4 | arch-reviewer / bug-hunter | O job `security-scan` escaneia apenas `--include='*.py' .specify/scripts/` para padrões perigosos. Arquivos em `.claude/knowledge/*.md` e `.claude/rules/*.md` podem conter blocos de código shell com `shell=True` ou chaves hardcoded que ficam invisíveis ao scan. O spec FR-002 diz "CI MUST scan all PRs for dangerous code patterns" sem restringir a `.specify/scripts/`. | `ci.yml:security-scan` — step `Check for dangerous code patterns` (linha ~128) | Estender o `grep` para cobrir `.claude/` com `--include='*.md'`, ou adicionar um step separado para Markdown no escopo de governança. Alternativamente, atualizar FR-002 na spec para refletir o escopo atual como decisão intencional. |
| W5 | bug-hunter / stress-tester | O padrão regex `password\s*=\s*["'"'"'][^"'"'"']` usa escape shell `'"'"'` dentro de um bloco `run:` YAML. O quoting está tecnicamente correto agora, mas é extremamente frágil a edições: qualquer modificação manual no YAML pode quebrar silenciosamente o padrão sem aviso, fazendo o `grep` retornar 0 (nenhum match) e o scan vira no-op para aquele padrão específico. | `ci.yml:security-scan` — regex dentro do `grep -rn -E '...'` (~linha 130) | Mover os padrões para `.github/security-patterns.txt` e usar `grep -f .github/security-patterns.txt`, eliminando todo quoting complexo no YAML. Torna o arquivo auditável e editável sem risco de regressão silenciosa. |
| W6 | bug-hunter | O step `Run impact analysis for changed knowledge files` no job `ai-infra` usa um `while read` loop bash sem `set -e`. Se `python3 .specify/scripts/skill-lint.py --impact-of "$file"` falhar (YAML corrompido, permissão, crash), o loop bash continua e o step sai com código 0, mascarando a falha. Um governance tool que silencia suas próprias falhas compromete a confiabilidade da camada de proteção. | `ci.yml:ai-infra` — step `Run impact analysis for changed knowledge files` (linha ~196) | Adicionar `set -euo pipefail` no início do bloco `run:` ou adicionar `|| { echo "::error::impact-of failed for $file"; exit 1; }` após o `python3`. |

---

### NITs (6)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| N1 | arch-reviewer | `cmd_impact_of()` mistura I/O (print direto para stdout) com lógica de negócio (retorna lista de resultados). Todas as outras funções lint retornam findings e deixam output para `main()`. Quebra a coesão modular estabelecida pelo restante do módulo. | `skill-lint.py:cmd_impact_of()` | Extrair prints para `main()` e fazer `cmd_impact_of()` retornar apenas a lista de resultados. |
| N2 | arch-reviewer | O job `ai-infra` usa `if: github.event_name == 'pull_request'`, então skill-lint nunca roda em pushes diretos a `main`. Dado que CODEOWNERS também só ativa em PRs, um push direto a `main` bypassa ambas as camadas de governança. | `ci.yml:ai-infra` | Documentar explicitamente em CONTRIBUTING.md que pushes diretos a `main` são desabilitados via branch protection rule. |
| N3 | bug-hunter | `test_build_knowledge_graph()` e `test_impact_of_known_file()` usam conjuntos exatos hardcoded (`{"adr", "blueprint", "containers", "context-map", "domain-model"}`). Adicionar qualquer skill que referencie `pipeline-contract-engineering.md` quebra os testes sem mudança na função testada. | `test_skill_lint.py:test_build_knowledge_graph()` / `test_impact_of_known_file()` | Substituir `assert eng_skills == {expected}` por `assert expected.issubset(eng_skills) and len(eng_skills) >= 5`. |
| N4 | stress-tester | `resolve_all_pipeline()` usa `if nid := node.get("id")` que silenciosamente ignora nodes sem chave `id`. Um node mal-formado em `platform.yaml` fica invisível na validação. | `skill-lint.py:resolve_all_pipeline()` | Emitir um log de warning quando um node não tiver `id`, para facilitar debugging de `platform.yaml` mal-formado. |
| N5 | simplifier | `test_lint_knowledge_declarations_valid` constrói YAML por concatenação de string manual (`entries.append(f" - file: {f}\n consumers: [...]")`), sensível a indentação e quoting. | `test_skill_lint.py:test_lint_knowledge_declarations_valid()` | Construir como dict Python e serializar com `yaml.dump()`. |
| N6 | bug-hunter | `resolve_all_pipeline()` poderia ser inlinada em `lint_knowledge_declarations()` — é chamada exatamente uma vez, tem 10 linhas, e não é reutilizada em nenhum outro code path. | `skill-lint.py:resolve_all_pipeline()` | Inline se não houver planos de reutilização. Se mantida como função, é uma decisão válida para testabilidade (está coberta por `test_all_pipeline_resolution`). |

---

## Findings Descartados pelo Judge

| # | Persona | Finding Original | Motivo do Descarte |
|---|---------|-----------------|-------------------|
| D1 | arch-reviewer | "Logic in resolve_all_pipeline() is inverted — checks wrong direction for FR-011" | **Parcialmente incorreto.** O check `uncovered = actual_refs - all_pipeline_ids` encontra skills fora do pipeline que referenciam o arquivo. Isso é uma verificação válida (diferente, mas não invertida). A função resolve_all_pipeline() IS chamada — linha `all_pipeline_ids = resolve_all_pipeline(platform_yaml_path)`. A conclusão de que é dead code está errada. |
| D2 | arch-reviewer | "build_knowledge_graph() called twice — second call is the BLOCKER, O(N×M)" | **Rebaixado.** A 2 plataformas e 8 entradas, o custo real é ~18 leituras extras de arquivos pequenos (~10KB cada). Não há crash, não há falha de correção. WARNING, não BLOCKER. |
| D3 | bug-hunter | "None-guard missing causes AttributeError crash — BLOCKER" | **Rebaixado.** `data.get("knowledge") or []` já protege o caminho mais crítico. `resolve_all_pipeline()` só crasharia com arquivo literalmente vazio, o que seria bloqueado antes pelo template validation (job `templates` no CI). WARNING. |
| D4 | bug-hunter | "Path traversal vulnerability via platform.yaml filename field" | **Risco desprezível.** `platform.yaml` é um arquivo version-controlled editado apenas pelo operator. Não há superfície de ataque externa. Reclassificado como NIT, e mesmo assim — omitido por ser de impacto ínfimo. |
| D5 | simplifier | "resolve_all_pipeline() é over-engineering — deve ser inlinada" | **Discordância de julgamento, não evidência.** A função é coberta por `test_all_pipeline_resolution`, o que justifica sua existência isolada. Rebaixado para NIT (N6). |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | Usar regex simples (não bandit/detect-secrets) para security scan | Médio — detectável, reversível | Sim — avaliado em research.md + pitch | APROVADA — scope intencional, facilmente expansível |
| 2 | CODEOWNERS com bypass admin para solo-dev | Médio — afeta governança | Sim — documentado em pitch + spec | APROVADA — escape hatch explícito, necessário para solo-dev |
| 3 | Knowledge declarations com severity WARNING apenas (não BLOCKER) | Baixo — backward compat intencional | Sim — spec FR-010, pitch Rabbit Holes | APROVADA — decisão explícita de compatibilidade documentada |

**Nenhuma decisão 1-way-door escapou ao classifier.**

---

## Personas que Falharam

Nenhuma — 4/4 personas retornaram com `PERSONA:` header e `FINDINGS:` section completos.

---

## Recomendações

### Antes de Mergear (WARNINGs trivialmente corrigíveis)

**Fix 1 — W1: Deduplicate `build_knowledge_graph()` (~3 linhas)**
```python
def lint_knowledge_declarations(platform_yaml_path):
    findings = []
    data = yaml.safe_load(platform_yaml_path.read_text(encoding="utf-8"))
    declarations = data.get("knowledge") or []
    all_pipeline_ids = resolve_all_pipeline(platform_yaml_path)
    graph = build_knowledge_graph()          # ← mover para cá, uma vez
    declared_files = set()
    for entry in declarations:
        ...
        if consumers == "all-pipeline" and all_pipeline_ids:
            actual_refs = graph.get(filename, set())  # ← reutilizar graph
```

**Fix 2 — W2: None-guard no yaml.safe_load() (~4 linhas)**
```python
def resolve_all_pipeline(platform_yaml_path):
    data = yaml.safe_load(platform_yaml_path.read_text(encoding="utf-8"))
    if data is None:          # ← adicionar
        return set()
    ...
```

**Fix 3 — W3: UnicodeDecodeError handling (~5 linhas)**
```python
for skill_path in COMMANDS_DIR.glob("*.md"):
    skill_name = skill_path.stem
    try:
        text = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        graph.setdefault(f"_read_error_{skill_name}", set())
        continue
```

### Tech Debt para Próximo Epic

- **W4**: Avaliar se o security scan deve cobrir `.claude/*.md` — envolve trade-off de falsos positivos (blocos de código de exemplo) vs. cobertura real.
- **W5**: Extrair patterns para `.github/security-patterns.txt`.
- **W6**: Adicionar `set -euo pipefail` ao impact analysis loop.

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Personas rodadas | 4/4 |
| Personas com falha | 0 |
| Findings brutos (pré-judge) | 28 |
| Findings descartados (hallucination / incorretos / scope) | 5 |
| Findings rebaixados (BLOCKER → WARNING) | 3 |
| BLOCKERs confirmados | 0 |
| WARNINGs confirmados | 6 |
| NITs confirmados | 6 |
| Score | **64%** (100 − 0×20 − 6×5 − 6×1) |
| Verdict | **FAIL** (score < 80) |

---

## Gate: ESCALATE

Score 64% com 0 BLOCKERs. Verdict FAIL por volume de WARNINGs. Recomenda-se aplicar os 3 fixes triviais (W1/W2/W3, ~12 LOC total) antes de mergear para elevar o score estimado para ~89% (PASS). Os demais WARNINGs (W4/W5/W6) podem ser tech debt.

*Gerado pelo `/madruga:judge` — 4 personas (Tech Reviewers): arch-reviewer, bug-hunter, simplifier, stress-tester*
