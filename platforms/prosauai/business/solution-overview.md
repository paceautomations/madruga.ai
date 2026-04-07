---
title: "Solution Overview"
updated: 2026-04-07
sidebar:
  order: 2
---
# ProsaUAI — Solution Overview

## Visao de Solucao

O dono de uma PME conecta seu numero WhatsApp, importa seu catalogo ou FAQ, escolhe o tom de voz do agente e esta no ar em menos de 15 minutos. A partir desse momento, o agente responde mensagens de clientes 24/7 — tira duvidas, faz agendamentos, acompanha pedidos. Quando nao sabe responder, transfere para um atendente humano com todo o contexto da conversa.

Em grupos WhatsApp, o agente participa quando mencionado — publica ranking, responde perguntas, organiza eventos. O dono acompanha tudo por um painel: conversas, metricas de resolucao, configuracoes do agente. Nao precisa de time de TI. Nao precisa de codigo. Paga pelo que usa.

> Personas e jornadas detalhadas → ver [Vision](/prosauai/vision/).

---

## Implementado — Funcional hoje

> Nenhuma feature implementada — plataforma em fase de design. As features abaixo estao priorizadas para os proximos ciclos.

---

## Next — Candidatos para proximos ciclos

| Feature | Descricao | Por que e importante |
|---------|-----------|---------------------|
| **Receber e responder mensagens** | Agente recebe mensagens WhatsApp e responde automaticamente, 24/7 | Base do produto — sem isso nada funciona |
| **Conversa inteligente com IA** | Agente entende contexto, historico e responde com precisao em portugues | Core da proposta de valor — atendimento que realmente resolve |
| **Agente em grupos WhatsApp** | Responde quando mencionado (@), observa sem responder quando nao mencionado | Moat competitivo — ninguem faz isso |
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
