---
description: Gera/atualiza STATE.md com progresso da sessao atual — tasks, decisoes, problemas, proximos passos
arguments:
  - name: platform
    description: "Nome da plataforma/produto."
    required: false
  - name: context
    description: "Contexto breve da sessao (ex: 'wave 3 implementation')."
    required: false
argument-hint: "[plataforma] [contexto-da-sessao]"
---

# Checkpoint — Estado da Sessao

Skill leve. Gera ou atualiza STATE.md com progresso da sessao: tasks completadas, decisoes, problemas e proximos passos. Baseado em dados reais (git log, tasks.md, filesystem).

## Regra Cardinal: ZERO Informacao Inventada

Tudo baseado em git log, tasks.md e filesystem real. Nenhuma suposicao.

## Persona

Session Recorder. Factual, conciso. Portugues BR.

## Uso

- `/checkpoint wave 3` — Checkpoint da sessao com contexto
- `/checkpoint` — Checkpoint generico

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill checkpoint` e parsear JSON (se plataforma fornecida).
- Ler `.specify/memory/constitution.md`.
- Verificar se tasks.md existe (spec dir ou raiz).

### 1. Coletar Dados

- STATE.md existente (se houver — para append)
- tasks.md — tasks marcadas [X]
- `git log --oneline -20` — commits recentes
- `git diff --stat` — arquivos alterados

### 2. Gerar/Atualizar STATE.md

Se STATE.md existe, adicionar nova sessao. Se nao, criar.

```markdown
# STATE — [Feature/Context]

**Session**: YYYY-MM-DD
**Branch**: `branch-name`

## Concluido

[Tasks marcadas [X] nesta sessao]

## Decisoes Tomadas

[Decisoes tomadas e por que — extrair de commits/contexto]

## Problemas e Solucoes

[Problemas encontrados e como resolvidos]

## Proximos Passos

[Derivado das tasks pendentes]

## Arquivos Alterados

[Lista de arquivos criados/modificados]
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todas tasks [X] tem commits correspondentes? | Verificar git log |
| 2 | Nenhuma informacao inventada? | Cruzar com git log/filesystem |
| 3 | Proximos passos derivados de tasks pendentes reais? | Verificar tasks.md |

### 4. Gate: Auto

Sem aprovacao humana. Salvar imediatamente.

### 5. Salvar + Relatorio

```
## Checkpoint salvo

**Arquivo:** [path/STATE.md]
**Tasks done esta sessao:** <N>
**Proximos passos:** <N>
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Sem tasks.md | Criar STATE.md minimo baseado em git log |
| Sem git repo | Criar STATE.md baseado apenas em filesystem |
