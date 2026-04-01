---
id: 014
title: "Telegram Notifications"
status: shipped
appetite: 2w
priority: 2
delivered_at: 2026-04-01
---
# Telegram Notifications

## Problem

Human gates no pipeline requerem aprovacao humana, mas nao ha mecanismo de notificacao. O operador precisa ficar monitorando manualmente se algum gate precisa de atencao. Isso inviabiliza operacao 24/7 e aumenta o tempo de resposta a gates para horas/dias.

## Appetite

**2w** — Depende da gate state machine de 013. aiogram e framework maduro — baixo risco tecnico.

## Dependencies

- Depends on: 013 (gate state machine)
- Blocks: 016 (daemon precisa de notificacoes para operar autonomamente)
