# Specification Analysis Report — Epic 012 Tenant Knowledge Base (RAG)

**Date**: 2026-04-26
**Artifacts analyzed**: spec.md (423 lines), plan.md (360 lines), tasks.md (417 lines)
**Mode**: Read-only consistency analysis (no edits applied).

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Coverage Gap | HIGH | spec.md FR-068 vs tasks.md T026 | FR-068 demanda audit log estruturado quando admin Pace cross-tenant lista documents/chunks via `pool_admin` BYPASSRLS. T026 cria 5 helpers structlog (`emit_document_uploaded/deleted/downloaded/search_executed/replace_detected`) — nenhum cobre acesso cross-tenant. Sem evento dedicado, FR-068 nao e implementavel | Adicionar 6o helper `emit_cross_tenant_access(actor_user_id, target_tenant_id, resource, action)` em T026 e callsite em T054 (GET list quando tenant_id query difere do admin scope) |
| F2 | Coverage Gap | HIGH | spec.md FR-072 vs tasks.md (none) | FR-072 exige `documents.source_hash` SHA-256 do raw file calculado no upload. Schema FR-001 inclui coluna `source_hash TEXT NOT NULL`, mas nenhuma task (T029-T030 endpoint upload, T020 repository) descreve calculo do SHA-256 nem persistencia. Sera campo NOT NULL sem fonte | T030 deve adicionar `hashlib.sha256(file_bytes).hexdigest()` antes do INSERT em `documents`; opcionalmente storage layer pode retornar hash junto do upload |
| F3 | Inconsistency | HIGH | spec.md FR-006 vs plan.md Phase 0/Strategy + tasks.md T005 | FR-006 declara "Operacao manual via Supabase SQL editor (uma vez)" para `CREATE EXTENSION vector`. Plano e T005 implementam como migration idempotente `20260601000006_create_pgvector_extension.sql`. Caminho real diverge da spec | Reescrever FR-006: "Sistema MUST aplicar migration idempotente `CREATE EXTENSION IF NOT EXISTS vector;` durante `dbmate up`. Habilitacao previa via Supabase managed plan e pre-requisito ops" |
| F4 | Ambiguity | MEDIUM | spec.md FR-013 | Texto: "validar tamanho `1 <= size_bytes <= rag.max_upload_mb`". Comparacao mistura unidades (bytes vs megabytes) sem conversao explicita. Implementador pode tratar `max_upload_mb` como bytes | Substituir por `1 <= size_bytes <= rag.max_upload_mb * 1024 * 1024` ou explicitar conversao |
| F5 | Inconsistency | MEDIUM | spec.md FR-021/FR-055 vs US-1 acceptance scenario | FR-021 diz "primeiros 10 chunks" preview, FR-055 confirma "primeiros 10". US-1 acceptance test #4 menciona "primeiros 3 chunks no detalhe". T060 implementa via `useDocumentChunks(documentId, 3)` (limite 3, divergente) | Padronizar limite de preview: `?limit` default 10 com seed UI default 3 (claro); ou ajustar T060 para 10 |
| F6 | Coverage Gap | MEDIUM | spec.md FR-075 vs tasks.md | FR-075 exige Trace Explorer renderizar `source_name = "(deleted)"` quando JOIN nulo. Trace Explorer e UI do epic 008 — nenhuma task em 012 toca aquele componente. Risco: FR-075 silenciosamente nao implementado | Adicionar task em Phase 5 ou Polish para ajustar componente do Trace Explorer (epic 008) com fallback de JOIN; OR registrar FR-075 como dependencia de epic 008 follow-up |
| F7 | Underspecification | MEDIUM | spec.md FR-073 + tasks.md T029 | FR-073 exige quota check pre-processamento e atomic-replace deve "deduzir chunks antigos do calculo (atomic: nao bloqueia replace)". T029 lista "(4) quotas pre-check (FR-073, retorna 413 com replace-aware delta calculation)" sem detalhar formula. Concorrencia entre 2 uploads diferentes pode driftar contagem | Especificar formula em FR-073 ou data-model.md: `effective_chunks = current_chunks - chunks_of_existing_with_same_source_name + estimated_new_chunks`. Garantir leitura sob `pg_advisory_xact_lock` (T020) |
| F8 | Inconsistency | LOW | tasks.md handoff "92 tasks" | Handoff bloco diz "92 tasks (T001-T092 + T1100-T1105)". Total real = 92 + 6 = 98. Pequeno mismatch numerico | Atualizar handoff para "98 tasks (T001-T092 base + T1100-T1105 deployment smoke)" |
| F9 | Ambiguity | LOW | spec.md FR-044 vs plan.md | `min_distance_threshold` listado no schema YAML como `float?` em FR-044, mas Sessao 2026-04-24 deferiu para 012.1 ("Threshold `rag.min_distance_threshold` per-tenant... para 012.1"). Aceitar campo no schema sem implementar uso pode confundir ops | Marcar campo como `# reserved for 012.1` no schema example T011 + omitir do RagConfig pydantic em T009 ate ativacao real |
| F10 | Underspecification | LOW | spec.md SC-006 | "ResenhAI agente cita chunk em respostas reais... medido via match parcial entre `messages.content` outbound e `knowledge_chunks.content`". Match parcial = ? (substring? n-gram? embedding similarity?). Mensuracao subjetiva | Definir threshold concreto: ex. "trigram Jaccard >=0.3 OR substring >=15 chars contiguous" |
| F11 | Inconsistency | LOW | plan.md "Storage" + tasks.md T008 | Plan diz bucket `knowledge` provisionavel via "supabase CLI / SQL". T008 implementa script Python `20260601000009_create_knowledge_storage_bucket.py` rodado por `dbmate up --migrations-dir plugin OR script post-migrate.py`. Caminho de execucao e ambiguo | Decidir entre (a) supabase CLI (declarativo) ou (b) script Python idempotente — atualizar plan + T008 |
| F12 | Ambiguity | LOW | spec.md FR-026 vs FR-037 | FR-026: embedder usa `model=text-embedding-3-small` (hardcoded). FR-037: tool MUST embedar query "com mesmo `model` do tenant". Tenant nao tem modelo configuravel em v1 (constante). Texto sugere flexibilidade que nao existe | Reescrever FR-037: "embedar query usando `documents.embedding_model` do tenant alvo (uniforme em v1, lock-in)" |
| F13 | Duplication | LOW | spec.md FR-040 vs FR-071 | Ambos exigem Safety Layer A validar chunks antes do envio ao LLM, com mesma logica e mesmo log. Redundancia | Consolidar em FR-040; FR-071 referencia FR-040 |
| F14 | Underspecification | LOW | spec.md FR-074 | "MIN_CHUNK_TOKENS=10" mencionado em edge cases mas constante nao referenciada formalmente em FR-022/FR-023 (chunker spec). T016 implementa | Adicionar referencia explicita a `MIN_CHUNK_TOKENS=10` em FR-022 (chunker MUST descartar/mergear chunks <10 tokens) |
| F15 | Coverage Gap | LOW | tasks.md vs Phase 11 ordering | T1100-T1105 em Phase 11 (Deployment Smoke) declarado como "Gate ultimo antes de rollout T092". Mas Phase 10 lista T092 (rollout) na lista, e Phase 11 segue depois. Ordem diz Phase 11 antes de T092 mas pratica seria executar T1100-T1105 antes | Mover T092 para Phase 11 (apos T1105) ou explicitar dependencia direta `T092 depends on T1105` |

---

## Coverage Summary

### Requirements with task mapping (selecao representativa — 76 FRs total)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 (table documents) | Yes | T006 | OK |
| FR-002 (table knowledge_chunks) | Yes | T007 | OK |
| FR-003 (HNSW index) | Yes | T007 | OK |
| FR-005 (RLS) | Yes | T006, T007, T019, T086 | Strong coverage including invariant |
| FR-006 (extension vector) | Yes | T005 | Implementacao diverge da spec — ver F3 |
| FR-007 (Storage bucket) | Yes | T008 | Caminho ambiguo — ver F11 |
| FR-011 (POST upload) | Yes | T029, T030 | OK |
| FR-013 (size validation) | Yes | T029, T027 | Ambiguidade unidades — ver F4 |
| FR-015 (atomic replace) | Yes | T020, T028, T030 | OK |
| FR-016 (advisory lock) | Yes | T020 | OK |
| FR-018 (GET list) | Yes | T054, T050 | OK |
| FR-019 (DELETE) | Yes | T055, T051 | OK |
| FR-020 (raw signed URL) | Yes | T056, T052 | OK |
| FR-021 (chunks preview) | Yes | T057, T053, T060 | Inconsistencia limite — ver F5 |
| FR-022/FR-023 (chunker) | Yes | T012, T016 | OK |
| FR-024 (max_chunks_per_doc) | Yes | T016 | OK |
| FR-026/FR-027/FR-028/FR-029 (embedder) | Yes | T013, T017 | OK |
| FR-030..FR-033 (Bifrost) | Yes | T021, T022, T023 | OK |
| FR-034..FR-040 (search_knowledge tool) | Yes | T039, T043, T044 | OK |
| FR-041 (pipeline filter tools) | Yes | T046 | OK |
| FR-043 (eval rag_used) | Yes | T048 | OK |
| FR-044..FR-047 (feature flag) | Yes | T009, T010, T011, T075 | OK |
| FR-048..FR-050 (per-agent toggle) | Yes | T064, T066, T067 | OK |
| FR-051..FR-057 (Admin UI) | Yes | T033-T037, T058-T061 | OK |
| FR-058..FR-061 (CLI reembed) | Yes | T070, T071 | OK |
| FR-062 (OTel baggage) | Partial | T017, T043 (spans) | Propagacao via instrumentation existente — implicito |
| FR-063 (Prometheus metrics) | Yes | T025 | OK |
| FR-064 (structlog) | Yes | T026 | OK |
| FR-065 (Trace Explorer) | Yes | T039 (test) | UI epic 008 reuse |
| FR-066/FR-067 (SAR cascade) | Yes | T062 | OK |
| **FR-068 (cross-tenant audit)** | **No** | — | **Gap — ver F1** |
| FR-069..FR-071 (security) | Yes | T040, T043, T045 | F13 dup |
| **FR-072 (source_hash SHA-256)** | **No** | — | **Gap — ver F2** |
| FR-073 (quotas) | Yes | T029, T027 | Subspec — ver F7 |
| FR-074 (zero chunk reject) | Yes | T030, T027 | OK |
| **FR-075 (Trace deleted rendering)** | **No** | — | **Gap — ver F6** |
| FR-076 (audit logs canonical) | Yes | T026 | F1 expansao necessaria |

### Success Criteria mapping (12 SCs)

| SC | Buildable in epic? | Mapped tasks |
|----|---------------------|--------------|
| SC-001 (onboarding <30 min) | Outcome metric | Smoke T038, T049, T092 |
| SC-002 (zero leak) | Yes | T019, T042, T086 |
| SC-003 (upload <=15s p95) | Yes | T091 (baseline), metric T025 |
| SC-004 (search <=2s p95) | Yes | T091, metric T025 |
| SC-005 (custo <=R$0.50) | Outcome | T079 audit script |
| SC-006 (chunk citation >=20%) | Outcome | Match logic underspecified — ver F10 |
| SC-007 (revert <=60s) | Yes | T077 |
| SC-008 (distance top1) | Outcome | metric via T039 span |
| SC-009 (eval correlation) | Outcome | T048 hook |
| SC-010 (spend tracking 100%) | Yes | T078, T079 |
| SC-011 (quota zero false-positive) | Yes | metric T025 |
| SC-012 (audit completeness) | Yes | T026 (gap F1 ameaca SC-012) |

### Unmapped Tasks

Nenhuma task sem requisito mapeado. Todas T001-T092 + T1100-T1105 trace para FR/SC ou trabalho de infraestrutura (setup, fixtures, dirs).

---

## Constitution Alignment

Plan.md Section "Constitution Check" auto-avalia 9 principios — todos PASS. Audit independente desta analise:

- Principio I (Pragmatism): Confirmado — zero novas libs Python/TS.
- Principio VII (TDD): Confirmado — tasks T012-T014, T019, T027-T028, T039-T042, T050-T053, T064-T065, T070, T073-T074, T078 escritas antes de implementacoes (TDD red->green).
- Principio IX (Observability): Audit canonico em FR-076 (5 eventos) **incompleto** vs FR-068 (cross-tenant access nao listado). Risco menor de violacao em compliance audit. Ver F1.

Nenhuma violacao CRITICAL.

---

## Metrics

- **Total Functional Requirements**: 76 (FR-001..FR-076)
- **Total Success Criteria**: 12 (SC-001..SC-012)
- **Total Tasks**: 98 (T001-T092 base + T1100-T1105 deployment smoke)
- **Coverage** (FRs com >=1 task mapeada): ~96% (73/76 com cobertura clara; 3 gaps confirmados: FR-068, FR-072, FR-075)
- **Ambiguity findings**: 3 (F4, F9, F12)
- **Inconsistency findings**: 4 (F3, F5, F8, F11)
- **Coverage gap findings**: 4 (F1, F2, F6, F15)
- **Underspecification findings**: 3 (F7, F10, F14)
- **Duplication findings**: 1 (F13)
- **Critical issues**: 0
- **High issues**: 3 (F1, F2, F3)
- **Medium issues**: 4 (F4, F5, F6, F7)
- **Low issues**: 8

---

## Next Actions

**No CRITICAL issues** — implementacao pode seguir, mas resolver os 3 HIGH antes de iniciar Phase 2 reduz retrabalho:

1. **F1 (FR-068)**: editar tasks.md T026 para incluir helper `emit_cross_tenant_access` e adicionar callsite em T054. ~5 min de edit.
2. **F2 (FR-072)**: editar tasks.md T030 para chamar `hashlib.sha256(file_bytes).hexdigest()` antes do INSERT. ~5 min de edit.
3. **F3 (FR-006)**: editar spec.md FR-006 para alinhar com implementacao via migration idempotente. ~2 min de edit.

**MEDIUM issues** podem ser resolvidos durante PR-A (F4, F5, F6, F7) — nao bloqueiam Phase 2.

**LOW issues** sao polish opcional; agendar para PR-C ou backlog 012.1.

Comando sugerido para correcao automatica:

```
/speckit.specify (refinement) — corrigir FR-006 conforme F3
# editar tasks.md manualmente para F1, F2 (atualizar T026, T030)
```

Apos correcoes: pode avancar para `/speckit.implement` com confianca.

---

## Remediation Offer

Posso preparar patches concretos (diffs) para os 3 HIGH (F1, F2, F3) e 2 MEDIUM (F4, F5) — apenas confirmar e aplico via Edit tool em uma proxima rodada. Os demais (LOW, F7, F6) requerem decisao de produto/arquitetura antes de remediar.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Analise pre-implementacao concluida. 0 CRITICAL, 3 HIGH (FR-068 cross-tenant audit gap, FR-072 source_hash sem task, FR-006 manual vs migration mismatch), 4 MEDIUM, 8 LOW. Cobertura geral 96% (73/76 FRs mapeados). TDD obrigatorio confirmado. RLS + cross-tenant invariants tem cobertura forte (T019, T042, T086). Recomenda-se resolver 3 HIGHs antes de Phase 2 — patches simples (~12 min total). Implementacao pode seguir; cuidado especial em (a) compute SHA-256 no upload, (b) audit cross-tenant access, (c) realinhar FR-006 com migration approach."
  blockers: []
  confidence: Alta
  kill_criteria: "Se F1/F2 nao forem corrigidos pre-implement, FR-068/FR-072 ficarao silenciosamente nao implementados — qa/reconcile detectara mas re-trabalho sera maior; F3 (spec vs migration) pode causar confusao em ops durante deploy se nao alinhado."
