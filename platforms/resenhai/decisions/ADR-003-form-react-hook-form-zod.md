---
title: "ADR-003: Form library — React Hook Form + Zod"
status: accepted
date: 2026-05-04
decision: >
  Adotar React Hook Form (uncontrolled) + Zod (schema/validação) para todos os formulários do app (cadastro, perfil, registrar jogo, criar campeonato, cobrança).
alternatives: >
  Formik + Yup; Final Form
rationale: >
  Performance superior em RN (uncontrolled, sem re-render por field), Zod já é fonte de verdade dos types/API (ADR-002), `zodResolver` pronto e downloads ~4x Formik.
---
# ADR-003: Form library — React Hook Form + Zod

## Status

Accepted — 2026-05-04 (retroativo)

## Context

ResenhAI tem múltiplos fluxos com formulários: cadastro de perfil (telefone, apelido, mão dominante, lado preferido na quadra), criação de grupo, criação de campeonato, registrar jogo (placar + duplas), assinatura (📋 ADR-008). Em RN, controlled forms re-renderizam todos os fields a cada keystroke — em formulários longos com lista de membros isso vira jank perceptível em devices low-end. Validação precisa ser compartilhada entre cliente (UX) e backend (Edge Function — ADR-006), o que exige schema único reaproveitável.

## Decision

Adotar **React Hook Form 7.66 + Zod 4.1**, com `zodResolver` para conectar schemas. Cada form declara um schema Zod em `lib/validation.ts` (codebase-context.md §13: 1212 LOC); o mesmo schema valida no cliente (input do usuário) e no Edge Function (input do request). Estilização via NativeWind (ADR-004).

## Alternatives Considered

### Alternative A: RHF + Zod (chosen)
- **Pros:** uncontrolled = re-render mínimo; `zodResolver` plug-and-play; schema único cliente+backend; downloads ~12M/sem.
- **Cons:** API menos didática para junior (registers, refs).
- **Fit:** Único `high` fit — Zod já é fonte de verdade do projeto (ADR-002).

### Alternative B: Formik + Yup
- **Pros:** API didática, docs maduras.
- **Cons:** controlled re-renderiza todos os fields a cada keystroke (perf RN ruim); manutenção desacelerou (autor original saiu).
- **Why rejected:** perf RN inferior + Yup duplica esforço de Zod (que já é usado em ADR-002).

### Alternative C: Final Form
- **Pros:** arquitetura subscription elegante.
- **Cons:** comunidade pequena (~500k dl/sem); devs novos no time não conhecem; manutenção lenta.
- **Why rejected:** ecossistema declinante.

## Consequences

### Positive
- Schema único (Zod) reduz drift cliente-backend.
- Forms grandes (registrar jogo com 4 jogadores + placar) renderizam suaves em Android low-end.
- DX consistente com ADR-002 (Zod everywhere).

### Negative
- Onboarding de junior dev tem curva inicial maior do que Formik.
- Erros de typing podem aparecer entre `register` ↔ `Controller` em campos custom (date pickers, image pickers) — exige conhecimento intermediário.

### Risks
- **Risco:** RHF mudar API (v8 quebrar v7). **Mitigação:** v7 estável desde 2022; codemods históricos.
- **Risco:** Zod v5 breaking. **Mitigação:** adoptar v4 atual; v5 só com refactor coordenado (impacta também ADR-002).

## References

- https://react-hook-form.com — docs oficiais
- https://zod.dev — Zod
- codebase-context.md §13 — `lib/validation.ts:1-1212`
