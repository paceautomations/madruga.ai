---
title: "ADR-005: Backend-as-a-Service consolidado — Supabase"
status: accepted
date: 2026-05-04
decision: >
  Adotar Supabase como BaaS único cobrindo Postgres, Auth, Storage, Realtime e Edge Functions. Decisão consolidada — 5 capabilities sob 1 ADR.
alternatives: >
  Firebase; AWS Amplify; (Pocketbase, Appwrite — descartados rapidamente)
rationale: >
  SQL nativo (40 migrations já escritas), RLS server-side (32 policies em produção), 22 views analíticas e Edge Functions Deno integradas tornam migração para outra plataforma uma reescrita massiva sem ROI.
---
# ADR-005: Backend-as-a-Service consolidado — Supabase

## Status

Accepted — 2026-05-04 (retroativo) — decisão consolidada

## Context

ResenhAI precisa de: (a) banco relacional para os 15 entidades + 22 views analíticas (codebase-context.md §7); (b) autenticação com OTP via WhatsApp (Magic Link); (c) storage para fotos de perfil e avatares de grupos (`images/*` bucket); (d) Realtime para sincronização do grupo (canal `grupos`); (e) compute serverless para webhook WhatsApp (Edge Function `whatsapp-webhook` em Deno). Equipe de 2 contribuidores não comporta operar 5 serviços separados (DB próprio + Auth0 + S3 + Pusher + Lambda) — precisa de plataforma consolidada.

Esta ADR é **consolidada**: ao invés de 5 ADRs separados (Postgres, Auth, Storage, Realtime, Edge), um ADR cobre a decisão de adotar Supabase como guarda-chuva. Os 5 são escolhas derivadas — SQL aberto (Postgres) e Deno (Edge) são portáveis se sair de Supabase; Auth/Storage/Realtime são acoplados.

## Decision

Adotar **Supabase** como BaaS:
- **Postgres 15** com 40 migrations idempotentes (`IF NOT EXISTS`, `DO $$`), 32 RLS policies e 48 funções/triggers.
- **Auth** nativo + OTP via WhatsApp (Magic Link gerado pelo workflow do ADR-006).
- **Storage** com bucket `images/*` (avatares, fotos de jogo).
- **Realtime** habilitado em `grupos` (canal único; eventos sync de membros).
- **Edge Functions Deno** para webhook WhatsApp.
- Tipos TS gerados via `supabase gen types --linked` apontando para staging (CLAUDE.md:336 do resenhai-expo).

## Alternatives Considered

### Alternative A: Supabase (chosen)
- **Pros:** Postgres puro (SQL standard, RLS portável); Edge Deno integrado (zero extra runtime); type-gen via CLI; Discord ativo, 78k+ stars.
- **Cons:** vendor lock-in em Auth e Storage; região BR ainda em São Paulo single-AZ; pricing pode escalar mal em alta carga.
- **Fit:** Único `high` fit — 40 migrations já escritas, RLS portável, Edge consolida runtime.

### Alternative B: Firebase
- **Pros:** Realtime maduro, escala global, Auth provider rico (Google, Apple, etc.).
- **Cons:** Firestore é NoSQL — sem JOINs, sem views, sem RLS server-side; reescrever 32 policies em regras Firestore é massivo; custo cresce não-linear com reads.
- **Why rejected:** schema relacional (15 tabelas + FKs + 22 views) exige SQL — Firestore obriga denormalização agressiva.

### Alternative C: AWS Amplify
- **Pros:** integração full AWS (Cognito enterprise, RDS, S3); ecossistema maduro.
- **Cons:** Gen2 mudou DX; multi-serviço aumenta MTTR; configuração inicial muito mais pesada que Supabase.
- **Why rejected:** complexidade operacional incompatível com equipe de 2.

### Alternative D: Pocketbase / Appwrite (descartados rapidamente)
- **Why rejected:** self-host adiciona infra/devops desnecessário; comunidade significativamente menor; sem service-managed BR equivalente.

## Consequences

### Positive
- Um único dashboard cobre DB, Auth, Storage, Realtime, Edge — reduz contexto operacional.
- RLS no DB protege dados independente de qual cliente acessa.
- Migrations idempotentes (CLAUDE.md:362) permitem rebuild de schema reproducível.
- Edge Functions Deno reaproveitam Zod schemas do cliente (ADR-002, ADR-003).

### Negative
- **God-DB-layer**: `services/supabase/database.ts` (1598 LOC, codebase-context.md §13) cresceu como camada única para todos os CRUDs — débito a quebrar por bounded context (épico-005-database-decomposition).
- **Tipos acoplados a staging**: `types/database.ts` é regenerado do staging linkado (CLAUDE.md:336); divergências staging↔prod (2 dumps separados) podem causar TS pass + runtime fail.
- **Single-AZ São Paulo**: incidentes de região afetam o produto inteiro; sem multi-region em pricing Pro.
- **Lock-in Auth/Storage**: sair do Supabase exige migrar usuários (Auth) e re-uploadar avatares (Storage).

### Risks
- **Risco:** latência p99 BR > 300ms sustentada. **Mitigação:** monitorar via Sentry (ADR-012) + PostHog; avaliar multi-region quando GA Supabase.
- **Risco:** Supabase encerrar plano Pro ou dobrar pricing. **Mitigação:** Postgres + RLS portáveis; plano de saída = self-host Postgres + Hasura/PostgREST + Auth0.
- **Risco:** divergência staging↔prod em schema. **Mitigação:** comparar `staging_schema.sql` vs `prod_schema.sql` antes de épicos schema-touching (CLAUDE.md:336).

## References

- https://supabase.com/customers — empresas em produção
- CLAUDE.md (resenhai-expo):362-366 — migrations idempotentes
- codebase-context.md §7 (15 tabelas, 22 views, 40 migrations) e §14 (débitos)
