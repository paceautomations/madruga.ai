---
title: "Epic 005 — Conversation Core"
epic_id: "005-conversation-core"
platform: prosauai
status: shipped
created: 2026-04-12
updated: 2026-04-12
appetite: 2 semanas
---

# Epic 005 — Conversation Core

## Problem

O ProsaUAI hoje recebe mensagens WhatsApp, valida, roteia e faz debounce — mas responde com **echo** (repete o texto recebido). O pipeline inteiro (epics 001-004) e uma fundacao sem cerebro: Channel + Observability + Multi-Tenant + Router MECE estao prontos, mas o **core domain** (Conversation) nao existe.

Sem IA respondendo, a plataforma nao entrega valor. E o ultimo epic do MVP. Apos este epic, o agente WhatsApp multi-tenant responde com inteligencia, persiste conversas em BD, e entrega a proposta de valor: "agente responde mensagens 24/7".

**Evidencia do gap no codigo:**
- `prosauai/main.py:255-338` — `_flush_echo()` e o unico handler pos-debounce. Ecoa texto via `EvolutionProvider.send_text()`.
- `FlushCallback = Callable[[str, str, str | None, str], Awaitable[None]]` — signature fixa: `(tenant_id, sender_key, group_id, text)`.
- `RespondDecision.agent_id` e resolvido no router mas **perdido no debounce** — nao e passado para o flush callback. Gap critico para saber qual agente usar.
- Zero dependencias LLM no `pyproject.toml`. Nenhum `asyncpg`, `supabase`, `pydantic-ai`, `anthropic`.
- `Tenant` model tem `default_agent_id: UUID | None` mas nenhum campo de config LLM.
- Nenhuma tabela SQL existe no Supabase — schemas estao definidos no `domain-model.md` mas nao aplicados.

## Appetite

**2 semanas** (10 dias uteis). Escopo controlado: M4-M5-M7-M8 core + M6/M10 como regex+sandwich (sem ML). Avaliador (M9) como heuristico (sem LLM-as-judge). Worker inline (sem ARQ). Sem Bifrost — LLM direto via pydantic-ai.

## Solution

Substituir `_flush_echo()` por um pipeline completo de conversacao:

```
debounce.flush → Customer lookup/create → Context assembly → Guardrails entrada (regex) →
Classificacao (LLM) → Agente IA (pydantic-ai) → Avaliador (heuristico) →
Guardrails saida (regex) → Delivery (EvolutionProvider)
```

**Integracao com codebase existente:**

1. **Debounce → Conversation**: Modificar `FlushCallback` ou o buffer item para carregar `agent_id` (resolvido pelo router no webhook). O debounce Lua script ja suporta JSON items com metadata (`trace_context`); adicionar `agent_id` ao item.

2. **Supabase**: Adicionar container Postgres ao `docker-compose.yml`. Aplicar schemas do `domain-model.md` (customers, conversations, messages, conversation_states, prompts, eval_scores). RLS habilitado desde o dia 1 (ADR-011).

3. **pydantic-ai**: Adicionar como dependencia. Orquestrar M8 (Agente IA) com structured output. Model default: GPT-4o-mini, configuravel por agent via `agents.config.model`.

4. **OTel**: Reaproveitar `GEN_AI_SYSTEM` e `GEN_AI_REQUEST_MODEL` (ja definidos em `conventions.py`). Novos spans: `conversation.process`, `conversation.classify`, `conversation.generate`, `conversation.evaluate`.

## Dependencies

| Dep | Status | Impacto |
|-----|--------|---------|
| 001 Channel Pipeline | shipped | Webhook, formatter, debounce, EvolutionProvider — fundacao completa |
| 002 Observability | shipped | OTel SDK, Phoenix, structlog bridge — spans prontos para Conversation |
| 003 Multi-Tenant | shipped | TenantStore, per-tenant auth/keys/idempotency, tenant_id em tudo |
| 004 Router MECE | shipped | `RespondDecision.agent_id`, `classify()+decide()`, routing rules YAML |
| Supabase (PG 15) | **novo no 005** | Container + schemas + RLS. Primeira vez que BD relacional entra |
| pydantic-ai | **novo no 005** | Framework de orquestracao LLM. ADR-001 aprovado |
| OpenAI API key | **externo** | Necessario para GPT-4o-mini. Via `.env` (Infisical futuro) |

## Rabbit Holes

1. **Bifrost** — NAO implementar. MVP chama OpenAI diretamente via pydantic-ai. Bifrost e epic futuro quando cost tracking per-tenant for necessario. Trocar URL do provider depois e trivial.
2. **ARQ Worker separado** — NAO. Pipeline roda inline no debounce flush callback (async). O debounce ja desacopla do webhook (retorna 200 antes do flush). `asyncio.Semaphore(10)` limita chamadas LLM concorrentes. Worker separado quando throughput exigir (>100 RPM sustained).
3. **Guardrails ML (Layer B DistilBERT)** — NAO. Escopo de evals (epic 014/015). MVP usa regex (Layer A) + sandwich pattern no prompt (ADR-016).
4. **Avaliador LLM-as-judge** — NAO. MVP usa heuristicas (resposta vazia, muito curta, idioma errado). Interface preparada para plugar LLM-as-judge depois.
5. **Summarization async** — NAO. Sliding window puro (ultimas N=10 mensagens). Conversas de PME raramente passam 20 trocas. Summarization se dados reais mostrarem necessidade.
6. **ResenhAI cross-DB reads** — NAO como query direta. Implementar como tool call (pydantic-ai tool) para desacoplar. ACL pattern conforme context-map. Escopo do tool: query de ranking/stats via API interna.
7. **Agent Config Versioning (ADR-019)** — NAO. Canary rollout, traffic split, eval comparison sao escopo futuro. MVP usa `agents.active_version_id = NULL` (config direto no agent, sem versioning).
8. **Pipeline Steps (agent_pipeline_steps)** — NAO. MVP e single LLM call (zero steps = backward compatible conforme domain model invariante 17).

## No-gos

- Nenhuma tabela `agent_config_versions` ou `agent_pipeline_steps` populada (schemas criados mas vazios).
- Sem UI admin (epic 010).
- Sem handoff real para humano (epic 008). `BypassAIDecision` do router continua como log-only.
- Sem triggers proativos (epic 009).
- Sem knowledge base / RAG (epic 018).

## Acceptance Criteria

1. **Resposta IA funcional**: Agente recebe mensagem WhatsApp (individual ou grupo com @mention), processa via LLM (GPT-4o-mini default), e responde com texto relevante em PT-BR.
2. **Persistencia**: Conversations, messages e customers persistidos no Supabase com RLS por tenant.
3. **Multi-tenant**: 2 tenants (Ariel + ResenhAI) operam em paralelo com agentes independentes (system prompts diferentes).
4. **Contexto**: Sliding window de ultimas 10 mensagens mantido no conversation_state. Respostas sao contextuais (nao stateless).
5. **Guardrails basicos**: Regex PII (CPF, telefone, email) em entrada + sandwich pattern no prompt. Resposta bloqueada se guardrail falha.
6. **Avaliador heuristico**: Respostas vazias, muito curtas (<10 chars), ou com encoding estranho sao rejeitadas (retry 1x, depois fallback message).
7. **OTel spans**: Pipeline de conversacao traceable fim-a-fim no Phoenix (webhook → debounce → classify → generate → evaluate → deliver).
8. **Testes**: Unit tests para cada modulo (M4-M9), integration test do pipeline completo com LLM mockado. RLS isolation tests para todas as tabelas novas.
9. **agent_id preserved**: `RespondDecision.agent_id` flui do router ate o agente IA sem perda (via debounce buffer metadata).
10. **Tool call ResenhAI**: Agente pode chamar tool para consultar dados do ResenhAI (ranking, stats) — implementado como pydantic-ai tool com ACL.

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | BD | Supabase (PG 15) como BD de persistencia desde o dia 1. Docker Compose container. RLS habilitado. | ADR-011 (pool+RLS), domain-model.md |
| 2 | Framework LLM | pydantic-ai como orquestrador do agente IA. Model-agnostic, type-safe, tool use nativo. | ADR-001 (pydantic-ai) |
| 3 | LLM Provider | OpenAI direto (sem Bifrost). GPT-4o-mini default, configuravel por agent. Bifrost futuro. | ADR-002 (Bifrost — adiado), blueprint |
| 4 | Guardrails | Layer A (regex) + sandwich pattern. Sem ML classifier (Layer B) ou LLM-as-judge (Layer C). | ADR-016 (runtime safety) |
| 5 | Avaliador | Heuristico (length, empty, encoding). Sem LLM-as-judge. Interface preparada para upgrade. | domain-model M9 |
| 6 | Contexto | Sliding window N=10 mensagens. Sem summarization async. Token budget: system ~1000 + messages + reserve ~2000. | domain-model invariantes 21-24 |
| 7 | Worker | Inline no prosauai-api (debounce flush callback). Sem ARQ worker separado. Semaphore(10) para LLM. | blueprint (worker planejado — adiado) |
| 8 | ResenhAI | Tool call via pydantic-ai, nao query direta cross-DB. ACL pattern. | context-map relacao 19, ADR-014 |
| 9 | agent_id flow | Adicionar `agent_id` ao debounce buffer item JSON (ao lado de `trace_context`). Router resolve, debounce preserva, flush usa. | Gap identificado no codebase scan |
| 10 | Config versioning | Schemas criados mas nao populados. MVP usa agent config direto, sem canary/versioning. | ADR-019 (adiado) |

## Resolved Gray Areas

**1. Como agent_id chega do router ate o flush callback?**
O debounce Lua script ja serializa items como JSON (`{"text": "...", "trace_context": {...}}`). Adicionar `"agent_id": "uuid"` ao item. No flush, `_parse_flush_items()` extrai o agent_id. Se multiplos items com agent_ids diferentes (raro — mesmo sender, mesmo debounce window), usar o ultimo.

**2. Onde fica a logica de conversacao?**
Novo package `prosauai/conversation/` com modulos: `customer.py` (M4), `context.py` (M5), `classifier.py` (M7), `agent.py` (M8), `evaluator.py` (M9). Guardrails ficam em `prosauai/safety/` com `input_guard.py` (M6) e `output_guard.py` (M10).

**3. Como conectar com Supabase sem asyncpg complexo?**
Usar `asyncpg` diretamente (sem ORM). Connection pool no lifespan (`app.state.pg_pool`). Queries SQL puras com parametros tipados. RLS via `SET LOCAL` por transacao (ADR-011). Repositories thin layer sobre asyncpg.

**4. Onde ficam os system prompts iniciais?**
Seed SQL script que popula tabelas `agents` e `prompts` com dados iniciais para Ariel e ResenhAI. Cada tenant tem um agent com system prompt customizado. Prompts sao templates globais da plataforma.

**5. FlushCallback precisa mudar de signature?**
Nao. A signature `(tenant_id, sender_key, group_id, text)` e suficiente. O `agent_id` vem do buffer item (extraido no flush antes de chamar o callback), nao precisa ser parametro do callback. Alternativa: passar como kwarg ou context var. Decisao: extrair no flush e passar via parametro adicional — **sim, mudar signature para `(tenant_id, sender_key, group_id, text, agent_id)`**. Breaking change controlado (unico caller).

## Applicable Constraints

| Constraint | Source | Impact |
|------------|--------|--------|
| RLS obrigatorio em toda tabela com tenant_id | ADR-011 | Todas as novas tabelas (customers, conversations, messages, etc.) |
| PII nunca em logs/traces — sempre SHA-256 hash | ADR-018 | Logger de conversacao, OTel spans |
| Messages append-only — nunca editadas | domain-model invariante 2 | Storage layer |
| Uma conversa ativa por customer/channel | domain-model invariante 4 | Customer lookup logic |
| Eval scores asincronos — nunca bloqueiam resposta | domain-model invariante 7 | Evaluator design |
| TDD obrigatorio | constitution VII | Tests before implementation |
| Structured logging com correlation_id | constitution IX | Todos os novos modulos |
| Hard limits: 20 tool calls/conversa, 60s timeout, 8K context tokens | ADR-016 | Agent orchestrator |

## Suggested Approach

### Fase 1 — Infraestrutura (dias 1-3)

1. Adicionar Postgres container ao `docker-compose.yml`
2. Aplicar schemas SQL do domain-model (migrations)
3. Adicionar `asyncpg` + `pydantic-ai` ao `pyproject.toml`
4. Implementar connection pool no lifespan (`app.state.pg_pool`)
5. Seed data: agents + prompts para Ariel e ResenhAI
6. Modificar debounce buffer item para incluir `agent_id`
7. Atualizar `FlushCallback` signature: `(tenant_id, sender_key, group_id, text, agent_id)`

### Fase 2 — Conversation Pipeline (dias 4-7)

8. `prosauai/conversation/customer.py` — M4: lookup/create customer por phone+tenant
9. `prosauai/conversation/context.py` — M5: montar context window (ultimas 10 msgs)
10. `prosauai/safety/input_guard.py` — M6: regex PII + length checks
11. `prosauai/conversation/classifier.py` — M7: classificar intent via LLM (ou heuristica simples)
12. `prosauai/conversation/agent.py` — M8: pydantic-ai agent com system prompt + tools
13. `prosauai/conversation/evaluator.py` — M9: heuristicas de qualidade
14. `prosauai/safety/output_guard.py` — M10: regex PII na saida

### Fase 3 — Integracao + Tools (dias 8-9)

15. Substituir `_flush_echo()` por `_flush_conversation()` no main.py
16. Implementar ResenhAI tool (pydantic-ai tool com ACL)
17. OTel spans para cada etapa do pipeline
18. Integration tests: pipeline completo com LLM mockado

### Fase 4 — Polish + RLS (dia 10)

19. RLS isolation tests (cross-tenant)
20. Seed real com 2 tenants operando em paralelo
21. Teste end-to-end com LLM real (smoke test manual)
