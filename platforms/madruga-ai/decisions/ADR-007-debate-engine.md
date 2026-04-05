---
title: 'ADR-007: Multi-Persona Debate Engine'
status: Superseded
superseded_by: ADR-019
decision: We will use a multi-persona debate engine where 3-5 synthetic reviewers
  with distinct perspectives critique specs in structured rounds, producing a consolidated
  list of issues (BLOCKER/WARNING/NIT).
alternatives: Single-pass review (um prompt de review), Human review only
rationale: Multiplas perspectivas encontram classes diferentes de problemas (security,
  performance, UX, maintainability)
---
# ADR-007: Multi-Persona Debate Engine para Qualidade de Specs
**Status:** Superseded by [ADR-019](ADR-019-subagent-judge-pattern.md) | **Data:** 2026-03-27

> **Superseded**: Esta ADR foi supersedida por [ADR-019](ADR-019-subagent-judge-pattern.md). O pattern de debate multi-persona com 3-5 reviewers em rounds estruturados foi substituido por Subagent Paralelo + Judge Pattern usando o Agent tool nativo do Claude Code. Motivo: elimina runtime Python custom, usa capacidade nativa ja provada no pipeline (Tier 3 auto-review, pm-discovery), e adiciona Judge pass para filtrar noise (HubSpot pattern).

## Contexto

Specs geradas por LLM em single-pass tendem a ter blind spots: edge cases ignorados, over-engineering, assuncoes nao validadas. Precisamos de um mecanismo que simule review por multiplas perspectivas (arquiteto, dev senior, PM, security) para encontrar falhas antes da implementacao. O mecanismo deve ser automatizado e executavel tanto interativamente quanto pelo easter.

## Decisao

We will use a multi-persona debate engine where 3-5 synthetic reviewers with distinct perspectives critique specs in structured rounds, producing a consolidated list of issues (BLOCKER/WARNING/NIT).

## Alternativas consideradas

### Single-pass review (um prompt de review)
- Pros: rapido, barato (1 LLM call), simples de implementar
- Cons: uma perspectiva so — perde edge cases que outra persona encontraria, sem tensao criativa entre viewpoints, resultados superficiais

### Human review only
- Pros: qualidade maxima, contexto de negocio real, julgamento nuancado
- Cons: bottleneck humano (horas/dias de latencia), nao escala para N plataformas, nao funciona para easter autonomo, fadiga de review

## Consequencias

- [+] Multiplas perspectivas encontram classes diferentes de problemas (security, performance, UX, maintainability)
- [+] Automatizado — executa em minutos, sem bottleneck humano
- [+] Structured output (BLOCKER/WARNING/NIT) permite automacao downstream
- [+] Reutilizavel — mesma engine para specs, plans, ADRs, code review
- [-] Custo de tokens — 3-5 personas * N rounds = 10-20 LLM calls por spec
- [-] Pode gerar false positives (problemas que nao sao reais) — requer calibracao de personas
- [-] Debate sintetico nao substitui domain expertise real — complementa, nao substitui
