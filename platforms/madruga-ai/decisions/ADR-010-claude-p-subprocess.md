---
status: accepted
title: "ADR-010: Claude -p Subprocess vs SDK Direto"
---
# ADR-010: Claude -p Subprocess vs SDK Direto
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O Madruga AI precisa invocar Claude para geracao de specs, debate multi-persona, classificacao de decisoes, e implementacao. Duas opcoes: usar o SDK Python da Anthropic diretamente, ou invocar `claude -p` (Claude Code CLI em modo pipe) como subprocess.

## Decisao

We will invoke Claude exclusively via `claude -p` subprocess, never using the Anthropic Python SDK directly.

## Alternativas consideradas

### Anthropic Python SDK
- Pros: tipado, streaming nativo, async, controle fino de parameters.
- Cons: requer gerenciar API key separadamente, nao herda config do Claude Code (hooks, CLAUDE.md), nao tem acesso a tools do Claude Code (Edit, Write, Bash), perde context do projeto.

### LangChain / LiteLLM
- Pros: abstrai provider, fallback entre modelos.
- Cons: overhead de abstração desnecessária para single-provider, latência adicional, dependência extra.

## Consequencias

- [+] Reaproveita autenticacao e configuracao do Claude Code já instalado
- [+] Subprocess pode usar tools do Claude Code quando necessario
- [+] ClaudeClient cria env limpo (CLAUDECODE unset, temp config dir) para evitar interferencia de hooks
- [-] Overhead de subprocess spawn (~50ms por call)
- [-] Output parsing manual (texto, nao structured)
- [-] Sem streaming nativo (output completo apos conclusao)
