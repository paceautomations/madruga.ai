---
title: "ADR-002: State/data layer — TanStack Query + Zod"
status: accepted
date: 2026-05-04
decision: >
  Adotar TanStack Query (com persist) como camada de estado server e Zod como schema/validação compartilhada entre cliente e backend.
alternatives: >
  SWR; Apollo Client; Redux Toolkit Query
rationale: >
  REST + persist nativo + RN-first + Zod como single source of truth para types e validação justifica único `high` fit na matriz; downloads ~3x SWR e ecossistema (devtools, persisters) maduro.
---
# ADR-002: State/data layer — TanStack Query + Zod

## Status

Accepted — 2026-05-04 (retroativo)

## Context

ResenhAI consome backend REST do Supabase (PostgREST) — não há GraphQL. Precisa de cache local, deduplicação de requests (vários componentes em paralelo lendo mesma query), optimistic updates (registrar jogo deve atualizar ranking imediatamente), persistência offline (jogador na quadra abre app sem sinal e ainda vê ranking) e sincronização Realtime (canal `grupos` em codebase-context.md §8). Convenção mandatória do projeto: queryKey factory centralizado em `hooks/queryKeys.ts` (CLAUDE.md:71-83 do repo resenhai-expo) — todas as queries derivam suas chaves desse arquivo.

## Decision

Adotar **TanStack Query 5.90** com `@tanstack/query-async-storage-persister` para persist, integrado com **Zod 4.1** como schema/validação compartilhada (cliente, backend, tests). Schema da API gerado por `lib/validation.ts` (1212 LOC, codebase-context.md §13). Mutações com `optimisticUpdate`; invalidação por escopo via queryKey factory.

## Alternatives Considered

### Alternative A: TanStack Query + Zod (chosen)
- **Pros:** persist first-class; RN suportado; devtools; optimistic updates; queryKey discipline força contrato claro.
- **Cons:** queryKey factory exige discipline — esquecer 1 entry vira bug de cache stale.
- **Fit:** Único com fit `high` em REST + persist + RN.

### Alternative B: SWR
- **Pros:** API minimalista (~4kb), DX ótima Next.js.
- **Cons:** persist não é first-class (precisa middleware); comunidade mobile menor.
- **Why rejected:** persist offline é requisito core (jogador na quadra sem sinal).

### Alternative C: Apollo Client
- **Pros:** cache normalizado top-tier.
- **Cons:** requer GraphQL — backend é REST PostgREST (Supabase).
- **Why rejected:** custo de migrar para GraphQL é proibitivo e Supabase não oferece GraphQL nativo robusto.

### Alternative D: Redux Toolkit Query
- **Pros:** integra Redux, codegen OpenAPI possível.
- **Cons:** arrasta Redux store inteiro; persist via redux-persist é mais frágil.
- **Why rejected:** equipe de 2 devs prefere API ergonômica do TanStack Query a boilerplate Redux.

## Consequences

### Positive
- Zod como single source of truth: schema → types TS, validação cliente, validação Edge Function (ADR-006), parse de respostas.
- queryKey factory permite invalidação cirúrgica por escopo.
- DevTools acelera debug em sessões de pair programming.

### Negative
- queryKey factory cresce (~28 hooks declarados — codebase-context.md §5); manutenção exige rigor.
- Persist async storage tem limite ~6MB no iOS — precisamos selecionar quais queries persistem (não tudo).

### Risks
- **Risco:** Migração futura para GraphQL invalida ADR. **Mitigação:** sem plano de GraphQL no roadmap; PostgREST é suficiente.
- **Risco:** TanStack Query v6 breaking. **Mitigação:** acompanhar release notes; v5→v6 historicamente teve codemod.

## References

- https://tanstack.com/query — docs oficiais
- CLAUDE.md (resenhai-expo):59,71-83 — convenção de queryKey factory
- codebase-context.md §4 (versão) e §12 (decisão pré-existente)
