---
title: "ADR-006: Workflow orchestration — Supabase Edge Functions (n8n é transitório)"
status: accepted
date: 2026-05-04
decision: >
  Adotar Supabase Edge Functions Deno como runtime único para todos os workflows de orquestração (Magic Link OTP, Create User Invite, WhatsApp group sync). n8n self-hosted Easypanel é estado transitório e será deprecated pelo épico-002-edge-migration.
alternatives: >
  n8n self-hosted (legado); Inngest; Cloudflare Workers
rationale: >
  Consolida runtime com o BaaS (ADR-005), elimina VM externa Easypanel, simplifica observabilidade e remove dependência de manutenção de contêiner adicional para 4 workflows stateless de baixa concorrência.
---
# ADR-006: Workflow orchestration — Supabase Edge Functions (n8n é transitório)

## Status

Accepted — 2026-05-04 — escolha forward-looking

> Esta ADR documenta a **decisão estratégica** atual. O estado em produção hoje (HEAD `09abf73`) ainda tem 4 workflows rodando em n8n self-hosted (Easypanel); são considerados **legados/transitórios**. Eles serão migrados para Edge Functions pelo **épico-002-edge-migration**. Em ADRs futuros, qualquer ADR que tenha sido emitido para "n8n como infra de workflow" seria marcado como **Superseded by ADR-006** — mas como o ADR retroativo de n8n nunca foi formalizado, esta ADR já nasce como decisão atual.

## Context

ResenhAI tem 4 workflows hoje: (a) Magic Link OTP — gera link no Supabase, envia via Evolution API; (b) Create User For Invite — cria auth user via Service Key admin; (c) WhatsappGroup_New e WhatsappGroup_Prod — sync de estado de grupo WhatsApp. Todos são stateless, request/response, baixa concorrência (poucas chamadas/min em produção atual). Hoje rodam em n8n self-hosted no Easypanel — adiciona uma 3ª runtime (além do Edge e do client) e uma VM extra a manter, com pontos de falha (qualquer downtime do n8n bloqueia onboarding inteiro — Magic Link OTP é a única porta de entrada).

A consolidação no Supabase Edge Functions Deno alinha 100% com o BaaS (ADR-005): mesma região, mesmo dashboard, mesmas secrets, mesmo CLI, RLS herdado.

## Decision

Adotar **Supabase Edge Functions** (Deno runtime, `supabase functions deploy`) como runtime único para todos os workflows. Migrar os 4 workflows atuais de n8n para Edge Functions no épico-002-edge-migration (paralelo ou após Stripe). Ao final da migração, **desligar a instância Easypanel n8n**. Cron jobs que precisarem rodar agendados usarão `pg_cron` + Edge Function trigger (suporte nativo Supabase desde 2025).

## Alternatives Considered

### Alternative A: Supabase Edge Functions (chosen)
- **Pros:** zero infra extra; mesmo deploy/secrets/CLI do BaaS; JWT/RLS herdados nativamente; cron via pg_cron; cold start ~50-200ms ok para use case; logs unificados no dashboard Supabase.
- **Cons:** timeout 150s máx (não cobre durable execution longa); ecossistema Deno ainda menor que Node.
- **Fit:** Único `high` fit dado consolidação com ADR-005.

### Alternative B: n8n self-hosted (legado, rejeitado para o futuro)
- **Pros:** debugging visual; 400+ integrations prontas; comunidade grande.
- **Cons:** VM extra (custo + ops); versionamento Git nativo é fraco (workflows como JSON ad-hoc); escalabilidade horizontal complexa; falha = onboarding bloqueado.
- **Why rejected (forward-looking):** mantém fragmentação de runtime e ponto de falha crítico no onboarding.

### Alternative C: Inngest
- **Pros:** durable execution out-of-the-box; retries automáticos; step functions; SDK TS.
- **Cons:** vendor extra (4º serviço a pagar); custo cresce com volume; overkill para 4 workflows simples.
- **Why rejected:** durable execution não é necessária no escopo atual; custo extra sem ROI.

### Alternative D: Cloudflare Workers
- **Pros:** edge global, frio rápido.
- **Cons:** mais um vendor; sem integração nativa com Supabase auth/RLS; complexidade de gerenciar 2 plataformas para o mesmo product.
- **Why rejected:** distancia do BaaS principal sem benefício claro.

## Consequences

### Positive
- 1 runtime, 1 deploy, 1 dashboard — operação muito mais simples.
- Onboarding (Magic Link OTP) deixa de depender de VM Easypanel — uptime alinhado ao próprio Supabase.
- Edge Functions reaproveitam types Zod do cliente (ADR-002).

### Negative
- **Migração não-trivial**: 4 workflows em JSON do n8n (incluindo WhatsappGroup_Prod com 60KB de lógica — codebase-context.md §5) precisam ser reescritos em TS Deno; risco de regressão durante migração exige paridade testada (épico-002).
- **Limite 150s timeout**: workflows longos (sync de grupo grande, batch operations) podem exceder; mitigar com chunking ou pg_cron.
- **Lock-in adicional em Supabase**: sair do Supabase agora também exige reescrever os workflows.

### Risks
- **Risco:** durante a janela de migração, ambos n8n e Edge coexistem — duplicidade pode gerar inconsistência de estado. **Mitigação:** épico-002 usa flag de feature por workflow (1 a 1 cutover); rollback é redirect do trigger para n8n.
- **Risco:** workflow precisar de durable execution > 150s. **Mitigação:** chunking + state em DB; reavaliar Inngest se padrão emergir.

## References

- https://supabase.com/edge-functions — docs
- https://github.com/EvolutionAPI/evolution-api — gateway
- codebase-context.md §5 (`n8n_backend/`) e §14 (débito)
- business-process.md §5, §6 — descrição dos workflows hoje em produção
