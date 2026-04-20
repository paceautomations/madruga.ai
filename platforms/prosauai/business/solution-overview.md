---
title: "Solution Overview"
updated: 2026-04-20
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
| **Transcricao de audio** | 🔄 epic 009 · previsao 2026-04-29 | end-user + tenant | Cliente envia audio (PTT ou arquivo) e recebe resposta coerente com o conteudo falado — nao precisa digitar, e o agente nao trava com "so entendo texto". | pt-BR prioritario; ingles suportado; ate 10 min por audio |
| **Descricao de imagem** | 🔄 epic 009 · previsao 2026-04-29 | end-user + tenant | Cliente envia foto (print de erro, comprovante, produto, documento escaneado) e o agente descreve em linguagem natural e responde com base nela. Reduz handoff em 30-50% dos casos. | JPG/PNG/WEBP ate 20 MB; caption do cliente e usada como contexto adicional |
| **Extracao de texto de documentos** | 🔄 epic 009 · previsao 2026-04-29 | end-user + tenant | Cliente envia PDF ou DOCX e o agente responde perguntas sobre o conteudo — "qual o valor", "qual a data de vencimento", termos de contrato. | PDF texto nativo + DOCX; ate 25 MB, 10 paginas. PDF escaneado fica para o proximo ciclo |
| **Stickers, localizacao, contatos e reacoes** | 🔄 epic 009 | end-user | Sticker vira texto descritivo, localizacao vira endereco em linguagem natural, contato compartilhado vira descricao, reacao (❤️/👍) conta como feedback explicito. Nenhum tipo de conteudo faz o agente travar. | — |
| **Suporte a Meta Cloud API (WhatsApp oficial)** | 📋 epic 009 PR-C · previsao 2026-05-10 | tenant | Tenant pode conectar o ProsaUAI via Meta Cloud (oficial) alem do gateway atual. Destrava funcionalidades oficiais (botoes, listas, templates aprovados) e elimina dependencia do gateway para quem prefere pagar a Meta direto. | Retrocompativel — tenants atuais continuam funcionando sem alteracao |
| **Fallback tonalizado por persona** | 🔄 epic 009 | end-user | Quando qualquer feature de midia falha (orcamento estourado, provider fora, arquivo corrompido, formato nao suportado), o cliente recebe mensagem humanizada pela persona do tenant ("Opa, hoje estou sem energia para audios longos, pode me resumir por texto?") — nunca um erro tecnico cru. | — |

### Controle operacional (Admin)

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Painel Admin (login + navegacao)** | ✅ epic 007 | admin | Area administrativa com login por cookie e sidebar de navegacao entre as abas operacionais. |
| **Overview por tenant** | 🔄 epic 008 | admin | Conversas ativas hoje, volume de mensagens, taxa de handoff, custo acumulado e distribuicao por intent. |
| **Trace Explorer** | 🔄 epic 008 | admin | Waterfall completo de cada resposta do pipeline com input/output de cada etapa. Inclui transcripts de audio e descricoes de imagem na integra. |
| **Performance AI** | 🔄 epic 008 | admin + Pace (ops) | Custo por modelo ao longo do tempo + custo por midia/dia (epic 009), latencia p50/p95/p99 por etapa e quality score medio por agente. |
| **Conversas e Inbox** | 🔄 epic 008 | admin | Listagem cross-tenant com busca (nome do cliente + conteudo) e filtros por status e tenant. Listagem em <100 ms em volumes de 10k+ conversas. |
| **Handoff para atendente humano** | 📋 epic 014 | tenant + end-user | Quando a IA decide (score baixo, topico critico, cliente pede) ou quando um atendente pega a conversa, o handoff e transparente — SLA configuravel, timeout retorna para bot. |

### Compliance e privacidade

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Retencao LGPD-first** | ✅ epic 006 + 009 | tenant + end-user | Conversas 90 dias default (configuravel 30-365 d). Midia bruta nunca persistida — bytes ficam em memoria e sao descartados apos processamento. Transcript e metadata retidos 90 d. Purga diaria automatica. |
| **Consent no primeiro contato** | ✅ epic 003 | end-user | Cliente novo recebe a politica de privacidade e escolhe prosseguir. Sem aceite → apenas fallback generico, zero processamento de dado pessoal. |
| **SAR (Subject Access Request)** | ✅ epic 006 | tenant | Exportacao completa dos dados de um end-user em 15 dias uteis. Inclui transcripts de audio e descricoes de imagem dentro da janela de 90 d. |

---

## Proximos ciclos e visao de longo prazo

| Feature | Horizonte | Valor |
|---------|-----------|-------|
| **PDF escaneado (OCR automatico)** | Proximo — epic 011 | Hoje o agente retorna aviso claro de que nao conseguiu ler. OCR remoto destrava PDFs de boletos, contratos e documentos fotografados. |
| **Instagram DM + Telegram** | Proximo — epic 010 | Mesmo agente passa a responder em outros canais reusando o adaptador do epic 009 — validacao de que integrar novo canal nao muda o core da plataforma. |
| **Agent tools (APIs externas)** | Proximo — epic 013 | Agente consulta dados reais do tenant (estoque, ranking, agenda), chama APIs e cria registros em nome do cliente. |
| **Triggers proativos** | Proximo — epic 015 | Plataforma inicia conversa com o cliente (lembrete de agendamento, follow-up de pedido, boas-vindas) em vez de so reagir. |
| **Streaming transcription** | Proximo — epic 012 | Audios transcritos em tempo real durante a fala. Ganho marginal em pt-BR curto — avaliar demanda antes de priorizar. |
| **Medicao e melhoria continua de qualidade** | Longo prazo | Score automatico por conversa, deteccao de respostas fracas, ciclo semanal de revisao e aprovacao de melhoria com gate humano. |
| **Cadastro self-service** | Longo prazo | Novo cliente se cadastra, configura agente e conecta WhatsApp sozinho — escala sem equipe de onboarding. |
| **Base de conhecimento por tenant** | Longo prazo | Agente busca em documentos, FAQs e manuais do tenant para respostas especializadas. |
| **Cobranca automatica** | Longo prazo | Billing integrado com tiers de preco e consumo medido. |
| **Formularios no WhatsApp** | Longo prazo | Cadastro, pesquisa de satisfacao e coleta de dados dentro do chat, sem sair do WhatsApp. |

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
