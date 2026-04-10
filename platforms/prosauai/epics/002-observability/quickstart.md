# Quickstart — Epic 002: Observability

**Branch**: `epic/prosauai/002-observability` | **Date**: 2026-04-10

## Pré-requisitos

- Docker + Docker Compose
- Python 3.12+
- Supabase Postgres acessível (local ou cloud)
- `.env` configurado (copiar de `.env.example`)

## Setup Local (Dev)

### 1. Subir Stack Completa
```bash
docker compose up -d
```

Containers: `prosauai-api` (8050), `redis` (6379), `phoenix` (6006/4317).

### 2. Verificar Health
```bash
curl http://localhost:8050/health
# {"status": "ok", "redis": true, "observability": {"status": "ok", "last_export_success": true}}
```

### 3. Acessar Phoenix UI
```
http://localhost:6006
```

## Como Debugar uma Mensagem

### Por message_id (via logs)
```bash
# 1. Encontrar trace_id no log
docker logs prosauai-api 2>&1 | grep '"message_id":"BAE5..."' | jq '.trace_id'
# → "abc123def456..."

# 2. Abrir no Phoenix
# http://localhost:6006 → Search → trace_id = abc123def456...
```

### Por trace_id (via Phoenix)
```
Phoenix UI → Traces → Filter by trace_id
→ Waterfall: webhook → parse → route → debounce.append → debounce.flush → echo
→ Cada span mostra duração, atributos, status
```

### Correlação Log↔Trace
```bash
# Dado um trace_id do Phoenix, encontrar todos os logs:
docker logs prosauai-api 2>&1 | grep '"trace_id":"abc123def456"'
```

## Configuração do Sampling

```bash
# .env
OTEL_SAMPLER_ARG=1.0    # 100% (dev)
OTEL_SAMPLER_ARG=0.1    # 10% (prod)
```

## Testes

```bash
# Rodar testes (OTel desabilitado por default)
pytest

# Rodar testes de observability especificamente
pytest tests/ -k "test_otel or test_trace or test_span"
```

## Troubleshooting

| Sintoma | Causa | Solução |
|---------|-------|---------|
| Sem traces no Phoenix | Exporter não conectou | Verificar `PHOENIX_GRPC_ENDPOINT` no `.env` |
| Phoenix UI não carrega | Container não subiu | `docker compose logs phoenix` |
| Logs sem trace_id | OTel não configurado | Verificar `OTEL_ENABLED=true` no `.env` |
| Warning "TracerProvider already set" | Hot reload uvicorn | Normal em dev, ignorar |
| API lento após instrumentação | Overhead OTel | Verificar sampling rate, não deve passar 5ms p95 |
