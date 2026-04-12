# Quickstart: Conversation Core (Epic 005)

**Epic**: 005-conversation-core  
**Pré-requisitos**: Docker, Python 3.12+, OpenAI API key

## 1. Setup Rápido

```bash
# Clonar e instalar
cd prosauai/
pip install -e ".[dev]"

# Copiar env com novas variáveis
cp .env.example .env
# Editar .env:
#   DATABASE_URL=postgresql://prosauai:prosauai@localhost:5432/prosauai
#   OPENAI_API_KEY=sk-...
#   LLM_SEMAPHORE_SIZE=10
#   CONVERSATION_INACTIVITY_TIMEOUT_HOURS=24
#   CONTEXT_WINDOW_SIZE=10
#   MAX_CONTEXT_TOKENS=8000

# Subir serviços (agora inclui Postgres)
docker compose up -d

# Aplicar migrations + seed
psql $DATABASE_URL -f migrations/001_create_schema.sql
psql $DATABASE_URL -f migrations/002_customers.sql
psql $DATABASE_URL -f migrations/003_conversations.sql
psql $DATABASE_URL -f migrations/003b_conversation_states.sql
psql $DATABASE_URL -f migrations/004_messages.sql
psql $DATABASE_URL -f migrations/005_agents_prompts.sql
psql $DATABASE_URL -f migrations/006_eval_scores.sql
psql $DATABASE_URL -f migrations/007_seed_data.sql

# Rodar API
uvicorn prosauai.main:app --host 0.0.0.0 --port 8050 --reload
```

## 2. Verificação

```bash
# Health check (agora inclui Postgres)
curl http://localhost:8050/health | jq .

# Verificar seed data
psql $DATABASE_URL -c "SELECT name, config->>'model' FROM agents;"
# Esperado: Ariel Assistant (gpt-4o-mini), ResenhAI Bot (gpt-4o-mini)
```

## 3. Teste Manual

Enviar mensagem WhatsApp para o número do agente Ariel. Verificar:
- [ ] Resposta é gerada por IA (não echo)
- [ ] Resposta é em PT-BR
- [ ] Span no Phoenix (localhost:6006) mostra pipeline completo

## 4. Teste Automatizado

```bash
# Testes unitários (LLM mockado)
pytest tests/conversation/ -v

# Testes de isolamento RLS
pytest tests/integration/test_rls_isolation.py -v

# Teste do pipeline completo (mock LLM)
pytest tests/integration/test_conversation_pipeline.py -v
```

## 5. Estrutura de Arquivos Novos

```
prosauai/
├── prosauai/
│   ├── conversation/          # NOVO — M4-M5, M7-M9
│   │   ├── __init__.py
│   │   ├── customer.py        # M4: Lookup/create customer
│   │   ├── context.py         # M5: Context window assembly
│   │   ├── classifier.py      # M7: Intent classification
│   │   ├── agent.py           # M8: pydantic-ai agent orchestration
│   │   ├── evaluator.py       # M9: Heuristic response evaluation
│   │   ├── pipeline.py        # Pipeline orchestrator (replaces _flush_echo)
│   │   └── models.py          # Domain models (Customer, Conversation, etc.)
│   ├── safety/                # NOVO — M6, M10
│   │   ├── __init__.py
│   │   ├── input_guard.py     # M6: PII detection + input validation
│   │   ├── output_guard.py    # M10: PII masking in output
│   │   └── patterns.py        # Regex patterns (shared)
│   ├── db/                    # NOVO — Repository layer
│   │   ├── __init__.py
│   │   ├── pool.py            # Connection pool setup
│   │   └── repositories.py    # Thin repository per entity
│   └── tools/                 # NOVO — pydantic-ai tools
│       ├── __init__.py
│       ├── registry.py        # Tool registry (ADR-014)
│       └── resenhai.py        # ResenhAI ranking/stats tool
├── migrations/                # NOVO — SQL scripts
│   ├── 001_create_schema.sql
│   ├── 002_customers.sql
│   ├── 003_conversations.sql
│   ├── 003b_conversation_states.sql
│   ├── 004_messages.sql
│   ├── 005_agents_prompts.sql
│   ├── 006_eval_scores.sql
│   └── 007_seed_data.sql
└── tests/
    ├── conversation/          # NOVO — Unit tests
    │   ├── test_customer.py
    │   ├── test_context.py
    │   ├── test_classifier.py
    │   ├── test_agent.py
    │   ├── test_evaluator.py
    │   └── test_pipeline.py
    ├── safety/                # NOVO — Guard tests
    │   ├── test_input_guard.py
    │   └── test_output_guard.py
    └── integration/           # NOVO — Integration tests
        ├── test_conversation_pipeline.py
        └── test_rls_isolation.py
```
