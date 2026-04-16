# Quickstart — Epic 007: Admin Front Dashboard

## Pré-requisitos

- Docker + Docker Compose
- pnpm >= 9.x (após monorepo)
- Node.js >= 20
- Python 3.12+
- PostgreSQL 15 com extensões: pgvector, pg_trgm
- Redis 7
- dbmate CLI (`brew install dbmate` ou download do release)

## Setup Local (após monorepo)

### 1. Clonar e instalar

```bash
git clone git@github.com:paceautomations/prosauai.git
cd prosauai
git checkout epic/prosauai/007-admin-front-dashboard

# Backend (API)
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Frontend (Admin)
cd ../../
pnpm install  # instala deps de apps/admin + packages/types
```

### 2. Configurar ambiente

```bash
cp .env.example .env
# Editar .env com:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/prosauai
# REDIS_URL=redis://localhost:6379
# JWT_SECRET=<string-aleatoria-32-chars-min>
# ADMIN_BOOTSTRAP_EMAIL=admin@pace.com
# ADMIN_BOOTSTRAP_PASSWORD=<senha-forte>
# ADMIN_FRONTEND_ORIGIN=http://localhost:3000
```

### 3. Subir infra + rodar migrations

```bash
# Subir apenas DB + Redis
docker compose up -d postgres redis

# Rodar migrations
dbmate --url "$DATABASE_URL" up

# Ou via docker compose (migration service)
docker compose up migrate
```

### 4. Subir serviços

```bash
# API
cd apps/api
uvicorn prosauai.main:app --host 0.0.0.0 --port 8050 --reload

# Admin (outro terminal)
cd apps/admin
pnpm dev  # http://localhost:3000
```

### 5. Primeiro acesso

1. O bootstrap cria o admin na primeira inicialização da API (via env vars)
2. Acessar `http://localhost:3000/admin/login`
3. Fazer login com `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`
4. Dashboard exibe gráfico de mensagens (vazio se não houver dados)

## Docker Compose (tudo junto)

```bash
docker compose up --build
# API: http://localhost:8050
# Admin: http://localhost:3000
# Health: http://localhost:8050/health
```

## Testes

```bash
# Backend
cd apps/api
pytest tests/ -v

# Frontend
cd apps/admin
pnpm test

# RLS smoke test (crítico após setup de roles)
cd apps/api
pytest tests/integration/test_rls_isolation.py -v
```

## Troubleshooting

| Problema | Solução |
|----------|---------|
| `role "authenticated" does not exist` | Rodar `dbmate up` — migration 010 cria as roles |
| `CORS error` no browser | Verificar `ADMIN_FRONTEND_ORIGIN` no `.env` da API |
| Cookie não setado | Verificar `allow_credentials=True` no CORS e `credentials: 'include'` no fetch |
| `relation "admin_users" does not exist` | Rodar `dbmate up` — migration 010 cria a tabela |
| Admin frontend não conecta na API | Verificar `NEXT_PUBLIC_API_URL=http://localhost:8050` no `.env` do admin |
