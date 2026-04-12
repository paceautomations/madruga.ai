---
epic: 005-conversation-core
created: 2026-04-12
updated: 2026-04-12T21:00
---
# Registro de Decisoes — Epic 005

1. `[2026-04-12 epic-context]` Supabase (PG 15) como BD de persistencia desde o dia 1, com RLS habilitado em todas as tabelas (ref: ADR-011, domain-model.md)
2. `[2026-04-12 epic-context]` pydantic-ai como framework de orquestracao do agente IA, model-agnostic e type-safe (ref: ADR-001)
3. `[2026-04-12 epic-context]` OpenAI direto sem Bifrost no MVP; GPT-4o-mini default, configuravel por agent (ref: ADR-002 — Bifrost adiado)
4. `[2026-04-12 epic-context]` Guardrails somente Layer A (regex) + sandwich pattern no prompt; sem ML classifier ou LLM-as-judge (ref: ADR-016)
5. `[2026-04-12 epic-context]` Avaliador heuristico (length, empty, encoding) sem LLM-as-judge; interface preparada para upgrade futuro (ref: domain-model M9)
6. `[2026-04-12 epic-context]` Sliding window N=10 mensagens sem summarization async; token budget fixo system+messages+reserve (ref: domain-model invariantes 21-24)
7. `[2026-04-12 epic-context]` Pipeline inline no prosauai-api via debounce flush callback; sem ARQ worker separado; Semaphore(10) para LLM (ref: blueprint)
8. `[2026-04-12 epic-context]` ResenhAI via tool call pydantic-ai com ACL pattern, nao query direta cross-DB (ref: context-map relacao 19, ADR-014)
9. `[2026-04-12 epic-context]` agent_id adicionado ao debounce buffer item JSON para preservar routing decision ate o flush (ref: gap identificado no codebase scan)
10. `[2026-04-12 epic-context]` FlushCallback signature estendida para incluir agent_id como parametro adicional (ref: codebase scan — breaking change controlado)
11. `[2026-04-12 implement]` Adicionado ConversationStateRepo alem dos 5 repos listados em T015 (CustomerRepo, ConversationRepo, MessageRepo, AgentRepo, EvalScoreRepo). A tabela conversation_states precisa de repo dedicado para upsert do context_window/intent/counters a cada interacao. (ref: T015, data-model.md 003b_conversation_states.sql)
12. `[2026-04-12 implement]` Pipeline salva inbound message ANTES do input guard (plan.md pseudocode steps 4→6). Mensagens bloqueadas ficam persistidas para auditoria. Alternativa (data-model.md flowchart) sugeria guard antes do save, mas optou-se pelo plano para manter rastreabilidade completa. (ref: T036, F-004 analyze-report)
13. `[2026-04-12 implement]` Pipeline step 12 agora reconstroi context_window via build_context_window() APOS salvar outbound message (step 11), garantindo que conversation_state persiste contexto completo incluindo a resposta do agente. Antes, usava contexto stale do step 5 (pre-outbound). Custo: 1 query extra por interacao; beneficio: estado preciso para proxima mensagem. (ref: T042, FR-003)
