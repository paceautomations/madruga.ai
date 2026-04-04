# Ref Tech Guide — Arquitetura de Governança Técnica para Projetos com AI Agents

> Guia consolidado de boas práticas para estruturar regras de engenharia, segurança e arquitetura
> em projetos que usam Claude Code (ou agentes AI similares).
> Fontes: análise do source code do Claude Code v2.1.88, referências OpenClaw (~345k stars),
> pesquisa de práticas de mercado 2025-2026.

---

## 1. Visão Geral — As 6 Camadas de Governança

Regras de engenharia **não vivem só no CLAUDE.md**. Estão distribuídas em 6 camadas, cada uma com escopo e enforcement diferentes:

```
Camada 6 ─ Automação (scripts, CI, AST checks)      ← determinístico, zero confiança
Camada 5 ─ .github/ (CODEOWNERS, PR template, CI)    ← process gates
Camada 4 ─ docs/ (architecture, security, threats)    ← referência profunda
Camada 3 ─ AGENTS.md / .claude/rules/ (por módulo)    ← boundary contracts
Camada 2 ─ Governance files (SECURITY, CONTRIBUTING)   ← política
Camada 1 ─ CLAUDE.md raiz                             ← instrução ao agente
```

**Princípio organizador:**

```
Regra pode ser verificada automaticamente?
  │
  ├── SIM → Camada 6 (linters, CI, AST checks)
  │         Enforcement determinístico. O agente nem precisa saber.
  │
  └── NÃO → Quão específica?
              ├── De um módulo → Camada 3 (.claude/rules/ com paths:)
              ├── Política do repo → Camada 2 (SECURITY.md, CONTRIBUTING.md)
              ├── Referência profunda → Camada 4 (docs/)
              ├── Process gate → Camada 5 (.github/)
              └── Instrução ao agente → Camada 1 (CLAUDE.md)
```

---

## 2. Camada 1 — CLAUDE.md (Instrução ao Agente)

### O que colocar

- Vocabulário do projeto e stack
- Comandos de build/test/lint
- Coding style (só o que linters não capturam)
- Patterns obrigatórios e anti-patterns proibidos
- Gate system (quando rodar o quê)
- Multi-agent safety

### O que NÃO colocar

- Trust model completo (vai no SECURITY.md)
- Detalhes de cada boundary (vai nos rules/ distribuídos)
- Threat model (vai no docs/)
- Regras que o linter já aplica
- Runbooks operacionais (SSH, deploy)

### Limite: ~200 linhas

Se passar, distribua para `.claude/rules/` ou use `@include`.

### Hierarquia de carregamento

| # | Localização | Prioridade |
|---|------------|------------|
| 1 | `/etc/claude-code/CLAUDE.md` | Menor |
| 2 | `~/.claude/CLAUDE.md` | ↓ |
| 3 | `CLAUDE.md` (raiz) | ↓ |
| 4 | `.claude/CLAUDE.md` | ↓ |
| 5 | `.claude/rules/*.md` | ↓ |
| 6 | `CLAUDE.local.md` | Maior |

**Regra-chave:** Carregado depois = mais peso no modelo. O que é mais importante vai no final ou em `CLAUDE.local.md`.

### Diretiva @include

```markdown
@./docs/architecture.md        # relativo ao arquivo
@~/personal-rules.md           # relativo ao home
```

Profundidade máxima: 5 níveis. Detecção de ciclos. Dedup por inode.
Limite por arquivo: **40.000 caracteres** (truncado silenciosamente se exceder).

---

## 3. Camada 2 — Governance Files (Política)

### SECURITY.md — Modelo de Segurança

O GitHub reconhece `SECURITY.md` na raiz e exibe na aba Security.

**Conteúdo recomendado:**

| Seção | O que contém |
|-------|-------------|
| **Trust model** | Quem acessa o quê, limites de confiança |
| **Vulnerability reporting** | Contato, prazo de resposta (48-72h), disclosure timeline (90 dias) |
| **Versões suportadas** | Quais versões recebem patches de segurança |
| **Controles de segurança** | Autenticação, autorização, criptografia |
| **Secret management** | Sem secrets no código, método de injeção (vault/env) |
| **Dependency policy** | Registries aprovados, SCA tool, auto-merge rules |
| **OWASP references** | Top 10 relevante ao stack (Web, API, LLM) |
| **AI-specific** | Se agentes AI podem acessar secrets, escopo de review |
| **Out-of-scope** | False positives comuns em reports |

**Tamanho típico:** ~400 linhas.

### CONTRIBUTING.md — Regras para Humanos

| Seção | Exemplo |
|-------|---------|
| Maintainer list + áreas de ownership | Domínios por pessoa |
| PR rules | "One thing per PR, no refactor-only PRs" |
| AI/vibe-coded PR policy | "Welcome but must be marked" |
| Before-you-PR checklist | `make test && make lint` |
| Commit conventions | Prefixos, idioma, Co-Authored-By |

### VISION.md — Direção Estratégica

| Seção | Exemplo |
|-------|---------|
| Prioridades ordenadas | Security > Stability > UX |
| Filosofia do projeto | Plugin model, extensibility |
| Contribution size limits | Max LOC por PR |

**Insight:** O CLAUDE.md referencia esses arquivos, mas não duplica. O agente lê sob demanda.

---

## 4. Camada 3 — Regras Distribuídas por Módulo

### Opção A: `.claude/rules/*.md` com frontmatter `paths:`

```markdown
---
paths:
  - "src/api/**/*.ts"
  - "src/middleware/*.ts"
---

# Regras de API
- Validar request body com Zod
- Retornar erros no formato RFC 7807
- Nunca expor stack traces em produção
```

Sem `paths:`, a regra é **sempre** carregada. Com `paths:`, só quando o agente trabalha em arquivos matching.

### Opção B: AGENTS.md distribuídos (por subsistema)

Cada subsistema tem seu próprio AGENTS.md definindo regras de boundary:

```markdown
# [Subsystem] AGENTS.md

## What this module owns
<Responsabilidade única>

## Public surface
<O que pode ser importado de fora>

## Rules
- O que PODE importar
- O que NÃO PODE importar
- O que requer versionamento

## Expansion policy
<Como adicionar novos seams>
```

**Por que distribuir?** Progressive disclosure — o agente carrega o contexto certo quando toca o diretório certo. Economiza context window.

**Nota:** `AGENTS.md` não é convenção oficial Anthropic — `.claude/rules/` com `paths:` é o mecanismo nativo equivalente.

---

## 5. Camada 4 — docs/ (Referência Profunda)

Documentação que o agente consulta sob demanda, mas **não carrega por default**.

### Architecture docs

| Arquivo | Conteúdo |
|---------|----------|
| `docs/architecture.md` | C4 levels (Context, Container, Component), deployment topology |
| `docs/domain-model.md` | Bounded contexts, aggregates, invariants |
| `docs/integration.md` | Pontos de integração, data flows, contratos de API |

**Regra:** Diagramas como código (LikeC4, Mermaid) — nunca imagens binárias sem fonte.

### Security docs (profundidade máxima)

| Arquivo | Conteúdo |
|---------|----------|
| `docs/security/threat-model.md` | MITRE ATT&CK/ATLAS threat model, trust boundaries |
| `docs/security/formal-verification.md` | Provas formais (TLA+/TLC) se aplicável |

**Insight:** Segurança em 4 níveis de profundidade:
CLAUDE.md (regras curtas) → SECURITY.md (política) → docs/security/ (threat model) → provas formais.

### Testing strategy

| Seção | Conteúdo |
|-------|----------|
| Test pyramid | Ratio target (e.g., 70/20/10 unit/integration/e2e) |
| Coverage | Mínimo por módulo (80% critical paths) |
| AI-generated code | Mesma cobertura que código humano — sem exceção |
| O que NÃO testar | Código gerado, internals de third-party |

### Code review guidelines

| Regra | Motivo |
|-------|--------|
| AI-generated code → review **mais rigoroso** | Autor não escreveu linha a linha |
| Verificar: error handling, APIs hallucinated, secrets | AI tende a happy-path code |
| PR deve declarar seções AI-assisted | Transparência |
| Lint + type-check + SCA antes de review humano | Automação primeiro |

---

## 6. Camada 5 — .github/ (Process Gates)

### CODEOWNERS — Quem Aprova o Quê

```
# Security paths → require secops review
src/security/     @team/secops
**/auth*          @team/secops
SECURITY.md       @team/secops

# CODEOWNERS itself → only owner
.github/CODEOWNERS  @owner
```

**Por que importa:** O agente gera o código, mas o PR não é aprovado sem review do owner. Enforcement sem depender da compliance do LLM.

### PR Template

```markdown
## Summary
## Change type (bug fix, feature, refactor, docs)
## Scope (modules affected)
## Security impact assessment:
  - [ ] Handles user input?
  - [ ] Modifies auth/permissions?
  - [ ] Exposes new API endpoints?
  - [ ] Modifies secret handling?
## Test plan
## Risks and mitigations
```

### CI Workflows

| Workflow | Propósito |
|----------|-----------|
| `ci.yml` | Pipeline principal (lint, test, build) |
| `codeql.yml` | CodeQL SAST |
| `dependency-review.yml` | Supply chain scan em PRs |

---

## 7. Camada 6 — Automação (Enforcement Determinístico)

**A camada mais importante.** Tudo que pode ser verificado automaticamente **deve** ser automatizado.

### Pre-commit hooks essenciais

| Hook | O que enforça |
|------|--------------|
| trailing-whitespace | Higiene |
| check-yaml | YAML válido |
| check-merge-conflict | Sem markers |
| detect-secrets | Sem secrets (com baseline) |
| shellcheck | Shell scripts seguros |
| ruff/oxlint | Linting |

### Architecture smell checkers

Scripts AST-based que escaneiam boundaries:
- Re-exports de internals (boundary violation)
- Imports cruzados proibidos
- Rodam no CI automaticamente

### Hooks do Claude Code

| Evento | Uso |
|--------|-----|
| `PostToolUse` | Auto-lint, auto-registro em DB |
| `PreToolUse` | Validação de permissões |
| `UserPromptSubmit` | Injeção de contexto |
| `SessionStart` | Setup de ambiente |

---

## 8. Princípios de Engenharia do Claude Code

### Filosofia: Pragmatismo Radical

| Princípio | Aplicação |
|-----------|-----------|
| **YAGNI** | "Don't add error handling for scenarios that can't happen" |
| **KISS** | "The right amount of complexity is what the task actually requires" |
| **Lean/MVP** | "A bug fix doesn't need surrounding code cleaned up" |

### O que NUNCA fazer

| Regra | Motivo |
|-------|--------|
| Não adicionar docstrings a código não alterado | Escopo mínimo |
| Não criar abstrações prematuras | 3 linhas similares > abstração prematura |
| Não refatorar além do pedido | Blast radius |
| Não usar feature flags desnecessários | Complexidade acidental |
| Não manter código morto | Remover se não usado |
| Não adicionar fallbacks impossíveis | Validar só em boundaries |

### O que SEMPRE fazer

| Regra | Motivo |
|-------|--------|
| Corrigir vulnerabilidades imediatamente | OWASP Top 10 |
| Ler código antes de mudar | Entender contexto |
| Diagnosticar antes de trocar abordagem | Evitar retry cego |
| Verificar reversibilidade de ações | Blast radius framework |

### Blast Radius Framework

| Categoria | Exemplos | Comportamento |
|-----------|----------|---------------|
| Reversível + Local | Editar arquivo, rodar teste | Executa sem perguntar |
| Irreversível + Local | `git reset --hard`, deletar | Pede confirmação |
| Visível externamente | Push, criar PR | Sempre confirma |
| Destrutivo | Force push, drop table | Confirma + alerta |

---

## 9. Git Safety Protocol

| Regra | Motivo |
|-------|--------|
| **NUNCA** `--no-verify` | Investigar e fixar o hook |
| **NUNCA** `push --force` para main | Alertar o usuário |
| **NUNCA** amend sem pedido explícito | Criar NEW commits — protege histórico |
| **NUNCA** `git add .` ou `git add -A` | Risco de incluir .env, credentials |
| Staging por arquivo | `git add specific-file.ts` |
| HEREDOC para commit messages | Formatação correta |

### Workflow de commit

```
1. git status + git diff + git log (paralelo)
2. Analisar mudanças + rascunhar mensagem
3. git add <arquivos> + git commit (paralelo)
4. Se pre-commit hook falhar → fix → NOVO commit (nunca --amend)
```

---

## 10. Segurança — Defense in Depth

### 5 Camadas de Segurança do Claude Code

| Camada | Mecanismo |
|--------|-----------|
| 1 — System prompt | Instrução OWASP Top 10 |
| 2 — Bash security validator | Bloqueia command injection, backtick injection, zsh expansion |
| 3 — Permissões granulares | `settings.json` com allow/deny por comando |
| 4 — Cyber risk instruction | Recusa técnicas destrutivas, DoS, supply chain |
| 5 — Blast radius framework | Classificação por reversibilidade |

### Dependency Management Policy

| Regra | Detalhe |
|-------|---------|
| Sources aprovados | PyPI, npm registry, mirrors internos |
| Update cadence | Security patches < 48h, minor mensal, major trimestral |
| Lock files | Sempre commitados |
| Supply chain | npm provenance, pip `--require-hashes` |
| License allowlist | MIT, Apache-2.0, BSD — flag copyleft para review |
| SCA no CI | Dependabot/Renovate + Snyk/Trivy, block merge em critical CVEs |

---

## 11. Arquitetura de Subagentes

### Quando usar subagente

| Cenário | Usar? |
|---------|-------|
| Pesquisa complexa multi-step | Sim |
| Buscar arquivo específico | Não — Glob/Grep direto |
| Ler 2-3 arquivos conhecidos | Não — Read direto |
| Tarefas paralelas independentes | Sim — múltiplos simultâneos |

### Princípio fundamental

> "Never delegate understanding."

O agente pai entende o problema e fornece contexto completo. O subagente executa, não decide arquitetura.

### Paralelismo

```
Independentes → paralelo (mesma mensagem, múltiplos tool calls)
Dependentes → sequencial (esperar resultado)
NUNCA → placeholders ou chutar valores dependentes
```

---

## 12. Estrutura Recomendada Completa

```
projeto/
├── CLAUDE.md                        # Instrução principal (~200 linhas)
│   @./SECURITY.md                   # Include: política de segurança
│   @./docs/architecture.md          # Include: arquitetura
├── CLAUDE.local.md                  # Overrides pessoais (gitignored)
├── SECURITY.md                      # Trust model, vulnerability policy
├── CONTRIBUTING.md                  # Regras para humanos + AI PRs
├── .claude/
│   ├── settings.json                # Permissões do time (commitado)
│   ├── settings.local.json          # Permissões pessoais (gitignored)
│   ├── commands/                    # Skills invocáveis via /nome
│   ├── knowledge/                   # Referência on-demand
│   ├── rules/
│   │   ├── api-rules.md             # paths: src/api/**
│   │   ├── test-rules.md            # paths: **/*.test.*
│   │   └── security-rules.md        # paths: src/auth/**, src/crypto/**
│   └── memory/
│       └── MEMORY.md                # Índice de memórias
├── .github/
│   ├── CODEOWNERS                   # Path protection
│   ├── pull_request_template.md     # Checklist de qualidade
│   └── workflows/
│       ├── ci.yml                   # Pipeline principal
│       └── codeql.yml               # SAST
├── docs/
│   ├── architecture.md              # C4, deployment, integrations
│   ├── testing-strategy.md          # Pyramid, coverage, AI code rules
│   └── security/
│       └── threat-model.md          # MITRE ATT&CK/ATLAS
└── .pre-commit-config.yaml          # Hooks determinísticos
```

---

## 13. Mapa: Onde Cada Tipo de Regra Vive

### Arquitetura

| Princípio | Onde | Enforcement |
|-----------|------|-------------|
| Boundaries | CLAUDE.md (resumo) + rules/ (detalhe) | AST checker (CI) |
| Protocol evolution | rules/ por subsistema | Schema validators |
| Separation of concerns | rules/ distribuídos | Import rules + linter |

### Segurança

| Aspecto | Onde | Enforcement |
|---------|------|-------------|
| Trust model | SECURITY.md | Policy (review) |
| Threat model | docs/security/ | Review-based |
| Secret scanning | .pre-commit-config.yaml | detect-secrets (CI) |
| Path protection | .github/CODEOWNERS | GitHub required reviews |
| SAST | .github/workflows/ | CodeQL (CI) |

### Qualidade

| Aspecto | Onde | Enforcement |
|---------|------|-------------|
| Style guide | CLAUDE.md | Linters (ruff, oxlint) |
| Coverage | docs/testing-strategy.md | CI test gate |
| File size | CLAUDE.md (~300 LOC) | Manual review |
| PR quality | .github/pull_request_template.md | Human review |

### Processo

| Aspecto | Onde | Enforcement |
|---------|------|-------------|
| Commits | CLAUDE.md | Pre-commit hook |
| PR workflow | CONTRIBUTING.md | Template + review |
| Release | .github/workflows/ | CI gates |

---

## 14. Anti-Patterns a Evitar

| Anti-Pattern | Motivo |
|-------------|--------|
| CLAUDE.md > 40K chars | Modelo perde atenção — truncado silenciosamente |
| Tudo num arquivo só | Sem filtragem contextual |
| Regras críticas no início do CLAUDE.md | Modelo dá mais peso ao que vem depois |
| Comentários HTML `<!-- -->` | Removidos antes da injeção — modelo não vê |
| Duplicar regras entre CLAUDE.md e linters | Manutenção dupla sem benefício |
| Regras operacionais (SSH, deploy) no CLAUDE.md | Pertencem a runbooks |
| Frontmatter sem `paths:` em rules/ | Carregado sempre — polui contexto |
| `@include` com depth > 5 | Ignorado silenciosamente |
| Paths absolutos no conteúdo | Quebram em máquinas diferentes |

---

## 15. Checklist de Implementação

### Obrigatórios (o Claude Code já aplica)

- [ ] Ler código antes de propor mudanças
- [ ] Diagnosticar erros antes de trocar abordagem
- [ ] Não adicionar código além do pedido
- [ ] Validar apenas em boundaries externos
- [ ] Nunca bypass pre-commit hooks
- [ ] Staging por arquivo (nunca `git add .`)
- [ ] Confirmar ações destrutivas/irreversíveis

### Recomendados (adicionar ao projeto)

- [ ] SECURITY.md com trust model e vulnerability policy
- [ ] CONTRIBUTING.md com regras de PR e AI code policy
- [ ] `.claude/rules/` com regras condicionais por path
- [ ] `.github/CODEOWNERS` com path protection
- [ ] `.github/pull_request_template.md` com security assessment
- [ ] `.pre-commit-config.yaml` com detect-secrets + linters
- [ ] `docs/architecture.md` com C4 e deployment topology
- [ ] `docs/testing-strategy.md` com pyramid e coverage rules
- [ ] CI com SAST (CodeQL) e SCA (Dependabot/Snyk)
- [ ] Dependency management policy documentada

---

## 16. Relação Entre Arquivos

```
CLAUDE.md (instrução ao agente)
  │
  ├── @SECURITY.md ──────────── Política de segurança
  │     └── docs/security/ ──── Threat model (profundidade)
  │
  ├── @docs/architecture.md ─── Referência arquitetural
  │     └── model/*.likec4 ──── Diagramas como código
  │
  ├── .claude/rules/ ────────── Regras condicionais por path
  │     ├── api-rules.md
  │     ├── test-rules.md
  │     └── security-rules.md
  │
  ├── .claude/commands/ ─────── Skills invocáveis
  │
  ├── .claude/knowledge/ ────── Referência on-demand
  │
  └── CONTRIBUTING.md ───────── Regras para humanos

.github/ (process gates — independente do agente)
  ├── CODEOWNERS ────────────── Quem aprova o quê
  ├── PR template ───────────── Checklist obrigatório
  └── workflows/ ────────────── CI/CD (enforcement determinístico)

.pre-commit-config.yaml ────── Hooks (enforcement local)
```

**A regra de ouro:** Tudo que pode ser automatizado, automatize. O CLAUDE.md é o **último recurso** — para regras que nenhum linter, hook ou CI check consegue enforçar.
