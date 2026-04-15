---
title: 'ADR-025: Default LLM model = openai:gpt-5.4-mini'
status: Accepted
decision: Migrate both main agent and classifier from openai:gpt-4o-mini to openai:gpt-5.4-mini
alternatives: Keep gpt-4o-mini (status quo), gpt-5-mini (non-reasoning), gpt-5 (full, overkill),
  Split (4o-mini classifier + 5.4-mini agent)
rationale: Tool-calling reliability, lower hallucination in pt-BR, and reasoning controls
  outweigh the ~$20-30/mes extra cost at 10k msgs/mes scale.
---
# ADR-025: Default LLM model = openai:gpt-5.4-mini

**Status:** Accepted | **Data:** 2026-04-14

## Contexto

O epic 005 (Conversation Core) foi seedado com `openai:gpt-4o-mini` ([migrations/007_seed_data.sql](../../../prosauai/migrations/007_seed_data.sql)) como decisao de baixo custo inicial enquanto o pipeline estabilizava. Com pipeline em producao e tool-calling ativo via pydantic-ai ([prosauai/tools/registry.py](../../../prosauai/prosauai/tools/registry.py)), o perfil de erros mudou: qualidade de selecao/parametrizacao de tools e aderencia ao system prompt passaram a importar mais que custo bruto por token.

OpenAI lancou em 17/marco/2026 o `gpt-5.4-mini` — familia com reasoning controls (`effort`/`verbosity`/`summary`), contexto 400k e custo ~3x do 5-mini (0.75/4.50 vs 0.25/2.00 por 1M tokens).

## Decisao

Migrar o modelo default de **todos** os agentes para `openai:gpt-5.4-mini`, incluindo:

1. **Agent principal** (conversa) — [prosauai/conversation/agent.py](../../../prosauai/prosauai/conversation/agent.py) fallback + seed dos tenants Ariel e ResenhAI.
2. **Classifier** (roda em toda mensagem) — [prosauai/conversation/classifier.py](../../../prosauai/prosauai/conversation/classifier.py).

Justificativas:

- **Tool calling** — reasoning models escolhem tool certa e preenchem args com muito menos erro. No WhatsApp customer-support, tool errada = ticket humano caro.
- **Aderencia ao system prompt** — multi-tenant com personas distintas; cada regra ignorada = experiencia inconsistente.
- **Menos alucinacao em pt-BR** — experiencia qualitativa consistente com benchmarks publicos.
- **Custo absoluto ainda baixo** — ~$32/mes em 10k msgs (vs ~$11 com 5-mini, ~$4 com 4o-mini). Diferenca de $20-30/mes nao justifica sacrificar qualidade em producao.

### Alternativas consideradas

| Alternativa | Por que nao |
|---|---|
| Manter gpt-4o-mini | Qualidade marginal em tool calling; alucina mais em pt-BR; sem reasoning. |
| gpt-5-mini (nao-reasoning) | ~3x mais barato que 5.4-mini mas sem reasoning; $20/mes nao justifica perder qualidade em tool calling. |
| gpt-5 full | Overkill, ~3x o custo de 5.4-mini sem ganho relevante pra mensagens curtas de WhatsApp. |
| Split (4o-mini classifier + 5.4-mini agent) | Economizaria no classifier (roda em toda msg), mas quebra consistencia e precisao de classificacao. Dono do produto escolheu consistencia. |

## Consequencias

### Positivas

- Tool calling mais confiavel (menos tickets escalados).
- System prompts respeitados com maior fidelidade (multi-tenant).
- Historico conversacional maior cabe no contexto (400k tokens).
- `temperature` e `max_tokens` passam a ser efetivos (fix correlato — ver nota abaixo).

### Negativas / riscos

- **Custo ~+50% sem cache** (em relacao a 4o-mini), ~+175% em relacao a 5-mini. Absoluto ainda baixo.
- **Reasoning tokens** contam como output e sao invisiveis — output real pode custar 20-40% mais que o estimado por `response_length`.
- **Latencia maior** — reasoning adiciona ~500-1500ms por chamada. Pipeline ja tolera 60s de timeout, sem impacto arquitetural, mas usuario pode notar respostas mais lentas.
- **Cache automatico ainda inativo** — requer system prompts >=1024 tokens pra kickar. Hoje prompts dos tenants tem ~150 tokens. Follow-up task (fora do escopo deste ADR) enriquece prompts para unlock do desconto de 90% no input cacheado.

### Fix correlato — ModelSettings efetivo

Descoberto ao planejar: `temperature` e `max_tokens` estavam em `agents.config` JSONB ([migrations/005_agents_prompts.sql](../../../prosauai/migrations/005_agents_prompts.sql)) mas nao eram aplicados no Agent do pydantic-ai. Corrigido no mesmo PR — agora sao passados via `ModelSettings(...)` em [prosauai/conversation/agent.py](../../../prosauai/prosauai/conversation/agent.py).

## Rollout

- Seed ([migrations/007_seed_data.sql](../../../prosauai/migrations/007_seed_data.sql)) atualizado para instalacoes novas.
- Migration 009 (`migrations/009_upgrade_agents_to_gpt5_mini.sql`) faz `UPDATE` idempotente para ambientes ja seedados (Docker dev `/docker-entrypoint-initdb.d/`; Supabase/prod aplicar manualmente via psql ou SQL Editor).
- Fallback em codigo em [prosauai/conversation/agent.py](../../../prosauai/prosauai/conversation/agent.py) atualizado para `openai:gpt-5.4-mini`.
- Classifier hardcoded em [prosauai/conversation/classifier.py](../../../prosauai/prosauai/conversation/classifier.py) atualizado.

## Follow-ups

1. Enriquecer system prompts >=1024 tokens por tenant para unlock do prompt caching (desconto de 90% input cacheado).
2. ~~Monitorar `classifier_llm_error` — se persistir apos upgrade, investigar separadamente.~~ **Resolvido 2026-04-15**: causa raiz era pydantic-ai 1.x renomeando `result_type` -> `output_type`; fix em [prosauai/conversation/classifier.py](../../../prosauai/prosauai/conversation/classifier.py) + teste de regressao nao-mockado + `record_exception` no except pra nao repetir o silent failure.
3. Adicionar dashboard no Phoenix com `input_tokens_cached / input_tokens_total` por tenant.
4. Avaliar override de `effort`/`verbosity` per-tenant via `OpenAIModelSettings` caso emerja necessidade (hoje defaults `medium/medium/auto` atendem customer support).
