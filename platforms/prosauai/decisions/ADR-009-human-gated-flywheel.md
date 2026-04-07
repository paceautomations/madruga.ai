---
title: 'ADR-009: Flywheel de dados com gate humano semanal'
status: Accepted
decision: Flywheel com gate humano
alternatives: Auto-deploy baseado em eval scores, Deploy manual ad-hoc
rationale: Zero risco de regressao silenciosa por auto-deploy
---
# ADR-009: Flywheel de dados com gate humano semanal
**Status:** Accepted | **Data:** 2026-03-23

## Contexto
O sistema coleta feedback e metricas de qualidade que podem ser usados para melhorar prompts automaticamente. Porem, auto-deploy de prompts sem revisao humana traz riscos de regressao silenciosa e comportamento inesperado.

## Decisao
We will implementar um flywheel de dados semanal com gate humano obrigatorio — nunca auto-deploy de prompts.

Motivos:
- Prompts afetam diretamente a experiencia do usuario — regressoes sao dificeis de detectar automaticamente
- Gate humano semanal permite curadoria de melhorias com contexto de negocio
- Flywheel coleta dados continuamente, mas mudancas sao aplicadas em batch controlado
- Safety first — erro de prompt em producao pode ser pior que prompt subotimo

## Alternativas consideradas

### Auto-deploy baseado em eval scores
- Pros: Ciclo de melhoria mais rapido, zero intervencao humana, otimizacao continua
- Cons: Risco de regressao em dimensoes nao medidas pelos evals, comportamento inesperado em edge cases, dificil rollback se problema so aparece dias depois

### Deploy manual ad-hoc
- Pros: Controle total, revisao caso a caso
- Cons: Sem cadencia, prompts ficam stale, nao aproveita dados coletados sistematicamente

## Consequencias
- [+] Zero risco de regressao silenciosa por auto-deploy
- [+] Revisao semanal cria disciplina de melhoria continua
- [+] Dados acumulados permitem decisoes informadas (nao gut feeling)
- [+] Rollback trivial — versao anterior sempre disponivel
- [-] Ciclo de melhoria mais lento (semanal vs continuo)
- [-] Requer disciplina do time para manter a cadencia semanal
- [-] Melhorias obvias ficam "na fila" ate a proxima revisao

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
