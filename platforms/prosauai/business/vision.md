---
title: "Vision"
updated: 2026-03-27
sidebar:
  order: 1
---
# ProsaUAI — Business Vision

## 1. Tese & Aspiracao

ProsaUAI transforma WhatsApp no canal de atendimento inteligente de qualquer PME brasileira. A plataforma e **configuration-driven**: cada novo cliente e uma configuracao — persona, tom de voz, catalogo, regras de negocio — sem escrever codigo. O primeiro cliente e o ResenhAI (app de futevolei), mas a arquitetura nasce multi-tenant desde o dia zero.

O diferencial estrutural e o **agente de grupo**: ProsaUAI e o unico player que faz IA conversacional em grupos WhatsApp — espaco nao-contestado por nenhum concorrente relevante.

**North Star Metric:** conversas resolvidas autonomamente / mes.

| Horizonte | Clientes ativos | MRR | Resolucao autonoma | Churn mensal |
|-----------|----------------|-----|---------------------|-------------|
| **6 meses** | 50 | R$ 25K | 40% | < 10% |
| **18 meses** | 500 | R$ 250K | 70% | < 5% |

---

## 2. Where to Play

### Mercado

- **TAM:** ~6 milhoes de PMEs brasileiras que ja usam WhatsApp comercialmente (SEBRAE + Meta Business)
- **SAM:** E-commerce + servicos com atendimento ativo via WhatsApp Business (~1.2M)
- **SOM:** 500 PMEs em 18 meses, via self-service + inside sales

### Cliente-alvo

| Dimensao | Detalhe |
|----------|---------|
| **Persona** | Dono(a) de PME, 28-55 anos, usa WhatsApp Business como canal principal, sem time de TI |
| **Dor principal** | Atendimento manual nao escala — mensagens perdidas, tempo de resposta alto, cliente insatisfeito |
| **Alternativa atual** | Responde manualmente ou usa chatbot tree-based (rigido, sem IA) |
| **Job-to-be-Done** | "Quero atender meus clientes fora do horario sem contratar mais gente" |

### Segmentos prioritarios

1. **Comunidades esportivas** — ResenhAI como caso de referencia. Agente em grupo que publica ranking, responde stats, organiza jogos. Nenhum player faz isso.
2. **E-commerce** — Pedidos, rastreio, trocas, carrinho abandonado. Maior volume de mercado.
3. **Servicos** — Agendamento, duvidas, pos-venda. Alto potencial de resolucao autonoma.

### Onde NAO jogamos

| ProsaUAI NAO e... | Porque |
|-----------------|--------|
| **CRM** | Nao gerencia pipeline de vendas. Integra com CRMs existentes. |
| **Call center** | Nao faz voz nem telefonia. Foco em mensageria. |
| **Marketplace** | Nao intermedia transacoes nem cobra comissao. |

---

## 3. How to Win

### Moat estrutural: Group AI Agent

Nenhum concorrente relevante — Blip, Botpress, Respond.io, Chatbase — faz IA conversacional em grupos WhatsApp. Todos sao construidos para conversas 1:1. ProsaUAI ocupa esse espaco nao-contestado.

O moat e dificil de copiar: requer engenharia especifica para contexto de grupo (multiplos participantes, @mentions, historico coletivo), alem de profundidade vertical em comunidades (ranking, stats, moderacao, engajamento). Quanto mais comunidades usam, mais dados de interacao em grupo alimentam a qualidade do agente.

### Posicionamento

ProsaUAI nao compete no eixo "chatbot generico". A categoria e **community AI agent** — grupo + proativo + vertical depth. Players enterprise (Blip, Zenvia) sao caros e complexos demais para PME. Builders globais (Botpress, Respond.io) so fazem 1:1. ProsaUAI ocupa a intersecao de grupo AI + comunidade + Brasil mid-market.

### Batalhas criticas

| # | Batalha | Metrica de sucesso | Por que importa |
|---|---------|-------------------|-----------------|
| 1 | **ResenhAI como caso de referencia** | 70% resolucao autonoma | Prova a tese. Sem case, sem credibilidade. |
| 2 | **Self-service onboarding** | PME ativa em < 15 min | Sem isso, nao escala. Cada cliente manual = gargalo. |
| 3 | **Unit economics positivo** | Margem bruta > 70% no Starter+ | Se custo por tenant > receita, crescer = queimar caixa. |
| 4 | **Grupo AI que funciona** | Engajamento em grupo > baseline sem IA | O moat so vale se o produto entrega. |
| 5 | **Retencao** | Churn < 10% (6m), < 5% (18m) | PMEs tem mortalidade alta. Precisa de stickiness. |

---

## 4. Landscape

| Player | Foco | Preco entry | Grupo AI |
|--------|------|-------------|----------|
| **Blip** | Enterprise BR, grandes contas | R$ 5K+/mes | Nao |
| **Botpress** | Agent builder global, SMB | Free tier (PAYG) | Nao |
| **Respond.io** | Messaging platform, mid-market | $79/mo | Nao |
| **Octadesk** | Suporte BR, AI (WOZ 2.0) | Segmentado | Nao |
| **ProsaUAI** | Community AI, PME BR | R$ 0-997/mo | **Sim** |

**Tese competitiva:** O mercado de chatbots 1:1 e lotado e comoditizado. ProsaUAI nao entra nessa briga. A aposta e criar a categoria "community AI agent" — onde ninguem compete — e expandir lateralmente para 1:1 e proativo a partir dessa base. A profundidade vertical (comunidades esportivas → e-commerce → servicos) cria switching costs que "adicionar portugues" nao replica.

---

## 5. Riscos & Premissas

### Riscos

| # | Risco | Prob. | Impacto | Mitigacao |
|---|-------|-------|---------|-----------|
| 1 | Meta muda pricing da API WhatsApp | Media | Alto | Monitorar announcements. Respostas a msgs do usuario sao gratis desde Nov/2024. |
| 2 | Concorrente copia Group AI | Media | Medio | First-mover + vertical depth. Copiar feature e facil; copiar dados de comunidade, nao. |
| 3 | Custo de LLM explode | Media | Alto | Classificador leve como router. Cache de respostas frequentes. |
| 4 | Ban de numero WhatsApp | Media | Alto | Quality score monitoring, opt-in rigoroso, rate limiting, warm-up. |
| 5 | Conteudo toxico gerado pela IA | Media | Alto | Filtros de entrada e saida, avaliador antes de enviar, blocklist por tenant. |
| 6 | Commoditization de IA | Alta | Medio | Se toda IA e boa, diferencial morre. Moat esta na verticalizacao, nao na IA generica. |
| 7 | Dependencia de canal unico (WhatsApp) | Media | Alto | WhatsApp-first, nao WhatsApp-only. Adapter para expansao futura. Nao dispersar foco agora. |

### Premissas criticas

Se qualquer uma for falsa, a tese precisa ser revisada:

1. **PMEs pagam por atendimento automatizado** — willingness to pay validada? R$197/mes e acessivel?
2. **70% de resolucao autonoma e atingivel** — para PMEs genericas, nao so para o caso controlado do ResenhAI.
3. **WhatsApp continua dominante no BR** — nenhum canal alternativo ganha tracao significativa em 18 meses.
4. **Custo de LLM continua caindo** — tendencia historica se mantem, viabilizando margem >70%.
5. **Churn de PME e gerenciavel** — taxa de mortalidade de pequenos negocios nao inviabiliza SOM de 500.

---

## 6. Modelo de Negocio

### Pricing

| Tier | Preco/mes | Msgs/mes | Agents | Numbers |
|------|-----------|----------|--------|---------|
| **Free** | R$ 0 | 100 | 1 | 1 |
| **Starter** | R$ 197 | 2.000 | 3 | 2 |
| **Growth** | R$ 497 | 10.000 | 10 | 5 |
| **Business** | R$ 997 | 50.000 | Ilimitado | 10 |
| **Enterprise** | Custom | Custom | Custom | Custom |

### Tailwind estrutural

Desde novembro de 2024, **respostas a mensagens iniciadas pelo usuario sao gratis** na API do WhatsApp (service conversations). O core do produto — atender mensagens de clientes — tem custo zero de canal. Custo variavel apenas em mensagens proativas (templates).

### Unit economics

- **Custo de LLM:** pass-through sem markup. Estimativa: ~R$0.05/conversa.
- **Margem bruta target:** >70% a partir do tier Starter.
- **Break-even por tenant:** ~R$60/mes (infra + LLM). Starter (R$197) ja e positivo.

---

*Framework: Playing to Win (Lafley & Martin). Ultima atualizacao: 2026-03-27.*
