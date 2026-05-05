---
id: "002"
title: "Epic 002: Migração n8n → Supabase Edge Functions"
status: planned
priority: P1
date: 2026-05-04
---
# Epic 002: Migração n8n → Supabase Edge Functions

## Problem

O onboarding via Magic Link OTP — única porta de entrada de novos usuários — depende hoje de **n8n self-hosted no Easypanel**, infra externa frágil cujo downtime bloqueia signups inteiros do produto. Adicionalmente, ter 3 runtimes (cliente Expo + Edge Function + n8n VM) adiciona complexidade operacional sem ganho. ADR-006 já declarou Edge Functions como destino arquitetural — mas a migração não foi executada.

## Outcome esperado

- 4 workflows n8n migrados para Edge Functions Deno na Supabase:
  - `Magic Link OTP (com Test Mode)` → `supabase/functions/auth-magic-link-otp/`
  - `Create User For Invite` → `supabase/functions/auth-create-user-invite/`
  - `WhatsappGroup_New` → integrado ao `whatsapp-webhook` ou função dedicada
  - `WhatsappGroup_Prod` → integrado ao `whatsapp-webhook` ou função dedicada
- Cutover gradual via feature flag por workflow (1 a 1, com rollback redirect para n8n).
- Paridade de comportamento testada (test_payloads.json do n8n_backend reaproveitados).
- Infraestrutura Easypanel n8n **desligada** ao fim do épico.
- Métrica de sucesso: 0 downtime de onboarding em 30d pós-cutover; latência p95 do OTP ≤ infra atual.

## Dependencies

- Depends on: **003-error-tracking** (Sentry live é pré-requisito — migrar workflows críticos sem visibilidade de errors é negligente).
- Recomendação de sequencing: após 001-stripe ir para produção (para evitar mudar 2 áreas críticas simultaneamente).
- Blocks: deprecação formal do n8n + retirada do contrato Easypanel.

## Notes

- ADR-006 ratifica a escolha + alternativas rejeitadas (Inngest, Cloudflare Workers).
- §5 e §6 da business-process descrevem os fluxos atuais.
- Edge Function timeout de 150s — se algum workflow exceder, chunking necessário.
