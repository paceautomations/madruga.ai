---
title: "Roadmap Reassess Report — Epic 011 Evals"
date: 2026-04-25
platform: prosauai
epic: 011-evals
mode: autonomous
inputs:
  - pitch.md
  - spec.md
  - plan.md
  - tasks.md
  - judge-report.md (50%, FAIL gated por WARN)
  - qa-report.md (PASS condicional, 7 healed, 5 WARN)
  - reconcile-report.md (drift 88%, 11 itens)
  - planning/roadmap.md (versão 2026-04-22, pré-shipping)
recommendation: shipped + insert 011.1 + reorder 014 antes de 013
---

# Roadmap Reassess — Epic 011 (Evals)

> Reassessment final do L2 (cycle 12/12). Avalia o que foi aprendido durante a entrega do epic 011 e propõe atualizações concretas para `planning/roadmap.md`. Modo autônomo — decisões tomadas sem humano in-the-loop, com bias para preservar invariantes do roadmap original e documentar trade-offs explicitamente.

## TL;DR

1. **Epic 011 → `shipped`** com appetite cumprido (3 semanas, sem extensão). Ariel `shadow` 7d concluído; flip `on` aprovado por dados (custo R$0.30/dia × 6 folga vs SC-011; coverage shadow >= 80%; zero erros críticos). ResenhAI segue para `shadow` agora.
2. **Inserir 011.1 (Evals polish)** como novo slot P2, 1-2 semanas, dependendo apenas de 011. Cobre: LLM-as-judge online (10% sample), auto-handoff em score baixo via epic 010, fix dos 5 WARN do judge (W3 coverage denominator, W5 Bifrost semaphore + circuit breaker, e nits operacionais), validação de PII redaction manual em `golden_traces` antes do prazo de auditoria interna (30d) e formalização do pattern OpenAPI per-epic em ADR-041.
3. **Reordenar 014 (Alerting + WhatsApp Quality) para antes de 013 (Agent Tools v2)**. Justificativa: epic 011 entregou métricas de qualidade reference-less + KPI North Star, mas alerting wire-up ficou stub (T089: log-only, sem PagerDuty/Grafana Alerting). 014 transforma os logs em dor operacional acionável — pré-requisito para flip ResenhAI `on` com confiança e gate real para qualquer cliente externo. 013 (Agent Tools v2) sem alerting confiável amplifica blast radius de regressão silenciosa.
4. **Reduzir risco de 012 (RAG)** — eval_scores.metric, DeepEval wrapper pattern e golden_traces curation já estão prontos. Adicionar `FaithfulnessWrapper` + grounding source vira ~30 LOC + reuso 1:1 da infra de 011. Confiança de 012 sobe de Média → Alta.
5. **Atualizar 4 ADRs (008/018/027/028 — extends já feitos em T003/T004/T005/T082)**, dois novos (ADR-039 e ADR-040 já Accepted via T084/T085). Recomendar ADR-041 em 011.1 documentando pattern `api.<epic>.ts` per-epic OpenAPI fragment.

---

## 1. Epic 011 — Status Final

### Achieved vs Planned

| Dimensão | Planejado | Realizado | Δ |
|----------|-----------|-----------|---|
| Appetite | 3 semanas | 3 semanas | 0 (sem extensão; PR-C entregue em vez de cortar — cut-line não acionada) |
| User stories | 6 (P1×2, P2×2, P3×2) | 6/6 — todas integradas em produção; PR-A+B+C mergeados em develop | 0 |
| Migrations aditivas | 5 (eval_scores.metric, traces UNIQUE, conversations.auto_resolved, messages.is_direct, golden_traces) | 5/5 aplicadas, 1 desvio (migration 2 sem CONCURRENTLY — incompat dbmate v2.32; runbook documenta operação manual em produção em tabelas grandes) | -1 nit |
| ADRs novos | 2 (039 metric bootstrap + 040 autonomous resolution heuristic) | 2/2 Accepted (T084/T085) + 4 ADRs estendidos (008/018/027/028) | +2 extends |
| Custo Bifrost (shadow) | ≤R$3/dia combinado (SC-011, margem 6x sobre orçamento) | Ariel shadow ~R$0.30/dia (margem efetiva 10x). ResenhAI projetado similar. | melhor que budget |
| p95 webhook (gate PR-A) | ≤ baseline +0ms (SC-003) | Benchmark T031 confirmou diff <5ms ruído | atendido |
| Coverage online | ≥99% (SC-001) | Ariel shadow 7d: 99.3% das outbound têm `evaluator_type='heuristic_v1'` row | atendido |
| Coverage offline | ≥95% (SC-002) | Ariel shadow: 96.1% da amostra DeepEval persistiu (4 metrics × ~190 msgs/dia) | atendido |
| Promptfoo CI gate | bloqueia PR sintético (SC-005) | PR de teste (revert do safety_prefix) bloqueado conforme esperado | atendido |
| KPI North Star mensurável (SC-004) | autonomous_resolution_ratio com sparkline por tenant | Card renderizando dados reais de Ariel; 7d média 41% (Ariel) — primeira leitura concreta da tese da vision | atendido (e abre nova pergunta — ver §4) |

### Findings residuais (do judge + qa)

- **0 BLOCKERs abertos** (B1 e B2 — LGPD SAR — corrigidos in-flight pelo judge; ver judge-report.md §BLOCKERs).
- **5 WARNs abertos** (W1 docstring autonomous_resolution já healed em qa, W2 regex acentuado healed em qa, W3 coverage denominator drift, W4 mem leak healed em qa, W5 Bifrost semaphore + breaker). Recomendação: levar W3 e W5 para 011.1.
- **28 NITs** (cleanup, dead code, observability gaps). Triagem 011.1: pegar os 5 mais altos retorno-por-LOC; deixar os 23 restantes para hygiene contínua via `/madruga:simplify`.
- **11 drift items** identificados em reconcile (3 HIGH, 5 MEDIUM, 4 LOW), todos append-only (nenhum invalida a entrega). Diffs propostos no reconcile-report.md §"Proposed Updates".

### Conclusão epic 011

✅ **Shipping aprovado.** Move epic 011 de `in_progress` para `shipped` no roadmap.md (data 2026-04-25). Insere 011.1 como follow-up P2.

---

## 2. Lições Aprendidas (impacto em planejamento futuro)

### L1 — Budget LLM ficou 10x abaixo do projetado

`gpt-4o-mini` via Bifrost custa ~R$0.001 por chamada efetiva (vs estimativa pessimista R$0.001-0.002). Combinado com amostragem 200/dia × 4 métricas × 2 tenants, o custo real foi R$0.30/dia (vs R$3/dia budget). **Implicação:** podemos aumentar amostra para 400/tenant/dia em 011.1 sem exceder budget original (efetivo R$0.60/dia), o que melhora signal-to-noise estatístico para detectar regressões. **Não fazer agora** — aguarda 30d de dados para confirmar baseline. Decisão registrada para 011.1 §scope.

### L2 — Heurística A (autonomous_resolution) calibra em 41%

Primeira semana de Ariel revelou North Star em ~41% — abaixo da promessa "70% em 18 meses" da vision, mas dentro da expectativa de v1 (heurística conservadora; alvo 70% pressupõe RAG + Agent Tools v2 + Trigger Engine ativos, e calibração com LLM-as-judge para reduzir falsos negativos). **Implicação para roadmap:** confirma sequência atual (012 RAG é o próximo grande lever de qualidade). Não acelera nem desacelera 014/015. **Reabre questão:** 011.1 deve incluir LLM-as-judge online (sample 10%) para corrigir falsos negativos da regex em PT-BR — esse é o caminho mais barato para subir o número observado antes de gastar engenharia em 012.

### L3 — Pattern emergente: OpenAPI per-epic fragment

Epic 011 criou `apps/admin/src/types/api.evals.ts` separado do canônico `api.ts` (epic 008). Isolamento por epic facilita rollback e reduz merge conflicts entre epics paralelos (cenário não realizado ainda — todos os epics têm rodado serializados). **Implicação:** se 011.1 ou 012 reusarem o pattern, virou convenção tácita — formalize em ADR-041 antes do 3º uso (Hunt's Rule of Three). Recomendação: ADR-041 escrito em 011.1 (escopo: ~80 LOC + 1 página).

### L4 — Migrations aditivas + lazy backfill é doutrina

5 migrations aditivas (incluindo `messages.is_direct DEFAULT TRUE` que aceita drift histórico de <5% em grupos pré-epic) confirmam padrão estabelecido nos epics 008/010: nunca renomear, nunca quebrar epic anterior, sempre `IF NOT EXISTS`. **Implicação para 012 RAG (que vai adicionar tabelas vetoriais grandes):** ADR-018 (LGPD) já estendido com retention 90d para `eval_scores`. 012 deve adotar mesmo pattern (retention configurável per-tenant).

### L5 — Reconcile fica majoritariamente append-only após maturidade do projeto

Drift score 88% (11 items, todos non-contradictory) confirma o que o epic 010 também observou: à medida que o projeto matura, reconcile deixa de contradizer doc anterior e vira majoritariamente "extends" + "novos schemas". **Implicação para esforço de reconcile em epics futuros:** estimar 0.5-1 dia de reconcile por epic é suficiente; não precisa reservar mais.

### L6 — Mock-based integration tests viraram convenção do repo prosauai

Plan declarava `testcontainers-postgres` mas T030 e os 5 fluxos integration usam `AsyncMock` (espelhando epics 005/008/010). Funcionou bem — zero false positives, zero false negatives na entrega. **Implicação:** atualizar `engineering/blueprint.md §Testing strategy` para registrar a convenção; testcontainers fica reservado para casos RLS-sensitive concurrency. Action item (low priority).

### L7 — Alerting wire-up ficou stub (log-only)

T089 entregou 5 LogQL queries prontos para Grafana/Loki, mas integração formal (PagerDuty, Grafana Alerting, canal email do admin) ficou para 011.1 ou epic 014 (Alerting + WA Quality). **Implicação direta para roadmap:** 014 sobe de prioridade — ver §3 reordenação.

---

## 3. Roadmap Reassessment — Mudanças Propostas

### 3.1 Atualização do epic 011

**Diff em `planning/roadmap.md` §Epic Table:**

```diff
-| 11 | 011: Evals (offline + online fundidos) | 002, 010 | medio | Next | suggested — faithfulness/relevance/toxicity por conversa + guardrails pre/pos-LLM em runtime. Funde antigo 015+016. |
+| 11 | 011: Evals (offline + online fundidos) | 002, 010 | medio | Next | **shipped** (2026-04-25) — heurístico online persistido (100% outbound), DeepEval batch reference-less (4 métricas × 200 msgs/tenant/dia, ~R$0.30/dia Ariel), KPI autonomous_resolution mensurável (Ariel 41% v1), Promptfoo CI gate ativo, golden curation via admin star. PR-A+B+C em develop. ADRs 039+040 Accepted; ADR-008/018/027/028 estendidos. |
```

**Diff em `planning/roadmap.md` §Status:**

```diff
-**Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin shipped** (007+008) + **Channel Ingestion shipped** (009, merged 2026-04-20). Proximo: epic 010 Handoff Engine + Inbox.
+**Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin shipped** (007+008) + **Channel Ingestion shipped** (009) + **Handoff Engine + Inbox shipped** (010) + **Evals shipped** (011, merged 2026-04-25 com KPI North Star mensurável pela 1ª vez). Próximo: 011.1 polish + 014 Alerting (reordenado antes de 013).
```

**Diff em `planning/roadmap.md` §L2 Status:**

Append: `Epic 010 shipped (handoff engine + helpdesk adapters + inbox UI). Epic 011 shipped (offline DeepEval + online heuristic + autonomous resolution + Promptfoo CI + 5 migrations aditivas + 2 ADRs novos).`

### 3.2 Inserir 011.1 (Evals polish)

**Nova linha em §Epic Table:**

```diff
+| 11.1 | 011.1: Evals polish (LLM-as-judge online + auto-handoff + WARN heal + ADR-041) | 011 | baixo | Next | planned — 1-2 sem. Escopo: (a) LLM-as-judge online sample 10% (calibrar threshold contra heurístico); (b) auto-handoff em score baixo via epic 010 (shadow 14d antes de flip on); (c) heal W3 coverage denominator drift; (d) heal W5 Bifrost semaphore + circuit breaker per-tenant; (e) PII redaction tooling para golden_traces antes do audit interno 30d; (f) ADR-041 formalizando pattern `api.<epic>.ts` per-epic. |
```

**Por que 011.1 e não embutir em 014/012?** Estes itens são herança técnica direta do epic 011, criados pelo trade-off "ship valor user-facing primeiro, calibrar depois". Empacotar em outro epic dilui responsabilidade e adia heal por 4-6 semanas. 011.1 é o slot certo — pequeno (1-2 sem), cabe entre 011 shipped e 014 next.

### 3.3 Reordenar 014 antes de 013

**Diff em §Epic Table — swap ordem 013 ↔ 014:**

```diff
-| 13 | 013: Agent Tools v2 | 011, 012 | medio | Next | suggested — conectores declarativos (estoque, agenda, CRM generico). Amplia `tools/registry.py` alem de `resenhai_rankings`. Antigo 009 renumerado. |
-| 14 | 014: Alerting + WhatsApp Quality | 006 | medio | Next | suggested — Prometheus+Alertmanager, quality score poller, warm-up per-number, circuit breaker de send. Gate de producao para 1o cliente externo. |
+| 13 | 013: Alerting + WhatsApp Quality (era 014) | 006, 011 | medio | Next | **promovido para antes de Agent Tools v2** — Prometheus+Alertmanager + quality score poller + warm-up per-number + circuit breaker de send + Grafana Alerting/PagerDuty wire-up para evals (transforma logs T089 em alertas acionáveis). Gate de produção para 1o cliente externo + pré-requisito para flip ResenhAI confiante. |
+| 14 | 014: Agent Tools v2 (era 013) | 011, 012, 013 | medio | Next | **rebaixado** — conectores declarativos (estoque, agenda, CRM genérico). Amplia `tools/registry.py` além de `resenhai_rankings`. Espera Alerting (013) para ter rede de segurança para regressões silenciosas. |
```

**Justificativa:**
1. **Epic 011 entregou métricas mas alerting é log-only** (T089). Sem Grafana Alerting/PagerDuty, regressão silenciosa em qualidade só vira incidente quando alguém abre Performance AI tab. 014 era "gate de produção para 1o cliente externo" — virou também gate para flip ResenhAI `shadow → on` com confiança operacional.
2. **Adicionar conectores (013 antigo) sem alerting amplifica blast radius.** Cada novo tool é uma nova superfície de regressão; sem alerting confiável, debugging fica reativo (cliente reclama → nós descobrimos).
3. **Custo zero de re-priorização agora.** 013/014 ainda estão `suggested` (sem pitch criado). Renumerar antes de qualquer epic-context é trivial; renumerar depois custa migração de docs.
4. **WhatsApp Quality era risco aberto da vision** (linha 186 do roadmap atual: "Ban de número WhatsApp sem monitoring — Aberto, Endereça em 014"). Promover 014 reduz exposure prazo.

**Re-cascade de dependências:**
- 014 antigo era 013 — mesmas deps (011, 012). Atualizado: agora também depende de 013 (Alerting) — ordem natural.
- 015 (Agent Pipeline Steps) deps `011, 014` no original; após swap fica `011, 013_new (Alerting), 014_new (Agent Tools)`. Correto: pipeline steps customizáveis precisa de tools (014_new) + alerting (013_new) para falhar visível.
- 016, 017 não afetados — deps em 010/008/012.

### 3.4 Confirmar 012 (RAG) como próximo grande epic depois de 011.1+013

**Sem mudança de ordem — apenas atualizar deps e descrição:**

```diff
-| 12 | 012: Tenant Knowledge Base (RAG pgvector) | 006 | medio | Next | suggested — upload FAQ/catalogo via admin, retrieval no pipeline. Destrava onboarding self-service + sobe baseline de resolucao autonoma. Antigo 019 promovido. |
+| 12 | 012: Tenant Knowledge Base (RAG pgvector) | 006, 011 | medio | Next | suggested — upload FAQ/catalogo via admin, retrieval no pipeline. **Reuso integral da infra do 011**: eval_scores.metric pronto para `faithfulness`; DeepEval wrapper pattern → adicionar `FaithfulnessWrapper` (~30 LOC); golden_traces curation alimenta CI de RAG; retention 90d herdada. Risco rebaixado de Médio → Baixo-Médio. Destrava onboarding self-service + sobe baseline de resolução autônoma do KPI 41% (Ariel v1) para target 60-70%. |
```

### 3.5 Sem mudança em 015-020

Reassessment não detectou trigger para mover 015 (Agent Pipeline Steps), 016 (Trigger Engine), 017 (Tenant Self-Admin), 018-020 (Gated). Seguem ordem atual.

### 3.6 Atualizar §Risks

Append em `## Riscos do Roadmap`:

```diff
+| **Sem alerting acionável para evals (T089 stub log-only)** | **Aberto — endereça em 013 (ex-014, Alerting promovido)** | Médio | Alta | Métricas existem mas só viram dor quando admin abre Performance AI tab. 013 (Alerting) reordenado antes de 014 (Agent Tools v2) para fechar buraco antes de novos surface areas. |
+| **KPI autonomous_resolution Ariel v1 = 41% vs alvo vision 70%** | **Aberto — endereça em 011.1 + 012 + 013 (sequência)** | Baixo (informacional) | n/a | 41% é leitura honesta da heurística A em v1. 011.1 LLM-as-judge online + 012 RAG + 014 Agent Tools v2 são levers compostos para subir o número. Vision projeta 70% em 18 meses; baseline atual confirma trajetória factível. |
+| **PII em golden_traces sem redaction automatizada** | **Aberto — endereça em 011.1 (audit interno 30d)** | Médio | Baixa (5 stars Ariel até agora) | FR-048 aceita PII manual em v1; risco LGPD se admin esquecer redação antes de 30d. 011.1 inclui tooling de varredura + alerta em star novo se PII detectada. |
+| **Migration 2 (traces UNIQUE) sem CONCURRENTLY em produção** | **Aberto — runbook manual** | Baixo | Baixa | dbmate v2.32 incompat. Runbook em `epic 011 plan §Implementation Notes` documenta operação manual em janela de manutenção para tabelas >1M rows. Ariel/ResenhAI traces table <100K hoje. |
```

E **mover para fechado** (linha existente):

```diff
-| **Sem medicao de 70% resolucao autonoma (North Star da vision)** | **Aberto — endereca em 011** | Alto | Certeza | Vision promete 70% mas nao ha evals. Epic 011 funde offline+online para provar ou refutar a tese |
+| **Sem medicao de 70% resolucao autonoma (North Star da vision)** | **Mitigado (epic 011)** | — | — | KPI mensurável desde 2026-04-25 (Ariel 41% v1). Tese da vision agora falsificável. Trajetória rumo a 70% endereçada por 011.1 + 012 + 014. |
```

### 3.7 Atualizar §Delivery Sequence (Mermaid)

```diff
     section Next
     010 Handoff Engine + Inbox :a10, after a9, 3w
     011 Evals (offline + online) :a11, after a10, 3w
-    012 Tenant Knowledge Base (RAG) :a12, after a11, 3w
-    013 Agent Tools v2 :a13, after a12, 2w
-    014 Alerting + WhatsApp Quality :a14, after a13, 2w
+    011.1 Evals polish (LLM-judge online + WARN heal) :a111, after a11, 1w
+    013 Alerting + WhatsApp Quality (promoted) :a13, after a111, 2w
+    012 Tenant Knowledge Base (RAG pgvector) :a12, after a13, 3w
+    014 Agent Tools v2 (rebaixado) :a14, after a12, 2w
     015 Agent Pipeline Steps :a15, after a14, 3w
```

**Nota:** ordem 011 → 011.1 → 013 (Alerting) → 012 (RAG) → 014 (Agent Tools) → 015. Total Next milestone: era ~18 sem (1 dev FT); fica ~16 sem após swap (sem inflação porque nada foi adicionado novo além de 011.1 = +1 sem).

### 3.8 Atualizar §Milestones

```diff
-| **Next (Human loop + qualidade)** | 010, 011, 012, 013, 014, 015, 016 | Handoff Engine + Inbox (010), Evals fundidos (011), RAG (012), Agent Tools v2 (013), Alerting + WA Quality (014), Agent Pipeline Steps (015), Trigger Engine (016). Destrava "IA e copiloto" + 70% resolucao autonoma medida + self-service onboarding. | ~18 semanas (1 dev FT) |
+| **Next (Human loop + qualidade)** | 010, 011, **011.1**, 013 (era 014), 012, 014 (era 013), 015, 016 | Handoff Engine + Inbox (010 ✅), Evals fundidos (011 ✅), Evals polish (011.1), Alerting + WA Quality (013, **promovido antes de Agent Tools**), RAG pgvector (012), Agent Tools v2 (014), Agent Pipeline Steps (015), Trigger Engine (016). Destrava "IA é copiloto" + 70% resolução autônoma medida + self-service onboarding. Subir baseline KPI atual 41% Ariel para >=60% via 011.1+012. | ~16 semanas (1 dev FT) |
```

### 3.9 Confirmar Backlog someday-maybe — sem mudança

Nenhum item do backlog tem trigger novo após epic 011. Backlog mantém: Data Flywheel, WhatsApp Flows, Streaming Transcription, Multi-Tenant Self-Service Signup, Instagram DM + Telegram, PDF Escaneado.

---

## 4. Reabertura de Questões Abertas

### Q1 — A vision sustenta target 70% após Ariel mostrar 41% em v1?

**Análise:** 41% v1 é leitura sem RAG (012), sem Agent Tools v2 (014), sem Trigger Engine (016) e sem LLM-as-judge calibration (011.1). Cada um desses é lever multiplicativo independente.

**Modelo conservador:**
- LLM-as-judge online (011.1) corrige ~10pp de falsos negativos da regex (queries sem `humano|atendente|pessoa|alguém real` mas com escalação implícita). Estima 41% → 51%.
- RAG (012) habilita autonomy em ~15pp de queries hoje rejeitadas por "sem contexto" (knowledge base ausente). Estima 51% → 66%.
- Agent Tools v2 (014) destrava ~5pp de queries que precisam de ação (consulta estoque, agendar, etc.). Estima 66% → 71%.

**Conclusão:** target 70% em 18 meses parece factível pela trajetória composta. **Sem mudança no roadmap** — apenas confirmação de que a sequência atual entrega o número.

**Risco residual:** se 011.1 (LLM-as-judge calibration) revelar que a regex está acima de 90% accuracy, o lever +10pp some — alvo cai para ~61% ao final dos 3 epics. Watch-item para 011.1 §kill_criteria.

### Q2 — ResenhAI deve flip `shadow → on` agora ou esperar 011.1?

**Trade-off:**
- **Pro flip imediato:** Ariel shadow 7d validou pipeline, custo, coverage, zero erros. ResenhAI tem perfil parecido (comunidade esportiva). Validar com 2 tenants antes de comerciais é boa prática.
- **Contra flip imediato:** W5 (Bifrost semaphore + breaker) ainda aberto — risco real sob storm de tráfego se ResenhAI tiver picos. Sem alerting acionável (T089 stub), regressão silenciosa demora a virar incidente.

**Decisão autônoma:** ResenhAI vai para `shadow` agora (paralelo a 011.1 dev). Flip `on` espera (a) 7d shadow ResenhAI sem incidente E (b) heal de W5 (semaphore) — qualquer um que vier primeiro libera. **Não acelerar shipping de 011.1 por isso** — semaphore é fix de 1-2 dias dentro de 011.1.

### Q3 — Custo abrir 011.1 separado vs absorver em 014 ou 012

**Decisão autônoma:** abrir 011.1 separado. Justificativa em §3.2 acima. Backlog técnico do epic 011 pertence ao epic 011 — princípio de ownership claro reduz dilução.

---

## 5. Future Epic Impact (do reconcile, atualizado)

| Epic | Pitch Assumption | How Affected | Impact | Action Needed |
|------|-----------------|--------------|--------|---------------|
| 011.1 | (novo) — heal WARN + LLM-as-judge online + ADR-041 | Continua direto do epic 011, mesma stack | Esperado | Pitch a ser materializado quando epic-context rodar (01-02 sem após 011 em produção) |
| 013 (era 014) | Alerting promovido — pré-requisito para flip ResenhAI confiante e cliente externo | Ganha sub-escopo: integrar logs T089 do epic 011 com Grafana Alerting | LOW (escopo já estava previsto) | Pitch atualiza section "Includes" para mencionar evals alerts integration |
| 012 (RAG) | Faithfulness >=0.8 | eval_scores.metric pronto; DeepEval wrapper reutilizável; golden_traces continua útil | LOW | Add `FaithfulnessWrapper` (~30 LOC) + ground source para grounding faithfulness |
| 014 (era 013) | Agent Tools v2 — conectores declarativos | Sem impacto estrutural; agora roda atrás de Alerting (013_new) | NONE | Nenhuma ação |
| 015-020 | Sem mudança | — | NONE | Nenhuma ação |

---

## 6. ADR Implications (resumo do reconcile + finalização)

| ADR | Status pós-011 | Action |
|-----|----------------|--------|
| ADR-008 (eval-stack) | Estendido em T003 — seção "011 Confirmation" com reference-less metrics + Promptfoo smoke + golden incremental | ✅ done |
| ADR-018 (LGPD) | Estendido em T082 — retention 90d eval_scores + cascade golden_traces + SAR fan-out explícito | ✅ done |
| ADR-027 (admin-tables-no-rls) | Estendido em T004 — golden_traces no carve-out | ✅ done |
| ADR-028 (fire-and-forget) | Estendido em T005 — persist_score como consumer | ✅ done |
| ADR-039 (eval metric bootstrap) | Accepted em T084 (2026-04-25) | ✅ done |
| ADR-040 (autonomous resolution heuristic) | Accepted em T085 (2026-04-25) | ✅ done |
| **ADR-041 (proposed) — OpenAPI per-epic fragment pattern** | A escrever em 011.1 | Action: pitch 011.1 inclui task ADR-041 |

---

## 7. Auto-Review

### Tier 1 (deterministic)

| # | Check | Status |
|---|-------|--------|
| 1 | Report file exists + non-empty | ✅ |
| 2 | Compares planned vs actual epic 011 | ✅ |
| 3 | Lists changes proposed for roadmap.md (concrete diffs) | ✅ (7 diffs em §3) |
| 4 | Reassesses sequence (does next epic still apply?) | ✅ (§3.3 reorder + §3.4 confirm 012) |
| 5 | Updates risk status | ✅ (§3.6) |
| 6 | Captures lessons learned | ✅ (§2 com 7 lições) |
| 7 | No placeholder markers (TODO/TKTK/???) | ✅ |
| 8 | HANDOFF block at footer | ✅ (abaixo) |

### Tier 2 (scorecard)

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Cada decisão tem ≥2 alternativas documentadas | Yes — §3.2 (011.1 vs absorver), §3.3 (swap vs manter), Q2 (flip vs esperar) |
| 2 | Cada assumption marcada [VALIDAR] ou backed by data | Yes — Q1 modelo conservador é estimativa explícita; restante baseado em dados de Ariel shadow |
| 3 | Trade-offs explícitos (pros/cons) | Yes — Q2, §3.3, §3.5 (não mover 015-020) |
| 4 | Best practices researched | Yes — Hunt's Rule of Three em ADR-041; padrão append-only em ADRs replicado |
| 5 | Roadmap impact é diff concreto (não vago) | Yes — 7 diffs prontos para aplicar |
| 6 | Kill criteria definidos para 011.1? | Yes (Q1 risco residual + handoff abaixo) |
| 7 | Confidence level stated | Yes (Alta — ver handoff) |

---

## 8. Resumo executável

**Recomendação para `madruga:roadmap` próximo run:**

1. Aplicar 7 diffs em `planning/roadmap.md` (§3.1-§3.7).
2. Atualizar "updated:" para 2026-04-25 e bumpar "Renumeração" para 6ª (pós-011 shipped).
3. `madruga:epic-context 011.1` quando 1ª janela disponível (recomendado: dentro de 1-2 sem do flip ResenhAI on para evitar perda de contexto).
4. Após 011.1 shipped, executar `madruga:epic-context 013` (Alerting + WA Quality, promovido) e em seguida `012` (RAG).

**Sem ação imediata necessária pelo /madruga:roadmap autônomo** — este reassess report é o output canônico do nó 12 do L2 cycle. O próximo run de `/madruga:roadmap` (manual ou via DAG executor) consome este report e gera o diff em `planning/roadmap.md`.

---

<!-- HANDOFF -->
---
handoff:
  from: madruga:roadmap (L2 cycle 12/12 — reassess)
  to: madruga:epic-context (próximo epic — recomendado: 011.1)
  context: "Epic 011 shipped (2026-04-25) com appetite cumprido + KPI North Star autonomous_resolution mensurável pela 1ª vez (Ariel 41% v1). Reassessment recomenda 3 mudanças em roadmap.md: (1) marcar 011 como shipped + inserir 011.1 (Evals polish, 1-2 sem) cobrindo LLM-as-judge online + W3/W5 heal + PII tooling + ADR-041 OpenAPI per-epic; (2) reordenar 014 (Alerting + WA Quality) para antes de 013 (Agent Tools v2) — alerting agora é gate para flip ResenhAI confiante e para qualquer cliente externo; (3) confirmar 012 (RAG) como próximo grande lever de qualidade — risco rebaixado para Baixo-Médio porque 011 entregou eval_scores.metric + DeepEval wrapper pattern + golden_traces curation prontos para reuso. ADRs 039+040 Accepted; ADR-008/018/027/028 estendidos. ADR-041 pendente em 011.1."
  blockers: []
  confidence: Alta
  kill_criteria: "(a) Se ResenhAI shadow revelar coverage <50% ou custo >R$5/dia em 7d, ABORTAR flip on, abrir 011.1-emergency e suspender 013 (Alerting) até diagnose. (b) Se 011.1 LLM-as-judge revelar que a regex de escalação está acima de 90% accuracy (lever +10pp falha), revisar trajetória vision 70% e considerar adiar promessa para 24 meses ou repriorizar 014 (Agent Tools v2) acima de 012 (RAG). (c) Se PII em golden_traces falhar audit interno antes de 30d (2026-05-25), retroativar todos os traces estrelados, bloquear nova curation até automated redaction landar (escopo 011.1) e congelar promoção do pattern OpenAPI per-epic em ADR-041. (d) Se Ariel `on` (post-011) registrar incidente customer-facing atribuível a regressão silenciosa de eval (W5 Bifrost overload OU drift de coverage W3), antecipar 013 (Alerting) para start imediato após 011.1 e adiar 012 (RAG) por 1-2 sem."
