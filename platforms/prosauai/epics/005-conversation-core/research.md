# Research: Conversation Core (Epic 005)

**Epic**: 005-conversation-core  
**Date**: 2026-04-12  
**Status**: Completo

## 1. pydantic-ai para Orquestração de Agente IA

### Decisão
Usar pydantic-ai v1.70+ como framework de orquestração LLM (ADR-001).

### Racional
- **Type-safety**: Validação Pydantic nativa para inputs/outputs do LLM, elimina runtime type errors.
- **Model-agnostic**: Troca de modelo (OpenAI → Anthropic → Gemini) sem refator — só mudar `model` no config.
- **Tool use nativo**: Decorador `@agent.tool` com type hints gera schema JSON automaticamente. Ideal para ResenhAI tool.
- **Structured output**: `result_type=MyModel` garante que a resposta do LLM é parseada e validada.
- **Streaming**: Suporte a streaming SSE se necessário no futuro (não no MVP).
- **Dependency injection**: `RunContext[Deps]` permite injetar tenant_id, pg_pool, etc. sem globals.

### Alternativas Consideradas
| Alternativa | Prós | Contras | Por que descartada |
|-------------|-------|---------|-------------------|
| LangChain | Ecossistema enorme, muitos exemplos | Over-engineering para nosso caso, abstrações pesadas, difícil debugar | Complexidade desnecessária para single-agent |
| Claude SDK direto | Controle total, sem abstrações | Sem tool schema generation, sem retry built-in, sem structured output | Muito baixo nível |
| CrewAI | Multi-agent fácil | Não precisamos de multi-agent no MVP, overhead desnecessário | Scope mismatch |

### Padrão de Uso no Epic 005

```python
from pydantic_ai import Agent
from pydantic import BaseModel

class ConversationDeps(BaseModel):
    tenant_id: str
    customer_id: UUID
    conversation_id: UUID
    pg_pool: asyncpg.Pool
    
agent = Agent(
    model="openai:gpt-4o-mini",
    system_prompt="...",  # Loaded from DB per agent config
    deps_type=ConversationDeps,
    result_type=str,  # Plain text response for MVP
    retries=1,
)

@agent.tool
async def search_rankings(ctx: RunContext[ConversationDeps], query: str) -> str:
    """Consulta rankings do ResenhAI."""
    # ACL check + query
    ...
```

---

## 2. asyncpg + RLS para Persistência Multi-Tenant

### Decisão
Usar asyncpg direto (sem ORM) com RLS policies per-transaction (ADR-011).

### Racional
- **Performance**: asyncpg é o driver Postgres async mais rápido para Python (~3x vs psycopg3 async).
- **Connection pool**: `asyncpg.create_pool()` com pool nativo, sem overhead de ORM pool adapter.
- **RLS per-transaction**: `SET LOCAL app.current_tenant_id = $1` dentro de cada transação garante isolamento.
- **SQL puro**: Para 6 tabelas com queries simples, ORM é overhead sem benefício. Type safety via Pydantic models no retorno.
- **Repositories thin**: Camada fina de repositories que recebem pool e executam queries parametrizadas.

### Alternativas Consideradas
| Alternativa | Prós | Contras | Por que descartada |
|-------------|-------|---------|-------------------|
| SQLAlchemy async | ORM completo, migrations (Alembic) | Overhead para queries simples, complexidade de setup async, RLS precisa de session hooks | Over-engineering para 6 tabelas |
| Supabase Python SDK | API pronta, RLS built-in | Async limitado, dependency em SDK que muda rápido, menos controle | Instabilidade da API |
| psycopg3 async | Mais popular, pool nativo | ~3x mais lento que asyncpg para nosso workload, menos battle-tested async | Performance |

### Padrão de Connection Pool + RLS

```python
# Lifespan setup
pool = await asyncpg.create_pool(
    dsn=settings.database_url,
    min_size=5,
    max_size=10,  # Aligned with LLM semaphore
    command_timeout=5.0,
)
app.state.pg_pool = pool

# Repository pattern with RLS
async def with_tenant(pool: asyncpg.Pool, tenant_id: str):
    async with pool.acquire() as conn:
        await conn.execute("SET LOCAL app.current_tenant_id = $1", tenant_id)
        yield conn
```

### Migrations
SQL scripts manuais em `migrations/` (sem Alembic — 6 tabelas, time-boxed 2 semanas). Ordem:
1. `001_create_schema.sql` — function `auth.tenant_id()`, extensions
> **Atualizado (epic 006):** Migration 001 reescrita — schema `auth` removido, extensão `uuid-ossp` removida, função movida para `public.tenant_id()`.
2. `002_customers.sql` — customers + RLS policy
3. `003_conversations.sql` — conversations + conversation_states + RLS
4. `004_messages.sql` — messages (append-only) + RLS
5. `005_agents_prompts.sql` — agents + prompts + RLS
6. `006_eval_scores.sql` — eval_scores + RLS
7. `007_seed_data.sql` — Ariel + ResenhAI agents, system prompts

---

## 3. GPT-4o-mini como LLM Default

### Decisão
OpenAI GPT-4o-mini direto via pydantic-ai (sem Bifrost proxy).

### Racional
- **Custo**: ~$0.15/1M input tokens, ~$0.60/1M output tokens — adequado para PME MVP.
- **Latência**: p50 ~500ms, p95 ~1.5s para respostas curtas — dentro do budget de 30s end-to-end.
- **Qualidade PT-BR**: GPT-4o-mini tem boa performance em português para conversas simples (atendimento PME).
- **Tool use**: Suporte nativo a function calling, compatível com pydantic-ai `@agent.tool`.

### Alternativas Consideradas
| Alternativa | Prós | Contras | Por que descartada |
|-------------|-------|---------|-------------------|
| Claude 3.5 Haiku | Melhor reasoning, MCP nativo | Mais caro (~2x), pydantic-ai suporta mas menos testado | Custo para MVP |
| Gemini 2.0 Flash | Grátis tier, muito rápido | Tool use menos maduro, pydantic-ai support recente | Maturidade |
| LLaMA 3.1 local | Sem custo recorrente, privacy total | Precisa de GPU, latência maior, sem tool use nativo | Infra complexa |

### Configuração per-Agent
O modelo é configurável por agent no BD (`agents.config → {"model": "openai:gpt-4o-mini"}`). Trocar modelo por tenant é alteração de config, não de código.

---

## 4. Guardrails Regex (Layer A) + Sandwich Pattern

### Decisão
Layer A (regex) para PII + sandwich pattern no system prompt (ADR-016). Sem ML classifier (Layer B) ou LLM-as-judge (Layer C).

### Racional
- **Latência**: <5ms para regex — negligível no pipeline inline.
- **Simplicidade**: Regex patterns bem conhecidos para CPF, telefone, email BR.
- **Sandwich pattern**: Instrução de segurança no início E no fim do system prompt. LLM tende a seguir instrução mais recente.
- **Sem falsos positivos bloqueantes**: PII na entrada é hasheado em logs mas não bloqueia. PII na saída é mascarado.

### Padrões Regex

```python
PII_PATTERNS = {
    "cpf": r"\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}",
    "phone_br": r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
}
```

### Sandwich Pattern Template

```
[SAFETY INSTRUCTIONS - START]
Você é um assistente profissional. NUNCA repita dados pessoais do usuário
(CPF, telefone, email, endereço). Se o usuário compartilhar dados pessoais,
reconheça que recebeu mas NÃO repita os dados na resposta.
[SAFETY INSTRUCTIONS - END]

{system_prompt do agent}

[SAFETY REMINDER]
Lembre-se: NUNCA inclua dados pessoais (CPF, telefone, email) na sua resposta.
```

---

## 5. Avaliador Heurístico (Sem LLM-as-Judge)

### Decisão
Heurísticas simples para avaliação de qualidade da resposta. Interface preparada para upgrade futuro.

### Racional
- **Latência zero adicional**: Heurísticas são O(1), não adicionam latência ao pipeline inline.
- **Custo zero**: Sem chamada LLM extra.
- **Eficácia para edge cases**: Detecta os problemas mais comuns (vazio, curto, encoding quebrado).

### Heurísticas Implementadas

| Check | Threshold | Ação |
|-------|-----------|------|
| Resposta vazia | `len(text.strip()) == 0` | Retry 1x → fallback |
| Resposta muito curta | `len(text.strip()) < 10` | Retry 1x → fallback |
| Encoding incorreto | `\ufffd` ou chars de controle | Retry 1x → fallback |
| Resposta muito longa | `> 4000 chars` | Truncar em boundary de sentença |

### Interface para Upgrade

```python
class ResponseEvaluator(Protocol):
    async def evaluate(self, response: str, context: EvalContext) -> EvalResult: ...

class HeuristicEvaluator:
    """MVP: regras simples."""
    async def evaluate(self, response: str, context: EvalContext) -> EvalResult: ...

class LLMJudgeEvaluator:
    """Futuro: LLM-as-judge para avaliação semântica."""
    async def evaluate(self, response: str, context: EvalContext) -> EvalResult: ...
```

---

## 6. Sliding Window N=10 (Sem Summarization)

### Decisão
Últimas 10 mensagens como contexto. Sem summarization assíncrona.

### Racional
- **Simplicidade**: Query SQL simples (`ORDER BY created_at DESC LIMIT 10`).
- **Adequação**: Conversas de PME são curtas (5-15 trocas). 10 mensagens cobrem 95%+ dos casos.
- **Token budget**: System prompt ~1000 tokens + 10 msgs ~4000 tokens + reserve ~2000 tokens = ~7000 tokens (dentro do limit de 8K).
- **Sem async complexity**: Summarization exigiria background job + storage adicional.

### Token Budget Breakdown

| Componente | Tokens Estimados |
|------------|-----------------|
| Safety instructions (sandwich) | ~200 |
| System prompt do agent | ~800 |
| Context (10 msgs × ~400 tokens) | ~4000 |
| Reserve para resposta | ~2000 |
| Tool definitions | ~500-1000 |
| **Total** | ~7500-8000 |

---

## 7. Pipeline Inline (Sem ARQ Worker)

### Decisão
Executar pipeline de conversação inline no debounce flush callback. Semáforo asyncio(10) limita concorrência LLM.

### Racional
- **Simplicidade**: Sem processo separado, sem Redis streams, sem consumer groups.
- **Adequação**: O debounce já desacopla do webhook (retorna 200 antes do flush). Flush é async.
- **Semáforo**: `asyncio.Semaphore(10)` alinhado ao pool Postgres (10 conexões) e throughput MVP (<100 RPM).
- **Backpressure natural**: Se semáforo cheio, flush aguarda (até 60s timeout).

### Alternativas para Escala Futura
- **ARQ Worker**: Quando throughput > 100 RPM sustained. Separar flush do api process.
- **Redis Streams**: Consumer groups para distribuir trabalho entre workers.
- **Celery**: Se precisar de scheduling complexo (triggers proativos, batch eval).

---

## 8. agent_id no Debounce Buffer Item

### Decisão
Adicionar `agent_id` ao item JSON do debounce buffer (ao lado de `trace_context`).

### Análise do Código Atual
O item atual é:
```json
{"text": "mensagem", "trace_context": {"traceparent": "00-..."}}
```

Proposta:
```json
{"text": "mensagem", "trace_context": {"traceparent": "00-..."}, "agent_id": "uuid-string"}
```

### Impacto
- **`_parse_flush_items()`**: Precisa extrair `agent_id` do JSON item. Se múltiplos items com `agent_id` diferentes, usar o último.
- **`FlushCallback`**: Mudar de `(tenant_id, sender_key, group_id, text)` para incluir `agent_id`. Breaking change controlado (único caller: `start_listener`).
- **`append()`**: Receber `agent_id` como parâmetro e incluir no JSON item.
- **Backward compatibility**: Items sem `agent_id` (legacy) usam `tenant.default_agent_id` como fallback.

---

## 9. ResenhAI Tool Call via ACL Pattern

### Decisão
Implementar como pydantic-ai tool com ACL check. Não query direta cross-DB.

### Racional (context-map relação 19, ADR-014)
- **Desacoplamento**: Tool call é boundary explícita. ResenhAI pode mudar schema sem quebrar conversação.
- **ACL**: Apenas agents com `tools_enabled: ["resenhai_rankings"]` podem chamar. Server-side enforcement.
- **Tenant isolation**: `tenant_id` injetado server-side no tool (OWASP Agentic Top 10 — nunca confiar no LLM).

### Implementação

```python
@agent.tool
async def search_rankings(ctx: RunContext[ConversationDeps], query: str) -> str:
    """Busca rankings e estatísticas de futebol do ResenhAI."""
    # ACL: verificar se tool está habilitado para este agent
    # Query: HTTP call para API interna ResenhAI (não query direta ao DB)
    # Retorno: texto formatado com dados
```

### Alternativas Consideradas
| Alternativa | Prós | Contras | Por que descartada |
|-------------|-------|---------|-------------------|
| Query direta cross-DB | Mais rápido, sem HTTP overhead | Acoplamento forte, RLS cross-schema complexo | Violação de bounded context |
| MCP server | Padrão emergente, pydantic-ai suporta | Overhead de setup para 1 tool, complexidade desnecessária | Over-engineering |
| Webhook event | Assíncrono, desacoplado | LLM precisa de resposta síncrona para tool call | Incompatível com flow |

---

## 10. Docker Compose: Postgres Container

### Decisão
Adicionar container Postgres 15 ao docker-compose.yml existente.

### Configuração

```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: prosauai
    POSTGRES_USER: prosauai
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - pgdata:/var/lib/postgresql/data
    - ./migrations:/docker-entrypoint-initdb.d
  ports:
    - "5432:5432"  # Dev only — Tailscale in prod
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U prosauai"]
    interval: 5s
    timeout: 3s
    retries: 5
  networks:
    - pace-net
```

### Alternativas Consideradas
| Alternativa | Prós | Contras | Por que descartada |
|-------------|-------|---------|-------------------|
| Supabase managed | Zero ops, UI dashboard | Custo recorrente, latência de rede, vendor lock-in | MVP sem budget para managed |
| Supabase local (Docker) | Full Supabase stack | Complexidade (15+ containers), overkill para MVP | Overhead absurdo |
| SQLite | Zero config, embedded | Sem RLS nativo, sem concurrent writers, sem pool | Não atende multi-tenant |
