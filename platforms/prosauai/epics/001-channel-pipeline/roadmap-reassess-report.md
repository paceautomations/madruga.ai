---
title: "Roadmap Reassessment — Post Epic 001"
date: 2026-04-09
epic: "001-channel-pipeline"
type: roadmap-reassess
trigger: "L2 cycle complete for epic 001"
---

# Roadmap Reassessment — Post Epic 001 (Channel Pipeline)

**Data:** 2026-04-09 | **Branch:** epic/prosauai/001-channel-pipeline  
**Trigger:** Epic 001 concluido com sucesso (52/52 tasks, 122 testes, judge 92%, QA 97%)

---

## Resumo Executivo

Epic 001 (Channel Pipeline) foi entregue com sucesso, estabelecendo a fundacao completa para todos os epicos subsequentes. A implementacao validou premissas arquiteturais (adapter pattern, Redis debounce atomico, HMAC security) e nao revelou novos riscos significativos. O roadmap permanece valido em sua estrutura — ajustes necessarios sao de **status** e **estimativas**, nao de sequenciamento.

---

## 1. O Que Foi Entregue

| Item | Planejado | Entregue | Delta |
|------|-----------|----------|-------|
| Tasks | 52 | 52/52 (100%) | — |
| Testes | 14+ | 122 | +8.7x do minimo |
| Judge Score | — | 92% (PASS) | — |
| QA Pass Rate | — | 97% | — |
| BLOCKERs encontrados | 0 | 1 (corrigido) | Debounce fallback — fix aplicado |
| WARNINGs encontrados | 0 | 8 (7 corrigidos) | PII, reconnect, provider compartilhado |
| Drift Score | — | 60% (6/10 docs current) | 4 docs desatualizados (status updates) |
| Estimativa tempo | 1 semana | ~1 dia (pipeline L2 automatizado) | Execucao muito mais rapida que estimado |

### Componentes Implementados

- **Webhook FastAPI** com validacao HMAC-SHA256 (ADR-017 compliance)
- **Smart Router** com 6 rotas (SUPPORT, GROUP_RESPOND, GROUP_SAVE_ONLY, GROUP_EVENT, HANDOFF_ATIVO stub, IGNORE)
- **Redis Debounce** com Lua script atomico, dual-key pattern, keyspace notifications, jitter anti-avalanche
- **Evolution API Adapter** (MessagingProvider ABC + EvolutionProvider)
- **Echo Response** (fundacao para LLM no epic 002)
- **Docker Compose** (api + redis com healthchecks)
- **Logging estruturado** (structlog, phone hash SHA-256, zero PII)

---

## 2. Validacao de Premissas do Roadmap

| Premissa Original | Resultado | Impacto no Roadmap |
|-------------------|-----------|-------------------|
| "Evolution API payload instavel entre versoes" | **Mitigado** — adapter pattern + 122 testes com fixtures reais cobrindo 10+ tipos de payload | Risco rebaixado de medio para baixo |
| "Redis adequado para debounce atomico" | **Confirmado** — Lua script atomico funcional, keyspace notifications confiaveis, fallback implementado | Nenhum — Redis continua como escolha correta |
| "HMAC-SHA256 viavel desde dia 1" | **Confirmado** — implementado sem complexidade adicional significativa | Nenhum |
| "Complexidade de grupo subestimada" | **Nao materializado** — Smart Router com 6 rotas implementado sem complicacoes | Risco removido |
| "Echo sem LLM valida infraestrutura" | **Confirmado** — pipeline completo testado end-to-end antes de adicionar LLM | Estrategia validada para epics futuros |
| "Processamento sincrono suficiente sem worker" | **Confirmado** — performance <2s para echo. Worker necessario apenas com LLM (epic 002) | Nenhum |

---

## 3. Forward Compatibility Check

O epic 001 implementou decisoes de forward compatibility que impactam epics futuros:

| Decisao | Epic Beneficiado | Status |
|---------|------------------|--------|
| `RouteResult.agent_id` presente desde dia 1 (None = tenant default) | 003 (Configurable Routing) | ✅ Pronto — zero breaking change |
| `HANDOFF_ATIVO` enum + stub que retorna IGNORE | 005 (Handoff Engine) | ✅ Pronto — zero breaking change |
| `MessagingProvider` ABC (adapter pattern) | Qualquer epic que adicione canal | ✅ Pronto — extensivel |
| `format_for_whatsapp()` passthrough (seam para formatacao) | 002 (Conversation Core) | ✅ Pronto — diff minimo |
| `DebounceManager` isolado com interface estavel | 002 (migracao para ARQ worker) | ✅ Pronto — swap transparente |

**Nenhum impacto negativo em epics futuros detectado.**

---

## 4. Atualizacoes Recomendadas ao Roadmap

### 4.1 Status do Epic 001

| Campo | Antes | Depois |
|-------|-------|--------|
| Status | proposed (pitch criado) | **complete** (52 tasks, 122 testes, judge 92%) |
| Lifecycle | design | **building** |
| Proximo marco | iniciar epic 001 | **iniciar epic 002 (Conversation Core)** |

### 4.2 Estimativas Revisadas

| Epic | Estimativa Original | Estimativa Revisada | Justificativa |
|------|---------------------|---------------------|---------------|
| 001: Channel Pipeline | 1 semana | **~1 dia** (entregue) | Pipeline L2 automatizado acelerou execucao significativamente |
| 002: Conversation Core | 2 semanas | **2 semanas** (mantida) | LLM integration e DB persistence sao mais complexos que echo. Incerteza do Bifrost + pydantic-ai justifica manter |
| 003-008 | Como planejado | **Sem alteracao** | Sem novos dados que justifiquem revisao |

**Nota sobre estimativas**: A execucao do epic 001 via pipeline L2 automatizado foi significativamente mais rapida que o estimado. Porem, epic 001 era scope bem definido (echo sem LLM). Epics futuros com LLM, DB, e integracao externa provavelmente terao mais incerteza. Manter estimativas conservadoras.

### 4.3 Riscos Atualizados

| Risco | Status Anterior | Status Atual | Acao |
|-------|----------------|--------------|------|
| Evolution API payload muda entre versoes | Medio/Media | **Mitigado** — adapter + 122 testes | Rebaixar risco |
| Custo LLM acima do esperado no MVP | Alto/Baixa | **Pendente** — epic 002 | Manter |
| Complexidade de grupo subestimada | Medio/Media | **Eliminado** — 6 rotas funcionais | Remover |

### Novos Riscos Identificados

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Migracao debounce API→Worker (epic 002) | Baixo | Baixa | `DebounceManager` isolado — interface estavel, swap transparente |
| Body size limit ausente no webhook (W5 open) | Medio | Baixa | Configurar `--limit-max-request-size` no uvicorn antes de producao |
| Reconexao keyspace listener em cenarios prolongados de Redis downtime | Baixo | Baixa | Exponential backoff implementado (max 10 tentativas). Monitoring recomendado |

### 4.4 Sequenciamento

**Sem alteracao no sequenciamento.** As dependencias originais permanecem validas:

- Epic 002 depende de 001 ✅ (satisfeito)
- Epic 003 depende de 002 (mantido)
- Epic 004/005 dependem de 002 (mantido)
- Nenhuma nova dependencia descoberta

### 4.5 MVP Definition

**MVP permanece: 001 + 002.** O criterio "agente responde com IA, persiste em BD" continua correto. Epic 001 entregou a metade infra (pipeline de mensagens), epic 002 entrega a outra metade (IA + persistencia).

**Progresso MVP: 50%** — infraestrutura de mensagens completa, falta inteligencia e persistencia.

---

## 5. Licoes Aprendidas para Epics Futuros

### O Que Funcionou

1. **TDD com fixtures reais**: 122 testes com payloads capturados da Evolution API garantiram alta confianca. Replicar para epics futuros.
2. **Forward compatibility decisions**: `agent_id`, `HANDOFF_ATIVO` stub, e `MessagingProvider` ABC foram baixo custo e alto valor. Continuar a pratica.
3. **Fallback patterns**: Redis down → processar sem debounce. Simples e eficaz.
4. **Pipeline L2 automatizado**: Execucao muito mais rapida que estimado. Pipeline L2 funciona bem para epics com scope claro.

### O Que Melhorar

1. **PII em logs**: Judge corrigiu 3 de 4 modulos, QA encontrou o 4o. Criar ruff rule ou grep check no CI para `phone[:\[]` em logs.
2. **Body size limit**: Configurar desde dia 1 em epics futuros (uvicorn `--limit-max-request-size`).
3. **Provider lifecycle**: Criar provider compartilhado no lifespan desde o inicio, nao como fix posterior.
4. **Log duplicacao**: Definir convencao clara sobre quais pontos do pipeline emitem logs (evitar duplicacao como GROUP_SAVE_ONLY).

---

## 6. Recomendacao de Proximo Passo

**Iniciar epic 002 (Conversation Core)** via `/epic-context prosauai 002`.

O epic 002 e o proximo na sequencia, depende exclusivamente do 001 (satisfeito), e completa o MVP. Scope previsto: pydantic-ai agents, Supabase persistence, Bifrost LLM proxy, ARQ worker.

**Pre-condicoes para epic 002:**
- [x] Pipeline de mensagens funcional (webhook → route → debounce → response)
- [x] `RouteResult.agent_id` pronto para integracao
- [x] `MessagingProvider` ABC extensivel
- [x] `format_for_whatsapp()` seam para formatacao de respostas LLM
- [ ] Aprovar propostas de reconcile (12 atualizacoes de docs — esforco Small)
- [ ] Merge branch `epic/prosauai/001-channel-pipeline` → main

---

## 7. Nao Este Ciclo (Reafirmado)

Itens que foram considerados mas permanecem fora do escopo imediato:

| Item | Motivo da Exclusao | Revisitar Quando |
|------|--------------------|------------------|
| Multi-worker uvicorn | Requer leader election para debounce listener | Epic 002 (com ARQ worker, listener migra) |
| Infisical secrets management | `.env` + pydantic-settings suficiente para dev/staging | Pre-producao (epic posterior) |
| Redis Streams para mensageria | Debounce funciona com keys diretas | Epic 002 (worker precisa de queue) |
| Idempotencia por message_id | Sem DB para dedup nesta fase | Epic 002 (Supabase) |
| Rate limiting no webhook | Volume baixo (<100 msgs/min para echo) | Pre-producao ou epic posterior |

---

## Auto-Review

### Tier 1 — Checks Deterministicos

| # | Check | Resultado |
|---|-------|-----------|
| 1 | Output file exists and is non-empty | ✅ PASS |
| 2 | Required sections present (Status, Premissas, Riscos, Sequenciamento, MVP, Proximo Passo) | ✅ PASS |
| 3 | No unresolved placeholder markers (TODO/TKTK/???/PLACEHOLDER) | ✅ PASS |
| 4 | HANDOFF block present at footer | ✅ PASS |
| 5 | Epic 001 status updated to complete | ✅ PASS |
| 6 | Riscos atualizados com status pos-epic | ✅ PASS |
| 7 | MVP definition reafirmada | ✅ PASS |
| 8 | Licoes aprendidas documentadas | ✅ PASS |
| 9 | "Nao Este Ciclo" section present | ✅ PASS |

---

handoff:
  from: madruga:roadmap (reassess)
  to: user (merge PR)
  context: "Roadmap reassessment completo pos-epic 001. Roadmap valido — ajustes de status e estimativas, nao de sequenciamento. Proximo passo: aprovar propostas de reconcile, merge branch epic/prosauai/001-channel-pipeline → main, iniciar epic 002 via /epic-context prosauai 002."
  blockers: []
  confidence: Alta
  kill_criteria: "Descoberta de incompatibilidade arquitetural entre epic 001 e epic 002 que invalide a premissa de MVP incremental."
