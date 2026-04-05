---
title: 'ADR-012: SQLite WAL Mode'
status: Accepted
decision: We will use SQLite WAL (Write-Ahead Logging) mode with busy_timeout=5000ms
  and foreign_keys=ON for all database connections.
alternatives: Default journal mode (DELETE), PostgreSQL
rationale: Leituras concorrentes sem bloqueio (dashboard funciona durante pipeline
  writes)
---
# ADR-012: SQLite WAL Mode
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O Madruga AI usa SQLite para persistencia operacional (epics, usage_log, debates, decisions, patterns, learning, persona_accuracy). O easter (writer) e o dashboard (reader) acessam o banco concorrentemente. SQLite em modo default (journal mode DELETE) serializa todas as operacoes, causando bloqueios quando o dashboard tenta ler durante uma escrita do pipeline.

## Decisao

We will use SQLite WAL (Write-Ahead Logging) mode with busy_timeout=5000ms and foreign_keys=ON for all database connections.

## Alternativas consideradas

### Default journal mode (DELETE)
- Pros: simples, sem arquivos extras.
- Cons: serializa reads e writes, dashboard bloqueia durante writes do pipeline.

### PostgreSQL
- Pros: MVCC nativo, queries complexas, escalavel.
- Cons: overhead operacional massivo para um sistema single-operator local, requer servidor, migrations, backups.

## Consequencias

- [+] Leituras concorrentes sem bloqueio (dashboard funciona durante pipeline writes)
- [+] Writes serializados mas com busy_timeout generoso (5s)
- [+] Zero overhead operacional (SQLite e um arquivo)
- [+] Foreign keys enforced para integridade referencial
- [-] Arquivos -wal e -shm criados junto ao .db (3 arquivos em vez de 1)
- [-] WAL pode crescer se nao houver checkpoints regulares
