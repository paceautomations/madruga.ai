---
id: "000"
title: "Epic 000: Foundation — construir base do produto"
status: done
priority: P0
date: 2026-05-04
---
# Epic 000: Foundation — construir base do produto

## Problem

Validar a tese de produto (gestão social de esportes de areia + ranking persistente + cobrança via WhatsApp) com base funcional real em produção. Sem isso, todas as decisões de roadmap dependeriam de hipótese sem dado de uso.

## Outcome (entregue retroativamente)

App multi-plataforma (iOS/Android/Web) operando em `paceautomations/resenhai-expo@09abf73` com:
- 15 tabelas Postgres + 22 views analíticas + 32 RLS policies + 48 funções/triggers + 40 migrations idempotentes
- Edge Function `whatsapp-webhook` (Deno) — sync de grupos com 3 handlers + audit em `whatsapp_events`
- 4 workflows n8n self-hosted (Magic Link OTP, Create User For Invite, WhatsappGroup_New/Prod) — `[transitório, sai com epic 002]`
- Mobile App em Expo SDK 54 + React Native 0.81 + Expo Router 6 (~58k LOC produção)
- 1898 testes (1695 Jest unit + 203 Playwright E2E web)
- Pipeline CI: `deploy-hostinger.yml` (web) + `deploy-supabase.yml` (migrations + functions)
- EAS Build/Submit/Update configurado (iOS + Android)
- PostHog SDK em produção com PII masking em `utils/logger.ts`
- Pricing tiers definidos em `docs/pricing.md` v2.0 (Jogador grátis, Dono R$ 49,90, Rei R$ 79,90, Enterprise) — implementação em epic-001

## Dependencies

- Depends on: nenhum (este é o épico raiz da plataforma).
- Blocks: 001, 002, 003, 004, 005, 006, 007 (todos os épicos subsequentes assumem este estado como ponto de partida).

## Notes

- Marca de tempo do estado base: HEAD `origin/develop = 09abf73` em 2026-03-24.
- Escopo deste épico é **declarativo/retroativo** — não há trabalho a executar.
- Para `madruga:reverse-reconcile`: todos os commits anteriores a `09abf73` em `origin/develop` podem ser auto-marcados como `epic_id=000-foundation` via `--assume-reconciled-before 09abf73`.
- ADRs gerados retroativamente (ADR-001 a ADR-011 acceptance + ADR-012 proposed) ratificam as decisões técnicas tomadas durante este épico.
