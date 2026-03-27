---
title: "Deep Research: Multi-Tenant Conversational AI Agent Platforms"
---
# Deep Research: Multi-Tenant Conversational AI Agent Platforms

> **Data:** 2026-03-21
> **Escopo:** Use cases, architecture patterns, WhatsApp ecosystem, agent-as-platform design, competitive landscape
> **Target:** Plataforma Fulano (multi-tenant WhatsApp AI agents)

---

## 1. Use Cases Alem de Sales & Support

### 1.1 Use Cases Ja Validados pelo Mercado

| Categoria | Exemplo Concreto | Quem Faz | Relevancia Fulano |
|-----------|-----------------|----------|-------------------|
| **Suporte 1:1** | FAQ automatizado, ticket routing, handoff humano | Todos (Chatbase, Respond.io, Octadesk, Zenvia) | **Ja planejado** — ResenhAI support |
| **Grupo engagement** | Bot em grupo que responde @mentions, modera, publica stats | Niche (poucos fazem bem) | **Ja planejado** — ResenhAI groups |
| **Sales/SDR** | Lead qualification, outbound follow-up, CRM sync | Respond.io, Relevance AI, Zenvia | **Futuro** — sales template |
| **E-commerce/Catalogo** | Browse catalog no WhatsApp, checkout, tracking, abandoned cart | Zoko (Shopify), Charles, Infobip | **Medio prazo** — WhatsApp Catalogs API |
| **Onboarding/Training** | Sequencia de boas-vindas, quiz interativo, drip campaigns | Typebot, Botpress | **Alto potencial** — config-driven |
| **Scheduling/Coordenacao** | Agendamento de consultas, reservas, lembretes | Respond.io (Calendly), Typebot | **Alto potencial** — tool generico |
| **Pagamentos in-chat** | Cobranca, PIX, checkout WhatsApp Pay (India) | Infobip (India), Zoko | **Futuro** — depende de WhatsApp Payments BR |
| **Internal Ops** | Help desk interno, IT support, HR self-service | Yellow.ai, Salesforce Agentforce | **Medio prazo** — tenant = empresa |
| **Content creation** | Gerador de posts, imagens, resumos via chat | Relevance AI | **Baixo** — melhor via web app |
| **Community management** | Moderacao de grupo, welcome messages, rules enforcement | Evolution API + custom | **Alto potencial** — diferencial |
| **Notification/Alerts** | Proactive messages baseadas em eventos (game scheduled, ranking update) | Zenvia, Blip | **Ja planejado** — M13 Trigger Engine |
| **Pesquisas/CSAT** | Surveys pos-atendimento, NPS, feedback collection | Octadesk, Zenvia | **Alto potencial** — WhatsApp Flows |

### 1.2 Use Cases Emergentes (2025-2026)

1. **Agentes de comunidade esportiva** — O que ResenhAI precisa. Nenhum player grande faz isso bem. Bot em grupo que:
   - Publica ranking automaticamente
   - Responde stats de jogadores quando perguntado
   - Organiza proximos jogos via poll
   - Modera e engaja (memes, provocacoes contextuais)
   - **Diferencial enorme** se bem executado

2. **WhatsApp Flows como mini-apps** — Formularios estruturados dentro do WhatsApp (lead gen, insurance quotes, loan applications). Meta investiu pesado nisso. Agentes que combinam conversa livre + flows estruturados sao o futuro.

3. **Voice-first agents** — WhatsApp agora suporta chamadas de voz via Business API. Agentes que transcrevem audio e respondem (Respond.io ja faz). Relevante para publico que prefere audio.

4. **Multi-agent workforces** — Relevance AI lidera aqui: SDR + Enrichment + Router + Support como agentes separados orquestrados. Pattern: agente especialista > agente generalista.

5. **Agent-assisted human** (copilot mode) — Em vez de substituir humano, o agente sugere respostas, resume historico, classifica sentimento. Intercom Fin e Chatwoot Captain fazem isso.

### 1.3 Recomendacao para Fulano

**Prioridade 1 (ja no roadmap):** Support 1:1, Group engagement, Proactive messages
**Prioridade 2 (Q3 2026):** Onboarding sequences, Scheduling agents, CSAT/Surveys (via Flows)
**Prioridade 3 (Q4 2026):** E-commerce catalog agents, Sales/SDR templates
**Prioridade 4 (2027):** Internal ops, Multi-agent workforces, Voice agents

---

## 2. Multi-Tenant Architecture Patterns

### 2.1 Modelos de Isolamento

Com base em Azure Architecture Center, AWS SaaS patterns, e analise dos players:

| Modelo | Descricao | Quando Usar | Quem Usa |
|--------|-----------|-------------|----------|
| **Silo (dedicated)** | Infra separada por tenant (DB, compute, queue) | Enterprise com compliance forte, dados sensiveis | Bland.ai (dedicated instances) |
| **Pool (shared)** | Infra compartilhada, isolamento logico (tenant_id em toda query) | Maioria dos SaaS, custo-eficiente | Botpress, Chatbase, Respond.io |
| **Bridge (hibrido)** | Shared compute + DB por tenant (ou schema por tenant) | Balanço entre custo e isolamento | Salesforce Agentforce |

**Recomendacao Fulano: Pool model com Supabase RLS** — ja esta na arquitetura atual e e a escolha correta:
- Supabase RLS garante isolamento de dados sem overhead de infra
- `tenant_id` em toda tabela
- Custo marginal por tenant proximo de zero
- Escala para centenas de tenants antes de precisar sharding

### 2.2 Como os Players Lidam com Multi-Tenancy

#### Botpress
- **Isolamento:** Bots separados por workspace, vector DB storage por bot (100MB free → 2GB team)
- **Shared infra:** Compute compartilhado, AI spend passado at-cost sem markup
- **Customizacao:** Cada bot tem seus prompts, knowledge base (vector store), e tools
- **Billing:** Base subscription + messages/events (500 free → 50K team) + AI spend (metered at provider cost)
- **Knowledge per tenant:** Vector DB separado por bot, auto-retrain, file storage (100MB → 10GB)
- **Limite:** 1-3 bots por plano (add-on $10/bot)

#### Voiceflow
- **Isolamento:** Workspaces separados por projeto, credits system
- **Multi-client:** White-labeling, multi-client workspace management (agency tier)
- **Billing:** Credits-based (message credits com multiplicador por tamanho do projeto, 1x-20x)
- **Knowledge:** Por projeto, com creditos de processamento
- **Destaque:** Melhor modelo para agencias — gerenciar N clientes de um workspace

#### Chatbase
- **Isolamento:** Agents separados por conta, public/private toggle
- **White-label:** Remove branding, custom instructions por agent
- **Billing:** Planos fixos ($40-$500/mo) com message credits, data limits por tier (400KB → 40MB)
- **Knowledge:** Por agent, auto-retrain, multiple data sources
- **Integracao WhatsApp:** Nativa

#### Relevance AI
- **Multi-agent:** Unlimited agents em todos os planos, workforces compostas
- **Billing:** Actions-based ($0 free/200 actions → $234/mo team/84K actions)
- **Multi-org:** Enterprise only
- **Destaque:** BYOLLM (bring your own LLM) no Pro+

#### Salesforce Agentforce
- **Isolamento:** Multi-tenant nativo do Salesforce (metadata-driven)
- **Agent Builder:** Low-code, topics customizaveis por org
- **Knowledge:** "Intelligent Context" + Data 360 (structured + unstructured)
- **Billing:** Flex Credits, Conversations, ou per-user licensing
- **Atlas Reasoning Engine:** Decompoe tasks complexas em subtasks

### 2.3 Patterns Criticos para Fulano

#### 2.3.1 Tenant Isolation Stack

```
┌─────────────────────────────────────────────────┐
│                    SHARED                        │
│  FastAPI (compute) │ Redis (cache/queue) │ LLM   │
│  Evolution API     │ LangFuse            │ Bifrost│
└─────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────┐
│              PER-TENANT (logical)                │
│  Supabase RLS     │ Prompts/Config  │ Knowledge  │
│  (tenant_id)      │ (JSONB)         │ (pgvector) │
│  Tools config     │ Agent params    │ Triggers    │
│  Conversation     │ Guardrails      │ Evals       │
│  history          │ rules           │ thresholds  │
└─────────────────────────────────────────────────┘
```

#### 2.3.2 Per-Tenant Configuration Model

Cada tenant precisa de:
1. **System prompt** — Persona, tom, regras de negocio
2. **Knowledge base** — Documentos, FAQs, dados especificos (pgvector namespace por tenant)
3. **Tools** — Quais tools o agent pode usar (Supabase queries, APIs externas, calendarios)
4. **Guardrails** — Topicos proibidos, PII rules, escalation triggers
5. **Triggers** — Eventos que disparam mensagens proativas
6. **Channel config** — WhatsApp number(s), Evolution instance, template messages
7. **Billing limits** — Max messages/mo, max LLM spend, overage policy

#### 2.3.3 Noisy Neighbor Mitigation

- **Rate limiting per tenant** no Redis (sliding window)
- **LLM spend caps** por tenant (Bifrost + LangFuse tracking)
- **Queue priority** — tenants pagantes vs free tier
- **Circuit breaker** — se um tenant gerar loops, isolar sem afetar outros

#### 2.3.4 Knowledge Base per Tenant

Pattern recomendado (pgvector + Supabase):
- Cada tenant tem embeddings com `tenant_id` como filtro
- Index: `CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops) WHERE tenant_id = X`
- Partial indexes por tenant para performance
- Upload via admin: PDF, TXT, CSV, URLs → chunk → embed → store
- Auto-retrain quando documentos atualizados

---

## 3. WhatsApp Business API Ecosystem 2026

### 3.1 Mudanca Critica: Per-Template Pricing (Julho 2025)

**ANTES (ate Jun 2025):** Cobranca por conversacao de 24h
**DEPOIS (Jul 2025+):** Cobranca por template message enviada

| Categoria | Modelo | Custo Relativo |
|-----------|--------|----------------|
| **Service** (user-initiated) | **GRATIS** desde Nov 2024 | $0 |
| **Utility** (pos-transacao) | Per-template, mais barato | $ |
| **Authentication** (OTP) | Per-template, medio | $$ |
| **Marketing** (promos, ofertas) | Per-template, mais caro | $$$ |

**Impacto para Fulano:**
- Respostas a mensagens do usuario = **gratis** (service window 24h)
- Click-to-WhatsApp ads = **gratis por 72h**
- 1.000 service conversations/mes gratis por WABA
- Templates proativos (M13 Trigger Engine) = custo variavel por categoria
- **Otimizacao:** Maximizar respostas dentro do service window, minimizar templates marketing

### 3.2 Features Disponiveis para Agentes

| Feature | Status | Uso para Agentes |
|---------|--------|-----------------|
| **WhatsApp Flows** | GA | Mini-formularios in-chat: onboarding, surveys, lead gen, insurance quotes. AI pode gerar flow definitions. |
| **Catalogs** | GA | Product browsing + checkout dentro do WhatsApp. Agent pode navegar catalogo com usuario. |
| **Payments** | India only (PIX futuro?) | Checkout in-chat. Ainda limitado geograficamente. |
| **Interactive messages** | GA | Buttons (max 3), lists, location requests. Essenciais para UX estruturada. |
| **Template messages** | GA (4 categorias) | Mensagens proativas fora do service window. Precisam aprovacao da Meta. |
| **Voice calls** | Beta/GA | Inbound gratis, outbound pago. Agents que transcrevem audio ja existem. |
| **Reactions** | GA | Agents podem reagir a mensagens (acknowledge, like). UX humanizada. |
| **Media messages** | GA | Imagens, videos (.mp4), documentos, stickers, contacts, locations. |

### 3.3 Limitacoes Importantes

- **Max 3 buttons** por mensagem (mais vao para "..." navigation)
- **Button text max 20 chars**
- **GIF e SVG nao suportados**
- **Video so .mp4**
- **Todos os numeros de um WABA compartilham o mesmo messaging limit** — precisa planejar capacidade
- **Templates precisam aprovacao** da Meta (24-72h)
- **Groups via Cloud API** — limitacoes vs Baileys (Evolution API suporta ambos)

### 3.4 BSP (Business Solution Provider) Landscape

| BSP | Markup | Diferencial |
|-----|--------|-------------|
| **Respond.io** | Zero markup | Plataforma completa, AI agents |
| **Twilio** | Markup variavel | ISV Tech Provider Program, multi-WABA |
| **Infobip** | Markup variavel | CPaaS completo, WhatsApp Payments (India) |
| **360dialog** | Baixo markup | Focado em WhatsApp, API simples |
| **Evolution API** | Zero (self-hosted) | Open-source, Baileys + Cloud API, gratis |

**Recomendacao Fulano:** Manter Evolution API (zero cost, full control, grupo support via Baileys). Adapter pattern para Cloud API direta quando necessario.

---

## 4. Agent-as-a-Platform: Configuration-Driven Design

### 4.1 O Principio

> Adicionar um novo use case (ex: "agente de reserva de restaurante") deve ser **configuracao, nao codigo**.

Isso significa que a plataforma precisa de:
1. **Agent Definition** como dados (nao como classe Python)
2. **Tool Registry** plugavel
3. **Knowledge Base** upload self-service
4. **Guardrails** configuraveis
5. **Trigger Engine** baseada em eventos genericos

### 4.2 Como os Melhores Fazem

#### GPT Runner Pattern (config-driven agents)
- Cada agente = um arquivo `.gpt.md` (markdown com frontmatter)
- Persona, instructions, tools = declarativos
- Versionavel via git
- Non-technical users podem criar/editar agents

#### Botpress Agent Builder
- Visual flow builder + knowledge base + custom actions
- Cada "bot" = uma config isolada com seus prompts + tools
- Deploy em multiplos canais com um clique

#### Salesforce Agent Builder
- Topics + actions definidos via low-code
- Reutiliza recursos existentes da org (objetos, flows, apex)
- Metadata-driven: tudo e config, nao codigo

#### Anthropic's Recommendation
- **Start simple** — prompt chaining antes de agents autonomos
- **Routing pattern** — classifier direciona para prompts especializados
- **Tool engineering** e tao importante quanto prompt engineering
- **Poka-yoke** — tools devem impedir erros por design (ex: forcar absolute paths)

### 4.3 Modelo Proposto para Fulano

```yaml
# Exemplo: Agent Definition (armazenado como JSONB no Supabase)
agent:
  id: "resenhai-support"
  tenant_id: "resenhai"
  name: "ResenhAI Suporte"
  type: "support"  # support | group | sales | onboarding | scheduling

  llm:
    primary: "claude-sonnet-4-6"
    router: "claude-haiku-4-5"
    temperature: 0.7
    max_tokens: 500

  persona:
    system_prompt: "Voce e o assistente do ResenhAI..."
    tone: "casual-br"
    language: "pt-BR"

  knowledge:
    sources:
      - type: "documents"
        collection: "resenhai-faq"
      - type: "api"
        endpoint: "https://api.resenhai.com/v1"

  tools:
    enabled:
      - "search_knowledge_base"
      - "query_resenhai_api"  # stats, jogos, ranking
      - "create_support_ticket"
      - "handoff_to_human"
    disabled:
      - "send_payment_link"
      - "modify_account"

  guardrails:
    blocked_topics: ["politica", "religiao", "apostas"]
    pii_handling: "mask"
    max_response_length: 500
    escalation_triggers: ["falar com humano", "reclamacao", "cancelar"]

  triggers:
    - event: "user.first_message"
      action: "send_welcome_template"
      template_id: "welcome_resenhai"
    - event: "game.scheduled"
      action: "notify_group"
      template_id: "game_reminder"

  channel:
    whatsapp_number: "+5511999999999"
    evolution_instance: "resenhai-prod"
    group_behavior: "respond_on_mention"
    individual_behavior: "always_respond"
```

### 4.4 Novo Use Case = Nova Config

Para adicionar "agente de restaurante":
1. Admin cria tenant no dashboard
2. Admin define agent config (persona, tools, knowledge)
3. Admin faz upload de FAQs/cardapio (knowledge base)
4. Admin conecta WhatsApp number (Evolution API instance)
5. Admin configura triggers (reserva confirmada → mensagem de lembrete)
6. **Zero codigo novo**

O que precisa ser **codigo** (desenvolvido uma vez):
- Tools novos (ex: `make_reservation` → integracao com sistema de reservas)
- Novos types de trigger events
- Novos guardrail rules

**Pattern:** Tool Registry — tools sao classes registradas com metadata:

```python
@tool_registry.register(
    name="make_reservation",
    description="Faz reserva no restaurante",
    required_params=["date", "time", "party_size"],
    category="scheduling",
    requires_integration="restaurant_api"
)
async def make_reservation(ctx: ToolContext, date: str, time: str, party_size: int):
    ...
```

Tenants habilitam tools no agent config. O LLM so ve tools habilitados.

---

## 5. Competitive Landscape

### 5.1 Players Globais (Plataformas de Agentes Multi-Tenant)

| Player | Tipo | WhatsApp | Multi-Tenant | Preco Entry | Diferencial | Fraqueza |
|--------|------|----------|-------------|-------------|-------------|----------|
| **Botpress** | Agent builder | Sim | Workspaces | $0 (PAYG) | Visual builder, AI spend at-cost | Limite de 1-3 bots por plano |
| **Voiceflow** | Agent builder | Via integracao | Workspaces + white-label | $60/mo | Melhor para agencias, credits system | Caro para alto volume |
| **Chatbase** | AI support agent | Sim (nativo) | Per-agent | $40/mo | White-label, setup rapido, SOC 2 | Knowledge base pequena (40MB max) |
| **Respond.io** | Messaging platform | Sim (core) | Teams | $79/mo | Zero markup WhatsApp, AI agents | Nao e agent-first, mais inbox |
| **Relevance AI** | Multi-agent platform | Sim | Workforces | $19/mo | Multi-agent orchestration, BYOLLM | Focado em GTM/sales, nao messaging |
| **Salesforce Agentforce** | Enterprise agent | Via ecosystem | Nativo Salesforce | Flex credits | Atlas engine, deep CRM integration | Lock-in Salesforce, enterprise-only |
| **Intercom Fin** | Support AI | Sim | Per-workspace | $29/resolved | Pay-per-resolution, high quality | Caro em escala, support-only |

### 5.2 Players Brasil (Foco WhatsApp)

| Player | Tipo | WhatsApp | Preco | Diferencial | Fraqueza |
|--------|------|----------|-------|-------------|----------|
| **Blip (Take)** | CPaaS + AI | Core | Enterprise | Maior player BR, multi-canal, AI agents | Caro, enterprise-focused |
| **Zenvia** | CPaaS + AI | Core | Enterprise | 10K+ clientes, CDP nativo, AI agents | Complexo, enterprise pricing |
| **Octadesk** | Support + AI | Core | Segmentado | WOZ 2.0 (AI agent), 2500 clientes, 9.3 Reclame Aqui | Menos flexivel, nao e plataforma de agentes |
| **Zoko** | WhatsApp Commerce | Core | Freemium | Shopify-native, catalogs, broadcasts | Nicho Shopify |
| **Evolution API** | Open-source API | Core | Gratis | Self-hosted, Baileys + Cloud API, Typebot/Chatwoot integration | Nao tem AI built-in, requer dev |

### 5.3 Players Open-Source (Build Blocks)

| Player | Tipo | WhatsApp | Uso para Fulano |
|--------|------|----------|-----------------|
| **Evolution API** | WhatsApp connector | Nativo | **Ja em uso** — core da infraestrutura |
| **Typebot** | No-code chatbot | Sim | Inspiracao para flow builder, 650+ empresas, WhatsApp nativo |
| **Chatwoot** | Omnichannel inbox | Sim | Inspiracao para handoff inbox, Captain AI agent |
| **LangGraph** | Agent orchestration | N/A | Patterns de state management, durable execution, memory |
| **n8n** | Workflow automation | Sim | Inspiracao para trigger engine, ja usado pela SereIA |

### 5.4 Posicionamento Fulano no Mercado

```
                    Enterprise ────────────────────── SMB/Startup
                         │                               │
                    Salesforce                       Botpress
                    Agentforce                       Chatbase
                         │                               │
                      Zenvia                         Respond.io
                       Blip                          Voiceflow
                         │                               │
          ───────────────┼───────────────────────────────┼──────
          Generic        │           FULANO              │  Niche
          Platform       │     (WhatsApp-first,          │  Tool
                         │      config-driven,           │
                         │      grupo + 1:1 + proativo,  │
                         │      Brasil-first)            │
                         │                               │
                    Octadesk                            Zoko
                    (support)                         (Shopify)
```

**Fulano se posiciona como:**
- **WhatsApp-first** (nao omnichannel — foco gera profundidade)
- **Config-driven** (novo use case = nova config, nao codigo)
- **Group + 1:1 + proativo** (poucos fazem os 3 bem)
- **Brasil-first** (PT-BR nativo, PIX futuro, cultura local)
- **Self-hosted option** (Evolution API, zero vendor lock-in)
- **Developer-friendly** (API-first, nao visual builder)

---

## 6. Recomendacoes Especificas para Fulano

### 6.1 Arquitetura (validada pela pesquisa)

A arquitetura atual do Fulano (plano-tecnico.md + module-map.md) esta **bem alinhada** com os patterns do mercado:

| Decisao Fulano | Validacao Mercado | Status |
|---------------|-------------------|--------|
| Pool model + Supabase RLS | Padrao da industria para < 500 tenants | OK |
| pydantic-ai agents | Alinhado com Anthropic's "start simple" | OK |
| Evolution API | Unico player que faz grupo + 1:1 + Cloud API | OK |
| Redis message buffer | Pattern universal (debounce WhatsApp) | OK |
| LangFuse observability | Equivalente ao que Botpress/Voiceflow tem built-in | OK |
| Config-driven agents (JSONB) | Pattern GPT Runner + Salesforce Agent Builder | OK |
| Bifrost LLM proxy | Unico — maioria usa LiteLLM ou direto. Boa escolha. | OK |

**Gaps identificados pela pesquisa:**

1. **Tool Registry pattern** — Falta no plano atual. Implementar registro declarativo de tools com metadata (nome, params, categoria, integracao requerida). Tenant habilita/desabilita tools via config.

2. **Agent Definition as Data** — O plano tem agents como classes Python (support.py, group.py, sales.py). Migrar para agent definition como JSONB no Supabase, com factory que instancia pydantic-ai agent a partir da config. Classes viram templates, nao implementacoes.

3. **WhatsApp Flows integration** — Nenhum modulo cobre. Adicionar capacidade de enviar Flows (surveys, forms) como parte da resposta do agent. Huge UX win.

4. **Usage metering per tenant** — LangFuse rastreia custo LLM, mas falta metering de messages, API calls, storage para billing. Adicionar counters no Redis com flush periodico para Supabase.

5. **White-label admin** — Plano atual tem admin Next.js. Considerar multi-tenant admin onde cada tenant ve so seus dados (Supabase RLS via JWT claims).

### 6.2 Billing Model

Com base nos modelos do mercado:

| Modelo | Quem Usa | Pros | Contras |
|--------|----------|------|---------|
| **Per-message** | Botpress, Chatbase | Simples, previsivel | Penaliza chatty agents |
| **Per-conversation** | Intercom ($29/resolved) | Alinhado com valor | Dificil definir "resolvido" |
| **Credits** | Voiceflow, Relevance AI | Flexivel, multipliers | Complexo de explicar |
| **Base + usage** | Botpress (sub + AI spend) | Receita recorrente + upside | Dois componentes |

**Recomendacao Fulano:**
```
Tier Free:     R$0/mo — 100 msgs, 1 agent, 1 WhatsApp number
Tier Starter:  R$197/mo — 2.000 msgs, 3 agents, 2 numbers, knowledge base 500MB
Tier Growth:   R$497/mo — 10.000 msgs, 10 agents, 5 numbers, knowledge base 2GB
Tier Business: R$997/mo — 50.000 msgs, unlimited agents, 10 numbers, knowledge base 10GB
Enterprise:    Custom — dedicated support, SLA, custom tools development

+ LLM spend pass-through at cost (como Botpress — sem markup)
+ WhatsApp template costs pass-through (Meta cobra direto ou via BSP)
```

### 6.3 Diferenciacao Competitiva

O que Fulano pode fazer que **ninguem faz bem**:

1. **Group AI Agent** — Nenhum dos grandes (Botpress, Voiceflow, Chatbase) tem suporte real a grupos WhatsApp. Fulano ja tem M3 (Smart Router) que diferencia grupo vs individual. Isso e um moat.

2. **Sports/Community vertical** — ResenhAI como case de referencia. "O mesmo sistema que engaja 10K atletas de futevolei pode engajar sua comunidade de crossfit, beach tennis, ou corrida."

3. **Proactive + Reactive unificado** — M13 (Trigger Engine) + M8 (Agents) no mesmo pipeline. Maioria dos players separa "chatbot" de "campaigns/broadcasts".

4. **Brasil-first pricing** — Em BRL, com PIX, com suporte PT-BR nativo. Zenvia e Blip sao enterprise. Octadesk e support-only. Espaco aberto no mid-market.

5. **Self-hosted option** — Evolution API + Docker Compose. Para clientes que nao podem ter dados em cloud (saude, financeiro, governo).

### 6.4 Riscos e Mitigacoes

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Meta muda pricing radicalmente | Media | Alto | Adapter pattern (ja planejado), monitorar announcements |
| Evolution API descontinuada | Baixa | Alto | Cloud API mode como fallback, adapter layer |
| Competidor grande lanca grupo agent | Media | Medio | First-mover advantage + vertical depth (sports) |
| LLM costs explodem com escala | Media | Alto | Bifrost + model routing (Haiku para simples, Sonnet para complexo) |
| WhatsApp bane numero por spam | Media | Alto | Rate limiting, template compliance, quality score monitoring |
| Tenant gera conteudo toxico via agent | Media | Alto | M6/M10 guardrails (pre/post), Haiku eval, content policy per tenant |

### 6.5 Roadmap Sugerido (Informado pela Pesquisa)

```
Fase 0 (Atual)     → Skeleton echo, infra base, CI/CD
Fase 1 (Abr 2026)  → ResenhAI support 1:1 (M1→M11 completo)
Fase 2 (Mai 2026)  → ResenhAI groups (M3 router + group agent)
Fase 3 (Jun 2026)  → Proactive messages (M13 Trigger Engine)
Fase 4 (Jul 2026)  → Admin dashboard + handoff inbox (Next.js)
Fase 5 (Ago 2026)  → Agent Definition as Data + Tool Registry
                      (aqui Fulano vira plataforma, nao so produto)
Fase 6 (Set 2026)  → Segundo tenant (onboarding ou scheduling use case)
Fase 7 (Out 2026)  → WhatsApp Flows integration + CSAT surveys
Fase 8 (Nov 2026)  → Usage metering + billing integration
Fase 9 (Dez 2026)  → White-label admin + self-service onboarding
Fase 10 (Q1 2027)  → Sales agent template + E-commerce template
```

---

## 7. Fontes e Referencias

| Fonte | Tipo | Dados Extraidos |
|-------|------|-----------------|
| Anthropic "Building Effective Agents" | Best practices | Agent patterns (routing, chaining, orchestrator-workers), tool engineering, production guidance |
| Botpress pricing page | Pricing | Tiers, usage limits, vector DB storage, AI spend model |
| Voiceflow pricing page | Pricing | Credits system, agency features, white-label |
| Chatbase pricing + features | Pricing + Features | Tiers, white-label, knowledge base limits, integrations |
| Relevance AI pricing + features | Pricing + Features | Multi-agent workforces, actions-based billing, BYOLLM |
| Salesforce Agentforce | Features | Atlas engine, Agent Builder, flex credits |
| Respond.io blog | WhatsApp API | July 2025 per-template pricing change, conversation categories, free service messages |
| Gallabox blog | WhatsApp pricing | Template categories, free incoming messages, subscription model |
| WhatsApp Business Platform | Official | 4 conversation categories, WhatsApp Flows, pricing calculator |
| Bland.ai | Architecture | Dedicated instance model, proprietary stack, SIP integration |
| Evolution API (GitHub) | Open-source | Baileys + Cloud API, multi-instance, Typebot/Chatwoot integration |
| Zenvia | Brazil CPaaS | 10K+ customers, AI agents, CDP, case studies (Casas Bahia, Mercado Livre) |
| Octadesk | Brazil support | WOZ 2.0 AI, 2500 customers, 9.3 Reclame Aqui |
| Blip/Take | Brazil CPaaS | Largest BR player, multi-channel, enterprise |
| Zoko | WhatsApp commerce | Shopify-native, catalogs, broadcasts |
| Typebot | Open-source chatbot | WhatsApp native, multi-number, session management, 650+ companies |
| Chatwoot (GitHub) | Open-source inbox | Captain AI agent, omnichannel, multi-tenant indicators |
| LangGraph (GitHub) | Agent framework | Durable execution, memory (short+long term), multi-agent patterns |
| Infobip docs | WhatsApp features | Flows, Payments (India), Catalogs, AI chatbots |
| Twilio docs | WhatsApp API | ISV Tech Provider Program, Verify API, multi-WABA |
| Microsoft Azure Architecture | Multi-tenant patterns | Silo/pool/bridge models, tenant isolation, checklist |
| GPT Runner (GitHub) | Config patterns | .gpt.md agent definitions, file-based config, preset sharing |
