---
id: 016
title: "Daemon 24/7"
status: planned
appetite: 2w
priority: 3
---
# Daemon 24/7

## Problem

O pipeline so executa quando um humano invoca skills manualmente no terminal. Nao existe processo persistente que monitore o estado do DAG, dispare skills quando prerequisites sao atendidos, e opere continuamente. Sem daemon, a promessa de autonomia do pipeline e impossivel.

## Appetite

**2w** — Ultimo epic do MVP. Monta em cima de tudo. Mecanico: asyncio event loop + health checks + systemd.

## Dependencies

- Depends on: 014 (notificacoes para gates), 013 (DAG executor)
- Blocks: nenhum (ultimo epic do MVP)

## Implementation Notes

- **Polling loop do Telegram**: epic 014 entrega `telegram_bot.py` como script standalone. O daemon 016 deve refatorar para integrar o polling como coroutine asyncio composavel dentro do event loop principal.
- **Fallback ntfy.sh**: ADR-018 define ntfy.sh como fallback quando Telegram API esta unreachable. Implementar neste epic (~15-20 LOC, HTTP POST simples).
