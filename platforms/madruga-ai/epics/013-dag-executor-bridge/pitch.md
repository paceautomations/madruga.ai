---
id: 013
title: "DAG Executor + SpeckitBridge"
status: shipped
appetite: 6w
priority: 1
delivered_at: 2026-03-31
updated: 2026-03-31
---
# DAG Executor + SpeckitBridge

## Problem

O pipeline hoje e invocado manualmente skill por skill. Nao existe runtime que execute o DAG automaticamente, respeite gates, gerencie estado de execucao, ou faca dispatch de skills via `claude -p`. Sem isso, o pipeline nao pode operar autonomamente.

## Appetite

**6w** — Core do runtime. Maior incerteza tecnica (DAG executor, gate state machine, claude -p dispatch). Absorver risco cedo.

## Dependencies

- Depends on: 012 (multi-repo precisa estar funcional)
- Blocks: 014 (gate state machine necessaria para notificacoes), 015 (dispatch necessario para subagent judge)



## Captured Decisions

| # | Area | Decision | Referencia Arquitetural |
|---|------|---------|------------------------|
| 1 | Runtime mode | **Standalone CLI** (`dag_executor.py --platform <name>`) — sem daemon/FastAPI neste epic. Daemon vem no epic 016. Executor roda como processo unico, sync subprocess. | ADR-017 (custom DAG executor), blueprint §3.1 (topologia) |
| 2 | Human gates | **CLI-only** — operador executa `platform.py gate approve <run-id>` manualmente. Pipeline bloqueia ate aprovacao (SQLite polling nao necessario agora). Telegram (014) e daemon polling (016) integram depois. | ADR-017 (human gate pause/resume), blueprint §1.4 (human gate timeout) |
| 3 | SpeckitBridge | **Reutilizar `compose_prompt()` do `implement_remote.py`** (epic 012) como base. Generalizar para todas as skills: cada skill type tem um template de prompt. Nao criar modulo separado — estender o existente. | Epic 012 (implement_remote.py:20), ADR-010 (claude -p subprocess) |
| 4 | Concorrencia | **Single executor = 1 claude -p por vez.** Sem semaforo file-based. Concorrencia (max 3 paralelos) fica para epic 016 (daemon asyncio com semaforo). | Blueprint Q9 (max 3 concorrentes), ADR-017 |
| 5 | Schema SQLite | **Adicionar campos na tabela `pipeline_runs` existente**: `gate_status` (TEXT: waiting_approval/approved/rejected/null), `gate_notified_at` (TEXT ISO), `gate_resolved_at` (TEXT ISO). Nova migration. Sem tabela nova. | ADR-012 (SQLite WAL), db.py pipeline_runs |
| 6 | Appetite | **Foco em alta qualidade, consistencia e performance.** ADR-017 estima 500-800 LOC. Infraestrutura existente (db.py, platform.yaml, implement_remote.py) reduz risco. Entrega rapida com cobertura de testes completa. | ADR-017 (estimativa LOC), epic 012 (precedente: 2w→1d) |

## Resolved Gray Areas

### 1. Como o executor sabe qual skill executar para cada node?

**Pergunta:** platform.yaml define `skill: "madruga:vision"` por node. Como traduzir isso em invocacao?

**Resposta:** O executor compoe um prompt baseado no skill name. Para skills L1 (madruga:*), o prompt e: "Execute /madruga:<skill> <platform>" com contexto dos artefatos de dependencia. Para skills L2 (speckit.*), usa `compose_prompt()` do implement_remote.py com artefatos do epic. Em ambos os casos, `claude -p --cwd=<repo_path>` executa.

**Racional:** Unifica dispatch via claude -p. O skill e uma instrucao no prompt, nao um import Python. Claude Code resolve o skill name internamente.

### 2. Como o executor detecta que um node completou com sucesso?

**Pergunta:** `claude -p` retorna exitcode 0/!=0. Mas como saber se o artefato esperado foi gerado?

**Resposta:** Dupla verificacao: (1) exitcode 0 do claude -p, (2) verificar que o(s) arquivo(s) listados em `outputs` do node existem no filesystem. Se exitcode=0 mas output ausente, marcar como `failed` com mensagem "output not found". Usar `post_save.py` existente para gravar no DB.

**Racional:** Exitcode sozinho nao garante que o skill gerou o artefato. Verificacao de filesystem e barata e deterministica.

### 3. Como funciona o resume apos human gate?

**Pergunta:** Operador aprova via CLI. Como o executor retoma?

**Resposta:** Fluxo em 2 fases:
1. **Executor roda** → atinge human gate → grava `gate_status=waiting_approval` no DB → imprime mensagem "Aguardando aprovacao para <node>. Execute: `platform.py gate approve <run-id>`" → **exit 0** (nao fica bloqueado).
2. **Operador aprova** → `platform.py gate approve <run-id>` → grava `gate_status=approved` + `gate_resolved_at` no DB.
3. **Operador re-executa** → `dag_executor.py --platform <name> --resume` → executor le DB, pula nodes completos, retoma do proximo node pronto.

**Racional:** Executor stateless entre runs. SQLite e o unico estado. Sem processo bloqueado esperando — operador re-invoca quando quiser. Compativel com daemon futuro (016) que fara polling automatico.

### 4. DAG traversal: topological sort ou priority queue?

**Pergunta:** ADR-017 menciona ambos.

**Resposta:** **Topological sort simples** (Kahn's algorithm). Pipeline tem 24 nodes com dependencias claras — nao precisa de priority queue. Nodes prontos (deps satisfeitas) sao executados sequencialmente na ordem topologica. Sem paralelismo neste epic.

**Racional:** Kahn's e ~30 LOC, determinístico, facil de testar. Priority queue adiciona complexidade sem beneficio para executor single-threaded.

### 5. L1 vs L2: como o executor distingue?

**Pergunta:** L1 roda uma vez por plataforma. L2 roda por epic. Como diferenciar?

**Resposta:** Dois modos de invocacao:
- `dag_executor.py --platform <name>` → executa L1 (le `pipeline.nodes` do platform.yaml)
- `dag_executor.py --platform <name> --epic <slug>` → executa L2 (le `pipeline.epic_cycle.nodes`)

Estado separado no DB: L1 usa `pipeline_nodes`, L2 usa `epic_nodes`. Ambos ja existem.

**Racional:** Separacao clara de contexto. Executor usa a mesma logica (topological sort + dispatch), so muda a fonte do DAG e a tabela de estado.

## Applicable Constraints

| Constraint | Fonte | Impacto no Epic |
|-----------|-------|-----------------|
| Zero deps novas | ADR-017, blueprint | Apenas stdlib Python + pyyaml (existentes) |
| SQLite WAL mode | ADR-012 | Writes serializados, busy_timeout=5000ms |
| claude -p subprocess | ADR-010 | Dispatch via subprocess.run, nao import |
| Filesystem source of truth | ADR-004 | Artefatos em disco, DB e cache/estado |
| Circuit breaker | ADR-011, blueprint §1.4 | Suspender apos 5 falhas, recovery 300s |
| Retry com backoff | Blueprint §1.4 | 3x com backoff exponencial (5s, 10s, 20s) |
| Watchdog timeout | Blueprint §1.4 | SIGKILL apos timeout configuravel |
| Output format json | Blueprint §1.4 | `--output-format json` para evitar stream-json bug |
| Max 500-800 LOC | ADR-017 | Codigo de producao, excluindo testes |

## Suggested Approach

### Entregaveis

1. **`dag_executor.py`** (~400-500 LOC) — Core: DAG parser (topological sort), dispatch loop, gate state machine, retry/circuit breaker, output verification, resume. Path: `.specify/scripts/dag_executor.py`

2. **Extensao de `implement_remote.py`** (~50 LOC) — Generalizar `compose_prompt()` para aceitar qualquer skill (nao so implement). Adicionar `compose_skill_prompt(platform, node, skill_type)` que monta o prompt correto por tipo de skill.

3. **Extensao de `platform.py`** (~30 LOC) — Subcomandos: `gate approve <run-id>`, `gate reject <run-id>`, `gate list` (pending gates).

4. **Migration SQLite** — Adicionar `gate_status`, `gate_notified_at`, `gate_resolved_at` a `pipeline_runs`.

5. **Extensao de `db.py`** (~40 LOC) — Funcoes: `approve_gate()`, `reject_gate()`, `get_pending_gates()`, `get_resumable_nodes()`.

6. **Testes** — pytest: DAG traversal (unit), gate state machine (unit), dispatch mock (integration), resume (integration).

### Sequencia

```
T1: Migration SQLite + db.py gate functions
T2: DAG parser (topological sort) + testes
T3: Dispatch loop + output verification + testes
T4: Gate state machine (pause/approve/reject) + testes
T5: Retry + circuit breaker + watchdog + testes
T6: SpeckitBridge (generalizar compose_prompt) + testes
T7: platform.py gate subcommands
T8: L2 mode (--epic flag) + testes
T9: Integration test end-to-end (L1 dry-run)
T10: Polish, ruff, docs
```

### O que NAO esta no scope

- Daemon/FastAPI (epic 016)
- Telegram notifications (epic 014)
- Subagent Judge (epic 015)
- Concorrencia de claude -p (epic 016)
- Web UI para gates (portal dashboard ja existe)

handoff:
  from: epic-context
  to: speckit.specify
  context: "Decisoes capturadas: standalone CLI, human gates CLI-only, SpeckitBridge reutiliza compose_prompt, single executor, schema extends pipeline_runs. Pronto para specify."
  blockers: []
  confidence: Alta
  kill_criteria: "Se claude -p nao suportar dispatch de skills via prompt, abordagem inteira precisa revisao."
