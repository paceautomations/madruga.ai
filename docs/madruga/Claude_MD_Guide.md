# Manual: Como Criar um CLAUDE.md de Alto Nível

> Guia consolidado com recomendações oficiais da Anthropic, análise do source code do Claude Code v2.1.88, e lições do ecossistema madruga.ai.

**Regra de ouro:** para cada linha, pergunte _"remover isso causaria erros?"_ — se não, corte.

---

## 1. Limites Técnicos

| Parâmetro | Valor | Consequência |
|-----------|-------|--------------|
| Tamanho máximo por arquivo | **40.000 chars** | Truncado silenciosamente |
| Linhas recomendadas | **< 200** | Compliance cai uniformemente com tamanho |
| Profundidade de `@include` | **5 níveis** | Ignorado silenciosamente após 5 |
| MEMORY.md | **~200 linhas** | Truncado após 200 |
| Comentários HTML | **Removidos** | Modelo nunca vê `<!-- -->` |
| Frontmatter YAML | **Processado e removido** | Usar para `paths:` em rules |

---

## 2. Hierarquia de Carregamento

Arquivos carregados **depois** recebem **mais atenção** do modelo:

| # | Tipo | Localização | Versionado | Prioridade |
|---|------|------------|------------|------------|
| 1 | Managed | `/etc/claude-code/CLAUDE.md` | Admin IT | Menor |
| 2 | User | `~/.claude/CLAUDE.md` | Pessoal | ↓ |
| 3 | Project | `CLAUDE.md` (raiz do repo) | Sim | ↓ |
| 4 | Project (alt) | `.claude/CLAUDE.md` | Sim | ↓ |
| 5 | Project Rules | `.claude/rules/*.md` | Sim | ↓ |
| 6 | Local | `CLAUDE.local.md` | Não (.gitignore) | **Maior** |

**Implicação:** regras que nunca devem ser ignoradas vão no `CLAUDE.local.md` ou no **final** do `CLAUDE.md`.

---

## 3. Estrutura Recomendada

### Template Base (~50 linhas)

```markdown
# CLAUDE.md — [Nome do Projeto]

## O que é
<1-2 frases. O que Claude NÃO deduz do código.>

## Comandos essenciais
<Só os que Claude não adivinha: build, test, lint.>

## Convenções
<Regras que diferem do padrão da linguagem.>

## Arquitetura (se não-óbvia)
<Boundaries e decisões que impactam geração de código.>

## Gotchas
<Armadilhas específicas que causam erros recorrentes.>
```

### Diretório `.claude/`

```
.claude/
├── CLAUDE.md                  # Alternativo ao root
├── settings.json              # Permissões do time (commitado)
├── settings.local.json        # Permissões pessoais (gitignored)
├── commands/                  # Skills invocáveis via /nome
├── agents/                    # Agentes especializados
├── rules/                     # Regras com path-scoping
│   ├── api-rules.md           # paths: src/api/**
│   └── security.md            # paths: src/auth/**
└── memory/
    └── MEMORY.md              # Índice de memórias
```

---

## 4. Seções Essenciais — Referência

| Seção | O que incluir | Exemplo |
|-------|---------------|---------|
| **Vocabulário** | Termos com significado específico no projeto | `"gate" = check que deve estar green` |
| **Boundaries** | Fronteiras arquiteturais + docs + rules | `Extensions MUST import only from plugin-sdk/*` |
| **Coding Standards** | Só regras que linters **não** aplicam | `Discriminated unions para branching runtime` |
| **Patterns** | Padrões obrigatórios do projeto | `Result<T,E> para operações falíveis` |
| **Anti-patterns** | Proibições explícitas (mais eficaz que positivas) | `NUNCA: magic strings para branching` |
| **Testes** | Framework, coverage, cleanup, performance | `Cleanup: timers, mocks, env, sockets` |
| **Gates** | Quando rodar o quê | `Local: make check / Landing: make test` |
| **Segurança** | Secrets, CODEOWNERS, validation | `NUNCA commitar secrets reais` |
| **Git** | Commit format, branch naming | `feat:, fix:, chore: — rebase only` |

Para boundaries, documentar 3 coisas: **docs** (onde está documentado), **definition files** (onde implementado), **rules** (o que pode importar de onde).

---

## 5. @include e Path-Scoping

### @include — Progressive Disclosure

```markdown
@./docs/architecture.md         # relativo ao arquivo
@~/personal-rules.md            # relativo ao home
@/etc/company/standards.md      # path absoluto
```

Limite: 5 níveis. Deduplicação por inode (symlinks resolvidos).

### .claude/rules/ — Regras Condicionais

```markdown
---
paths:
  - "src/api/**/*.ts"
---
# Regras de API
- Validar request body com Zod
- Retornar erros no formato RFC 7807
```

Sem `paths:` → carregada **sempre** (polui contexto). Com `paths:` → só quando trabalhando em arquivos que dão match.

---

## 6. Permissões (settings.json)

| Arquivo | Escopo | Versionado |
|---------|--------|------------|
| `~/.claude/settings.json` | Global | Não |
| `.claude/settings.json` | Projeto (time) | Sim |
| `.claude/settings.local.json` | Projeto (pessoal) | Não |

```json
{
  "permissions": {
    "allow": ["Read", "Bash(npm run test)", "Bash(git:*)"],
    "deny": ["Bash(rm -rf:*)"]
  }
}
```

---

## 7. Hooks — 10 Eventos

| Evento | Quando |
|--------|--------|
| `PreToolUse` / `PostToolUse` | Antes/depois de executar tool |
| `PreCompact` / `PostCompact` | Antes/depois de compactar contexto |
| `Stop` | Agente para |
| `Notification` | Em notificações |
| `SessionStart` | Início de sessão |
| `UserPromptSubmit` | Usuário envia prompt |
| `PermissionRequest` | Pedido de permissão |
| `PostToolUseFailure` | Tool falha |

Tipos: `command` (shell), `prompt` (instrução ao modelo), `agent` (subagente).

---

## 8. Ciclo de Vida

- **Crie manualmente** — `/init` gera conteúdo genérico. Comece com 10-20 linhas.
- **Atualize após erros** — corrija o erro, adicione a regra que previne recorrência.
- **Prune mensal** — remova regras que o agente já acerta ou que linters aplicam.
- **Teste canário** — adicione instrução única e verificável. Se ignorada, arquivo está grande demais.

---

## 9. Incluir vs. Excluir

| Incluir | Excluir |
|---------|---------|
| Comandos não-óbvios (build, test) | O que Claude deduz do código |
| Regras de estilo não-padrão | Convenções padrão da linguagem |
| Boundaries arquiteturais | Documentação de API (linke ou Context7) |
| Convenções do repo (commits, branches) | Info que muda frequentemente |
| Gotchas recorrentes | Descrições arquivo-por-arquivo |
| Vocabulário do projeto | Instruções vagas ("escreva código limpo") |
| Quirks do ambiente | O que linters/hooks já aplicam |

---

## 10. Anti-Patterns

| Anti-pattern | Problema |
|--------------|----------|
| CLAUDE.md > 40K chars | Truncado silenciosamente (`MAX_MEMORY_FILE_SIZE`) |
| Comentários HTML para "esconder" texto | Removidos por `stripHTMLComments()` — modelo nunca vê |
| Regras críticas no **início** do arquivo | Modelo dá mais peso ao que vem **depois** |
| Rules sem `paths:` em `.claude/rules/` | Carregada sempre — polui contexto não-relacionado |
| `@include` com depth > 5 | Silenciosamente ignorado |
| Usar CLAUDE.md como linter | LLMs não são determinísticos — use hooks reais |
| Descrever cada arquivo | Claude lê o codebase |
| Gerar com `/init` | Produz conteúdo genérico |
| Nunca remover regras | Arquivo vira ruído — prune mensal |
| Duplicar regras do linter | Sem valor — se linter aplica, não repita |

---

## 11. Debugging

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Ignora regras novas | Arquivo muito longo | Prune para < 200 linhas |
| Ignora TUDO | Context collapse | `/clear` ou nova conversa |
| Ignora regras específicas | Conflito entre CLAUDE.md files | `/memory` para verificar |
| Compliance inconsistente | Instrução vaga | Tornar concreta e verificável |
| Viola boundaries | Boundary não definida | Adicionar docs + definition files + rules |

---

## Fontes

- [Anthropic — Best Practices](https://code.claude.com/docs/en/best-practices)
- [Anthropic — Memory Docs](https://code.claude.com/docs/en/memory)
- [Boris Cherny — CLAUDE.md Tips](https://x.com/bcherny/status/2017742747067945390)
- [HumanLayer — Writing a Good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Claude Code Source Analysis (v2.1.88)](https://github.com/chatgptprojects/clear-code)
