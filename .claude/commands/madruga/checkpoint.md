---
description: Gera/atualiza STATE.md com progresso da sessao atual — tasks, decisoes, problemas, proximos passos
arguments:
  - name: context
    description: "Contexto breve da sessao (ex: 'wave 3 implementation')."
    required: false
argument-hint: "[contexto-da-sessao]"
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

Verificar se tasks.md existe (spec dir ou raiz). Minimo necessario.

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

## Completed

[Tasks marcadas [X] nesta sessao]

## Decisions Made

[Decisoes tomadas e por que — extrair de commits/contexto]

## Problems & Solutions

[Problemas encontrados e como resolvidos]

## Next Steps

[Derivado das tasks pendentes]

## Files Touched

[Lista de arquivos criados/modificados]
```

### 3. Gate: Auto

Sem aprovacao humana. Salvar imediatamente.

### 4. Salvar + Relatorio

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
