---
title: "Context Map"
---
# Context Map

> Dominios DDD e suas relacoes. Para diagrama interativo, veja [Context Map (Interactive)](/fulano/context-map/).

## Dominios

<!-- AUTO:domains -->
| # | Dominio | Modulos | Responsabilidade |
|---|---------|---------|------------------|
| 1 | **Channel (Supporting)** | M1, M2, M3, M11 | Ingestao, buffering, roteamento e entrega de mensagens |
| 2 | **Conversation (Core)** | M4, M5, M7, M8, M9 | CORE: gestao de clientes, contexto, classificacao, agentes e avaliacao |
| 3 | **Safety (Supporting)** | M6, M10 | Guardrails de entrada e saida |
| 4 | **Operations (Supporting)** | M12, M13 | Handoff para humano e triggers proativos |
| 5 | **Observability (Generic)** | M14 | Tracing, metricas de qualidade e uso |
<!-- /AUTO:domains -->

## Relacoes entre Dominios

<!-- AUTO:relations -->
| Upstream | Downstream | Tipo | Descricao |
|----------|-----------|------|----------|
| Channel | Conversation (Core) | ACL | Anti-Corruption Layer: Channel traduz InboundMessage para ConversationRequest, isolando o core do formato de canal |
| Conversation (Core) | Bifrost | ACL | Conversation usa Bifrost como proxy para LLMs, traduzindo para formato OpenAI-compatible |
| Conversation (Core) | Supabase ResenhAI | ACL | Agente IA acessa Supabase ResenhAI via tools (read-only) com ACL para isolar schema externo |
| Conversation (Core) | Supabase Fulano | ACL | Conversation acessa Supabase Fulano via repositories com ACL (domain models isolados do schema SQL) |
| Channel | Redis | ACL | Channel usa Redis para debounce (Lua scripts) e streams, com ACL isolando detalhes de implementacao |
| Safety | Conversation (Core) | Customer-Supplier | Conversation (customer) consome Safety (supplier) para validacao de entrada — Safety define contrato de guardrails |
| Conversation (Core) | Safety | Customer-Supplier | Conversation (customer) consome Safety (supplier) para validacao de saida — Safety define contrato de formatacao |
| Conversation (Core) | Operations | Customer-Supplier | Conversation (customer) solicita handoff a Operations (supplier) quando avaliador decide escalar |
| Operations | Channel | Customer-Supplier | Operations (supplier) envia triggers proativos via Channel (customer) para entrega |
| Channel | Observability | Publish-Subscribe |  |
| Conversation (Core) | Observability | Publish-Subscribe |  |
| Conversation (Core) | Observability | Publish-Subscribe |  |
| Conversation (Core) | Observability | Publish-Subscribe |  |
| Operations | Observability | Publish-Subscribe |  |
| Operations | Observability | Publish-Subscribe |  |
| Evolution API | Channel | Conformist | Channel se conforma ao schema de webhooks da Evolution API — sem traducao, aceita o formato externo |
| Observability | LangFuse | Conformist | Observability se conforma ao SDK/API do LangFuse para envio de traces e scores |
| Agente WhatsApp | Channel | Conformist | Agente interage via WhatsApp — Channel aceita o formato do usuario sem traducao |
<!-- /AUTO:relations -->

## Principios

1. **Conversation e o dominio core** — todos os outros dominios existem para servi-lo
2. **ACL obrigatorio** para sistemas externos — nunca expor modelos internos
3. **Observability e passivo** — recebe eventos, nunca altera estado de outros dominios
4. **Safety e sincrono** — guardrails bloqueiam antes de continuar o fluxo
