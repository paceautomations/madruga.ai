---
title: "Containers"
---
# C4 L2 — Containers

> Containers deployaveis da plataforma Fulano. Para diagrama interativo, veja [Containers (Interactive)](/fulano/containers/).

## Containers

<!-- AUTO:containers -->
| Container | Tech | Porta | Responsabilidade |
|-----------|------|-------|------------------|
| **Bifrost** | Go (Bifrost) | 8050 | Proxy LLM com interface OpenAI-compatible (/v1/chat/completions). Rate limiting por tenant configuravel, fallback chain (Sonnet -> Haiku -> resposta generica), cost tracking agregado por modelo e tenant. Circuit breaker integrado. |
| **fulano-admin** | Next.js 15 + shadcn/ui | 3000 | Admin panel com dashboard de metricas, conversation viewer em tempo real, prompt manager com versionamento, e fila de handoff para agentes humanos. Autenticacao via Supabase Auth (JWT). |
| **fulano-api** | Python 3.12 + FastAPI | 8040 | Webhook receiver (Evolution API), REST endpoints para CRUD, Socket.io gateway para realtime push ao admin panel. Valida HMAC-SHA256, dedup por message_id (Redis TTL 24h), enqueue no Redis Streams. |
| **fulano-worker** | Python 3.12 + ARQ | — | Worker async via ARQ sobre Redis. Processa pipeline completa: debounce flush, orquestracao LLM (via Bifrost), delivery de respostas (via Evolution API), eval batch jobs, e trigger evaluator. Escalavel horizontalmente. |
| **Redis** | Redis 7 | 6379 | Componente critico. Job queue (ARQ), debounce buffers (Lua atomico), cache de sessao, PubSub. Particionamento por prefixo: arq:, buf:, cache:, ps:. AOF enabled para crash recovery. Sem fallback — healthcheck + restart automatico. |
| **Supabase Fulano** | PostgreSQL 15 + pgvector | 5432 | Source of truth do sistema. Armazena conversas, mensagens, clientes, prompts versionados, trigger rules, eval scores. pgvector para embeddings (1536 dims, HNSW index). RLS com tenant_id para isolamento multi-tenant. LISTEN/NOTIFY para realtime events. |
| **Supabase ResenhAI** | PostgreSQL 15 | 5433 | Banco externo do ResenhAI. Acesso read-only via asyncpg para consultar dados de jogos, estatisticas, ranking. Usado por tool calls dos agentes (get_group_ranking, get_game_stats, get_player_stats). |
<!-- /AUTO:containers -->

## Decisoes de Design

1. **API e Worker separados** — desacoplamento permite escalar workers independentemente
2. **ARQ sobre Redis** — queue leve, Python nativo, sem overhead de Celery
3. **Bifrost como proxy** — centraliza rate limiting, fallback Sonnet→Haiku, e cost tracking
