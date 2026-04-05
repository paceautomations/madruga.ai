---
title: "Tech Alternatives"
updated: 2026-03-30
---
# Madruga AI — Alternativas Tecnologicas

## Resumo Executivo

A plataforma Madruga AI esta em transicao de sistema de documentacao arquitetural para pipeline autonomo de spec-to-code. O runtime engine (easter, orchestrator, debate engine, SpeckitBridge) sera construido nativamente neste repositorio, capturando aprendizados de `general/services/madruga-ai` mas sem migracao de codigo. As 4 decisoes tecnologicas abaixo definem como o runtime se comunica com Claude, notifica o operador, observa sua propria saude, e automatiza a execucao do pipeline.

Contexto: easter Python 3.12 asyncio rodando em WSL2 local. Subscription Claude Code (sem API key separada). Stack existente: SQLite WAL, structlog, FastAPI, Astro portal.

---

## Decisao 1: Interface Programatica com Claude

### Contexto

O runtime engine precisa invocar Claude programaticamente para executar skills (specify, plan, tasks, implement, review). Duas opcoes existem: `claude -p` (CLI headless mode) e Claude Agent SDK (Python package).

### Matriz de Alternativas

| Criterio | `claude -p` subprocess | Claude Agent SDK |
|----------|----------------------|-----------------|
| **Custo** | $0 (usa subscription existente) | Per-token API billing (requer API key) |
| **Latencia startup** | 2-5s por invocacao | Sub-segundo |
| **Acesso MCP servers** | Sim (completo, mesma config do usuario) | Custom tools only |
| **Concorrencia** | 3-5 seguro; 10+ instavel | Sem limite pratico |
| **Error handling** | Manual (exit codes, stderr) | Native Python exceptions |
| **Streaming** | stream-json (bug conhecido de hang) | Async iterators |
| **Crash recovery** | --resume de session file | Programatico |
| **Maturidade** | Estavel, usado em producao por milhares | SDK mais novo, menos battle-tested |
| **Fit para projeto** | Alto — unica opcao viavel | Bloqueado — requer API key |

### Analise Detalhada

**`claude -p` subprocess:**
- Pros: usa subscription existente ($0 extra), acesso completo a MCP servers configurados, --resume para manter estado entre calls, --allowedTools para controle de seguranca
- Cons: overhead de startup (2-5s), bug de hang em stream-json, concorrencia limitada a 3-5, error handling manual
- Mitigacoes: usar --output-format json (evita hang), semaforo asyncio (max 3), watchdog timer para SIGKILL, --resume para amortizar startup
- Source: [Claude Code Headless Docs](https://docs.anthropic.com/en/docs/claude-code/cli-usage#headless-mode)

**Claude Agent SDK:**
- Pros: startup sub-segundo, native Python exceptions, async iterators, controle programatico total
- Cons: **requer API key com billing separado** — nao aceita auth de subscription Pro/Max. Anthropic proibe uso de OAuth tokens de subscription em produtos terceiros.
- Source: [Agent SDK Issue #559](https://github.com/anthropics/claude-agent-sdk-python/issues/559), [Anthropic OAuth Policy](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/)

### Recomendacao

**`claude -p` subprocess** — unica opcao viavel dado o constraint de billing. Agent SDK esta bloqueado ate Anthropic suportar Max plan billing (sem previsao).

---

## Decisao 2: Canal de Notificacoes do Easter

### Contexto

O easter precisa notificar o operador sobre status de epics, decisoes pendentes, e erros. O canal sera Telegram Bot API via aiogram (ADR-018 supersedeu ADR-015). A implementacao sera construida nativamente em `madruga.ai`.

### Matriz de Alternativas

| Criterio | WhatsApp (wpp-bridge) | Telegram Bot | ntfy.sh | Discord Bot |
|----------|----------------------|-------------|---------|------------|
| **Custo** | Free (self-hosted) | Free | Free | Free |
| **Setup** | Ja existe, migrar | ~10 min | ~5 min | ~20 min |
| **Bidirecional** | Sim (poll messages) | Excelente (inline buttons) | Limitado | Bom (gateway) |
| **Async Python** | httpx (existente) | aiogram | aiohttp raw | discord.py |
| **WSL2** | Funciona (bridge local) | Outbound only | Outbound only | Outbound only |
| **Onde o operador ja esta** | **Sim — WhatsApp e o app principal** | Instalacao extra | App extra | App extra |
| **Fit para projeto** | Alto — ja funciona, migrar apenas | Alto — melhor UX tecnico | Medio — unidirecional | Medio |

### Analise Detalhada

**WhatsApp (wpp-bridge):**
- Pros: operador ja usa WhatsApp como app principal, bridge ja implementado e testado, poll-based (ask_choice com timeout), alertas com emoji/levels, integracao existente com easter (MessagingClient/WhatsAppProvider)
- Cons: wpp-bridge e servico separado que precisa rodar junto, WhatsApp Web session pode desconectar, sem inline buttons (interacao via texto livre A/B/C)
- Source: implementacao existente em `general/services/madruga-ai/src/integrations/messaging/providers/whatsapp.py`

**Telegram Bot API:**
- Pros: inline buttons nativos, callbacks sem tunnel, setup rapido, aiogram excelente
- Cons: operador precisaria abrir outro app, perda de contexto conversacional existente
- Source: [Telegram Bot API](https://core.telegram.org/bots/api)

### Recomendacao

**WhatsApp via wpp-bridge** — manter o canal onde o operador ja esta. Migrar o codigo do bridge e do provider para dentro do `madruga.ai` junto com o runtime engine. Refinamentos na implementacao serao definidos no epic de migracao.

> **Atualizado 2026-03-31:** Decisao revista — **Telegram Bot API (aiogram)** escolhido como canal de notificacoes. Motivacao: wpp-bridge depende de protocolo WhatsApp Web nao-oficial (instavel), exige headless Chromium (~200-400MB RAM), session desconecta com QR code manual, sem inline buttons. Alem disso, a decisao de nao migrar o codigo de `general` elimina a vantagem de "codigo ja existe". Ver [ADR-018](../decisions/ADR-018-telegram-bot-notifications.md).

---

## Decisao 3: Observability do Easter

### Contexto

O easter atualmente usa structlog para logging. Nao ha metricas, traces, ou error tracking estruturado. Precisa de visibilidade sobre saude, performance, e erros.

### Matriz de Alternativas

| Criterio | OTel + Grafana | structlog + SQLite | PostHog self-hosted | Sentry cloud free |
|----------|---------------|-------------------|--------------------|--------------------|
| **RAM** | ~1 GB | **~0 MB** | ~4-8 GB | **~15 MB** |
| **Setup** | 2-4h (Docker Compose) | **1-2h** | 2-4h | **15 min** |
| **Metricas** | Sim (Prometheus) | **Sim (custom)** | Nao | Nao |
| **Error tracking** | Basico | Custom | Basico | **Excelente** |
| **Traces** | Sim (Tempo) | Nao | Nao | **Sim** |
| **Dashboard** | Grafana (rico) | **Custom Astro** | PostHog UI | Sentry UI |
| **Manutencao** | Alta | **Baixa** | Alta | **Zero** |
| **structlog integracao** | Manual processor | **Nativo** | Manual | Bom (plugin) |
| **100% local** | Sim | **Sim** | Sim | Nao (SaaS) |

### Analise Detalhada

**structlog + SQLite metrics table:**
- Pros: ~100 LOC, zero deps novas, usa stack existente, dashboard no portal Astro, near-zero resource usage
- Cons: sem traces, sem alerting automatico, dashboard e custom work
- Implementacao: tabela `metrics` com (ts, name, kind, value, labels), middleware FastAPI ~30 LOC, cleanup periodico
- Source: [structlog docs](https://www.structlog.org/en/stable/), [SQLite WAL](https://www.sqlite.org/wal.html)

**Sentry cloud free tier:**
- Pros: error tracking com stack traces e breadcrumbs, auto-instrumenta FastAPI, performance traces, 5K erros/mes gratis, setup 15 min
- Cons: SaaS (nao 100% local), limite de 5K erros/mes
- Source: [Sentry Python FastAPI](https://docs.sentry.io/platforms/python/integrations/fastapi/), [Sentry Pricing](https://sentry.io/pricing/)

**OTel + Grafana:**
- Pros: observability completa (metricas + traces + logs), dashboards ricos
- Cons: ~1 GB RAM, 5 containers Docker, manutencao alta — overkill para easter unico
- Source: [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)

**PostHog self-hosted:**
- Pros: product analytics poderoso
- Cons: 4-8 GB RAM, 10+ containers, **ferramenta errada** — PostHog e product analytics, nao backend observability
- Source: [PostHog self-hosted](https://posthog.com/docs/self-host)

### Recomendacao

**Combo: structlog + SQLite metrics (local) + Sentry cloud free tier (error tracking)**

80% do valor por 5% do esforço. Graduar para OTel+Grafana so quando tiver 3+ servicos.

---

## Decisao 4: Automacao DAG-Driven do Pipeline

### Contexto

O pipeline tem 24 nodes em 2 niveis (L1: 13, L2: 11 por epic). Cada node tem dependencias, gate type, skill, e output. Hoje skills sao invocadas manualmente. O objetivo e automatizar a execucao lendo a definicao do DAG e adaptando quando o YAML muda.

### Matriz de Alternativas

| Criterio | Custom DAG Executor | Prefect 3 | Temporal | Airflow |
|----------|--------------------|-----------|---------| --------|
| **Human gates** | Manual (SQLite + resume) | **NAO** (so Cloud pago) | Nativo (signals) | NAO |
| **YAML source of truth** | **Direto** | Traducao necessaria | Read at runtime | Traducao |
| **Deps novas** | **Nenhuma** | ~50 packages | temporalio + Go binary | Massivo |
| **RAM** | **~0** | ~300MB | ~112MB | ~800MB |
| **Crash recovery** | Manual (DB state) | Built-in | Built-in (replay) | Built-in |
| **Complexidade setup** | **Trivial** | Medio | Medio | Alto |
| **Fit stdlib-only** | **Sim** | Nao | Nao | Nao |

### Analise Detalhada

**Custom DAG Executor (YAML-driven):**
- Pros: ~200 LOC, zero deps, YAML e source of truth direto, 80% ja construido (platform.yaml tem DAG, check-prerequisites.sh faz resolucao, post_save.py grava estado, db.py tem schema)
- Cons: sem crash recovery automatico (SQLite checkpoints sao suficientes), sem web UI (portal dashboard ja existe)
- Arquitetura: `dag_executor.py` le `platform.yaml` → topological sort → dispatch loop → `claude -p` por node → `post_save.py` grava → human gates pausam, Telegram notifica, resume quando aprovado
- Source: implementacao existente em `.specify/scripts/`

**Prefect 3:**
- Pros: web UI bonito, retries/timeouts built-in
- Cons: **human gates NAO suportados no OSS** (so Prefect Cloud pago), 50+ packages de dependencia, DAG-from-YAML requer camada de traducao
- Source: [Prefect OSS](https://www.prefect.io/prefect/open-source)

**Temporal:**
- Pros: **melhor suporte a human gates** (signals + wait_condition), duravel, crash recovery automatico
- Cons: requer Go binary (~112MB), learning curve alta (deterministic replay constraints), overkill para 24 nodes single-user
- Source: [Temporal Python SDK](https://docs.temporal.io/develop/python)

**Airflow:**
- Descartado: ~800MB RAM, sem human gates nativos, complexidade extrema para o use case

### Recomendacao

**Custom DAG Executor** (~200 LOC Python). O YAML do `platform.yaml` e o source of truth — muda o YAML, comportamento muda. Se depois precisar de durabilidade do Temporal, migracao e limpa: YAML fica igual, troca backend.

---

## Tabela Consolidada

| # | Decisao | Recomendacao | Confianca | Gate |
|---|---------|-------------|-----------|------|
| 1 | Interface com Claude | `claude -p` subprocess | Alta | auto |
| 2 | Canal de notificacoes | ~~WhatsApp via wpp-bridge~~ → Telegram Bot API (aiogram) — ver ADR-018 | Alta | 1-way-door |
| 3 | Observability | structlog+SQLite + Sentry free | Alta | auto |
| 4 | Automacao DAG-driven | Custom DAG executor (YAML→SQLite→subprocess) | Alta | 1-way-door |

---

## Premissas e Riscos

### Premissas

1. Subscription Claude Code Max se mantem ativa e sem restricoes adicionais em `claude -p` [VALIDAR periodicamente]
2. ~~wpp-bridge continua funcional e mantenivel apos migracao~~ [INVALIDADA — ver ADR-018, substituido por Telegram Bot API]
3. Sentry free tier (5K erros/mes) e suficiente para easter single-user [VALIDAR em producao]
4. 24 nodes e escala suficiente para custom executor vs framework [VALIDAR se pipeline crescer para 50+]

### Riscos Tecnologicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Anthropic restringe `claude -p` headless em subscription | Baixa | Critico | Monitorar changelogs. Fallback: migrar para API key (Agent SDK) |
| ~~wpp-bridge WhatsApp Web session desconecta frequentemente~~ | ~~Media~~ | ~~Medio~~ | [ELIMINADO — ver ADR-018, substituido por Telegram Bot API] |
| Sentry free tier descontinuado ou limites reduzidos | Baixa | Baixo | structlog+SQLite cobre 80% — Sentry e complementar |
| Custom DAG executor nao escala para pipelines complexos | Baixa | Medio | Migracao para Temporal quando necessario (YAML fica igual) |
| Bug de hang em `claude -p` stream-json bloqueia easter | Media | Medio | Usar --output-format json, watchdog timer com SIGKILL |

---

## Fontes

1. [Claude Code Headless Mode](https://docs.anthropic.com/en/docs/claude-code/cli-usage#headless-mode)
2. [Agent SDK Issue #559 — Max plan billing](https://github.com/anthropics/claude-agent-sdk-python/issues/559)
3. [Anthropic OAuth Policy](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/)
4. [Claude Code CLI hang bug #25629](https://github.com/anthropics/claude-code/issues/25629)
5. [Claude Code concurrent sessions #24990](https://github.com/anthropics/claude-code/issues/24990)
6. [structlog docs](https://www.structlog.org/en/stable/)
7. [Sentry Python FastAPI](https://docs.sentry.io/platforms/python/integrations/fastapi/)
8. [Prefect OSS](https://www.prefect.io/prefect/open-source)
9. [Temporal Python SDK](https://docs.temporal.io/develop/python)
10. [Telegram Bot API](https://core.telegram.org/bots/api)
