# Implementation Plan: Conversation Core

**Branch**: `epic/prosauai/005-conversation-core` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `epics/005-conversation-core/spec.md`

## Summary

Substituir o handler echo (`_flush_echo`) por um pipeline completo de conversação com IA. O pipeline recebe mensagens do debounce flush, processa via LLM (pydantic-ai + GPT-4o-mini), persiste em Postgres com RLS multi-tenant, e responde via EvolutionProvider. Inclui guardrails regex (Layer A), avaliador heurístico, sliding window de contexto (N=10), e tool call para ResenhAI. Execução inline no prosauai-api com semáforo asyncio(10).

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI >=0.115, pydantic-ai >=1.70, asyncpg >=0.30, pydantic >=2.0, httpx, structlog, redis[hiredis] >=5.0  
**Storage**: PostgreSQL 15 (Docker container) com RLS per-transaction (ADR-011), Redis 7 (existente — debounce + idempotency)  
**Testing**: pytest + pytest-asyncio + pytest-cov. LLM mockado em unit/integration. RLS isolation tests.  
**Target Platform**: Linux server (Docker Compose)  
**Project Type**: Web service (FastAPI) — extensão do prosauai-api existente  
**Performance Goals**: <30s end-to-end (webhook → resposta), <3s p95 para pipeline (excl. debounce 3s)  
**Constraints**: Semáforo 10 LLM concurrent, pool 10 Postgres connections, 60s timeout LLM, 8K context tokens, 20 tool calls/conversa  
**Scale/Scope**: 2 tenants (Ariel + ResenhAI), <100 RPM sustained, ~15 novos arquivos Python, ~10 SQL migrations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Evidência |
|-----------|--------|-----------|
| I. Pragmatism Above All | ✅ PASS | Inline pipeline (sem worker separado), asyncpg direto (sem ORM), heurísticas (sem LLM judge), regex (sem ML guardrails) |
| II. Automate Repetitive Tasks | ✅ PASS | Migrations SQL automatizadas, seed data script, docker compose up |
| III. Structured Knowledge | ✅ PASS | research.md, data-model.md, contracts/ documentam todas as decisões |
| IV. Fast Action | ✅ PASS | 10 dias timeboxed, MVP scope controlado (sem Bifrost, sem ARQ, sem versioning) |
| V. Alternatives and Trade-offs | ✅ PASS | Cada decisão em research.md tem >=2 alternativas com prós/contras |
| VI. Brutal Honesty | ✅ PASS | Rabbit holes explícitos no pitch. No-gos claros. Nenhuma feature "nice to have" incluída. |
| VII. TDD | ✅ PASS | Tests before implementation. Unit tests per module (M4-M10). Integration test do pipeline. RLS isolation tests. |
| VIII. Collaborative Decision Making | ✅ PASS | 10 decisões capturadas no pitch com referências arquiteturais. Clarifications resolvidas no spec. |
| IX. Observability and Logging | ✅ PASS | OTel spans para cada etapa. structlog com correlation_id. PII hasheado (ADR-018). Phoenix integration (epic 002). |

**Resultado**: PASS — nenhuma violação. Não há complexity tracking necessário.

### Re-check Pós-Design (Phase 1)

| Princípio | Status | Evidência |
|-----------|--------|-----------|
| I. Pragmatism | ✅ PASS | data-model.md: 7 tabelas simples, SQL puro, sem ORM. Pipeline: 8 etapas lineares, sem fan-out. |
| V. Alternatives | ✅ PASS | research.md: 10 decisões com alternativas documentadas |
| VII. TDD | ✅ PASS | quickstart.md: test commands definidos. Contract: interfaces mockáveis. |
| IX. Observability | ✅ PASS | contracts/conversation-pipeline.md: spans definidos por etapa. SpanAttributes existentes reutilizados. |

## Project Structure

### Documentation (this epic)

```text
epics/005-conversation-core/
├── pitch.md                           # Epic pitch (Shape Up)
├── spec.md                            # Feature specification
├── plan.md                            # This file
├── research.md                        # Phase 0: Technology research
├── data-model.md                      # Phase 1: SQL schemas + ER diagram
├── quickstart.md                      # Phase 1: Dev quickstart
├── contracts/
│   └── conversation-pipeline.md       # Phase 1: Pipeline interface contracts
├── decisions.md                       # Cross-cutting decision log
└── checklists/
    └── requirements.md                # Spec requirements checklist
```

### Source Code (prosauai repository)

```text
prosauai/
├── prosauai/
│   ├── main.py                        # MODIFIED — new flush callback, pg_pool in lifespan
│   ├── config.py                      # MODIFIED — new settings (DATABASE_URL, LLM, conversation)
│   ├── conversation/                  # NEW — Core domain (M4-M5, M7-M9)
│   │   ├── __init__.py
│   │   ├── models.py                  # Domain models: Customer, Conversation, Message, etc.
│   │   ├── customer.py                # M4: get_or_create_customer
│   │   ├── context.py                 # M5: build_context_window
│   │   ├── classifier.py             # M7: classify_intent
│   │   ├── agent.py                   # M8: pydantic-ai agent orchestration
│   │   ├── evaluator.py              # M9: heuristic response evaluation
│   │   └── pipeline.py               # Pipeline orchestrator (replaces _flush_echo)
│   ├── safety/                        # NEW — Guardrails (M6, M10)
│   │   ├── __init__.py
│   │   ├── patterns.py               # PII regex patterns (shared)
│   │   ├── input_guard.py            # M6: Input validation + PII detection
│   │   └── output_guard.py           # M10: PII masking in LLM output
│   ├── db/                            # NEW — Database layer
│   │   ├── __init__.py
│   │   ├── pool.py                    # asyncpg pool creation + RLS helper
│   │   └── repositories.py           # Thin repos: CustomerRepo, ConversationRepo, etc.
│   ├── tools/                         # NEW — pydantic-ai tools
│   │   ├── __init__.py
│   │   ├── registry.py               # Tool registry (ADR-014)
│   │   └── resenhai.py               # ResenhAI ranking/stats tool
│   ├── core/
│   │   ├── debounce.py               # MODIFIED — agent_id in buffer item + new FlushCallback
│   │   └── ...                        # Existing (unchanged)
│   └── observability/
│       └── conventions.py             # MODIFIED — new span attribute constants
├── migrations/                        # NEW — SQL migration scripts
│   ├── 001_create_schema.sql
│   ├── 002_customers.sql
│   ├── 003_conversations.sql
│   ├── 003b_conversation_states.sql
│   ├── 004_messages.sql
│   ├── 005_agents_prompts.sql
│   ├── 006_eval_scores.sql
│   └── 007_seed_data.sql
├── docker-compose.yml                 # MODIFIED — add postgres service
├── pyproject.toml                     # MODIFIED — add asyncpg, pydantic-ai deps
├── .env.example                       # MODIFIED — new env vars
└── tests/
    ├── conversation/                  # NEW — Unit tests per module
    │   ├── test_customer.py
    │   ├── test_context.py
    │   ├── test_classifier.py
    │   ├── test_agent.py
    │   ├── test_evaluator.py
    │   └── test_pipeline.py
    ├── safety/                        # NEW — Guard tests
    │   ├── test_input_guard.py
    │   └── test_output_guard.py
    ├── tools/                         # NEW — Tool tests
    │   └── test_resenhai.py
    └── integration/                   # NEW — Integration tests
        ├── test_conversation_pipeline.py
        └── test_rls_isolation.py
```

**Structure Decision**: Extensão do monolito existente (prosauai-api). Novos packages `conversation/`, `safety/`, `db/`, `tools/` dentro do namespace `prosauai/`. Sem novos serviços — pipeline inline. Alinhado com a decisão do pitch (sem ARQ worker separado).

## Fase 1 — Infraestrutura de Dados (Dias 1-3)

### 1.1 Dependências e Configuração

**Objetivo**: Adicionar asyncpg e pydantic-ai ao projeto, configurar novas settings.

**Arquivos modificados**:
- `pyproject.toml`: Adicionar `asyncpg>=0.30`, `pydantic-ai>=1.70`
- `config.py`: Novas settings — `database_url`, `llm_semaphore_size`, `conversation_inactivity_timeout_hours`, `context_window_size`, `max_context_tokens`, `openai_api_key`
- `.env.example`: Documentar novas variáveis

**Decisão**: Sem `openai` SDK direto — pydantic-ai gerencia o cliente internamente. Apenas `OPENAI_API_KEY` como env var.

### 1.2 PostgreSQL Container + Migrations

**Objetivo**: Adicionar Postgres ao docker-compose, criar schemas com RLS.

**Arquivos**:
- `docker-compose.yml`: Novo serviço `postgres` (15-alpine), volume `pgdata`, healthcheck
- `migrations/001_create_schema.sql` → `007_seed_data.sql`: Scripts SQL conforme data-model.md

**Decisão**: Migrations manuais (SQL scripts em ordem numérica), sem Alembic. Justificativa: 7 tabelas, time-boxed 2 semanas, equipe de 5. Alembic adiciona complexidade sem benefício para este scope.

**RLS Hardening (ADR-011)**:
1. `auth.tenant_id()` function com `SECURITY DEFINER` + `SET search_path = ''`
2. Policy `tenant_isolation` em TODA tabela com `tenant_id`
3. Index em CADA coluna `tenant_id`
4. Messages: policies adicionais bloqueiam UPDATE e DELETE (append-only)

### 1.3 Connection Pool + Repository Layer

**Objetivo**: Setup asyncpg pool no lifespan, repositories thin.

**Arquivos novos**:
- `prosauai/db/__init__.py`
- `prosauai/db/pool.py`: `create_pool()`, `with_tenant()` context manager para RLS
- `prosauai/db/repositories.py`: `CustomerRepo`, `ConversationRepo`, `MessageRepo`, `AgentRepo`, `EvalScoreRepo`

**Pattern**: Repository recebe `conn` (com RLS já setado via `with_tenant()`). Retorna Pydantic models. Zero lógica de negócio — apenas SQL parametrizado.

```python
# pool.py
@asynccontextmanager
async def with_tenant(pool: asyncpg.Pool, tenant_id: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SET LOCAL app.current_tenant_id = $1", tenant_id
            )
            yield conn
```

### 1.4 Debounce: agent_id no Buffer Item

**Objetivo**: Preservar `agent_id` do router através do debounce até o flush.

**Arquivos modificados**:
- `prosauai/core/debounce.py`:
  - `append()`: Novo parâmetro `agent_id: str | None`. Inclui no JSON item.
  - `_parse_flush_items()`: Extrai `agent_id` do JSON. Se múltiplos, usa o último.
  - `FlushCallback`: Nova signature com `agent_id` como 5º parâmetro.
  - `start_listener()`: Passa `agent_id` extraído para o callback.
- `prosauai/main.py` (webhook handler): Passa `agent_id` do `RespondDecision` para `debounce.append()`.

**Backward compatibility**: Items sem campo `agent_id` no JSON (legacy) retornam `None`. Pipeline usa `tenant.default_agent_id` como fallback.

### 1.5 Lifespan Update

**Objetivo**: Inicializar pg_pool e semáforo no startup, fechar no shutdown.

**Arquivo modificado**: `prosauai/main.py` (lifespan)

Sequência de startup atualizada:
```
Settings → TenantStore → RoutingEngines → Redis → DebounceManager
→ [NEW] asyncpg Pool → [NEW] LLM Semaphore → Observability
```

Shutdown:
```
[NEW] pg_pool.close() → cancel listener → close Redis → flush OTel
```

## Fase 2 — Conversation Pipeline (Dias 4-7)

### 2.1 Domain Models

**Arquivo**: `prosauai/conversation/models.py`

Pydantic models espelhando as tabelas SQL:
- `Customer(id, tenant_id, phone_hash, display_name, metadata, created_at, updated_at)`
- `Conversation(id, tenant_id, customer_id, agent_id, channel, status, close_reason, started_at, closed_at, last_activity_at)`
- `Message(id, tenant_id, conversation_id, direction, content, content_type, metadata, created_at)`
- `ConversationState(id, tenant_id, conversation_id, context_window, current_intent, intent_confidence, message_count, token_count)`
- `AgentConfig(id, tenant_id, name, config, active_prompt_id, enabled)`
- `PromptConfig(id, tenant_id, agent_id, version, system_prompt, safety_prefix, safety_suffix, tools_enabled, parameters)`
- `EvalScore(id, tenant_id, conversation_id, message_id, evaluator_type, quality_score, details)`
- `ContextMessage(role, content, created_at)` — Lightweight model para context window

### 2.2 Customer Module (M4)

**Arquivo**: `prosauai/conversation/customer.py`

Função principal: `get_or_create_customer(pool, tenant_id, phone, display_name) → Customer`

Lógica:
1. Hash do phone com SHA-256 (nunca armazena raw).
2. `SELECT` por `(tenant_id, phone_hash)`.
3. Se não existe, `INSERT` e retorna.
4. Se existe, atualiza `display_name` se fornecido e `updated_at`.

**Testes**: `tests/conversation/test_customer.py` — create, get existing, update display_name, hash correctness.

### 2.3 Context Module (M5)

**Arquivo**: `prosauai/conversation/context.py`

Função principal: `build_context_window(pool, conversation_id, tenant_id, max_messages=10, max_tokens=8000) → list[ContextMessage]`

Lógica:
1. Query últimas N mensagens `ORDER BY created_at DESC LIMIT max_messages`.
2. Reverse para ordem cronológica.
3. Estimar tokens (chars / 4 heurística).
4. Se total > max_tokens, drop mensagens mais antigas até caber.
5. Retorna lista de `ContextMessage(role, content, created_at)`.

Função auxiliar: `get_or_create_conversation(pool, tenant_id, customer_id, agent_id, channel, inactivity_timeout_hours) → (Conversation, is_new)`

Lógica de conversa:
1. Busca conversa ativa para `(tenant_id, customer_id, channel)`.
2. Se existe e `last_activity_at` + timeout < now → fecha (status=closed, reason=inactivity_timeout), cria nova.
3. Se existe e dentro do timeout → retorna existente, atualiza `last_activity_at`.
4. Se não existe → cria nova.

**Testes**: `tests/conversation/test_context.py` — build window, token truncation, conversation lifecycle, inactivity timeout.

### 2.4 Safety: Input Guard (M6)

**Arquivo**: `prosauai/safety/patterns.py` + `prosauai/safety/input_guard.py`

`patterns.py`: Regex patterns para CPF, telefone BR, email. Constantes compartilhadas entre input e output guards.

`input_guard.py`: Função `check_input(text) → GuardResult`

Lógica:
1. Detectar PII via regex → lista de tipos encontrados.
2. Gerar `sanitized_text` com PII mascarado (para logs).
3. Se `len(text) > 4000` → `allowed=False`, `blocked_reason="message_too_long"`.
4. Se injection pattern detectado → `allowed=False`, `blocked_reason="injection_detected"`.
5. Caso contrário → `allowed=True`, `original_text` preservado (PII vai pro LLM, não bloqueia).

**Testes**: `tests/safety/test_input_guard.py` — PII detection (CPF, phone, email), length check, injection patterns, clean text pass.

### 2.5 Intent Classifier (M7)

**Arquivo**: `prosauai/conversation/classifier.py`

Função: `classify_intent(text, context, agent_config) → ClassificationResult`

MVP approach: LLM classification com structured output.

```python
classification_agent = Agent(
    model="openai:gpt-4o-mini",
    system_prompt="Classifique a intenção da mensagem do usuário...",
    result_type=ClassificationOutput,  # Pydantic model com intent + confidence
)
```

Se `confidence < 0.7` → fallback para `intent="general"`.
Se LLM falha → fallback para `intent="general"` com `confidence=0.0`.

**Alternativa considerada**: Keyword matching puro (sem LLM). Descartada porque: não captura nuances, não escala com novos intents. LLM via pydantic-ai é simples e o custo é negligível (1 call extra com output estruturado curto).

**Testes**: `tests/conversation/test_classifier.py` — known intents, low confidence fallback, LLM failure fallback.

### 2.6 Agent Orchestrator (M8)

**Arquivo**: `prosauai/conversation/agent.py`

Core do epic. Implementa a geração de resposta via pydantic-ai.

```python
async def generate_response(
    agent_config: AgentConfig,
    prompt: PromptConfig,
    context: list[ContextMessage],
    user_message: str,
    classification: ClassificationResult,
    deps: ConversationDeps,
    semaphore: asyncio.Semaphore,
) -> GenerationResult:
```

Lógica:
1. Aguardar semáforo (`async with semaphore`).
2. Construir system prompt: `safety_prefix + system_prompt + safety_suffix` (sandwich pattern).
3. Construir messages: context window + user_message.
4. Criar pydantic-ai Agent com model do config, tools do prompt.tools_enabled.
5. `agent.run(user_message, message_history=history, deps=deps)` com timeout 60s.
6. Retornar `GenerationResult(text, model, tokens_used, tool_calls_count, latency_ms)`.

**Tool Registration**: Tools são registrados no agent apenas se listados em `prompt.tools_enabled`. Server-side whitelist enforcement (ADR-014).

**Dependency Injection**: `ConversationDeps` contém `tenant_id`, `customer_id`, `conversation_id`, `pg_pool` — disponível para tools via `RunContext[ConversationDeps]`.

**Testes**: `tests/conversation/test_agent.py` — successful generation (mocked LLM), timeout handling, tool call, semaphore limiting.

### 2.7 Response Evaluator (M9)

**Arquivo**: `prosauai/conversation/evaluator.py`

Função: `evaluate_response(response_text, context) → EvalResult`

Checks heurísticos:
1. `empty`: `len(text.strip()) == 0` → action: retry
2. `too_short`: `len(text.strip()) < 10` → action: retry
3. `bad_encoding`: `\ufffd` ou chars de controle presentes → action: retry
4. `too_long`: `> 4000 chars` → truncar em boundary de sentença, action: deliver

Score: `1.0` se todos passam, `0.5` se truncado, `0.0` se qualquer falha crítica.
Action: `"deliver"` | `"retry"` | `"fallback"` (baseado em retry count).

Interface `ResponseEvaluator(Protocol)` preparada para upgrade futuro (LLM-as-judge).

**Testes**: `tests/conversation/test_evaluator.py` — empty, short, bad encoding, long, clean pass.

### 2.8 Safety: Output Guard (M10)

**Arquivo**: `prosauai/safety/output_guard.py`

Função: `check_output(text) → GuardResult`

Diferente do input guard:
- PII detectado na saída É mascarado/removido (não apenas logado).
- Retorna `sanitized_text` pronto para envio.
- Pattern: CPF → `[CPF removido]`, phone → `[telefone removido]`, email → `[email removido]`.

**Testes**: `tests/safety/test_output_guard.py` — PII masking, clean text pass-through.

## Fase 3 — Integração + Tools (Dias 8-9)

### 3.1 Pipeline Orchestrator

**Arquivo**: `prosauai/conversation/pipeline.py`

Função principal: `process_conversation(request: ConversationRequest, app_state) → ConversationResponse`

Orquestra todas as etapas em sequência:

```python
async def process_conversation(request, app_state):
    pool = app_state.pg_pool
    semaphore = app_state.llm_semaphore
    tenant_store = app_state.tenant_store
    
    with tracer.start_as_current_span("conversation.process") as span:
        # 1. Resolve agent
        agent_config, prompt = await resolve_agent(pool, request.tenant_id, request.agent_id, tenant_store)
        
        # 2. Customer lookup/create
        customer = await get_or_create_customer(pool, request.tenant_id, request.sender_key)
        
        # 3. Conversation get/create
        conversation, is_new = await get_or_create_conversation(pool, request.tenant_id, customer.id, agent_config.id)
        
        # 4. Save inbound message
        inbound_msg = await save_message(pool, conversation.id, request.tenant_id, "inbound", request.text)
        
        # 5. Build context
        context = await build_context_window(pool, conversation.id, request.tenant_id)
        
        # 6. Input guard
        guard_result = await check_input(request.text)
        if not guard_result.allowed:
            return blocked_response(guard_result, request)
        
        # 7. Classify intent
        classification = await classify_intent(request.text, context, agent_config)
        
        # 8. Generate response (with retry)
        response_text, is_fallback = await generate_with_retry(
            agent_config, prompt, context, request.text, classification, deps, semaphore
        )
        
        # 9. Output guard
        output_result = await check_output(response_text)
        final_text = output_result.sanitized_text
        
        # 10. Save outbound message
        outbound_msg = await save_message(pool, conversation.id, request.tenant_id, "outbound", final_text)
        
        # 11. Update conversation state (async-safe)
        await update_conversation_state(pool, conversation.id, request.tenant_id, classification)
        
        # 12. Save eval score (fire-and-forget — never blocks delivery)
        asyncio.create_task(save_eval_score(pool, conversation.id, outbound_msg.id, request.tenant_id, eval_result))
        
        return ConversationResponse(...)
```

**generate_with_retry**: Chama `generate_response()`. Se `evaluator.evaluate()` retorna `action=retry` e retry_count < 1, tenta novamente. Se falha novamente, usa `FALLBACK_MESSAGE`.

### 3.2 Substituir _flush_echo

**Arquivo modificado**: `prosauai/main.py`

Substituir `_make_flush_callback` (echo) por `_make_flush_conversation`:

```python
def _make_flush_conversation(app: FastAPI):
    async def _flush_conversation(
        tenant_id: str,
        sender_key: str,
        group_id: str | None,
        text: str,
        agent_id: str | None,  # NEW parameter
    ) -> None:
        request = ConversationRequest(
            tenant_id=tenant_id,
            sender_key=sender_key,
            group_id=group_id,
            text=text,
            agent_id=agent_id,
        )
        result = await process_conversation(request, app.state)
        
        # Deliver response via EvolutionProvider
        tenant = app.state.tenant_store.get(tenant_id)
        provider = EvolutionProvider(...)
        try:
            await provider.send_text(
                to=sender_key,
                text=result.response_text,
                group_id=group_id,
            )
        finally:
            await provider.close()
    
    return _flush_conversation
```

### 3.3 ResenhAI Tool

**Arquivos**: `prosauai/tools/registry.py`, `prosauai/tools/resenhai.py`

Registry pattern (ADR-014):
```python
# registry.py
TOOL_REGISTRY: dict[str, Callable] = {}

def register_tool(name: str, *, category: str, required_params: list[str]):
    def decorator(func):
        TOOL_REGISTRY[name] = ToolEntry(func=func, category=category, required_params=required_params)
        return func
    return decorator
```

ResenhAI tool:
```python
# resenhai.py
@register_tool("resenhai_rankings", category="integration", required_params=["query"])
async def search_rankings(ctx: RunContext[ConversationDeps], query: str) -> str:
    """Busca rankings e estatísticas de futebol do ResenhAI."""
    # ACL: tenant_id injetado server-side (nunca do LLM)
    # HTTP call para API interna ResenhAI
    # Fallback: "Não consegui obter dados do ResenhAI no momento."
```

**MVP**: HTTP call para API interna. Se ResenhAI não tem API exposta ainda, implementar como stub que retorna dados mock. Tool funcional end-to-end mas dados podem ser estáticos.

**Testes**: `tests/tools/test_resenhai.py` — successful call, API failure fallback, ACL check.

### 3.4 OTel Spans

**Arquivo modificado**: `prosauai/observability/conventions.py`

Novos atributos:
```python
# Conversation pipeline (epic 005)
CONVERSATION_ID = "prosauai.conversation.id"
CUSTOMER_ID = "prosauai.customer.id"
CONVERSATION_IS_NEW = "prosauai.conversation.is_new"
CONVERSATION_INTENT = "prosauai.conversation.intent"
CONVERSATION_INTENT_CONFIDENCE = "prosauai.conversation.intent_confidence"
CONVERSATION_IS_FALLBACK = "prosauai.conversation.is_fallback"
CONVERSATION_TOOL_CALLS = "prosauai.conversation.tool_calls"
CONVERSATION_LATENCY_MS = "prosauai.conversation.latency_ms"
EVAL_QUALITY_SCORE = "prosauai.eval.quality_score"
EVAL_ACTION = "prosauai.eval.action"
```

Spans criados no pipeline:
1. `conversation.process` — span raiz do pipeline
2. `conversation.customer_lookup` — M4
3. `conversation.context_build` — M5
4. `conversation.input_guard` — M6
5. `conversation.classify` — M7
6. `conversation.generate` — M8
7. `conversation.evaluate` — M9
8. `conversation.output_guard` — M10
9. `conversation.deliver` — envio via EvolutionProvider
10. `conversation.save_eval` — fire-and-forget eval score

## Fase 4 — Testes + Polish (Dia 10)

### 4.1 RLS Isolation Tests

**Arquivo**: `tests/integration/test_rls_isolation.py`

Testa que:
1. Tenant A não vê customers de Tenant B.
2. Tenant A não vê conversations de Tenant B.
3. Tenant A não vê messages de Tenant B.
4. UPDATE em messages falha (append-only policy).
5. DELETE em messages falha (append-only policy).

### 4.2 Pipeline Integration Test

**Arquivo**: `tests/integration/test_conversation_pipeline.py`

Testa pipeline completo com:
- LLM mockado (pydantic-ai test mode).
- Postgres real (testcontainers ou fixture com cleanup).
- Redis real (existente nos testes).
- Verifica: customer criado, conversa criada, mensagens salvas, resposta retornada.

### 4.3 Multi-Tenant Parallel Test

Verifica que 2 tenants processando simultaneamente (asyncio.gather):
- Não compartilham dados.
- Usam agents diferentes.
- Respostas refletem system prompts distintos.

### 4.4 Estimativa de LOC

| Componente | Arquivos | LOC Estimado |
|------------|----------|-------------|
| Models | 1 | ~150 |
| Customer (M4) | 1 + test | ~100 + 120 |
| Context (M5) | 1 + test | ~180 + 150 |
| Input Guard (M6) | 2 + test | ~120 + 100 |
| Classifier (M7) | 1 + test | ~130 + 100 |
| Agent (M8) | 1 + test | ~250 + 200 |
| Evaluator (M9) | 1 + test | ~120 + 100 |
| Output Guard (M10) | 1 + test | ~80 + 80 |
| Pipeline | 1 + test | ~300 + 250 |
| DB layer | 3 | ~350 |
| Tools | 3 + test | ~200 + 100 |
| Migrations | 7 | ~300 |
| main.py changes | 1 | ~100 |
| debounce.py changes | 1 | ~50 |
| config.py changes | 1 | ~30 |
| docker-compose changes | 1 | ~20 |
| OTel conventions | 1 | ~30 |
| Integration tests | 2 | ~400 |
| **Total** | ~30 files | **~3900 LOC** |

**Nota**: Estimativa com multiplicador 1.5x aplicado (docstrings, error handling, logging). Sem multiplicador seria ~2600 LOC.

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| asyncpg + RLS overhead alto | Baixa | Alto | Pool de 10 conexões, `SET LOCAL` por transação (documentado em ADR-011 como viável) |
| pydantic-ai breaking change | Baixa | Médio | Pin version `>=1.70,<2.0`. Abstrair em `agent.py` — swap fácil |
| GPT-4o-mini qualidade PT-BR | Baixa | Médio | Model configurável por agent. Trocar para Claude se necessário |
| Debounce agent_id breaking change | Muito baixa | Baixo | Único caller (`start_listener`). Backward compat com fallback `None` |
| Migrations manuais drift | Média | Baixo | Scripts idempotentes (IF NOT EXISTS). Seed data com UUIDs fixos |
| ResenhAI API indisponível | Média | Baixo | Tool retorna fallback message. Agente responde sem dados |

## Decisões Arquiteturais Resumo

| # | Decisão | Alternativa Descartada | Justificativa |
|---|---------|----------------------|---------------|
| 1 | asyncpg direto (sem ORM) | SQLAlchemy async | 7 tabelas simples, queries diretas mais performantes, time-boxed |
| 2 | Migrations SQL manuais | Alembic | Scope pequeno (7 scripts), sem schema evolution esperada no MVP |
| 3 | Pipeline inline (sem worker) | ARQ worker separado | Debounce já desacopla, <100 RPM, semáforo(10) suficiente |
| 4 | Heurísticas (sem LLM judge) | LLM-as-judge para eval | Zero latência adicional, detecta problemas mais comuns, upgrade path preparado |
| 5 | Regex guardrails (Layer A) | ML classifier (Layer B) | <5ms, sem model deployment, cobre PII patterns BR |
| 6 | GPT-4o-mini direto (sem Bifrost) | Bifrost proxy | Sem need de cost tracking per-tenant no MVP, 1 provider (OpenAI) |
| 7 | Sliding window N=10 | Summarization async | Queries simples, conversas PME são curtas, token budget comporta |
| 8 | LLM intent classification | Keyword matching | Melhor accuracy, custo negligível, escala com novos intents |
| 9 | Tool registry declarativo | Tools avulsas | Whitelist enforcement, admin discoverability (ADR-014) |
| 10 | Postgres container | Supabase managed | Zero custo, controle total, RLS testável local |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo para Conversation Core (epic 005). 4 fases, 10 dias. Infraestrutura (PG + asyncpg + pydantic-ai, dias 1-3), pipeline de conversação (M4-M10, dias 4-7), integração + tools (dias 8-9), testes + polish (dia 10). ~3900 LOC em ~30 arquivos. Todas as decisões documentadas em research.md com alternativas. Data model com 7 tabelas + RLS. Contracts definidos para cada etapa do pipeline."
  blockers: []
  confidence: Alta
  kill_criteria: "Se asyncpg + RLS per-transaction apresentar latência >500ms (p95) para queries simples, ou se pydantic-ai não suportar tool calls com dependency injection, a arquitetura precisa revisão."
