---
title: "ADR-010: Claude -p Subprocess como Interface Programatica"
status: accepted
date: 2026-03-30
supersedes: "ADR-010 original (2026-03-27)"
decision: Invocar Claude exclusivamente via `claude -p` subprocess. Agent SDK bloqueado
  por constraint de billing (requer API key). SDK Python direto perde acesso a tools e
  MCP servers.
alternatives: Claude Agent SDK (claude_agent_sdk), Anthropic Python SDK direto
rationale: Processo unico — sem overhead de coordenacao distribuida
---
# ADR-010: Claude -p Subprocess como Interface Programatica

## Status

Accepted — 2026-03-30 (atualizado; supersede versao de 2026-03-27)

## Contexto

O runtime engine do Madruga AI precisa invocar Claude programaticamente para executar skills do pipeline (specify, plan, tasks, implement, review). O easter roda em Python 3.12 asyncio sobre WSL2. O operador tem subscription Claude Code Max e NAO quer billing separado de API.

Tres opcoes foram avaliadas: `claude -p` (CLI headless), Claude Agent SDK, e Anthropic Python SDK direto.

A versao anterior desta ADR (2026-03-27) avaliou SDK vs subprocess mas nao incluia a restricao de billing da subscription nem dados de concorrencia e bugs conhecidos. Esta atualizacao incorpora a pesquisa de tech-alternatives.md (2026-03-30).

## Decisao

Invocar Claude exclusivamente via `claude -p` subprocess. O Agent SDK esta bloqueado pelo constraint de billing (requer API key, nao aceita subscription). O SDK Python direto perde acesso a tools e MCP servers do Claude Code.

Mitigacoes obrigatorias:
1. `--output-format json` (evita bug de hang em stream-json)
2. Semaforo asyncio max 3 calls concorrentes (evita contencao de recursos e interleaving de stdout)
3. Watchdog timer com SIGKILL para processos pendurados (timeout configuravel)
4. `--allowedTools` explicito em toda call (seguranca)
5. `--resume` / `--continue` para amortizar startup em conversas longas
6. Adapter layer: todas as chamadas a `claude -p` isoladas em `ClaudeClient` (ja existe). Se output format mudar entre versoes do CLI, so esse modulo precisa de ajuste.

**Trigger de revisao:** se Anthropic adicionar billing de subscription ao Agent SDK, ou lançar um SDK local que aceite auth de subscription, re-avaliar esta decisao.

## Alternativas Consideradas

### Alternativa A: `claude -p` subprocess (escolhida)
- **Pros:** $0 extra (usa subscription existente), acesso completo a MCP servers configurados, --resume para manter estado, --allowedTools para controle de seguranca, tools do Claude Code (Read, Write, Edit, Bash, Grep, Glob)
- **Cons:** overhead de startup 2-5s por invocacao, bug conhecido de hang em stream-json ([#25629](https://github.com/anthropics/claude-code/issues/25629)), concorrencia instavel acima de 5 sessions ([#24990](https://github.com/anthropics/claude-code/issues/24990)), error handling manual (exit codes + stderr)
- **Fit:** Unica opcao viavel dado o constraint de billing. O overhead de startup e aceitavel para um easter que processa epics de minutos/horas.

### Alternativa B: Claude Agent SDK (`claude_agent_sdk`)
- **Pros:** startup sub-segundo, native Python exceptions, async iterators, controle programatico total, custom tools
- **Cons:** **requer API key com billing separado** — Anthropic proibe uso de OAuth tokens de subscription Pro/Max em produtos terceiros ([Issue #559](https://github.com/anthropics/claude-agent-sdk-python/issues/559)). Sem acesso a MCP servers do Claude Code. Sem tools built-in (Read, Write, Edit).
- **Rejeitada porque:** constraint de billing e dealbreaker. Sem previsao de suporte a Max plan.

### Alternativa C: Anthropic Python SDK direto
- **Pros:** tipado, streaming nativo, async, controle fino de parameters
- **Cons:** mesma restricao de billing do Agent SDK (requer API key), nao herda config do Claude Code (hooks, CLAUDE.md), sem acesso a tools do Claude Code, sem acesso a MCP servers
- **Rejeitada porque:** mesmo dealbreaker de billing + perda de todo o ecossistema de tools e config do Claude Code.

## Consequencias

### Positivas
- Zero custo adicional — opera dentro da subscription existente
- Acesso completo ao ecossistema Claude Code (tools, MCP servers, hooks, CLAUDE.md)
- ClaudeClient ja implementado com circuit breaker separado para epics/actions
- Env limpo (CLAUDECODE unset, temp config dir) previne interferencia de hooks do projeto

### Negativas
- Overhead de startup de 2-5s por invocacao (aceitavel para pipeline de minutos)
- Bug de hang em stream-json exige watchdog externo
- Concorrencia limitada a 3-5 sessions simultaneas
- Error handling via parsing de stderr (fragil, pode quebrar entre versoes do CLI)

### Riscos
- Anthropic pode restringir `claude -p` headless em subscriptions futuras → mitigacao: monitorar changelogs, fallback para API key se necessario
- OOM em acumulo de subprocessos ([#13126](https://github.com/anthropics/claude-code/issues/13126)) → mitigacao: semaforo de concorrencia + cleanup apos cada call

## Referencias

- [Claude Code Headless Mode](https://docs.anthropic.com/en/docs/claude-code/cli-usage#headless-mode)
- [Agent SDK Issue #559 — Max plan billing](https://github.com/anthropics/claude-agent-sdk-python/issues/559)
- [Anthropic OAuth Policy](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/)
- [CLI hang bug #25629](https://github.com/anthropics/claude-code/issues/25629)
- [Concurrent sessions bug #24990](https://github.com/anthropics/claude-code/issues/24990)
- [OOM subprocess accumulation #13126](https://github.com/anthropics/claude-code/issues/13126)
