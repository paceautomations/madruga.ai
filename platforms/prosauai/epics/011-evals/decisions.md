---
epic: 011-evals
created: 2026-04-24
updated: 2026-04-24
---
# Registro de Decisoes — Epic 011

1. `[2026-04-24 epic-context]` Escopo v1: Offline DeepEval batch + Online heuristico (reusa evaluator.py do epic 005). LLM-as-judge online adiado para 011.1. (ref: Q1-B epic-context 2026-04-24)
2. `[2026-04-24 epic-context]` Cold-start sem dataset: bootstrap com reference-less metrics (AnswerRelevancy, Toxicity, Bias, Coherence). Faithfulness adiado ate epic 012 RAG. (ref: ADR-039 novo)
3. `[2026-04-24 epic-context]` Golden dataset cresce incremental via admin curation — admin "estrela" traces na Trace Explorer; Promptfoo suite comeca com 3-5 smoke cases hand-written. (ref: ADR-039 novo)
4. `[2026-04-24 epic-context]` Persistencia online: todo score grava em eval_scores com coluna `evaluator` discriminante (heuristic_v1, deepeval, human). Schema ja existe (epic 005). (ref: domain-model.md:678-694)
5. `[2026-04-24 epic-context]` Resolucao autonoma: heuristica conservadora A (sem mute, sem tokens de escalacao regex, 24h silencio). Cron noturno popula conversations.auto_resolved BOOLEAN. LLM-as-judge v2 em 011.1. (ref: ADR-040 novo)
6. `[2026-04-24 epic-context]` Acao em score baixo: v1 apenas log + Prometheus counter + alerta 24h. Zero acao automatica na conversa. Auto-handoff via 010 adiado para 011.1 apos shadow data. (ref: Q4-A)
7. `[2026-04-24 epic-context]` Dashboards canonicos em Admin Performance AI tab (4 cards novos). Phoenix permanece para drill-down individual via trace_id, sem duplicar visualizacoes agregadas. (ref: Q5-B)
8. `[2026-04-24 epic-context]` Feature flag per-tenant `evals.mode: off|shadow|on` + `offline_enabled` + `online_sample_rate` em tenants.yaml, config_poller <=60s. Herda pattern epic 010. (ref: Q6-A)
9. `[2026-04-24 epic-context]` DeepEval metric set v1: AnswerRelevancy, Toxicity, Bias, Coherence. Cron noturno, 200 msgs/tenant/dia amostra estratificada. (ref: ADR-008 confirmed + ADR-039)
10. `[2026-04-24 epic-context]` Promptfoo CI suite: 3-5 smoke cases iniciais + gerador automatico de YAML a partir de golden_traces estrelados pelo admin. Gate blocking em PRs que tocam agents/prompts/safety. (ref: ADR-008 confirmed)
11. `[2026-04-24 epic-context]` Golden curation: nova tabela public.golden_traces (admin-only, ADR-027 carve-out) — trace_id, verdict (positive|negative), notes, created_by_user_id. API POST /admin/traces/{trace_id}/golden. (ref: ADR-027 extended)
12. `[2026-04-24 epic-context]` Autonomous resolution cron: periodic task no FastAPI lifespan com pg_try_advisory_lock singleton, cadencia diaria 03:00 UTC. (ref: pattern epic 010)
13. `[2026-04-24 epic-context]` Evaluator online heuristico: apos evaluate step do pipeline, asyncio.create_task(persist_eval_score) grava em eval_scores com evaluator='heuristic_v1'. Fire-and-forget. (ref: ADR-028)
14. `[2026-04-24 epic-context]` DeepEval cron cadencia diaria 02:00 UTC (antes do autonomous resolution). Chunks de 10, falha de 1 metric nao aborta as outras. (ref: novo)
15. `[2026-04-24 epic-context]` Eval coverage metric: coverage_% = evaluated_messages / total_messages last 7d. Baseline pos-rollout: online 100%, offline 5-10%. (ref: novo)
16. `[2026-04-24 epic-context]` Alerting thresholds conservadores per-tenant em tenants.yaml evals.alerts: relevance <0.6 1h log; toxicity >5% 24h log+email; autonomous_resolution <30% 7d badge. Sem alerta critico em v1. (ref: Q4-A)
17. `[2026-04-24 epic-context]` Rollout: Ariel off -> shadow (7d) -> on; ResenhAI mesmo trajeto 7d depois. (ref: Q6-A; herdado epic 010)
18. `[2026-04-24 epic-context]` Sample rate online em shadow e on: 1.0 (heuristico barato). Parametro existe para o dia em que LLM-as-judge online entrar (011.1) — amostrar 10% via esse dial. (ref: Q6-A)
19. `[2026-04-24 epic-context]` Observabilidade: novas metricas Prometheus via structlog facade — eval_scores_persisted_total, eval_score_below_threshold_total, eval_batch_duration_seconds, autonomous_resolution_ratio. (ref: pattern epic 010)
20. `[2026-04-24 epic-context]` OTel baggage: trace_id propaga desde epic 002. Novo span eval.score.persist atachado ao trace original; DeepEval batch cria eval.batch.deepeval com child por metric. (ref: pattern epic 002)
21. `[2026-04-24 epic-context]` Golden traces privacy: operador admin responsavel por redagir PII antes de inserir trace em Promptfoo YAML. LGPD SAR cascade-deleta golden_traces via FK trace_id -> traces -> tenant. (ref: ADR-018 extended)
22. `[2026-04-24 epic-context]` Grupo vs 1:1: heuristica de autonomous resolution aplica igualmente a ambos. Refinar per-segment adiado. DeepEval roda em msgs outbound de ambos. (ref: simplicity-first)
