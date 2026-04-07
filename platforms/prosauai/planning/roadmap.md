---
title: "Roadmap"
updated: 2026-03-30
---
# ProsaUAI — Delivery Roadmap

> Sequenciamento de epics, milestones e definicao de MVP. Atualizado: 2026-03-30.

---

## Status

**Lifecycle:** design — nenhum codigo implementado ainda.
**L1 Pipeline:** 7/13 nodes completos (platform-new, vision, solution-overview, adr, blueprint, domain-model, epic-breakdown).
**L1 Pendente:** business-process, tech-research, codebase-map, containers, context-map, roadmap.

---

## MVP

**MVP Epics:** 001-channel-pipeline + 002-conversation-core
**MVP Criterion:** Agente recebe mensagem WhatsApp, responde com IA (nao echo), persiste em BD.
**Total MVP Appetite:** ~3 semanas (1w + 2w)

---

## Delivery Sequence

```mermaid
gantt
    title Roadmap ProsaUAI
    dateFormat YYYY-MM-DD
    section MVP
    001 Channel Pipeline    :a1, after start, 1w
    002 Conversation Core   :a2, after a1, 2w
    section Post-MVP
    003 Group Routing       :a3, after a2, 1w
    004 Agent Tools         :a4, after a2, 2w
    005 Handoff Engine      :a5, after a2, 2w
    006 Trigger Engine      :a6, after a5, 1w
    section Admin
    007 Admin Dashboard     :a7, after a4, 2w
    008 Admin Handoff Inbox :a8, after a5, 1w
```

---

## Epic Table

> **Convenção:** apenas o epic 001 tem pitch file criado. Demais são sugestões no roadmap — arquivos serão criados sob demanda quando o epic for iniciado via `/epic-context`.

| Ordem | Epic | Appetite | Deps | Risco | Milestone | Status |
|-------|------|----------|------|-------|-----------|--------|
| 1 | 001: Channel Pipeline | 1w | — | baixo | MVP | **proposed** (pitch criado) |
| 2 | 002: Conversation Core | 2w | 001 | medio | MVP | sugerido (sem arquivo) |
| 3 | 003: Group Routing | 1w | 002 | baixo | Post-MVP | sugerido |
| 4 | 004: Agent Tools | 2w | 002 | medio | Post-MVP | sugerido |
| 5 | 005: Handoff Engine | 2w | 002 | medio | Post-MVP | sugerido |
| 6 | 006: Trigger Engine | 1w | 005 | baixo | Post-MVP | sugerido |
| 7 | 007: Admin Dashboard | 2w | 004 | medio | Admin | sugerido |
| 8 | 008: Admin Handoff Inbox | 1w | 005 | baixo | Admin | sugerido |

### Epics Futuros (criados conforme necessidade)

| Epic | Descricao | Deps Provavel | Prioridade |
|------|-----------|---------------|------------|
| 009: Evals Offline | Score automatico por conversa (faithfulness, relevance, toxicity) | 002 | Next |
| 010: Evals Online | Guardrails pre/pos-LLM em tempo real | 002 | Next |
| 011: Data Flywheel | Ciclo semanal de melhoria com revisao humana | 009, 010 | Later |
| 012: Multi-Tenant Self-Service | Cadastro self-service, onboarding autonomo | 007 | Later |
| 013: RAG pgvector | Base de conhecimento com embeddings por tenant | 002 | Later |
| 014: Billing Stripe | Cobranca automatica com tiers e consumo medido | 012 | Later |
| 015: WhatsApp Flows | Formularios estruturados dentro do WhatsApp | 002 | Later |

---

## Dependencies

```mermaid
graph LR
  E001[001 Channel Pipeline] --> E002[002 Conversation Core]
  E002 --> E003[003 Group Routing]
  E002 --> E004[004 Agent Tools]
  E002 --> E005[005 Handoff Engine]
  E005 --> E006[006 Trigger Engine]
  E004 --> E007[007 Admin Dashboard]
  E005 --> E008[008 Admin Handoff Inbox]
```

---

## Milestones

| Milestone | Epics | Criterio de Sucesso | Estimativa |
|-----------|-------|---------------------|------------|
| **MVP** | 001, 002 | Agente responde mensagens WhatsApp com IA, persiste conversas, funciona em grupo | ~3 semanas |
| **Post-MVP** | 003-006 | Routing de grupo, tools, handoff humano, triggers proativos | ~6 semanas |
| **Admin** | 007-008 | Dashboard + fila de atendimento humano funcionais | ~3 semanas |

---

## Riscos do Roadmap

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Evolution API payload muda entre versoes | Medio | Media | Adapter pattern + testes com payloads reais |
| Custo LLM acima do esperado no MVP | Alto | Baixa | Bifrost com fallback Sonnet → Haiku |
| Complexidade de grupo subestimada | Medio | Media | Grupo separado em epic dedicado (003) |
| L1 incompleto bloqueia L2 | Alto | Media | Completar business-process e containers antes do epic 001 |

---

*Proximos passos: completar L1 pendente (business-process, containers, context-map) → iniciar epic 001 via `/epic-context prosauai 001`.*
