---
title: "Test Journeys"
updated: 2026-05-04
---
# Jornadas de Teste — resenhai

> Jornadas de usuário para validação end-to-end. Atualizado por `speckit.tasks` e `madruga:reconcile`.
> Marcar `required: true` para jornadas que bloqueiam o QA quando falham.

---

## J-001 — Onboarding via convite WhatsApp

Valida o caminho crítico do produto (Flow F1 — business-process.md): Dono cria grupo, gera convite, novo Jogador clica deep link, recebe Magic Link OTP via WhatsApp, completa cadastro e aparece na lista de membros.

```yaml
id: J-001
title: "Onboarding via convite WhatsApp"
required: true
steps:
  - type: browser
    action: "navigate http://localhost:8081"
    screenshot: true
  - type: browser
    action: "assert_contains ResenhAI"
  # Demais steps a serem adicionados pelo épico que tocar onboarding (épico-002-edge-migration ou épico-001-stripe).
  # Cobrir: tela de login, fluxo de Magic Link OTP em test mode (n8n / Edge), redirect de deep link e validação final.
```

---

## J-002 — Resenha do dia a dia (placeholder)

Valida o ritual semanal — confirmar presença, conversar no zap, ver ranking público postado pelo app (Flow F2).

```yaml
id: J-002
title: "Resenha do dia a dia"
required: false
steps:
  # Placeholder — adicionar após épico que toque o ranking público no WhatsApp.
```

---

## J-003 — Registrar jogo + atualização de ranking (placeholder)

Loop core do produto (Flow F3) — registrar partida, ver stats e ranking atualizarem ao vivo via Realtime.

```yaml
id: J-003
title: "Registrar jogo + atualização de ranking"
required: true
steps:
  # Placeholder — depende de credenciais staging (SEED_TEST_DATA + STAGING_SUPABASE_*).
```

---

## J-004 — Cobrança (Stripe) 📋

Validação do fluxo de upgrade/checkout (Flow F5). Bloqueado pelo épico-001-stripe.

```yaml
id: J-004
title: "Cobrança via Stripe"
required: false
steps:
  # Placeholder — a definir no épico-001-stripe (checkout, webhook, ativação de tier).
```

<!-- Adicione mais jornadas (J-005, J-006 ...) conforme novos fluxos forem priorizados. -->
