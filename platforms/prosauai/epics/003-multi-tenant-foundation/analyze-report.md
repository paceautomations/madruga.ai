# Specification Analysis Report — 003 Multi-Tenant Foundation

**Date**: 2026-04-10  
**Epic**: `epic/prosauai/003-multi-tenant-foundation`  
**Artifacts Analyzed**: spec.md (273 lines), plan.md (441 lines), tasks.md (359 lines)  
**Supporting Artifacts**: data-model.md, contracts/webhook-api.md, contracts/tenant-config.md, research.md, pitch.md

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | SC-011 / tasks.md | SC-011 define p99 < 100ms para webhook acceptance, mas **nenhuma task mede ou valida esse critério**. Não há task de benchmark, load test, ou instrumentação de latência. | Adicionar task em Phase 10 (Polish): "Run benchmark de latência com N requests concorrentes via `wrk` ou `httpx` async, verificar p99 < 100ms". Alternativamente, remover SC-011 se medição não for viável na Fase 1 (2 tenants internos). |
| C2 | Coverage | LOW | spec.md Edge Cases / tasks.md | Edge case "Webhook com body vazio ou JSON inválido → 400" não tem task de teste explícita. T011 (test_auth.py) e T028 (test_webhook.py) podem cobrir implicitamente, mas não é declarado. | Adicionar caso de teste explícito em T028 (test_webhook.py): POST com body vazio, POST com JSON inválido — verificar HTTP 400. |
| C3 | Coverage | LOW | spec.md Edge Cases / tasks.md | Edge case "`groups.upsert` com lista vazia em `data`" não tem fixture capturada nem teste explícito. | Adicionar fixture sintética mínima `groups_upsert_empty_data.input.json` ou incluir caso em T024 (test_formatter.py). |
| F1 | Inconsistency | MEDIUM | plan.md §2.2 / tasks.md | **Numeração de tasks divergente.** Plan §2.2 referencia tasks com numeração do pitch (T1-T21, T6b-T6j, T11b-T11f). tasks.md usa T001-T046. Não há tabela de mapeamento explícita. Implementador precisa inferir correspondência. | Adicionar nota no topo de tasks.md: "Task IDs T001-T046 substituem a numeração do pitch (T0-T21). Mapeamento: T002=pitch.T1, T003=pitch.T2, ..." ou atualizar plan.md §2.2 para referenciar IDs do tasks.md. |
| F2 | Inconsistency | MEDIUM | pitch.md / tasks.md T030 | Pitch menciona `append_or_immediate()` em T11e como método do `DebounceManager` que também precisa de `tenant_id`. tasks.md T030 menciona apenas `append()`. Se `DebounceManager` tem `append_or_immediate()`, sua assinatura também precisa ser atualizada mas não está explícita em tasks.md. | Verificar se `append_or_immediate()` existe no código atual do epic 001. Se sim, adicionar sua atualização de assinatura explicitamente em T030 ou criar sub-task. |
| F3 | Inconsistency | LOW | pitch.md / spec.md / data-model.md | **Contagem de campos do ParsedMessage varia**: spec diz "22 campos" (FR-023), pitch diz "12→22 campos", data-model lista 28 campos no schema (excluindo `sender_key` property). A discrepância é porque "22 campos" conta campos novos + existentes sem o property, enquanto data-model conta todos os campos do BaseModel incluindo defaults. | Uniformizar para "28 campos" (contagem real no schema) ou "22+ campos" (já usado em alguns lugares). Atualizar FR-023 para "22+ campos" se quiser manter margem para campos opcionais adicionais. |
| D1 | Duplication | LOW | tasks.md T005 / T041 | T005 diz "remove 7 tenant-specific fields" do Settings, incluindo `tenant_id`. T041 diz "Remove `tenant_id` field from Settings class" — com nota "already handled if T005 was thorough". Se T005 for completo, T041 é redundante. | Manter T041 como **verificação** (grep por `settings.tenant_id` em todo o codebase), não como task de implementação. Ajustar descrição: "Verify T005 removed `tenant_id` — grep for remaining references". |
| A1 | Ambiguity | MEDIUM | spec.md Edge Cases / FR-019 | Edge case diz: "`message_id` ausente no payload: o parser **sintetiza um ID** a partir de campos disponíveis **ou rejeita** com log de warning." O "ou" é ambíguo — qual comportamento prevalece? Para `messages.upsert` sem `key.id`, sintetizar ou rejeitar? A fórmula de síntese (`{instance_name}-{event}-{timestamp_epoch_ms}`) é definida apenas para `group-participants.update`. | Clarificar: (a) `messages.upsert` sem `key.id` → rejeitar com warning (é mandatório na Evolution); (b) `groups.upsert` sem key → sintetizar; (c) `group-participants.update` sem key → sintetizar com fórmula definida. Remover o "ou" ambíguo. |
| A2 | Ambiguity | LOW | FR-019 / clarifications | Fórmula `{instance_name}-{event}-{timestamp_epoch_ms}`: se dois eventos `group-participants.update` ocorrem no mesmo milissegundo para a mesma instância, o `message_id` sintetizado colide. Clarificação diz "determinístico, único dentro do TTL de 24h" — mas eventos rápidos podem colidir. | Probabilidade extremamente baixa com resolução de milissegundo. Aceitar como risco documentado. Se preocupante, adicionar random suffix: `{instance_name}-{event}-{timestamp_epoch_ms}-{random4}`. |
| A3 | Ambiguity | LOW | spec.md Edge Cases | "Redis indisponível durante check de idempotência: fail-open" está definido para idempotência (FR-014). Mas **debounce** também depende de Redis — comportamento fail-open/fail-closed para debounce quando Redis cai não está especificado. | Documentar comportamento de debounce com Redis indisponível. Sugestão: fail-open (enviar imediatamente sem agrupar) com log warning, consistente com FR-014. |
| U1 | Underspecification | LOW | spec.md / tasks.md | Spec define "Tenant com `enabled: false` → 404" mas não especifica se a resposta 404 é idêntica a "tenant desconhecido" (sem leak de informação que o tenant existe). Pitch menciona "sem leak de informação" mas não é um FR explícito. | Se privacy importa, garantir que response body para disabled=404 e unknown=404 são idênticos: `{"detail": "Unknown instance"}`. Adicionar nota em T012. |
| U2 | Underspecification | LOW | tasks.md T014 | T014 (test_captured_fixtures.py) diz "partial assertion — ignore `_*` keys". O comportamento para campos no expected.yaml que têm valor `null` ou estão ausentes não é especificado. Loader compara apenas campos **presentes**? Ou campo ausente no expected = "qualquer valor aceito"? | Especificar: campos presentes no expected.yaml devem bater exatamente; campos ausentes são ignorados (qualquer valor aceito). Documentar convenção no header do test file. |
| E1 | Coverage | LOW | tasks.md Phase 5 / spec.md US3-AS4 | US3 Acceptance Scenario 4 diz "flush callback resolve tenant pela chave e usa credenciais específicas". T032 implementa isso, mas nenhum teste unitário valida especificamente que `_make_flush_callback` resolve o tenant correto e cria `EvolutionProvider` com credenciais certas. T028 (test_webhook.py) cobre integração mas não unit test do flush. | Adicionar caso de teste em T028 ou criar test auxiliar em test_debounce.py que valida flush callback com 2 tenants — verifica que tenant A recebe credenciais de A, não de B. |

---

## Coverage Summary

### Requirements → Tasks

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (YAML loader) | ✅ | T003 | |
| FR-002 (indexed lookup) | ✅ | T003 | |
| FR-003 (reject invalid YAML) | ✅ | T003 | |
| FR-004 (reject missing env) | ✅ | T003 | |
| FR-004b (reject duplicates) | ✅ | T003, T009 | |
| FR-004c (no hot reload) | ✅ | T003 | By design |
| FR-005 (Tenant fields) | ✅ | T002 | |
| FR-006 (resolve by instance_name) | ✅ | T012 | |
| FR-007 (404 unknown) | ✅ | T012, T011 | |
| FR-008 (constant-time compare) | ✅ | T012, T011 | |
| FR-009 (401 invalid) | ✅ | T012, T011 | |
| FR-010 (no HMAC) | ✅ | T012, T013 | |
| FR-011 (idempotency check) | ✅ | T006, T031 | |
| FR-012 (Redis SET NX EX) | ✅ | T006 | |
| FR-013 (duplicate response) | ✅ | T031 | |
| FR-013b (processed response) | ✅ | T031 | |
| FR-014 (fail-open Redis) | ✅ | T006, T010 | |
| FR-015 (13 message types) | ✅ | T016 | |
| FR-016 (3 sender formats) | ✅ | T017 | |
| FR-017 (mentionedJid top-level) | ✅ | T020 | |
| FR-018 (groups.upsert lista) | ✅ | T018 | |
| FR-019 (group-participants.update) | ✅ | T019 | |
| FR-020 (quotedMessage) | ✅ | T021 | |
| FR-021 (reactionMessage) | ✅ | T022 | |
| FR-022 (ignore irrelevant) | ✅ | T023 | |
| FR-023 (22+ field schema) | ✅ | T015 | |
| FR-024 (route_message(msg,tenant)) | ✅ | T029 | |
| FR-025 (3-strategy mention) | ✅ | T029, T027 | |
| FR-026 (don't change enum) | ✅ | T029 | |
| FR-027 (tenant-prefixed keys) | ✅ | T030, T026 | |
| FR-028 (sender_key) | ✅ | T030 | |
| FR-029 (flush resolves tenant) | ✅ | T032 | |
| FR-030 (no ports) | ✅ | T035 | |
| FR-031 (port 8050) | ✅ | T005, T035 | |
| FR-032 (volume mount) | ✅ | T035 | |
| FR-033 (remove tenant_id Resource) | ✅ | T039 | |
| FR-034 (per-span tenant_id) | ✅ | T031, T030 | |
| FR-035 (preserve SpanAttributes) | ✅ | T040 | |
| FR-036 (structlog contextvars) | ✅ | T031 | |
| FR-037 (26 fixture tests) | ✅ | T014 | |
| FR-038 (input+expected pairs) | ✅ | T014 | |
| FR-039 (delete synthetic fixture) | ✅ | T025 | |
| FR-040 (cross-tenant test) | ✅ | T028 | |

### Success Criteria → Tasks

| SC Key | Has Task? | Task IDs | Notes |
|--------|-----------|----------|-------|
| SC-001 (100% webhooks aceitos) | ✅ | T012, T031 | |
| SC-002 (26 fixtures passam) | ✅ | T014, T044 | |
| SC-003 (13 tipos reconhecidos) | ✅ | T016, T024 | |
| SC-004 (2 tenants isolados) | ✅ | T028, T031 | |
| SC-005 (zero duplicatas) | ✅ | T006, T033, T034 | |
| SC-006 (zero portas expostas) | ✅ | T035 | |
| SC-007 (onboarding < 15min) | ✅ | T042 | Soft metric |
| SC-008 (zero Settings no router) | ✅ | T029 | `grep -c` validation |
| SC-009 (diff ≤ 30 lines) | ✅ | T029 | Soft constraint |
| SC-010 (tenant_id nos spans) | ✅ | T031, T039, T040 | |
| SC-011 (p99 < 100ms) | ⚠️ **GAP** | — | Nenhuma task de benchmarking |

### Unmapped Tasks

Nenhuma task órfã — todas as 46 tasks mapeiam para pelo menos um FR, SC, ou edge case.

---

## Constitution Alignment

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism + Simplicity | ✅ PASS | Alternativa D (multi-tenant estrutural, 2 tenants) é pragmática. Schema único para 3 eventos evita over-engineering. |
| II. Automate Repetitive | ✅ PASS | Fixture-driven testing automatiza validação. TenantStore loader automatiza interpolação de env vars. |
| III. Structured Knowledge | ✅ PASS | 26 fixtures como single source of truth. decisions.md acumula micro-decisões. 5 artifacts de design. |
| IV. Fast Action + TDD | ✅ PASS | Rip-and-replace (não incremental). Testes antes da implementação em cada fase (TDD). |
| V. Alternatives + Trade-offs | ✅ PASS | research.md documenta ≥3 alternativas por decisão com pros/cons. Plan §2.4 justifica rip-and-replace vs incremental. |
| VI. Brutal Honesty | ✅ PASS | Pitch documenta sem sugarcoating: "100% rejeitados", "50% silenciados". |
| VII. TDD | ✅ PASS | tasks.md coloca testes ANTES da implementação em cada fase (T008-T011 antes de T012; T014 antes de T015-T023). |
| VIII. Collaborative Decision | ✅ PASS | 18+ decisões documentadas no pitch. 5 clarificações na spec. |
| IX. Observability + Logging | ✅ PASS | FR-033-036 cobrem observabilidade. structlog + OpenTelemetry. tenant_id per-span. |

**Nenhuma violação de constituição encontrada.**

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 43 |
| Total Success Criteria | 11 |
| Total Tasks | 46 |
| Total User Stories | 7 |
| Total Edge Cases | 11 |
| FR Coverage % | **100%** (43/43 FRs com ≥1 task) |
| SC Coverage % | **91%** (10/11 SCs com ≥1 task) |
| Ambiguity Count | 3 |
| Duplication Count | 1 |
| Critical Issues | 0 |
| High Issues | 0 |
| Medium Issues | 4 |
| Low Issues | 8 |
| Total Findings | 12 |

---

## Next Actions

### No CRITICAL or HIGH issues found. Epic is ready for `/speckit.implement`.

**Recommended before implementation (MEDIUM issues):**

1. **C1 (SC-011 p99 gap)**: Decidir se SC-011 será medida na Fase 1 ou adiada. Se medir: adicionar task de benchmark em Phase 10. Se adiar: anotar SC-011 como `[ESTIMAR]` e remover como gate de sucesso.

2. **F1 (task numbering)**: Adicionar nota de mapeamento entre numeração do pitch e do tasks.md — reduz confusão durante implementação. Alternativa: atualizar plan.md §2.2 para usar IDs do tasks.md.

3. **F2 (append_or_immediate)**: Verificar se `DebounceManager.append_or_immediate()` existe no código atual e, se sim, garantir que T030 cobre sua atualização de assinatura.

4. **A1 (message_id ausente)**: Clarificar o "ou" ambíguo no edge case de `message_id` ausente — especificar comportamento por tipo de evento.

**Opcional (LOW issues — podem ser resolvidos durante implementação):**

5. C2, C3: Adicionar casos de teste para edge cases de body vazio e groups.upsert com lista vazia.
6. D1: Ajustar T041 para ser verificação, não implementação.
7. U1: Garantir response 404 idêntica para disabled e unknown tenants.
8. U2: Documentar convenção de partial assertion no test loader.

**Sugestão de comando**: Após resolver os itens MEDIUM (opcionalmente), prosseguir com:
```
/speckit.implement prosauai 003-multi-tenant-foundation
```

---

## Offer of Remediation

Os 4 itens MEDIUM podem ser resolvidos com edits cirúrgicas em spec.md e tasks.md. Nenhum requer mudança arquitetural ou replanejamento. O epic está em excelente forma para implementação.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise pré-implementação concluída. 0 CRITICAL, 0 HIGH, 4 MEDIUM, 8 LOW. Coverage 100% em FRs, 91% em SCs (SC-011 sem task de benchmark). Constituição sem violações. Epic pronto para implementação — itens MEDIUM são melhorias opcionais, não bloqueadores."
  blockers: []
  confidence: Alta
  kill_criteria: "Se novos requisitos surgirem ou se a verificação do append_or_immediate (F2) revelar gap significativo na cobertura de debounce."
