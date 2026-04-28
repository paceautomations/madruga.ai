# Implementation Plan: Agent Pipeline Steps — sub-routing configurável por agente

**Branch**: `epic/prosauai/015-agent-pipeline-steps` | **Date**: 2026-04-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/015-agent-pipeline-steps/spec.md`

## Summary

Habilitar **sub-routing configurável por agente** dentro do step `generate_response` (atualmente `step_order=9` em `trace_steps`, ver [`step_record.py`](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/conversation/step_record.py) `STEP_NAMES`). Hoje a chamada é **monolítica** — `apps/api/prosauai/conversation/pipeline.py:_generate_with_retry()` invoca `agent.py:generate_response()` em uma única chamada LLM. Este épico introduz uma **tabela de orquestração declarativa** (`agent_pipeline_steps`, ainda não criada em produção — schema-draft em [`domain-model.md`](../../engineering/domain-model.md) linha 244) que permite encadear até 5 steps tipados (`classifier|clarifier|resolver|specialist|summarizer`) com `condition` JSONB de roteamento.

**Abordagem técnica**: criar um **executor declarativo** novo (`pipeline_executor.py`) chamado por `pipeline.py` quando o agente tiver ≥1 step configurado. Agentes sem steps configurados continuam executando o caminho atual (`generate_response()` direto), com **zero overhead observável** (1 query indexada `WHERE agent_id=$1 AND is_active=true` retornando 0 rows ≤1 ms — SC-010). Sub-steps persistem em **nova coluna `sub_steps JSONB`** em `trace_steps` (decisão D-PLAN-01 — alternativa a tabela própria), populada apenas para o row `generate_response`. Cada sub-step interno truncado a 4 KB; cap total de 32 KB na coluna. Trace Explorer (épico 008) lê e renderiza esses sub-spans de forma consistente com o waterfall atual.

**Cut-line operacional**: PRs 1–4 entregam US1+US2+US6 (P1) — pipeline executor + 3 step types funcionando + zero regressão. PR-5 (US3 admin UI) e PR-6 (US4+US5 group-by-version + Trace Explorer extension) são P2 e podem ser **cortados** para épico próprio se passar de 4 semanas (ver `pitch.md` Captured Decisions). PR-1 a PR-4 são auto-suficientes — operadores configuram via SQL direto durante phase 1, validam em produção, e só depois decidem investir em UI.

**Non-goals decididos no plan** (registrados em decisions.md como D-PLAN-XX para auditoria):
- Não implementar `agent_config_versions` (ADR-019) neste épico — descoberta D-PLAN-02: a tabela **não existe em produção** apesar de ADR aprovado. Pipeline_steps fica vinculado direto a `agents.id` (sem snapshot versionado). Versioning vira épico próprio se canary regressar.
- Não implementar retry inteligente entre steps (FR-026 — Clarifications 2026-04-27).
- Não implementar OR/parens no avaliador de `condition` (FR-024 — Clarifications 2026-04-27).
- Não suportar configuração dinâmica de `MAX_PIPELINE_STEPS_PER_AGENT` por tenant (FR-003 — Clarifications 2026-04-27).
- Não introduzir granularidade de canary per-step (escopo é per-agent-version, ADR-019 quando shippar).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x (frontend Next.js 15 — apenas se P2 entrar)
**Primary Dependencies**: FastAPI ≥0.135, asyncpg ≥0.31, pydantic ≥2.12, pydantic-ai ≥1.80, structlog ≥25.0, opentelemetry-sdk 1.39.x, redis[hiredis] ≥7.0 (já em uso). **Zero novas dependências Python**.
**Storage**: PostgreSQL 15 (Supabase) — nova tabela `public.agent_pipeline_steps` (RLS ON, policy por `tenant_id`) + nova coluna `public.trace_steps.sub_steps JSONB` (sem RLS — herda regra ADR-027 do épico 008). Migrations via `dbmate` em `apps/api/db/migrations/`.
**Testing**: pytest + pytest-asyncio + testcontainers-postgres (suite existente em `apps/api/tests/`). Frontend: pnpm test + Playwright (apenas se PR-5/PR-6 entrarem).
**Target Platform**: Linux server (FastAPI em uvicorn, container `apps/api`); browser desktop (PR-5/PR-6).
**Project Type**: Web service (backend) — extensão do conversation pipeline existente.
**Performance Goals**:
- Overhead p95 do lookup `agent_pipeline_steps` para agente sem pipeline ≤**5 ms** (SC-010, hard gate).
- Overhead estrutural p95 do executor (com 0 steps, zero LLM calls) ≤**10 ms** vs. baseline atual.
- Latência p95 do pipeline `classifier+specialist` para `greeting` ≤**1 s** (SC-002).
- Custo médio por mensagem: redução ≥**30%** com pipeline configurado vs. baseline (SC-001).
**Constraints**:
- **Backward compatibility absoluta**: `pipeline_steps=[]` → execução exatamente igual à atual (FR-021, FR-071, gate de merge SC-008).
- Cap de **5 steps** por agente (constante `MAX_PIPELINE_STEPS_PER_AGENT`).
- Cap de **16 KB** por `config` JSONB (FR-004).
- Cap de **8 KB** por sub-step `input`/`output` no trace (alinhado com truncate existente).
- Cap de **32 KB** total na coluna `sub_steps` (proteção contra inflação).
- Timeout total do pipeline = `_PIPELINE_TIMEOUT_SECONDS` global (60 s, FR-027); por step = config (default 30 s, max 60 s, FR-028).
- Fire-and-forget para persistência de sub-steps (mesma regra ADR-028 do épico 008).
- Branch `epic/prosauai/015-agent-pipeline-steps` já existe — checkout direto.
**Scale/Scope**:
- 6 tenants ativos hoje, ~5 k mensagens/dia/tenant.
- Adoção esperada: 2–3 tenants em pipeline em até 60 dias (SC-011).
- Volume novo: tabela `agent_pipeline_steps` cresce devagar (~30 rows máximo: 6 agentes × 5 steps); coluna `sub_steps` adiciona ~2 KB/trace × 30 k traces/dia × 30 dias retention = ~1.8 GB cumulativos (cabe folgado no orçamento de storage do épico 008).
- ~3 endpoints novos no admin (PR-5 P2): GET/PUT pipeline-steps + admin agent detail extension.

## Constitution Check

*GATE: passa antes do Phase 0 research. Re-check após Phase 1 design.*

| Princípio | Avaliação | Justificativa |
|-----------|-----------|---------------|
| I — Pragmatismo & Simplicidade | ✅ | Reusa tudo: pydantic-ai, asyncpg, structlog, OTel, schema do épico 008 (trace_steps + pool_admin). Single new column em vez de tabela aninhada. Sem retry, sem OR/parens — escolhas conscientes. |
| II — Automate repetitive | ✅ | Reusa `_record_step`, `persist_trace_fire_and_forget`, `pricing.calculate_cost`, `tool_registry`, sandwich prompt, `ModelSettings`. **Zero código de orquestração novo** que não seja específico ao executor. |
| III — Knowledge structured | ✅ | `decisions.md` semeado pelo epic-context será enriquecido com D-PLAN-01..D-PLAN-12 (sub_steps storage, sem agent_config_versions, condition grammar, etc). Cross-reference para ADR-006/019/027/028. |
| IV — Fast action | ✅ | 6 PRs sequenciais; PR-1 (migration + repository) é 4h; PR-2 (executor + step types) é o coração — 8d. Cada PR deixa o sistema funcional. |
| V — Alternativas & trade-offs | ✅ | `research.md` (Phase 0) compara: (R1) sub_steps column vs. nested JSON vs. parent_step_id table; (R2) executor inline em pipeline.py vs. módulo novo; (R3) condition evaluator regex vs. AST vs. mini-DSL; (R4) cache Redis vs. lookup direto; (R5) versionamento agora vs. depois. |
| VI — Brutal honesty | ✅ | Plan reconhece publicamente que `agent_config_versions` (ADR-019) **não existe em produção** apesar de ADR aprovado — descoberta crítica. PR-2 + PR-3 listam riscos explícitos: regressão silenciosa do generate_response (mitigado com gate SC-008 e test parity). |
| VII — TDD | ✅ | Testes em 3 camadas: (a) unit puro (`condition.py`, cada step type isolado com mock LLM); (b) integration (`pipeline_executor` end-to-end com asyncpg + testcontainers); (c) regression (suite existente passa intacta — SC-008 hard gate). PR-2 escreve testes de condition + executor ANTES da integração com pipeline.py. |
| VIII — Collaborative decisions | ✅ | 5 ambiguidades já resolvidas no clarify (operadores, retry, summarizer, limite, filtros). 5 novas decisões D-PLAN expostas para revisão (sub_steps storage, sem versioning, executor isolado, sem cache, cut-line PR-5). |
| IX — Observability | ✅ | Cada step emite OTel sub-span (`conversation.pipeline.step.{type}`); cada sub-step persiste em `trace_steps.sub_steps`; structlog logs com `correlation_id` (trace_id) + `step_index` + `step_type` + `model` + `tokens` + `cost`. Failure de step gera `level=error` + `error_type` no buffer. |

**Violações**: nenhuma. `Complexity Tracking` vazio.

### Post-Phase-1 re-check

| Risco | Status |
|-------|--------|
| Regressão no caminho hot (agentes sem pipeline) | Mitigado: SC-010 (≤5 ms p95) validado em benchmark dedicado em PR-2; SC-008 (suite existente passa) é gate de merge no PR-3. |
| Sub_steps column inflar storage do épico 008 | Mitigado: cap 32 KB + truncate 4 KB por sub-step; estimativa 1.8 GB em 30d (cabe no SSD orçado). Métrica `trace_steps_substeps_bytes_p95` adicionada. |
| Condition evaluator quebrar em produção com input inesperado | Mitigado: try/except → False + warning logado **uma vez por agente/step** (FR-024); fuzz test com hypothesis em PR-2; comentário explícito na docstring. |
| Pipeline executor mascarar erro no specialist (UX silencioso) | Mitigado: erro em qualquer step → fallback canned (mesma `FALLBACK_MESSAGE` do step 9 atual); trace registra `status=error` + `error_type` para debug; `messages.metadata.terminating_step` registra qual step abortou. |
| Versionamento ausente impede rollback fácil | Aceito: `agent_pipeline_steps` direto na tabela (sem snapshot). Rollback via `DELETE FROM agent_pipeline_steps WHERE agent_id=X` é atômico. Histórico via `audit_log` (PR-5). Trade-off documentado em D-PLAN-02. |
| Frontend (PR-5/PR-6) não shippa em 3 semanas | Aceito: cut-line explícito; produto/ops continuam configurando via SQL — sem bloqueio para US1/US2/US6. |
| Tests existentes (`apps/api/tests/conversation/test_pipeline.py`) precisarem fixture de pipeline_steps vazio | Mitigado: lookup retorna `[]` por default (zero rows) — fixture conftest sem mudança. |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/015-agent-pipeline-steps/
├── plan.md                  # Este arquivo
├── spec.md                  # Feature specification (pós-clarify, 5 decisões autônomas)
├── pitch.md                 # Shape Up pitch (epic-context — referência)
├── decisions.md             # Capturas L2 (semente do epic-context, enriquecido durante implement)
├── research.md              # Phase 0 — R1..R5 alternativas com pros/cons
├── data-model.md            # Phase 1 — DDL agent_pipeline_steps + sub_steps column + ER
├── quickstart.md            # Phase 1 — setup local + validação US1..US6
├── contracts/
│   └── openapi.yaml         # Phase 1 — endpoints admin (PR-5, P2)
├── checklists/
│   └── requirements.md      # pré-existente (gerado pelo specify)
└── tasks.md                 # Phase 2 — gerado por /speckit.tasks (NÃO criado por este skill)
```

### Source Code (repository — `paceautomations/prosauai`, branch `epic/prosauai/015-agent-pipeline-steps`)

```text
apps/api/                                                 # backend FastAPI (existente)
├── db/migrations/                                        # dbmate
│   ├── 20260601000010_create_agent_pipeline_steps.sql   # NEW — tabela + índices + RLS
│   └── 20260601000011_alter_trace_steps_sub_steps.sql   # NEW — coluna sub_steps JSONB
├── prosauai/
│   ├── main.py                                          # registrar novo router admin (PR-5)
│   ├── conversation/                                    # epic 005
│   │   ├── pipeline.py                                  # MODIFIED — branch para executor quando steps presentes
│   │   ├── pipeline_executor.py                         # NEW — orchestrator declarativo (coração do épico)
│   │   ├── condition.py                                 # NEW — avaliador `<,>,<=,>=,==,!=,in` + AND-implícito
│   │   ├── pipeline_state.py                            # NEW — dataclass `PipelineState` (scope para condition)
│   │   ├── steps/                                       # NEW dir
│   │   │   ├── __init__.py
│   │   │   ├── base.py                                  # NEW — Protocol `PipelineStep` + `StepResult`
│   │   │   ├── classifier.py                            # NEW — pydantic-ai Agent com output_type
│   │   │   ├── clarifier.py                             # NEW — pydantic-ai Agent texto livre
│   │   │   ├── resolver.py                              # NEW — pydantic-ai Agent com tools
│   │   │   ├── specialist.py                            # NEW — wrap generate_response com routing_map
│   │   │   └── summarizer.py                            # NEW — pydantic-ai Agent → `summarized_context`
│   │   ├── agent.py                                     # UNCHANGED — generate_response continua o caminho default
│   │   ├── step_record.py                               # MODIFIED — campo `sub_steps: list[StepRecord] | None`
│   │   └── trace_persist.py                             # MODIFIED — persistir sub_steps junto com top-level
│   ├── db/queries/
│   │   └── pipeline_steps.py                            # NEW — repository (list/insert/replace/delete + validate)
│   ├── admin/                                           # epic 008 (PR-5, P2)
│   │   ├── pipeline_steps.py                            # NEW — GET/PUT /admin/agents/{id}/pipeline-steps
│   │   ├── schemas/
│   │   │   └── pipeline_steps.py                        # NEW — Pydantic models p/ request/response
│   │   ├── agents.py                                    # MODIFIED — agent detail inclui pipeline_steps[]
│   │   └── traces.py                                    # MODIFIED — trace detail expõe sub_steps[] (PR-6)
│   └── tests/  (na verdade fica em apps/api/tests/)
│       ├── conversation/
│       │   ├── test_condition.py                        # NEW — 30+ casos unit (operadores, AND, key inexistente)
│       │   ├── test_pipeline_executor.py                # NEW — fluxos com mock LLM (success/skip/error)
│       │   ├── test_steps_classifier.py                 # NEW — output schema validation
│       │   ├── test_steps_clarifier.py                  # NEW — terminating step behavior
│       │   ├── test_steps_specialist.py                 # NEW — routing_map + default_model
│       │   ├── test_steps_resolver.py                   # NEW — tools + entity extraction
│       │   ├── test_steps_summarizer.py                 # NEW — summarized_context substitui histórico
│       │   ├── test_pipeline_backwards_compat.py        # NEW — gate SC-008 (suite + zero overhead)
│       │   └── test_pipeline.py                         # UNCHANGED — gate SC-007/SC-008
│       ├── integration/
│       │   ├── test_pipeline_executor_pg.py             # NEW — testcontainers-postgres + asyncpg + RLS
│       │   └── test_admin_pipeline_steps.py             # NEW (PR-5)
│       └── benchmarks/
│           └── test_overhead_no_pipeline.py             # NEW — bench p95 ≤5 ms (SC-010 hard gate)

apps/admin/                                              # Next.js 15 (PR-5/PR-6, P2 — pode ser cortado)
├── app/admin/agents/[id]/
│   └── pipeline-steps/
│       └── page.tsx                                     # NEW — UI gestão de steps (PR-5)
├── components/
│   ├── pipeline-step-form.tsx                          # NEW — formulário tipado por step_type (PR-5)
│   ├── pipeline-step-list.tsx                          # NEW — lista ordenada + reorder (PR-5)
│   └── trace-detail.tsx                                 # MODIFIED — render sub_steps quando presentes (PR-6)
└── lib/api/pipeline-steps.ts                            # NEW — wrappers TanStack Query (PR-5)
```

**Structure Decision**: Single web-service repo (`paceautomations/prosauai`). Pipeline executor é módulo Python isolado em `prosauai/conversation/pipeline_executor.py` chamado por `pipeline.py` quando há ≥1 step configurado para o agente. Frontend (Next.js 15 em `apps/admin/`) entra apenas em PR-5/PR-6 (P2, sujeito a cut-line).

## Implementation Phases (Shape Up — sequenciamento por valor)

> Cada PR deixa o sistema funcional e mergeable. Hard gate de regressão (SC-008) repetido a cada PR.

### PR-1 — Schema base (US6 backbone, ~4 h)

**Objetivo**: criar tabela + coluna sem mudar comportamento de runtime.

- Migration `20260601000010_create_agent_pipeline_steps.sql` — tabela exatamente como em [`domain-model.md`](../../engineering/domain-model.md) linha 244 (RLS ON, policy `tenant_isolation`, índices `(agent_id, step_order)` e `(tenant_id)`).
- Migration `20260601000011_alter_trace_steps_sub_steps.sql` — `ALTER TABLE public.trace_steps ADD COLUMN sub_steps JSONB` (idempotent via `ADD COLUMN IF NOT EXISTS`). Sem RLS — herda regra ADR-027.
- Repository `prosauai/db/queries/pipeline_steps.py` — `list_active_steps(conn, agent_id) -> list[PipelineStepRow]`. `replace_steps(conn, agent_id, steps_json)` (transação atômica DELETE+INSERT). Função `validate_steps_payload(steps_json) -> list[ValidationError]` consultada por admin endpoints (PR-5) e migration scripts.
- Constante `MAX_PIPELINE_STEPS_PER_AGENT = 5` em `prosauai/conversation/pipeline_constants.py` (módulo novo, evita import circular).
- Testes: `tests/integration/test_pipeline_steps_repository_pg.py` (RLS isolation, UNIQUE constraint, max 5 steps).

**Gate**: migrations idempotentes (FR-072); suite existente passa intacta (`make test`).

### PR-2 — Pipeline executor + condition + step types (US1+US2 core, ~8 d)

**Objetivo**: executor declarativo funcional ponta-a-ponta com 3 step types (classifier, clarifier, specialist). Resolver e summarizer ficam em PR-4.

- `prosauai/conversation/condition.py` — avaliador puro:
  - `evaluate(condition: dict | None, scope: dict) -> bool` — `None` → True; dict vazio → True; demais regras conforme FR-024 + Clarifications.
  - `_parse_predicate(value: str) -> (operator, literal)` — regex `^(<=|>=|!=|==|<|>|in)\s*(.+)$`.
  - `_resolve_path(scope, "classifier.confidence") -> Any | _MISSING` — dotted lookup.
  - Erro de avaliação OR chave inexistente → False + structlog `condition_eval_skipped` com `agent_id`, `step_index`, `condition`, `reason`. Warning **deduplicado uma vez por (agent_id, step_index)** via in-process LRU cache (FR-024 evita flood).
  - 30+ unit tests cobrindo operadores, AND-implícito, sintaxe quebrada, dotted paths inexistentes.

- `prosauai/conversation/pipeline_state.py` — `@dataclass PipelineState` com:
  - `classifier: dict | None` — output do classifier step (ou None).
  - `clarifier: dict | None`, `resolver: dict | None`, `specialist: dict | None`, `summarizer: dict | None`.
  - `summarized_context: str | None` — substitui histórico para steps subsequentes (FR-015).
  - `context: dict` — meta (`message_count`, `is_first_message`, etc.) usado por conditions.
  - Método `to_scope() -> dict` retorna shape consumido pelo `condition.evaluate()`.

- `prosauai/conversation/steps/base.py` — `Protocol PipelineStep`:
  ```python
  class PipelineStep(Protocol):
      step_type: ClassVar[str]
      async def execute(
          self,
          *,
          config: dict,
          state: PipelineState,
          context_messages: list[ContextMessage],
          user_message: str,
          deps: ConversationDeps,
          semaphore: asyncio.Semaphore,
      ) -> StepResult: ...
  ```
  `StepResult` dataclass: `output: dict`, `text_for_customer: str | None` (não-None encerra pipeline → terminating_step), `model_used: str | None`, `tokens_in: int`, `tokens_out: int`, `cost_usd: Decimal`, `tool_calls: list | None`, `latency_ms: int`.

- Step types (PR-2 entrega 3):
  - `steps/classifier.py` — pydantic-ai Agent com `output_type=ClassifierOutput` (Pydantic model com `intent: str`, `confidence: float`, `explanation: str | None`); modelo + prompt_slug + intent_labels via `config`. Falha de parse → step erro (não retry).
  - `steps/clarifier.py` — pydantic-ai Agent com texto livre (≤140 chars validados); seta `text_for_customer = output.question_text` (terminating).
  - `steps/specialist.py` — wrap thin sobre `agent.py:generate_response()` injetando `model = config.routing_map.get(state.classifier.intent, config.default_model)`. Reusa toda a infra de tools/sandwich/temperature.

- `prosauai/conversation/pipeline_executor.py` — orquestrador:
  ```python
  async def execute_agent_pipeline(
      *,
      steps: list[PipelineStepRow],
      agent_config: AgentConfig,
      prompt: PromptConfig,
      context: list[ContextMessage],
      user_message: str,
      classification: ClassificationResult,
      deps: ConversationDeps,
      semaphore: asyncio.Semaphore,
      tenant: Any | None = None,
      pipeline_timeout_seconds: float = 60.0,
  ) -> PipelineExecutionResult:
      """Executa steps em ordem, avalia condition, encadeia outputs.
      Returns final response_text + sub_steps[] + GenerationResult-like
      aggregate (model_used = último specialist; tokens = soma).
      """
  ```
  Algoritmo:
  1. Snapshot ATÔMICO dos `steps` (cópia local) — captura no início, não recarrega.
  2. Inicializa `PipelineState`, `sub_steps: list[StepRecord] = []`.
  3. Loop `for step in steps`:
     - Avalia `condition.evaluate(step.condition, state.to_scope())` → False → emite StepRecord(status=skipped, output={"reason": condition_repr}); continue.
     - Resolve `PipelineStep` impl via registry (step_type → class).
     - Try: `result = await asyncio.wait_for(step_impl.execute(...), timeout=step_timeout)`.
     - Catch (TimeoutError, ConnectionError, RuntimeError, ValidationError) → log `pipeline_step_failed` + emite StepRecord(status=error) + marca subsequentes skipped (`reason: prior_step_failed`) + retorna fallback canned.
     - Atualiza `state` (`setattr(state, step.step_type, result.output)`); se `step.step_type=='summarizer'` → `state.summarized_context = result.output['summary_text']`.
     - Se `result.text_for_customer is not None` → `terminating_step = step.step_type`; quebra loop e marca subsequentes como skipped.
  4. Calcula agregados (custo, tokens) e retorna.

- Modificação `pipeline.py:_generate_with_retry()` — branch:
  ```python
  pipeline_steps = await pipeline_steps_repo.list_active_steps(conn, agent_id)
  if not pipeline_steps:
      # Caminho atual — zero mudança.
      return await generate_response(...)
  return await execute_agent_pipeline(steps=pipeline_steps, ...)
  ```
  O lookup `list_active_steps` roda DENTRO do span `conversation.generate` para visibilidade; usa o `pool` per-tenant (RLS aplica).

- `step_record.py` — adicionar `sub_steps: list[StepRecord] | None = None` (default None mantém compat). Validar lista ≤5 sem inflar tamanho.

- `trace_persist.py` — passar `sub_steps` no INSERT da row `generate_response` (serializado como JSONB).

- Testes (PR-2):
  - 30+ unit em `test_condition.py`.
  - `test_pipeline_executor.py` — mocks de `PipelineStep`; cenários: sucesso linear, skip por condition, terminating step (clarifier), erro no meio (rest skipped), timeout no specialist.
  - `test_steps_classifier.py` — output schema válido/inválido, intent fora de `intent_labels`.
  - `test_steps_clarifier.py` — terminating, length validation.
  - `test_steps_specialist.py` — routing_map + default_model fallback.
  - `test_pipeline_backwards_compat.py` — fixture com `pipeline_steps=[]`; verifica que `generate_response` é chamado, `pipeline_executor.execute_agent_pipeline` NÃO é chamado, e que a saída é byte-equivalente (mock LLM mesmo seed).
  - `tests/benchmarks/test_overhead_no_pipeline.py` — 100 iterações; assert p95 do delta `with_lookup - without_lookup` ≤5 ms (SC-010).

**Gate**: SC-008 (suite passa) + SC-010 (overhead p95 ≤5 ms).

### PR-3 — Tracing + metadata + observability (US5 backbone, ~3 d)

**Objetivo**: visibilidade completa em `trace_steps.sub_steps`, `messages.metadata`, OTel spans.

- Modifica `pipeline_executor.py` para emitir, por step:
  - OTel sub-span `conversation.pipeline.step` com attributes `step.type`, `step.order`, `step.model`, `step.condition_evaluated`, `step.terminating`.
  - StepRecord com `name="generate_response.{step_type}"` (ou usa estrutura aninhada — D-PLAN-04 abaixo) — payload truncado a 4 KB por sub-step.
- Modifica `pipeline.py` para escrever em `messages.metadata`:
  ```python
  metadata = {
      "terminating_step": exec_result.terminating_step,
      "pipeline_step_count": len(steps),
      # pipeline_version: SOMENTE quando agent_config_versions existir (D-PLAN-02)
  }
  ```
  Para agentes single-call: NOT escreve esses campos (FR-064).
- Modifica `step_record.py` `_record_step` helper para passar `sub_steps` quando presente.
- Modifica `trace_persist.py:persist_trace` — INSERT da row `generate_response` agora inclui `sub_steps` JSONB.
- Atualiza `STEP_NAMES` para refletir que `generate_response` pode conter aninhado, mas mantém schema flat de top-level (sem novo top-level name).

- Testes:
  - `test_trace_persist_sub_steps_pg.py` (integration) — INSERT row com sub_steps; SELECT confirma JSON correto + cap 32 KB enforce.
  - Extender `test_pipeline_executor.py` para verificar `messages.metadata.terminating_step` é gravado.

**Gate**: SC-008 ainda passa; trace tem sub_steps no integration test; payload bytes within cap.

### PR-4 — Resolver + summarizer (US1 enriquecido, ~3 d)

**Objetivo**: completar os 5 step types da v1.

- `steps/resolver.py` — pydantic-ai Agent com `output_type=ResolverOutput` (Pydantic model com `entities: dict[str, Any]`); usa tools habilitadas via `prompt.tools_enabled` mesmo padrão de `agent.py:get_enabled_tools`.
- `steps/summarizer.py` — pydantic-ai Agent texto; output `{summary_text, message_count}` (count = quantas mensagens originais foram resumidas); seta `state.summarized_context` (FR-015 — substitui, não prepende). Steps subsequentes consomem `state.summarized_context` em vez do `context_messages` original quando não-None.
- Modifica `pipeline_executor.py` para passar `effective_context = state.summarized_context or original_context_messages` aos steps subsequentes ao summarizer.
- Testes específicos para cada step type.

**Gate**: SC-008.

### PR-5 — Admin UI (US3, P2, ~5 d — sujeito a cut-line)

**Objetivo**: configurar pipeline sem SQL.

- Backend `apps/api/prosauai/admin/pipeline_steps.py`:
  - `GET /admin/agents/{id}/pipeline-steps` → `list[PipelineStepResponse]` (ordenada por step_order).
  - `PUT /admin/agents/{id}/pipeline-steps` body `{steps: [...]}` — substitui lista inteira atomicamente (transação `BEGIN; DELETE; INSERT...; COMMIT`); valida via `validate_steps_payload`; 422 com `field_errors` em caso de problema; emite `audit_log` com diff.
  - Schemas Pydantic em `admin/schemas/pipeline_steps.py` — discriminated union por `step_type` (FR-043 — só campos relevantes ao tipo aparecem).
- Frontend `apps/admin/app/admin/agents/[id]/pipeline-steps/page.tsx`:
  - Lista vertical de steps (cards) com botões Add / Edit / Reorder (up/down, sem drag para v1) / Remove.
  - Dialog com `pipeline-step-form.tsx` — formulário tipado por step_type (renderiza condicionalmente os campos).
  - `lib/api/pipeline-steps.ts` — TanStack Query hooks com optimistic update.
- Atualizar `agents.py` admin endpoint para incluir `pipeline_steps_count` na listagem.

**Gate**: SC-006 (operador adiciona step em <3 min); audit_log preenchido; PUT atômica.

### PR-6 — Trace Explorer + group-by-version (US4+US5 frontend, P2, ~3 d — sujeito a cut-line)

**Objetivo**: visualizar sub-steps no Trace Explorer + comparar versões.

- Backend `traces.py` admin endpoint — incluir `sub_steps` no payload do trace detail quando presente.
- Frontend `components/trace-detail.tsx` — quando `step.sub_steps`, renderiza accordion aninhado com mesmo visual dos top-level (waterfall, duração, status, accordion expansível com input/output/modelo/tokens).
- Frontend `components/perf-ai-card.tsx` (épico 008) — adicionar toggle "Group by version" quando `agent_version_id` distinto >1; usa `?group_by=agent_version` no endpoint de Performance AI.
- Filtros na lista de traces:
  - `?terminating_step=clarifier` — query `WHERE output_jsonb->>'terminating_step'='clarifier'` no row `generate_response`.
  - `?pipeline_version=<uuid>` — query `WHERE agent_version_id=$1` em trace_steps.

**Gate**: SC-007 (debug em <1 min); toggle visível no canary; sub_steps renderizam.

### Cut-line decision

Se ao final da semana 3 PR-1..PR-4 não estiverem mergeados E em produção em pelo menos 1 tenant via SQL, **abortar PR-5 e PR-6 deste épico** e abrir épico 016 (`015b-agent-pipeline-admin-ui`) para retomar depois. Ship absoluto desta entrega exige só PR-1..PR-4 + um runbook simples ("como configurar pipeline via SQL").

## Phase 0: Outline & Research

Ver [`research.md`](./research.md) para o detalhamento das 5 alternativas-chave (R1..R5), cada uma com pros/cons + decisão + justificativa.

Resumo das decisões (D-PLAN-01..D-PLAN-12):

| # | Decisão | Alternativa rejeitada | Justificativa curta |
|---|---------|----------------------|---------------------|
| D-PLAN-01 | sub_steps como **coluna JSONB nova** em `trace_steps` (não tabela aninhada nem nested em `output`) | Tabela `trace_sub_steps` com FK → over-engineering p/ fan-out ≤5; nested em `output` JSONB → estoura cap 8 KB | Cap natural 5 sub-steps × 4 KB = 20 KB cabe folgado em coluna dedicada; queries simples (`WHERE name='generate_response' AND sub_steps IS NOT NULL`); migration trivial. |
| D-PLAN-02 | **Não** implementar `agent_config_versions` neste épico — pipeline_steps direto em tabela própria com FK → `agents.id` | Implementar ADR-019 dentro deste épico (escopo +1.5 semana) | Versioning não existe em produção apesar de ADR aprovado; aumentar escopo aqui violaria 3-week appetite. Rollback = `DELETE WHERE agent_id=X`; histórico = `audit_log`. Documentado follow-up. |
| D-PLAN-03 | Pipeline executor em **módulo separado** (`pipeline_executor.py`) | Branch inline em `_generate_with_retry` | Mantém `pipeline.py` legível; testabilidade unit isolada do orquestrador top-level; switch é 5 linhas em `_generate_with_retry`. |
| D-PLAN-04 | Cada sub-step é **objeto JSON dentro do array `sub_steps`** com mesmas chaves de StepRecord (order, name=`{type}`, status, duration_ms, model, tokens_in, tokens_out, input, output, error) | Criar 5 novos top-level step_names (`pipeline_classifier`, `pipeline_specialist`, ...) | Mantém schema top-level estável (CHECK `step_order BETWEEN 1 AND 12` continua válido); evita 5 ALTER CHECK migrations. |
| D-PLAN-05 | **Sem cache** de pipeline_steps lookup (asyncpg direto) | Redis cache 60s TTL keyed em agent_id | SC-010 exige ≤5 ms p95; índice `(agent_id, step_order)` torna lookup sub-ms; cache adiciona surface de stale config. Reavaliar se prod mostrar p95 >3 ms. |
| D-PLAN-06 | **Snapshot atômico** dos steps no início do `_generate_with_retry` (cópia local) | Recarregar a cada step | Hot reload concorrente NÃO afeta execução em curso (FR-020); cópia local é zero overhead. |
| D-PLAN-07 | Condition evaluator usa **regex parser + dict scope** (sem AST/eval/ast.literal_eval) | mini-DSL com pyparsing, ou `eval()` sandbox | Regex `^(<=|>=|!=|==|<|>|in)\s*(.+)$` cobre 100% dos casos da v1 (FR-024); eval mesmo sandboxed = risco; pyparsing = dependência nova proibida. |
| D-PLAN-08 | `routing_map` no specialist é **dict literal no config** (`{intent_label: model_name}`) com `default_model` obrigatório | Tabela separada `agent_step_routing` | Dict de 3-10 entradas em JSONB é trivial; tabela separada = JOIN extra no caminho hot. Validador checa modelo conhecido via `pricing.PRICING_TABLE` (ADR-029). |
| D-PLAN-09 | `prompt_slug` no config referencia **`prompts.version`** existente (chave `(agent_id, version)`) | Tabela separada `pipeline_step_prompts` | Reusa tabela existente, sem duplicação; engenheiro de prompt já trabalha com versões. Validador checa existência. |
| D-PLAN-10 | Admin UI (PR-5) usa **PUT replace-all** em vez de PATCH per-step | PATCH per-step | Atomicidade trivial (BEGIN; DELETE; INSERT*; COMMIT); evita race entre múltiplos PATCHes; UI envia lista completa após edição. |
| D-PLAN-11 | Step types implementados como **classes em arquivos separados** com Protocol comum | Funções soltas em `pipeline_executor.py` | Testabilidade unit; futuro extension fica trivial (adicionar arquivo). Registry simples `_STEP_TYPES = {"classifier": ClassifierStep, ...}`. |
| D-PLAN-12 | Fallback canned reusa **`FALLBACK_MESSAGE` existente** do `_generate_with_retry` | Mensagem específica por step type | Consistência com UX atual; clientes não distinguem qual step abortou. Trace contém detalhes para debug. |

## Phase 1: Design & Contracts

### Data model

Ver [`data-model.md`](./data-model.md) para DDL completo, ER e cap policy. Resumo:

```sql
-- NOVA tabela
CREATE TABLE public.agent_pipeline_steps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id),
    agent_id    UUID NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
    step_order  INT NOT NULL CHECK (step_order BETWEEN 1 AND 5),
    step_type   TEXT NOT NULL CHECK (step_type IN ('classifier','clarifier','resolver','specialist','summarizer')),
    config      JSONB NOT NULL DEFAULT '{}'
                CHECK (octet_length(config::text) <= 16384),  -- 16 KB cap
    condition   JSONB,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_id, step_order)
);
ALTER TABLE public.agent_pipeline_steps ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.agent_pipeline_steps
    USING (tenant_id = public.tenant_id())
    WITH CHECK (tenant_id = public.tenant_id());
CREATE INDEX idx_pipeline_agent_active ON public.agent_pipeline_steps (agent_id, is_active, step_order);
CREATE INDEX idx_pipeline_tenant ON public.agent_pipeline_steps (tenant_id);

-- ALTER em trace_steps (épico 008)
ALTER TABLE public.trace_steps
    ADD COLUMN IF NOT EXISTS sub_steps JSONB;
COMMENT ON COLUMN public.trace_steps.sub_steps IS
    'Pipeline sub-steps for generate_response only. Capped at 32 KB total; each sub-step truncated to 4 KB. NULL for single-call agents (épico 015).';
```

Limite **5 steps por agente** é enforced por:
1. CHECK constraint `step_order BETWEEN 1 AND 5` (nivel banco — defesa básica).
2. Aplicação valida no `validate_steps_payload(steps_json)` antes de qualquer INSERT (mensagem 422 amigável).
3. Constante Python `MAX_PIPELINE_STEPS_PER_AGENT = 5` central.

### Contracts

Ver [`contracts/openapi.yaml`](./contracts/openapi.yaml) para schemas completos. Endpoints novos (PR-5, P2):

| Method | Path | Descrição |
|--------|------|-----------|
| GET | `/admin/agents/{id}/pipeline-steps` | Lista steps ordenados (admin only, BYPASSRLS) |
| PUT | `/admin/agents/{id}/pipeline-steps` | Substitui lista inteira (atomic); 422 em validação |
| GET | `/admin/agents/{id}` (existente, modificado) | Inclui `pipeline_steps_count` |
| GET | `/admin/traces/{trace_id}` (existente, modificado) | Inclui `sub_steps` no row `generate_response` |
| GET | `/admin/performance` (existente, modificado) | Aceita `?group_by=agent_version` quando >1 versão (PR-6) |

Discriminated union para body PUT:

```yaml
PipelineStepWrite:
  type: object
  required: [step_order, step_type, config]
  properties:
    step_order: { type: integer, minimum: 1, maximum: 5 }
    step_type: { type: string, enum: [classifier, clarifier, resolver, specialist, summarizer] }
    is_active: { type: boolean, default: true }
    condition: { $ref: '#/components/schemas/PipelineCondition' }
    config:
      oneOf:
        - $ref: '#/components/schemas/ClassifierConfig'
        - $ref: '#/components/schemas/ClarifierConfig'
        - $ref: '#/components/schemas/ResolverConfig'
        - $ref: '#/components/schemas/SpecialistConfig'
        - $ref: '#/components/schemas/SummarizerConfig'
      discriminator: { propertyName: __step_type__ }
```

### Quickstart

Ver [`quickstart.md`](./quickstart.md) para passo-a-passo de:
- Setup local (testcontainers vs docker-compose).
- Aplicar migrations e seed agente de teste.
- Configurar pipeline via SQL (US1 path).
- Validar US1 (classifier+specialist barato/caro).
- Validar US2 (clarifier por confidence baixa).
- Validar US6 (regression — agente sem steps).
- Verificar trace no Trace Explorer (US5).

### Agent context

Após PR-2 mergear, rodar `.specify/scripts/bash/update-agent-context.sh claude` para registrar:
- New module `prosauai/conversation/pipeline_executor.py` no contexto Claude.
- Pattern `condition.evaluate(scope)` como referência para futuros features de condicionalidade.
- Constraint `MAX_PIPELINE_STEPS_PER_AGENT = 5`.

## Complexity Tracking

> Vazio — Constitution Check passou sem violations.

## Risks & Open Questions

| Risco / Questão | Mitigação / Estado |
|----------------|--------------------|
| `agent_config_versions` (ADR-019) não existe — canary verdadeiro fica fora do escopo | Aceito (D-PLAN-02). Pipeline_steps direto em tabela; rollback via DELETE atômico; histórico via audit_log (PR-5). Follow-up épico para ADR-019. |
| Cap 32 KB em `sub_steps` JSONB pode ser estreito se 5 specialists com tool_calls grandes | Mitigado: truncate 4 KB por sub-step → 5 × 4 = 20 KB worst-case. Tool_calls truncados separadamente conforme step_record existente. |
| Condition evaluator semântica mudar entre v1 (regex) e v2 (futuro AST) | Aceito: v1 é deliberadamente conservadora (sem OR/parens); migração futura para AST mantém superset compatível. Contrato documentado em `condition.py` docstring + research.md R3. |
| Frontend Recharts/TanStack/shadcn não estarem alinhados ao épico 008 quando PR-5 entrar | Mitigado: PR-5 só inicia depois que PR-1..PR-4 estão mergeados. Se épico 008 ainda em flux, PR-5 fica atrás. |
| `prompts.version` é varchar grosso (ex: '1.0', '2.1') sem garantia de monotonicidade global | Aceito: `prompt_slug` no config refere uma versão específica (string match); não usamos para canary aqui. |
| Pipeline executor adicionar latência mensurável mesmo com 1 specialist (vs single call) | Mitigado: bench em PR-2 compara `specialist-only` vs `generate_response` direto; se delta >50 ms, optimizar (skip executor para 1-step pipelines). |
| Tests do pipeline existente quebrarem por imports cruzados | Mitigado: `pipeline_constants.py` evita import circular; PR-1 já valida antes de PR-2. |

## Decision Audit Trail

| ID | Decisão | Skill | Source |
|----|---------|-------|--------|
| Clarif-1 | Operadores condition: `<,>,<=,>=,==,!=,in`; AND-implícito | clarify | spec.md Clarifications 2026-04-27 (autônoma) |
| Clarif-2 | Zero retry — fallback canned imediato | clarify | spec.md Clarifications 2026-04-27 (autônoma) |
| Clarif-3 | Summarizer **substitui** histórico em `summarized_context` | clarify | spec.md Clarifications 2026-04-27 (autônoma) |
| Clarif-4 | `MAX_PIPELINE_STEPS_PER_AGENT=5` hard-coded v1 | clarify | spec.md Clarifications 2026-04-27 (autônoma) |
| Clarif-5 | Filtros via `messages.metadata` + `trace_steps.agent_version_id` (sem novas colunas) | clarify | spec.md Clarifications 2026-04-27 (autônoma) |
| D-PLAN-01..12 | Ver tabela em Phase 0 acima | plan | autônoma — tradeoffs em research.md |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo para epic 015. Decisões críticas (D-PLAN-01..12) capturadas: (a) sub_steps como nova coluna JSONB em trace_steps com cap 32 KB / 4 KB por sub-step; (b) NÃO implementar agent_config_versions (ADR-019) neste épico — pipeline_steps direto em tabela própria com FK agents; (c) executor em módulo separado pipeline_executor.py; (d) condition evaluator regex puro (sem AST/eval); (e) snapshot atômico dos steps no início; (f) sem cache Redis (lookup direto otimizado); (g) routing_map dict no config + default_model; (h) PUT replace-all no admin (atomic). Sequência: PR-1 schema (4h) → PR-2 executor + 3 step types + condition (8d, coração) → PR-3 tracing + metadata (3d) → PR-4 resolver+summarizer (3d) → PR-5 admin UI P2 (5d, sujeito a cut-line) → PR-6 trace explorer + group-by-version P2 (3d). Hard gates: SC-008 (suite existente passa) + SC-010 (overhead ≤5 ms p95). Cut-line: PR-5+PR-6 viram épico 015b se passar de 4 semanas. Tasks devem cobrir os 6 PRs com numeração T001 (PR-1) até T0XX (PR-6); cada PR começa com tests-first quando aplicável (TDD). Risco principal: regressão silenciosa no caminho hot — mitigado por benchmarks dedicados em PR-2 e fixture `pipeline_steps=[]` byte-equivalente."
  blockers: []
  confidence: Alta
  kill_criteria: "Plan inválido se: (a) bench em PR-2 mostrar overhead >5 ms p95 mesmo com lookup otimizado — força repensar (cache Redis ou lazy-load); (b) `agent_config_versions` for shippado por outro épico antes de PR-1 — reabrir D-PLAN-02 para integrar versionamento aqui; (c) descobrir em PR-1 que `trace_steps.sub_steps` JSONB inflar storage além do orçado (>3 GB em 30d) — reduzir cap para 16 KB ou trocar para tabela separada; (d) tests-suite existente exigir mais que 5% de modificação para acomodar o branch novo no `_generate_with_retry` — força refatoração antes do PR-2; (e) decisão de produto cortar US3 inteira → PR-5 some, ainda valida cut-line; (f) integração com `prompts.version` revelar que prompts não tem RLS adequada para pipeline use-case — adicionar PR de hardening antes de PR-2."
