---
title: 'ADR-040: Autonomous resolution operational definition (heuristic A)'
status: Proposed
decision: Cron noturno `autonomous_resolution_cron` (03:00 UTC) popula
  `conversations.auto_resolved BOOLEAN` usando heuristica A canonica:
  (a) SEM mute em `handoff_events`, (b) SEM regex de escalacao
  (`humano|atendente|pessoa|alguem real`) em inbound direcionado ao bot,
  (c) silencio do cliente >=24h, (d) filtro `messages.is_direct=TRUE`
  para grupo-chat. Singleton via `pg_try_advisory_lock(hashtext('autonomous_resolution_cron'))`.
alternatives: LLM-as-judge classificando resolucao, Heuristica per-segment
  (grupo vs 1:1), Heuristica baseada em NPS pos-conversa, Nao medir
  (KPI sem north-star quantitativo), Calculo real-time em cada msg
rationale: Heuristica deterministica e barata, auditavel linha a linha,
  reversivel. Fecha o gap entre vision ("70% resolucao autonoma 18m")
  e pipeline em producao sem criar novo custo LLM ou infra.
  LLM-as-judge fica para 011.1 apos termos 30d de baseline heuristico.
---
# ADR-040: Autonomous resolution operational definition (heuristic A)

**Status:** Proposed | **Data:** 2026-04-24 | **Relaciona:** [ADR-036](ADR-036-ai-active-unified-mute-state.md), [ADR-039](ADR-039-eval-metric-bootstrap.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md), `../business/vision.md`

> **Escopo:** Epic 011 (Evals). Aplica-se a `apps/api/prosauai/evals/autonomous_resolution.py`,
> `apps/api/db/migrations/20260601000003_alter_conversations_auto_resolved.sql`,
> `apps/api/db/migrations/20260601000004_alter_messages_is_direct.sql` e ao
> `autonomous_resolution_cron` registrado pelo `EvalsScheduler`.

## Contexto

A vision do ProsaUAI (`platforms/prosauai/business/vision.md`) declara
meta de **"70% de resolucao autonoma em 18 meses"**. Ate o epic 011 esse
KPI era um vetor de aspiracao, nao uma coluna mensuravel — nao havia
definicao operacional de "resolvido autonomamente".

Candidatos investigados:

| Definicao | Problema |
|-----------|----------|
| "Conversa fechada sem atendente humano intervir" | Nao distingue entre bot-resolveu vs cliente-abandonou. |
| "Bot enviou a ultima mensagem" | Ignora case onde bot respondeu algo e cliente desistiu sem resposta clara. |
| "Cliente nao pediu handoff explicito" | Preciso mas nao captura mute manual (admin silenciou). |
| "Silencio do cliente por N horas apos ultima resposta do bot" | Proxy fraco mas falsamente positivo em clientes que so queriam info + sumiram. |

O epic 010 ja entrega **sinal operacional chave**: `handoff_events` com
tipo `mute` quando a conversa foi explicitamente transferida para
atendente (via webhook Chatwoot, manual admin, ou fromMe detection).

Ainda faltam dois sinais:

1. **Regex de escalacao** no conteudo do cliente (`humano|atendente|
   pessoa|alguem real|falar com pessoa`) — captura pedido explicito de
   escalacao que nao virou `mute` (ex.: admin viu e decidiu nao mutar,
   mas o cliente pediu).
2. **Filtro grupo-chat**: em grupo do WhatsApp, mensagens nao-direcionadas
   ao bot (sem mention, sem reply) sao ruido. Se contarmos como "inbound
   directed" todas as msgs do grupo, heuristica fica enviesada.

## Decisao

We will definir **heuristica A** como norma operacional de `auto_resolved`,
avaliada por cron noturno:

### Heuristica A — condicoes cumulativas

Uma conversa `closed` e marcada `auto_resolved=TRUE` sse TODAS:

1. **(a) Nao houve `handoff_events.kind='mute'`** para a conversa ate o
   fechamento. Source: `SELECT NOT EXISTS (SELECT 1 FROM handoff_events
   WHERE conversation_id=$1 AND kind='mute')`.

2. **(b) Nenhuma mensagem inbound direcionada contem regex de escalacao**.
   Source: `SELECT NOT EXISTS (SELECT 1 FROM messages WHERE
   conversation_id=$1 AND direction='inbound' AND is_direct=TRUE AND
   content ~* '\y(humano|atendente|pessoa|alguem real)\y')`.
   Regex case-insensitive, word-boundary (`\y` no regex POSIX Postgres).

3. **(c) Silencio do cliente >=24h**. Source: `(SELECT MAX(created_at)
   FROM messages WHERE conversation_id=$1 AND direction='inbound' AND
   is_direct=TRUE) < NOW() - INTERVAL '24 hours'`.

4. **(d) Filtro grupo-chat via `is_direct`**: apenas msgs com
   `is_direct=TRUE` contam em (b) e (c). Em 1:1 todas as msgs sao
   directas por default. Em grupo, adapter seta `is_direct` quando a
   msg e mention/reply ao bot.

### Tri-state `auto_resolved`

- `NULL` — ainda nao calculado. Cron ainda nao processou ou conversa
  ainda esta aberta.
- `TRUE` — heuristica A passou.
- `FALSE` — heuristica A reprovou (explicitamente nao-autonoma).

Tri-state intencional: `NULL` nao conta no KPI North Star ("% auto_resolved
entre conversas fechadas"). Permite reprocessamento controlado
(`UPDATE ... SET auto_resolved=NULL WHERE ...` + re-run cron).

### Singleton via advisory lock

Cron roda `pg_try_advisory_lock(hashtext('autonomous_resolution_cron'))`.
Se lock nao obtido, loga `skipped=lock_held` e retorna. Garante que
multiplos workers do uvicorn nao processem em paralelo (race
`UPDATE` → scores diferentes em cada rodada).

### Reprocessamento

Cron filtra `WHERE auto_resolved IS NULL AND closed_at < NOW() -
INTERVAL '24 hours' LIMIT 1000`. Nao re-processa rows com valor ja
setado — manter historico estavel. Se heuristica mudar (v2), migrar
atraves de `UPDATE conversations SET auto_resolved=NULL WHERE closed_at
> NOW() - INTERVAL 'N days'` + re-run.

## Alternativas consideradas

### A. LLM-as-judge classificando resolucao

- **Pros:** captura nuances ("o cliente parece satisfeito mesmo sem dizer",
  "o bot deu info errada mas cliente nao pediu escalacao"). Mais proximo
  da verdade humana.
- **Cons:**
  - Custo: ~R$0.01/conversa × 500 conversas/dia/tenant = R$10/dia × 2
    tenants = R$600/mes. Fora do budget SC-011 (≤R$3/dia combinado).
  - Latencia: cron demora 2-4h em vez de 5min.
  - Dependencia de calibracao: sem baseline heuristico, nao sabemos se
    o judge esta sobre-marcando `TRUE` ou sub-marcando.
- **Rejeitada porque:** heuristica determinista como baseline e
  pre-requisito. LLM-as-judge vira v2 em 011.1 comparando taxa com
  baseline + alerta em divergencia >15pp.

### B. Heuristica per-segment (grupo vs 1:1)

- **Pros:** bot em grupo opera muito diferente de 1:1 (mais ruido,
  mention sparse). Conditions (c) poderia ser 48h em grupo vs 24h em 1:1.
- **Cons:**
  - Cria 2 caminhos de codigo + 2 thresholds para tunar.
  - Ariel + ResenhAI sao overwhelmingly 1:1 — over-engineering para v1.
  - `is_direct=TRUE` default em grupo pre-epic gera FP <5% (R6 no plan.md).
- **Rejeitada porque:** `is_direct` filter e condicao suficiente. Per-segment
  thresholds revisado em 011.1 se dado de producao mostrar bias por segmento.

### C. NPS pos-conversa (perguntar ao cliente)

- **Pros:** ground-truth direto. Gold standard para calibrar qualquer
  heuristica.
- **Cons:**
  - Requer UX pos-close que nao existe (chatbot enviando NPS survey).
  - Taxa de resposta tipica 5-15% — amostra pequena.
  - Aciona fadiga em clientes das comunidades esportivas (Ariel/ResenhAI).
- **Rejeitada porque:** fora do escopo do epic 011. Considerado como
  side-channel de validacao futura (conf Pace decide se/quando lancar).

### D. Nao medir (aceitar KPI qualitativo)

- **Pros:** zero codigo novo. Operadores reportam ad-hoc.
- **Cons:**
  - Vision tem meta numerica (70% em 18m) — precisa ser mensuravel.
  - Sem KPI, decisoes de roadmap ficam sem backing quantitativo.
- **Rejeitada porque:** viola compromisso com a vision.

### E. Calculo real-time em cada msg

- **Pros:** dashboard sempre fresh; admin ve efeito imediato de mute.
- **Cons:**
  - Overhead de query por msg no hot path.
  - Condition (c) "silencio >=24h" e inerentemente retroativo — so faz
    sentido avaliar quando conversa fecha.
- **Rejeitada porque:** cron noturno satisfaz necessidade operacional
  (North Star e mensal, nao real-time). Performance AI cards sao
  servidos por query agregada em cima do resultado do cron.

## Consequencias

- [+] **Vision mensuravel** — "% auto_resolved" vira coluna SQL queryavel
  por janela 30d/90d/18m.
- [+] **Auditavel linha a linha** — operador pode fazer `SELECT * FROM
  conversations WHERE auto_resolved=FALSE` e entender rapidamente por
  que a heuristica reprovou (via joins com handoff_events + messages).
- [+] **Zero custo LLM adicional** — puro SQL.
- [+] **Reversivel** — mudanca de heuristica = mudanca de query + UPDATE
  para reprocessar (tri-state `NULL` e o estado intermediario).
- [+] **Sem impacto no hot path** — cron roda 03:00 UTC (horario morto).
- [-] **Heuristica grosseira** — falha em capturar casos sutis (bot deu
  info errada, cliente abandona frustrado sem pedir humano). Mitigacao:
  cross-reference com DeepEval `answer_relevancy` (ADR-039) em 011.1 para
  refinar.
- [-] **Regex fixo em portugues brasileiro** — `humano|atendente|pessoa|
  alguem real` cobre Ariel + ResenhAI mas nao seria adequado para tenant
  em ingles ou espanhol. Aceito (v1 so tem tenants PT-BR).
- [-] **Default `is_direct=TRUE`** distorce historia pre-epic em grupos
  (R6). Mitigacao: documentar em runbook que KPI para janelas que cobrem
  pre-epic precisa ter tolerancia ±5%.
- [-] **Re-processamento e opcional** — se cron falhar por 3 dias, as
  conversas fechadas nesses dias viram parte do pool "NULL forever"
  ate `UPDATE` manual. Aceito: advisory lock + metric alertam falha.

## Metricas de sucesso (pos-deploy)

Monitorar pos PR-A merge:

| Metrica | Alvo |
|---------|------|
| `autonomous_resolution_ratio{tenant='ariel', window='7d'}` | >=0 (existe) + tendencia nao-monotona → heuristica diferencia casos |
| Cron duration (`eval_batch_duration_seconds{job='autonomous_resolution'}`) | <5min para volume diario ariel+resenhai |
| Taxa `auto_resolved=NULL` em conversas closed >48h | <1% (indica cron rodando normalmente) |
| `handoff_events_total` × taxa de `auto_resolved=FALSE` | Correlacao forte esperada (>=80% dos FALSE tem handoff mute) |

**North Star atingido** (18 meses): `AVG(auto_resolved::int) WHERE
closed_at > NOW() - INTERVAL '30 days' GROUP BY tenant_id` >= 0.70
para ambos Ariel e ResenhAI.

## Teste de regressao

`apps/api/tests/unit/evals/test_autonomous_resolution.py` (T035):

```python
async def test_heuristic_a_positive(pool):
    """Caso positivo: sem mute, sem regex, silencio >=24h, is_direct=TRUE."""
    # Seed: conversa fechada ha 25h, 1 msg inbound "oi, qual o jogo hoje?",
    # 1 msg outbound "A as 16h", cliente nao respondeu.
    cid = await _seed_autoresolved_positive(pool)

    from prosauai.evals.autonomous_resolution import run_cron_once
    await run_cron_once(pool)

    row = await pool.fetchrow("SELECT auto_resolved FROM conversations WHERE id=$1", cid)
    assert row["auto_resolved"] is True


async def test_heuristic_a_negative_has_mute(pool):
    """Caso negativo: teve handoff_events.kind='mute'."""
    cid = await _seed_with_mute_event(pool)
    await run_cron_once(pool)
    row = await pool.fetchrow("SELECT auto_resolved FROM conversations WHERE id=$1", cid)
    assert row["auto_resolved"] is False


async def test_heuristic_a_negative_escalation_regex(pool):
    """Caso negativo: inbound contem 'falar com atendente'."""
    cid = await _seed_with_escalation_content(pool, "quero falar com atendente")
    await run_cron_once(pool)
    row = await pool.fetchrow("SELECT auto_resolved FROM conversations WHERE id=$1", cid)
    assert row["auto_resolved"] is False


async def test_group_non_direct_ignored(pool):
    """Msg grupo sem mention (is_direct=FALSE) nao conta para condicao (c)."""
    # Bot respondeu, cliente "falou" no grupo sem mencionar o bot.
    # Silencio do cliente em direct msgs >=24h → heuristica A passa.
    cid = await _seed_group_noise_no_direct(pool)
    await run_cron_once(pool)
    row = await pool.fetchrow("SELECT auto_resolved FROM conversations WHERE id=$1", cid)
    assert row["auto_resolved"] is True
```

---

> **Proximo passo:** T012-T013 criam as migrations `conversations.auto_resolved`
> + `messages.is_direct`; T033-T039 implementam o cron. Este ADR e a
> referencia normativa para ambos.
