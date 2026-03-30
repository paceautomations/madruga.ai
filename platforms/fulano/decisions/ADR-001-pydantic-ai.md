---
title: 'ADR-001: pydantic-ai v1.70 como framework de agentes'
status: Accepted
decision: pydantic-ai v1.70
alternatives: LangGraph, Claude Agent SDK
rationale: Type safety end-to-end com Pydantic models como input/output de cada agent
---
# ADR-001: pydantic-ai v1.70 como framework de agentes
**Status:** Accepted | **Data:** 2026-03-23 | **Atualizado:** 2026-03-25

## Contexto
Precisamos de um framework para orquestrar agentes LLM que seja type-safe, suporte multiplos modelos e integre nativamente com MCP. O mercado oferece opcoes como LangGraph, Claude Agent SDK e pydantic-ai.

## Decisao
We will adotar pydantic-ai v1.70 como framework principal de agentes.

Motivos:
- Type-safe com validacao Pydantic nativa — erros pegos em dev, nao em prod
- Model-agnostic: troca de provider sem reescrever logica
- Suporte nativo a MCP (Model Context Protocol) sem adapters
- API enxuta e pythonico — curva de aprendizado baixa pro time

## Alternativas consideradas

### LangGraph
- Pros: Ecossistema LangChain maduro, muitos exemplos, suporte a grafos complexos
- Cons: Abstrações pesadas, vendor lock-in sutil com LangSmith, tipagem fraca (dict-based), overhead de runtime

### Claude Agent SDK
- Pros: Integração direta com Claude, bem mantido pela Anthropic
- Cons: Lock-in em Claude (sem model-agnostic), menos flexivel para orquestração custom, ecossistema menor

## Consequencias
- [+] Type safety end-to-end com Pydantic models como input/output de cada agent
- [+] Troca de modelo (OpenAI, Claude, Gemini) via config sem refactor
- [+] MCP nativo simplifica integracao com tools existentes
- [-] Ecossistema menor que LangChain — menos exemplos e community recipes
- [-] Versao 1.x ainda evoluindo rapido — possivel breaking changes em minor versions
- [-] V2 previsto para Abr/2026 — monitorar breaking changes. V1 tera 6 meses de suporte apos V2 launch
