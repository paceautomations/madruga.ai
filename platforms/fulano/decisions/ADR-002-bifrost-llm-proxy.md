---
title: 'ADR-002: Bifrost (Go) como LLM proxy'
status: Accepted
decision: Bifrost (Go, MIT)
alternatives: LiteLLM, Proxy custom (httpx + FastAPI)
rationale: Latencia minima no proxy layer — usuarios nao percebem overhead
---
# ADR-002: Bifrost (Go) como LLM proxy
**Status:** Accepted | **Data:** 2026-03-23

## Contexto
Precisamos de um proxy unificado para rotear chamadas a multiplos LLM providers (OpenAI, Anthropic, Google) com load balancing, fallback e observabilidade. As opcoes principais sao LiteLLM (Python) e Bifrost (Go).

## Decisao
We will adotar Bifrost (Go) como LLM proxy unificado.

Motivos:
- 50x mais rapido que LiteLLM em benchmarks de throughput
- 68% menos consumo de memoria — critico para rodar junto com os servicos
- Binario Go estatico — deploy trivial, sem dependencias Python extras
- API compativel com OpenAI — drop-in replacement

## Alternativas consideradas

### LiteLLM
- Pros: Ecossistema Python (mesma stack), suporte a 100+ providers, community ativa, UI de admin inclusa
- Cons: Performance significativamente inferior (50x mais lento), consumo de memoria alto, adiciona mais uma app Python no stack

### Proxy custom (httpx + FastAPI)
- Pros: Controle total, sem dependencia externa
- Cons: Reinventar roda (retry, fallback, rate limiting), custo de manutencao alto, tempo de desenvolvimento

## Consequencias
- [+] Latencia minima no proxy layer — usuarios nao percebem overhead
- [+] Footprint pequeno — roda como sidecar sem impacto nos recursos
- [+] Deploy simples com binario unico
- [-] Linguagem diferente do stack principal (Go vs Python) — contribuicoes requerem conhecimento Go
- [-] Menos providers suportados out-of-the-box que LiteLLM
