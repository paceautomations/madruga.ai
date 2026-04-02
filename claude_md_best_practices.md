# Guia para um CLAUDE.md Eficiente

> Baseado nas recomendações de **Boris Cherny** (Head of Claude Code, Anthropic) e na documentação oficial.

---

## Princípio Fundamental

**Só inclua o que o Claude erraria sem a instrução.** Para cada linha, pergunte: "Remover isso causaria erros?" Se não — corte.

---

## Tamanho e Formato

| Regra | Valor |
|-------|-------|
| Tamanho máximo | **< 200 linhas** (docs oficiais) / **~1.000 tokens** (Boris no HN) |
| Formato | Markdown com headers e bullets — Claude escaneia estrutura como um humano |
| Instruções | Concretas e verificáveis: "Use 2-space indentation", não "formate bem o código" |
| Ênfase | `IMPORTANT` / `YOU MUST` só para regras críticas — use com parcimônia |
| Comentários HTML | São removidos antes da injeção no contexto — use para notas humanas sem custo de tokens |

> **Atenção**: Conforme o número de instruções cresce, a compliance cai **uniformemente** — Claude não ignora só as extras, começa a ignorar TUDO. O orçamento prático é ~150-200 instruções (o system prompt já consome ~50).

---

## O que Incluir vs. Excluir

### Incluir

- Comandos bash que Claude não adivinha (build, test, deploy)
- Regras de estilo que diferem do padrão da linguagem
- Instruções de teste e runners preferidos
- Convenções do repo (branches, PRs, commit messages)
- Decisões arquiteturais específicas do projeto
- Quirks do ambiente (env vars obrigatórias, versões)
- Gotchas não-óbvios que causam erros recorrentes

### Excluir

- O que Claude deduz lendo o código (ele lê o codebase)
- Convenções padrão da linguagem (Claude já sabe)
- Documentação de API (linke em vez de copiar)
- Informação que muda frequentemente
- Descrições arquivo-por-arquivo do codebase
- Práticas autoevientes ("escreva código limpo", "trate erros")
- O que linters/hooks já aplicam deterministicamente

---

## Hierarquia de Carregamento

```
/etc/claude-code/CLAUDE.md     → Policy organizacional (não pode ser excluído)
        ↓
~/.claude/CLAUDE.md            → Preferências pessoais (todos os projetos)
        ↓
../../CLAUDE.md                → Parent directories (walking up from cwd)
        ↓
./CLAUDE.md                    → Projeto (compartilhado via git)
        ↓
./subdir/CLAUDE.md             → On-demand (quando Claude lê arquivos dali)
        ↓
.claude/rules/*.md             → Regras modulares com path-scoping
```

**Parent directories** carregam no launch. **Child directories** carregam on-demand. Use isso a seu favor — coloque regras específicas onde elas pertencem.

---

## Estrutura Recomendada

```markdown
# CLAUDE.md

## O que é este projeto
<1-2 frases. Não repita o README — diga o que Claude precisa saber.>

## Comandos Essenciais
<Só os que Claude não adivinha.>

## Convenções
<Regras de estilo, branch naming, commit format — só o que difere do padrão.>

## Arquitetura (se não-óbvia)
<Decisões que impactam como Claude deve escrever código.>

## Gotchas
<Armadilhas específicas que causam erros recorrentes.>
```

---

## Padrões Avançados

### @imports — Mantenha o raiz enxuto

```markdown
# CLAUDE.md
Git workflow: @docs/git-instructions.md
API conventions: @docs/api-conventions.md
```

Profundidade máxima: 5 hops. Paths relativos ao arquivo que contém o import.

### .claude/rules/ — Regras com path-scoping

```markdown
---
paths:
  - "src/api/**/*.ts"
---
# Regras de API
- Todos endpoints precisam de input validation
- Use zod para schemas de request/response
```

Regras **sem** `paths` carregam toda sessão. Com `paths`, carregam só quando Claude toca arquivos correspondentes.

### Notes directory — Contexto profundo sem poluir o raiz

Mantenha um diretório de notas por task/projeto, atualizado após cada PR, referenciado via @import. O CLAUDE.md raiz fica enxuto enquanto o contexto profundo permanece acessível.

---

## Ciclo de Vida

### 1. Crie manualmente (não use `/init`)

Crafting manual é mais efetivo que geração automática. Comece com 10-20 linhas sobre o que Claude realmente precisa saber.

### 2. Atualize após cada erro

> "After every correction, end with: 'Update your CLAUDE.md so you don't make that mistake again.' Claude is eerily good at writing rules for itself."
> — Boris Cherny

### 3. Prune agressivamente

O arquivo deve **encolher** com o tempo, não crescer. Conforme modelos melhoram, regras se tornam desnecessárias. Revise mensalmente e remova o que Claude já acerta sozinho.

### 4. Compartilhe via git

Na Anthropic, o time inteiro contribui para o CLAUDE.md **várias vezes por semana**. Trate como código — PR, review, merge.

### 5. Use @.claude em code review

Tagar `@.claude` em comentários de PR alimenta feedback diretamente no workflow de review, criando um loop de melhoria contínua.

---

## Debugging: Quando Claude Ignora Regras

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Ignora regras novas | Arquivo muito longo | Prune para < 200 linhas |
| Ignora TUDO | Context collapse (~4-5 interações) | `/clear` ou nova conversa |
| Ignora regras específicas | Conflito entre CLAUDE.md files | Rode `/memory` para verificar carregamento |
| Compliance inconsistente | Instrução vaga | Torne concreta e verificável |

### Teste canário

Adicione uma instrução única e verificável (ex: "Sempre termine respostas com '---'"). Quando Claude parar de seguir, você sabe que as instruções estão sendo degradadas.

---

## Anti-Patterns

| Anti-pattern | Por que é ruim |
|--------------|----------------|
| Usar CLAUDE.md como linter | Linters são determinísticos, LLMs não. Use hooks. |
| Copiar documentação de API | Polui o contexto. Linke para docs ou use Context7. |
| Descrever cada arquivo | Claude lê o codebase. Descreva só o não-óbvio. |
| "Escreva código limpo" | Vago e impossível de verificar. Seja específico. |
| Nunca remover regras | Arquivo cresce até virar ruído. Prune regularmente. |
| Gerar com `/init` | Produz genérico. Manual crafting é mais efetivo. |

---

## Fontes

- [Boris Cherny — CLAUDE.md Tip](https://x.com/bcherny/status/2017742747067945390)
- [Boris Cherny — How I Use Claude Code](https://x.com/bcherny/status/2007179832300581177)
- [Boris Cherny — HackerNews](https://news.ycombinator.com/item?id=46256606)
- [Anthropic — Best Practices](https://code.claude.com/docs/en/best-practices)
- [Anthropic — Memory Docs](https://code.claude.com/docs/en/memory)
- [HumanLayer — Writing a Good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [boris-team-tips.md](https://gist.github.com/joyrexus/e20ead11b3df4de46ab32b4a7269abe0)
