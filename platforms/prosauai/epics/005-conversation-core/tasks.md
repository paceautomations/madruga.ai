# Tasks: Conversation Core

**Input**: Design documents from `platforms/prosauai/epics/005-conversation-core/`  
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/conversation-pipeline.md, research.md, quickstart.md  
**Tests**: TDD obrigatório (Constitution VII). Tests escritos ANTES da implementação.

**Organization**: Tasks agrupadas por user story para implementação e teste independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências)
- **[Story]**: User story a que pertence (US1-US6)
- File paths referem ao repositório prosauai (externo)

## Path Conventions

- **Source**: `prosauai/` (namespace Python)
- **Tests**: `tests/`
- **Migrations**: `migrations/`
- **Config**: Raiz do repositório prosauai

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Adicionar dependências, configurar Postgres container, novas settings.

- [x] T001 Adicionar `asyncpg>=0.30` e `pydantic-ai>=1.70` ao `pyproject.toml` (seção dependencies)
- [x] T002 [P] Adicionar serviço `postgres` (15-alpine) com volume `pgdata` e healthcheck ao `docker-compose.yml`
- [x] T003 [P] Adicionar novas settings de conversação em `prosauai/config.py`: `database_url`, `llm_semaphore_size=10`, `conversation_inactivity_timeout_hours=24`, `context_window_size=10`, `max_context_tokens=8000`, `openai_api_key`
- [x] T004 [P] Atualizar `.env.example` com novas variáveis: `DATABASE_URL`, `OPENAI_API_KEY`, `LLM_SEMAPHORE_SIZE`, `CONVERSATION_INACTIVITY_TIMEOUT_HOURS`, `CONTEXT_WINDOW_SIZE`, `MAX_CONTEXT_TOKENS`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migrations SQL com RLS, DB connection pool, repositories, domain models, debounce agent_id, OTel conventions.

**⚠️ CRITICAL**: Nenhuma user story pode iniciar até esta fase estar completa.

### Migrations SQL

- [x] T005 Criar `migrations/001_create_schema.sql` com extensão uuid-ossp e função `auth.tenant_id()` (SECURITY DEFINER) conforme data-model.md
- [x] T006 [P] Criar `migrations/002_customers.sql` com tabela `customers`, unique constraint `(tenant_id, phone_hash)`, RLS policy conforme data-model.md
- [x] T007 [P] Criar `migrations/003_conversations.sql` com tabela `conversations`, enum types, unique partial index `idx_one_active_per_customer`, RLS policy conforme data-model.md
- [x] T008 [P] Criar `migrations/003b_conversation_states.sql` com tabela `conversation_states`, unique constraint `(conversation_id)`, RLS policy conforme data-model.md
- [x] T009 [P] Criar `migrations/004_messages.sql` com tabela `messages`, enum `message_direction`, append-only policies (DENY UPDATE/DELETE), RLS conforme data-model.md
- [x] T010 [P] Criar `migrations/005_agents_prompts.sql` com tabelas `agents` e `prompts`, FK circular `active_prompt_id`, RLS policies conforme data-model.md
- [x] T011 [P] Criar `migrations/006_eval_scores.sql` com tabela `eval_scores`, RLS policy conforme data-model.md
- [x] T012 Criar `migrations/007_seed_data.sql` com dados iniciais para agents e prompts dos tenants Ariel e ResenhAI conforme data-model.md

### DB Layer

- [x] T013 Criar `prosauai/db/__init__.py` com exports do package
- [x] T014 Criar `prosauai/db/pool.py` com `create_pool()` (asyncpg), `with_tenant()` context manager para SET LOCAL RLS, e `close_pool()`
- [x] T015 Criar `prosauai/db/repositories.py` com `CustomerRepo`, `ConversationRepo`, `MessageRepo`, `AgentRepo`, `EvalScoreRepo` — thin layer sobre asyncpg com SQL parametrizado

### Domain Models

- [x] T016 Criar `prosauai/conversation/__init__.py` e `prosauai/conversation/models.py` com Pydantic models: `Customer`, `Conversation`, `Message`, `ConversationState`, `AgentConfig`, `PromptConfig`, `EvalScore`, `ContextMessage`, `ConversationRequest`, `ConversationResponse`, `GenerationResult`, `ClassificationResult`, `EvalResult`, `GuardResult`

### Safety Patterns (Shared)

- [x] T017 Criar `prosauai/safety/__init__.py` e `prosauai/safety/patterns.py` com regex patterns para CPF (`\d{3}\.?\d{3}\.?\d{3}-?\d{2}`), telefone BR (`\(?\d{2}\)?\s?\d{4,5}-?\d{4}`), email (`[\w.-]+@[\w.-]+\.\w+`), e constantes de mascaramento

### Debounce Changes

- [x] T018 Modificar `prosauai/core/debounce.py`: adicionar `agent_id` ao JSON item em `append()`, extrair em `_parse_flush_items()` (fallback None para items legacy), atualizar `FlushCallback` signature para `(tenant_id, sender_key, group_id, text, agent_id)`

### OTel Conventions

- [x] T019 Modificar `prosauai/observability/conventions.py`: adicionar novos span attribute constants — `CONVERSATION_ID`, `CUSTOMER_ID`, `CONVERSATION_IS_NEW`, `CONVERSATION_INTENT`, `CONVERSATION_INTENT_CONFIDENCE`, `CONVERSATION_IS_FALLBACK`, `CONVERSATION_TOOL_CALLS`, `CONVERSATION_LATENCY_MS`, `EVAL_QUALITY_SCORE`, `EVAL_ACTION`

### Lifespan Update

- [x] T020 Modificar `prosauai/main.py` lifespan: inicializar `app.state.pg_pool` (via `create_pool()`), `app.state.llm_semaphore` (asyncio.Semaphore), e fechar pool no shutdown

**Checkpoint**: Infraestrutura completa — migrations aplicáveis, pool funcional, models definidos. User stories podem iniciar.

---

## Phase 3: User Story 1 — Resposta IA a Mensagem Individual (Priority: P1) 🎯 MVP

**Goal**: Cliente envia mensagem WhatsApp individual → pipeline processa → agente responde com texto IA relevante em <30s.

**Independent Test**: Enviar mensagem WhatsApp individual e verificar resposta IA (não-echo), relevante, em <30s.

### Tests for User Story 1 (TDD — Constitution VII)

> **NOTE: Escrever estes testes PRIMEIRO, garantir que FALHAM antes da implementação**

- [x] T021 [P] [US1] Criar `tests/conversation/test_customer.py` com testes: create novo customer, get existente, update display_name, hash SHA-256 correto, customer por tenant isolado
- [x] T022 [P] [US1] Criar `tests/conversation/test_context.py` com testes: build window vazia, build com N mensagens, truncation por token limit, ordem cronológica correta
- [x] T023 [P] [US1] Criar `tests/conversation/test_classifier.py` com testes: intent conhecida, low confidence fallback (general), LLM failure fallback
- [x] T024 [P] [US1] Criar `tests/conversation/test_agent.py` com testes: geração com LLM mockado, timeout handling, sandwich prompt (prefix+system+suffix), semaphore limiting
- [x] T025 [P] [US1] Criar `tests/conversation/test_evaluator.py` com testes: resposta OK (score 1.0), resposta vazia (retry), muito curta <10 (retry), bad encoding (retry), muito longa >4000 (truncate), action deliver/retry/fallback
- [x] T026 [P] [US1] Criar `tests/conversation/test_pipeline.py` com testes: pipeline completo com LLM mockado (happy path), fallback quando LLM falha após retry, input guard bloqueio (mensagem longa), eval retry + fallback
- [x] T027 [P] [US1] Criar `tests/safety/test_input_guard.py` com testes: PII detection (CPF, phone, email), allowed=True com PII (não bloqueia), bloqueio por length >4000, injection detection, texto limpo
- [x] T028 [P] [US1] Criar `tests/safety/test_output_guard.py` com testes: PII masking (CPF→[CPF removido], phone→[telefone removido], email→[email removido]), texto limpo pass-through

### Implementation for User Story 1

- [x] T029 [US1] Implementar `prosauai/conversation/customer.py` — `get_or_create_customer()`: hash phone SHA-256, SELECT por (tenant_id, phone_hash), INSERT se não existe, UPDATE display_name se fornecido
- [x] T030 [US1] Implementar `prosauai/conversation/context.py` — `build_context_window()`: query últimas N mensagens, reverse para cronológica, estimar tokens (chars/4), truncar se >max_tokens. `get_or_create_conversation()`: busca ativa, check inactivity timeout, fecha/cria se expirada
- [x] T031 [US1] Implementar `prosauai/safety/input_guard.py` — `check_input()`: detectar PII via patterns.py, gerar sanitized_text, bloquear se >4000 chars ou injection detected, permitir com PII (hashear em logs)
- [x] T032 [US1] Implementar `prosauai/conversation/classifier.py` — `classify_intent()`: pydantic-ai Agent com structured output (`ClassificationOutput`), fallback intent="general" se confidence <0.7 ou LLM error
- [x] T033 [US1] Implementar `prosauai/conversation/agent.py` — `generate_response()`: aguardar semáforo, construir system prompt sandwich (safety_prefix + system_prompt + safety_suffix), criar pydantic-ai Agent com model do config, run com timeout 60s, retornar GenerationResult
- [x] T034 [US1] Implementar `prosauai/conversation/evaluator.py` — `evaluate_response()`: checks heurísticos (empty, too_short <10, bad_encoding \\ufffd, too_long >4000 truncar), score 0.0-1.0, action deliver/retry/fallback. Protocol `ResponseEvaluator` para upgrade futuro
- [x] T035 [US1] Implementar `prosauai/safety/output_guard.py` — `check_output()`: detectar PII via patterns.py, mascarar/remover PII na saída (diferente de input: aqui bloqueia), retornar sanitized_text pronto para envio
- [x] T036 [US1] Implementar `prosauai/conversation/pipeline.py` — `process_conversation()`: orquestrar etapas 1-12 (resolve agent, customer lookup, conversation get/create, save inbound msg, build context, input guard, classify, generate with retry, output guard, save outbound msg, update state, eval async). OTel spans por etapa. `generate_with_retry()`: retry 1x se eval rejeita, depois FALLBACK_MESSAGE
- [x] T037 [US1] Modificar `prosauai/main.py`: substituir `_make_flush_callback` (echo) por `_make_flush_conversation` que instancia `ConversationRequest` e chama `process_conversation()`, depois entrega via `EvolutionProvider.send_text()`
- [x] T038 [US1] Modificar `prosauai/main.py` webhook handler: passar `agent_id` do `RespondDecision` para `debounce.append()`

**Checkpoint**: US1 funcional — mensagem individual recebe resposta IA via pipeline completo. Testável de ponta a ponta.

---

## Phase 4: User Story 2 — Contexto Conversacional Persistente (Priority: P1)

**Goal**: Agente mantém contexto das últimas 10 mensagens e responde de forma coerente com o histórico.

**Independent Test**: Enviar 3 mensagens sequenciais onde a 3ª referencia a 1ª. Verificar resposta contextual.

### Tests for User Story 2 (TDD)

- [x] T039 [P] [US2] Criar `tests/conversation/test_context_lifecycle.py` com testes: conversa ativa reutilizada dentro do timeout, conversa encerrada após 24h de inatividade (status=closed, reason=inactivity_timeout), nova conversa criada após timeout, sliding window com >10 mensagens retorna apenas as 10 mais recentes
- [x] T040 [P] [US2] Criar `tests/integration/test_conversation_pipeline.py` com teste: pipeline completo com 3 mensagens sequenciais — LLM mockado, verificar que context_window contém mensagens anteriores, messages persistidas em ordem, conversation_state atualizado

### Implementation for User Story 2

- [x] T041 [US2] Estender `prosauai/conversation/context.py` — adicionar lógica de encerramento automático por inatividade no `get_or_create_conversation()`: checar `last_activity_at + inactivity_timeout_hours`, fechar conversa (status=closed, close_reason=inactivity_timeout, closed_at=now), criar nova se timeout expirado. Timeout configurável por tenant (range 1h-72h, default 24h)
- [x] T042 [US2] Estender `prosauai/conversation/pipeline.py` — garantir que `update_conversation_state()` persiste `context_window` (JSON das últimas 10 mensagens), `current_intent`, `intent_confidence`, `message_count`, `token_count` a cada interação
- [x] T043 [US2] Estender `prosauai/db/repositories.py` — `ConversationRepo.close_conversation()` e `ConversationRepo.update_last_activity()` para suportar lifecycle de conversa

**Checkpoint**: US2 funcional — contexto persistido, sliding window respeitada, conversas encerradas por inatividade.

---

## Phase 5: User Story 3 — Multi-Tenant com Agentes Independentes (Priority: P2)

**Goal**: 2 tenants (Ariel + ResenhAI) operam em paralelo com agentes IA independentes e zero vazamento de dados.

**Independent Test**: Configurar 2 tenants com system prompts distintos, enviar mesma pergunta para ambos, verificar respostas com personalidades diferentes.

### Tests for User Story 3 (TDD)

- [x] T044 [P] [US3] Criar `tests/integration/test_rls_isolation.py` com testes: tenant A não vê customers de tenant B, tenant A não vê conversations de tenant B, tenant A não vê messages de tenant B, UPDATE em messages falha (append-only), DELETE em messages falha (append-only), cada tabela com tenant_id tem RLS funcional
- [x] T045 [P] [US3] Criar `tests/integration/test_multi_tenant.py` com testes: 2 tenants processando simultaneamente (asyncio.gather), dados não compartilhados, agents diferentes usados, system prompts distintos refletidos nas respostas (LLM mockado com responses condicionais)

### Implementation for User Story 3

- [x] T046 [US3] Verificar e ajustar `prosauai/conversation/pipeline.py` — garantir que `tenant_id` é passado consistentemente em TODAS as chamadas de repositório e que `with_tenant()` é usado para cada transação. Validar que `resolve_agent()` carrega agent do tenant correto via RLS
- [x] T047 [US3] Ajustar `migrations/007_seed_data.sql` — garantir seed data com UUIDs fixos para 2 tenants (Ariel + ResenhAI) com system prompts distintos, models configurados, tools_enabled corretos. Tenant IDs devem corresponder aos de `tenants.yaml`

**Checkpoint**: US3 funcional — 2 tenants isolados, RLS verificado, agents independentes.

---

## Phase 6: User Story 4 — Resposta IA em Grupo com @Mention (Priority: P2)

**Goal**: Agente responde apenas a mensagens com @mention em grupos WhatsApp, com contexto relevante.

**Independent Test**: Enviar mensagem com @mention em grupo → resposta entregue. Mensagem sem @mention → sem resposta.

### Tests for User Story 4 (TDD)

- [x] T048 [P] [US4] Criar `tests/conversation/test_pipeline_group.py` com testes: pipeline processa mensagem de grupo com group_id preenchido, resposta entregue no grupo (group_id passado para EvolutionProvider.send_text), customer criado corretamente para contexto de grupo

### Implementation for User Story 4

- [x] T049 [US4] Verificar e ajustar `prosauai/conversation/pipeline.py` — garantir que `group_id` flui corretamente do `ConversationRequest` até `EvolutionProvider.send_text()`. Ajustar `_make_flush_conversation` para passar `group_id` na chamada de delivery. Sem lógica adicional necessária — o router MECE (epic 004) já filtra mensagens sem @mention (`IgnoreDecision`)

**Checkpoint**: US4 funcional — mensagens de grupo com @mention recebem resposta no grupo.

---

## Phase 7: User Story 5 — Consulta de Dados ResenhAI via Tool Call (Priority: P3)

**Goal**: Agente do ResenhAI usa tool call para consultar rankings/stats e inclui dados na resposta.

**Independent Test**: Perguntar "Qual o ranking atual?" ao agente ResenhAI → resposta inclui dados de ranking.

### Tests for User Story 5 (TDD)

- [ ] T050 [P] [US5] Criar `tests/tools/test_resenhai.py` com testes: tool call bem-sucedido (API mockada), fallback quando API indisponível, ACL check (tenant_id injetado server-side), tool registrado no registry
- [ ] T051 [P] [US5] Criar `tests/tools/test_registry.py` com testes: registro de tool, lookup por nome, whitelist enforcement (tool não habilitado não é acessível)

### Implementation for User Story 5

- [ ] T052 [US5] Criar `prosauai/tools/__init__.py` e `prosauai/tools/registry.py` — `TOOL_REGISTRY`, `register_tool()` decorator com category e required_params, função `get_enabled_tools()` que filtra por `prompt.tools_enabled` (whitelist enforcement ADR-014)
- [ ] T053 [US5] Criar `prosauai/tools/resenhai.py` — `search_rankings()` tool com `@register_tool("resenhai_rankings")`, ACL via `ctx.deps.tenant_id` (server-side), HTTP call para API interna ResenhAI (stub com dados mock se API não exposta), fallback message se serviço indisponível
- [ ] T054 [US5] Estender `prosauai/conversation/agent.py` — integrar tool registry: carregar tools habilitados do `prompt.tools_enabled`, registrar como pydantic-ai tools no Agent, injetar deps via `RunContext[ConversationDeps]`. Respeitar hard limit de 20 tool calls por conversa (ADR-016)

**Checkpoint**: US5 funcional — agente ResenhAI consulta rankings via tool call, ACL enforced.

---

## Phase 8: User Story 6 — Guardrails de Segurança (Priority: P3)

**Goal**: PII detectada por regex na entrada é hasheada em logs/traces. PII na saída é mascarada antes do envio.

**Independent Test**: Enviar mensagem com CPF → PII hasheado em logs, resposta não repete CPF.

### Tests for User Story 6 (TDD)

- [ ] T055 [P] [US6] Criar `tests/safety/test_pii_e2e.py` com testes: mensagem com CPF passa pelo pipeline (não bloqueia), PII hasheado em logs (SHA-256), resposta do LLM contendo telefone é mascarada na saída, OTel spans não contêm PII em texto plano
- [ ] T056 [P] [US6] Criar `tests/safety/test_patterns.py` com testes: regex CPF (com e sem pontuação), regex telefone BR (com e sem DDD/parênteses), regex email, false negatives e false positives comuns

### Implementation for User Story 6

- [ ] T057 [US6] Estender `prosauai/safety/input_guard.py` — integrar com structlog para log de PII hasheado (SHA-256), adicionar correlation_id no log, garantir que `sanitized_text` é usado em TODOS os logs e traces do pipeline
- [ ] T058 [US6] Estender `prosauai/conversation/pipeline.py` — garantir que OTel spans usam `sanitized_text` (nunca raw text com PII) nos atributos. PII detection result logado como tipo apenas (ex: `pii_types=["cpf", "email"]`), nunca o valor

**Checkpoint**: US6 funcional — PII nunca em texto plano em logs/traces, saída mascarada.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Melhorias que afetam múltiplas user stories.

- [ ] T059 [P] Adicionar docstrings em todos os módulos públicos de `prosauai/conversation/` e `prosauai/safety/`
- [ ] T060 [P] Verificar cobertura de testes ≥80% por módulo (M4-M10) com `pytest --cov`
- [ ] T061 Rodar validação do quickstart.md — verificar que todos os comandos funcionam (docker compose up, migrations, seed, health check)
- [ ] T062 [P] Verificar que todos os OTel spans do pipeline são visíveis no Phoenix (conversation.process, conversation.customer_lookup, conversation.context_build, conversation.input_guard, conversation.classify, conversation.generate, conversation.evaluate, conversation.output_guard, conversation.deliver, conversation.save_eval)
- [ ] T063 Code review final: verificar que FALLBACK_MESSAGE é usado em todos os error paths, connection pool sizing alinhado ao semáforo (10), e timeout de 5s para pool esgotado

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode iniciar imediatamente
- **Foundational (Phase 2)**: Depende de Setup (T001). BLOQUEIA todas as user stories
- **US1 (Phase 3)**: Depende de Foundational. É a base do MVP — implementa o pipeline inteiro
- **US2 (Phase 4)**: Depende de US1 (reutiliza pipeline, estende lifecycle de conversa)
- **US3 (Phase 5)**: Depende de US1 (testa isolamento do pipeline existente)
- **US4 (Phase 6)**: Depende de US1 (verifica group handling no pipeline)
- **US5 (Phase 7)**: Depende de US1 (estende agent com tools)
- **US6 (Phase 8)**: Depende de US1 (hardening de guardrails já implementados)
- **Polish (Phase 9)**: Depende de todas as US desejadas

### User Story Dependencies

- **US1 (P1)**: Pode iniciar após Foundational — independente de outras stories. **MVP scope.**
- **US2 (P1)**: Depende de US1 (context module e pipeline já implementados)
- **US3 (P2)**: Depende de US1 (pipeline funcional para testar isolamento). Parallelizável com US2
- **US4 (P2)**: Depende de US1 (pipeline funcional). Parallelizável com US2, US3
- **US5 (P3)**: Depende de US1 (agent module para integrar tools). Parallelizável com US2-US4
- **US6 (P3)**: Depende de US1 (guards já implementados, esta story hardening). Parallelizável com US2-US5

### Within Each User Story

- Tests MUST ser escritos e FALHAR antes da implementação (Constitution VII)
- Models antes de services
- Services antes de pipeline integration
- Core implementation antes de integration tests

### Parallel Opportunities

- T002, T003, T004 podem rodar em paralelo (Phase 1)
- T006-T011 podem rodar em paralelo (migrations independentes)
- T021-T028 podem rodar em paralelo (todos os testes de US1)
- US3, US4, US5, US6 podem rodar em paralelo após US1 (se equipe permitir)
- T059, T060, T062 podem rodar em paralelo (Phase 9)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together (TDD — write first, ensure they fail):
Task: "test_customer.py" — tests/conversation/test_customer.py
Task: "test_context.py" — tests/conversation/test_context.py
Task: "test_classifier.py" — tests/conversation/test_classifier.py
Task: "test_agent.py" — tests/conversation/test_agent.py
Task: "test_evaluator.py" — tests/conversation/test_evaluator.py
Task: "test_pipeline.py" — tests/conversation/test_pipeline.py
Task: "test_input_guard.py" — tests/safety/test_input_guard.py
Task: "test_output_guard.py" — tests/safety/test_output_guard.py

# Then implement modules (some parallelizable):
Task: "customer.py" — prosauai/conversation/customer.py       [P]
Task: "context.py" — prosauai/conversation/context.py         [P]
Task: "input_guard.py" — prosauai/safety/input_guard.py       [P]
Task: "classifier.py" — prosauai/conversation/classifier.py   (after models)
Task: "agent.py" — prosauai/conversation/agent.py             (after classifier)
Task: "evaluator.py" — prosauai/conversation/evaluator.py     [P]
Task: "output_guard.py" — prosauai/safety/output_guard.py     [P]
Task: "pipeline.py" — prosauai/conversation/pipeline.py       (after all modules)
Task: "main.py changes" — prosauai/main.py                     (after pipeline)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (deps, docker, config)
2. Complete Phase 2: Foundational (migrations, DB, models, debounce)
3. Complete Phase 3: User Story 1 — Pipeline completo de conversação
4. **STOP and VALIDATE**: Testar envio de mensagem WhatsApp → resposta IA
5. Deploy/demo se pronto — **este é o MVP**

### Incremental Delivery

1. Setup + Foundational → Infraestrutura pronta
2. Add US1 → Resposta IA funcional → **MVP!** Valor entregue
3. Add US2 → Contexto persistente → Experiência conversacional
4. Add US3 → Multi-tenant verificado → Isolamento garantido
5. Add US4 → Grupos suportados → Canal expandido
6. Add US5 → Tools ResenhAI → Feature específica de tenant
7. Add US6 → Guardrails hardened → Segurança reforçada
8. Polish → Cobertura, docs, validação final

### Estimativas

| Phase | Tasks | LOC Estimado |
|-------|-------|-------------|
| Setup | 4 | ~100 |
| Foundational | 16 | ~1200 |
| US1 (P1) | 18 | ~1800 |
| US2 (P1) | 5 | ~300 |
| US3 (P2) | 4 | ~350 |
| US4 (P2) | 2 | ~100 |
| US5 (P3) | 5 | ~400 |
| US6 (P3) | 4 | ~200 |
| Polish | 5 | ~50 |
| **Total** | **63** | **~4500 LOC** |

---

## Notes

- [P] tasks = arquivos diferentes, sem dependências
- [Story] label mapeia task para user story específica
- Cada user story deve ser independentemente completável e testável
- Verificar que testes FALHAM antes de implementar (TDD)
- Commitar após cada task ou grupo lógico
- Parar em qualquer checkpoint para validar story independentemente
- FALLBACK_MESSAGE: "Desculpe, não consegui processar sua mensagem. Tente novamente em instantes."
- Hard limits: 20 tool calls/conversa, 60s timeout LLM, 8K context tokens, semáforo 10

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "Tasks geradas para Conversation Core (epic 005). 63 tasks em 9 fases. MVP é US1 (Phase 3) — pipeline completo de conversação com IA. TDD obrigatório. 6 user stories organizadas por prioridade (P1→P3). ~4500 LOC estimados em ~30 arquivos. Parallel opportunities identificadas em cada fase."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o pipeline inline não suportar <30s end-to-end com semáforo 10, ou se pydantic-ai tool registration não funcionar com whitelist enforcement, a arquitetura de tasks precisa revisão."
