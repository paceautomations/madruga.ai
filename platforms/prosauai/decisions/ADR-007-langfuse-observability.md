---
title: 'ADR-007: LangFuse v3 self-hosted para observabilidade'
status: Superseded
superseded_by: ADR-020-phoenix-observability
decision: LangFuse v3 (self-hosted)
alternatives: LangSmith, Phoenix (Arize), Helicone
rationale: Visibilidade completa de traces, custo e latencia por agente/modelo
---
# ADR-007: LangFuse v3 self-hosted para observabilidade
**Status:** ~~Accepted~~ **Superseded** por [ADR-020](ADR-020-phoenix-observability.md) (Phoenix/Arize) | **Data:** 2026-03-23 | **Atualizado:** 2026-04-12

> **NOTA:** Esta ADR foi superseded no epic 002. A decisao de usar Phoenix (Arize) self-hosted em vez de LangFuse foi motivada por: single container (sem ClickHouse), Postgres backend (Supabase), API OTLP gRPC nativa, ops drasticamente mais simples. Ver [ADR-020](ADR-020-phoenix-observability.md).

## Contexto
Precisamos de observabilidade completa para chamadas LLM: traces, custo, latencia, qualidade de respostas e prompt management. As opcoes incluem LangFuse (open-source), LangSmith (Langchain) e Phoenix (Arize).

## Decisao
We will adotar LangFuse v3 self-hosted como plataforma de observabilidade LLM.

Motivos:
- 26M+ SDK installs/mes — adocao massiva, community forte
- Licenca MIT — sem restricoes de uso comercial
- Prompt management integrado — versiona e deploya prompts sem redeploy de app
- Self-hosted elimina preocupacao com dados sensiveis saindo do ambiente

## Alternativas consideradas

### LangSmith
- Pros: Integracao perfeita com LangChain/LangGraph, UI polida, bom para debugging de chains
- Cons: SaaS-only (dados fora do ambiente), pricing opaco em escala, lock-in com ecossistema LangChain

### Phoenix (Arize)
- Pros: Forte em evals automatizados, bom para deteccao de drift, open-source
- Cons: Foco mais em ML observability que LLM ops, community menor, prompt management limitado

### Helicone (cloud proxy)
- Pros: Setup em 1 linha (proxy URL), dashboard automatico, rate limiting e caching built-in, free tier generoso (100K requests)
- Cons: SaaS-only (dados fora do ambiente — mesmo problema do LangSmith), sem prompt management nativo, menos profundidade em traces multi-step que LangFuse

## Consequencias
- [+] Visibilidade completa de traces, custo e latencia por agente/modelo
- [+] Prompt management centralizado — versoes, A/B, rollback
- [+] Dados ficam no nosso ambiente (self-hosted)
- [+] SDK leve — decorator-based, nao invasivo no codigo
- [-] Infra adicional para manter (Postgres + ClickHouse para LangFuse v3)
- [-] Self-hosted requer updates manuais e monitoramento

## Alertas operacionais (ClickHouse v3)
ClickHouse (requerido pelo LangFuse v3) tem problemas operacionais documentados:
- **CPU spikes idle**: ClickHouse consome CPU alto mesmo sem uso do LangFuse. Persiste apos shutdown do web/worker
- **Missing events table** (v3.152.0): Migration nao cria tabela necessaria — pagina de traces quebra
- **Permission issues**: Volumes em shared storage (Azure) falham no startup
- **Timezone**: ClickHouse DEVE rodar em UTC. Non-UTC nao e suportado
- **Clustered mode**: Requer migrations manuais (auto-migration desabilitada)

### Regras obrigatorias
1. **Fixar versao** do LangFuse e ClickHouse — NUNCA atualizar sem testar em staging primeiro
2. **Monitorar CPU/memoria** do ClickHouse separadamente do app
3. **Backup plan**: Phoenix (Arize, open-source, sem ClickHouse) como fallback se ops ficar inviavel para time de 5

### Instrumentacao
Adotar **OpenTelemetry GenAI Semantic Conventions** como padrao de instrumentacao:
- Span types: `invoke_agent`, `chat {model_name}`, `tool_call`
- Atributos: `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `tenant_id` como atributo obrigatorio em todo span — permite filtrar dashboards e cost attribution por tenant

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
