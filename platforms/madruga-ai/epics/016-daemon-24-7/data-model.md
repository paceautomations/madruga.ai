# Data Model: Daemon 24/7

**Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)

## Entities

Este epic nao introduz novas entidades no banco de dados. O daemon **consome** entidades existentes (definidas nos epics 006, 009, 014) e adiciona campos/queries necessarios para operacao continua.

### Entidades consumidas (read)

| Entidade | Tabela | Campos usados pelo daemon | Definida em |
|----------|--------|---------------------------|-------------|
| Epic | `epics` | epic_id, platform_id, status, priority, branch_name | Epic 006 |
| EpicNode | `epic_nodes` | platform_id, epic_id, node_id, status | Epic 006 |
| PipelineRun | `pipeline_runs` | run_id, platform_id, node_id, epic_id, gate_status, gate_notified_at, telegram_message_id | Epic 006 + 014 |
| PipelineNode | `pipeline_nodes` | platform_id, node_id, status | Epic 006 |
| Event | `events` | entity_type, entity_id, action, payload | Epic 006 |
| LocalConfig | `local_config` | key, value (telegram_last_update_id) | Epic 006 |

### Entidades consumidas (write)

| Entidade | Tabela | Operacoes do daemon |
|----------|--------|---------------------|
| PipelineRun | `pipeline_runs` | INSERT (inicio de node), UPDATE gate_status/gate_notified_at/telegram_message_id |
| EpicNode | `epic_nodes` | UPDATE status (pending→running→done/failed/skipped) |
| PipelineNode | `pipeline_nodes` | UPDATE status |
| Event | `events` | INSERT (gate_notified, gate_resolved, decision_notified, decision_resolved, daemon_started, daemon_stopped, telegram_degraded, telegram_recovered) |
| LocalConfig | `local_config` | UPDATE telegram_last_update_id |

### Novos eventos do daemon

| Evento | entity_type | action | payload |
|--------|-------------|--------|---------|
| Daemon iniciou | daemon | daemon_started | `{"version": "1.0", "pid": N}` |
| Daemon parou | daemon | daemon_stopped | `{"reason": "signal/error", "uptime_s": N}` |
| Telegram degradado | daemon | telegram_degraded | `{"failed_checks": N}` |
| Telegram recuperado | daemon | telegram_recovered | `{"downtime_s": N}` |
| Epic dispatch iniciado | epic | epic_dispatch_started | `{"epic_id": "...", "node_count": N}` |
| Epic dispatch completo | epic | epic_dispatch_completed | `{"epic_id": "...", "nodes_executed": N}` |
| Circuit breaker abriu | daemon | circuit_breaker_opened | `{"failures": N}` |
| Circuit breaker fechou | daemon | circuit_breaker_closed | `{"recovery_time_s": N}` |

### State Machine: Daemon

```
starting → running → degraded → shutting_down → stopped
              ↑          │
              └──────────┘  (Telegram recovered)
```

| Estado | Descricao | Telegram | Auto gates | Human gates |
|--------|-----------|----------|------------|-------------|
| starting | Inicializando servicos | Conectando | Nao | Nao |
| running | Operacao normal | Ativo | Sim | Sim |
| degraded | Telegram unreachable | Inativo | Sim | Pausados |
| shutting_down | Recebeu SIGTERM/SIGINT | N/A | Cancelando | N/A |
| stopped | Processo encerrado | N/A | N/A | N/A |

### State Machine: Epic (transicoes relevantes para o daemon)

```
proposed → in_progress → shipped
              │
              ├→ blocked (node falhou / gate rejeitado)
              └→ waiting_approval (human gate)
```

O daemon monitora a transicao `proposed → in_progress` (trigger manual via CLI/Telegram) e gerencia as demais automaticamente.

## Queries criticas do daemon

### Poll epics prontos
```sql
SELECT epic_id, platform_id, priority, branch_name
FROM epics
WHERE status = 'in_progress'
ORDER BY priority ASC, rowid ASC
```

### Poll gates pendentes (reutiliza telegram_bot.py)
```sql
SELECT run_id, platform_id, epic_id, node_id, gate_status, gate_notified_at, started_at
FROM pipeline_runs
WHERE gate_status = 'waiting_approval' AND gate_notified_at IS NULL
ORDER BY started_at
```

### Checkpoint: ultimo node completo de um epic
```sql
SELECT node_id FROM epic_nodes
WHERE platform_id = ? AND epic_id = ? AND status = 'done'
```

## Nao ha novas tabelas ou migrations

O daemon opera 100% sobre o schema existente. Os eventos novos (daemon_started, etc.) usam a tabela `events` generica ja existente.
