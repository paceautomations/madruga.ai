---
title: "Integrations"
updated: 2026-04-06
sidebar:
  order: 5
---
# Madruga AI — Integrations

> Pontos de integracao externa: APIs, webhooks, filas, bancos de dados externos.
> Topologia de deploy → ver [blueprint.md](../blueprint/) · Containers → ver [containers.md](../containers/)

---

## Mapa de Integracoes

| # | Sistema Externo | Protocolo | Direcao | Frequencia | Auth | Fallback |
|---|----------------|-----------|---------|-----------|------|----------|
| 1 | **Telegram Bot API** | HTTPS long-polling (aiogram) | Easter ↔ Telegram | Contínuo (polling) | Bot token | Reconnect com backoff exponencial |
| 2 | **Anthropic Claude CLI** | subprocess + JSON stdout | DAG Executor → claude -p | Per-skill dispatch | Keychain (automatico) | 3 retries + circuit breaker (5 falhas → 300s) |
| 3 | **GitHub** | SSH/HTTPS git | DAG Executor → GitHub | Per-epic (clone/fetch) | SSH key / HTTPS token | Retry 3x |
| 4 | **Sentry** | HTTPS SDK (DSN) | Easter → Sentry | Per-error (async) | DSN env var | Fire-and-forget (opcional) |
| 5 | **ntfy.sh** | HTTPS POST | Easter → ntfy | Per-alert | — (public topic) | Silencioso se falhar |

---

## Detalhes por Integracao

### Telegram Bot API

- **Biblioteca:** aiogram 3.x
- **Modo:** Long-polling (não webhook — simplifica deploy sem TLS)
- **Funcionalidades:** Inline keyboards para gate approval, comandos (/status, /gates, /help), free-text via claude -p
- **Chat ID:** Fixo via env `MADRUGA_TELEGRAM_CHAT_ID` (segurança: ignora mensagens de outros chats)
- **Backoff:** aiogram built-in retry para polling errors
- **ADR:** ADR-018

### Anthropic Claude CLI

- **Invocação:** `claude -p --output-format json --max-turns 50`
- **Timeout:** `MADRUGA_EXECUTOR_TIMEOUT` (default 3000s)
- **Retry:** 3 tentativas com backoff [5, 10, 20]s + jitter
- **Circuit Breaker:** 5 falhas consecutivas → open 300s → half-open test
- **Output:** JSON com `result`, `cost_usd`, `duration_ms`, `total_turns`
- **ADR:** ADR-010

### GitHub (VCS)

- **Uso:** Clone/fetch repos externos para worktree isolation (epics de plataformas com repo externo)
- **Protocolo:** SSH (preferido) ou HTTPS
- **Frequência:** Per-epic startup (epic-context skill)
- **ADR:** —

### Sentry (Error Tracking)

- **SDK:** sentry-sdk Python (opcional — ativado via `MADRUGA_SENTRY_DSN`)
- **Integracoes:** FastAPI, asyncio
- **Modo:** Async fire-and-forget
- **ADR:** ADR-016

### ntfy.sh (Push Alerts)

- **Protocolo:** HTTP POST simples (stdlib urllib)
- **Uso:** Alertas de gate pending, pipeline completion
- **Fallback:** Silencioso se falhar (não bloqueia pipeline)
