---
title: 'ADR-008: DeepEval + Promptfoo como stack de avaliacao'
status: Accepted
decision: DeepEval + Promptfoo
alternatives: Apenas DeepEval, Apenas Promptfoo, Custom eval scripts
rationale: Metricas profundas garantem qualidade de respostas em producao
---
# ADR-008: DeepEval + Promptfoo como stack de avaliacao
**Status:** Accepted | **Data:** 2026-03-23

## Contexto
Precisamos avaliar qualidade de respostas dos agentes de forma sistematica — tanto metricas profundas (faithfulness, relevance, hallucination) quanto gates automatizados em CI para prevenir regressoes de prompt.

## Decisao
We will usar DeepEval e Promptfoo de forma complementar: DeepEval para metricas profundas e Promptfoo para CI gates.

Motivos:
- DeepEval: metricas LLM-as-judge robustas (faithfulness, answer relevancy, hallucination score)
- Promptfoo: CI gates rapidos, comparacao side-by-side de prompts, YAML-driven
- Complementares — DeepEval para profundidade, Promptfoo para velocidade e automacao
- Ambos open-source com community ativa

## Alternativas consideradas

### Apenas DeepEval
- Pros: Metricas mais profundas, API Python nativa, relatorios detalhados
- Cons: Mais lento para rodar em CI (LLM-as-judge), nao tem comparacao side-by-side nativa de prompts

### Apenas Promptfoo
- Pros: Rapido, YAML config, bom para CI/CD, comparacao de prompts excelente
- Cons: Metricas mais superficiais, menos granularidade em avaliacao de qualidade

### Custom eval scripts
- Pros: Controle total, sem dependencia
- Cons: Reinventar metricas ja validadas pela comunidade, custo de manutencao alto

## Consequencias
- [+] Metricas profundas garantem qualidade de respostas em producao
- [+] CI gates previnem regressoes de prompt antes do merge
- [+] Comparacao side-by-side acelera iteracao de prompts
- [-] Duas ferramentas para manter e aprender
- [-] DeepEval em CI pode ser lento (mitiga com subset de test cases)
- [-] Custo de LLM-as-judge para rodar evals (tokens adicionais)

---

## 011 Confirmation (2026-04-24)

O epic 011 (Evals) implementa esta stack pela primeira vez em producao.
Duas decisoes de escopo foram feitas durante o plano e ficam registradas
aqui como confirmacoes desta ADR (nao substituicoes):

### DeepEval — set reference-less (v1)

v1 usa **4 metricas reference-less** que nao exigem ground-truth:
`AnswerRelevancyMetric`, `ToxicityMetric`, `BiasMetric` e `GEval` com
rubrica de coerencia. Detalhes e rationale completo em
[ADR-039](ADR-039-eval-metric-bootstrap.md).

**Faithfulness explicitamente adiada** ate epic 012 (RAG) estar em
producao — exige grounding source (passage RAG) que o ProsaUAI ainda
nao tem. `AnswerRelevancyMetric` substitui 70% do sinal ("resposta
relacionada a pergunta") sem exigir grounding. Quando RAG estiver
online, `FaithfulnessMetric` e adicionada como 5a metrica, sem remover
as 4 existentes (schema `eval_scores.metric` ja prevista via
[ADR-039](ADR-039-eval-metric-bootstrap.md) CHECK constraint extensivel).

### Promptfoo — smoke suite + generator incremental

v1 tem **5 casos hand-written** em `apps/api/prosauai/evals/promptfoo/
smoke.yaml` (gate blocking em PRs que tocam `agents/|prompts/|safety/`)
+ **generator Python** que gera YAML a partir de `public.golden_traces`
(admin estrela traces em producao, golden cresce organicamente —
ver [ADR-039](ADR-039-eval-metric-bootstrap.md) para golden bootstrap).

A preocupacao original "DeepEval em CI pode ser lento" se confirma:
DeepEval roda **apenas offline no batch noturno**, nunca no CI. O CI
gate usa **Promptfoo** (rapido, YAML-driven; os 5 smoke cases
validam saidas esperadas sem LLM-as-judge).

### Custo efetivo validado

Estimativa original ("tokens adicionais") ficou concreta: `gpt-4o-mini`
via Bifrost, amostra de 200 msgs/tenant/dia × 4 metricas × 2 tenants ≈
**R$0.48/dia combinado**. Orcamento SC-011 do epic 011 tem folga 6x
(≤R$3/dia combinado). Fallback documentado: reduzir amostra 200→100
ou desligar Toxicity/Bias via `tenants.yaml evals.*`.

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
