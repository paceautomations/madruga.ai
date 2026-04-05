---
title: 'ADR-013: Decision Gates (1-way/2-way Door)'
status: Accepted
decision: We will classify all decisions as 1-way doors (irreversible, require human
  approval) or 2-way doors (reversible, auto-decidable by easter), with configurable
  always_2way patterns and automatic ADR generation for 1-way doors.
alternatives: Tudo escala para humano, Tudo auto-decide
rationale: Autonomia para decisoes reversiveis (2-way doors)
---
# ADR-013: Decision Gates (1-way/2-way Door)
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O easter executa autonomamente e inevitavelmente encontra decisoes durante o pipeline (ex: escolha de lib, mudanca de schema, API publica). Algumas decisoes sao reversiveis ("usar pytest vs unittest") e podem ser tomadas autonomamente. Outras sao irreversiveis ("deletar coluna de banco em producao") e devem escalar para humano. Precisamos de um mecanismo para classificar e tratar decisoes automaticamente.

## Decisao

We will classify all decisions as 1-way doors (irreversible, require human approval) or 2-way doors (reversible, auto-decidable by easter), with configurable always_2way patterns and automatic ADR generation for 1-way doors.

## Alternativas consideradas

### Tudo escala para humano
- Pros: seguro, humano decide tudo.
- Cons: mata autonomia do easter, pipeline para a cada decisao trivial, nao escala.

### Tudo auto-decide
- Pros: maximo throughput.
- Cons: riscos catastroficos em decisoes irreversiveis (mudanca de API publica, delete de dados).

## Consequencias

- [+] Autonomia para decisoes reversiveis (2-way doors)
- [+] Safety gate para decisoes irreversiveis (1-way doors)
- [+] ADRs gerados automaticamente para 1-way doors (rastreabilidade)
- [+] Notificacao Telegram em CRITICAL_STOP gates
- [+] Configurable always_2way list (naming, formatting, code style, etc.)
- [-] Classificador pode errar (falso positivo = pipeline para desnecessariamente; falso negativo = decisao irreversivel tomada autonomamente)
- [-] Epic fica parked ate humano responder (timeout 24h)
