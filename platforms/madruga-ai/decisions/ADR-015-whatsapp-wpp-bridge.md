---
title: "ADR-015: WhatsApp via wpp-bridge como Canal de Notificacoes"
status: accepted
date: 2026-03-30
---
# ADR-015: WhatsApp via wpp-bridge como Canal de Notificacoes

## Status

Accepted — 2026-03-30

## Contexto

O daemon Madruga AI precisa notificar o operador sobre status de epics, decisoes pendentes (1-way-door), e erros criticos. O canal deve suportar comunicacao bidirecional: o daemon envia, o operador responde para aprovar/rejeitar decisoes.

O operador (Gabriel) usa WhatsApp como app principal de comunicacao. Um gateway wpp-bridge ja existe e funciona em `general/services/madruga-ai/src/integrations/messaging/providers/whatsapp.py`. O runtime engine sera migrado para o repo madruga.ai, incluindo o wpp-bridge.

## Decisao

Manter WhatsApp como canal de notificacoes, usando wpp-bridge como gateway HTTP local. Migrar o codigo do provider e do bridge de `general/services/` para dentro do repo `madruga.ai` junto com o runtime engine.

A interface `MessagingProvider` permanece abstrata com 3 metodos (send, ask_choice, alert). Isso torna a escolha de canal uma **2-way door**: trocar WhatsApp por Telegram ou ntfy.sh requer apenas implementar um novo provider, sem mudar daemon ou pipeline.

**Plano de degradacao (wpp-bridge offline):**
1. Health check periodico do bridge (HTTP GET /status a cada 60s)
2. Se bridge offline por >3 checks: daemon muda para modo log-only (structlog WARNING, continua processando auto gates, pausa human gates)
3. Notificacao de fallback via ntfy.sh (HTTP POST, zero deps, config opcional em config.yaml)
4. Operador reconecta wpp-bridge manualmente (QR code), daemon detecta e retoma WhatsApp

**Nota sobre estabilidade:** wpp-bridge depende de WhatsApp Web protocol, que e nao-oficial e pode quebrar com atualizacoes do WhatsApp. Esse risco e aceito conscientemente — o plano de degradacao garante que o daemon nao para.

## Alternativas Consideradas

### Alternativa A: WhatsApp via wpp-bridge (escolhida)
- **Pros:** operador ja usa WhatsApp como app principal (zero fricao), bridge ja implementado e testado, poll-based bidirectional (ask_choice com timeout), alertas com emoji/levels, integracao existente com daemon (MessagingClient/WhatsAppProvider), funciona em WSL2 (bridge local HTTP)
- **Cons:** wpp-bridge e servico separado que precisa rodar junto, WhatsApp Web session pode desconectar (reconexao manual), sem inline buttons (interacao via texto livre A/B/C), dependencia de WhatsApp Web protocol (pode quebrar)
- **Fit:** Alto — o operador ja esta no WhatsApp, e o bridge ja funciona.

### Alternativa B: Telegram Bot API (aiogram)
- **Pros:** inline keyboard buttons nativos para approve/reject, callbacks sem tunnel (outbound HTTPS only), setup rapido (~10 min), aiogram e excelente framework asyncio, mensagens com Markdown rico
- **Cons:** operador precisaria abrir outro app (Telegram), perda de contexto conversacional existente, mais um app para monitorar
- **Rejeitada porque:** o operador ja esta no WhatsApp. Mudar de canal introduz fricao sem ganho proporcional. Se wpp-bridge se tornar instavel, Telegram e o fallback natural.

### Alternativa C: ntfy.sh (push notifications)
- **Pros:** setup ultra-simples (HTTP POST), self-hostable, app mobile disponivel, zero dependencias Python (apenas aiohttp POST)
- **Cons:** comunicacao bidirecional limitada (sem reply nativo, workaround com pub/sub), plain text only (sem Markdown), single-maintainer project (sem SLA)
- **Rejeitada porque:** bidirectional e requisito critico (decisoes 1-way-door). ntfy.sh nao suporta nativamente.

### Alternativa D: Discord Webhooks / Bot
- **Pros:** embeds ricos, botoes com discord.py, free, boa comunidade
- **Cons:** requer persistent WebSocket gateway, interacoes expiram em 3s se nao acknowledged, operador precisaria abrir Discord
- **Rejeitada porque:** mesma fricao de "app extra" que Telegram, com complexidade adicional do gateway persistente.

## Consequencias

### Positivas
- Zero mudanca de habito para o operador — notificacoes chegam no WhatsApp
- Codigo ja existe e esta testado — migracao e copy + adapt, nao rewrite
- Interface abstrata (MessagingProvider) permite trocar provider sem mudar daemon
- Poll-based ask_choice funciona para decisoes 1-way-door com timeout configuravel

### Negativas
- wpp-bridge e um servico extra que precisa estar rodando (mais um processo para gerenciar)
- WhatsApp Web session pode desconectar e exigir reconexao manual (scan QR code)
- Sem inline buttons — interacao por texto (A/B/C) e menos elegante que Telegram

### Riscos
- WhatsApp Web protocol muda e wpp-bridge quebra → mitigacao: plano de degradacao (health check → log-only → ntfy.sh fallback). Se wpp-bridge se tornar permanentemente inviavel, migrar para Telegram Bot API (melhor alternativa tecnica)
- Session desconecta durante decisao critica → mitigacao: timeout com retry em ask_choice, human gates pausam ate reconexao (nao perdem estado)
- wpp-bridge roda headless Chromium (~200-400MB RAM) → mitigacao: aceitavel em WSL2 com 16GB+, monitorar se RAM se tornar constraint

## Referencias

- Implementacao existente: `general/services/madruga-ai/src/integrations/messaging/providers/whatsapp.py`
- Implementacao existente: `general/services/madruga-ai/src/integrations/messaging/client.py`
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [ntfy.sh](https://ntfy.sh/)
