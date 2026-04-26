---
title: "Solution Overview"
updated: 2026-04-22
sidebar:
  order: 2
---
# ProsaUAI — Solution Overview

## Visao de Solucao

O dono de uma PME conecta seu numero WhatsApp, importa seu catalogo ou FAQ, escolhe o tom de voz do agente e esta no ar em menos de 15 minutos. A partir desse momento, o agente responde mensagens de clientes 24/7 — tira duvidas, faz agendamentos, acompanha pedidos. Quando nao sabe responder, transfere para um atendente humano com todo o contexto da conversa.

Em grupos WhatsApp, o agente participa quando mencionado — publica ranking, responde perguntas, organiza eventos. O dono acompanha tudo por um painel: conversas, metricas de resolucao, configuracoes do agente. Nao precisa de time de TI. Nao precisa de codigo. Paga pelo que usa.

> Personas e jornadas detalhadas → ver [Vision](./vision/).

---

## Mapa de Features

> Catalogo de funcionalidades user-facing. Linguagem de negocio — o "o que" e o "por que", nao o "como". Cada feature carrega **Status** (✅ live · 🔄 em progresso · 📋 planejado), **Para quem** (end-user / tenant / admin) e, quando relevante, **Limites** observaveis pelo usuario.

### Entrega de conversas

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Recepcao WhatsApp** | ✅ epic 001 | end-user | Cliente envia mensagem no WhatsApp e ela e recebida, interpretada e registrada sem intervencao humana. |
| **Debounce de mensagens rapidas** | ✅ epic 001 | end-user | Quando o cliente manda varias mensagens em sequencia, o agente agrupa e responde uma unica vez — conversa natural, sem respostas quebradas. |
| **Multi-tenant isolado** | ✅ epic 003 | tenant | Cada tenant tem suas conversas, agentes, precos e configuracoes isolados. Zero chance de um tenant enxergar dados de outro. |
| **Roteamento por persona (multi-agente)** | ✅ epic 004 | tenant | Cada tenant pode ter multiplos agentes com personas diferentes (atendimento geral, rankings, ajuda com conta). Regras declarativas escolhem qual agente responde — sem codigo. |
| **Resposta com IA contextualizada** | ✅ epic 005 | end-user + tenant | O agente lembra das ultimas mensagens da conversa, aplica a persona do tenant e gera resposta com qualidade auditada (score por resposta). Custo por mensagem rastreado. |

### Conteudo de midia

| Feature | Status | Para | Valor | Limites |
|---------|--------|------|-------|---------|
| **Transcricao de audio** | ✅ epic 009 | end-user + tenant | Cliente envia audio (PTT ou arquivo) e recebe resposta coerente com o conteudo falado — nao precisa digitar, e o agente nao trava com "so entendo texto". | pt-BR prioritario; ingles suportado; ate 10 min por audio |
| **Descricao de imagem** | ✅ epic 009 | end-user + tenant | Cliente envia foto (print de erro, comprovante, produto, documento escaneado) e o agente descreve em linguagem natural e responde com base nela. Reduz handoff em 30-50% dos casos. | JPG/PNG/WEBP ate 20 MB; caption do cliente e usada como contexto adicional |
| **Extracao de texto de documentos** | ✅ epic 009 | end-user + tenant | Cliente envia PDF ou DOCX e o agente responde perguntas sobre o conteudo — "qual o valor", "qual a data de vencimento", termos de contrato. | PDF texto nativo + DOCX; ate 25 MB, 10 paginas. PDF escaneado fica para backlog (OCR). |
| **Stickers, localizacao, contatos e reacoes** | ✅ epic 009 | end-user | Sticker vira texto descritivo, localizacao vira endereco em linguagem natural, contato compartilhado vira descricao, reacao (❤️/👍) conta como feedback explicito. Nenhum tipo de conteudo faz o agente travar. | — |
| **Suporte a Meta Cloud API (WhatsApp oficial)** | ✅ epic 009 (PR-C) | tenant | Tenant pode conectar o ProsaUAI via Meta Cloud (oficial) alem do gateway atual. Destrava funcionalidades oficiais (botoes, listas, templates aprovados) e elimina dependencia do gateway para quem prefere pagar a Meta direto. | Retrocompativel — tenants atuais continuam funcionando sem alteracao |
| **Fallback tonalizado por persona** | ✅ epic 009 | end-user | Quando qualquer feature de midia falha (orcamento estourado, provider fora, arquivo corrompido, formato nao suportado), o cliente recebe mensagem humanizada pela persona do tenant ("Opa, hoje estou sem energia para audios longos, pode me resumir por texto?") — nunca um erro tecnico cru. | — |

### Controle operacional (Admin)

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Painel Admin (login + navegacao)** | ✅ epic 007 | admin | Area administrativa com login por cookie e sidebar de navegacao entre as abas operacionais. |
| **Overview por tenant** | ✅ epic 008 | admin | Conversas ativas hoje, volume de mensagens, taxa de handoff, custo acumulado e distribuicao por intent. |
| **Trace Explorer** | ✅ epic 008 | admin | Waterfall completo de cada resposta do pipeline com input/output de cada etapa. Inclui transcripts de audio e descricoes de imagem na integra. |
| **Performance AI** | ✅ epic 008 + 009 | admin + Pace (ops) | Custo por modelo ao longo do tempo + custo por midia/dia, latencia p50/p95/p99 por etapa e quality score medio por agente. |
| **Conversas e Inbox** | ✅ epic 008 | admin | Listagem cross-tenant com busca (nome do cliente + conteudo) e filtros por status e tenant. Listagem em <100 ms em volumes de 10k+ conversas. |
| **Handoff para atendente humano** | 🔄 epic 010 · proximo | tenant + end-user | Quando a IA decide (score baixo, topico critico, cliente pede) ou quando um atendente pega a conversa, o handoff e transparente — SLA configuravel, timeout retorna para bot. Inbox dedicado para atendente. |

### Compliance e privacidade

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Retencao LGPD-first** | ✅ epic 006 + 009 | tenant + end-user | Conversas 90 dias default (configuravel 30-365 d). Midia bruta nunca persistida — bytes ficam em memoria e sao descartados apos processamento. Transcript e metadata retidos 90 d. Purga diaria automatica. |
| **Consent no primeiro contato** | ✅ epic 003 | end-user | Cliente novo recebe a politica de privacidade e escolhe prosseguir. Sem aceite → apenas fallback generico, zero processamento de dado pessoal. |
| **SAR (Subject Access Request)** | ✅ epic 006 | tenant | Exportacao completa dos dados de um end-user em 15 dias uteis. Inclui transcripts de audio e descricoes de imagem dentro da janela de 90 d. |

---

## Proximos ciclos

> Ordem reconciliada em 2026-04-22 apos shipping de 009. Ver [roadmap.md](../planning/roadmap/) para datas e deps.

| Feature | Horizonte | Valor |
|---------|-----------|-------|
| **Handoff Engine + Inbox** | Proximo — epic 010 | Materializa `pending_handoff` no DB + UI dedicada para atendente humano. SLA configuravel, timeout volta para bot. Fecha o buraco "IA e copiloto, nao piloto". |
| **Evals (offline + online)** | Proximo — epic 011 | Score automatico por conversa (faithfulness, relevance, toxicity) + guardrails pre/pos-LLM em runtime. Unica forma de medir o 70% de resolucao autonoma da vision. |
| **Base de conhecimento por tenant (RAG)** | Proximo — epic 012 | Tenant faz upload de FAQ/catalogo via admin; agente busca em documentos do proprio tenant. Destrava onboarding self-service <15min. |
| **Agent Tools v2 (APIs externas)** | Proximo — epic 013 | Agente consulta dados reais do tenant (estoque, ranking, agenda), chama APIs e cria registros em nome do cliente. Conectores declarativos. |
| **Alerting + WhatsApp Quality** | Proximo — epic 014 | Prometheus/Alertmanager para pipeline quebrado, quality score poller da Meta/Evolution, warm-up per-number, circuit breaker de send. Gate de producao para 1o cliente externo. |
| **Agent Pipeline Steps** | Proximo — epic 015 | Pipeline configuravel por agente (classifier → clarifier → resolver → specialist). Reduz handoff desnecessario com clarificacao antes de chamar LLM caro. |
| **Triggers proativos** | Proximo — epic 016 | Plataforma inicia conversa com o cliente (lembrete de agendamento, follow-up de pedido, boas-vindas) em vez de so reagir. |
| **Tenant Self-Admin** | Proximo — epic 017 | Dono da PME loga na propria area administrativa (subset das abas) e ve so seus dados. Pre-requisito para billing e onboarding autonomo. |

## Gated (liberacao sob trigger comercial)

| Feature | Epic | Trigger |
|---------|------|---------|
| **API publica + onboarding externo** | epic 018 | Primeiro cliente externo disposto a pagar/testar. |
| **Cobranca automatica (Stripe)** | epic 019 | Cliente pagando manualmente ha >=1 mes; operacao quer automatizar. |
| **TenantStore Postgres + Ops Fase 3** | epic 020 | >=5 tenants reais simultaneos OU dor operacional com YAML. |

## Backlog someday-maybe

> Nao descartados — aguardam trigger concreto para promover a epic ativo. Ver [roadmap.md](../planning/roadmap/) para a lista completa de triggers.

| Feature | Trigger para promover |
|---------|-----------------------|
| **PDF escaneado (OCR remoto)** | Demanda recorrente em segmento Servicos/Juridico por leitura de documentos nao-texto-nativo. |
| **Instagram DM + Telegram** | Cliente real demanda canal nao-WhatsApp OU validacao arquitetural multi-source vira prioridade. |
| **Streaming transcription** | p95 Whisper >5s sustentado por 30d OU audios >2min recorrentes em PT-BR. |
| **WhatsApp Flows (formularios estruturados)** | Tier Business exige Flows como diferencial OU demanda real de cliente por captura estruturada. |
| **Data Flywheel** | >=20 tenants gerando volume de conversas que justifique ciclo semanal de revisao humana. |
| **Self-service signup 100% autonomo** | Public API Fase 2 estavel + admin manual virou gargalo (>=5 pedidos/semana). |

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
