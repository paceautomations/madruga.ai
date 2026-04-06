---
title: 'ADR-015: Noisy Neighbor mitigation — rate limiting e circuit breaker per tenant'
status: Accepted
decision: Rate limiting + circuit breaker
alternatives: Sem rate limiting (confiar no billing), Infra separada por tenant (silo
  — como Bland.ai), Throttling apenas no LLM (Bifrost caps), WAF/API Gateway externo
  (Cloudflare, Kong)
rationale: 1 tenant nao derruba todos — protecao em 4 camadas (borda, LLM, fila, logica)
---
# ADR-015: Noisy Neighbor mitigation — rate limiting e circuit breaker per tenant
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
Fulano usa Pool model compartilhado (ADR-011) onde todos os tenants dividem a mesma infra: Postgres, Redis, Bifrost, LLM providers. Sem protecao, um unico tenant pode consumir todos os recursos (LLM tokens, Redis connections, CPU) e degradar a experiencia de todos os outros. Isso e o problema classico de "noisy neighbor" em sistemas multi-tenant.

O research (multi-tenant-agents-mar2026.md, Secao 2.3.3) identificou 4 mecanismos necessarios.

## Decisao
We will implementar 4 camadas de protecao contra noisy neighbors, todas operando per-tenant:

### 1. Rate Limiting per Tenant (Redis Sliding Window)

```python
# Sliding window no Redis — limita mensagens por minuto por tenant
# Key: rate:{tenant_id}:msgs — TTL: 60s
async def check_rate_limit(tenant_id: str) -> bool:
    key = f"rate:{tenant_id}:msgs"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 60)
    return current <= tenant.rate_limit_per_minute  # ex: 100/min starter, 500/min business
```

- Limites configurados por tier de billing (ADR-012)
- Resposta ao exceder: HTTP 429 + mensagem amigavel ao usuario final ("Estou um pouco ocupado, tente novamente em alguns segundos")
- Granularidade: por minuto (burst protection) + por dia (budget protection)

### 2. LLM Spend Caps (Bifrost — ADR-002)

- Bifrost proxy rastreia custo acumulado por tenant por dia
- Hard cap configuravel por tier (ex: Starter = $5/dia, Business = $50/dia)
- Ao atingir cap: throttle (rate limit reduzido) antes de bloquear
- Alerta ao admin do tenant quando atinge 80% do cap diario
- Dashboard de custo no admin panel (real-time via LangFuse — ADR-007)

### 3. Queue Priority (Redis Streams — ADR-003)

- Consumer groups com prioridade por tier:
  - `priority:high` — Business + Enterprise (processamento imediato)
  - `priority:normal` — Starter + Growth
  - `priority:low` — Free tier (best-effort, pode ter delay de ate 5s)
- Implementacao: 3 streams separados, consumers leem high primeiro, depois normal, depois low
- Starvation prevention: low priority processado pelo menos 1 a cada 10 mensagens

### 4. Circuit Breaker per Tenant

```python
# Se tenant gera mais de N erros em janela de tempo, circuit abre
# Pattern: closed → open (block) → half-open (test) → closed
circuit_config = {
    "error_threshold": 50,       # erros em 5 minutos
    "open_duration_seconds": 300, # 5 min bloqueado
    "half_open_max_requests": 5,  # testa com 5 requests
}
```

- Triggers: loops de agente (agente chamando mesmo tool infinitamente), webhooks falhando repetidamente, LLM retornando erros em serie
- Ao abrir circuito: mensagens do tenant vao para DLQ (ADR-003), admin recebe alerta
- Half-open: libera 5 mensagens de teste. Se passam, fecha circuito. Se falham, abre de novo
- Log detalhado no LangFuse para diagnostico

### Monitoramento

- Dashboard de saude por tenant no admin (mensagens/min, erros/min, LLM spend, queue depth)
- Alertas automaticos: rate limit hit >10x em 1h, circuit breaker aberto, spend cap >80%
- Metricas expostas via LangFuse (ADR-007) para correlacao com qualidade de respostas

## Alternativas consideradas

### Sem rate limiting (confiar no billing)
- Pros: Zero complexidade, billing natural limita uso
- Cons: Um tenant com bug (loop de mensagens) consome todo o LLM budget e degrada outros tenants em tempo real. Billing so limita no fim do mes — dano ja aconteceu. Inaceitavel em pool model.

### Infra separada por tenant (silo — como Bland.ai)
- Pros: Isolamento total, noisy neighbor impossivel
- Cons: Custo inviavel (ADR-011 ja decidiu pool model), complexidade operacional enorme, nao escala para 100+ tenants com time de 5

### Throttling apenas no LLM (Bifrost caps)
- Pros: Mais simples que 4 camadas, protege o recurso mais caro
- Cons: Nao protege Redis, Postgres, CPU. Tenant pode fazer 10K requests/min que nao chegam no LLM mas sobrecarregam o sistema. Rate limiting na borda e necessario.

### WAF/API Gateway externo (Cloudflare, Kong)
- Pros: Rate limiting battle-tested, DDoS protection, zero codigo custom
- Cons: Nao tem contexto de tenant (rate limit por IP, nao por tenant_id), nao integra com billing tiers, custo adicional, nao resolve circuit breaker por logica de negocio

## Consequencias
- [+] 1 tenant nao derruba todos — protecao em 4 camadas (borda, LLM, fila, logica)
- [+] Degradacao graciosa: fallback para modelo mais barato antes de bloquear
- [+] Queue priority garante SLA para tenants pagantes
- [+] Circuit breaker previne cascading failures (loop de agente nao consome infinitamente)
- [+] Monitoramento per-tenant permite diagnostico rapido
- [-] Complexidade adicional — 4 mecanismos para implementar e manter
- [-] Falsos positivos possiveis: tenant legitimo com pico de uso pode ser throttled (mitiga: limites generosos + alerta antes de bloquear)
- [-] Rate limiting no Redis adiciona 1 roundtrip por request (mitiga: sub-ms em Redis local)
- [-] Tuning dos thresholds requer dados reais de producao — valores iniciais serao estimativas

## Refinamentos da architecture review (Mar/2026)

### TPM como metrica primaria de rate limiting
RPM (Request-Per-Minute) e insuficiente para LLM workloads — um request pode consumir 100 tokens ou 100K tokens. **TPM (Token-Per-Minute)** captura o custo real:
- Rate limit por RPM: baseline, necessario mas nao suficiente
- Rate limit por TPM: essencial — conta tokens input + output consumidos
- Combinacao: RPM protege contra burst, TPM protege contra custo

### Concurrency limits (critico para streaming)
Streaming responses mantem conexoes abertas por longos periodos. Um tenant com muitas conversas simultaneas pode monopolizar connections:
- Limite de requests simultaneos por tenant (ex: Free=5, Starter=20, Business=100)
- Conexoes de streaming contam como slots ativos ate completar

### Anti-pattern: retry loop em 429
Agente recebendo HTTP 429 que retenta em loop apertado sem backoff = DoS auto-infligido. Regra: tratar 429 como circuit breaker trigger (abrir circuito), nao como "tente de novo imediatamente". Usar exponential backoff com jitter apos circuit re-close
