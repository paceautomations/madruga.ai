# Testes A/B & Experimentação — Pesquisa e Roadmap

> Pesquisa realizada em 2026-03-27. Contexto: avaliar LaunchDarkly e alternativas para testes A/B no Fulano.

---

## O que o Fulano já tem hoje

O Fulano já possui peças relevantes para experimentação, mesmo sem uma ferramenta dedicada:

| Capacidade existente | Onde mora |
|---|---|
| **Agent-as-Data** (ADR-006) | Agentes como config no PostgreSQL — versionáveis, com rollback |
| **Bifrost proxy** (ADR-002) | Roteamento de LLM (Claude Sonnet primary, Haiku fallback) |
| **LangFuse** (ADR-007) | Traces, métricas, evaluation workflows |
| **DeepEval + Promptfoo** (ADR-008) | Avaliação de qualidade offline e CI gates |
| **Human-gated flywheel** (ADR-009) | Ciclo semanal de melhoria com validação humana |

Isso significa que o Fulano **já tem a base** para experimentação: versionamento de prompts, observabilidade, e avaliação de qualidade. O que falta é a **camada de assignment (split de tráfego) + análise estatística**.

---

## LaunchDarkly: Faz sentido para o Fulano?

**Resposta curta: Não neste momento.**

| Fator | Avaliação |
|---|---|
| **AI Configs** (prompt A/B testing) | Excelente fit técnico — feito pra testar prompts, modelos, temperature |
| **Server-side SDKs** | Perfeito para backend WhatsApp (sem browser) |
| **Preço** | **Blocker** — Experimentação requer Enterprise (~$30K+/ano). Fulano atende PMEs brasileiras com tier free de R$0 |
| **Complexidade** | Overkill para o estágio atual (Design/MVP) |
| **Data sovereignty** | SaaS americano, relevante para LGPD (ADR-018) |

---

## Alternativas — Comparação completa

### Tier 1: Recomendadas para o Fulano

| | **GrowthBook** | **Statsig** | **PostHog** |
|---|---|---|---|
| **Modelo** | Open-source (MIT) | SaaS freemium | Open-source + Cloud |
| **Custo inicial** | **$0** (self-hosted, ilimitado) | **$0** (2M eventos/mês, unlimited experiments) | **$0** (1M eventos/mês) |
| **Stats engine** | Best-in-class (CUPED, Bayesian, sequential, bandits) | Bom (Bayesian, sequential) | Básico (Bayesian) |
| **Server-side SDK** | Python, Node, Go, Ruby | Python, Node, Go, Java | Python, Node, Go, Ruby |
| **Warehouse-native** | Sim (Postgres, BigQuery, etc.) | Opcional | Não (dados próprios) |
| **LGPD/Data control** | Total (self-hosted) | Médio (SaaS US) | Alto (self-hosted option) |
| **AI/LLM features** | Guia prático de A/B para AI | Genérico | LLM analytics module |
| **Fit com Fulano** | **Excelente** — conecta direto no Postgres existente | **Muito bom** — zero setup, generous free tier | **Bom** — all-in-one mas overlap com LangFuse |

### Tier 2: Viáveis mas com trade-offs

| | **Flagsmith** | **Unleash** | **Split.io** |
|---|---|---|---|
| **Modelo** | Open-source (BSD) | Open-source (Apache 2.0) | SaaS |
| **Custo** | Free (self-hosted, 1 projeto) | Free (self-hosted) | Free → $1,600/mês (experiments) |
| **A/B Testing** | Multivariate flags apenas (sem stats engine) | Básico (sem stats engine) | Bom, mas caro |
| **Veredicto** | Bom para feature flags, fraco para A/B | Feature flags only | Salto de preço proibitivo |

### Tier 3: Evitar

| Ferramenta | Por quê |
|---|---|
| **LaunchDarkly** | $30K+/ano para experimentação. Overkill. |
| **Eppo** | Adquirido pelo Datadog (maio 2025), sem preço público |
| **AWS Evidently** | **Descontinuado** (outubro 2025) |
| **Firebase A/B Testing** | Feito para mobile/web UI, não funciona para backend conversacional |
| **Amplitude Experiment** | $30K+/ano para experimentação |

---

## A/B Testing em plataformas conversacionais WhatsApp

### O que é diferente

O A/B testing para chat é fundamentalmente diferente de web:

| Aspecto | Web tradicional | WhatsApp/Conversacional |
|---|---|---|
| **O que testa** | Botão, layout, cor | Prompt, tom, fluxo, modelo, threshold de escalação |
| **Sessão** | Stateless (page view) | Stateful (conversa multi-turn) |
| **Consistência** | Por page view | **Por usuário E por conversa** (sticky obrigatório) |
| **Métricas** | CTR, bounce rate | Taxa de resolução, CSAT, reengajamento, custo/conversa |
| **Execução** | Client-side (DOM) | **Server-side only** |
| **Volume** | Alto (web traffic) | Menor (por tenant) — precisa de stats engine com sequential testing |

### Padrões de teste relevantes para o Fulano

1. **Prompt variants** — testar tom, instruções, persona do agente
2. **Model variants** — Claude Sonnet vs Haiku vs outro para diferentes tipos de conversa
3. **Flow variants** — perguntar esclarecimento vs tentar responder direto
4. **Threshold de handoff** — quando escalar para humano
5. **Temperature/parâmetros** — encontrar sweet spot de criatividade vs precisão

---

## Recomendação: Abordagem progressiva

### Fase 1 — Agora (MVP, custo zero)

**Use o que já existe.** O Agent-as-Data + LangFuse + Bifrost já permitem:

- Criar 2 versões de um agente no Postgres
- Rotear % do tráfego via lógica simples no worker
- Logar variante no LangFuse trace
- Analisar com SQL no Postgres

Adicione: uma tabela `experiment_assignments` simples (`user_id`, `experiment_id`, `variant`, `assigned_at`) e lógica de sticky assignment por hash do `user_id`.

### Fase 2 — Product-market fit (0–6 meses)

**Adicionar Statsig free tier** ou **GrowthBook self-hosted**:

- **Statsig** se quiser zero ops (2M eventos free, SDK Python)
- **GrowthBook** se quiser controle total + LGPD compliance (warehouse-native no Postgres)

### Fase 3 — Growth (6–12 meses)

**GrowthBook self-hosted** como plataforma de experimentação:

- Conecta direto no Postgres do Fulano (warehouse-native)
- Stats engine avançado (CUPED, sequential testing — importante com volumes menores por tenant)
- Multi-armed bandit para otimização automática de prompts
- Zero custo de licença, escala ilimitada

---

## Padrão de arquitetura para experimentação no Fulano

```
WhatsApp message arrives
  → Identify user + tenant
  → Evaluate feature flags (server-side SDK, local cache)
  → Select prompt variant / flow variant / model variant
  → Generate response with selected variant
  → Log experiment exposure (user_id, tenant_id, variant, conversation_id)
  → Send response via WhatsApp API
  → Collect feedback signals (implicit: conversation continuation; explicit: rating)
  → Analyze in experimentation platform
```

Chave: usar **sticky assignment por `user_id`** (não por mensagem) para garantir consistência dentro e entre conversas.

---

## TL;DR

| Pergunta | Resposta |
|---|---|
| LaunchDarkly faz sentido? | **Não agora** — muito caro ($30K+/ano), overkill para o estágio |
| O Fulano precisa de A/B testing? | **Sim, eventualmente** — essencial para otimizar prompts, fluxos, e modelos |
| O que já temos? | Agent-as-Data + LangFuse + DeepEval cobrem ~60% da necessidade |
| Melhor caminho? | Fase 1: assignment manual + LangFuse → Fase 2: Statsig ou GrowthBook → Fase 3: GrowthBook self-hosted |
| Investimento agora? | **Zero.** Uma tabela + lógica de roteamento no worker resolve a Fase 1 |
