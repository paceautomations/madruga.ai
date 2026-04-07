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

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
