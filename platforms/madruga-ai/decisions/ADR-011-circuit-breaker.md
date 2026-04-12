---
title: 'ADR-011: Circuit Breaker para API Calls'
status: Accepted
decision: We will implement a Circuit Breaker pattern with separate breakers per call
  category (epic pipeline vs standalone actions), failing fast when the breaker is
  open.
alternatives: Retry-only (sem circuit breaker), Rate limiter fixo (token bucket)
rationale: Fail-fast quando API esta com problemas (0ms check local)
---
# ADR-011: Circuit Breaker para API Calls
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O easter executa autonomamente 24/7 e faz multiplas chamadas ao Claude API por pipeline. Se o API estiver com problemas (rate limit, downtime), chamadas consecutivas desperdicam tempo e podem piorar a situacao. Precisamos de um mecanismo para suspender chamadas automaticamente quando detectamos falhas consecutivas, e retomar quando o servico se recuperar.

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

## Addendum: Same-Error Escalation (2026-04-12)

O circuit breaker generico (5 falhas → open) nao resolvia o caso de erros deterministicos que nunca se recuperam por retry (e.g., "unfilled template" repetido 5x no epic 023, "exitcode 1" repetido 29x no epic 021). Nesses casos, o retry e puro desperdicio — o problema nao e transiente.

**Decisao adicional:** Classificar erros antes de retry em 3 categorias:

| Categoria | Patterns | Threshold | Justificativa |
|-----------|----------|-----------|---------------|
| **Deterministic** | unfilled template, exitcode, output not found | 2 identicos → escalar | Retry nunca resolve bugs no template ou no skill |
| **Transient** | rate_limit, timeout, context_length | Ciclo completo (4 tentativas) | APIs se recuperam; context_length pode melhorar com prompt trimming |
| **Unknown** | Qualquer outro | 3 identicos → escalar | Conservador — pode ser transiente ou deterministico |

**Ortogonalidade:** Same-error escalation opera por tentativa dentro de `dispatch_with_retry_async()`, independente do CircuitBreaker generico por plataforma. Ambos coexistem — same-error e um fast-path que evita chegar aos 5 failures do breaker generico.

**Impacto medido:** -7h de wall-clock waste nos dados recentes (29 retries exitcode 1 → 2, 5 retries unfilled template → 2).
