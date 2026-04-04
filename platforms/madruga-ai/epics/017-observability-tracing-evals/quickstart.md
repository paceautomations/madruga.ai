# Quickstart: Observability, Tracing & Evals

**Epic**: 017-observability-tracing-evals | **Branch**: `epic/madruga-ai/017-observability-tracing-evals`

## Pre-requisitos

- Python 3.11+
- Node.js 20+ (para portal)
- SQLite 3.35+ (para window functions)
- Daemon dependencies: `pip install fastapi uvicorn structlog pyyaml`
- Portal dependencies: `cd portal && npm install`

## Setup Rapido

### 1. Aplicar migration

A migration 010 e aplicada automaticamente pelo `migrate()` em db.py quando o daemon ou qualquer script inicia. Para verificar manualmente:

```bash
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn, migrate
conn = get_conn()
migrate(conn)
# Verificar tabelas
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('traces' in tables, 'eval_scores' in tables)  # True True
conn.close()
"
```

### 2. Iniciar daemon com endpoints de observabilidade

```bash
# Terminal 1: daemon
python3 .specify/scripts/daemon.py

# Verificar endpoints
curl http://localhost:8040/health
curl http://localhost:8040/api/traces?platform_id=madruga-ai
curl http://localhost:8040/api/stats?platform_id=madruga-ai&days=7
```

### 3. Iniciar portal

```bash
# Terminal 2: portal
cd portal && npm run dev
# Abrir http://localhost:4321/madruga-ai/observability
```

### 4. Executar pipeline para gerar dados

```bash
# Executar um pipeline run (gera trace + spans + evals)
python3 .specify/scripts/dag_executor.py --platform madruga-ai --epic 017-observability-tracing-evals --mode auto

# Ou via daemon (ja rodando)
# Basta ter epic com status='in_progress' no DB
```

## Executar Testes

```bash
# Todos os testes
make test

# Testes especificos de observabilidade
python3 -m pytest .specify/scripts/tests/test_db_observability.py -v
python3 -m pytest .specify/scripts/tests/test_eval_scorer.py -v
python3 -m pytest .specify/scripts/tests/test_daemon_observability.py -v
python3 -m pytest .specify/scripts/tests/test_observability_export.py -v
```

## Validacao End-to-End

### Cenario 1: Trace com metricas

1. Executar pipeline run
2. Verificar no DB:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '.specify/scripts')
   from db import get_conn
   conn = get_conn()
   traces = conn.execute('SELECT * FROM traces ORDER BY started_at DESC LIMIT 1').fetchone()
   print(dict(traces))
   runs = conn.execute('SELECT node_id, tokens_in, cost_usd FROM pipeline_runs WHERE trace_id=?', (traces['trace_id'],)).fetchall()
   for r in runs: print(dict(r))
   conn.close()
   "
   ```
3. Verificar no portal: `http://localhost:4321/madruga-ai/observability` → tab Runs

### Cenario 2: Eval scores

1. Apos pipeline run completo, verificar evals:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '.specify/scripts')
   from db import get_conn
   conn = get_conn()
   scores = conn.execute('SELECT node_id, dimension, score FROM eval_scores ORDER BY evaluated_at DESC LIMIT 20').fetchall()
   for s in scores: print(dict(s))
   conn.close()
   "
   ```
2. Portal: tab Evals → scoreboard com 4 dimensoes por node

### Cenario 3: Export CSV

```bash
curl -o traces.csv "http://localhost:8040/api/export/csv?platform_id=madruga-ai&entity=traces&days=30"
head -5 traces.csv
```

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| `traces` table not found | Migration nao aplicada | Restart daemon ou rodar `migrate()` manualmente |
| Tokens/cost sempre NULL | Claude CLI nao retornou JSON | Verificar `--output-format json` no dispatch. Verificar versao do Claude CLI. |
| CORS error no portal | Daemon sem CORSMiddleware | Verificar que daemon.py tem CORSMiddleware configurado |
| Dashboard vazio | Nenhum trace no DB | Executar pipeline run para gerar dados |
| Eval scores nao gerados | Node falhou (so nodes completed geram evals) | Verificar status dos nodes no trace |
