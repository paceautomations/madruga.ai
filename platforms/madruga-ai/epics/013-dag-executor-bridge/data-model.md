---
title: "Data Model: DAG Executor + SpeckitBridge"
updated: 2026-03-31
---
# Data Model: DAG Executor + SpeckitBridge

## Extensao do Schema Existente

Nenhuma tabela nova. Apenas 3 colunas adicionadas a `pipeline_runs`:

### Migration 007: gate_fields

```sql
ALTER TABLE pipeline_runs ADD COLUMN gate_status TEXT
    CHECK (gate_status IN ('waiting_approval', 'approved', 'rejected'));
ALTER TABLE pipeline_runs ADD COLUMN gate_notified_at TEXT;
ALTER TABLE pipeline_runs ADD COLUMN gate_resolved_at TEXT;
```

### Entidades In-Memory (nao persistidas)

| Entidade | Atributos | Lifecycle |
|----------|-----------|-----------|
| Node | id, skill, outputs, depends, gate, layer, optional, skip_condition | Parse-time (do YAML) |
| CircuitBreaker | state (closed/open/half-open), failure_count, last_failure_at, max_failures, recovery_seconds | Runtime (in-memory, reseta entre runs) |

### Tabelas Utilizadas (existentes)

| Tabela | Uso no Executor |
|--------|----------------|
| pipeline_nodes | L1: ler/gravar estado de nodes |
| epic_nodes | L2: ler/gravar estado de nodes |
| pipeline_runs | Registrar execucoes, gate state |
| platforms | Resolver platform_id |
| epics | Resolver epic_id para L2 |
