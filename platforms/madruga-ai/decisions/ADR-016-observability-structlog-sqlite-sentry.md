---
title: "ADR-016: Observability — structlog + SQLite Metrics + Sentry Free"
status: accepted
date: 2026-03-30
decision: Adotar structlog + SQLite metrics table (~100 LOC) para metricas custom e Sentry
  cloud free tier para error tracking com stack traces e performance traces.
alternatives: OpenTelemetry + Grafana Stack, PostHog self-hosted, Sentry self-hosted
rationale: 80% do valor por 5% do esforco — metricas em SQLite reusam DB existente,
  Sentry adiciona error tracking profissional com 15 min de setup
---
# ADR-016: Observability — structlog + SQLite Metrics + Sentry Free

## Status

Accepted — 2026-03-30

## Contexto

O daemon Madruga AI roda como servico FastAPI em WSL2. Atualmente a unica observability e structlog para logging. Nao ha metricas (duracao de requests, taxa de erros), nem error tracking estruturado (stack traces com contexto), nem traces de performance.

Para um daemon single-user local, a solucao deve ser leve (RAM minima), pragmatica (maximo valor com minimo esforco), e compativel com a stack existente (Python 3.12, SQLite WAL, structlog, Astro portal).

## Decisao

Adotar uma abordagem em duas camadas:

1. **structlog + SQLite metrics table** (~100 LOC): metricas custom (request duration, status codes, error rates) armazenadas na mesma SQLite DB do pipeline, com dashboard no portal Astro.
2. **Sentry cloud free tier**: error tracking com stack traces, breadcrumbs, e performance traces. Auto-instrumenta FastAPI. 5K erros/mes gratis.

Graduar para OTel + Grafana apenas quando houver 3+ servicos e necessidade de traces distribuidos.

## Alternativas Consideradas

### Alternativa A: structlog + SQLite metrics + Sentry free (escolhida)
- **Pros:** ~100 LOC para metricas, zero deps novas para camada local, near-zero resource usage, dashboard no portal Astro (reusa stack), Sentry adiciona error tracking profissional com 15 min de setup, auto-instrumenta FastAPI
- **Cons:** sem traces distribuidos na camada local (Sentry cobre parcialmente), dashboard custom requer trabalho, Sentry e SaaS (nao 100% local)
- **Fit:** 80% do valor por 5% do esforco. Encaixa perfeitamente no principio de pragmatismo.

### Alternativa B: OpenTelemetry + Grafana Stack (Prometheus + Grafana + Loki + Tempo)
- **Pros:** observability completa (metricas + traces + logs + dashboards ricos), standard industry, auto-instrumenta FastAPI via `opentelemetry-instrumentation-fastapi`
- **Cons:** ~1 GB RAM (5 containers Docker), setup 2-4h, manutencao alta (version mismatches, retention policies, scrape configs), overkill para daemon unico
- **Rejeitada porque:** complexidade e resource usage desproporcionais para um daemon single-user. O investimento em infra nao se justifica ate ter 3+ servicos.

### Alternativa C: PostHog self-hosted
- **Pros:** product analytics poderoso, UI rico
- **Cons:** 4-8 GB RAM (10+ containers: PostgreSQL, Redis, ClickHouse, Kafka), **ferramenta errada** — PostHog e product analytics, nao backend observability. Sem metricas, sem traces, sem log aggregation.
- **Rejeitada porque:** nao resolve o problema. PostHog e para tracking de usuarios em web apps, nao para monitorar saude de daemon.

### Alternativa D: Sentry self-hosted
- **Pros:** error tracking excelente, performance traces, profiling
- **Cons:** 4-8 GB RAM (~20 containers: PostgreSQL, Redis, Kafka, ClickHouse, Snuba, workers), setup 2-4h, manutencao alta
- **Rejeitada como self-hosted porque:** mesmo resource overhead que PostHog. O free tier cloud oferece o mesmo valor sem a infra. Se Sentry cloud se tornar inaceitavel, migrar para self-hosted e possivel.

## Consequencias

### Positivas
- Metricas de request em SQLite com custo zero de infra — reusa DB existente
- Dashboard no portal Astro — operador consulta no mesmo lugar que ja usa
- Sentry free tier captura stack traces com contexto, breadcrumbs, e performance traces automaticamente
- structlog permanece como camada de logging — zero mudanca no codigo existente
- Evolucao gradual: nao impede migracao futura para OTel+Grafana

### Negativas
- Dashboard de metricas e custom work (nao pre-built como Grafana)
- Sentry e SaaS — dados de erro saem do ambiente local
- Sentry free tier tem quota de 5K erros/mes e 10M transactions/mes. Para daemon com retries, monitorar consumo. Se exceder: Sentry degrada silenciosamente (drops events), structlog+SQLite continua funcionando
- Dois sistemas de observability (SQLite metrics + Sentry) para um daemon single-user pode ser over-engineering. Justificativa: SQLite cobre metricas custom (request duration, pipeline throughput), Sentry cobre o que e dificil de construir (stack traces com breadcrumbs, performance waterfall). Se Sentry se tornar desnecessario, remover sem impacto
- Sem alerting automatico na camada local (usar Sentry alerts para erros, metricas no portal sao consulta manual)

### Riscos
- Sentry free tier descontinuado ou limites reduzidos → mitigacao: structlog+SQLite cobre 80% do valor, Sentry e complementar
- SQLite metrics table cresce sem bound → mitigacao: cleanup periodico (DELETE WHERE ts < date('now', '-30 days')) como periodic task do daemon. Estimativa: ~1-5 MB/mes para daemon single-user, cleanup mensal mantem tabela sob 10MB

## Referencias

- [structlog docs](https://www.structlog.org/en/stable/)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [Sentry Python FastAPI integration](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [Sentry Pricing](https://sentry.io/pricing/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [PostHog self-hosted requirements](https://posthog.com/docs/self-host)
