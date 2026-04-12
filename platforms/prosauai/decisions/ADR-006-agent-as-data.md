---
title: 'ADR-006: Agent-as-Data — multi-client, white-label e customizacao por tenant'
status: Accepted
decision: Agent-as-Data (JSONB)
alternatives: Classes Python por agente, YAML/TOML config files, Plataforma low-code
  (Botpress/Voiceflow), Full low-code builder para tenants (modelo Voiceflow)
rationale: Time-to-market de novo agente/tenant cai de horas para minutos
---
# ADR-006: Agent-as-Data — multi-client, white-label e customizacao por tenant
**Status:** Accepted | **Data:** 2026-03-23 | **Atualizado:** 2026-04-12

## Contexto
Cada novo caso de uso exige criar um agente com personalidade, tools e fluxo especificos. A abordagem tradicional e criar uma classe Python por agente. Precisamos escalar para dezenas de agentes sem deploy a cada novo caso.

Alem disso, ProsaUAI atende multiplos clientes (tenants) que precisam de:
- Setup rapido (< 15 minutos) sem envolver engenharia
- White-label (branding, tone, canais proprios)
- Customizacao granular (prompts, tools, guardrails, escalacao)
- Autonomia para product/ops gerenciar agentes sem deploy

## Decisao
We will representar agentes como configuracao JSONB no banco, nao como classes Python. Novo tenant = INSERT de config, zero deploy.

### Modelo multi-client
- Novo cliente = INSERT na tabela `agents` via admin panel (Next.js — ADR-010)
- Setup < 15 minutos: preencher config, conectar canal WhatsApp, subir knowledge base
- White-label: cada tenant controla branding, tone, welcome message, canal proprio (Evolution API — ADR-005)
- Dados do cliente sao propriedade do cliente (principio inviolavel)

### Routing declarativo MECE per-tenant (atualizado epic 004)

Cada tenant tem suas proprias regras de roteamento em arquivo YAML (`config/routing/{tenant}.yaml`). O Router MECE opera em duas camadas:
- **Layer 1 — classify()**: funcao pura que deriva `MessageFacts` (channel, event_kind, content_kind, has_mention, from_me, etc.)
- **Layer 2 — RoutingEngine.decide()**: avalia regras por prioridade, first-match wins. 5 acoes: RESPOND, LOG_ONLY, DROP, BYPASS_AI, EVENT_HOOK

Agent resolution para acoes RESPOND: `rule.agent` > `tenant.default_agent_id` > `AgentResolutionError`.

> **Nota:** A decisao original previa routing rules em tabela DB (`routing_rules`). A implementacao real (epic 004) adotou YAML per-tenant por simplicidade operacional na Fase 1. Migracao para DB-backed esta planejada no epic 006 (Configurable Routing).

### Config por agent (JSONB)
Campos configuráveis por tenant/agent:
- `system_prompt` — personalidade e instrucoes (texto livre)
- `template` — comportamento base: `support_1v1`, `group_responder`, `sales`
- `tools_enabled` — subset de tools filtrado por template/stage (anti-pattern #5: nunca tools globais)
- `tone` — estilo de comunicacao
- `welcome_message` — primeira mensagem ao usuario
- `escalation_rules` — quando e para onde escalar (Chatwoot, webhook, grupo)
- `active_hours` — horario de funcionamento
- `knowledge_source` — namespace do pgvector (ADR-013)
- `channel_config` — credenciais WhatsApp/Evolution API por tenant
- `billing_tier` — limites de mensagens (ADR-012)

### Camadas de customizacao (do mais simples ao mais avancado)

| Camada | O que customiza | Como |
|--------|----------------|------|
| **Template** | Comportamento base | Escolha: `support_1v1`, `group_responder`, `sales` — cada um com tools/tone predefinidos |
| **System prompt** | Personalidade e instrucoes | Texto livre editavel no admin |
| **Guardrails** | Limites entrada/saida | JSONB: PII detection, forbidden topics, max length, disclaimers (colunas explicitas — anti-pattern #6) |
| **Tools** | Capacidades do agente | Filtrado por template — support nao ve sales_tools (anti-pattern #5) |
| **Routing Rules** | Qual acao + agente por MessageFacts | YAML per-tenant (`config/routing/*.yaml`): when conditions → action + agent. Priority ASC, first-match wins. DB-backed planejado para epic 006 |
| **Pipeline Steps** | Sequencia de processamento do agente | `agent_pipeline_steps` table: classifier → clarifier → resolver → specialist (configuravel por agent). Zero steps = single LLM call |
| **Triggers** | Regras de escalacao | Phase 1: 4 hardcoded. v2: IF condition THEN action configuravel |
| **Router MECE** | Classificacao + decisao de roteamento | classify() → MessageFacts + RoutingEngine.decide() → 5 acoes (RESPOND, LOG_ONLY, DROP, BYPASS_AI, EVENT_HOOK). YAML per-tenant, MECE garantido em 4 camadas |

### Safety net para mudancas de config
- A/B testing com golden dataset antes de mudar prompts (score novo > baseline + 0.05 — ADR-008)
- **Canary rollout progressivo** — nova versao recebe % do trafego, comparacao automatica de eval scores, rollback imediato se regressao. Mecanismo completo em [ADR-019](./ADR-019-agent-config-versioning/)
- Sem auto-deploy de mudancas de prompt — human gate + review semanal (ADR-009, anti-pattern #12)
- "Prompt Review Friday" por tenant (data flywheel)

## Alternativas consideradas

### Classes Python por agente
- Pros: Type-safe, facil de debugar, IDE support completo, testes unitarios diretos
- Cons: Cada novo agente requer PR, code review e deploy; nao escala para dezenas de variantes; mudanca de prompt = deploy; onboarding de novo cliente depende de eng (anti-pattern #13)

### YAML/TOML config files
- Pros: Legivel, versionavel no git, familiar pro time
- Cons: Requer deploy para atualizar, nao suporta queries complexas, sem UI de edicao nativa, product/ops nao consegue mexer sozinho

### Plataforma low-code (Botpress/Voiceflow)
- Pros: Setup rapido, white-label nativo em alguns tiers, community de templates
- Cons: Vendor lock-in, sem controle do pipeline de LLM, custo cresce com mensagens, customizacao limitada do agent loop

### Full low-code builder para tenants (modelo Voiceflow)
- Pros: Tenant configura fluxos complexos sozinho, maximo de flexibilidade
- Cons: Complexidade absurda pro tenant configurar, 90% quer so mudar prompt + knowledge, overengineering

## Consequencias
- [+] Time-to-market de novo agente/tenant cai de horas para minutos
- [+] Product/ops pode ajustar agentes sem depender de eng
- [+] JSONB permite queries flexiveis (ex: "todos agentes que usam tool X")
- [+] White-label nativo — cada tenant controla branding sem fork de codigo
- [+] Camadas de customizacao permitem desde ajuste simples (prompt) ate avancado (triggers)
- [-] Menos type-safety — erros de config descobertos em runtime
- [-] Requer validacao robusta (JSON Schema ou Pydantic) para evitar configs invalidas
- [-] Debugging mais dificil — stack trace nao aponta direto pro "codigo" do agente
- [-] Guardrails JSONB pode virar "mega config" — mitiga com colunas explicitas e validacao strict
- [+] Routing rules: multiplos agentes por numero, cada um para um tipo de interacao — zero deploy
- [+] Pipeline steps: comportamento do agente configuravel per-tenant (classifier → resolver) sem mudar codigo
- [-] Routing rules mal configuradas podem direcionar mensagens ao agente errado — mitigar com validacao no admin + "test message" feature

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
