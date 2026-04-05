# Operacao Assistida #1 — 2026-04-05

## Resumo

Operacao assistida do daemon madruga.ai com monitoramento de pipeline, portal (dashboard + observability), e resolucao de bugs em tempo real.

**Duracao**: ~2 horas de operacao ativa (daemon running 100+ min)
**Branch**: `epic/madruga-ai/020-code-quality-dx`
**Test suite**: 551 testes, 0 falhas (5 novos adicionados)
**Epic 021**: Pipeline executando autonomamente — 31+ nodes completados (27 implement tasks)

---

## O que esta funcionando bem

### Pipeline & BD
- **15 epics shipped** (006-020) para plataforma madruga-ai — ciclo L2 completo
- **L1 100%** (13/13 nodes) para madruga-ai
- SQLite WAL mode estavel (58 traces, 56 eval scores, 46 pipeline runs, 40 events)
- Gate system funcional: pending gates detectados e aprovados corretamente
- Sequential constraint do daemon funciona (1 epic por vez)

### Portal
- Dashboard servindo via Astro SSR na porta 4321 — HTTP 200 em todas as rotas
- Paginas: `/`, `/madruga-ai/dashboard/`, `/madruga-ai/observability/`, `/fulano/dashboard/`
- PipelineDAG component renderiza com dados completos via SSR props
- ObservabilityDashboard com 4 tabs (Runs, Traces, Cost, Evals) conectando a `localhost:8040`

### Daemon
- FastAPI app inicia corretamente com lifespan context
- Endpoints `/health` e `/status` respondem corretamente
- APIs de observability (`/api/traces`, `/api/evals`, `/api/stats`) funcionais com filtro por platform
- Exponential backoff funcionando para erros consecutivos

### Eval Scores (epic 020)
| Dimensao | Media | Scores |
|----------|-------|--------|
| adherence_to_spec | 7.4 | 14 |
| completeness | 10.0 | 14 |
| cost_efficiency | 5.0 | 14 |
| quality | 7.8 | 14 |

---

## Bugs encontrados e corrigidos

### BUG 1: Trace Spam no Daemon (CRITICO)

**Sintoma**: 25+ traces orphan criadas em ~3 minutos, todas com `status=running`, 0 nodes, 0 spans.

**Causa raiz**: `create_trace()` era chamado ANTES do check de pending gates em `run_pipeline_async`. Quando o gate estava pendente, a funcao retornava imediatamente mas a trace ja tinha sido criada. O daemon re-despachava a cada 15s, criando mais traces.

**Fix aplicado**:
- `dag_executor.py`: Movido `create_trace()` para DEPOIS do gate check (ambas versoes async e sync)
- Teste de regressao: `test_run_pipeline_async_no_trace_when_gate_pending`

**Arquivos**: `dag_executor.py` (linhas 1079-1113), `test_dag_executor.py`

### BUG 2: Daemon Re-dispatch com Gate Pendente

**Sintoma**: Daemon despachava o mesmo epic a cada 15s mesmo com gate `waiting_approval`.

**Causa raiz**: O `dag_scheduler` nao verificava se o epic tinha gates pendentes antes de despachar. O epic era adicionado a `_running_epics`, `run_pipeline_async` retornava 0, e no finally o epic era removido — permitindo re-dispatch.

**Fix aplicado**:
- `daemon.py`: Adicionado check de `get_pending_gates` antes do dispatch. Se epic tem gate `waiting_approval`, faz `continue` (skip).
- Teste de regressao: `test_dag_scheduler_skips_epic_with_pending_gate`

**Arquivos**: `daemon.py`, `test_daemon.py`

### BUG 3: progress_pct nao contava skipped nodes

**Sintoma**: Epic 020 mostrava "10/11 (90.9%)" mesmo com todos nodes completos (qa era `skipped`).

**Causa raiz**: `get_epic_status()` e `get_platform_status()` calculavam `progress_pct` como `done / total`, sem incluir `skipped` no numerador. Display no CLI tambem mostrava apenas `done` no "X/Y".

**Fix aplicado**:
- `db_pipeline.py`: `progress_pct = (done + skipped) / total`
- `platform_cli.py`: Display usa `done + skipped` como numerador; adicionado campo `skipped` no JSON do epic
- Testes: `test_get_epic_status_progress_includes_skipped`, `test_get_platform_status_progress_includes_skipped`, `test_progress_pct_zero_skipped_unchanged`

**Arquivos**: `db_pipeline.py`, `platform_cli.py`, `test_db_pipeline.py`

---

## Blocker identificado

### claude -p nao autentica via OAuth (subprocess)

**Impacto**: O daemon nao consegue despachar skills. Nenhum epic pode progredir via daemon autonomo.

**Causa**: A autenticacao do Claude CLI usa OAuth (claude.ai first-party). Em modo `-p` (pipe/subprocess), a sessao OAuth nao e propagada. O subprocess retorna "Not logged in".

**Evidencia**:
```
$ claude -p "echo hello" --bare --output-format json
{"is_error":true,"result":"Not logged in · Please run /login"}
```

**Solucao proposta**:
1. Configurar `ANTHROPIC_API_KEY` no `.env` para auth via API key (funciona em subprocess)
2. Ou: executar `claude login` com API key auth em vez de OAuth
3. Alternativa: rodar pipeline manualmente via esta sessao (skills diretos)

**Prioridade**: BLOCKER para operacao autonoma do daemon

---

## Cleanup realizado

| Acao | Quantidade |
|------|-----------|
| Traces orphan canceladas | 58 |
| Gates aprovados | 3 (reconcile/020, specify/021, plan/fulano-001) |
| Epic 020 marcado shipped | 1 |
| Pipeline runs failed resetados | 1 |

---

## Metricas do portal

| Pagina | Status | Componentes |
|--------|--------|-------------|
| `/` (home) | HTTP 200 | Links para ambas plataformas |
| `/madruga-ai/dashboard/` | HTTP 200 | PipelineDAG (React SSR) |
| `/madruga-ai/observability/` | HTTP 200 | ObservabilityDashboard (React, 4 tabs) |
| `/fulano/dashboard/` | HTTP 200 | PipelineDAG (React SSR) |
| `/madruga-ai/bc/observability/` | HTTP 200 | LikeC4Diagram (bounded context zoom) |

**Playwright**: Firefox nao inicia no WSL2 (sem display). Config alterada para `--headless --browser chromium` mas precisa restart do MCP server para efetivar.

---

## Melhorias sugeridas

### Alta prioridade
1. **Configurar ANTHROPIC_API_KEY** — unico blocker para daemon autonomo
2. **Playwright headless por padrao** — detectar WSL2/CI e usar `--headless` automaticamente
3. **Daemon: limitar retries por sessao** — apos 3 falhas consecutivas de um node, parar de redespachar ate intervencao manual (evitar loop infinito de falhas)

### Media prioridade
4. **Trace dedup** — antes de criar trace, verificar se ja existe uma `running` para o mesmo epic/mode
5. **Stale node detection** — 4 nodes L1 marcados como `stale` no madruga-ai (vision, codebase-map, adr, roadmap). Considerar job periodico de re-validacao
6. **Cost tracking** — todos os campos de custo (tokens_in, tokens_out, cost_usd) estao NULL. Implementar extracao do output JSON do `claude -p`
7. **Export CSV** — endpoint `/api/export/csv` existe mas nao foi testado nesta operacao

### Baixa prioridade
8. **Telegram bot config** — env vars ausentes em dev. Considerar mock/dry-run mode para testes
9. **Portal observability offline** — quando daemon para, dashboard mostra dados vazios sem indicacao de erro. Adicionar banner "daemon offline"
10. **Epic 021-pipeline-intelligence** — precisa do ciclo L2 completo (specify -> reconcile)

---

## Diff desta operacao

```
 .specify/scripts/daemon.py                  |  13 ++++++++
 .specify/scripts/dag_executor.py            |  30 +++++++++--------
 .specify/scripts/db_pipeline.py             |   4 +--
 .specify/scripts/platform_cli.py            |   7 ++--
 .specify/scripts/tests/test_daemon.py       |  44 +++++++++++++++++++++++++
 .specify/scripts/tests/test_dag_executor.py |  40 +++++++++++++++++++++++
 .specify/scripts/tests/test_db_pipeline.py  |  49 ++++++++++++++++++++++++++++
 8 files changed, 169 insertions(+), 18 deletions(-)
```

**Test suite**: 551 passed (546 pre-existentes + 5 novos)
