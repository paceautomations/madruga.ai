---
title: 'ADR-006: Agent-as-Data — multi-client, white-label e customizacao por tenant'
status: Accepted
decision: Agent-as-Data (JSONB)
alternatives: Classes Python por agente, YAML/TOML config files, Plataforma low-code
  (Botpress/Voiceflow), Full low-code builder para tenants (modelo Voiceflow)
rationale: Time-to-market de novo agente/tenant cai de horas para minutos
---
# ADR-006: Agent-as-Data — multi-client, white-label e customizacao por tenant
**Status:** Accepted | **Data:** 2026-03-23 | **Atualizado:** 2026-03-25

## Contexto
Cada novo caso de uso exige criar um agente com personalidade, tools e fluxo especificos. A abordagem tradicional e criar uma classe Python por agente. Precisamos escalar para dezenas de agentes sem deploy a cada novo caso.

Alem disso, Fulano atende multiplos clientes (tenants) que precisam de:
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
| **Triggers** | Regras de escalacao | Phase 1: 4 hardcoded. v2: IF condition THEN action configuravel |
| **Smart Router** | Quando responder em grupos | 5 paths (mention, reply, save-only, event, ignore) com thresholds ajustaveis |

### Safety net para mudancas de config
- A/B testing com golden dataset antes de mudar prompts (score novo > baseline + 0.05 — ADR-008)
- **Canary rollout progressivo** — nova versao recebe % do trafego, comparacao automatica de eval scores, rollback imediato se regressao. Mecanismo completo em [ADR-019](/fulano/decisions/adr-019-agent-config-versioning/)
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
