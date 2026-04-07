---
title: 'ADR-012: Modelo de billing para tenants'
status: Proposed
decision: Modelo de billing
alternatives: ''
rationale: ''
---
# ADR-012: Modelo de billing para tenants
**Status:** Proposed (decisao pendente) | **Data:** 2026-03-25

## Contexto
Precisamos definir como cobrar tenants pelo uso da plataforma. O modelo de billing impacta diretamente unit economics, barreira de entrada para novos clientes e previsibilidade de receita. Esta decisao sera tomada antes de implementar o modulo de billing.

O mercado de agentes IA usa 4 modelos principais. Abaixo o mapeamento de cada um com pros, contras e quem usa.

## Alternativas em avaliacao

### Opcao A: Consumo por mensagem com tiers fixos
Modelo: planos com limite de mensagens/mes + throttling gracioso (sem surprise bills).

Referencia de tiers inicial (a ser validada):

| Tier | Preco (BRL) | Msgs/mes | Target |
|------|-------------|----------|--------|
| Free | R$0 | 100 | POC / validacao |
| Starter | R$197 | 2.000 | 1-5 filiais pequenas |
| Growth | R$497 | 10.000 | 5-20 filiais medias |
| Business | R$997 | 50.000 | Enterprise multi-unidade |
| Enterprise | Custom | Custom | SLA dedicado |

- Pros: Simples de comunicar ("ate X mensagens por mes"), previsivel para o cliente, alinhamento uso-custo
- Cons: Mensagens complexas (RAG + 3 tools) custam mais que simples mas cobram o mesmo — margem varia. Free tier gera custo sem receita
- Quem usa: Chatbase ($40-$500/mo com message credits)

### Opcao B: Per-seat (por usuario)
- Pros: Previsivel para o cliente, modelo familiar (SaaS classico), facil de entender
- Cons: Penaliza crescimento — cliente hesita em adicionar usuarios, nao reflete uso real do servico (1 usuario pode mandar 50K msgs), incentivo errado
- Quem usa: Salesforce (per-user licensing como uma das opcoes)

### Opcao C: Credits com multiplicador
- Pros: Flexivel, permite cobrar mais por acoes complexas (1 msg simples = 1 credito, 1 msg com RAG = 5 creditos)
- Cons: Confuso para o cliente ("1 mensagem = quantos creditos?"), imprevisivel, dificil de comunicar pricing
- Quem usa: Voiceflow (1x-20x multiplicador por complexidade)

### Opcao D: Actions-based
- Pros: Granular, cobra por valor entregue (cada tool call = 1 action)
- Cons: Totalmente imprevisivel — depende de quantas tools o agente chama internamente, cliente nao consegue estimar custo mensal
- Quem usa: Relevance AI (200 free → 84K actions/mo no team)

### Opcao E: AI spend at-cost + subscription
- Pros: Transparente, sem markup no LLM, cliente ve custo real
- Cons: Margem zero na camada de LLM, precisa monetizar infra/features separadamente, receita instavel
- Quem usa: Botpress (base subscription + AI spend metered at provider cost)

## Principios ja definidos (independente do modelo escolhido)
- LLM cost tracking via Bifrost (ADR-002) por tenant por dia — necessario para qualquer modelo
- Billing ledger em Supabase com agregacao per-tenant per-day
- Throttling gracioso (typing indicator, queuing) — nunca corte abrupto
- Stripe integration no roadmap v2

## Decisoes pendentes
1. Qual modelo adotar (A-E ou hibrido)?
2. Tiers e pricing exatos
3. Overage: hard limit vs soft limit vs cobranca extra?
4. Free tier: sim/nao? Qual limite?
5. Unit economics: custo medio por mensagem (GPT mini ~$0.0004) vs preco cobrado

## Proximo passo
Validar unit economics com dados reais de custo LLM por conversa (pos-Phase 0) antes de decidir modelo e pricing.
