# Contract: Retention CLI

**Tipo**: CLI (Command-Line Interface)
**Módulo**: `prosauai.ops.retention_cli`
**Consumidor**: Container `retention-cron` (Docker) + operador manual

## Interface

```bash
python -m prosauai.ops.retention_cli [OPTIONS]
```

### Opções

| Flag | Tipo | Default | Descrição |
|---|---|---|---|
| `--dry-run` | bool | `true` | Listar o que seria purgado sem executar |
| `--database-url` | string | `$DATABASE_URL` | Connection string Postgres (deve ter BYPASSRLS) |
| `--log-level` | string | `INFO` | Nível de log (DEBUG, INFO, WARN, ERROR) |

### Exit Codes

| Código | Significado |
|---|---|
| 0 | Sucesso (purge completo ou dry-run listado) |
| 1 | Erro de conexão com Postgres |
| 2 | Erro durante purge (parcial — logs indicam ponto de falha) |

### Output (stdout — structlog JSON)

```json
{"event": "retention_run_start", "run_id": "uuid", "dry_run": true, "timestamp": "..."}
{"event": "retention_check", "table": "messages", "partitions_eligible": 2, "estimated_rows": 15420, "dry_run": true}
{"event": "retention_check", "table": "conversations", "rows_eligible": 342, "dry_run": true}
{"event": "retention_check", "table": "eval_scores", "rows_eligible": 1203, "dry_run": true}
{"event": "retention_run_complete", "run_id": "uuid", "duration_ms": 1234, "dry_run": true}
```

Quando `--dry-run=false`:

```json
{"event": "retention_run_start", "run_id": "uuid", "dry_run": false}
{"event": "partition_dropped", "table": "messages", "partition": "messages_2026_01", "rows_removed": 8721}
{"event": "rows_purged", "table": "conversations", "rows_removed": 342, "batch_size": 1000}
{"event": "rows_purged", "table": "eval_scores", "rows_removed": 1203, "batch_size": 1000}
{"event": "partitions_created", "table": "messages", "partitions": ["messages_2026_07", "messages_2026_08"]}
{"event": "retention_run_complete", "run_id": "uuid", "duration_ms": 5678, "total_rows_purged": 10266, "partitions_dropped": 1, "partitions_created": 2}
```

## Regras de Retention (ADR-018)

| Tabela | Retention Default | Método de Purge | Configurável por Tenant |
|---|---|---|---|
| `prosauai.messages` (partições) | 90 dias | `DROP TABLE partition` (DDL) | Sim (futuro) |
| `prosauai.conversations` (closed) | 90 dias | `DELETE WHERE closed_at < threshold` em batch (1000 rows) | Sim (futuro) |
| `prosauai.eval_scores` | 90 dias | `DELETE WHERE created_at < threshold` em batch (1000 rows) | Não |
| Phoenix traces (schema observability) | 90 dias | `DELETE FROM spans WHERE start_time < threshold` | Não |
| `admin.audit_log` | 365 dias | **NUNCA purge automático** | N/A |

## Invariantes

1. **Dry-run é default**: Execução sem `--dry-run=false` nunca deleta dados
2. **UTC everywhere**: Todas as comparações de data usam `now() AT TIME ZONE 'UTC'`
3. **Idempotente**: Re-execução não causa efeitos colaterais
4. **Audit-log intocável**: Nunca purga `admin.audit_log` independente do flag
5. **Batch deletes**: DELETEs em tabelas não-particionadas usam `LIMIT 1000` por iteração para limitar lock duration
