---
status: accepted
title: "ADR-011: Circuit Breaker para API Calls"
---
# ADR-011: Circuit Breaker para API Calls
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O daemon executa autonomamente 24/7 e faz multiplas chamadas ao Claude API por pipeline. Se o API estiver com problemas (rate limit, downtime), chamadas consecutivas desperdicam tempo e podem piorar a situacao. Precisamos de um mecanismo para suspender chamadas automaticamente quando detectamos falhas consecutivas, e retomar quando o servico se recuperar.

## Decisao

We will implement a Circuit Breaker pattern with separate breakers per call category (epic pipeline vs standalone actions), failing fast when the breaker is open.

## Alternativas consideradas

### Retry-only (sem circuit breaker)
- Pros: simples.
- Cons: nao para de bater em API com problema, desperdiça rate limit budget, nao distingue falha transitoria de downtime.

### Rate limiter fixo (token bucket)
- Pros: previne burst.
- Cons: nao reage a falhas reais, apenas limita throughput.

## Consequencias

- [+] Fail-fast quando API esta com problemas (0ms check local)
- [+] Breakers separados: falha em actions nao bloqueia epics (e vice-versa)
- [+] Recovery automatico apos timeout (300s por padrao)
- [+] Configuravel: failure_threshold=5, recovery_timeout=300s
- [-] Complexidade adicional no ClaudeClient
- [-] Pode ser over-cautious (abre breaker por 5min mesmo que problema dure 30s)
