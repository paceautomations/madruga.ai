---
status: accepted
title: "ADR-004: Git File-Based Storage"
---
# ADR-004: Git File-Based Storage como Persistencia Primaria
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O sistema gera e gerencia artefatos de documentacao (specs, plans, ADRs, epics, modelos LikeC4). Estes artefatos sao texto/markdown e precisam de: versionamento com historico, diff legivel, code review via PR, e acesso por humanos e LLMs. A persistencia precisa ter zero overhead operacional — sem servidor de banco, sem migrations, sem backups.

## Decisao

We will use git as the primary storage for all documentation artifacts, with SQLite only for lightweight operational data (epic tracking, pattern learning, metrics).

## Alternativas consideradas

### PostgreSQL
- Pros: queries complexas, ACID, escalavel, ecossistema rico
- Cons: overhead operacional (servidor, migrations, backups), overkill para documentos texto, perde versionamento git nativo, diff de documentos em DB e ruim

### MongoDB
- Pros: schema flexivel (bom para documentos variados), queries em JSON
- Cons: mesmo overhead operacional que PostgreSQL, perde git history, nao integra com code review (PRs), hosting necessario

### Cloud DB (Firestore, DynamoDB)
- Pros: serverless, escalavel, zero ops de infraestrutura
- Cons: vendor lock-in, custo recorrente, perde git history e code review, latencia de rede para operacoes locais, documentos nao sao editaveis em editor de texto

## Consequencias

- [+] Zero overhead operacional — git ja e usado, nenhum servidor adicional
- [+] Versionamento nativo com historico completo, blame, bisect
- [+] Code review de artefatos via PRs — processo familiar para engenheiros
- [+] Artefatos sao plain text — editaveis em qualquer editor, legiveis por LLMs
- [+] Backup automatico (push para remote) sem configuracao adicional
- [-] Sem queries complexas — nao da para fazer "todos os ADRs com status X across platforms" facilmente
- [-] SQLite necessario como complemento para dados operacionais (kanban state, metrics)
- [-] Conflitos de merge em markdown podem ocorrer com edits concorrentes
