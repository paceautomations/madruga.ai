---
title: "Research: DAG Executor + SpeckitBridge"
updated: 2026-03-31
---
# Research: DAG Executor + SpeckitBridge

## Decisoes Tecnicas

### 1. Kahn's Algorithm

- **Decisao**: Usar Kahn's algorithm para topological sort
- **Racional**: O(V+E), determinístico, detecta ciclos naturalmente (~30 LOC). Para 24 nodes e bem mais que suficiente.
- **Alternativas**: DFS recursivo (nao detecta ciclos tao elegantemente), priority queue (desnecessaria sem paralelismo)

### 2. Circuit Breaker Pattern

- **Decisao**: Implementar como classe simples com 3 estados (closed/open/half-open)
- **Racional**: Blueprint define 5 falhas → open, 300s → half-open. Estado in-memory, reseta entre runs.
- **Alternativas**: Persistir em SQLite (overkill — executor e processo curto), biblioteca tenacity (dep nova)

### 3. Subprocess Dispatch

- **Decisao**: `subprocess.run()` com `timeout` parameter nativo do Python
- **Racional**: Python 3.11 subprocess.run ja implementa watchdog internamente (SIGKILL apos timeout). Nao precisa de thread separada.
- **Alternativas**: subprocess.Popen + threading.Timer (mais complexo, mesmo resultado)

### 4. Prompt Composition Strategy

- **Decisao**: compose_skill_prompt() como funcao unica que roteia por skill type
- **Racional**: Implementar em implement_remote.py (ja tem compose_prompt). L1 skills: instrucao + artefatos deps. L2 skills: reutiliza compose_prompt existente para implement, variantes para outros.
- **Alternativas**: Template files por skill (overengineering), classes por skill type (abstraction prematura)

## Nada Mais a Pesquisar

Todas as tecnologias (Python stdlib, SQLite, pyyaml, subprocess) ja sao usadas no projeto. ADR-017 ja documenta a decisao arquitetural. Nenhuma clarificacao pendente.
