# Roadmap Reassessment — Epic 006 Production Readiness

**Data:** 2026-04-12 | **Branch:** epic/prosauai/006-production-readiness | **Skill:** madruga:roadmap (L2 step 12)

---

## 1. Resumo do Epic Entregue

| Campo | Valor |
|-------|-------|
| Epic | 006 — Production Readiness |
| Status | **shipped** |
| Tasks | 34 (100% completas) |
| Testes | 67 |
| Judge Score | 88% (initial: 33% → 9 fixes aplicados) |
| QA Pass Rate | 100% (4 healed, 0 unresolved) |
| LOC | ~3270 linhas adicionadas |
| Appetite Planejado | 1 semana (5 dias) |
| Appetite Real | 1 sessao easter |
| Milestone | MVP |

### O que foi entregue

1. **Schema isolation** — Tabelas de negocio em `prosauai`, helpers RLS em `prosauai_ops`, schemas `observability` e `admin` reservados. Zero objetos em `auth` ou `public`. Supabase-safe.
2. **Migration runner** — Script Python custom (~80 LOC) com asyncpg, tracking em `prosauai_ops.schema_migrations`, advisory lock, idempotencia, fail-fast no startup.
3. **Particionamento messages** — `PARTITION BY RANGE (created_at)` mensal. PK composta `(id, created_at)`. Particoes futuras criadas automaticamente.
4. **Retention cron** — Purge diario: `DROP PARTITION` para messages, batch DELETE para demais tabelas. `--dry-run` safety. Structured logging com run_id.
5. **Log rotation** — Docker `json-file` driver com `max-size: 50m`, `max-file: 5` em todos os services. Max 1.25GB de logs.
6. **Phoenix Postgres backend** — `PHOENIX_SQL_DATABASE_SCHEMA=observability` em prod. SQLite mantido para dev.
7. **Host monitoring** — Netdata container em `127.0.0.1:19999` com metricas de CPU, RAM, disco e containers.
8. **Docker Compose prod** — `docker-compose.prod.yml` com overrides de producao completos.

### Decisoes Arquiteturais Tomadas

| # | Decisao | ADR |
|---|---------|-----|
| 1 | Schemas `prosauai` + `prosauai_ops` em vez de `public` + `auth` | ADR-024 (novo) |
| 2 | `prosauai_ops.tenant_id()` substitui `auth.tenant_id()` | ADR-011 (atualizado) |
| 3 | FK `eval_scores.message_id` removida (PG partition limitation) | Documentado em ADR-024 |
| 4 | Migration runner custom com asyncpg (zero deps novas) | Documentado em blueprint |
| 5 | Retention via container sleep loop (portavel, sem host crontab) | ADR-018 (atualizado) |

---

## 2. Impacto no MVP

### Antes do Epic 006

| Metrica | Valor |
|---------|-------|
| Epics MVP | 001, 002, 003, 004, 005, 006 |
| Epics shipped | 001, 002, 003, 004 (4/6) |
| Progresso | 80% |

### Apos o Epic 006

| Metrica | Valor |
|---------|-------|
| Epics shipped | 001, 002, 003, 004, 006 (5/6) |
| Progresso | **90%** |
| Blocker restante | Epic 005 (Conversation Core) — em andamento |
| Estimativa MVP completo | Apos merge de 005 + 006 |

### MVP Criterion Atualizado

O MVP criterion permanece valido: "Agente recebe mensagem WhatsApp multi-tenant, parseia 100% dos payloads reais, responde com IA, persiste em BD, com observabilidade total, router MECE provado em CI, e **infra production-ready**."

O epic 006 resolve a parte "infra production-ready". O epic 005 resolve a parte "responde com IA, persiste em BD". Ambos sao necessarios para o MVP completo.

---

## 3. Riscos Atualizados

### Riscos Mitigados

| Risco | Status Anterior | Status Atual | Evidencia |
|-------|----------------|--------------|-----------|
| Schema collision com Supabase (auth + public) | Pendente (epic 006) | **Mitigado** | Schemas dedicados `prosauai` + `prosauai_ops`. ADR-024. Zero objetos em auth/public |
| Disco VPS cheio (logs + Phoenix SQLite + pgdata) | Pendente (epic 006) | **Mitigado** | Log rotation json-file (max 1.25GB). Phoenix Postgres backend. Netdata monitoring |
| LGPD non-compliance (sem purge de dados) | Pendente (epic 006) | **Mitigado** | Cron retention diario: DROP PARTITION messages, batch DELETE demais. `--dry-run` safety |
| Particionamento messages quebra queries | Risco no pitch | **Eliminado** | PK composta funciona. FK removida (PG limitation). 67 testes passando |

### Riscos Remanescentes

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Custo LLM acima do esperado no MVP | Alto | Baixa | Bifrost com fallback Sonnet → Haiku (epic 005) |
| Docker log rotation insuficiente para 30d com alto volume | Baixo | Media | 250MB/service cobre >30d para 2-10 tenants. Monitorar apos deploy. Camada 2 (log aggregation) quando necessario |
| Sleep loop retention-cron drift acumulado | Baixo | Muito Baixa | Idempotencia natural mitiga. Tech debt: substituir por supercronic antes de multi-VPS |
| DATABASE_URL naming mismatch em prod Supabase | Baixo | Media | `.env.example` documenta. Funciona em Docker local. Requer atencao no deploy real |
| Merge de 006 antes de 005 causa conflito de migrations | Alto | Media | Coordenar branches: 005 deve mergear primeiro (ou simultaneamente). Migrations 006 reescrevem as mesmas de 005 |

### Riscos Novos Descobertos

| Risco | Origem | Impacto | Probabilidade | Mitigacao |
|-------|--------|---------|---------------|-----------|
| domain-model.md desatualizado (auth.tenant_id, sem schema prefix) | Reconcile D4.1/D4.2 | Medio | Alta | Aplicar propostas do reconcile antes do proximo epic que use domain-model como referencia |
| ADR-019 (Agent Tools) SQL sem schema prefix | Reconcile D7 | Baixo | Certa quando epic 008 iniciar | Atualizar no inicio do epic 008 |

---

## 4. Reavaliacao de Prioridades

### Sequencia Original (roadmap atual)

```
005 Conversation Core → 006 Production Readiness → 007 Configurable Routing → 008 Agent Tools → 009 Handoff Engine
```

### Sequencia Reavaliada

**Nenhuma mudanca na sequencia.** O epic 006 nao revelou necessidade de reordenacao. Justificativas:

1. **Epic 005 continua como proximo merge** — e o ultimo blocker MVP funcional. Sem ele, o agente nao responde com IA.
2. **Epic 007 (Configurable Routing DB)** mantem posicao — depende de 004 + 006 (ambos shipped). Escopo reduzido pelo 004 (engine declarativa ja entrega MECE routing). Prioridade baixa confirmada.
3. **Epic 008 (Agent Tools)** mantem posicao — depende de 006 (shipped). Pode comecar apos merge de 005+006.
4. **Epic 009 (Handoff Engine)** mantem posicao — depende de 006 (shipped). Pode comecar apos merge de 005+006.

### Epics Beneficiados pelo 006

| Epic | Beneficio |
|------|-----------|
| 007 (Configurable Routing DB) | Schema `prosauai` + migration runner prontos |
| 008 (Agent Tools) | Schema isolation + migration runner. ADR-019 precisa update menor |
| 013 (Public API Fase 2) | Schema `admin` reservado e vazio |
| 014 (TenantStore Postgres) | Namespace `admin` pronto, search_path documentado |
| 015/016 (Evals) | Phoenix Postgres backend resolve blocker de escalabilidade |
| 019 (RAG pgvector) | Extension `vector` trivial de adicionar em migration futura |

### Epics Negativamente Impactados

**Nenhum.** Epic 006 e puramente infraestrutural — nao altera logica de negocio, APIs ou contratos.

---

## 5. Licoes Aprendidas

### O que funcionou

1. **Pesquisa pre-implementacao** — Phase 0 (research.md) identificou a limitacao de UNIQUE global em tabelas particionadas PG 15 ANTES da implementacao. Evitou rewrite custoso.
2. **Migrations reescritas antes de prod** — Reescrever todas as 7 migrations com schema prefix foi trivial (nenhum dado existente). Fazer isso depois de prod seria ordens de magnitude mais complexo.
3. **Judge como safety net** — Score inicial 33% → 88% apos 9 fixes. O BLOCKER `DELETE...LIMIT` em PG teria causado falha silenciosa no retention cron em producao.
4. **Zero deps novas** — Migration runner com asyncpg, retention com stdlib. Alinhado com constitution (Principio I: pragmatismo).

### O que pode melhorar

1. **Enum types no public** — As migrations 003/004 criavam enums sem schema prefix. Judge detectou (WARNING #2). Deveria ter sido capturado na task de rewrite.
2. **Advisory lock ausente** — Migration runner inicial nao tinha lock para concorrencia. Judge detectou (WARNING #5). Pattern obvio para runners — incluir desde o inicio.
3. **domain-model.md drift** — Drift de ~25 ocorrencias `auth.tenant_id()`. Deveria ter sido incluido nas tasks de documentacao (Phase 10). Reconcile capturou, mas poderia ter sido previsto no plano.

---

## 6. Atualizacoes Necessarias no roadmap.md

As seguintes atualizacoes sao necessarias no `planning/roadmap.md` para refletir o resultado do epic 006. Baseadas nas propostas do reconcile-report.md:

### Diff 1 — Header e Status

| Secao | Campo | Antes | Depois |
|-------|-------|-------|--------|
| Header | updated | 2026-04-12 | 2026-04-12 (manter — mesmo dia) |
| Status | Lifecycle | building — epics 001-004 entregues, MVP a 80% | building — epics 001-004 + 006 entregues, MVP a 90% |
| Status | L2 Status | (adicionar) | Epic 006 shipped (34 tasks, 67 testes, judge 88%, QA 100%) |
| Status | Progresso MVP | 80% (001-004 shipped; 005 em andamento; 006 drafted) | 90% (001-004, 006 shipped; 005 em andamento) |

### Diff 2 — Epic Table

| Epic | Antes | Depois |
|------|-------|--------|
| 006 | **drafted** — schema isolation, log persistence, data retention, particionamento, host monitoring, migration runner | **shipped** (34 tasks, 67 testes, judge 88%, QA 100%) — schema isolation, log persistence, data retention, particionamento, host monitoring, migration runner |

### Diff 3 — Riscos

| Risco | Antes | Depois |
|-------|-------|--------|
| Schema collision com Supabase | Pendente (epic 006), Alto, Alta | **Mitigado (epic 006)**, —, — |
| Disco VPS cheio | Pendente (epic 006), Alto, Media | **Mitigado (epic 006)**, —, — |
| LGPD non-compliance | Pendente (epic 006), Alto, Alta | **Mitigado (epic 006)**, —, — |

### Diff 4 — Nota final

| Antes | Depois |
|-------|--------|
| Proximos passos: epic 005 em andamento. Epic 006 drafted — fecha gaps de infra | Proximos passos: epic 005 em andamento. Epic 006 shipped — gaps de infra resolvidos. Apos 005 mergear, primeiro deploy producao (VPS 2vCPU/4GB/40GB) |

### Diff 5 — Gantt

| Item | Antes | Depois |
|------|-------|--------|
| 006 Production Readiness | `:a6, after a5, 1w` | `:done, a6, after a5, 1w` |

---

## 7. Documentacao Pendente (do Reconcile)

| Prioridade | Doc | Mudanca | Blocker? |
|-----------|-----|---------|----------|
| **HIGH** | domain-model.md | Trocar ~25 ocorrencias `auth.tenant_id()` → `prosauai_ops.tenant_id()` | Sim — proximo epic que use domain-model como referencia SQL |
| **MEDIUM** | domain-model.md | Prefixar tabelas com `prosauai.` | Sim — mesma razao |
| **HIGH** | roadmap.md | 5 diffs acima (status, riscos, progresso, gantt) | Sim — roadmap desatualizado |

**Recomendacao:** Aplicar as 3 atualizacoes (domain-model + roadmap) **antes do merge** do epic 006 para main, ou imediatamente apos.

---

## 8. Proximo Passo Recomendado

### Imediato

1. **Mergear epic 005** (Conversation Core) — blocker MVP restante. Se 005 ainda esta em branch, coordenar merge com 006.
2. **Aplicar diffs do roadmap.md** — status, riscos, progresso (este report documenta o que mudar).
3. **Atualizar domain-model.md** — propostas D4.1/D4.2 do reconcile.

### Apos MVP (005 + 006 merged)

4. **Primeiro deploy producao** — VPS 2vCPU/4GB/40GB SSD. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.
5. **Iniciar proximo epic** — candidatos por prioridade:
   - **007 (Configurable Routing DB + Groups)** — se routing por DB e necessidade imediata
   - **008 (Agent Tools)** — se tools sao prioridade de produto
   - **009 (Handoff Engine)** — se handoff humano e prioridade de produto
   - **015 (Evals Offline)** — se qualidade do agente e prioridade

**Recomendacao:** Decidir com base em feedback do primeiro deploy real. O epic que mais reduz risco de churn e o **009 (Handoff Engine)** — permite escalar para clientes que precisam de fallback humano. Mas a decisao depende do pipeline de vendas.

---

## Auto-Review

### Tier 1 — Checks Deterministicos

| # | Check | Resultado |
|---|-------|----------|
| 1 | Output file exists and is non-empty | PASS |
| 2 | Line count within bounds | PASS (~200 linhas) |
| 3 | Required sections present (MVP impact, risks, priorities, next steps) | PASS |
| 4 | No placeholder markers (TODO, TKTK, ???, PLACEHOLDER) | PASS |
| 5 | HANDOFF block present at footer | PASS |

---

handoff:
  from: madruga:roadmap
  to: merge
  context: "Roadmap reassessment completo para epic 006 production readiness. MVP progresso 90% (5/6 epics shipped). 3 riscos mitigados (schema collision, disco VPS, LGPD). Nenhuma reordenacao de epics necessaria. Documentacao pendente: domain-model.md (25 ocorrencias auth.tenant_id), roadmap.md (5 diffs de status/riscos). Proximo: mergear 005 + 006, primeiro deploy producao VPS."
  blockers: []
  confidence: Alta
  kill_criteria: "Se epic 005 nao mergear antes de 006, migrations podem conflitar — coordenar branches."
