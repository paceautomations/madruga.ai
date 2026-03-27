---
title: "Solution Overview"
updated: 2026-03-27
---
# Fulano — Solution Overview

> O que vamos construir, para quem, e em que ordem. Ultima atualizacao: 2026-03-27.

---

## Visao de Solucao

O dono de uma PME conecta seu numero WhatsApp, importa seu catalogo ou FAQ, escolhe o tom de voz do agente e esta no ar em menos de 15 minutos. A partir desse momento, o agente responde mensagens de clientes 24/7 — tira duvidas, faz agendamentos, acompanha pedidos. Quando nao sabe responder, transfere para um atendente humano com todo o contexto da conversa. Em grupos WhatsApp, o agente participa quando mencionado — publica ranking, responde perguntas, organiza eventos.

O dono acompanha tudo por um painel: conversas, metricas de resolucao, configuracoes do agente. Nao precisa de time de TI. Nao precisa de codigo. Paga pelo que usa.

---

## Personas x Jornadas

| Persona | O que faz | O que ganha | Jornada principal |
|---------|-----------|-------------|-------------------|
| **Dono da PME** | Configura agente, define regras, acompanha metricas, ajusta tom de voz | Atendimento 24/7 sem contratar, mais vendas, menos mensagens perdidas | Cadastro → config agente → conecta WhatsApp → monitora painel |
| **Cliente final** | Envia mensagem no WhatsApp, recebe resposta do agente ou do humano | Resposta rapida, fora do horario, sem esperar em fila | Envia duvida → recebe resposta IA → resolve ou fala com humano |
| **Operador / Atendente** | Recebe conversas escaladas, responde no painel, encerra atendimento | Contexto completo da conversa, sem repetir perguntas | Recebe notificacao → ve resumo IA → responde → encerra |

---

## Feature Map

→ Para status de execucao, ver [Roadmap](/fulano/roadmap/).

| Prioridade | Feature | Descricao | Valor | Epicos |
|------------|---------|-----------|-------|--------|
| **Now** | Receber e responder mensagens | Agente recebe mensagens WhatsApp e responde automaticamente | Base do produto — sem isso nada funciona | [001](../epics/001-channel-pipeline/pitch), [002](../epics/002-conversation-core/pitch) |
| **Now** | Conversa inteligente com IA | Agente entende contexto, historico e responde com precisao em portugues | Core da proposta de valor — atendimento que funciona | [002](../epics/002-conversation-core/pitch) |
| **Now** | Agente em grupos WhatsApp | Responde quando mencionado (@), observa sem responder quando nao mencionado | Moat competitivo — ninguem faz isso | [001](../epics/001-channel-pipeline/pitch), [003](../epics/003-group-routing/pitch) |
| **Now** | Consultas em tempo real | Agente consulta dados do negocio (ranking, stats, agenda, estoque) | Respostas uteis, nao genericas | [004](../epics/004-agent-tools/pitch) |
| **Now** | Transferencia para humano | Quando a IA nao resolve, transfere para atendente com resumo e contexto | Rede de seguranca — cliente nunca fica sem resposta | [005](../epics/005-handoff-engine/pitch) |
| **Now** | Mensagens automaticas | Notificacoes por eventos: lembrete de agendamento, pedido enviado, boas-vindas | Engajamento proativo, nao so reativo | [006](../epics/006-trigger-engine/pitch) |
| **Next** | Painel de controle | Dashboard com conversas, metricas de resolucao, configuracao de agentes | Dono da PME gerencia tudo sozinho | [007](../epics/007-admin-dashboard/pitch) |
| **Next** | Fila de atendimento humano | Operador ve e gerencia conversas escaladas em tempo real | Atendimento humano organizado, sem perder conversa | [008](../epics/008-admin-handoff-inbox/pitch) |
| **Next** | Medicao de qualidade | Score automatico por conversa, deteccao de respostas ruins antes e depois de publicar | Melhoria continua — saber o que funciona e o que nao | [009](../epics/009-evals-offline/pitch), [010](../epics/010-evals-online/pitch) |
| **Next** | Melhoria continua com revisao humana | Ciclo semanal: identificar respostas fracas, revisar, aprovar e publicar melhoria | Agente fica melhor toda semana sem esforco do dono | [011](../epics/011-data-flywheel/pitch) |
| **Later** | Cadastro self-service | Novo cliente se cadastra, configura agente e conecta WhatsApp sozinho | Escala sem equipe de onboarding | [012](../epics/012-multi-tenant-self-service/pitch) |
| **Later** | Base de conhecimento | Agente busca em documentos, FAQs e manuais do negocio para responder | Respostas especializadas por cliente | [013](../epics/013-rag-pgvector/pitch) |
| **Later** | Cobranca automatica | Billing integrado com tiers de preco, consumo medido | Monetizacao automatica | [014](../epics/014-billing-stripe/pitch) |
| **Later** | Formularios no WhatsApp | Cadastro, pesquisa de satisfacao e coleta de dados dentro do WhatsApp | Interacao estruturada sem sair do chat | [015](../epics/015-whatsapp-flows/pitch) |

---

## Principios de Produto

1. **Setup em menos de 15 minutos** — Conectar numero, importar catalogo, escolher tom de voz, ativar. Sem onboarding de semanas.
2. **IA e copiloto, nao piloto** — O agente responde e resolve, mas o humano sempre pode assumir. Transferencia e cidadao de primeira classe.
3. **Dados do cliente sao do cliente** — Export completo a qualquer momento. Zero lock-in. Privacidade desde o primeiro contato.
4. **Sem surpresas de custo** — Pricing transparente por tier. O dono sabe quanto vai pagar antes de comecar.
5. **Melhor toda semana** — O agente aprende com cada conversa. Ciclo de melhoria continua com gate humano, nunca automatico.
