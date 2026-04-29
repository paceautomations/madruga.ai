# Easter Tracking — prosauai 016-trigger-engine

Started: 2026-04-26 (retrospectivo — pair-program executado como revisão pós-entrega em 2026-04-29)

---

## Melhoria — madruga.ai

### M1 — analyze-report.md ausente do phase dispatch context `[FIXED 2026-04-29]`

`_add_epic_docs_phase_scoped` não incluía `analyze-report.md`. Findings HIGH do analyze dependiam do modelo ler o arquivo autonomamente — não garantido.

**Fix:** nova `_analyze_report_slice_multi` + incluída em `_add_epic_docs_phase_scoped`. Commit neste mesmo branch.

### M3 — TelegramConflictError sem alerta ativo `[OPEN]`

Easter mitiga conflito de sessão via `preflight_polling_safe` no startup e `bot.session.close()` no shutdown (`easter.py:786-793`, `:822-828`). Sem monitoramento ativo de conflito externo persistente (outro processo usando mesmo token).

### M4 — File contexts não function-scoped (plan.md, data-model.md) `[OPEN — baixa prioridade]`

`_add_epic_docs_phase_scoped` inclui `plan.md` e `data-model.md` completos. Tasks e spec são scoped; estes dois arquivos não. Em planos grandes (>30KB) desperdiça tokens por fase.

---

## Melhoria — prosauai

### P1-P5 — BLOCKERs epic 015 (sandbox constraint impediu auto-heal) `[OPEN]`

Descobertos no qa-report/judge-report do epic 015. Auto-heal bloqueado por constraint "Do NOT write outside epic directory" — código vive em `paceautomations/prosauai` (repo externo, ADR-024). Requerem PR dedicado `fix/epic-015-judge-fallout`.

### P6 — LGPD DPO sign-off em `ON DELETE CASCADE trigger_events` `[OPEN]`

Auditoria de conformidade pendente antes de ativar `mode: live` no Ariel.

### P7 — SC-011 alert de custo `trigger_cost_today_usd > 50` — firing em pré-prod não verificado `[OPEN]`

YAML validado sintaticamente (T085 PASS); simulação end-to-end contra Alertmanager pendente.

### P8 — `intent_filter`, `agent_id_filter`, `min_message_count` sem wiring SQL `[OPEN — 016.1+]`

Emitem `WARN trigger_match_filter_unsupported` (loud-warning, não silencioso). Wiring completo deferido para 016.1+.

---

## Deep Dive — madruga.ai

### M1 — analyze-report.md ausente do phase dispatch

**Validação de código:**
`_add_epic_docs_phase_scoped` (`dag_executor.py:923-941`, antes do fix) incluía apenas `plan.md`, spec scoped, `data-model.md` e contracts. `compose_task_prompt` (path legado, linha ~730-761) incluía `_analyze_report_slice` scoped por task — mas phase dispatch nunca chamava essa função.

**Causa raiz:**
`compose_phase_prompt` foi criado como otimização sobre `compose_task_prompt` e `_add_epic_docs_phase_scoped` foi introduzida paralelamente. Na migração, a lógica de analyze-report não foi replicada — só spec, plan e data-model foram portados. Sem testes para garantir paridade de conteúdo entre paths.

**Impacto:**
Findings HIGH do analyze (ex: epic 010 — I1 HMAC header, C1/C2 bridges; epic 015 — L3-B2 exception tuple estreito) não chegam ao modelo via phase dispatch. O modelo precisa executar `Read analyze-report.md` autonomamente — confiável 50–70% dependendo de instrução no cue, não garantido.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Slice multi-task por fase (aplicado)** | Zero tokens desnecessários; mirrors `_analyze_report_slice` existente; scoped por task_id | Paragraph-split pode perder contexto se finding referencia task por string parcial |
| Full analyze-report (+16KB/fase) | 100% visibilidade garantida | Custo de tokens mesmo quando 0 findings relevantes; plan.md 40KB + analyze 15KB = prompt >80KB para fases pequenas |
| Cue no header (estado anterior) | Zero custo de tokens | Não confiável — modelo pode ignorar; observado em epics 010 e 015 |

**Recomendação aplicada:** Slice multi-task. Mesma heurística do `_analyze_report_slice` individual: paragráfo contém `task_id` string → relevante. Se analyze não referencia tasks da fase, seção omitida. Zero regressão de tokens nas fases onde analyze não cita as tasks.

**Fix:** `dag_executor.py` — nova `_analyze_report_slice_multi` (L635-645) + `_add_epic_docs_phase_scoped` inclui slice (L939-941). 2 testes adicionados em `test_dag_executor.py`.

---

### M3 — TelegramConflictError sem alerta ativo

**Validação de código:**
`easter.py:786-793` — `preflight_polling_safe(bot, offset)` no startup aguarda até 5s para confirmar que não há outra sessão de polling ativa. `easter.py:822-828` — `bot.session.close()` no shutdown fecha a sessão HTTP, liberando o lock server-side do Telegram para a próxima instância.

Esses dois pontos cobrem o caso mais comum: restart rápido do easter (SIGTERM → start) sem delay. Não cobrem: outro processo externo (dev local, staging) usando o mesmo token de produção simultaneamente.

**Causa raiz:**
aiogram não expõe `tryings` como evento programático; o retry interno acontece silenciosamente. O conflito externo persistente (`getUpdates` de outra instância mantendo o lock) não é detectável sem tentativa de polling — o que é exatamente o que `preflight_polling_safe` faz, mas apenas 1 vez no startup.

**Impacto:**
Baixo em ambiente bem gerenciado (token separado por ambiente). Alto em desenvolvimento com sharing de token: notificações de 1-way-door (reconcile, qa) nunca chegam → operador não recebe alerta de gate pendente.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Middleware aiogram: log WARNING quando conflito detectado (recomendado curto prazo)** | Visível no portal via structlog; sem infraestrutura nova | Não elimina o conflito, só o torna observável |
| Webhook mode | Elimina a classe de conflito inteiramente | Requer endpoint público com TLS; infra adicional para dev |
| Token separado por ambiente (recomendado longo prazo) | Elimina conflito na raiz; best practice | Overhead operacional: gerenciar 2+ bots; reconfigurar CLAUDE.md |

**Recomendação:** Middleware aiogram curto prazo (observabilidade) + token separado dev/prod como próxima prioridade operacional.

---

### M4 — File contexts não function-scoped

**Validação de código:**
`_add_epic_docs_phase_scoped` (L923) inclui `plan.md` full via `_read_context`. `data-model.md` idem. Files de tasks.md são scoped via `_slice_tasks_for_phase`; spec via `_scoped_spec_section`. `plan.md` e `data-model.md` ficaram fora do scoping.

Observado no epic 026: phase-1 com 12 tasks disparada com `total_bytes=103,144`. Breakdown: tasks=27KB + spec=25KB + **plan=23KB** + data_model=7KB + contracts=9KB. Epic 026 era relativamente enxuto; planos maiores (epic 016 `plan.md` = 65KB) elevam o custo por fase significativamente.

**Causa raiz:**
Scoping de `plan.md` requer heurística de "qual seção do plan é relevante para esta fase" — mais difícil que spec (User Story sections) ou tasks (IDs explícitos). A implementação mais conservadora foi incluir o plano completo como referência.

**Impacto:**
Variável por epic. Epic 016 `plan.md` = 65KB → cada fase recebe 65KB de plano, independente de quantas tasks estão naquela fase. Para epics com 8+ fases isso é ~520KB total de conteúdo de plan repetido no contexto.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Phase-header slice para plan.md (recomendado)** | Mirrors `_slice_tasks_for_phase`; usa estrutura `## Phase N:` já existente | Requer que plan.md tenha headers `## Phase N:` — epics sem fases definidas no plan precisam de fallback |
| Cap por LOC (ex: 300 linhas) | Simples, sem parsing | Pode cortar a seção relevante se a fase estiver no final do plan |
| AST-based extraction para `.py` | 35KB de economia para arquivos Python grandes | Requer ast parsing; não generaliza para outros file types |
| Manter full (atual) | Zero risco de perda de contexto | Custo crescente conforme planos ficam maiores |

**Recomendação:** Phase-header slice, mesmo padrão de `_scoped_spec_section`. Baixa prioridade — não bloqueia nenhum epic, melhoria de eficiência.

---

## Deep Dive — prosauai

### P1 — `_PIPELINE_EXEC_METADATA` não é WeakKeyDictionary (epic 015, L3-B1)

**Localização:** `apps/api/prosauai/conversation/pipeline.py:603`

**Validação:**
```python
_PIPELINE_EXEC_METADATA: dict[int, Any] = {}  # linha 603
```
Docstring na linha 583-585 afirma ser `WeakKeyDictionary`. É `dict[int, Any]` keyed por `id(gen_result)`.

**Causa raiz:**
Docstring foi escrita refletindo a intenção original (WeakKeyDictionary para GC automático), mas a implementação usou `dict[int, Any]` — possivelmente por não importar `weakref`. Sem testes que verificassem o tipo real.

**Failure modes:**
1. **Memory leak:** se `_consume_pipeline_exec_result` nunca for chamado (exceção em `_record_step`, exporter OTel, output_guard), a entry permanece até restart do processo. Alto volume → acumulação.
2. **Cross-tenant id() reuse:** após GC do `gen_result` original, Python pode reusar o mesmo `id()` para um novo `GenerationResult` de outra conversa/tenant. `_PIPELINE_EXEC_METADATA` retorna o metadata do tenant A para o tenant B — violação de isolamento.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **`WeakValueDictionary[int, PipelineExecMetadata]` (recomendado)** | GC automático quando `gen_result` destrói; zero memory leak; type-safe | Requer que `PipelineExecMetadata` seja um objeto (não só dict) — minor refactor |
| Attribute assignment direto em `gen_result` | Zero risco de id reuse; acesso O(1) | Polui o objeto com estado externo; quebra separação de responsabilidades |
| `try/finally` em todos os callers para garantir `_consume` | Garante cleanup | Frágil — caller precisa cooperar; não resolve o risco de id reuse |

**Recomendação:** `weakref.WeakValueDictionary` com `PipelineExecMetadata` como dataclass. PR: `fix/epic-015-judge-fallout`, arquivo `pipeline.py`.

---

### P2 — Exception tuple estreito em `pipeline_executor.py:369` (epic 015, L3-B2)

**Localização:** `apps/api/prosauai/conversation/pipeline_executor.py:369`

**Validação:** filtro `(TimeoutError, ConnectionError, RuntimeError, ValidationError)` — exclui `httpx.HTTPStatusError`, `httpx.ReadTimeout`, `openai.RateLimitError`, `anthropic.APIError`, `pydantic_ai.exceptions.UnexpectedModelBehavior`, `OSError`.

**Causa raiz:**
Tuple foi escrito antes de o projeto adotar pydantic-ai e httpx como deps primárias. Não foi atualizado após epic 005 (LLM integration). Sem testes de chaos/fuzz que disparassem esses caminhos.

**Impacto:**
Em storms de 5xx do provider LLM (ex: Anthropic manutenção), `httpx.HTTPStatusError` propaga pelo executor (violando docstring "executor never raises"), aborta `_run_pipeline` → caminho de entrega de mensagem cai. FR-026 (zero retry / fallback canned response) quebrado.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **`except Exception` com whitelist de não-retryáveis (recomendado)** | Captura qualquer SDK futuro sem modificar o tuple; não-retryáveis (KeyboardInterrupt, SystemExit) excluídos via `BaseException` filter | Marginalmente mais amplo — pode mascarar bugs de programação |
| Ampliar tuple explicitamente | Preciso; auto-documentado | Nunca está completo; todo novo SDK exige update |
| Retry layer no caller (epic 016 pattern) | Defense-in-depth | Não resolve o crash; apenas adiciona retry em cima |

**Recomendação:** `except Exception` com `if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise` logo acima. Adicionalmente, logar o tipo exato via structlog para identificar novos exception classes antes que causem incidentes.

---

### P3 — Decimal coercion divergente (epic 015, L3-B3)

**Localização:** `apps/api/prosauai/conversation/pipeline_executor.py:418-419` (aggregate) vs `:439` (SubStepRecord)

**Validação:**
- Linha 418-419: `contextlib.suppress(Exception)` envolve `Decimal(result.cost_usd or 0)` — silencia erros de coerção no agregado.
- Linha 439: construtor `SubStepRecord(cost_usd=Decimal(result.cost_usd))` sem suppression — `decimal.InvalidOperation` para valores malformados.

**Causa raiz:**
Dois sites de coerção escritos independentemente; o primeiro (aggregate) teve tratamento de erro adicionado como correção incremental; o segundo (SubStepRecord) não foi atualizado na mesma passagem.

**Impacto:**
Provider LLM futuro retornando `cost_usd="NaN"` ou string arbitrária → `SubStepRecord` dispara `decimal.InvalidOperation` depois da chamada LLM bem-sucedida → executor crasha, mensagem processada mas não registrada.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **`_safe_decimal(v, default=Decimal(0))` helper (recomendado)** | Unifica os dois sites; testável isoladamente; padrão DRY | Requer extração de função; menor refactor |
| Duplicar `contextlib.suppress` no SubStepRecord | Imediato | Duplicação; próximo site vai divergir novamente |
| Validar `cost_usd` no boundary (provider response) | Falha rápido na origem | Não protege de providers legados já integrados |

**Recomendação:** `_safe_decimal` helper, 3 linhas. Replicar em ambos os sites.

---

### P4 — Missing expression index em `audit_log details->>'agent_id'` (epic 015, L3-B4)

**Localização:** `apps/api/prosauai/admin/pipeline_steps.py:389-396`

**Query:**
```sql
WHERE action='agent_pipeline_steps_replaced'
  AND (details::jsonb)->>'agent_id' = $1
ORDER BY created_at DESC LIMIT 1
```

**Causa raiz:**
Index existente `idx_audit_log_action` cobre `action`, mas não a extração `details->>'agent_id'`. Planner faz seq scan no resultado filtrado por action + re-extração JSON por row + sort.

**Impacto:**
6 tenants × audit churn → acima de ~100K rows em `audit_log`, latência ultrapassa `pool_admin.acquire(timeout=3.0)`. Endpoint de rollback de pipeline-steps (`/admin/agents/{id}/pipeline-steps/rollback`) fica intermitente sob carga.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Expression index `CREATE INDEX ... ON audit_log ((details->>'agent_id')) WHERE action='agent_pipeline_steps_replaced'` (recomendado)** | Partial index — só as rows relevantes; tamanho mínimo; elimina seq scan | Requer migration; timing em prod deve ser `CREATE INDEX CONCURRENTLY` |
| GIN index em `details jsonb` | Cobre todas as queries JSON | Muito maior; overhead de write; overkill |
| Cache de `latest_audit` por `agent_id` em Redis TTL 60s | Zero latência de DB | Stale por 60s; complica rollback semantics |

**Recomendação:** Partial expression index via migration. `CREATE INDEX CONCURRENTLY` em produção para zero-downtime.

---

### P5 — PUT replace sem optimistic concurrency (epic 015, L3-B5)

**Localização:** `apps/api/prosauai/admin/pipeline_steps.py:298-352`; `apps/api/prosauai/db/queries/pipeline_steps.py:259-273`

**Validação:**
Endpoint acquire `pool_admin` 3× sequencialmente (resolve tenant → load before-state → atomic replace) sem `SELECT ... FOR UPDATE` em `agents.id` nem `pg_advisory_xact_lock`. PUTs concorrentes no mesmo agente:
- PUT-A lê before-state
- PUT-B lê o mesmo before-state
- A commit → audit_log entry com before-state correto
- B commit com before-state de A → audit_log timeline corrompido; rollback de B desfaz trabalho de A

**Causa raiz:**
Pattern multi-acquire sem lock foi um descuido de concorrência — comum em endpoints admin "raros". Admin de pipeline-steps foi assumido como operação singleton (um operator por vez), o que não se mantém em time distribuído.

**Impacto:**
Perda silenciosa de edições; audit_log incoerente → rollback retorna estado errado. Severidade alta em equipes com múltiplos admins.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **`pg_advisory_xact_lock(hashtext(agent_id::text))` no início da transação replace (recomendado)** | Lock por agente, não global; liberado automaticamente no commit/rollback; zero schema change | Aumenta duração da transação; deadlock possível se dois endpoints pegam locks em ordem inversa (improvável aqui — lock único por agente) |
| `SELECT ... FOR UPDATE` em `agents.id` | Lock por row; padrão explícito | Requer que o SELECT de `agents.id` faça parte da mesma transação — refactor maior |
| Optimistic locking via `version_counter` column | Sem lock; rejeita conflitos com 409 | Requer schema migration + retry logic no frontend |

**Recomendação:** `pg_advisory_xact_lock` — menor impacto, sem schema change, resolve race condition.

---

### P6 — LGPD DPO sign-off em `ON DELETE CASCADE trigger_events`

**Localização:** `apps/api/db/migrations/20260601000020_create_trigger_events.sql`; `decisions.md D33`

**Validação:**
Migration define `customer_id UUID REFERENCES public.customers(id) ON DELETE CASCADE`. SAR (Subject Access Request) que deleta um customer apaga automaticamente todos os `trigger_events` desse customer — audit trail operacional removido.

Trade-off registrado em `decisions.md D33`: CASCADE hard-delete em v1; anonimização alternativa (`set NULL + redact payload`) adiada para 016.1+ se DPO/jurídico requerer.

**Causa raiz:**
Decisão foi tomada como "mais simples para v1" com marcador `[VALIDAR]`. DPO sign-off não foi obtido antes da implementação.

**Impacto:**
Sem sign-off, o epic não pode sair de `mode: shadow` para `mode: live` no Ariel. Risco regulatório se uma SAR apagar dados que fossem necessários para auditoria de antispam (Meta compliance).

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Manter CASCADE + obter DPO sign-off explícito (recomendado)** | Menor esforço técnico; alinhado com decisão existente | Requer aprovação legal — timeline incerto |
| Migrar para anonimização (`customer_id = NULL`, payload redacted) | Preserva audit trail operacional; mais LGPD-friendly | Migration em tabela com dados reais; lógica de anonimização a implementar |
| Soft delete por `deleted_at` flag | Audit trail preservado; SAR cumpre com redação de PII | Schema change; queries devem filtrar `deleted_at IS NULL` em todos os lugares |

**Recomendação:** Obter sign-off DPO para CASCADE antes de flipar `mode: live`. Se DPO rejeitar, migrar para anonimização com NULL + redact (menor invasão que soft delete).

---

### P7 — SC-011 alert custo não disparado em pré-prod

**Localização:** `platforms/prosauai/config/rules/triggers.yml` (regra Prometheus)

**Validação:**
`tasks.md T085 [x]` confirma YAML sintaticamente válido. Não existe registro de teste de firing end-to-end contra Alertmanager.

**Causa raiz:**
Smoke test de alert (simular `trigger_cost_today_usd > 50` em pré-prod e verificar que Slack recebe o alerta) requer ambiente com Alertmanager provisionado — não disponível no ambiente de develop local.

**Impacto:**
Se a regra tiver path errado de metric name, threshold, ou label mismatch, o alert pode não disparar em produção mesmo com custo acima do limite. Descoberto somente quando o overrun já ocorreu.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Teste de integração local com `promtool test rules`** | Sem Alertmanager real; valida a regra staticamente | Não valida o path completo até o Slack |
| Synthetic firing em pré-prod (recomendado para rollout) | Validação end-to-end real | Requer staging provisionado |
| `amtool` check-config | Valida sintaxe Alertmanager | Não valida a regra Prometheus |

**Recomendação:** `promtool test rules` como gate local imediato (pode ser adicionado ao `make ci`). Synthetic firing como checklist de rollout pré-live.

---

### P8 — `intent_filter`, `agent_id_filter`, `min_message_count` sem wiring SQL

**Localização:** `apps/api/prosauai/triggers/matchers.py:438-493`

**Validação:**
`_warn_unsupported_filters` emite `WARN trigger_match_filter_unsupported` por valor não-default. `consent_required` foi wired (B5 heal). Os outros 3 filtros declarados no YAML de tenant passam silenciosamente sem efeito no SQL.

**Causa raiz:**
Esses filtros requerem JOIN com tabelas de conversations/agents que tornam o matcher SQL mais complexo (subquery ou CTE adicional). Foram depriorizados para v1 por não serem usados pelo Ariel (único pilot).

**Impacto:**
Baixo para epic 016 (Ariel não usa esses filtros). Médio para 016.1+ se um tenant configurar `agent_id_filter: [agent_abc]` esperando filtrar por agente — triggers dispararão para todos os agentes sem aviso claro no admin UI.

**Soluções avaliadas:**

| Opção | Pro | Con |
|-------|-----|-----|
| **Wiring SQL + testes (016.1+, recomendado)** | Cumpre spec FR-008 completo; elimina surpresa operacional | Complexidade SQL moderada; testes de integração a adicionar |
| Bloquear configuração via validação no YAML load | Falha fast se tenant configura filtro não suportado | Breaking change para configurações existentes |
| Manter loud-warning (atual) | Sem esforço | Operador pode ignorar o log |

**Recomendação:** Wiring SQL em 016.1+. Adicionar exposição do warning no admin UI (badge/tooltip ao lado dos campos desabilitados).

---

## Incidents críticos

_(nenhum — epic 016 rodou sem incidentes registrados durante a execução)_

---

## Síntese (2026-04-29)

**Métricas:**
- Incidents críticos: **0**
- Tempo perdido estimado: **0 min** (epic rodou limpo)
- Fixes commitados (madruga.ai): **1** (`_analyze_report_slice_multi` + `_add_epic_docs_phase_scoped` + 2 testes)
- Melhorias documentadas: **12** (4 madruga.ai + 8 prosauai)

---

### Agrupamento por causa raiz

#### Causa raiz A — Paridade incompleta entre `compose_task_prompt` e `compose_phase_prompt` (M1, FIXED)

Ao criar o path de phase dispatch, `_add_epic_docs_phase_scoped` não replicou a inclusão de `analyze-report.md` do path por-task. Findings HIGH do analyze chegam ao modelo apenas por iniciativa autônoma — não garantido.

**Fix:** `_analyze_report_slice_multi` + inclusão em `_add_epic_docs_phase_scoped`. Parity restaurada.

---

#### Causa raiz B — Observabilidade passiva de conflitos Telegram (M3, OPEN)

Easter mitiga conflito de sessão própria mas não detecta conflito externo persistente. Impacto: notificações de gates 1-way-door podem não chegar ao operador.

**Próximo passo:** middleware aiogram para logar WARNING quando polling conflict é detectado durante operação (não só no startup).

---

#### Causa raiz C — Acumulação de dívida técnica em prosauai (P1-P5, OPEN)

5 BLOCKERs do epic 015 não foram auto-healed por constraint sandbox. Todos identificados e documentados; requerem PR dedicado em `paceautomations/prosauai`:
- `pipeline.py:603` — WeakValueDictionary (P1)
- `pipeline_executor.py:369` — exception broadening + `_safe_decimal` (P2, P3)
- `pipeline_steps.py:389` — partial expression index (P4)
- `pipeline_steps.py:298-352` — `pg_advisory_xact_lock` (P5)

---

#### Causa raiz D — Gates pré-live sem checklist formal (P6, P7, OPEN)

DPO sign-off (P6) e alert firing test (P7) são gates operacionais sem owner definido e sem SLA. Risco de o Ariel passar para `mode: live` sem esses gates validados.

**Próximo passo:** adicionar ao `RUNBOOK.md` de rollout como bloqueadores explícitos com checkbox antes de `mode: live`.
