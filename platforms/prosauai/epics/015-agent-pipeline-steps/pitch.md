---
id: "015"
title: "Agent Pipeline Steps — multi-step reasoning declarativo (classifier + clarifier + resolver + specialist) com eval/trace per step"
slug: 015-agent-pipeline-steps
appetite: "3 semanas"
status: drafted
priority: P2
depends_on: ["011-evals", "014-alerting-whatsapp-quality"]
created: 2026-04-26
updated: 2026-04-26
---

# Epic 015 — Agent Pipeline Steps (multi-step reasoning declarativo)

> **DRAFT** — planejado em sequencia apos 014. Promocao via `/madruga:epic-context prosauai 015` (sem `--draft`) faz delta review e cria branch.

## Problema

A [ADR-006 (Agent-as-Data)](../../decisions/ADR-006-agent-as-data.md) **ja declarou** o padrao em §"Camadas de customizacao":

> *"Pipeline Steps | Sequencia de processamento do agente | `agent_pipeline_steps` table: classifier → clarifier → resolver → specialist (configuravel por agent). Zero steps = single LLM call (backward compatible)."*

E o [glossario do blueprint](../../engineering/blueprint.md) repete:

> *"Pipeline Step | Etapa configuravel de processamento dentro de um agente (classifier, clarifier, resolver, specialist). Zero steps = single LLM call (backward compatible)."*

Mas hoje (pos epic 005-014) **nada disso esta implementado**. Realidade pratica:

1. **`conversation/pipeline.py` tem 12 steps fixos** (M1-M14) onde a "geracao de resposta" e um **single-shot LLM call** ([conversation/agent.py:generate_response](.) — sandwich `safety_prefix + system_prompt + safety_suffix`). Nao ha multi-step reasoning. Bot recebe mensagem complexa ("quero saber se voces tem produto X em estoque, qual o prazo de entrega, e se tem desconto pra clientes antigos") → 1 chamada LLM tenta resolver tudo de uma vez. Resultado: respostas truncadas, tools usadas erradamente, ou alucinacao.

2. **Classificacao existe mas e isolada** ([conversation/classifier.py:classify_intent](.)) — produz `ClassificationResult.intent` antes da geracao, **mas o resultado nao molda o pipeline**. Apenas vira label de analytics. Nao ha um caminho onde "intent=billing" → resolver com tool especifica vs "intent=greeting" → resposta curta sem tool.

3. **Sem clarifier nativo**. Mensagens ambiguas hoje viram ou (a) resposta especulativa do specialist OU (b) handoff prematuro. Faltam etapas intermediarias ("posso confirmar? voce quer ver estoque atual ou previsao de chegada?") que reduziriam handoffs e subiriam a metrica `auto_resolved` (epic 011 [ADR-040](../../decisions/ADR-040-autonomous-resolution-heuristic.md)).

4. **Sem resolver-especialista**. Use case real do ResenhAI: cliente pergunta sobre **ranking de partida especifica**, sistema deveria (i) classificar como "ranking query", (ii) clarificar qual partida (se ambigua), (iii) chamar tool `resenhai_rankings` (epic 005), (iv) gerar resposta com voz de community manager. Hoje o agente tenta tudo em 1 prompt — o LLM precisa carregar TODAS as instrucoes de TODOS os fluxos no system_prompt, custo de tokens enorme + diluicao de qualidade.

5. **Eval e cego ao step que falhou**. Epic 011 mede `AnswerRelevancy` da resposta final. Se a resposta e ruim, **nao da pra dizer** se foi (a) classifier errou intent, (b) clarifier nao perguntou o que faltava, (c) resolver chamou tool errada, (d) specialist gerou em voz errada. Sem granularidade, melhoria continua via prompt review e cega.

6. **Trace nao mostra reasoning**. Epic 008 Trace Explorer renderiza 12 steps fixos com input/output. Multi-step reasoning vira **um unico bloco grande no step `agent.generate`** — operador ve "input=msg + output=resposta" sem ver onde a inteligencia decidiu coisa.

7. **Tools (epic 012/013) tem alvo errado**. RAG `search_knowledge` (012 in_progress) e Google Calendar (013 drafted) sao registradas no `tools_enabled` do agent. Sem multi-step, todas as tools competem na mesma chamada LLM — `gcal.create_event` e `search_knowledge` aparecem juntas no system prompt, LLM decide qual chamar com base em heuristica fraca. Multi-step permite isolar: classifier define intent → resolver usa **somente** as tools relevantes para aquele intent.

Epic 015 entrega o que ADR-006 prometeu **6 semanas atras**:

- **Pipeline_steps declarativo** como JSONB em `prompts.config_jsonb` — array ordenado de step configs (preset, prompt template, model, tools_enabled, output schema). Editado via admin existente epic 008.
- **Step engine generico `llm_step`** + **4 presets** (`classifier`, `clarifier`, `resolver`, `specialist`) com defaults sensiveis. Custom step para escape hatch.
- **Linear execution** em v1 — `step[0] → step[1] → ... → step[N-1]`. Saida final = output do ultimo step. Conditional routing em 015.1+.
- **Step outputs accumulados** acessiveis via Jinja-like template em prompts subsequentes (`{step_outputs.classifier.intent}`).
- **Eval + trace per step** — extensao das tabelas `eval_scores` (epic 011) e `trace_steps` (epic 008) com coluna `step_index`. Performance AI tab ganha breakdown por step.
- **Backward compat**: agent com `pipeline_steps` ausente OU `[]` → comportamento atual (single LLM call). Zero migration de Ariel/ResenhAI.
- **Admin JSONB editor** na aba "Agentes" existente — preset selector, prompt diff entre steps, schema validation client-side.

## Appetite

**3 semanas** (1 dev full-time, sequencia de 3 PRs mergeaveis em `develop`, reversivel via `pipeline_steps: null` no prompt config — agente volta ao single-shot em <1 query DB).

| Semana | Entrega | Gate |
|--------|---------|------|
| Sem 1 | Schema migration (`prompts.pipeline_steps JSONB NULL`) + executor linear + backward compat path + Pydantic models para step config + smoke test single-step minimum | Unit tests verdes; Ariel single-step `pipeline_steps=[{preset:'specialist', prompt:'...'}]` produz mesmo output que single-shot atual |
| Sem 2 | 4 presets (`classifier`, `clarifier`, `resolver`, `specialist`) com prompts default + output schemas Pydantic + Jinja-like template renderer + step_outputs accumulation + eval/trace integration (`step_index` em ambas tabelas) + 4 metricas Prometheus per-step (epic 014 dep) | Ariel 2-step pipeline (`classifier→specialist`) processa 1 mensagem real; Performance AI tab mostra breakdown; eval scores por step persistem |
| Sem 3 | Admin JSONB editor na aba "Agentes" (preset selector + prompt diff + schema validation) + Ariel rollout shadow→on com agente-piloto 4-step (classifier→clarifier→resolver→specialist) | Ariel agente-piloto 4-step em prod shadow 3d; comparacao A/B vs single-shot mostra `auto_resolved` ratio NAO regride; admin operador edita JSONB via UI e ve preview |

**Cut-line dura**: se semana 1 estourar (improvavel — schema + executor sao escopo controlado), **PR-B vira 015.1**. PR-A entrega so o framework (zero feature user-facing — backward compat ja funciona).

**Cut-line mole**: se semana 2 estourar (provavel: integracao eval/trace per-step exige extensao de schema das duas tabelas + retro-fit de queries do epic 008 admin), **admin UI editor vira 015.1**. Quality core (presets + executor + eval/trace) fica em 015. Operador edita JSONB via API/CLI no curto prazo.

**Cut-line mais mole**: se semana 3 estourar (complicacao no diff de prompts entre steps no admin), **rollout em prod vira 015.1**. Agentes ficam disponiveis para criar mas Ariel/ResenhAI seguem em single-shot ate validacao adicional.

## Dependencies

Prerrequisitos:

- **011-evals (shipped)** — `eval_scores` table esta em prod, com `tenant_id`, `conversation_id`, `message_id`, `evaluator`, `metric`, `score`, `details JSONB`. Extensao desta epic: coluna `step_index INT NULL` (NULL = score do agregado / single-shot legacy; INT = score do step especifico). Alteracao backward-compat (default NULL).
- **008-admin-evolution (shipped)** — `trace_steps` table tem `trace_id`, `step_index`, `step_name`, `input JSONB` truncado 8KB, `output JSONB` truncado 8KB, `duration_ms`, `error`. **Ja tem `step_index`** (era para os 12 steps do pipeline). Esta epic adiciona uma 2a dimensao via `step_kind ENUM('pipeline_step', 'agent_pipeline_step')` ou similar — definicao concreta no plano.
- **014-alerting-whatsapp-quality (drafted)** — Prometheus + Alertmanager + `prometheus_client`. Esta epic emite series novas (`pipeline_step_duration_seconds`, `pipeline_step_errors_total`, etc) via mesmo facade. Cardinality control da [ADR-045 (drafted)](../014-alerting-whatsapp-quality/pitch.md): `step_preset` label tem ≤5 valores (`classifier|clarifier|resolver|specialist|custom`), seguro.
- **005-conversation-core (shipped)** — `conversation/pipeline.py` orquestrador 12-step + `conversation/agent.py:generate_response` single-shot. Esta epic enfia o multi-step **dentro** do step 8 (`generate_response`), preservando os outros 11 steps externos (M1-M7, M9-M14). Boundary clara: pipeline outer (12 fixed) + pipeline inner (N configurable per agent).
- **006-production-readiness (shipped)** — migration runner fail-fast no startup, idempotente, advisory lock. Schema change segue o pattern.

Pre-requisitos que **nao bloqueiam**:

- **012-tenant-knowledge-base-rag (in_progress)** — `search_knowledge` builtin tool funcional. Step `resolver` v1 ja pode usar — preset `resolver` declara `tools_enabled: ['search_knowledge']` por default.
- **013-agent-tools-v2 (drafted)** — connector framework + Google Calendar. Step `resolver` aceita `tools_enabled: ['gcal.*']` via glob whitelist do epic 013. Zero coupling de timing.
- **009-channel-ingestion (shipped)** — Canonical schema, fixtures reais. Multi-step nao toca channel boundary.

ADRs novos desta epic (draft — promocao pode ajustar):

- **ADR-047** — Agent Pipeline Steps as JSONB on prompts (declarative multi-step reasoning, executor linear, presets + custom escape hatch)
- **ADR-048** — Per-step eval + trace correlation (extensao de schema das duas tabelas com `step_index` 2a dimensao)

ADRs estendidos:

- **ADR-006** agent-as-data — pipeline_steps materializado como JSONB em `prompts` (originalmente em `agents` — decisao tomada durante esta epic com base em ja existir versionamento de prompts ja pronto). Inalterado conceitualmente.
- **ADR-016** agent-runtime-safety — hard limits aplicam **per pipeline_step** (max 20 tool calls, 60s timeout, 8K context tokens). Limite agregado e o produto: agente 4-step com 60s/step pode consumir 240s no pior caso. **Override**: agent config opcional `total_timeout_seconds` (default 90s) abortando pipeline se exceder.
- **ADR-008** eval-stack — eval scores por step viram input para `Performance AI` tab; identificacao de gargalo de qualidade vira tooling diario.
- **ADR-027** admin-tables-no-rls — sem novas tabelas. `trace_steps` ja e admin-only.
- **ADR-028** fire-and-forget — eval scores per-step persistem fire-and-forget. Trace_step inserts seguem pattern existente.

Dependencias externas:

- **`jinja2`** — lib stdlib-adjacent, ja eh dep transitiva via FastAPI. Usada para template rendering nos prompts (`{step_outputs.classifier.intent}`). Modo restrito (no exec, no import) por seguranca.
- **Sem outras deps novas.**

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Step abstraction model | **Generic `llm_step`** com config declarativa + 4 presets (`classifier`, `clarifier`, `resolver`, `specialist`) que pre-preenchem defaults. Tipo `custom` como escape hatch. Engine unico — preset eh metadata, nao codigo separado. | Q1-A; ADR-047 novo |
| 2 | Storage | **Coluna JSONB `pipeline_steps` em `prompts`** — array ordenado de step configs (1 prompt → 1 pipeline). Pattern ADR-006 Agent-as-Data. Versionamento via existente `prompts.version`. NULL OR `[]` → backward compat. | Q2-A; ADR-006 reaffirmed; ADR-047 |
| 3 | Data flow | **Cada step recebe `(user_message, context_window, step_outputs_so_far)`** — todos os outputs anteriores acessiveis via dict (`step_outputs.classifier.intent`, etc). Step prompt eh Jinja-like template sobre essas vars. | Q3-A; ADR-047 |
| 4 | Conditional routing | **Linear-only em v1** — `pipeline_steps[0] → [1] → ... → [N-1]`. Ultimo step.output e a resposta final. Branching/DAG fica para 015.1+. | Q4-A; ADR-047 |
| 5 | Failure handling | **Step falha → retry 1x → handoff via epic 010** (mute conversation + mensagem amigavel). Reusa retry budget ADR-016 + handoff pattern existente. Fallback step adiado para 015.1+. | Q5-A; ADR-016 reaffirmed; epic 010 pattern |
| 6 | Eval & tracing per step | **Cada step gera 1 row em `eval_scores` (com novo `step_index INT NULL`) + 1 row em `trace_steps` (campo `step_index` ja existe — adicionar `step_kind ENUM`)**. 4 metricas Prometheus per-step: `pipeline_step_duration_seconds`, `pipeline_step_tokens_total`, `pipeline_step_errors_total`, `pipeline_step_executions_total`. | Q6-A; ADR-048 novo |
| 7 | Admin UI | **JSONB editor na aba "Agentes"** (epic 008) — preset selector, prompt diff entre steps, schema validation client-side via Zod gerado de openapi-typescript. Read+write via `PATCH /admin/prompts/{id}`. Sem visual graph editor em v1. | Q7-A |
| 8 | Backward compat | **`prompts.pipeline_steps IS NULL OR len == 0` → comportamento atual** (single LLM call via `agent.py:generate_response`). Ariel + ResenhAI nao precisam migrar. ADR-006 promete isso. | sem pergunta — ADR-006 reaffirmed |
| 9 | Tools per step | **Cada step declara `tools_enabled` opcional**. Default herda do agent prompt. Glob whitelist do epic 013 funciona (`['gcal.*', 'search_knowledge']`). Permite isolar tools por intent (classifier sem tools, resolver com `search_knowledge` + `gcal.*`, specialist sem tools). | sem pergunta — recomendacao base |
| 10 | Step output schema | Cada **preset declara output Pydantic**: `ClassifierOutput.intent: str`, `ClarifierOutput.questions: list[str]`, `ResolverOutput.answer: str` + `tool_calls: list`, `SpecialistOutput.final_response: str`. Custom step usa `Any` (perde type safety mas ganha flexibilidade). | sem pergunta — recomendacao base |
| 11 | Step prompt template | **Jinja-like restrict** sobre `{user_message, context_window, step_outputs.<step_name>.<field>}`. Modo sandboxed (sem `import`, `exec`, `__class__`). Renderer testado em CI contra payloads adversariais. | sem pergunta — ADR-047 |
| 12 | Step model override | Cada step declara `model` opcional (default = `prompts.model`). Permite step `classifier` em modelo barato + step `specialist` em modelo premium. Reusa `ADR-025 gpt-5.4-mini default`. | ADR-025 reaffirmed |
| 13 | Sandwich pattern preserved | **Apenas o ultimo step** aplica `safety_prefix + step_prompt + safety_suffix`. Steps intermediarios usam apenas `step_prompt` puro (eficiencia + presets ja sao internos). Cardinal: prompt injection mitigado no step que produz output user-facing. | ADR-016 reaffirmed |
| 14 | Latency budget per step | **≤2s p95 individual** (gpt-4o-mini latency típica). Pipeline total budget: agent prompt declara `total_timeout_seconds` (default 90s). Pipeline aborta se exceder; mensagem amigavel + handoff. | ADR-016 + NFR Q1 reaffirmed |
| 15 | NFR Q1 override per agent | Multi-step amplia naturalmente p95. Agentes multi-step **declaram override `nfr_p95_seconds`** no prompt config (default 8s para 4-step, 5s para 2-step). Alert rule do epic 014 fica per-agent dinamica via Prometheus query. | NFR Q1 amplified |
| 16 | Pipeline executor module | Novo `apps/api/prosauai/conversation/pipeline_steps_executor.py`: `async def execute_pipeline_steps(prompt: PromptConfig, context: PipelineContext) → SpecialistOutput`. Boundary clara — orchestrator existente (12-step) chama executor quando `pipeline_steps not in (None, [])`, senao chama `generate_response` legacy. | novo modulo |
| 17 | Eval per-step persistence | `EvalScoreRepo.save()` recebe param novo `step_index: int \| None`. NULL = score do agregado (legacy single-shot ou last-step-as-final). INT = score do step especifico. Migration: `ALTER TABLE eval_scores ADD COLUMN step_index INT NULL`. | ADR-048 novo |
| 18 | Trace per-step persistence | `trace_steps` ja tem `step_index INT` (1-12). Adicionar `step_kind TEXT NOT NULL DEFAULT 'pipeline'` ENUM `('pipeline', 'agent_step')`. Index `(trace_id, step_kind, step_index)`. Pipeline outer = `step_kind='pipeline'`, agent inner = `step_kind='agent_step'`. | ADR-048 novo |
| 19 | Per-step Prometheus series | 4 series novas via facade structlog (epic 010 pattern): `pipeline_step_duration_seconds{tenant, agent_id, step_preset, step_index}` (histogram), `pipeline_step_tokens_total{tenant, agent_id, step_preset, model}` (counter), `pipeline_step_errors_total{tenant, agent_id, step_preset, error_type}` (counter), `pipeline_step_executions_total{tenant, agent_id, step_preset}` (counter). Cardinality safe — `step_preset` ≤5 vals. | epic 014 dep |
| 20 | Preset definitions v1 | **classifier**: prompt detecta intent (5-10 categorias per agent), output `ClassifierOutput.intent + .confidence`. **clarifier**: prompt pergunta esclarecimento se ambiguo, output `ClarifierOutput.questions[]` (vazio se claro). **resolver**: prompt + tools_enabled busca info; output `ResolverOutput.answer + .tool_calls`. **specialist**: prompt aplica voz/tom; output `SpecialistOutput.final_response`. Defaults editaveis. | catalogo concreto |
| 21 | Custom step type | Escape hatch — `preset: 'custom'` aceita `output_schema: 'any'`. Permite tenant escrever step nao-coberto pelos 4 presets sem PR. v1 documenta como "use com cuidado — no type safety". | flexibilidade |
| 22 | Step retry budget | Cada step herda max 3 retries com backoff exponencial (ADR-016). Apos 3, pipeline aborta + handoff via epic 010. **NAO** ha retry no nivel do pipeline (sem repetir steps anteriores). | ADR-016 reaffirmed |
| 23 | Step circuit breaker | Per `(tenant, agent_id, step_preset)` abre apos 50 erros/5min. Half-open testa 1 execucao apos 5min. Pattern epic 010/013/014. Quando aberto: skip step + use fallback string OR escala para handoff. | ADR-015 extended |
| 24 | Eval threshold per step | v1: **apenas observa**, sem alerta automatico. Threshold per step calibrado durante shadow phase (3d Ariel). 015.1+ adiciona alerta dedicado por step com regression detection (epic 014 alert rule pattern). | calibracao gradual |
| 25 | Admin diff feature | Aba "Agentes" → seletor de prompt versao + diff visual entre steps de mesma versao + diff entre versoes. Reusa diff component do epic 008 (ja existe para `safety_prefix/system_prompt/safety_suffix`). | UX continuidade |
| 26 | Schema migration | 1 migration: `ALTER TABLE prompts ADD COLUMN pipeline_steps JSONB NULL`; `ALTER TABLE eval_scores ADD COLUMN step_index INT NULL`; `ALTER TABLE trace_steps ADD COLUMN step_kind TEXT NOT NULL DEFAULT 'pipeline'`. Idempotente, fail-fast no startup (epic 006). | ADR-024 reaffirmed |
| 27 | Backward compat test | Golden test em CI: agent com `pipeline_steps=NULL` produz **mesma resposta** que single-shot atual para 5 fixtures Ariel. Diff zero exigido para PR-A merge. | invariante operacional |
| 28 | Rollout | Ariel **agente-piloto novo** (nao migrar agentes existentes) com 4-step `classifier→clarifier→resolver→specialist`. Shadow 3d (logging only — comparacao A/B com single-shot copia do agente) → flip para `on` se `auto_resolved` ratio nao regride. ResenhAI fica para 015.1+ apos validacao Ariel. Outros agentes Ariel/ResenhAI permanecem single-shot. | epic 010/011 pattern |
| 29 | Step output truncation | 8KB JSONB limit (mesmo dos `trace_steps` epic 008). Output maior eh truncado com marker `...[truncated]`. UTF-8 multibyte safe (ja fixado em epic 008 issue B3). | epic 008 reaffirmed |
| 30 | Cardinality control | Labels Prometheus: `tenant` (≤100), `agent_id` (≤500), `step_preset` (≤5), `step_index` (≤10), `model` (≤10), `error_type` (≤20). Total max ≤500K series — bem dentro do hard cap 200/metric. Lint no startup. | epic 014 reaffirmed |

## Resolved Gray Areas

Decisoes tomadas durante este epic-context (2026-04-26, modo `--draft`):

1. **Step abstraction model (Q1)** — Generic `llm_step` + 4 presets + custom escape hatch. Declarativo, escalavel sem deploy. Permite preset selection com defaults sensiveis e ainda flexibilidade total.

2. **Storage (Q2)** — Coluna JSONB `pipeline_steps` em `prompts`. Pattern ADR-006 Agent-as-Data. Versionamento via `prompts.version` existente. Coexiste com `system_prompt/safety_prefix/safety_suffix` legacy.

3. **Data flow (Q3)** — Cada step recebe `(user_message, context, step_outputs_so_far)`. Jinja-like template em prompts subsequentes acessa outputs anteriores. Necessario para resolver acessar classifier.intent.

4. **Conditional routing (Q4)** — Linear-only em v1. Cobre 90% dos casos (classifier→clarifier→resolver→specialist). Branching/DAG vira 015.1+.

5. **Failure handling (Q5)** — Retry 1x + handoff via epic 010. Reusa pattern existente. Fallback step adiado.

6. **Eval & tracing per step (Q6)** — Extensao das tabelas eval_scores + trace_steps com `step_index` (eval) + `step_kind` (trace). 4 metricas Prometheus per-step. Performance AI tab ganha breakdown.

7. **Admin UI (Q7)** — JSONB editor na aba Agentes com preset selector + prompt diff + Zod validation. Visual graph editor adiado.

8. **Backward compat (sem pergunta)** — `pipeline_steps IS NULL OR len == 0` → comportamento atual. Zero migration. ADR-006 promete isso.

9. **Tools per step (sem pergunta)** — Cada step pode override `tools_enabled`. Glob whitelist epic 013 + builtin epic 012. Default herda do agent.

10. **Latency budget multi-step (sem pergunta)** — ≤2s p95 per step + agent declara `total_timeout_seconds` (default 90s). NFR Q1 amplificado via override `nfr_p95_seconds` per agent.

## Applicable Constraints

**Do blueprint** ([engineering/blueprint.md](../../engineering/blueprint.md)):

- Python 3.12, FastAPI, asyncpg, redis[hiredis], structlog, opentelemetry, httpx, **`jinja2`** (sandboxed). Sem novas deps externas.
- NFR Q1 (p95 <3s) — multi-step amplifica naturalmente. Override `nfr_p95_seconds` per agent (default 8s para 4-step). Alert rule epic 014 dinamica.
- NFR Q4 (safety bypass <1%) — sandwich pattern preservado **apenas no ultimo step**. Output guards (epic 005) continuam aplicados a `step_outputs[-1].final_response`.
- NFR Q10 (faithfulness >0.8) — eval per step permite identificar onde qualidade cai. Alerta dedicado per step em 015.1+.
- ADR-006 — Agent-as-Data; pipeline_steps materializado como prometido.
- ADR-008 — eval-stack; per-step viraadtrack-of-quality canonical.
- ADR-014 — tool registry; tools_enabled herdada e overridable per step.
- ADR-015 — circuit breaker estendido para `(tenant, agent_id, step_preset)`.
- ADR-016 — hard limits per step + total_timeout_seconds per agent.
- ADR-024 — schema migration via runner fail-fast.
- ADR-025 — model default `gpt-5.4-mini`; per-step override permitido.
- ADR-027 — sem novas tabelas admin-only.
- ADR-028 — fire-and-forget para eval/trace persistence.

**Do epic 008** (admin pattern reusado):

- pool_admin BYPASSRLS para queries cross-tenant (Performance AI breakdown).
- Diff component existente para prompts.
- TanStack Query v5 + Zod + openapi-typescript.

**Do epic 011** (eval pattern reusado):

- `eval_scores.evaluator` discrimina origem (`heuristic_v1`, `deepeval`, `human`). Per-step nao introduz novo evaluator — usa os mesmos.
- Reference-less metrics aplicaveis a outputs intermediarios (e.g., `Toxicity` em clarifier output).

**Do epic 014** (alerting pattern reusado):

- Prometheus + Alertmanager containers ja em prod (assumindo 014 sera shipped antes de 015 ativacao).
- Cardinality control rigoroso.

## Suggested Approach

**3 PRs sequenciais** mergeaveis em `develop`. Cada PR atras de feature gate (`prompts.pipeline_steps IS NULL` por default) — risco zero em prod.

### PR-A (Sem 1) — Schema + executor + backward compat

Backend foundation. Sem features user-facing. Tudo unit-tested.

- Migration `migrations/NNN_add_pipeline_steps.sql`: 3 ALTERs (prompts, eval_scores, trace_steps).
- `apps/api/prosauai/conversation/pipeline_steps_models.py`: Pydantic models — `StepConfig`, `StepPreset enum`, `ClassifierOutput`, `ClarifierOutput`, `ResolverOutput`, `SpecialistOutput`, `PipelineStepsConfig`.
- `apps/api/prosauai/conversation/pipeline_steps_executor.py`: `execute_pipeline_steps(prompt, context) → SpecialistOutput`. Linear loop. Retry/handoff integration.
- `apps/api/prosauai/conversation/pipeline.py`: orchestrator existente passa por `if prompt.pipeline_steps: → executor` else `→ generate_response legacy`.
- `apps/api/prosauai/conversation/template_renderer.py`: Jinja2 sandboxed renderer com whitelist de globals.
- Golden backward-compat test: 5 fixtures Ariel single-shot vs `pipeline_steps=NULL` produzem mesma resposta. Diff zero exigido.
- Unit tests para executor, template renderer, schema validation.

Gate: `pytest` verde; golden test produz diff zero; CI lint pass.

### PR-B (Sem 2) — Presets + eval/trace + Prometheus

Quality + observability completas. Permite criar pipelines reais.

- `apps/api/prosauai/conversation/presets.py`: 4 presets com prompts default + output schemas + tools_enabled defaults.
- `EvalScoreRepo.save()` aceita `step_index: int | None`. Pipeline executor chama por step.
- `TraceStepRepo.save()` extendido com `step_kind`. Executor emite `step_kind='agent_step'` para steps internos.
- 4 metricas Prometheus via facade (epic 014 dep).
- Integration tests: 2-step (`classifier→specialist`) processa fixture real, eval_scores tem 2 rows com step_index distinto, trace_steps tem 2 rows com step_kind='agent_step'.
- Performance AI tab (epic 008): query SQL extendida pra agrupar por `step_index`. Frontend renderiza breakdown como nova tab subtree.

Gate: Ariel agente-piloto 2-step processa 1 mensagem real em prod (shadow), Performance AI mostra breakdown, eval scores per step persistem corretos.

### PR-C (Sem 3) — Admin JSONB editor + Ariel rollout

UX + producao.

- `apps/admin/app/(dashboard)/agents/[id]/page.tsx`: secao "Pipeline Steps" com array de cards (1 per step), drag-reorder, preset selector dropdown, prompt textarea com Jinja syntax highlight, tools_enabled glob input, output_schema preview.
- `apps/admin/components/prompts-diff.tsx`: extensao do diff existente — agora compara cada step entre versoes. UI separa `safety_prefix`, `system_prompt`, `pipeline_steps[*]`, `safety_suffix`.
- `contracts/openapi.yaml`: schema para `pipeline_steps` array. Tipos regenerados via `pnpm gen:api` + Zod.
- `apps/api/prosauai/api/admin/prompts.py`: `PATCH /admin/prompts/{id}` aceita `pipeline_steps` no body. Validacao server-side.
- Rollout: Ariel cria **agente-piloto novo** com 4-step pipeline. Shadow 3d com logging do single-shot equivalente em paralelo (sem chamar LLM 2x — gera prompt single-shot em background pra comparacao). Flip para `on` se `auto_resolved` ratio nao regride.
- Documentacao runbook em `apps/api/prosauai/conversation/PIPELINE_STEPS.md`.

Gate: Ariel agente-piloto 4-step em prod `on`. Admin operador edita JSONB via UI e ve preview.

### Cut-line execucao

| Cenario | Acao |
|---------|------|
| Sem 1 estourar (>5d) | PR-A entrega so schema + executor sem template renderer. PR-B comecca com tarefa adicional. |
| Sem 2 estourar (>5d, parte 1: eval/trace integration complica) | Eval per-step vira 015.1. PR-B entrega so presets + Prometheus. Admin Performance AI breakdown adia 1 sem. |
| Sem 2 estourar (>5d, parte 2: presets default precisam tunar muito) | Preset `custom` cobre v1 com defaults minimos; presets `classifier/clarifier/resolver/specialist` ficam para 015.1+. |
| Sem 3 estourar (>5d) | Admin UI vira 015.1. Operador edita pipeline_steps via API/CLI. Ariel agente-piloto fica em prod via PATCH direto via tooling backend. |
| Tudo no prazo | ResenhAI rollout em 015.1 (observa Ariel 7d antes). |

## Riscos especificos desta epic

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Multi-step explode custo de tokens (classifier+clarifier+resolver+specialist = 4x chamadas LLM) | Alto | Media | Per-step model override (Q12); presets `classifier` + `clarifier` em modelo barato. Total cost monitorado via `pipeline_step_tokens_total` Prometheus. Cap diario per agent via Bifrost (epic 002). |
| Latencia p95 8s estoura NFR Q1 atual de 3s | Alto | Alta | NFR Q1 override per agent (Q15). Documentar em runbook que agentes multi-step tem NFR proprio. Performance AI tab mostra p95 per agent. |
| Jinja2 template injection em step prompt | Alto | Baixa | Sandboxed mode (no `import`, no `__class__`, no `__getattribute__`). CI test contra payloads adversariais conhecidos. |
| Step output supera 8KB JSONB limit | Medio | Media | Truncacao em `pipeline_step_output_truncated_total` counter. Alerta se >5% das execucoes truncam. |
| Backward compat quebrada por bug em executor | Alto | Baixa | Golden test diff zero exigido em PR-A. Prod tem agentes Ariel/ResenhAI com `pipeline_steps=NULL` — qualquer regressao quebra producao imediatamente. |
| Eval threshold per step e calibrado errado, gera alert spam | Medio | Media | v1 nao alerta automatico (Decision #24). Apenas observa por 3d shadow. 015.1+ adiciona alerts calibrados. |
| Trace_steps schema migration falha em VPS com volume grande | Medio | Baixa | `ALTER TABLE ... ADD COLUMN ... DEFAULT 'pipeline'` e fast (no rewrite no PG 11+). Pre-validado em staging. |
| Admin JSONB editor permite config invalida que quebra agent em runtime | Medio | Media | Schema validation client-side (Zod) + server-side (Pydantic) + dry-run no `PATCH` (executa preview com mensagem fixture e retorna outputs). |
| Steps em paralelo (futuro) nao caberao no design linear | Baixo | Baixa | v1 declara explicitamente linear-only. 015.1+ pode ramificar com `parallel_group` field se demanda. |
| Preset default prompts ficam genericos demais e tenant nao tira proveito | Medio | Alta | Preset = ponto de partida, nao fim. Admin diff feature ajuda tenant iterar. Documentacao runbook orienta padroes. |
| `step_outputs` cresce demais em pipeline 10-step e estoura context window | Medio | Baixa | Hard limit 8 steps em v1. Override per-agent. Alert se >5 steps em pipeline ativo. |

## Anti-objetivos (out of scope)

- **Conditional routing / DAG** — linear v1. Branching vira 015.1+ com demanda real (e.g., "se intent=billing, skip clarifier").
- **Visual graph editor admin** — JSONB editor cobre v1. Graph editor vira 015.1+ se 5+ tenants pedirem.
- **Eval threshold automatico per step** — v1 observa 3d shadow. Calibracao + alerts em 015.1+.
- **Steps em paralelo** — `parallel_group` field nao existe em v1. Performance optimization adiada.
- **Custom output schemas** alem de Pydantic + Any — `custom` step usa Any. Schema-as-data via ferramenta tipo OpenAPI fica fora.
- **Step result caching** — cada execucao re-roda todos os steps. Cache (e.g., classifier output cached por user para mesma mensagem) vira 015.1+.
- **Migrar agentes Ariel/ResenhAI existentes** — ficam single-shot. Agente-piloto novo prova o caminho. Migration manual sob demanda.
- **Per-tenant preset library** — tenants compartilham os 4 presets globais em v1. Custom presets per tenant em 015.1+.
- **Streaming entre steps** — pipeline executor e sincrono, output completo de cada step antes do proximo. Streaming entre steps fica fora.
- **Step abort por low confidence** — se classifier retorna `confidence < 0.7`, pipeline continua com `intent='general'` (pattern existente). Abort logic adiado.
- **A/B testing per agent** — comparacao single-shot vs multi-step e ad-hoc no shadow do PR-C. Framework formal de A/B (epic 015 sai e cria 015.X) fora.

---

> **Proximo passo (apos promocao via `/madruga:epic-context prosauai 015` sem `--draft`)**: `/speckit.specify prosauai 015-agent-pipeline-steps` para spec formal a partir desta pitch + delta review se mudou algo entre 2026-04-26 e a promocao.
