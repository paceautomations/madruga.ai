# Reconcile Report — Epic 002: Observability

**Plataforma**: ProsauAI | **Epic**: 002-observability | **Data**: 2026-04-10  
**Branch**: `epic/prosauai/002-observability` | **Skill**: madruga:reconcile

---

## Resumo Executivo

O epic 002 implementou observabilidade fim-a-fim no pipeline de mensagens do ProsauAI — OpenTelemetry SDK + Phoenix (Arize) self-hosted, spans manuais, W3C Trace Context no debounce, correlação log↔trace, e dashboards documentados.

**Drift Score: 55%** (5 docs current / 11 docs checked).

A implementação está funcional (248 testes passando, judge 88%, QA aprovado), mas 3 categorias de drift exigem atenção:
1. **Fixes do Judge/QA não commitados** no repo prosauai — BLOCKERs (PII em logs) permanecem no código commitado
2. **ADR-020 e ADR-007 atualizado existem APENAS no repo prosauai** — não foram copiados para `platforms/prosauai/decisions/` no madruga.ai
3. **Docs de engenharia (domain-model, context-map, integrations, process)** ainda referenciam LangFuse

---

## Tabela de Saúde Documental

| Doc | Categorias (D1-D10) | Status | Drift Items |
|-----|---------------------|--------|-------------|
| `business/solution-overview.md` | D1 | ✅ CURRENT | 0 — atualizado com features epic 001+002 |
| `business/process.md` | D1, D8 | ❌ OUTDATED | 2 — referências LangFuse nos diagramas Mermaid e texto |
| `engineering/blueprint.md` | D2 | ✅ CURRENT | 0 — folder structure e §4.4 atualizados |
| `engineering/containers.md` | D3 | ✅ CURRENT | 0 — Phoenix no diagrama, Implementation Status, Container Matrix atualizados |
| `engineering/domain-model.md` | D4 | ❌ OUTDATED | 3 — referências LangFuse em M14, schema SQL, invariantes |
| `engineering/context-map.md` | D8 | ❌ OUTDATED | 2 — diagrama Mermaid e tabela ainda mostram LangFuse como Conformist |
| `engineering/integrations.md` | D8 | ❌ OUTDATED | 1 — linha 12 referência `prosauai-worker → LangFuse` |
| `decisions/ADR-007` | D5 | ❌ OUTDATED | 1 — status ainda "Accepted" (deveria ser "Superseded by ADR-020") |
| `decisions/ADR-020` | D5 | ❌ MISSING | 1 — arquivo existe no repo prosauai mas NÃO em platforms/prosauai/decisions/ |
| `planning/roadmap.md` | D6 | ✅ CURRENT | 0 — epic 002 in-progress, riscos atualizados |
| `platform.yaml` | D6 | ✅ CURRENT | 0 — lifecycle=building correto para estágio atual |

---

## Detecção de Drift por Categoria

### D1 — Scope Drift

**Documentos verificados**: `business/solution-overview.md`, `business/process.md`

| ID | Affected Doc | Current State | Expected State | Severity |
|----|-------------|---------------|----------------|----------|
| D1.1 | `business/process.md` | Diagrama Mermaid: `M14["M14 Observabilidade"] -.->|Traces| LF[/"LangFuse"/]` | Deveria ser `Phoenix` | medium |
| D1.2 | `business/process.md` | Texto: "LangFuse: Traces com spans por modulo" e "Prompt versions: source of truth no LangFuse" | Atualizar para Phoenix. Nota: prompt versioning NÃO é feature do Phoenix — remover menção ou marcar como futuro | medium |

`solution-overview.md` está CURRENT — features de epic 001 documentadas na tabela "Implementado", features de observabilidade não precisam aparecer aqui (é infraestrutura, não feature de negócio).

### D2 — Architecture Drift

**Documentos verificados**: `engineering/blueprint.md`

Nenhum drift detectado. Blueprint §2 (Stack), §3 (Folder Structure), §4.4 (Observabilidade), §4.6 (Failure Modes), §5 (LGPD) e Glossário foram todos atualizados para refletir Phoenix.

### D3 — Model Drift (Containers)

**Documentos verificados**: `engineering/containers.md`

Nenhum drift detectado. Container Matrix, diagrama Mermaid, Communication Matrix, Scaling Strategy e nova seção Implementation Status estão corretos.

**Nota sobre implementação vs docs**: O docker-compose no repo prosauai usa `arizephoenix/phoenix:latest` mas o ADR-020 (no repo prosauai) e a QA report especificam `8.22.1`. Isso é drift de implementação, não de documentação — ver D5.2 abaixo.

### D4 — Domain Drift

**Documentos verificados**: `engineering/domain-model.md`

| ID | Affected Doc | Current State | Expected State | Severity |
|----|-------------|---------------|----------------|----------|
| D4.1 | `domain-model.md` | M14 Observability: "LangFuse: Tracing de LLM calls, prompt management, sessoes | SDK Python, traces por conversation_id" | Atualizar para Phoenix. Remover prompt management (não é feature atual). Atualizar padrão de traces: `trace_id` por mensagem (não por conversation_id) | medium |
| D4.2 | `domain-model.md` | SQL schema: `evaluator TEXT NOT NULL, -- 'deepeval', 'promptfoo', 'langfuse', 'human'` | Substituir `langfuse` por `phoenix` na lista de evaluators | low |
| D4.3 | `domain-model.md` | Invariante: "LangFuse trace_id = conversation_id — correlacao 1:1" | Atualizar: trace_id por mensagem no Phoenix, não por conversation. Correlação via `trace_id` injetado no structlog | medium |

### D5 — Decision Drift

**Documentos verificados**: `decisions/ADR-007-*.md`, `decisions/ADR-020-*` (ausente)

| ID | Affected Doc | Current State | Expected State | Severity |
|----|-------------|---------------|----------------|----------|
| D5.1 | `decisions/ADR-007-langfuse-observability.md` | `status: Accepted` | `status: Superseded by ADR-020`. O arquivo no repo prosauai já tem `status: Superseded by ADR-020` + `superseded_by: ADR-020`. Copiar para madruga.ai | **high** |
| D5.2 | `decisions/ADR-020-phoenix-observability.md` | **ARQUIVO INEXISTENTE** | Copiar ADR-020 do repo prosauai (`git show epic/prosauai/002-observability:platforms/prosauai/decisions/ADR-020-phoenix-observability.md`). Esse ADR já existe no repo prosauai, apenas falta no madruga.ai | **high** |

**Ação recomendada**: Amend não necessário — os ADRs já existem no repo prosauai com conteúdo correto. Basta copiar ADR-020 e atualizar ADR-007 no madruga.ai.

### D6 — Roadmap Drift

**Documentos verificados**: `planning/roadmap.md`, `platform.yaml`

| Field | Planned (roadmap) | Actual (epic) | Drift? |
|-------|-------------------|---------------|--------|
| Status | in-progress | Implementado (248 testes, judge 88%, QA ok) | ⚠ Atualizar para **shipped** após merge do PR |
| Milestone | MVP | On track | ✅ Sem drift |
| Dependencies | 001 | 001 (correto) | ✅ Sem drift |
| Risks | 3 riscos documentados | Todos mitigados | ✅ Sem drift |

**Nota**: O status não deve mudar para "shipped" até o PR ser mergeado. O roadmap está correto como "in-progress". Após merge, atualizar:
- Epic Table: status `in-progress` → `shipped`
- L2 Status: adicionar "(epic 002 shipped)"
- Progresso MVP: 20% → 30%

### D7 — Epic Drift (Future Epics)

**Epics verificados**: 003-multi-tenant-foundation, 004-router-mece

| Epic | Pitch Assumption | How Affected | Impact | Action Needed |
|------|-----------------|--------------|--------|---------------|
| 003 | "Observability (epic 002) precisa de `tenant_id` nos spans" | ✅ Confirmado — `tenant_id` já é atributo obrigatório em todo span (`SpanAttributes.TENANT_ID` em conventions.py, valor via `settings.tenant_id`) | Nenhum | Delta review ao promover 003 — swap de placeholder `prosauai-default` para `tenant.id` real |
| 003 | "Delta review adiciona `tenant_id` em spans (~5 linhas)" | ✅ Correto — `tenant_id` já presente como `prosauai-default`. Delta real: trocar source de `settings.tenant_id` para `tenant_store.find_by_instance(instance_name).id` | Baixo | Mitigação trivial confirmada |
| 004 | "Observabilidade estruturada (structlog)" com `Decision.matched_rule` | ✅ Compatible — structlog com `trace_id`/`span_id` já funcional. Epic 004 adiciona `matched_rule` como atributo extra | Nenhum | Nenhuma ação |

**Nenhum impacto negativo** do epic 002 em epics futuros. As assumptions dos pitches estão alinhadas com a implementação.

### D8 — Integration Drift

**Documentos verificados**: `engineering/context-map.md`, `engineering/integrations.md`

| ID | Affected Doc | Current State | Expected State | Severity |
|----|-------------|---------------|----------------|----------|
| D8.1 | `context-map.md` | Diagrama: `langfuse["LangFuse"]` + `M14 -- "Conformist" --> langfuse` | Substituir por `phoenix["Phoenix (Arize)"]` + `M14 -- "Conformist" --> phoenix` | medium |
| D8.2 | `context-map.md` | Tabela: "Observability (M14) → LangFuse | Conformist" | Atualizar para "Observability (M14) → Phoenix (Arize) | Conformist (OTel SDK, não SDK proprietário)" | medium |
| D8.3 | `integrations.md` | "HTTPS SDK traces | prosauai-worker → LangFuse" | Atualizar: "OTLP gRPC :4317 | prosauai-api → Phoenix (Arize) | async (fire-and-forget via BatchSpanProcessor)" | medium |

### D9 — README Drift

Nenhum `platforms/prosauai/README.md` existe no madruga.ai. O README do repo prosauai foi atualizado com seção Observabilidade. **Sem drift** — README é artefato do repo externo, não do madruga.ai.

### D10 — Epic Decisions Drift

**Documento verificado**: `epics/002-observability/decisions.md` (13 decisões)

| # | Decision | Contradiction with ADR? | Promotion Candidate? | Still Valid? |
|---|---------|------------------------|---------------------|--------------|
| 1 | Phoenix substitui LangFuse | ✅ ADR-020 criado (repo prosauai), ADR-007 superseded | ⚠ ADR-020 falta no madruga.ai | ✅ Sim |
| 2 | OTel SDK + auto-instrumentation | Sem contradição | Não (decisão de implementação) | ✅ Sim |
| 3 | Supabase mesmo projeto, schema `observability` | Sem contradição com ADR-011 | Não (escopo limitado) | ✅ Sim |
| 4 | W3C Trace Context via Redis | Sem contradição | Não (padrão OTel) | ✅ Sim |
| 5 | `tenant_id` via settings | Sem contradição com ADR-017 | Não (placeholder) | ✅ Sim |
| 6 | Stack único (Phoenix sobe sempre) | Sem contradição | Não | ✅ Sim |
| 7 | Sampling head-based | Sem contradição | Não | ✅ Sim |
| 8 | OTel GenAI conventions | Alinhado com ADR-007 (princípio mantido) | Não | ✅ Sim |
| 9 | structlog processor | Sem contradição | Não | ✅ Sim |
| 10 | Zero PII em spans | Alinhado com ADR-018 | Não | ✅ Sim — **PORÉM** ver achado crítico abaixo |
| 11 | D0 como primeira tarefa | Sem contradição | Não | ✅ Aplicado |
| 12 | Sem alerting/metrics/distributed tracing | Sem contradição | Não | ✅ Sim |
| 13 | Critério migração Supabase separado | Sem contradição | Não (threshold) | ✅ Sim |

**Achado crítico (D10 + código):** A decisão #10 (Zero PII em spans) está documentada e correta, mas o código commitado no repo prosauai **ainda contém** `phone=phone` em 6 chamadas de log no `debounce.py` e `number[:8]+"..."` no `evolution.py`. O judge reportou esses como BLOCKERs e afirmou tê-los corrigido, mas as correções **não foram commitadas** na branch `epic/prosauai/002-observability`.

---

## Achado Crítico: Fixes Judge/QA Não Commitados

O judge-report.md e qa-report.md reportam 12+ fixes aplicados, incluindo 3 BLOCKERs. Verificação do estado do código na branch `epic/prosauai/002-observability` (commit `1c751b1`) revela que **nenhum fix foi commitado**:

| Fix Reportado | Status no Código | Severidade |
|---------------|-----------------|------------|
| PII: `phone=phone` → `phone_hash` em debounce.py (6 ocorrências) | ❌ NÃO aplicado | **BLOCKER** |
| PII: `number[:8]+"..."` → SHA-256 hash em evolution.py | ❌ NÃO aplicado | **BLOCKER** |
| Docker: portas bound a `127.0.0.1` | ❌ NÃO aplicado (ainda `6006:6006`) | WARNING |
| Phoenix: image pinada `8.22.1` | ❌ NÃO aplicado (ainda `latest`) | WARNING |
| `otel_grpc_insecure` setting | ❌ NÃO aplicado | WARNING |
| TracerProvider `force_flush()` + `shutdown()` | ❌ NÃO aplicado | WARNING |
| Safety TTL com `jitter_max` | ❌ NÃO verificado | WARNING |

**Ação necessária**: Antes de mergear o PR, todos os fixes reportados pelo judge e QA devem ser aplicados e commitados na branch do repo prosauai. Os BLOCKERs de PII violam ADR-018 (LGPD).

---

## Drift Score e Raio de Impacto

### Drift Score

`Score = 5 / 11 = 45%` → **55% dos docs verificados estão desatualizados.**

(11 docs verificados: solution-overview, process, blueprint, containers, domain-model, context-map, integrations, ADR-007, ADR-020, roadmap, platform.yaml)

### Raio de Impacto

| Área Alterada | Docs Diretamente Afetados | Docs Transitivamente Afetados | Esforço |
|---------------|--------------------------|-------------------------------|---------|
| LangFuse → Phoenix | ADR-007, domain-model, context-map, integrations, process | Nenhum adicional | M (5 arquivos, múltiplas seções cada) |
| ADR-020 (novo) | decisions/ | Nenhum | S (copiar arquivo do repo prosauai) |
| Fixes Judge/QA | Código no repo prosauai | Nenhum (docs já refletem design correto) | M (re-aplicar fixes em 7 arquivos) |

---

## Propostas de Atualização

### Proposta 1 — D5.2: Criar ADR-020 no madruga.ai (HIGH)

**Ação**: Copiar `ADR-020-phoenix-observability.md` do repo prosauai para `platforms/prosauai/decisions/`.

```diff
+ platforms/prosauai/decisions/ADR-020-phoenix-observability.md
```

O conteúdo já existe em `git show epic/prosauai/002-observability:platforms/prosauai/decisions/ADR-020-phoenix-observability.md` no repo prosauai.

### Proposta 2 — D5.1: Atualizar ADR-007 status (HIGH)

**Ação**: Mudar status de "Accepted" para "Superseded by ADR-020".

```diff
- status: Accepted
+ status: Superseded by ADR-020
+ superseded_by: ADR-020
```

### Proposta 3 — D4.1/D4.3: Atualizar domain-model.md M14 (MEDIUM)

**Antes**:
```
| **LangFuse** | Tracing de LLM calls, prompt management, sessoes | SDK Python, traces por conversation_id |
...
5. **LangFuse trace_id = conversation_id** — correlacao 1:1 para facilitar debugging
```

**Depois**:
```
| **Phoenix (Arize)** | Tracing fim-a-fim da jornada de mensagens via OTel, waterfall UI, SpanQL queries | OTel SDK Python → OTLP gRPC; traces por message_id |
...
5. **trace_id injetado em todo log estruturado** — correlacao bidirecional log↔trace via structlog processor
```

### Proposta 4 — D4.2: Atualizar evaluator SQL enum (LOW)

```diff
-     evaluator TEXT NOT NULL,  -- 'deepeval', 'promptfoo', 'langfuse', 'human'
+     evaluator TEXT NOT NULL,  -- 'deepeval', 'promptfoo', 'phoenix', 'human'
```

### Proposta 5 — D8.1/D8.2: Atualizar context-map.md (MEDIUM)

**Diagrama Mermaid**: Substituir `langfuse["LangFuse"]` por `phoenix["Phoenix (Arize)"]` e edge `M14 -- "Conformist" --> phoenix`.

**Tabela**: Atualizar linha "Observability (M14) → LangFuse | Conformist" para "Observability (M14) → Phoenix (Arize) | Conformist (via OTel SDK padronizado)".

### Proposta 6 — D8.3: Atualizar integrations.md (MEDIUM)

```diff
- | 12 | **HTTPS SDK traces** | HTTPS SDK | prosauai-worker → LangFuse | per-message | — | Fire-and-forget; buffer local em Redis |
+ | 12 | **OTLP gRPC traces** | OTLP gRPC :4317 | prosauai-api → Phoenix (Arize) | per-span (batch) | — | Fire-and-forget via BatchSpanProcessor; API continua se Phoenix indisponível |
```

### Proposta 7 — D1.1/D1.2: Atualizar process.md (MEDIUM)

**Diagrama Mermaid**: Substituir `LF[/"LangFuse"/]` por `PX[/"Phoenix (Arize)"/]` em ambos os diagramas onde M14 aparece.

**Texto**: Substituir menções a LangFuse por Phoenix. Remover "Prompt versions: source of truth no LangFuse" (prompt versioning não é feature do Phoenix nesta fase).

### Proposta 8 — Fixes Judge/QA no repo prosauai (BLOCKER)

**Ação**: Re-aplicar e commitar os fixes reportados pelo judge e QA na branch `epic/prosauai/002-observability`:

1. `debounce.py`: 6x `phone=phone` → `phone_hash=hash_phone(phone)` (PII BLOCKER)
2. `evolution.py`: `number[:8]+"..."` → SHA-256 hash real (PII BLOCKER)
3. `docker-compose.yml`: portas `"127.0.0.1:6006:6006"`, `"127.0.0.1:4317:4317"` e `"127.0.0.1:6379:6379"`
4. `docker-compose.yml`: Phoenix image `arizephoenix/phoenix:8.22.1`
5. `config.py`: adicionar `otel_grpc_insecure: bool = True`
6. `main.py`: adicionar `force_flush()` + `shutdown()` no lifespan shutdown
7. `debounce.py`: buffer TTL incluir `jitter_max`

---

## Revisão do Roadmap (Mandatória)

### Status do Epic 002

| Campo | Planejado | Atual | Ação |
|-------|-----------|-------|------|
| Status | in-progress | Implementado (judge+QA concluídos, fixes pendentes de commit) | Atualizar para `shipped` após merge do PR |
| Appetite | 1 semana | ~1 semana (estimativa alinhada) | ✅ Sem desvio |
| Milestone | MVP | On track | ✅ Sem desvio |

### Dependências Descobertas

| Dependência | Tipo | Impacto |
|------------|------|---------|
| Epic 003 precisa de delta review para `tenant_id` em spans | Esperada (já documentada) | Baixo — swap trivial (~5 linhas) |
| Fixes judge/QA devem ser commitados antes de merge | Não esperada — nova | **Alto** — BLOCKERs de PII |

### Status dos Riscos

| Risco | Status | Ação |
|-------|--------|------|
| Observability ops complexity | ✅ Mitigado — Phoenix single container funcional | Nenhuma |
| OTel overhead em hot path | ✅ Mitigado — benchmark executado (T046) | Nenhuma |
| Reconcile pendente do epic 001 (12 propostas) | ✅ Resolvido — D0 aplicado nos 4 docs | Nenhuma |

### Riscos Novos

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Fixes judge/QA perdidos (não commitados) | Alto | Alta (status atual) | Re-aplicar fixes antes do merge |
| ADR-020 ausente do madruga.ai causa confusão | Médio | Média | Copiar ADR-020 como parte deste reconcile |

### Diffs Concretos para roadmap.md

Após merge do PR:
```diff
- | 2 | 002: Observability (Phoenix + OTel) | 001 | medio | MVP | **in-progress** (branch epic/prosauai/002-observability) |
+ | 2 | 002: Observability (Phoenix + OTel) | 001 | medio | MVP | **shipped** (248 testes, judge 88%, QA 97%) |
```

```diff
- **L2 Status:** Epic 001 shipped (52 tasks, 122 testes, judge 92%, QA 97%). Epic 002 in-progress. Epics 003 e 004 drafted.
+ **L2 Status:** Epic 001 shipped (52 tasks, 122 testes, judge 92%, QA 97%). Epic 002 shipped (51 tasks, 248 testes, judge 88%, QA ok). Epics 003 e 004 drafted.
```

```diff
- **Progresso MVP:** 20% (001 entregue; 002 in-progress; 003, 004, 005 pendentes)
+ **Progresso MVP:** 30% (001, 002 entregues; 003, 004, 005 pendentes)
```

---

## Impacto em Epics Futuros

| Epic | Pitch Assumption | Como Afetado | Impacto | Ação |
|------|-----------------|--------------|---------|------|
| 003 Multi-Tenant | `tenant_id` placeholder em spans | ✅ Alinhado — `settings.tenant_id` já presente | Nenhum | Delta review ao promover |
| 003 Multi-Tenant | structlog com `tenant_id` em todo log | ✅ Compatível — processor OTel já injeta `trace_id`/`span_id`, adicionar `tenant_id` é trivial | Nenhum | Adicionar no delta review |
| 004 Router MECE | `Decision.matched_rule` em logs | ✅ Compatível — structlog funcional, adicionar atributo é aditivo | Nenhum | Nenhuma |

**Nenhum impacto negativo em epics futuros detectado.**

---

## Auto-Review

### Tier 1 — Checks Determinísticos

| # | Check | Result |
|---|-------|--------|
| 1 | Report file exists and non-empty | ✅ PASS |
| 2 | All 10 drift categories scanned (D1-D10) | ✅ PASS |
| 3 | Drift Score computed | ✅ PASS (45%) |
| 4 | No placeholder markers | ✅ PASS (0 TODO/TKTK/???/PLACEHOLDER) |
| 5 | HANDOFF block present | ✅ PASS |
| 6 | Impact radius matrix present | ✅ PASS |
| 7 | Roadmap review section present | ✅ PASS |

### Tier 2 — Scorecard

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Every drift item has current vs expected state | ✅ Yes — all 13 drift items com before/after |
| 2 | Roadmap review completed with actual vs planned | ✅ Yes — status, appetite, milestone, riscos |
| 3 | ADR contradictions flagged with recommendation | ✅ Yes — ADR-007 superseded, ADR-020 missing |
| 4 | Future epic impact assessed (top 3) | ✅ Yes — 003, 004 analisados, zero impacto negativo |
| 5 | Concrete diffs provided (not vague descriptions) | ✅ Yes — diffs explícitos para cada proposta |
| 6 | Trade-offs explicit for each proposed change | ✅ Yes — severidade e esforço por proposta |
| 7 | Kill criteria defined | ✅ Yes |

**Confiança**: Média — drift score alto (45%) puxado por referências LangFuse espalhadas em 4 docs de engenharia, e achado crítico de fixes não commitados. Os drifts são previsíveis (substituição de tooling) e mecânicos de corrigir.

---

## Gate: Human

### Decisões que requerem aprovação

1. **Aplicar propostas 1-7** (atualizar docs no madruga.ai para eliminar referências LangFuse e adicionar ADR-020)?
2. **Proposta 8 (fixes judge/QA)**: Re-aplicar fixes no repo prosauai e commitar antes do merge? Isso é BLOCKER para merge — PII em logs viola ADR-018.
3. **Roadmap update**: Atualizar status para "shipped" agora ou após merge efetivo?

### Recomendação

Aplicar propostas 1-7 agora (atualizações documentais no madruga.ai). Proposta 8 é BLOCKER e deve ser resolvida no repo prosauai antes de qualquer merge.

---

## Cascade Branch Seal

```
Branch: epic/prosauai/002-observability
Working tree: modified files uncommitted (platform docs + epic artifacts)
Status: NÃO selar agora — aguardando:
  1. Aprovação das propostas de atualização documental
  2. Resolução dos fixes judge/QA no repo prosauai
  3. Merge do PR após todas as correções
```

Após aprovação, o commit será:
```
feat: epic 002 observability — full L2 cycle + reconcile
```

---

handoff:
  from: madruga:reconcile
  to: madruga:roadmap
  context: "Reconcile detectou drift score 45% — 13 items em 6 categorias. Principal achado: fixes judge/QA (incl. 2 BLOCKERs PII) não commitados no repo prosauai. 8 propostas de atualização: ADR-020 missing, ADR-007 status, 4 docs com referências LangFuse, fixes de código. Nenhum impacto negativo em epics futuros. Roadmap precisa atualizar epic 002 para shipped após merge."
  blockers:
    - "Fixes judge/QA não commitados no repo prosauai (2 BLOCKERs PII)"
  confidence: Media
  kill_criteria: "Se os BLOCKERs de PII não forem resolvidos antes do merge, o epic NÃO pode ser considerado shipped."
