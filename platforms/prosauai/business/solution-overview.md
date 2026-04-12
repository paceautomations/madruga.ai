---
title: "Solution Overview"
updated: 2026-04-12
sidebar:
  order: 2
---
# ProsaUAI — Solution Overview

## Visao de Solucao

O dono de uma PME conecta seu numero WhatsApp, importa seu catalogo ou FAQ, escolhe o tom de voz do agente e esta no ar em menos de 15 minutos. A partir desse momento, o agente responde mensagens de clientes 24/7 — tira duvidas, faz agendamentos, acompanha pedidos. Quando nao sabe responder, transfere para um atendente humano com todo o contexto da conversa.

Em grupos WhatsApp, o agente participa quando mencionado — publica ranking, responde perguntas, organiza eventos. O dono acompanha tudo por um painel: conversas, metricas de resolucao, configuracoes do agente. Nao precisa de time de TI. Nao precisa de codigo. Paga pelo que usa.

> Personas e jornadas detalhadas → ver [Vision](./vision/).

---

## Implementado — Funcional hoje

### Epic 001 — Channel Pipeline

| Feature | Descricao | Epic |
|---------|-----------|------|
| **Recepcao de mensagens** | Webhook FastAPI recebe mensagens WhatsApp via Evolution API | 001 |
| **Debounce** | Agrupa mensagens rapidas (janela 3s + jitter) via Redis Lua script atomico | 001 |
| **Echo response** | Responde com echo do texto recebido (sem IA — fundacao para epic 005) | 001 |
| **Health check** | Endpoint `/health` com status do Redis e degradacao graciosa | 001 |

### Epic 002 — Observability

| Feature | Descricao | Epic |
|---------|-----------|------|
| **Tracing distribuido** | OpenTelemetry SDK com spans manuais por etapa do pipeline (webhook, classify, decide) | 002 |
| **Phoenix (Arize)** | UI de observabilidade self-hosted (:6006) + ingestao OTLP gRPC (:4317). Substitui LangFuse | 002 |
| **structlog bridge** | Correlacao log↔trace: `trace_id`/`span_id` injetados em todo log estruturado | 002 |
| **Exporter health** | `ExporterHealthTracker` monitora status de exportacao OTel (thread-safe). Health endpoint reflete estado | 002 |

### Epic 003 — Multi-Tenant Foundation

| Feature | Descricao | Epic |
|---------|-----------|------|
| **Multi-tenant auth** | `X-Webhook-Secret` per-tenant com constant-time compare. Substitui HMAC imaginario que rejeitava 100% dos webhooks reais | 003 |
| **TenantStore** | `Tenant` frozen dataclass (10 campos) + `TenantStore` file-backed YAML com interpolacao `${ENV_VAR}`. 2 tenants reais: Ariel + ResenhAI | 003 |
| **Parser Evolution v2.3.0** | 13 tipos de mensagem suportados: text, image, video, audio (PTT), document, sticker, contact, location, live_location, poll, reaction, event, group_metadata. 12 correcoes contra 26 fixtures capturadas reais | 003 |
| **Idempotency** | Redis SETNX per `(tenant_id, message_id)` com TTL 24h. Neutraliza retries agressivos da Evolution API | 003 |
| **Deploy isolado** | Tailscale (dev) + Docker network privada `pace-net` (prod). Zero porta publica exposta | 003 |

### Epic 004 — Router MECE

| Feature | Descricao | Epic |
|---------|-----------|------|
| **classify() puro** | Funcao pura (sem I/O) que deriva `MessageFacts` a partir da mensagem + estado pre-carregado. Enums: `Channel` (individual/group), `EventKind` (message/group_membership/group_metadata/protocol/unknown), `ContentKind` (text/media/structured/reaction/empty) | 004 |
| **RoutingEngine declarativo** | Avalia regras por prioridade (menor = maior), first-match wins. 5 tipos de acao: RESPOND, LOG_ONLY, DROP, BYPASS_AI, EVENT_HOOK | 004 |
| **Config YAML per-tenant** | Regras de roteamento em `config/routing/{tenant}.yaml`. Cada tenant tem suas proprias regras com prioridades e condicoes | 004 |
| **MentionMatchers** | Deteccao de mencao com 3 estrategias: opaque @lid, phone number, keywords configurados por tenant | 004 |
| **Agent resolution** | Resolucao de agente: rule.agent > tenant.default_agent_id > AgentResolutionError. Validacao fail-fast no startup | 004 |
| **MECE 4 camadas** | Garantias de exaustividade: (1) tipo (enums), (2) schema (pydantic validates overlaps), (3) runtime (discriminated union), (4) CI (property-based testing) | 004 |
| **CLI verification** | `prosauai router verify` e `prosauai router explain` para validar regras de roteamento | 004 |

---

## Next — Candidatos para proximos ciclos

| Feature | Descricao | Por que e importante |
|---------|-----------|---------------------|
| **Conversa inteligente com IA** | Agente entende contexto, historico e responde com precisao em portugues | Core da proposta de valor — atendimento que realmente resolve |
| **Consultas em tempo real** | Agente consulta dados do negocio (ranking, stats, agenda, estoque) para dar respostas uteis | Respostas relevantes, nao genericas |
| **Transferencia para humano** | Quando a IA nao resolve, transfere para atendente com resumo e contexto completo | Rede de seguranca — cliente nunca fica sem resposta |
| **Mensagens automaticas** | Notificacoes por eventos: lembrete de agendamento, pedido enviado, boas-vindas | Engajamento proativo, nao so reativo |
| **Painel de controle** | Dashboard com conversas, metricas de resolucao, configuracao de agentes | Dono da PME gerencia tudo sozinho |
| **Fila de atendimento humano** | Operador ve e gerencia conversas escaladas em tempo real | Atendimento humano organizado, sem perder conversa |

---

## Later — Visao de longo prazo

| Feature | Descricao | Por que e importante |
|---------|-----------|---------------------|
| **Medicao de qualidade** | Score automatico por conversa, deteccao de respostas ruins | Melhoria continua — saber o que funciona e o que nao |
| **Melhoria continua** | Ciclo semanal: identificar respostas fracas, revisar, aprovar e publicar melhoria | Agente fica melhor toda semana sem esforco do dono |
| **Cadastro self-service** | Novo cliente se cadastra, configura agente e conecta WhatsApp sozinho | Escala sem equipe de onboarding |
| **Base de conhecimento** | Agente busca em documentos, FAQs e manuais do negocio para responder | Respostas especializadas por cliente |
| **Cobranca automatica** | Billing integrado com tiers de preco e consumo medido | Monetizacao automatica |
| **Formularios no WhatsApp** | Cadastro, pesquisa de satisfacao e coleta de dados dentro do chat | Interacao estruturada sem sair do WhatsApp |

---

## Principios de Produto

1. **Setup em menos de 15 minutos** — Conectar numero, importar catalogo, escolher tom de voz, ativar. Sem onboarding de semanas.
2. **IA e copiloto, nao piloto** — O agente responde e resolve, mas o humano sempre pode assumir. Transferencia e cidadao de primeira classe.
3. **Dados do cliente sao do cliente** — Export completo a qualquer momento. Zero lock-in. Privacidade desde o primeiro contato.
4. **Sem surpresas de custo** — Pricing transparente por tier. O dono sabe quanto vai pagar antes de comecar.
5. **Melhor toda semana** — O agente aprende com cada conversa. Ciclo de melhoria continua com gate humano, nunca automatico.

---

## O que NAO fazemos

| NAO e... | Porque |
|----------|--------|
| **CRM** | Nao gerencia pipeline de vendas. Integra com CRMs existentes. |
| **Call center** | Nao faz voz nem telefonia. Foco em mensageria. |
| **Marketplace** | Nao intermedia transacoes nem cobra comissao. |
| **Plataforma de anuncios** | Nao faz marketing automation nem campanhas em massa. Foco em atendimento. |

---

> **Proximo passo:** `/madruga:business-process prosauai` — mapear fluxos core a partir do feature map priorizado.
