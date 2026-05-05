---
title: "ADR-008: Payment Processor — Stripe (planejado, épico-001-stripe)"
status: proposed
date: 2026-05-04
decision: >
  Adotar Stripe como payment processor para subscriptions (Free/Dono/Rei/Enterprise), cupons, pro-rata upgrades e webhooks idempotentes. Cobre cartão + PIX + Boleto no mercado BR.
alternatives: >
  Pagar.me; Iugu; Asaas; MercadoPago
rationale: >
  Stripe Billing entrega subscriptions + cupons + pro-rata out-of-the-box, suporte a PIX/Boleto BR desde 2024, webhooks idempotentes nativos e DX líder. Concorrentes BR exigem reimplementar lógica de Billing.
---
# ADR-008: Payment Processor — Stripe (planejado)

## Status

Proposed — 2026-05-04 — depende do épico-001-stripe para entrega

## Context

ResenhAI hoje **não tem cobrança ativa** — código de payment ausente em `services/` (codebase-context.md §8 e §14). Pricing definido em `docs/pricing.md` (resenhai-expo, lido na Fase 1.2): tier Jogador grátis, Dono da Resenha R$ 49,90/mês, Rei da Praia R$ 79,90/mês, Enterprise (Arena) a negociar. Necessidades técnicas: subscriptions com tier upgrades pro-rata, cupons (FUTEVOLEIDEPRESSAO 80% por 3 meses na fase de lançamento; 50% por 2 meses em pós-lançamento), webhooks idempotentes para ativação/desativação de tier, suporte a PIX/Boleto/cartão (mercado BR), fluxo de upgrade quando grupo bate teto de membros.

Sem cobrança, não há receita — épico-001-stripe é a prioridade #1 do roadmap (vision §3 batalha #1).

## Decision

Adotar **Stripe** como payment processor:
- **Stripe Billing** para subscriptions (planos Dono e Rei, mensal e anual com 33% desconto).
- **Stripe Checkout** redirect-based para o fluxo de assinatura.
- **PIX/Boleto** via Stripe BR (suporte oficial desde 2024).
- **Webhooks** entregues à Edge Function dedicada `stripe-webhook` (a criar) com validação de signature + idempotency via `stripe_event_id`.
- **Tabela `subscriptions`** no Supabase (a criar no épico) relacionando `user_id`, `stripe_customer_id`, `stripe_subscription_id`, `plan_name`, `status`, cupom ativo.
- **Cupons** definidos no Stripe: `FUTEVOLEIDEPRESSAO` (80% off, 3 meses, max 500 redeems), `INFLUENCER_*` (50% off, 2 meses, sem limite).

## Alternatives Considered

### Alternative A: Stripe (chosen)
- **Pros:** Stripe Billing nativo (subs, coupons, pro-rata, dunning); webhooks idempotentes; dashboard, SDKs e docs líderes; PIX/Boleto BR desde 2024.
- **Cons:** custo PIX 1,49% (vs concorrentes BR mais baratos); dispute handling em USD com conversão; suporte BR é remoto.
- **Fit:** Único `high` fit que entrega Billing pronto + PIX BR.

### Alternative B: Pagar.me
- **Pros:** PIX recorrente nativo; antifraude Stone; BR-first com docs PT.
- **Cons:** Billing menos rico que Stripe; pro-rata e cupom complexos exigem lógica própria; integração mais artesanal.
- **Why rejected:** custo de implementar Billing engine internamente é alto; risco de bugs em pro-rata no tier upgrade.

### Alternative C: Iugu
- **Pros:** SaaS BR, foco em SaaS/SMB.
- **Cons:** Billing OK mas com menos features que Stripe (cupons recorrentes, pro-rata edge cases); ecossistema menor; documentação inferior.
- **Why rejected:** sem ganho real vs Stripe.

### Alternative D: Asaas
- **Pros:** custo mais baixo no BR (1,99% cartão; PIX R$1,99 fixo); ideal SMB.
- **Cons:** sem subscription engine completo (pro-rata/coupons via lógica própria); split nativo mas sem dispute handling robusto.
- **Why rejected:** mesmo problema do Pagar.me — exige reescrever Billing.

### Alternative E: MercadoPago
- **Pros:** dominante em LatAm; suporte completo a meios de pagamento BR.
- **Cons:** Billing limitado; UX de Checkout dated; webhooks menos robustos.
- **Why rejected:** Stripe oferece melhor DX para subscription SaaS.

## Consequences

### Positive
- Stripe Billing acelera entrega do épico — não reinventamos pro-rata, cupons, dunning.
- PIX BR cobre o canal preferido do TAM (sem fricção de cartão).
- DX excelente reduz curva para 2 devs.

### Negative
- **Custo PIX 1,49%** vs concorrentes BR (1,99% Asaas, 0,99% Pagar.me) — em volume alto, pode pesar; precisa monitorar margem por tier.
- **Dispute em USD**: contestações de cartão tramitam pelo time global Stripe (não há ouvidoria PT-BR oficial).
- **Lock-in em Stripe**: schema `subscriptions.stripe_*` columns acopla ao vendor; trocar exige migração de dados.

### Risks
- **Risco:** custo PIX inviabilizar margem do tier R$ 49,90 (alvo margem bruta 85% — vision §6). **Mitigação:** monitor margem mensalmente; gatilho < 70% → reavaliar Pagar.me ou modelo híbrido.
- **Risco:** webhook duplicado causa double-charge ou tier duplo. **Mitigação:** idempotency via `stripe_event_id` único na tabela `subscriptions_events` (a criar).
- **Risco:** mudança regulatória BR de PIX (taxa, KYC). **Mitigação:** Stripe é regulado como PSP no BR; baixo risco regulatório.

## References

- https://stripe.com/customers — empresas em produção
- https://stripe.com/docs/billing — Stripe Billing
- https://stripe.com/br/payments/pix — PIX no Stripe (BR)
- docs/pricing.md (resenhai-expo) — tiers e cupons definidos
- docs/stripe-recomendacao.md (resenhai-expo, 14.5KB) — análise prévia interna `[VALIDAR — confirmar alinhamento]`
