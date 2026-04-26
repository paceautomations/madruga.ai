---
id: "011"
title: "Evals — Offline (DeepEval) + Online (heuristico) + Dataset incremental"
slug: 011-evals
appetite: "3 semanas"
status: shipped
priority: P1
depends_on: ["002-observability", "010-handoff-engine-inbox"]
created: 2026-04-24
updated: 2026-04-24
delivered_at: 2026-04-25
---

# Epic 011 — Evals (offline + online fundidos)

## Problema

A [vision](../../business/vision.md) promete **70% de resolucao autonoma em 18 meses** como North Star. Hoje (pos-epic 010), nao existe nenhum mecanismo para medir isso — a plataforma entrega mensagens, persiste traces, silencia quando humano assume, mas **nao sabe dizer se a resposta foi boa**. Consequencias operacionais concretas:

1. **Performance AI tab** (epic 008) renderiza grafico "Quality Trend" com dado vazio. Admin olha um chart placeholder.
2. **NFR Q10** do blueprint fixa faithfulness medio >0.8 como target. Sem metrica, nao ha alerta, nao ha gate de producao.
3. **Prompt regression**: qualquer mudanca em `system_prompt` ou `safety_prefix` (epic 008 admin curation) pode regredir silenciosamente — nao ha CI gate validando.
4. **Thesis falsification**: os 70% de resolucao autonoma viraram premissa religiosa. Sem evals, a tese dos 18 meses (500 clientes, R$ 250K MRR) nao e falsificavel — qualquer cliente frustrado vira anedota, nao sinal.
5. **Cold-start problem**: nao temos dataset de referencia. Ariel + ResenhAI sao comunidades esportivas; fixtures do [tests/fixtures/captured/](../../engineering/blueprint.md#L200) cobrem payloads (parsing), nao qualidade de resposta. Construir golden dataset seed antes de ver trafego real seria benchmark-gaming.

Epic 011 fecha o buraco adotando **dois caminhos complementares**:

- **Online heuristico** — `conversation/evaluator.py` do epic 005 ja avalia resposta com heuristicas (APPROVE/RETRY/ESCALATE) sem LLM extra. Escopo desta epic: **persistir esses scores em `eval_scores`** com `evaluator='heuristic_v1'`, expondo series temporais no admin ja a partir do dia 1. Zero custo LLM adicional, zero impacto no p95 <3s (NFR Q1). Pre/pos-LLM guardrails de runtime sao o mesmo pipeline do safety (epic 005) emissor de sinal.
- **Offline DeepEval** batch com **metricas reference-less** (AnswerRelevancy, Toxicity, Bias, Coherence) rodando em cron noturno sobre `messages` do dia — grava em `eval_scores` com `evaluator='deepeval'`. Nao exige golden dataset para iniciar.

O **golden dataset cresce organicamente**: admin ganha acao "marcar trace como positivo/negativo" na Trace Explorer; esses traces formam a suite do Promptfoo CI, que comeca com 3-5 smoke cases escritos a mao (ex: "hello world", "cliente pede ranking ResenhAI", "cliente diz 'quero falar com humano'") e expande com cada trace estrelado.

Resolucao autonoma ganha definicao operacional conservadora: conversa **auto_resolved** quando (a) `ai_active=true` durante toda a conversa (sem mute), (b) nenhuma msg do cliente contem tokens de escalacao ("humano", "atendente", "pessoa", regex), (c) cliente silencia >=24h apos ultima resposta do bot. Cron noturno marca `conversations.auto_resolved` e popula o KPI North Star.

## Appetite

**3 semanas** (1 dev full-time, 1 PR mergeavel em develop, reversivel via `evals.mode: off` per-tenant em <60s).

| Semana | Entrega | Gate |
|--------|---------|------|
| Sem 1 | Schema + heuristico online (grava em `eval_scores`) + `auto_resolved` cron + feature flag | Ariel shadow |
| Sem 2 | DeepEval batch cron + reference-less metrics + Promptfoo smoke suite + golden curation API | Ariel shadow -> on se Q10 green |
| Sem 3 | Admin Performance AI: 4 cards novos + golden "star" UI em Trace Explorer + ResenhAI rollout | ResenhAI on |

**Cut-line**: se semana 2 estourar (cenario provavel: DeepEval integrations surpreendem com auth/rate-limit), a golden curation UI vira 011.1. Valor user-facing (heuristico online + offline DeepEval + Performance AI cards) sobrevive.

## Dependencies

Prerrequisitos (todos `shipped`):

- **002-observability** — Phoenix + OTel ja operacional. `trace_id` em todo log permite correlacionar eval score com trace especifico. DeepEval pode consumir spans direto de `observability.spans` para montar input/output pairs sem instrumentacao nova.
- **008-admin-evolution** — Performance AI tab, Trace Explorer, pool_admin BYPASSRLS, pattern fire-and-forget (ADR-028). Os 4 cards novos ocupam o espaco reservado para "Quality Trend". Golden "star" action encaixa como coluna nova no Trace Explorer.
- **010-handoff-engine-inbox** — `conversations.ai_active` + `handoff_events` + feature flag pattern (`off|shadow|on`). Reutilizado quase integralmente. Resolucao autonoma consulta `handoff_events` para excluir conversas que deram mute. Acao automatica em score baixo e intencionalmente NAO implementada neste epic (adiada para 011.1) — feature flag per-tenant preserva opcao.
- **005-conversation-core** — `conversation/evaluator.py` ja retorna scores heuristicos. Esta epic so persiste. Pipeline step "evaluate" ja existe; vira passagem obrigatoria por nova funcao de persistencia.

ADRs novos desta epic:

- **ADR-039** — Eval metric bootstrap sem golden dataset (reference-less DeepEval metrics como v1; golden grows incremental via admin curation)
- **ADR-040** — Autonomous resolution operational definition (heuristica A como canonica; revisitar com LLM-as-judge em 011.1)

ADRs estendidos (nao substituidos):

- **ADR-008** eval-stack — confirmed DeepEval+Promptfoo. Promptfoo com smoke suite inicial (3-5 casos); dataset Promptfoo cresce via golden curation.
- **ADR-027** admin-tables-no-rls — nova tabela `public.golden_traces` herda o carve-out (admin-only curation data).
- **ADR-028** pipeline fire-and-forget — persistencia do eval score online e fire-and-forget; Bifrost downtime nao bloqueia pipeline.

Dependencias externas: DeepEval lib (Python), Promptfoo CLI (Node). **Bifrost ja esta no critical path**; DeepEval usa o mesmo endpoint `/v1/chat/completions` para LLM-as-judge — zero integracao nova.

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Escopo v1 | **Offline (DeepEval batch) + Online heuristico (reusa `evaluator.py` do epic 005)**. LLM-as-judge online adiado para 011.1 — evita +R$0.02/msg em 10% samples antes de calibrar threshold. | Q1-B (epic-context 2026-04-24) |
| 2 | Cold-start sem dataset | **Bootstrap com reference-less metrics** — DeepEval `AnswerRelevancy`, `Toxicity`, `Bias`, `Coherence` nao exigem golden answer. Faithfulness adiado ate epic 012 RAG (ha contexto para comparar). | ADR-039 novo; Q3 (epic-context 2026-04-24) |
| 3 | Golden dataset | **Cresce incremental via admin curation** — admin "estrela" traces na Trace Explorer (positive/negative), esses casos alimentam Promptfoo CI. Suite comeca com 3-5 smoke cases escritos a mao. | ADR-039 novo; Q3 |
| 4 | Persistencia online | Todo eval score (heuristico + futuramente LLM-as-judge) grava em `eval_scores` com coluna `evaluator` discriminante: `heuristic_v1`, `deepeval`, `human` (golden curation). Schema ja existe ([domain-model.md:678-694](../../engineering/domain-model/#L678-L694)). | epic 005 schema |
| 5 | Resolucao autonoma | **Heuristica conservadora A**: `auto_resolved=true` sse (a) `ai_active` nunca foi `false` na conversa; (b) nenhuma msg do cliente contem tokens de escalacao (regex `humano\|atendente\|pessoa\|alguem real`); (c) cliente silencia >=24h. Cron noturno calcula e persiste em nova coluna `conversations.auto_resolved BOOLEAN`. LLM-as-judge v2 em 011.1. | ADR-040 novo; Q2-A |
| 6 | Acao em score baixo | **v1: apenas logar + Prometheus counter + alerta 24h** (`eval_score_below_threshold_total{tenant,metric}`). Zero acao automatica na conversa atual — evita regressao antes de calibrar threshold. Auto-handoff via epic 010 adiado para 011.1 apos 2-4 semanas de shadow data. | Q4-A |
| 7 | Dashboards | **Admin Performance AI tab** e a UI canonica (single pane of glass). 4 cards novos: (a) Faithfulness/Relevance trend 7d/30d; (b) Toxicity/Bias rate; (c) Eval coverage % (quantas msgs com score); (d) Autonomous resolution % 7d. Phoenix permanece como drill-down via `trace_id` mas sem duplicacao de visualizacoes agregadas. | Q5-B |
| 8 | Feature flag | **`evals.mode: off \| shadow \| on` per-tenant** em `tenants.yaml` + `evals.offline_enabled: bool` + `evals.online_sample_rate: 0.0-1.0`. Padrao `off`. Shadow emite `eval_scores` mas nao alerta nem conta pro SLO. Config_poller do epic 010 re-le em <=60s. | Q6-A; herdado do epic 010 |
| 9 | DeepEval metric set v1 | **4 reference-less metrics**: `AnswerRelevancy` (pergunta vs resposta), `Toxicity` (classificador), `Bias` (demografico/politico), `Coherence` (logica interna). Rodam em cron noturno sobre amostra de 200 msgs/tenant/dia (custo ~R$1/tenant/dia). | ADR-008 confirmed + ADR-039 |
| 10 | Promptfoo CI suite | **Suite inicial: 3-5 smoke cases escritos a mao** (hello world, pedido de stats ResenhAI, "quero falar com humano", injection tentativa, mensagem fora de topico). Expande automaticamente: trace estrelado pelo admin vira caso Promptfoo via gerador de YAML. Gate blocking no CI. | ADR-008 confirmed |
| 11 | Golden curation | **Nova tabela `public.golden_traces`** (admin-only, herda ADR-027 carve-out): `trace_id UUID, verdict TEXT CHECK (verdict IN ('positive','negative')), notes TEXT, created_by_user_id UUID, created_at TIMESTAMPTZ`. API: `POST /admin/traces/{trace_id}/golden {verdict, notes}`. UI: botao "star" na Trace Explorer. | ADR-027 extended |
| 12 | Autonomous resolution cron | **Novo periodic task** no FastAPI lifespan (padrao do epic 010): `autonomous_resolution_cron` com `pg_try_advisory_lock(hashtext('autonomous_resolution_cron'))` singleton. Cadencia diaria 03:00 UTC. Calcula heuristica A para conversas fechadas nas ultimas 24h. | pattern epic 010 |
| 13 | Evaluator online (heuristico) | `conversation/evaluator.py` do epic 005 ja retorna `{score: 0-1, verdict: APPROVE\|RETRY\|ESCALATE}`. Novo: apos evaluate step do pipeline, `asyncio.create_task(persist_eval_score(...))` grava em `eval_scores` com `evaluator='heuristic_v1'`, `metric='heuristic_composite'`, `details={verdict, components}`. Fire-and-forget (ADR-028). | ADR-028 |
| 14 | DeepEval cron | **Novo periodic task** `deepeval_batch_cron` cadencia diaria 02:00 UTC (antes do autonomous resolution). Amostra ate 200 msgs/tenant/dia estratificada por intent. Processamento em chunks de 10 (DeepEval async). Budget: falha de 1 metric nao aborta as outras. | novo |
| 15 | Eval coverage metric | Coluna derivada no admin: `coverage_% = COUNT(DISTINCT eval_scores.message_id WHERE created_at > 7d) / COUNT(DISTINCT messages WHERE created_at > 7d)`. Baseline esperado pos-rollout: online 100% (heuristico em toda msg), offline ~5-10% (sampled). | novo |
| 16 | Alerting thresholds | **Defaults conservadores** configuraveis per-tenant em `tenants.yaml evals.alerts`: relevance <0.6 por 1h -> log; toxicity >5% 24h -> log + email; autonomous_resolution <30% 7d -> dashboard badge amarelo. Nenhum alerta critico em v1 (calibra antes de flip para critical). | Q4-A |
| 17 | Rollout per-tenant | **Ariel `off -> shadow (7d) -> on`**; ResenhAI mesmo trajeto 7d depois. Shadow valida: (a) `eval_scores` povoa sem erro; (b) thresholds fazem sentido com trafego real; (c) cron jobs completam no budget de tempo. | Q6-A; herdado epic 010 |
| 18 | Sample rate online | `evals.online_sample_rate: 1.0` em shadow (100%, heuristico e barato), mantido em `1.0` no `on` para heuristico. Parametro existe para o dia em que LLM-as-judge online entrar (011.1) — servira para amostrar 10% via esse mesmo dial. | Q6-A |
| 19 | Observabilidade | Novas metricas Prometheus via structlog facade (padrao epic 010): `eval_scores_persisted_total{tenant, evaluator, metric}`, `eval_score_below_threshold_total{tenant, metric}`, `eval_batch_duration_seconds{job}`, `autonomous_resolution_ratio{tenant}`. Logs structlog canonicos: `tenant_id, conversation_id, message_id, evaluator, metric, score`. | pattern epic 010 |
| 20 | OTel baggage | `trace_id` ja propaga desde epic 002. Novo span `eval.score.persist` atachado ao trace original. DeepEval batch cria span root `eval.batch.deepeval` com child por metric. | pattern epic 002 |
| 21 | Golden dataset privacy | Traces estrelados nao anonimizam payload antes de popular Promptfoo YAML — operador admin e responsavel por redagir PII se necessario (tool manual). Em v1 aceito o trade-off; LGPD SAR ja cascade-deleta `golden_traces` pelo `trace_id` via nova FK adicionada na SAR query. | ADR-018 extended |
| 22 | Grupo vs 1:1 | Heuristica de autonomous resolution aplica igualmente a grupo e 1:1. Refinar per-segment (ex: grupo tem "silencio de 24h" diferente) adiado. DeepEval roda em msgs de ambos os tipos. | simplicity-first |

## Resolved Gray Areas

Decisoes tomadas durante este epic-context (2026-04-24):

1. **Escopo offline vs online (Q1)** — Offline completo (DeepEval batch cron) + online **heuristico apenas** (reusa `evaluator.py` do epic 005, zero LLM extra). LLM-as-judge online adiado para 011.1 apos calibracao.
2. **Golden dataset cold-start (Q3)** — Nao temos dados agora. Solucao: bootstrap com reference-less metrics (DeepEval sem golden) + crescimento incremental via admin curation ("star" traces).
3. **Definicao de resolucao autonoma (Q2)** — Heuristica conservadora A (sem mute, sem tokens de escalacao, 24h silencio). Formalizada em ADR-040; revisitar em 011.1 com LLM-as-judge se trafego justificar custo.
4. **Acao em score baixo (Q4)** — v1: log + counter + alerta. Auto-handoff via 010 e retry automatico adiados — precisa 2-4 sem de dados de shadow para calibrar threshold.
5. **Single pane of glass (Q5)** — Admin Performance AI. Phoenix continua util para drill-down individual (`trace_id` deeplink) mas nao duplica visualizacoes agregadas.
6. **Feature flag shape (Q6)** — `evals.mode: off\|shadow\|on` + `evals.offline_enabled` + `evals.online_sample_rate`. Herda invariantes do epic 010 (config_poller <=60s, per-tenant).
7. **Faithfulness vs outras metricas** — Faithfulness tradicional exige grounding source (RAG context); como epic 012 (RAG) ainda nao aconteceu, metric fica out-of-scope em v1. AnswerRelevancy substitui no set reference-less (compara pergunta vs resposta sem external truth).
8. **Groupo chat em evals** — Mesmo tratamento 1:1. Adversarial: grupo tem mensagens nao-direcionadas (`@mention` ausente -> bot nao responde, mas conversa existe). Essas nao entram em `eval_scores` porque `evaluator.py` so roda quando bot responde (`messages.direction='outbound'`).

## Applicable Constraints

**Do blueprint** ([engineering/blueprint.md](../../engineering/blueprint.md)):

- Python 3.12, FastAPI, asyncpg, redis[hiredis], structlog, opentelemetry — **zero libs novas alem de `deepeval` (Python) e `promptfoo` (Node dev)**.
- NFR Q1 (p95 <3s) — online heuristico nao pode adicionar latencia. Fire-and-forget (ADR-028) obrigatorio.
- NFR Q10 (faithfulness >0.8) — metrica efetiva e AnswerRelevancy em v1 (faithfulness real depende de epic 012 RAG).
- NFR Q11 (guardrail latency <260ms) — nao impactado; evals sao downstream do pipeline.
- NFR Q4 (safety bypass <1%) — Toxicity + Bias metrics (DeepEval) viram signal de bypass detectado tardio.
- ADR-027 admin-tables-no-rls — `public.golden_traces` tabela nova admin-only.
- ADR-028 fire-and-forget — persistencia de `eval_scores` NUNCA bloqueia pipeline ou webhook response.
- ADR-011 RLS — `eval_scores` mantem tenant_id + policy tenant_isolation (schema ja tem isso).
- ADR-018 LGPD — SAR e retention aplicam a `eval_scores` (tem `tenant_id`, herda cascade). `golden_traces` admin-only sem tenant_id direto, mas FK trace_id -> traces -> tenant indiretamente; SAR query explicita adicionada.
- ADR-024 schema isolation — `eval_scores` continua em schema `prosauai`; `golden_traces` em `public` (admin carve-out).

**Do epic 008** ([epics/008-admin-evolution/](../008-admin-evolution/)):

- Admin Performance AI tab usa TanStack Query v5 + Recharts + shadcn/ui. Cards novos seguem o mesmo pattern.
- Pool_admin BYPASSRLS para queries agregadas cross-tenant (`?tenant=all`).
- OpenAPI 3.1 em `contracts/openapi.yaml` — novos endpoints geram tipos via `pnpm gen:api`.

**Do epic 010** ([epics/010-handoff-engine-inbox/](../010-handoff-engine-inbox/)):

- Feature flag shape `tenants.yaml` com `handoff.mode` valida; replica `evals.mode`.
- Advisory lock pattern para cron singleton (`pg_try_advisory_lock`).
- Scheduler no FastAPI lifespan com `asyncio.wait(timeout=5s)` no shutdown graceful.
- Structlog facade para metricas Prometheus (sem `prometheus_client` como dep nova).

## Suggested Approach

Dividir em **3 PRs sequenciais mergeaveis em develop**, cada um reversivel via `evals.mode: off`:

### PR-A (semana 1) — Schema + heuristico online + auto_resolved cron

1. Migration: `ALTER TABLE conversations ADD COLUMN auto_resolved BOOLEAN NULL` (NULL=nao calculado ainda).
2. Migration: `CREATE TABLE public.golden_traces (...)` (admin-only, herda ADR-027).
3. `prosauai/evals/__init__.py` novo modulo: `persist_score(tenant_id, message_id, conversation_id, evaluator, metric, score, details)` usando pool asyncpg + fire-and-forget wrapper.
4. Patch em `conversation/pipeline.py` step `evaluate`: apos `evaluator.evaluate(...)`, `asyncio.create_task(evals.persist_score(...))`.
5. Novo `evals/autonomous_resolution.py` + scheduler task `autonomous_resolution_cron` (lifespan).
6. `tenants.yaml` schema: adicionar bloco `evals: {mode, offline_enabled, online_sample_rate, alerts}`. Config poller passa a ler.
7. Testes: unit (persist_score idempotency, auto_resolved heuristic cases), integration (pipeline -> eval_scores end-to-end).
8. Ariel em `shadow` no final da semana — valida fluxo sem impacto.

### PR-B (semana 2) — DeepEval batch cron + Promptfoo smoke

1. Dep: `deepeval>=3.0` em `pyproject.toml`.
2. `evals/deepeval_batch.py`: sampler (estratificado por intent, 200 msgs/tenant/dia), runner (4 metrics async), persistencia.
3. Scheduler task `deepeval_batch_cron` (02:00 UTC).
4. Promptfoo: `prosauai/evals/promptfoo/smoke.yaml` com 5 casos hand-written + generator Python para YAML a partir de `golden_traces`.
5. GitHub Action: `promptfoo eval` como gate blocking em PRs que tocam `agents/`, `prompts/`, `safety/`.
6. API: `POST /admin/traces/{trace_id}/golden` (pool_admin, insere em `golden_traces`).
7. Testes: DeepEval mock (respx), Promptfoo YAML generation, API auth.
8. Ariel shadow -> `on` se coverage% >= 80% e sem erros.

### PR-C (semana 3) — Admin UI + rollout ResenhAI

1. Performance AI tab: 4 cards novos (TanStack Query + Recharts), usando novos endpoints agregadores do admin (`GET /admin/metrics/evals?tenant=...`).
2. Trace Explorer: coluna "Golden" com botao star (positive/negative/clear), toast de confirmacao, invalida query `golden_traces`.
3. Tenants tab: linha `evals.mode` badge + toggle (usa `PATCH /admin/tenants/{id}/evals`).
4. Tipos gerados: `pnpm gen:api` -> commit.
5. Playwright smoke: navega Performance AI, valida 4 cards renderizando; estrela um trace; verifica aparece no golden_traces.
6. ResenhAI rollout shadow -> on (7 dias apos Ariel estar on).
7. Docs: runbook de calibracao de thresholds; README do golden curation para admin.

### Invariantes obrigatorios

- **Fire-and-forget** em TODA persistencia de eval score — pipeline nunca espera DB write.
- **Sample rate respeitado** em DeepEval batch (`online_sample_rate` ignorado no cron, que tem amostragem propria 200/dia).
- **Shadow mode honrado** — `evals.mode=shadow` grava em `eval_scores` mas alerts sao no-op.
- **Golden traces nunca mutaveis** — curadoria e append-only; correcao via novo insert com verdict oposto.
- **Feature flag off == zero side effect** — nenhum INSERT em `eval_scores`, nenhum cron job, nenhum card renderizado (skeleton "evals desabilitados").

---

> **Proximo passo:** `/speckit.specify prosauai 011` — especificacao funcional detalhada a partir deste pitch.
