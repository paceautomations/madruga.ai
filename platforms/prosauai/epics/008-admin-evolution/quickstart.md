# Quickstart — Epic 008 Admin Evolution

Guia rápido para desenvolver, executar e validar localmente o admin evoluído.

---

## Pré-requisitos

- Node.js 20+, pnpm 9+
- Python 3.12
- Docker + Docker Compose (Postgres + Redis)
- `dbmate` instalado (`brew install dbmate` ou equivalente)
- Branch `epic/prosauai/008-admin-evolution` checked-out no repo `paceautomations/prosauai`
- `.env` configurado com `DATABASE_URL`, `REDIS_URL`, `ADMIN_JWT_SECRET`, `NEXT_PUBLIC_API_URL=http://localhost:8050`

---

## Setup

```bash
# 1. Clonar e mudar para branch
cd ~/repos/paceautomations/prosauai
git checkout epic/prosauai/008-admin-evolution
git pull origin epic/prosauai/008-admin-evolution

# 2. Instalar deps
pnpm install
cd apps/api && uv sync
cd ../..

# 3. Subir infra local
docker compose up -d postgres redis

# 4. Aplicar migrations (incluindo as 4 novas deste epic)
cd apps/api
dbmate up
cd ../..

# 5. Rodar backfill (primeira vez apenas)
python apps/api/scripts/backfill_last_message.py

# 6. Rodar API
cd apps/api && uvicorn prosauai.main:app --reload --port 8050

# 7. Em outro terminal, rodar frontend
cd apps/admin && pnpm dev  # → http://localhost:3000
```

---

## Validação funcional — User Stories

### US1 — Inspecionar conversa sem SQL

```bash
# 1. Login em http://localhost:3000/login
# 2. Navegar para /conversations
# 3. Buscar por nome (ex: "João")
# 4. Clicar na conversa → ver thread + perfil do contato
# 5. Verificar: metadados AI expansíveis com latência/tokens/QS
```

**Critério de sucesso**: <30 s do login ao thread completo (SC-001).

### US2 — Debug pipeline via trace waterfall

```bash
# 1. Em uma conversa, clicar "Ver trace" em uma mensagem AI
# 2. Verificar waterfall das 12 etapas com barras proporcionais
# 3. Expandir step dominante → ver input/output JSON
# 4. Se houver erro, verificar step com destaque vermelho
```

**Critério**: <30 s para identificar etapa dominante (SC-002).

### US3 — Performance AI

```bash
# 1. Navegar para /performance
# 2. Selecionar período 7d + tenant=pace-internal
# 3. Verificar 4 KPIs + 5 gráficos (intent, quality, latency, heatmap, cost)
# 4. Verificar Cache-Control: max-age=300 no response header
```

### US4 — Overview

```bash
# 1. Abrir / (Overview)
# 2. Verificar 6 KPI cards com sparklines + deltas coloridos
# 3. Verificar System Health (API/PG/Redis/Evolution/Phoenix)
# 4. Verificar Live Activity Feed atualiza a cada 15s
```

**Critério**: <10 s para identificar componente degradado (SC-003).

### US5 — Audit rotas e DROPs

```bash
# 1. Navegar para /routing
# 2. Filtrar decision_type=DROP
# 3. Clicar em decisão → ver MessageFacts + matched_rule em JSON
```

---

## Testes

```bash
# Backend unit
cd apps/api
pytest tests/unit/conversation/test_pipeline_instrumentation.py -v
pytest tests/unit/router/test_routing_persistence.py -v
pytest tests/unit/conversation/test_pricing.py -v

# Backend integration (requer PG via testcontainers)
pytest tests/integration/admin/ -v

# Suite completa (hard gate SC-007)
pytest tests/ -v  # 100% GREEN requerido

# Frontend unit
cd apps/admin
pnpm test

# E2E Playwright
cd apps/admin
pnpm playwright test
```

**Gate de merge PR 2** (pipeline instrumentation): todos os testes dos epics 004 + 005 passando.

---

## Benchmarks esperados

| Endpoint | P95 meta | Sem cache | Com cache |
|----------|----------|-----------|-----------|
| GET /admin/conversations (10k) | <300 ms | ~80 ms | N/A |
| GET /admin/traces (50k) | <300 ms | ~120 ms | N/A |
| GET /admin/metrics/performance (30d) | <2 s / <200 ms | ~1.5 s | ~50 ms |
| GET /admin/metrics/overview | <500 ms | ~200 ms | N/A |
| GET /admin/metrics/activity-feed | <300 ms | ~80 ms | ~20 ms (Redis 10s) |

Pipeline overhead (instrumentação): **<10 ms p95** (SC-006). Medir com:

```bash
# Staging A/B
export INSTRUMENTATION_ENABLED=false && ab -n 1000 ... > before.txt
export INSTRUMENTATION_ENABLED=true && ab -n 1000 ... > after.txt
diff before.txt after.txt
```

---

## Troubleshooting

### Traces não aparecem em /admin/traces

1. Verificar `asyncpg` log: `tail -f apps/api/logs/api.log | grep trace_persist`
2. Confirmar OTel ativo: `curl http://localhost:8050/health | jq .trace_id` → deve retornar hex
3. Verificar fire-and-forget: `SELECT COUNT(*) FROM traces;` aumenta após mensagens processadas
4. Se falha silenciosa: `grep "trace_persist_failed" apps/api/logs/api.log`

### Listagem de conversas lenta

1. Verificar backfill rodou: `SELECT COUNT(*) FROM conversations WHERE last_message_at IS NULL;` → deve ser próximo de 0
2. Verificar índice: `\d+ conversations` → `idx_conversations_tenant_last_msg` presente
3. Analisar plan: `EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM conversations WHERE tenant_id = '...' ORDER BY last_message_at DESC LIMIT 50;`

### Performance endpoint >2s

1. Verificar cache hit: `redis-cli GET "admin:perf:performance:all:7d:*"` (hash do params)
2. Se sempre miss: checar `CACHE_TTL` env → deve ser 300
3. Se cache quente e ainda lento: SQL analyzer — índice BRIN em traces.started_at pode não estar sendo usado

### Login redireciona em loop

1. Verificar `admin_token` cookie no DevTools → httpOnly? domain?
2. `jwt.decode(token)` local → exp não expirou?
3. Backend log: `grep "401" apps/api/logs/api.log | tail`

---

## Docs úteis

- [spec.md](./spec.md) — requirements funcionais
- [research.md](./research.md) — decisões técnicas com alternativas
- [data-model.md](./data-model.md) — schemas + migrations
- [contracts/openapi.yaml](./contracts/openapi.yaml) — API completa
- [pitch.md](./pitch.md) — contexto Shape Up
- [reference-spec.md](./reference-spec.md) — ground truth dos layouts
- [benchmarks/inbox_list_query.md](./benchmarks/inbox_list_query.md) — query plan esperado para inbox listing (SC-005)

---

## Validação final (dry-run) — Phase 11

Checklist de validação funcional a rodar antes do merge para `main`. Cada item
é independente e reproduz critério de sucesso do spec.

### SC-001 — Localizar conversa em <30s (US1)

```bash
# 1. Clock start
# 2. Login em http://localhost:3000/login
# 3. Navegar /admin/conversations
# 4. Buscar "João" (nome conhecido do seed)
# 5. Clicar na conversa → thread + perfil renderizados
# 6. Clock stop ⇒ deve ser <30s
```

PASS se clock stop <30s. Falha típica: busca lenta (verificar `EXPLAIN` da query + índice em `customers.display_name`).

### SC-002 — Identificar step dominante em <30s (US2)

```bash
# 1. Clock start
# 2. /admin/traces com filter status=error OU min_duration=5000
# 3. Selecionar trace
# 4. Waterfall rendered → step dominante destacado
# 5. Expandir step → input/output visíveis
# 6. Clock stop ⇒ deve ser <30s
```

PASS se clock stop <30s + dominant step (>60% do total) visualmente destacado.

### SC-003 — Overview em <10s (US4)

```bash
# 1. Clock start no login page
# 2. Login
# 3. Redirect para /
# 4. 6 KPI cards + activity feed + system health + tenant table visíveis acima da dobra
# 5. Clock stop ⇒ deve ser <10s
```

PASS se clock stop <10s. Falha típica: SSR lento (adicionar `unstable_cache` ou medir com Lighthouse).

### SC-004 — Endpoints P95 (listagens <300 ms, performance <2 s / <200 ms cached)

```bash
# Com dataset seedado 10k conversas + 50k traces
for i in {1..50}; do
  curl -s -o /dev/null -w "%{time_total}\n" \
    -H "Cookie: admin_token=<JWT>" \
    "http://localhost:8050/admin/conversations?tenant=pace-internal&limit=50"
done | sort -n | awk 'NR==48{print "P95:",$1"s"}'

# Idem para /admin/traces, /admin/metrics/performance (medir cache hit/miss)
```

PASS se P95 <300 ms (listagens) + <2 s (performance sem cache) + <200 ms (performance com cache).

### SC-005 — Inbox <100 ms (bench query)

Ver `benchmarks/inbox_list_query.md` — rodar `EXPLAIN ANALYZE` em dataset de 10k conversas.

### SC-007 — Suíte verde antes do merge

```bash
# Gate obrigatório do PR 2 + PR 10
cd apps/api && pytest tests/ -v 2>&1 | tail -5
# PASS: "X passed, 0 failed" — nenhum test pré-existente dos epics 004/005 quebrou
```

### SC-012 — 100% das decisões de routing persistidas

```bash
# Last 24h
psql $DATABASE_URL -c \
  "SELECT COUNT(*) FROM routing_decisions WHERE created_at > now() - '24h'::interval"
# Comparar com contagem de webhooks recebidos:
grep "webhook_received" apps/api/logs/api.log | wc -l
```

PASS se delta <1% (fire-and-forget pode perder alguns em caso de falha transiente de conexão).

---

## Rollback plan

Se algum dos PRs apresenta regressão em prod após deploy:

1. **Rollback rápido** — env flag `INSTRUMENTATION_ENABLED=false` desativa a persistência de trace/steps e routing_decisions (pipeline volta ao comportamento epic 005); admin continua funcional mas mostra `—` em campos dependentes.
2. **Rollback migration** — `dbmate rollback` reverte a migration mais recente. Ordem inversa das 4 migrations (T010..T013) funciona porque não há FK do schema antigo para o novo.
3. **Rollback frontend** — revert do PR em Next.js é idempotente (sem side-effects no DB).
4. **Rollback completo do epic** — revert dos 10 PRs na ordem inversa; `dbmate rollback` 4x para desfazer migrations; backfill não precisa ser revertido (colunas ficam NULL e não afetam queries antigas).
