---
title: 'ADR-005: Evolution API Cloud mode como primeiro channel adapter (estrategia
  omnichannel)'
status: Accepted
decision: Evolution API Cloud mode
alternatives: Baileys (via Evolution API modo Baileys), WhatsApp Business API direta
  (sem Evolution), Twilio WhatsApp
rationale: Zero risco de ban — API oficial com aprovacao do Meta
---
# ADR-005: Evolution API Cloud mode como primeiro channel adapter (estrategia omnichannel)
**Status:** Accepted | **Data:** 2026-03-23 | **Atualizado:** 2026-03-25

## Contexto
ProsaUAI e uma plataforma **omnichannel** por design — WhatsApp e o primeiro canal implementado, mas a arquitetura suporta Telegram, Facebook Messenger, Blip, Zendesk e outros via channel adapter pattern. Para o primeiro canal (WhatsApp), as opcoes sao usar Baileys (lib open-source que simula WhatsApp Web) ou Evolution API em modo Cloud (wrapper sobre a API oficial do WhatsApp Business).

## Decisao
We will usar Evolution API em modo Cloud (WhatsApp Business API) como **primeiro channel adapter**, com adapter pattern que permite adicionar novos canais sem mudar o core do sistema.

### Estrategia omnichannel
```
                    ┌─────────────────┐
                    │   Agent Engine   │
                    │   (pydantic-ai)  │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │  Channel Router  │
                    │  (adapter layer) │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
   ┌────────┴───────┐ ┌─────┴──────┐ ┌───────┴───────┐
   │  WhatsApp       │ │  Telegram   │ │  Facebook     │
   │  (Evolution API)│ │  (futuro)   │ │  (futuro)     │
   │  ✅ Fase 1      │ │             │ │               │
   └────────────────┘ └────────────┘ └───────────────┘
```

- Cada canal implementa a mesma interface (receber msg, enviar msg, enviar media, enviar template)
- Agent Engine nao sabe qual canal esta sendo usado — recebe/envia mensagens normalizadas
- Novo canal = novo adapter, zero mudanca no core
- Config por tenant define quais canais estao habilitados (ADR-006)

### WhatsApp especificamente (primeiro adapter)
Motivos para Evolution API Cloud mode:
- Baileys tem risco real de ban — issues #2228 e #2298 documentam banimentos de numeros
- Modo Cloud usa API oficial do Meta — sem risco de ban por TOS violation
- Evolution API abstrai complexidade da API oficial com interface REST simples
- Suporte a webhooks, media, templates e status nativamente

## Alternativas consideradas

### Baileys (via Evolution API modo Baileys)
- Pros: Gratuito (sem custo por mensagem), funciona sem aprovacao do Meta, setup rapido para dev
- Cons: Risco alto de ban (issues #2228, #2298), sessao instavel (reconexoes frequentes), sem suporte oficial do WhatsApp, features podem quebrar sem aviso

### WhatsApp Business API direta (sem Evolution)
- Pros: Controle total, sem intermediario
- Cons: API complexa (webhooks, token refresh, template approval), mais codigo para manter, sem valor agregado sobre Evolution

### Twilio WhatsApp (BSP gerenciado)
- Pros: BSP confiavel, ISV Tech Provider Program (multi-WABA), SDKs maduros, suporte enterprise, SLA garantido
- Cons: Markup sobre precos Meta (custo por mensagem maior), sem suporte a grupos WhatsApp, vendor lock-in no canal, menos controle sobre webhooks e payloads

## Consequencias
- [+] Zero risco de ban — API oficial com aprovacao do Meta
- [+] Sessao estavel — sem reconexoes ou QR code
- [+] Suporte a message templates aprovados (marketing, transacional)
- [+] Adapter pattern permite adicionar Telegram, Facebook, Blip, Zendesk sem mudar agent engine
- [+] Tenant pode habilitar multiplos canais simultaneamente via config (ADR-006)
- [-] Custo por mensagem (conversation-based pricing do Meta)
- [-] Requer aprovacao de templates pelo Meta (pode levar 24-48h)
- [-] Dependencia do servico Evolution API (self-hosted ou cloud)
- [-] Cada novo canal requer implementacao de adapter (estimativa: 2-5 dias por canal)

## Hardening obrigatorio (Evolution API v2.x)
Evolution API v2.x tem instabilidades documentadas em producao:
- QR Code nao gera em v2.1.1 e v2.2.3 (loop infinito de reconnection)
- Sync perdido apos reboot (instancia para de receber mensagens)
- sendStatus timeout em v2.3.7
- Redis errors inundando logs em v2.1.1

### Regras
1. **Fixar versao especifica** — NUNCA usar tag `latest` em producao. Testar upgrades em staging
2. **Health checks agressivos**: endpoint de status a cada 30s + auto-restart se unhealthy por >2min
3. **Meta Cloud API como fallback**: tenants enterprise que podem fazer business verification devem ter opcao de usar API oficial direta (sem Evolution)
4. **Webhook HMAC-SHA256**: validar signature de TODA webhook recebida — rejeitar requests sem signature valida (ADR-017)

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
