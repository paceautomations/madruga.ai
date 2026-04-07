---
title: 'ADR-010: Next.js 15 + shadcn/ui para admin panel'
status: Accepted
decision: Next.js 15 + shadcn/ui
alternatives: Retool / Appsmith (low-code), React + Vite + Material UI
rationale: Handoff inbox com real-time via Socket.io — operador ve mensagens instantaneamente
---
# ADR-010: Next.js 15 + shadcn/ui para admin panel
**Status:** Accepted | **Data:** 2026-03-23

## Contexto
Precisamos de um painel administrativo para gerenciar agentes, monitorar conversas e operar o handoff inbox (transferencia de conversa de agente para humano em tempo real). O frontend precisa de suporte a real-time (Socket.io) para o handoff.

## Decisao
We will usar Next.js 15 com shadcn/ui para o admin panel, com Socket.io para real-time no handoff inbox.

Motivos:
- Next.js 15: App Router + Server Components reduzem bundle size e simplificam data fetching
- shadcn/ui: componentes copy-paste (nao lib), customizaveis, acessiveis, Tailwind-based
- Socket.io: bidirecional, reconexao automatica, necessario para handoff inbox em tempo real
- Stack frontend moderna e bem documentada — facil de contratar/onboardar

## Alternativas consideradas

### Retool / Appsmith (low-code)
- Pros: Speed-to-market altissimo, drag-and-drop, integracao com DBs direto
- Cons: Limitado para UX custom (handoff inbox), pricing escala mal, lock-in, dificil versionar

### React + Vite + Material UI
- Pros: Mais leve que Next.js, MUI maduro e completo
- Cons: Sem SSR (SEO irrelevante mas cache de dados util), MUI pesado e opinionated demais, mais boilerplate para routing

## Consequencias
- [+] Handoff inbox com real-time via Socket.io — operador ve mensagens instantaneamente
- [+] shadcn/ui permite UI polida sem dependencia de lib pesada
- [+] Server Components reduzem JS enviado ao browser
- [-] Next.js adiciona complexidade de deploy (Node.js server ou Vercel)
- [-] Socket.io requer server-side handler (pode rodar no mesmo Next.js API route ou servico separado)
- [-] Time precisa dominar React + Next.js App Router (curva de aprendizado moderada)

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
