---
title: "ADR-018: Telegram Bot API (aiogram) como Canal de Notificacoes"
status: accepted
date: 2026-03-31
supersedes: ADR-015
decision: Usar Telegram Bot API via aiogram como canal de notificacoes do easter,
  substituindo WhatsApp via wpp-bridge. Long-polling (outbound HTTPS only).
alternatives: WhatsApp via wpp-bridge (ADR-015), ntfy.sh (push notifications), Discord
  Webhooks/Bot
rationale: Inline keyboard buttons nativos para human gates, zero processo extra (sem
  bridge, sem Chromium), framework asyncio-native
---
# ADR-018: Telegram Bot API (aiogram) como Canal de Notificacoes

## Status

Accepted — 2026-03-31. Supersedes [ADR-015](ADR-015-whatsapp-wpp-bridge.md).

## Contexto

O easter Madruga AI precisa notificar o operador sobre status de epics, decisoes pendentes (1-way-door), e erros criticos. O canal deve suportar comunicacao bidirecional: o easter envia, o operador responde para aprovar/rejeitar decisoes.

A decisao anterior (ADR-015) escolheu WhatsApp via wpp-bridge como canal. Na pratica, wpp-bridge apresenta problemas significativos:
- Depende de protocolo WhatsApp Web **nao-oficial** — pode quebrar com atualizacoes do WhatsApp
- Exige headless Chromium (~200-400MB RAM) rodando como processo separado
- Session desconecta periodicamente, exigindo reconexao manual via QR code
- Sem inline buttons — interacao por texto livre (A/B/C) e fragil e menos intuitiva
- A migracao do codigo de `general/services/` para `madruga.ai` adicionaria complexidade desnecessaria

Alem disso, a decisao de **nao migrar** o wpp-bridge de `general` para `madruga.ai` elimina a premissa original de "codigo ja existe e esta testado".

## Decisao

Usar **Telegram Bot API via aiogram** como canal de notificacoes do easter, substituindo WhatsApp via wpp-bridge.

A interface `MessagingProvider` permanece abstrata com 4 metodos (`send`, `ask_choice`, `alert`, `edit_message`). A implementacao muda de `WhatsAppBridge` para `TelegramAdapter`. Isso mantem a escolha de canal como **2-way door** — trocar provider requer apenas nova implementacao, sem mudar easter ou pipeline.

**Modo de operacao: long-polling** (nao webhook). O bot usa `aiogram`'s built-in polling loop para receber updates. Isso evita necessidade de porta inbound, tunnel, ou certificado HTTPS — o easter faz apenas requests HTTPS outbound para `api.telegram.org`.

**Plano de degradacao (Telegram Bot API unreachable):**
1. Health check periodico (HTTPS GET `getMe` a cada 60s)
2. Se unreachable por >3 checks: easter muda para modo log-only (structlog WARNING, continua processando auto gates, pausa human gates)
3. Notificacao de fallback via ntfy.sh (HTTP POST, zero deps, config opcional em config.yaml)
4. Quando Telegram volta, easter detecta e retoma notificacoes

## Alternativas Consideradas

### Alternativa A: Telegram Bot API via aiogram (escolhida)
- **Pros:** inline keyboard buttons nativos para approve/reject (UX superior para human gates), callbacks sem tunnel (outbound HTTPS only), setup rapido (~10 min com @BotFather), aiogram e excelente framework asyncio (fit perfeito com easter asyncio), mensagens com Markdown rico, zero processo extra (sem bridge, sem Chromium)
- **Cons:** operador precisa instalar Telegram (app extra), perda de contexto conversacional existente no WhatsApp
- **Fit:** Alto — infra mais simples, UX melhor para human gates, asyncio-native.

### Alternativa B: WhatsApp via wpp-bridge (anterior — rejeitada)
- **Pros:** operador ja usa WhatsApp como app principal (zero fricao de adocao)
- **Cons:** wpp-bridge depende de protocolo nao-oficial (instavel), headless Chromium ~200-400MB RAM, session desconecta exigindo QR code manual, sem inline buttons (interacao por texto A/B/C), processo extra para gerenciar
- **Rejeitada porque:** instabilidade do bridge, overhead de RAM, complexidade operacional. A decisao de nao migrar o codigo de `general` elimina a vantagem de "codigo ja existe".

### Alternativa C: ntfy.sh (push notifications)
- **Pros:** setup ultra-simples (HTTP POST), self-hostable, app mobile disponivel, zero dependencias Python
- **Cons:** comunicacao bidirecional limitada (sem reply nativo), plain text only (sem Markdown), single-maintainer project
- **Rejeitada porque:** bidirectional e requisito critico (decisoes 1-way-door). ntfy.sh nao suporta nativamente. Mantido como **fallback** para degradacao.

### Alternativa D: Discord Webhooks / Bot
- **Pros:** embeds ricos, botoes com discord.py, free, boa comunidade
- **Cons:** requer persistent WebSocket gateway, interacoes expiram em 3s se nao acknowledged, operador precisaria abrir Discord
- **Rejeitada porque:** complexidade do gateway persistente, timeout curto de interacoes.

## Consequencias

### Positivas
- Inline keyboard buttons para human gates — UX muito melhor que texto A/B/C
- Zero processo extra — sem bridge, sem Chromium, sem QR code
- Outbound HTTPS only — sem porta inbound, sem tunnel, sem exposicao de rede
- Framework asyncio-native (aiogram) — fit perfeito com easter asyncio existente
- Callback queries com data payload — permite approve/reject com um toque
- Markdown rico nas mensagens (bold, code, links)
- Setup em ~10 min via @BotFather

### Negativas
- Operador precisa instalar Telegram (mais um app)
- Perde contexto conversacional que existia no WhatsApp
- Dependencia de terceiro (Telegram) — mitigado: long-polling e outbound only, sem vendor lock-in na interface

### Riscos
- Telegram Bot API muda breaking changes → mitigacao: aiogram acompanha upstream, library madura com releases frequentes
- Telegram bloqueia bot por spam → mitigacao: volume esperado < 20 msgs/dia, bem abaixo dos limites (30 msgs/s)
- Rate limit em picos (muitos human gates simultaneos) → mitigacao: aiogram tem retry built-in, volume e baixo

## Referencias

- Supersedes: [ADR-015 — WhatsApp via wpp-bridge](ADR-015-whatsapp-wpp-bridge.md)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [aiogram docs](https://docs.aiogram.dev/)
- [@BotFather](https://t.me/botfather)
- [ntfy.sh](https://ntfy.sh/) (fallback)
