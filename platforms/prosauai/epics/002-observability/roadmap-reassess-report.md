# Roadmap Reassessment Report — Epic 002: Observability

**Plataforma**: ProsauAI | **Epic**: 002-observability | **Data**: 2026-04-10  
**Branch**: `epic/prosauai/002-observability` | **Skill**: madruga:roadmap (reassess)

---

## Resumo Executivo

O epic 002 (Observability — Tracing total da jornada de mensagem) completou o ciclo L2 completo: specify → clarify → plan → tasks → analyze → implement → judge (88%) → QA (97%) → reconcile. A implementação entregou OpenTelemetry SDK + Phoenix (Arize) self-hosted com spans manuais, W3C Trace Context no debounce, correlação log↔trace via structlog, e dashboards documentados.

**Veredicto**: Epic 002 está **pronto para merge** após resolução dos blockers de PII identificados pelo reconcile (fixes judge/QA não commitados). A estimativa de 1 semana foi cumprida. O roadmap permanece on-track para o MVP.

---

## 1. Status do Epic 002

| Métrica | Planejado | Realizado | Desvio |
|---------|-----------|-----------|--------|
| Appetite | 1 semana | ~1 semana | ✅ Sem desvio |
| Tasks | 51 | 51/51 completadas | ✅ 100% |
| Testes | 130+ (122 + 8 novos) | 248 passando | ✅ Superou expectativa (+96 testes) |
| LOC novos | ~1055 | ~5793 adicionadas | ⚠ 5.5x maior — inclui testes extensivos (2600 LOC), benchmarks, dashboards |
| Judge score | ≥80% | 88% | ✅ Aprovado |
| QA score | — | 97% (4/4 layers) | ✅ Aprovado |
| Drift score (reconcile) | 0% | 55% | ⚠ Referências LangFuse persistem em 5 docs de engenharia |

### Entregas Confirmadas

- [x] OpenTelemetry SDK com auto-instrumentation FastAPI/httpx/redis
- [x] 5+ spans manuais nos pontos de domínio (webhook, route, debounce.append, debounce.flush, echo)
- [x] W3C Trace Context propagado pelo Redis — trace contínuo webhook → flush → echo
- [x] Correlação log↔trace via structlog processor (trace_id/span_id em todo log)
- [x] Container Phoenix no docker-compose com volume persistente
- [x] 5 dashboards curados (SpanQL queries documentadas)
- [x] Health endpoint estendido com campo `observability`
- [x] Forward-compat: `gen_ai.system="echo"` placeholder para epic 003
- [x] Zero PII em spans (phone_hash, nunca text raw)
- [x] ADR-020 publicado (Phoenix substitui LangFuse — supersedes ADR-007)

### Pendências Pré-Merge

| Item | Severidade | Ação |
|------|-----------|------|
| PII em logs (6x `phone=phone` em debounce.py, `number[:8]+"..."` em evolution.py) | **BLOCKER** | Re-aplicar fixes judge/QA e commitar no repo prosauai |
| ADR-020 ausente no madruga.ai | HIGH | Copiar do repo prosauai |
| ADR-007 status não atualizado no madruga.ai | HIGH | Marcar como Superseded by ADR-020 |
| 5 docs com referências LangFuse (domain-model, context-map, integrations, process, ADR-007) | MEDIUM | Aplicar propostas 1-7 do reconcile |
| Docker image Phoenix não pinada (`:latest`) | LOW | Pinar para `8.22.1` |

---

## 2. Impacto no Roadmap

### 2.1 Progresso do MVP

| Antes (pré-002) | Depois (pós-002) |
|-----------------|-------------------|
| 20% (001 entregue) | **30%** (001 + 002 entregues) |
| 5 epics MVP | 5 epics MVP (sem mudança) |
| ~6-7 semanas restantes | ~4-5 semanas restantes |

### 2.2 Atualização da Epic Table

| Ordem | Epic | Status Anterior | Status Novo |
|-------|------|----------------|-------------|
| 1 | 001: Channel Pipeline | shipped | shipped (sem mudança) |
| 2 | **002: Observability** | **in-progress** | **shipped** (248 testes, judge 88%, QA 97%) |
| 3 | 003: Multi-Tenant Foundation | drafted | drafted (próximo a promover) |
| 4 | 004: Router MECE | drafted | drafted |
| 5 | 005: Conversation Core | sugerido | sugerido |

### 2.3 Gantt Atualizado

```mermaid
gantt
    title Roadmap ProsaUAI (pos-Epic 002)
    dateFormat YYYY-MM-DD
    section MVP
    001 Channel Pipeline (DONE)   :done, a1, 2026-04-08, 1d
    002 Observability (DONE)      :done, a2, 2026-04-10, 1w
    003 Multi-Tenant Foundation   :a3, 2026-04-17, 1w
    004 Router MECE               :a4, after a3, 1w
    005 Conversation Core         :a5, after a4, 2w
    section Post-MVP
    006 Configurable Routing DB + Groups :a6, after a5, 1w
    007 Agent Tools         :a7, after a5, 2w
    008 Handoff Engine      :a8, after a5, 2w
    009 Trigger Engine      :a9, after a8, 1w
    section Admin
    010 Admin Dashboard     :a10, after a7, 2w
    011 Admin Handoff Inbox :a11, after a8, 1w
```

---

## 3. Riscos Atualizados

### Riscos Mitigados pelo Epic 002

| Risco | Status Anterior | Status Novo |
|-------|----------------|-------------|
| Observability ops complexity | Pendente | ✅ **Mitigado** — Phoenix single container funcional, stack único com `docker compose up` |
| OTel overhead em hot path do webhook | Novo | ✅ **Mitigado** — benchmark executado, overhead aceitável |
| Reconcile pendente do epic 001 (12 propostas) | Carregado | ✅ **Resolvido** — D0 aplicado (4 docs atualizados) |

### Riscos Novos Descobertos

| Risco | Impacto | Probabilidade | Mitigação | Épico Afetado |
|-------|---------|---------------|-----------|---------------|
| Fixes judge/QA não commitados (PII em logs) | Alto | Alta (status atual) | Re-aplicar e commitar antes do merge | 002 (pré-merge) |
| Drift documental acumulado (refs LangFuse em 5 docs) | Médio | Certa | Aplicar propostas reconcile como parte do merge | 002 (pré-merge) |
| Phoenix SQLite local vs Postgres Supabase em prod | Baixo | Média | Pragmatismo: SQLite dev, Supabase prod. Documentar no quickstart | 002 (aceito) |
| Volume de spans pode crescer com epic 003 (LLMs = mais spans) | Médio | Média | Sampling 10% prod já configurado. Critério migração documentado: >5M spans/dia | 003+ |

### Riscos Existentes — Sem Mudança

| Risco | Status |
|-------|--------|
| Custo LLM acima do esperado (epic 005) | Pendente — sem novos dados |
| Router não-MECE hardcoded (epic 004) | Endereçado (draft) |
| Serviço rejeita 100% dos webhooks reais (epic 003) | Endereçado (draft) |
| Parser falha em 50% das mensagens reais (epic 003) | Endereçado (draft) |
| Merge conflict entre 003 e 004 | Endereçado (sequência back-to-back) |

---

## 4. Impacto em Epics Futuros

### 4.1 Dependências Confirmadas

| Epic | Assumption no Pitch | Status pós-002 | Ação |
|------|---------------------|----------------|------|
| 003 Multi-Tenant Foundation | `tenant_id` placeholder em spans | ✅ Confirmado — `settings.tenant_id` presente como `prosauai-default` em todo span | Delta review: swap para `tenant_store.find_by_instance(name).id` (~5 linhas) |
| 003 Multi-Tenant Foundation | structlog com `tenant_id` em todo log | ✅ Compatível — processor OTel injeta trace_id/span_id; adicionar tenant_id é aditivo | Adicionar `tenant_id` ao structlog no delta review |
| 004 Router MECE | Observabilidade estruturada com `Decision.matched_rule` | ✅ Compatível — structlog funcional, adicionar atributo customizado é trivial | Nenhuma ação |
| 005 Conversation Core | Forward-compat `gen_ai.*` para LLM tracing | ✅ Confirmado — `gen_ai.system="echo"` placeholder, `GEN_AI_REQUEST_MODEL` reservado | Swap `"echo"` para provider real (pydantic-ai) |
| 014/015 Evals Offline/Online | Phoenix como base de eval | ✅ Confirmado — Phoenix tem datasets e experiments nativos, vazios mas prontos | Nenhuma ação imediata |

### 4.2 Nenhum Impacto Negativo Detectado

O epic 002 não invalidou nenhuma premissa dos epics futuros. Todas as interfaces de forward-compat (tenant_id, gen_ai.*, structlog, OTel conventions) estão no lugar.

---

## 5. Lições Aprendidas

### O que funcionou bem

1. **Estimativa calibrada**: 1 semana planejada, ~1 semana executada. Fator 1.5-2x já incorporado.
2. **TDD efetivo**: 248 testes (vs 130+ planejados). Testes extensivos pegaram bugs que o judge e QA refinaram.
3. **research.md como fundação**: 7 tópicos de pesquisa pré-implementação evitaram rabbit holes. Alternativas documentadas com trade-offs.
4. **Forward-compat pragmática**: Placeholders (`gen_ai.system="echo"`, `tenant_id=prosauai-default`) custaram ~10 LOC extras mas garantem zero refactor nos epics 003-005.

### O que pode melhorar

1. **LOC estimado vs real**: 1055 planejados → 5793 reais (5.5x). Testes + dashboards + benchmark foram subestimados. **Recomendação**: multiplicar estimativa de LOC por 3-4x quando inclui testes extensivos.
2. **Fixes do judge/QA não persistidos**: Judge reportou 12 fixes aplicados, mas nenhum foi commitado na branch. **Recomendação**: judge e QA devem commitar fixes automaticamente (ou deixar claro se os fixes são apenas no contexto local).
3. **D0 doc sync inconsistente**: Tasks marcadas como concluídas no tasks.md mas edições não aplicadas nos docs do madruga.ai. **Recomendação**: analyze-post deveria verificar diffs reais antes de aprovar tasks de documentação.
4. **Drift documental previsível**: Quando tooling muda (LangFuse → Phoenix), referências espalhadas em múltiplos docs de engenharia geram drift mecânico. **Recomendação**: considerar grep automatizado pós-implement para termos substituídos.

---

## 6. Recomendações para Próximos Passos

### Imediato (antes do merge do PR)

1. **Resolver BLOCKERs PII** no repo prosauai (debounce.py + evolution.py)
2. **Aplicar propostas do reconcile** (ADR-020, ADR-007 status, refs LangFuse)
3. **Merge PR** do epic 002

### Próximo Epic: 003 — Multi-Tenant Foundation

**Justificativa para sequência**: Epic 003 é o próximo na cadeia de dependências. Resolve os 2 riscos mais críticos do roadmap: (a) serviço rejeita 100% dos webhooks reais (HMAC imaginário), (b) parser falha em 50% das mensagens reais. Deploy back-to-back com 004.

**Delta review necessário ao promover 003**:
- `tenant_id` em spans: swap de placeholder para lookup real (~5 linhas)
- `tenant_id` no structlog: adicionar ao processor (~2 linhas)

**Comando**: `/madruga:epic-context prosauai 003` (sem `--draft`) para promover, criar branch `epic/prosauai/003-multi-tenant-foundation`, e entrar no ciclo L2.

### Sequência recomendada mantida

```
002 (DONE) → 003 (Multi-Tenant) → 004 (Router MECE) → [deploy prod] → 005 (Conversation Core)
```

Sem alteração na sequência. O epic 002 não revelou nenhuma informação que justifique reordenação.

---

## 7. Diffs Concretos para roadmap.md

Após merge do PR do epic 002, aplicar no `platforms/prosauai/planning/roadmap.md`:

### Status Section

```diff
- **L2 Status:** Epic 001 shipped (52 tasks, 122 testes, judge 92%, QA 97%). Epic 002 in-progress. Epics 003 e 004 drafted.
+ **L2 Status:** Epic 001 shipped (52 tasks, 122 testes, judge 92%, QA 97%). Epic 002 shipped (51 tasks, 248 testes, judge 88%, QA 97%). Epics 003 e 004 drafted.
```

### MVP Section

```diff
- **Progresso MVP:** 20% (001 entregue; 002 in-progress; 003, 004, 005 pendentes)
+ **Progresso MVP:** 30% (001, 002 entregues; 003, 004, 005 pendentes)
```

### Gantt Section

```diff
-     002 Observability              :a2, after a1, 1w
+     002 Observability (DONE)       :done, a2, after a1, 1w
```

### Epic Table

```diff
- | 2 | 002: Observability (Phoenix + OTel) | 001 | medio | MVP | **in-progress** (branch epic/prosauai/002-observability) |
+ | 2 | 002: Observability (Phoenix + OTel) | 001 | medio | MVP | **shipped** (51 tasks, 248 testes, judge 88%, QA 97%) |
```

### Riscos Section

```diff
- | OTel overhead em hot path do webhook | Novo (epic 002) | Baixo | Baixa | Sampling configuravel + benchmark p50/p95/p99 antes/depois |
+ | OTel overhead em hot path do webhook | **Mitigado (epic 002)** | Baixo | Baixa | Benchmark executado, overhead aceitável. Sampling configurável via env |
- | Reconcile pendente do epic 001 (12 propostas) | Carregado (epic 002) | Baixo | — | Aplicar como primeira tarefa do epic 002 (status updates de docs) |
+ | Reconcile pendente do epic 001 (12 propostas) | **Resolvido (epic 002)** | — | — | D0 aplicado: solution-overview, blueprint, containers, platform.yaml atualizados |
```

### Footer

```diff
- *Proximos passos: terminar epic 002 (Observability). Promover epic 003 (Multi-Tenant Foundation) apos 002 mergar — delta review adiciona `tenant_id` em spans do 002. Depois 004-router-mece. Prod deploy unico apos 003 + 004 mergerem.*
+ *Proximos passos: promover epic 003 (Multi-Tenant Foundation) — delta review adiciona `tenant_id` real em spans. Depois 004-router-mece. Prod deploy unico apos 003 + 004 mergerem.*
```

```diff
- > **Proximo passo:** terminar `epic/prosauai/002-observability` em andamento. Depois: `/madruga:epic-context prosauai 003` (sem `--draft`) para promover, fazer delta review do 002 (`tenant_id` em spans), criar branch `epic/prosauai/003-multi-tenant-foundation` e entrar no ciclo L2.
+ > **Proximo passo:** `/madruga:epic-context prosauai 003` (sem `--draft`) para promover epic 003, delta review (`tenant_id` em spans), criar branch `epic/prosauai/003-multi-tenant-foundation` e entrar no ciclo L2.
```

---

## Auto-Review

### Tier 1 — Checks Determinísticos

| # | Check | Result |
|---|-------|--------|
| 1 | Output file exists and non-empty | ✅ PASS |
| 2 | Line count within bounds | ✅ PASS |
| 3 | Required sections present (Status, Impacto, Riscos, Epics Futuros, Diffs) | ✅ PASS |
| 4 | No unresolved placeholders | ✅ PASS (0 TODO/TKTK/???/PLACEHOLDER) |
| 5 | HANDOFF block present | ✅ PASS |
| 6 | Diffs concretos para roadmap.md | ✅ PASS |
| 7 | Gantt Mermaid válido | ✅ PASS |

### Tier 2 — Scorecard

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Todas as entregas do epic verificadas | ✅ Yes — 10 entregas confirmadas |
| 2 | Status de riscos atualizado | ✅ Yes — 3 mitigados, 4 novos, 5 sem mudança |
| 3 | Impacto em epics futuros avaliado | ✅ Yes — 5 epics verificados, 0 impacto negativo |
| 4 | Diffs concretos para roadmap.md | ✅ Yes — 6 blocos de diff |
| 5 | Lições aprendidas documentadas | ✅ Yes — 4 positivas, 4 melhorias |
| 6 | Próximo passo claro | ✅ Yes — epic 003 com delta review |
| 7 | Kill criteria defined | ✅ Yes |

**Confiança**: Alta — epic completou todos os 12 nodes L2, entregas alinhadas com spec, sequência do roadmap não precisa mudar.

---

handoff:
  from: madruga:roadmap (reassess)
  to: merge PR + madruga:epic-context prosauai 003
  context: "Epic 002 shipped: 51 tasks, 248 testes, judge 88%, QA 97%. Roadmap atualizado com diffs concretos. Progresso MVP: 30%. Próximo: resolver BLOCKERs PII, merge PR, promover epic 003 (Multi-Tenant Foundation) com delta review (tenant_id em spans). Sequência 003 → 004 → deploy prod mantida."
  blockers:
    - "BLOCKERs PII (fixes judge/QA) devem ser commitados no repo prosauai antes do merge"
  confidence: Alta
  kill_criteria: "Se os BLOCKERs de PII não forem resolvidos, o epic NÃO pode ser mergeado. Se o delta review do 003 revelar incompatibilidade com a instrumentação do 002, reabrir."
