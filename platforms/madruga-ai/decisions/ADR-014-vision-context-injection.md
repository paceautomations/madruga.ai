---
title: 'ADR-014: Vision Context Injection por Fase'
status: Accepted
decision: 'We will inject Vision context proportionally per phase: specify gets vision_brief
  + context_map, plan gets context_map + domain_model + relevant ADRs, implement gets
  ADRs + containers (NFRs), and reconcile gets full context for node-by-node diff.'
alternatives: Contexto completo em toda fase, Zero contexto (cada fase isolada)
rationale: Cada fase recebe exatamente o contexto que precisa (proporcional)
---
# ADR-014: Vision Context Injection por Fase
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O pipeline spec-to-code gera artefatos progressivamente (spec -> plan -> tasks -> implement). Cada fase precisa de contexto da arquitetura (Vision) para produzir output alinhado, mas o contexto total (vision brief + context map + domain model + 19 ADRs + containers + integrations) excede limites praticos de prompt. Precisamos de uma estrategia para injetar contexto proporcional a necessidade de cada fase.

## Decisao

We will inject Vision context proportionally per phase: specify gets vision_brief + context_map, plan gets context_map + domain_model + relevant ADRs, implement gets ADRs + containers (NFRs), and reconcile gets full context for node-by-node diff.

## Alternativas consideradas

### Contexto completo em toda fase
- Pros: maximo contexto disponivel.
- Cons: excede token budget em fases simples, dilui atencao do LLM, custo desnecessario de tokens.

### Zero contexto (cada fase isolada)
- Pros: minimo de tokens, fases independentes.
- Cons: specs sem contexto de arquitetura, plans sem ADRs, implementacao sem NFRs — incoerencia garantida.

## Consequencias

- [+] Cada fase recebe exatamente o contexto que precisa (proporcional)
- [+] Token budget controlado (max 50K por prompt)
- [+] ADRs filtrados lazy: so carrega os referenciados no frontmatter `arch.modules` do epic
- [+] Diff truncado a 30K tokens no reconcile (evita prompt overflow)
- [-] Configuracao de injecao precisa ser mantida conforme fases evoluem
- [-] ADR filter pode perder ADRs relevantes se frontmatter estiver incompleto
