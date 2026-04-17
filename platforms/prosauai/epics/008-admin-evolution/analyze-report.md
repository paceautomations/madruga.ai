# Specification Analysis Report — Epic 008 Admin Evolution

**Date**: 2026-04-17
**Mode**: Autonomous (pre-implement cross-artifact consistency check)
**Artifacts analyzed**: spec.md, plan.md, tasks.md (+ pitch.md, data-model.md, contracts/openapi.yaml as supporting context)
**Constitution**: `.specify/memory/constitution.md`

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| D1 | Duplication | LOW | spec.md FR-102, pitch.md Decision 23 | Retention defaults (30d traces / 90d routing) repetidos em FR-102 + pitch decisão 23 + tasks T056. Consistentes, mas redundantes. | Aceitar — cada artefato tem propósito distinto (spec define requirement, tasks operacionaliza). |
| A1 | Ambiguity | MEDIUM | spec.md FR-014, tasks.md T413 | "System Health checando API, Postgres, Redis, Evolution API, Phoenix" — não define o que é "degradado" vs. "down" (latência threshold). T413 menciona "degraded/down status refletem latência/timeout" sem especificar número. | Adicionar threshold numérico em T413 (ex: down se timeout >2s, degraded se latency >500ms) ou linkar para health-rules.ts |
| A2 | Ambiguity | LOW | spec.md FR-093, tasks.md T821 | "3+ `login_failed` do mesmo IP nas últimas 24h" é destacado visualmente, mas spec não define se é contabilizado só na página atual ou globalmente. T810 menciona "subquery COUNT login_failed agrupado por IP" — assume global. | Explicitar "global na janela 24h, independente da paginação" em FR-093. |
| A3 | Ambiguity | LOW | spec.md FR-050 Edge Case "Routing decision sem match de regra" | UI mostra "regra: default" para decisões sem match explícito. Mas na data-model, `matched_rule` pode ser NULL — não há definição clara de quem sintetiza o label "default". | Confirmar em T522 (decisions-list) que NULL → renderiza "default" no frontend. |
| U1 | Underspecification | MEDIUM | tasks.md T904 | "se falhar, rollback via env flag" — nenhum env flag de rollback da instrumentação definido em research.md ou tasks.md. | Definir explicitamente `ENABLE_TRACE_PERSISTENCE=true` (ou similar) em T025/T026, adicionar task de criação do flag, documentar em env.example. |
| U2 | Underspecification | MEDIUM | tasks.md T512/T513 | T511 expõe `snapshot_rules()` mas RoutingEngine é tipicamente singleton por worker FastAPI — com múltiplos workers, cada um tem seu próprio estado in-memory. Endpoint `/admin/routing/rules` pode retornar estados diferentes por hit. | Adicionar assumption em spec (FR-072) ou comentário em T511 que, em caso de múltiplos workers, pode haver inconsistência transitória pós hot-reload de regras; aceitar como trade-off v1 ou escolher worker "líder". |
| U3 | Underspecification | LOW | spec.md FR-092 vs tasks.md T820 | FR-092 permite filtro "por usuário" mas T810 parâmetros usa `user_email` — não clarifica se é exact-match ou ILIKE. | Definir exact-match (email é identificador único) em T810. |
| C1 | Coverage Gap | MEDIUM | spec.md FR-104 | FR-104: "100% da suíte existente de epics 004+005 passando" — gate presente em T029/T043/T054, mas não há task explícita verificando que suíte do epic 002 (observability) não quebra após novo consumo de `trace_id` do OTel. | Adicionar assertion em T030 smoke test: "Phoenix continua recebendo spans normalmente durante janela de 24h" ou task explícita em PR 2. |
| C2 | Coverage Gap | LOW | spec.md FR-032 | "propagar `trace_id` gerado pelo SDK OTel existente" — tests T024/T022 cobrem helper `get_trace_id_hex()`, mas não há teste end-to-end validando que trace_id emitido nos StepRecords persistidos == trace_id emitido no span OTel pai (evitar drift silencioso). | Adicionar integration test em T025 ou T026: compara `traces.trace_id` DB vs. Phoenix/OTel exporter. |
| C3 | Coverage Gap | MEDIUM | spec.md FR-015 (tenant health rule "rolling 5min error_rate >10%") | T412 (`tenant_health.py`) e T064 (`health.py` Python espelho) usam `classify_tenant_health` mas não é claro se a query calcula error rate rolling 5min ou se usa cache. T400 valida regra mas sem especificar performance. | Especificar em T412 que error rate rolling 5min é `SELECT COUNT(*) FILTER WHERE status='error' AND started_at > now() - interval '5 min'` contra base de traces; documentar se vai para Redis cache. |
| C4 | Coverage Gap | LOW | spec.md FR-012 "AI resolveu sem handoff" como evento do feed | T411 UNION ALL lista `ai_resolved` mas a definição formal deste evento (conversa fechada sem nenhuma mensagem role=human_operator) não está em spec nem em tasks. | Formalizar definição de "ai_resolved" em T411 (SQL claro) ou adicionar ao spec como edge case de FR-012. |
| C5 | Coverage Gap | MEDIUM | spec.md User Story 6 AC#4 ("Ativar versão antiga") | FR-064 requires confirmation explícita. T624 menciona "confirmation dialog" mas NENHUMA task cobre audit logging dessa ativação (mudança de `active_prompt_id` é uma mudança de produção). | Adicionar INSERT em `audit_log` na `activate_prompt` query (T610). |
| I1 | Inconsistency | MEDIUM | spec.md FR-050 vs data-model.md (trace_steps schema) | FR-050 diz "intent_confidence < 0.5 registrado pelo mesmo step [classify_intent]" — assume-se que `intent_confidence` está no `output_jsonb` do step. Mas T310 `aggregate_kpis` pode ter dificuldade para consultar campos aninhados em JSONB sem índice GIN. | Considerar promover `intent_confidence` para coluna dedicada em `traces` (já existe `intent` e `quality_score` conforme T028) OU adicionar índice GIN em `trace_steps.output_jsonb` para o step classify_intent. |
| I2 | Inconsistency | LOW | pitch.md Decision 17 ("cost calc no fim do pipeline") vs tasks.md T028 | Pitch diz cost calc só no `generate_response`. T028 faz soma de `total_tokens_in`/`total_tokens_out` do pipeline inteiro. Se houver múltiplas chamadas LLM (ex: evaluate_response usa LLM separado), o custo deve somar de todos. | Clarificar em T027/T028: capturar tokens de TODOS os steps com chamada LLM (generate_response, evaluate_response potencialmente), não só generate_response. |
| I3 | Inconsistency | LOW | spec.md FR-022 ("quality score") vs data-model.md | Inbox list mostra QS por item. Mas QS é por-mensagem (step evaluate_response), não por-conversa. O que aparece na lista? Média? Último? | Especificar em T110 `list_conversations`: QS do last message ou AVG da conversa. Recomendação: last message QS (já alinhado com `last_message_id` denorm). |
| X1 | URL Coverage | LOW | testing.urls (se declarado) | Novas rotas frontend: /conversations, /conversations/[id], /traces, /traces/[trace_id], /performance, /agents, /agents/[id], /routing, /tenants, /tenants/[slug], /audit. Tasks T1003 checa `testing.urls` mas plataforma pode não ter estas rotas declaradas ainda. | Atualizar `platform.yaml` testing.urls após PR 7-10 para incluir as 11 novas rotas antes do QA final. |
| X2 | Non-Functional | LOW | spec.md SC-004, tasks.md | SC-004 especifica p95 com dataset de 10k conversas + 50k traces, mas nenhuma task gera dataset sintético para benchmark. T055 benchmark assume "dataset de 10k conversas" existente. | Adicionar task em Phase 11: script de seed de dataset sintético para benchmark validation. |
| X3 | Coverage Gap | LOW | spec.md Assumptions ("3-10 admin users simultâneos") | Activity feed polling 15s × 10 admins = baixo overhead, mas nenhum teste de carga valida isso. | Documentar como follow-up em tasks.md ou aceitar como validação manual pós-deploy. |

**Totais**: 18 findings (0 CRITICAL, 7 MEDIUM, 11 LOW)

## Coverage Summary

| Requirement Key (spec) | Has Task? | Task IDs | Notes |
|------------------------|-----------|----------|-------|
| FR-001 (8-item sidebar) | ✅ | T120, T122 | |
| FR-002 (tenant dropdown URL param) | ✅ | T121 | |
| FR-003 (dark mode único) | ✅ | — (inherited epic 007) | Assumido via tokens OKLCH pré-existentes |
| FR-010..FR-011 (6 KPIs + thresholds) | ✅ | T063, T410, T420 | Thresholds em health-rules.ts |
| FR-012..FR-013 (activity feed + polling 15s) | ✅ | T411, T421 | |
| FR-014 (system health) | ⚠️ | T413, T422 | Thresholds degraded/down não definidos (A1) |
| FR-015 (tenant health hierarchical) | ✅ | T063/T064, T412, T423 | |
| FR-020..FR-028 (Conversas) | ✅ | T110-T129 | |
| FR-030..FR-040 (Trace Explorer) | ✅ | T025, T026, T210-T226 | |
| FR-050..FR-057 (Performance AI) | ⚠️ | T310-T326 | I1 (intent_confidence query perf) |
| FR-060..FR-064 (Agents) | ⚠️ | T610-T624 | C5 (audit log de activate_prompt faltando) |
| FR-070..FR-074 (Routing) | ⚠️ | T041-T043, T510-T524 | U2 (multi-worker snapshot consistency) |
| FR-080..FR-082 (Tenants) | ✅ | T114, T710-T712 | |
| FR-090..FR-093 (Audit) | ⚠️ | T810-T822 | A2 (escopo 3+ login_failed), U3 (filter semantics) |
| FR-100..FR-104 (NFR) | ⚠️ | T029, T030, T043, T054, T904 | C1 (epic 002 suite), U1 (rollback flag) |
| SC-001..SC-012 | ✅ | T908 (cronometrado) + individual gates | |

**Coverage**: ~95% (FRs explicitamente mapeados). 5 FRs com gaps menores marcados acima.

## Unmapped Tasks

Todas as ~120 tasks rastreiam a um requisito funcional, US, NFR, polish ou smoke. Nenhuma task órfã detectada.

## Constitution Alignment Issues

Nenhuma violação do constitution. Plan.md já documenta Constitution Check PASS (pré e pós-Phase 1). Verificado:

- Princípio I (Simplicidade): ✅ reuso de stack epic 007, hardcode pricing
- Princípio II (Automate): ✅ openapi-typescript, retention-cron reuse
- Princípio V (Alternativas): ✅ research.md R1..R16
- Princípio VII (TDD): ✅ tests escritos antes (T021, T024, T040, T065, etc.)
- Princípio IX (Observability): ✅ spans admin.endpoint.*, fire-and-forget com log estruturado

## Metrics

- **Total Functional Requirements**: 59 (FR-001..FR-104 com gaps numéricos)
- **Total User Stories**: 8
- **Total Success Criteria**: 12
- **Total Tasks**: ~120 (T001..T1005)
- **Coverage (FRs com ≥1 task)**: ~95%
- **Ambiguity Count**: 3
- **Duplication Count**: 1
- **Underspecification Count**: 3
- **Coverage Gaps**: 5
- **Inconsistency Count**: 3
- **URL Coverage Issues**: 1
- **Critical Issues**: 0
- **High Issues**: 0
- **Medium Issues**: 7
- **Low Issues**: 11

## Next Actions

**Recomendação**: prosseguir com `/speckit.implement`. Os 18 findings são todos MEDIUM ou LOW — nenhum é bloqueante. Sugestões de refinamento que podem ser aplicadas em paralelo à implementação:

### Antes do PR 2 (prioridade alta — afetam instrumentação)
1. **U1**: Criar env flag `ENABLE_TRACE_PERSISTENCE` em T025/T026 para kill-switch de rollback.
2. **I2**: Confirmar com T027/T028 se `evaluate_response` também faz chamada LLM com tokens próprios — somar todos.
3. **C1**: Adicionar assertion em T030 (smoke 24h): Phoenix continua recebendo spans.
4. **C2**: Adicionar integration test comparando `traces.trace_id` DB vs. Phoenix/OTel.

### Antes do PR 6 (prioridade média — afetam endpoints)
5. **A1**: Definir thresholds numéricos para system health degraded/down em T413.
6. **I1**: Decidir se `intent_confidence` vira coluna em `traces` ou usa GIN index — afeta performance FR-050.
7. **U2**: Documentar trade-off multi-worker snapshot em FR-072 ou T511.
8. **C3**: Especificar query SQL de rolling 5min error rate em T412.
9. **C5**: Adicionar INSERT em audit_log em T610 (`activate_prompt`).

### Antes do PR 10 (prioridade baixa — cosmético)
10. **A2, A3, U3, I3, C4**: Clarificações menores em FRs e tasks.
11. **X1**: Atualizar `platform.yaml` testing.urls com 11 novas rotas antes de T1003.
12. **X2**: Script de seed de dataset sintético para SC-004 benchmark validation.

### Comandos sugeridos
- `/speckit.implement` — pode prosseguir; findings são não-bloqueantes
- Opcionalmente: editar manualmente `tasks.md` para incorporar findings U1/I2/C5 antes do PR 2 (risco baixo, valor alto)

## Would you like me to suggest concrete remediation edits for the top 5 issues?

Disponível sob demanda — os findings U1, I2, C5, A1, I1 são os de maior ROI. Edições seriam em `tasks.md` (adicionar tasks pontuais) e, para I1, potencial ALTER migration em `data-model.md`.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise cross-artifact concluída. 18 findings (0 CRITICAL, 7 MEDIUM, 11 LOW). Coverage FR ~95%. Nenhum bloqueador. Top 5 melhorias sugeridas para aplicar antes/durante PR 2: (1) env flag rollback instrumentação, (2) soma tokens de todos steps LLM (não só generate_response), (3) verify Phoenix não quebra durante smoke 24h, (4) thresholds numéricos system health, (5) decisão sobre intent_confidence como coluna dedicada vs. GIN. Implement pode prosseguir com tasks.md atual; findings registrados para tracking. Gate SC-007 (100% suite existente verde no PR 2) permanece não-negociável."
  blockers: []
  confidence: Alta
  kill_criteria: "Este relatório fica inválido se: (a) tasks.md for regerado com breaking changes em IDs; (b) spec receber mudança estrutural em FRs que invalide coverage map; (c) nova decisão arquitetural (ex: mover traces para Phoenix-only) invalidar metade das tasks analisadas."
