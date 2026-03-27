---
id: 003
title: "Execucao em Waves com Subagents Frescos"
status: proposed
phase: pitch
appetite: small-batch
priority: next
arch:
  modules: [pipelineRunner, claudeClient, orchestratorSlots]
  contexts: [execution, integration]
  containers: [pipelinePhases, runtimeDaemon, orchestrator]
---
# Execucao em Waves com Subagents Frescos

## Problema

Pipelines longos (specify → implement) acumulam contexto no mesmo processo Claude, causando **context rot**: o LLM comeca a "esquecer" instrucoes iniciais, misturar contextos de fases anteriores, e gerar output de qualidade decrescente. Sintomas observados:

1. **Hallucination crescente** — apos 50k+ tokens de contexto, Claude comeca a inventar detalhes
2. **Instrucoes ignoradas** — constitution e templates sao "esquecidos" nas fases finais
3. **Confusao de fases** — output da fase TASKS referencia detalhes de SPECIFY que deveriam estar encapsulados na spec
4. **Custo exponencial** — cada fase paga pelo contexto acumulado de todas as fases anteriores

## Appetite

1-2 semanas (small batch). O pipeline runner ja executa fases em sequencia. O trabalho e particionar cada fase em um subprocess `claude -p` separado, passando apenas o artefato relevante.

## Solucao

Executar cada fase do pipeline como um **subagent fresco** (nova invocacao `claude -p`):

1. **Wave 1 (SPECIFY)**: `claude -p` recebe pitch.md + constitution + template-specify → gera spec.md
2. **Wave 2 (CLARIFY)**: `claude -p` recebe spec.md + template-clarify → gera perguntas + spec atualizada
3. **Wave 3 (DEBATE)**: `claude -p` recebe spec.md + personas → gera review
4. **Wave 4 (PLAN)**: `claude -p` recebe spec.md (aprovada) + template-plan → gera plan.md
5. **Wave 5 (TASKS)**: `claude -p` recebe plan.md + template-tasks → gera tasks.md
6. **Wave 6-N (IMPLEMENT)**: `claude -p` por task, recebendo apenas task + codebase context relevante

Cada wave recebe **apenas o artefato da fase anterior**, nao o historico completo. O pipeline runner gerencia o handoff entre waves, persistindo artefatos intermediarios no filesystem.

## Rabbit Holes

- **Nao tentar compartilhar contexto entre waves** — o ponto e justamente isolar. Se uma fase precisa de info de outra, essa info deve estar no artefato (spec.md, plan.md), nao no context window
- **Nao otimizar prematuramente** — comece com 1 wave por fase. Se alguma fase for rapida demais para justificar um subprocess, merge later
- **Nao paralelizar waves** — fases sao sequenciais por natureza (plan depende de spec)

## Criterios de Aceitacao

- [ ] Cada fase do pipeline executa em subprocess `claude -p` separado
- [ ] Context window de cada wave comeca "limpo" (apenas artefato + template)
- [ ] Artefatos intermediarios persistidos no filesystem entre waves
- [ ] Qualidade do output da fase IMPLEMENT e igual ou superior ao baseline (single-process)
- [ ] Metricas coletadas: tokens por wave, duracao por wave, qualidade score
- [ ] Pipeline completo (6+ waves) executa com sucesso end-to-end
