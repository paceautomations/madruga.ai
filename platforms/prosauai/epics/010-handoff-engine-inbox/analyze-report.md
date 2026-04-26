# Specification Analysis Report — Epic 010: Handoff Engine + Multi-Helpdesk Integration

**Date**: 2026-04-23
**Branch**: `epic/prosauai/010-handoff-engine-inbox`
**Artifacts analyzed**: `spec.md` (53+ FRs, 14 SCs, 7 User Stories) · `plan.md` (3 PRs, 12 phases) · `tasks.md` (~107 tasks) · `contracts/helpdesk-adapter.md` · `contracts/openapi.yaml` · `data-model.md`
**Constitution version**: 1.1.0

---

## Summary Table

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | HIGH | spec.md FR-017; plan.md §Constraints; contracts/helpdesk-adapter.md §2.1 | HMAC header name conflict: spec/plan diz `X-Webhook-Secret`, contrato implementa `X-Webhook-Signature` | Alinhar para `X-Webhook-Signature` no spec FR-017 e plan.md; corrigir antes de T051 |
| C1 | Coverage Gap | HIGH | spec.md FR-007, FR-038b; tasks.md Phase 2-9 | `rule_match` source (FR-007) e integração `handoff.rules[]` → router (FR-038b) sem nenhuma task implementando o path `rules.py → state.mute()` | Adicionar task T090b: "Estender `core/router/rules.py` para emitir `state.mute_conversation(reason='rule_match')` quando regra listada em `handoff.rules[]` casa" |
| C2 | Coverage Gap | HIGH | spec.md FR-007; tasks.md todas as phases | `safety_trip` source (FR-007) — safety guards do epic 005 mencionados no pitch §Problem mas sem task que bridge guards → `state.mute_conversation(reason='safety_trip')` | Criar task ou marcar explicitamente como out-of-scope PR-A; FR-007 deve listar `safety_trip` como "implementado em epic 005.1" se adiado |
| G1 | URL Coverage | HIGH | platform.yaml testing.urls; spec.md FR-017/028-030; tasks.md T213/T410/T411/T611/T711 | 5 endpoints novos do epic 010 ausentes em `platform.yaml testing.urls`: `/webhook/helpdesk/chatwoot/{tenant_slug}`, `/admin/conversations/{id}/mute`, `.../unmute`, `.../reply`, `/admin/performance/handoff` | Adicionar os 5 endpoints em `platform.yaml testing.urls` antes de Phase 11 Smoke (T1103) |
| I2 | Inconsistency | MEDIUM | spec.md FR-043; contracts/helpdesk-adapter.md §1 | Spec FR-043 lista 5 métodos do Protocol (`on_conversation_assigned`, `on_conversation_resolved`, `push_private_note`, `send_operator_reply`, `verify_webhook_signature`), mas contrato define 6 — faltando `parse_webhook_event()` que é central para o dispatch de eventos Chatwoot | Adicionar `parse_webhook_event()` a FR-043 no spec.md; garante que contract tests T023 cubram o método completo |
| I3 | Inconsistency | MEDIUM | spec.md FR-045; contracts/helpdesk-adapter.md §4; tasks.md T022 | Spec FR-045 diz `get_helpdesk_adapter(helpdesk_type)` mas contrato §4 e task T022 usam `get_adapter(helpdesk_type)` — dois nomes para a mesma função | Escolher um nome. Preferência: `get_adapter` (mais curto, consistente com `ChannelAdapter` do epic 009 `channels/registry.py`). Corrigir FR-045 |
| I4 | Inconsistency | MEDIUM | tasks.md T020, T021 | T020 e T021 ambos marcados `[P]` (parallel) mas criam o mesmo arquivo `apps/api/prosauai/handoff/base.py` — paralelismo físico impossível | Remover `[P]` de T021 (ou fundi-los em T020 como sub-items); T021 deve executar após T020 criar o arquivo |
| U1 | Ambiguity | MEDIUM | spec.md FR-026; spec.md US4 AC2 | FR-026: "mesmo que `message_id` nao case exatamente, mensagens muito recentes do bot nao mutam" implica que **janela 10s sozinha** é suficiente para classificar como echo — contradiz US4 AC2 que exige `message_id presente em bot_sent_messages AND sent_at < 10s` (ambas condições) | Corrigir FR-026 para exigir ambas condições: "echo = `message_id IN bot_sent_messages` E `sent_at < now() - 10s`"; a janela 10s é guard adicional, não substituto |
| U2 | Underspecification | MEDIUM | spec.md FR-039; tasks.md T063 | FR-039 define `default handoff.mode: off` mas nenhuma task testa o comportamento quando o bloco `handoff:` está completamente ausente do `tenants.yaml` (implicitamente torna-se `off`) — config_poller pode falhar silenciosamente | Adicionar cenário em T063: "tenant sem bloco `handoff:` → assume `mode=off`, não levanta KeyError, emite log `tenant_handoff_config_missing_using_default`" |
| C3 | Coverage Gap | MEDIUM | spec.md FR-023; tasks.md T072 | FR-023 "Pipeline MUST continuar rodando content processing mesmo quando `ai_active=false`" — T072 adiciona safety net que pula LLM generation, mas nenhuma task confirma via teste que steps anteriores ao `generate` (incluindo content_process/audio transcription) continuam executando durante handoff | Adicionar asserção em T074 (test_generate_safety_net): "step `content_process` aparece no trace mesmo quando `ai_muted_skip` é emitido" |
| I5 | Inconsistency | MEDIUM | spec.md US3 AC5; tasks.md T417 | US3 Acceptance Scenario 5 diz "audit log registra `admin_user_id` para rastreabilidade" e menciona "entry correspondente em `audit_logs` existente" (tabela do epic 008). T417 só escreve em `handoff_events.metadata` — não cria entry em `audit_logs`. Se epic 008 tem tabela `audit_logs` separada, há gap | Verificar se `audit_logs` do epic 008 existe como tabela. Se sim, T417 deve também fazer INSERT. Se não (apenas `handoff_events`), remover referência "audit_logs existente" de US3 AC5 |
| A1 | Underspecification | LOW | contracts/helpdesk-adapter.md §2.4; spec.md FR-030, SC-014 | Contrato §2.4 `send_operator_reply` anota: "Se Chatwoot Pace nao suportar custom `sender_name` nativamente, alternativa é prefix no texto". Decisão [DEFINIR] fica para PR-C implementação. SC-014 (auditoria 100%) depende de identidade funcionar. Nenhuma task verifica capacidade do Chatwoot version antes de PR-C começar | Adicionar task T060b em PR-A: "Consultar Chatwoot API docs version da instância Pace e confirmar suporte a `sender_name` ou `sender_type` custom; documentar em decisions.md se prefix fallback for necessário" |
| I6 | Inconsistency | LOW | plan.md §Testing strategy; tasks.md Phase 11 | Plan.md §Testing Strategy menciona "E2E Playwright: J-003 (novo journey) — admin abre conversa com handoff ativo, ve badge, clica composer, envia, verifica outbound". Phase 11 Smoke (T1105) referencia apenas J-001 (happy path existente), não J-003 | Ou adicionar T1106 para executar J-003 em Phase 11, ou mover execução de J-003 para dentro de T602 (US5 E2E test) |
| D1 | Underspecification | LOW | spec.md SC-013; tasks.md T414 | SC-013 "Admin UI p95 <2s" para tela de detalhe de conversa — T414 cobre lista (<100ms) mas nenhum test task mede performance da tela de detalhe (badge + histórico + composer) | Adicionar asserção de performance em T415 ou T401 (Playwright): "detalhe conversa carrega em <2s com dataset real Ariel" |
| D2 | Underspecification | LOW | spec.md FR-047a; tasks.md T716 | FR-047a diz cleanup em "batches de 1000 linhas" mas T716 apenas menciona DELETE sem especificar batch. Nenhum test valida comportamento com >1000 rows (loop de batches) | Adicionar nota em T716: "implementar com LIMIT 1000 em loop; test: 2500 rows mock → verifica 3 iterações" |
| U3 | Underspecification | LOW | spec.md FR-038c; tasks.md T062 | T062 cobre validação de range para `auto_resume_after_hours` mas FR-038c define range separado para `human_pause_minutes` (1..1440) — T062 não menciona explicitamente a validação de `human_pause_minutes` | Expandir T062: "validar também `human_pause_minutes` no range 1..1440; valor fora → reject reload + metric + log" |

---

## Coverage Summary

### Requirements with ≥1 Task

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 `ai_active` column | ✅ | T010 | |
| FR-002 metadata columns | ✅ | T010 | |
| FR-003 PG single source of truth | ✅ | T070, T090 | |
| FR-004 Redis legacy telemetria | ✅ | T090, T091 | |
| FR-005 advisory lock | ✅ | T031 | |
| FR-006 commit ordering | ✅ | T031, T032 | |
| FR-007 5 mute sources | ⚠️ Partial | T031, T210, T410, T511 | `rule_match` e `safety_trip` sem task — **HIGH gap C1/C2** |
| FR-008 Chatwoot assign → mute | ✅ | T210, T213 | |
| FR-009 Chatwoot resolved → resume | ✅ | T211, T213 | |
| FR-010 NoneAdapter fromMe → mute | ✅ | T511 | |
| FR-011 timer renewal | ✅ | T511 | |
| FR-012 group skip | ✅ | T511 | |
| FR-013 3 return triggers | ✅ | T211, T311, T411 | |
| FR-014 scheduler asyncio | ✅ | T311 | |
| FR-015 graceful shutdown | ✅ | T312 | |
| FR-016 silent resume | ✅ | T313 | |
| FR-017 HMAC validation | ✅ | T051, T213 | ⚠️ header name inconsistency — **HIGH I1** |
| FR-017a 2 event types only | ✅ | T213 | |
| FR-018 idempotency Redis | ✅ | T213, T201 | |
| FR-019 always 200 OK | ✅ | T213 | |
| FR-020 circuit breaker | ✅ | T040, T041 | |
| FR-021 pipeline safety net | ✅ | T072 | |
| FR-022 customer_lookup amortize | ✅ | T070 | |
| FR-022a populate external_refs | ✅ | T071, T216 | |
| FR-023 content processing continues | ⚠️ | T072 (implicit) | No explicit test — **MEDIUM C3** |
| FR-024 bot_sent_messages table | ✅ | T012 | |
| FR-025 outbound tracking | ✅ | T080, T081 | |
| FR-026 echo tolerance window | ⚠️ | T511 | Ambiguous semantics — **MEDIUM U1** |
| FR-027 cleanup cron 12h | ✅ | T513 | |
| FR-028 mute endpoint | ✅ | T410 | |
| FR-029 unmute endpoint | ✅ | T411 | |
| FR-030 composer reply endpoint | ✅ | T611 | |
| FR-031 NoneAdapter 409 | ✅ | T611 | |
| FR-032 auth scope | ✅ | T412 | |
| FR-033 list badge | ✅ | T414 | |
| FR-034 detail toggle | ✅ | T415 | |
| FR-035 composer UI | ✅ | T613 | |
| FR-036 Performance AI 4 cards | ✅ | T712 | |
| FR-037 date range filter | ✅ | T714 | |
| FR-038 tenants.yaml blocks | ✅ | T061 | |
| FR-038a auto_resume range validation | ✅ | T062 | |
| FR-038b handoff.rules[] router integration | ❌ | — | **HIGH gap C1** |
| FR-038c human_pause_minutes range | ⚠️ | T062 (implícito) | Não mencionado explicitamente — **LOW U3** |
| FR-039 default mode off | ✅ | T063 | Missing: implicit default test — **MEDIUM U2** |
| FR-040 shadow mode | ✅ | T031, T810 | |
| FR-041 mode off → no-op | ✅ | T213 | |
| FR-042 config_poller 60s | ✅ | T061 | |
| FR-043 HelpdeskAdapter Protocol | ⚠️ | T020, T021 | 5 métodos spec vs 6 contrato — **MEDIUM I2** |
| FR-044 ChatwootAdapter + NoneAdapter | ✅ | T050, T510 | |
| FR-045 registry function | ⚠️ | T022 | Nome diverge spec vs contrato — **MEDIUM I3** |
| FR-046 future adapter extensibility | ✅ | T022 | |
| FR-047 handoff_events table | ✅ | T011 | |
| FR-047a retention cron 90d | ✅ | T716 | Batch not tested — **LOW D2** |
| FR-048 all transitions emit events | ✅ | T031, T032 | |
| FR-049 metadata per event | ✅ | T031 | |
| FR-050 operator IDs in metadata only | ✅ | T031 | |
| FR-051 OTel baggage | ✅ | T217, T902 | |
| FR-052 Prometheus metrics | ✅ | T218, T900 | |
| FR-053 structlog | ✅ | T901 | |

### Unmapped Tasks (tasks sem FR correspondente)

| Task | Propósito | Status |
|------|-----------|--------|
| T006 script sign_chatwoot_webhook.py | Dev helper, não é FR | OK — infraestrutura dev |
| T120 benchmark gate PR-A | SC-004 gate | OK — succes criteria |
| T130, T131 smoke validation | SC-005 gate | OK — succes criteria |
| T907 update-agent-context.sh | Processo pós-merge | OK — housekeeping |
| T908 CLAUDE.md update | Active tech stack | OK — housekeeping |
| T912 audit final | Verificação operacional | OK — observabilidade |
| T913 make test/lint/ruff | CI green gate | OK — qualidade |
| T914 /madruga:judge | Pipeline gate L2 | OK — processo |

---

## Análise Detalhada por Categoria

### Constitution Alignment

| Princípio | Status | Observação |
|-----------|--------|-----------|
| I — Pragmatismo e Simplicidade | ✅ PASS | Zero libs novas. Boolean vs state machine. Protocol espelha epic 009. |
| II — Automatize repetitivos | ✅ PASS | 3 crons (handoff_events cleanup, bot_sent_messages cleanup, auto_resume). |
| III — Conhecimento estruturado | ✅ PASS | 22 decisões, 3 ADRs novos, spec pós-clarify com 6 Q&As. |
| IV — Ação rápida | ✅ PASS | Cut-line PR-C explícito. Daily checkpoint easter-tracking.md. |
| V — Alternativas e trade-offs | ✅ PASS | research.md documenta 7 alternativas rejeitadas com justificativa. |
| VI — Honestidade brutal | ✅ PASS | Confiança Média declarada em Q2/Q5; R9 aceito conscientemente. |
| VII — TDD | ✅ PASS | Test tasks (T200-T203, T300-T302, etc.) precedem implementation tasks por fase. |
| VIII — Decisões colaborativas | ✅ PASS | 6 ambiguidades resolvidas em clarify pass + 14 Resolved Gray Areas. |
| IX — Observabilidade | ✅ PASS | FR-051/052/053 cobrem OTel baggage, Prometheus, structlog; audit trail handoff_events. |

**Violações de constituição**: nenhuma.

---

## URL Coverage Check (testing: block detectado)

**Framework**: FastAPI (backend). Roteamento via decorators FastAPI.

Novos endpoints introduzidos por este epic (detectados em spec.md + openapi.yaml + tasks.md):

| Endpoint | Tipo | Declarado em testing.urls? |
|----------|------|-----------------------------|
| `POST /webhook/helpdesk/chatwoot/{tenant_slug}` | api | ❌ **Ausente** |
| `POST /admin/conversations/{id}/mute` | api | ❌ **Ausente** |
| `POST /admin/conversations/{id}/unmute` | api | ❌ **Ausente** |
| `POST /admin/conversations/{id}/reply` | api | ❌ **Ausente** |
| `GET /admin/performance/handoff` | api | ❌ **Ausente** |

**Recomendação**: Adicionar os 5 endpoints em `platform.yaml testing.urls` antes de Phase 11 Smoke (T1103 valida todas as URLs). Sem isso, T1103 não valida os endpoints novos.

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Total FRs analisados (incluindo sub-FRs) | 58 |
| FRs com ≥1 task cobrindo | 53 (91%) |
| FRs sem task (gap crítico/alto) | 2 (`rule_match` via FR-038b + `safety_trip` via FR-007) |
| FRs parcialmente cobertos | 3 |
| Total tasks | ~107 |
| Tasks sem FR mapeado (housekeeping) | 8 |
| Findings CRITICAL | 0 |
| Findings HIGH | 4 |
| Findings MEDIUM | 5 |
| Findings LOW | 5 |
| Ambiguidades detectadas | 2 |
| Inconsistências detectadas | 6 |
| Gaps de cobertura | 3 |
| Violações de constituição | 0 |

---

## Próximos Passos

### Antes de `/speckit.implement`

As 4 findings HIGH devem ser resolvidas antes de iniciar implementação:

1. **I1 (HMAC header)** — Correção simples: atualizar FR-017 em spec.md e a menção em plan.md de `X-Webhook-Secret` → `X-Webhook-Signature`. Impacto: T051 implementa corretamente sem confusão de header name.

2. **C1 (`rule_match` + `handoff.rules[]`)** — Decidir: (a) implementar em PR-B criando task T090b que estende `core/router/rules.py`; ou (b) mover explicitamente para out-of-scope marcando como "implementação futura epic 013 (Agent Tools v2)" e atualizando FR-007 para 4 sources em v1. Não implementar silenciosamente.

3. **C2 (`safety_trip`)** — Mesma decisão que C1. Epic 005 safety guards podem emitir `state.mute()` quando safety trip dispara. Se não está no escopo deste epic, remover `safety_trip` de FR-007 e documentar em decisions.md como "planned post-epic 005".

4. **G1 (testing.urls)** — Adicionar 5 endpoints em `platform.yaml testing.urls`. Tarefa de 5 minutos, mas bloqueia T1103.

### Após resolução dos HIGHs

Os findings MEDIUM podem ser resolvidos inline durante a implementação:
- **I2**: Adicionar `parse_webhook_event` a FR-043 — 1 linha de spec.
- **I3**: Escolher nome canônico e alinhar spec + tasks — `get_adapter` recomendado.
- **I4**: Remover `[P]` de T021 — 1 edição em tasks.md.
- **U1**: Corrigir FR-026 semântica — 1 sentença.
- **U2**: Expandir T063 com cenário de bloco ausente.
- **C3**: Adicionar 1 asserção em T074.
- **I5**: Verificar se `audit_logs` do epic 008 existe como tabela antes de PR-C.

---

## Remediation Sugerida (Top Issues)

### I1 — Alinhar HMAC header name

**spec.md FR-017** — Substituir:
> `X-Webhook-Secret` + body HMAC-SHA256

Por:
> `X-Webhook-Signature` com HMAC-SHA256 do body raw usando `webhook_secret` (header Chatwoot nativo, confirmado em `contracts/helpdesk-adapter.md §2.1`)

### C1 — Adicionar task para `rule_match` ou mover para out-of-scope

**Se implementar em PR-B**, adicionar após T090 em tasks.md:
```
- [ ] T090b [US?: rule_match] Estender `apps/api/prosauai/core/router/rules.py`: quando regra listada em `tenant.handoff.rules[]` casa durante step `route`, emitir `await state.mute_conversation(conn, ..., reason='rule_match', source='rule_match', metadata={'rule_name': rule_name})`. Retornar `action='mute'` em vez de `action='route_to'`.
- [ ] T090c [P] Criar `apps/api/tests/unit/router/test_rules_handoff_integration.py` — regra listada em `handoff.rules[]` casa → mute emitido; regra NÃO listada → sem mute mesmo que case.
```

### G1 — Adicionar endpoints a platform.yaml testing.urls

Adicionar em `platforms/prosauai/platform.yaml` na seção `testing.urls`:
```yaml
    - url: http://localhost:8050/webhook/helpdesk/chatwoot/test-tenant
      type: api
      label: "Chatwoot webhook endpoint"
      expect_status: [200, 401, 404]
    - url: http://localhost:8050/admin/conversations/00000000-0000-0000-0000-000000000000/mute
      type: api
      label: "Admin mute endpoint (auth required)"
      expect_status: [401, 403]
    - url: http://localhost:8050/admin/conversations/00000000-0000-0000-0000-000000000000/unmute
      type: api
      label: "Admin unmute endpoint (auth required)"
      expect_status: [401, 403]
    - url: http://localhost:8050/admin/conversations/00000000-0000-0000-0000-000000000000/reply
      type: api
      label: "Admin composer endpoint (auth required)"
      expect_status: [401, 403]
    - url: http://localhost:8050/admin/performance/handoff
      type: api
      label: "Performance AI handoff metrics"
      expect_status: [401, 403]
```

---

## Conclusão

O epic 010 apresenta **especificação de alta qualidade** com 91% de cobertura de FRs em tasks, zero violações de constituição, e documentação exaustiva de decisões (22 micro-decisões, 6 Q&As de clarify, 14 gray areas resolvidas). O design é sólido e a abordagem de 3 PRs com cut-line explícito é prudente.

Os 4 findings HIGH são corrigíveis com edições pontuais antes de implementação — nenhum exige replanejamento arquitetural. O mais crítico operacionalmente é I1 (header HMAC), que causaria falha silenciosa em produção se o contrato divergir do spec durante a implementação.

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Analyze pré-implement completo. 4 HIGH findings devem ser resolvidos antes de /speckit.implement: (I1) HMAC header X-Webhook-Secret→X-Webhook-Signature em FR-017; (C1) rule_match source sem task — adicionar T090b ou mover para out-of-scope; (C2) safety_trip source sem task — idem; (G1) 5 endpoints novos ausentes em platform.yaml testing.urls. 5 MEDIUM findings resolvíveis inline durante implementação. Coverage 91% (53/58 FRs com task). Zero violações de constituição."
  blockers:
    - "I1: HMAC header name mismatch entre spec FR-017 e contrato helpdesk-adapter.md §2.1 — pode causar falha silenciosa em produção"
    - "C1: FR-038b handoff.rules[] → router integration sem task implementando"
    - "C2: FR-007 safety_trip source sem task — escopo v1 ambíguo"
    - "G1: 5 endpoints novos ausentes em platform.yaml testing.urls — bloqueia Phase 11 Smoke T1103"
  confidence: Alta
  kill_criteria: "Se durante PR-A a fixture real de webhook Chatwoot (T001-T003) revelar que o header HMAC é diferente de X-Webhook-Signature E de X-Webhook-Secret, reabrir contrato helpdesk-adapter.md §2.1 antes de T051."
