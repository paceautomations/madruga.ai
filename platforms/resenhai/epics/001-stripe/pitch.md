---
id: "001"
title: "Epic 001: Cobrança Stripe — destrava receita e classifica usuários em tier"
status: planned
priority: P1
date: 2026-05-04
---
# Epic 001: Cobrança Stripe — destrava receita e classifica usuários em tier

## Problem

ResenhAI hoje não tem receita ativa — código de payment ausente em `services/`, sem tabela `subscriptions`, sem fluxo de Checkout. Sem cobrança a tese de "Dono da Resenha paga para liderar" não é validada e a empresa não sustenta-se. Adicionalmente, **todos os usuários hoje são tratados implicitamente como Free** porque não existe classificação ativa em tier — features premium (badge 👑, Hall da Fama, AI ilimitado, ranking semanal) ficam não-distinguíveis até o épico entregar.

## Outcome esperado

- Stripe Billing configurado com 4 produtos: **Jogador** (Free), **Dono da Resenha** (R$ 49,90/mês, anual R$ 399,90), **Rei da Praia** (R$ 79,90/mês, anual R$ 639,90), **Enterprise** (preço custom).
- Cada usuário cadastrado tem **tier ativo classificado** (Free como default, mudando via Stripe webhook).
- Cupons: `FUTEVOLEIDEPRESSAO` (80% off, 3 meses, max 500 redempções) e template `INFLUENCER_*` (50% off, 2 meses).
- Stripe Checkout redirect-based para fluxo de assinatura.
- Edge Function `stripe-webhook` (Deno) com validação de signature + idempotency.
- Tabela `subscriptions` com `user_id`, `stripe_*`, `plan_name`, `status`, cupom ativo.
- Enforcement de limites: 1 grupo / 20 membros / 1 campeonato (Dono); 3 grupos / 50 membros / 10 campeonatos (Rei). Modal de upgrade quando bate teto.
- Features premium destravadas: badge 👑 no ranking público, Hall da Fama, AI ilimitado, histórico completo, ranking semanal.
- Suporte a PIX/Boleto BR (via Stripe BR — desde 2024).
- Métrica de sucesso: **primeiro pagamento real** + 100% dos usuários com `subscriptions.plan_name` setado em até 7d pós-deploy.

## Dependencies

- Depends on: **003-error-tracking** (Sentry deve estar live antes do Stripe ir para produção — necessário para detectar falhas em webhooks de cobrança).
- Blocks: nenhum funcionalmente, mas é meta de receita do roadmap (1.000 grupos pagantes em 2026).

## Notes

- ADR-008 ratifica a escolha do Stripe + alternativas rejeitadas.
- Pricing detalhado em `docs/pricing.md` v2.0 (resenhai-expo).
- Spec interna `006-stripe-pricing` (`CLAUDE.md:376-377` do resenhai-expo) — confirmar se é o mesmo escopo deste épico ou prequel.
- F5 do business-process já documenta o fluxo planejado.
