---
type: roadmap-reassess
epic: 004-router-mece
date: 2026-04-11
branch: epic/prosauai/004-router-mece
mvp_progress: "60%"
epics_shipped: [001, 002, 003]
epic_in_progress: 004
next_epic: 005
---

# Roadmap Reassessment — Pos Epic 004: Router MECE

**Data:** 11/04/2026 | **Branch:** `epic/prosauai/004-router-mece`
**Trigger:** Conclusao do ciclo L2 do epic 004 (judge 90%, QA 96%, reconcile 50% drift score, 947 testes)

---

## 1. Status Geral do MVP

| Campo | Antes (roadmap pre-004) | Agora (pos-004) |
|-------|------------------------|-----------------|
| **Epics shipped** | 001 | 001, 002, 003 |
| **Epic in-progress** | 002 | 004 (L2 cycle completo, merge pendente) |
| **Epics pendentes** | 003, 004, 005 | 005 |
| **Progresso MVP** | 20% | **60%** (3 shipped + 1 pronto para merge) |
| **Estimativa restante** | ~5-6 semanas | **~2-3 semanas** (somente 005 Conversation Core) |
| **Riscos criticos abertos** | 3 (HMAC, parser, router MECE) | **0 riscos criticos** — todos mitigados |

### Evolucao de Qualidade por Epic

| Epic | Tasks | Testes | Judge | QA | Tempo Real |
|------|-------|--------|-------|----|------------|
| 001 Channel Pipeline | 52 | 122 | 92% | 97% | ~1 semana |
| 002 Observability | — | — | — | — | ~1 semana |
| 003 Multi-Tenant Foundation | — | — | — | — | ~1 semana |
| 004 Router MECE | 51 | **947** | 90% | 96% | ~1 semana |

> O salto de 122 para 947 testes reflete a estrategia de property-based testing (enumeracao exaustiva + Hypothesis) introduzida no 004. Este padrao de teste sera reutilizado em epics futuros que envolvam routing ou classificacao.

---

## 2. Impacto do Epic 004 no Roadmap

### 2.1 Epics Diretamente Beneficiados

| Epic | Impacto | Detalhe |
|------|---------|---------|
| **005: Conversation Core** | **Desbloqueado** | `RespondDecision.agent_id` agora esta disponivel — 005 consome diretamente em vez de hardcodar default. Contrato `handoff:{tenant_id}:{sender_key}` documentado como aberto (005 sera o primeiro escritor). |
| **006: Configurable Routing DB** | **Escopo reduzido drasticamente** | Epic 004 ja entregou `RoutingEngine` + loader YAML + overlap analysis + CLI. Epic 006 se reduz a trocar o backend de YAML para tabela `routing_rules` — refactor trivial (~1-2 dias em vez de 1 semana). |
| **009: Trigger Engine** | **Desacoplado** | Trigger engine opera com routing rules separadas; nenhum impacto direto do 004. |
| **011: Admin Handoff Inbox** | **Contrato documentado** | Epic 011 (ou 005) deve escrever key Redis `handoff:{tenant_id}:{sender_key}`. 004 ja le com fallback seguro `False`. |
| **013: TenantStore Postgres** | **Decisao adiada** | `default_agent_id` e flat no `Tenant` dataclass. Quando 013 migrar para Postgres, o campo JSONB settings sera migrado para coluna tipada — decisao adiada ate a dor existir. |

### 2.2 Padroes Arquiteturais Introduzidos pelo 004

| Padrao | Reutilizavel em | Valor |
|--------|-----------------|-------|
| Property-based testing com enumeracao exaustiva | Qualquer epic com domain logic finita | Prova formal de invariantes em CI |
| Discriminated union pydantic (Decision subtypes) | 005 (LLM responses), 008 (Handoff actions) | Exhaustiveness provada por mypy/pyright |
| Sans-I/O classify() puro | 007 (Agent Tools classification) | Testabilidade maxima sem mocks |
| YAML config per-tenant com overlap analysis | 006 (DB migration preserva semantica) | Admin panel (009) ganha modelo de dados pronto |
| Contrato aberto (leitura sem escritor) | Qualquer feature com dependencia futura | Documenta gap sem bloquear progresso |

---

## 3. Reavaliacao de Prioridades

### 3.1 Sequencia Recomendada (pos-004)

| Ordem | Epic | Estimativa | Justificativa |
|-------|------|-----------|---------------|
| **1** | **005: Conversation Core** | 2 semanas | Unico bloqueio restante para MVP. Consome `RespondDecision.agent_id`. Primeira integracao LLM real. |
| 2 | 006: Configurable Routing DB + Groups | 3-5 dias | Escopo reduzido pelo 004. So troca loader YAML → DB table. |
| 3 | 007: Agent Tools | 2 semanas | Habilita agentes com acoes (consultar catalogo, agendar, etc.). |
| 4 | 008: Handoff Engine | 2 semanas | Escreve key `handoff:` no Redis — ativa regra `handoff_bypass` que 004 ja entende. |
| 5 | 009: Trigger Engine | 1 semana | Mensagens proativas. Depende de 008. |
| 6 | 010: Admin Dashboard | 2 semanas | UI de gerenciamento. Depende de 007. |
| 7 | 011: Admin Handoff Inbox | 1 semana | Fila de atendimento humano. Depende de 008. |

### 3.2 Mudancas na Sequencia Original

| Mudanca | Razao |
|---------|-------|
| Epic 006 estimativa de 1 semana → **3-5 dias** | RoutingEngine + loader ja existem; so trocar backend |
| Epic 008 agora documenta pre-requisito de escrever key Redis `handoff:` | Contrato aberto do 004 — 008 ou 011 devem implementar |
| Nenhuma reordenacao de epics | Sequencia original continua valida; 004 so acelerou 006 |

---

## 4. Riscos Atualizados

### 4.1 Riscos Mitigados

| Risco | Status Anterior | Status Atual |
|-------|----------------|--------------|
| Router nao-MECE hardcoded bloqueia agent resolution | Enderecado (draft) | **MITIGADO** — 4 camadas MECE provadas, 947 testes, 26 fixtures reais com equivalencia |
| Merge conflict entre 003 e 004 | Enderecado (draft) | **ELIMINADO** — sequencia back-to-back sem conflito |
| Servico rejeita 100% dos webhooks reais (HMAC imaginario) | Enderecado (003 draft) | **ELIMINADO** — 003 shipped com X-Webhook-Secret per-tenant |
| Parser falha em 50% das mensagens reais | Enderecado (003 draft) | **ELIMINADO** — 003 shipped com 12 correcoes + 26 fixtures |

### 4.2 Riscos Novos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| `conversation_in_handoff` sempre False ate epic 005/011 | Esperado | Baixo | Fallback seguro documentado. Regra `handoff_bypass` e inativa ate key existir. Teste explicito valida fallback. |
| mypy --strict nao automatizado em CI | Media | Medio | Match/case correto no codigo, mas prova formal nao automatizada. Adicionar ao CI como prioridade media. |
| Custo LLM acima do esperado no MVP (epic 005) | Media | Alto | Bifrost com fallback Sonnet → Haiku. Definir budget caps por tenant. |
| Complexidade de integracao LLM no 005 subestimada | Media | Medio | 005 e o epic mais complexo do MVP — alocar 2 semanas com buffer. TDD rigoroso. |

---

## 5. MVP — Projecao Atualizada

### Criterio MVP (inalterado)

Agente recebe mensagem WhatsApp **multi-tenant** (>=2 instancias Evolution reais), parseia 100% dos payloads reais, responde com IA, persiste em BD, **com observabilidade total + router MECE provado em CI**.

### Progresso

```
001 Channel Pipeline     ████████████████████ SHIPPED
002 Observability        ████████████████████ SHIPPED
003 Multi-Tenant Found.  ████████████████████ SHIPPED
004 Router MECE          ████████████████████ MERGE PENDENTE
005 Conversation Core    ░░░░░░░░░░░░░░░░░░░░ PENDENTE
```

**Estimativa para MVP completo:** ~2-3 semanas (somente epic 005 restante)

### O que 004 entregou para o MVP

- [x] Classificacao MECE por construcao — provada em CI via enumeracao exaustiva
- [x] Regras de roteamento externas (YAML per-tenant) — zero deploy para mudar
- [x] `agent_id` resolvido pelo router — epic 005 consome `Decision.agent_id`
- [x] Observabilidade: spans `router.classify` + `router.decide` com atributos estruturados
- [x] 947 testes passando (122 → 947 = +675% desde epic 001)
- [x] Rip-and-replace completo — zero codigo legado (enum, funcoes) remanescente

---

## 6. Objetivos e Resultados

| Objetivo de Negocio | Product Outcome | Baseline | Target | Epics | Status |
|---------------------|-----------------|----------|--------|-------|--------|
| Atender clientes 24/7 via WhatsApp | Resolucao autonoma de conversas | 0% (sem IA) | 40% (6m) | 001, 002, 003, 004, **005** | 80% — falta LLM integration |
| Operar multi-tenant sem deploy | Regras de roteamento editaveis por config | 0 tenants | 2+ tenants reais | 003, **004** | **100%** — 2 tenants com YAML independente |
| Observabilidade total da jornada | Trace fim-a-fim por mensagem | 0 spans | Waterfall completo (webhook → router → debounce → echo) | 002, **004** | **100%** — classify + decide spans adicionados |
| Escalar sem reescrever | Agent_id resolvido pelo router | `agent_id` sempre None | `agent_id` valido em toda decisao RESPOND | **004**, 005 | **100%** — RespondDecision.agent_id preenchido |

---

## 7. Nao Este Ciclo (Reafirmado)

| Item | Motivo da Exclusao | Revisitar Quando |
|------|--------------------|------------------|
| Expression language nas regras (jsonlogic/CEL) | Igualdade + conjuncao cobre 100% dos casos reais com 2 tenants. Overlap analysis fica decidivel. | Quando um tenant real precisar de OR/NOT que nao se resolve com 2 rows YAML |
| Hot reload de config de roteamento | Startup-only e suficiente; mudancas passam por PR + restart. | Epic 006 (DB-backed) ou epic 009 (admin API com hot reload) |
| Regex/glob em campos `when` | Overlap analysis se torna NP-hard com regex. | Nunca (rejeitado permanentemente no deep-dive) |
| mypy --strict em CI | Correto no codigo mas nao automatizado. | Proximo epic que toque em typing — adicionar como task T0 |

---

## 8. Recomendacao de Proximo Passo

**Merge epic 004** para main via PR. Depois:

```
/madruga:epic-context prosauai 005
```

Epic 005 (Conversation Core) e o unico bloqueio restante para o MVP. Com o router MECE entregando `RespondDecision.agent_id`, o 005 tem contrato de entrada limpo para integrar LLM (Bifrost → Claude/GPT) e persistir conversas.

**Pre-condicoes para 005:**
- [x] `RespondDecision.agent_id` disponivel (004)
- [x] Observabilidade total do pipeline (002 + 004)
- [x] Multi-tenant operando com 2 tenants reais (003)
- [x] Parser 100% correto contra payloads reais (003)
- [ ] Bifrost configurado e operacional (setup task do 005)
- [ ] Schema de conversas definido (design task do 005)

---

## Auto-Review

### Tier 1 — Checks Deterministicos

| # | Check | Resultado |
|---|-------|----------|
| 1 | Output file exists and is non-empty | PASS |
| 2 | Line count within bounds | PASS (< 300 linhas) |
| 3 | Required sections present (Status, Impacto, Prioridades, Riscos, MVP, Proximo Passo) | PASS |
| 4 | No placeholder markers remain (TODO/TKTK/???/PLACEHOLDER) | PASS |
| 5 | HANDOFF block present at footer | PASS |
| 6 | Objetivos e Resultados section present | PASS |
| 7 | Nao Este Ciclo section present with min 1 entry | PASS (4 entries) |
| 8 | All shipped epics from epics/ included | PASS (001, 002, 003 + 004 in-progress) |
| 9 | Dependencies acyclic | PASS |
| 10 | MVP clearly defined | PASS |

---

handoff:
  from: roadmap-reassess
  to: merge-and-next-epic
  context: "Roadmap reassessment completo pos-epic 004. MVP em 60% — 3 epics shipped, 1 pronto para merge. Unico bloqueio restante e epic 005 (Conversation Core, ~2-3 semanas). Epic 006 escopo reduzido para ~3-5 dias. Nenhum risco critico aberto. Proximo passo: merge 004, depois /madruga:epic-context prosauai 005."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o epic 005 revelar que a arquitetura sans-I/O do router nao suporta o fluxo LLM async, ou se o contrato RespondDecision.agent_id se provar insuficiente para o Conversation Core."
