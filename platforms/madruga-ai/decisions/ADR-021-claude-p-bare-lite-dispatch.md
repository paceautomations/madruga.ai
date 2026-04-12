---
title: "ADR-021: Bare-Lite Dispatch Flags + Task-Scoped Context"
status: accepted
date: 2026-04-10
decision: Reduzir input tokens do `claude -p` dispatch em ~50% combinando (a) flags
  `--strict-mcp-config`, `--disable-slash-commands`, `--tools`, `--no-session-persistence`
  para aproximar `--bare` sob OAuth, e (b) escopar `compose_task_prompt` por metadados
  de task em vez de injetar docs estáticos incondicionalmente. Tudo com kill-switch
  via env var para rollback sub-10s.
alternatives: Migrar para `--bare` com ANTHROPIC_API_KEY; comprimir tasks.md;
  subagents para leituras pesadas
rationale: OAuth DOES usar prompt caching (validado empiricamente) e os flags funcionam
  sob subscription. Task metadata (files, description) é suficiente para gating sem
  embeddings nem parsing semântico.
---
# ADR-021: Bare-Lite Dispatch Flags + Task-Scoped Context

## Status

Accepted — 2026-04-10

## Contexto

O `dag_executor` dispatcha tasks de implementação via `claude -p` e o portal estava reportando **1-3M input tokens cumulativos por task** (T032 do epic prosauai/003 atingiu 2.6M). Um ciclo L2 de ~40 tasks queimava ~80-120M tokens.

A investigação (plan: `/home/gabrielhamu/.claude/plans/goofy-humming-mitten.md`) identificou três causas compostas:

1. **MCP servers + skills list + tool definitions** injetadas em todo dispatch via `build_system_prompt`, herdadas do user scope (CLAUDE.md + `~/.claude/settings.json`) porque `--bare` requer ANTHROPIC_API_KEY e o operador usa OAuth.
2. **Hook contamination**: `simplify-reminder.sh` (Stop hook) dispara em todas as sessões dispatched, forçando Claude a gastar turns extras respondendo ao aviso.
3. **`compose_task_prompt` injeta docs estáticos incondicionalmente**: plan.md + spec.md + data-model.md + contracts/*.md + analyze-report.md + implement-context.md acumulado, totalizando 100-155KB por user prompt por task, independente de a task tocar models, APIs ou o report.

O constraint de billing (ADR-010) descarta `--bare`. A restrição de subscription OAuth removida em 2026-03-17 afeta programmatic API access, **não** o Claude Code CLI — caching funciona sob OAuth, confirmado empiricamente por chamadas de teste.

## Decisao

Aplicar uma sequência de reduções validadas empiricamente, cada uma com kill-switch via env var:

### Dispatch flags (`dag_executor.build_dispatch_cmd`, Action 1)

Gated por `MADRUGA_BARE_LITE=1` (default on):
- `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` — zero MCP servers carregados
- `--disable-slash-commands` — skip skill auto-resolver (skill body injetado via `--system-prompt`)
- `--tools Read,Edit,Write,Bash,Grep,Glob` — prune tool definitions, **apenas** em nodes `implement:*` (judge/qa precisam de Agent, tech-research precisa de Web*)
- `--no-session-persistence` — apenas em dispatches fresh (omitido em `--resume`)

Gated por `MADRUGA_STRICT_SETTINGS=1` (opt-in, off por default):
- `--setting-sources project` — ignora user scope + local scope. Requer auditoria prévia de `settings.local.json` para garantir que nenhum dispatch depende dele.

### Task-scoped context (`dag_executor.compose_task_prompt`, Actions 2 + 3a)

Gated por `MADRUGA_KILL_IMPLEMENT_CONTEXT=1` (default on):
- `append_implement_context` vira NO-OP — progresso recente é derivado de `[t.id for t in tasks if t.checked][-5:]` direto do tasks.md autoritativo. Zero I/O adicional, zero cross-trace leakage.

Gated por `MADRUGA_SCOPED_CONTEXT=1` (default on):
- `data-model.md` injetado apenas se `task.files` casa `(^|/)(models|schemas|migrations|db)/` OU description tem `\b(model|entity|schema|migration|dataclass|pydantic|table)\b`
- `contracts/*.md` injetado apenas se `task.files` casa `(^|/)(api|routes|handlers|endpoints|webhooks)/` OU description tem `\b(api|endpoint|webhook|contract|validation|serializer|dto|route)\b`
- `analyze-report.md` filtrado a parágrafos que mencionam o `task.id`; se não houver menções, a seção é omitida

### Hook discipline (`sync_memory.py`, Action 5)

O flag `MADRUGA_DISPATCH=1` que o `_dispatch_env()` já seta virou semáforo vivo:
```python
if os.environ.get("MADRUGA_DISPATCH") == "1":
    sys.exit(0)
```
`sync_memory.py` agora respeita o flag e não roda durante dispatch, eliminando a PostToolUse write cascade + WAL contention que amplificava latência em tasks com muitos Edit.

## Alternativas Consideradas

### Alternativa A: Flags bare-lite + task-scoped context (escolhida)

- **Pros:**
  - Validado empiricamente: 64,280 → 19,340 tokens (-70%) em teste isolado; 4.96MB → 3.64MB (-26.6%) em prompts compostos do epic 003
  - Turns por task caem de 2 para 1 no smoke test (hook isolation)
  - Zero novo dep, zero mudança de auth, zero impacto em judge/qa/tech-research
  - Rollback sub-10s via systemd drop-in (`MADRUGA_BARE_LITE=0`, etc.)
  - Byte-a-byte idêntico ao baseline quando todos os kill-switches desligados
- **Cons:**
  - Heurísticas regex em task.description podem ter falsos positivos/negativos; mitigado por word boundaries + path anchors + fallback via description keywords
  - Requer documentação de env vars pra novos contribuidores
  - Depende de `task.files` ser preenchido consistentemente (já é, via `parse_tasks` + FILE_PATH_RE)
- **Fit:** único caminho que reduz input cumulativo sem mudar auth ou quebrar contratos SpecKit

### Alternativa B: Migrar para `--bare` com `ANTHROPIC_API_KEY`

- **Pros:** isolamento total (sem hooks, sem CLAUDE.md, sem MCPs, sem user settings), mais agressivo
- **Cons:** exige billing API pay-as-you-go separado da subscription; contradiz ADR-010 que estabeleceu subscription como restrição firme
- **Rejeitada porque:** billing constraint é dealbreaker. Usuário reafirmou NO ANTHROPIC_API_KEY

### Alternativa C: Comprimir tasks.md em tabela estruturada

- **Pros:** reduziria ~25KB de user prompt por task
- **Cons:** quebra o contrato SpecKit (speckit.tasks emite o formato atual, outras skills consomem). Drift com upstream
- **Rejeitada porque:** ganho não compensa o custo de compatibilidade

### Alternativa D: Subagent delegation para leituras pesadas

- **Pros:** context isolation em sessões interativas
- **Cons:** subagents não funcionam dentro de `claude -p` headless dispatches
- **Rejeitada porque:** não aplicável ao easter

### Alternativa E: Regex-based sibling file skeletons

- **Pros:** reduziria ~10KB por task
- **Cons:** Python é flexível demais pra regex naive (multi-line signatures, decorators, nested defs, docstrings com quotes desbalanceadas). Risco de regressão alto
- **Rejeitada porque:** ganho pequeno, risco alto. Se algum dia revisitar, usar `ast.parse`/`ast.unparse`, não regex

## Consequencias

### Positivas

- **Input tokens por task cai ~30-50%** (empírico: -26.6% só em user prompt do epic 003, multiplicado pelo efeito de redução de turns do bare-lite)
- **Turns por dispatch caem via hook isolation** — simplify-reminder deixa de disparar quando `MADRUGA_STRICT_SETTINGS=1` (Phase 3)
- **Rollback trivial** por env var (`systemctl --user edit madruga-easter` drop-in sem redeploy)
- **Zero regressão em delivery quality** — suite de testes 930 passando, smoke tests byte-a-byte validados
- **Instrumentação permanente**: cada dispatch agora loga `prompt_composed` e `dispatch_cmd` com bytes por seção, facilitando debug futuro
- **Hook leak fechado**: sync_memory.py respeita `MADRUGA_DISPATCH`, eliminando Python subprocess + WAL contention em toda Write/Edit interna

### Negativas

- Quatro novos env vars no vocabulário do sistema (`MADRUGA_BARE_LITE`, `MADRUGA_KILL_IMPLEMENT_CONTEXT`, `MADRUGA_SCOPED_CONTEXT`, `MADRUGA_STRICT_SETTINGS`) — requer documentação em CLAUDE.md e runbook
- Heurística regex para gating de data-model/contracts pode ter falsos negativos em tasks de validação cross-cutting (mitigação: keyword "validation"/"schema" na description)
- Tasks sem US tag ou sem path claro caem no caminho default (incluem tudo) — comportamento conservador mas reduz o ganho

### Riscos

- **Regex gating** pode errar em casos edge. Mitigação: logs `prompt_composed` permitem auditar qualquer task específica. Se falsos negativos aparecerem, adicionar keywords ao regex (lista centralizada no topo do dag_executor.py)
- **`--tools` flag** vs `--allowedTools`: composição correta, mas mudanças futuras em `NODE_TOOLS` precisam lembrar de que `--tools` está hardcoded pra `IMPLEMENT_TASK_TOOLS` apenas em nodes implement. Testes `test_bare_lite_tools_flag_absent_for_judge` e `..._tech_research` protegem contra regressão
- **`--setting-sources project`** (Phase 3) pode esconder hooks/permissions que algum dispatch dependia. Por isso gated em opt-in; aplicar só após auditoria
- **Prompt caching invalidation** quando `--tools` muda entre nodes: aceito, cada node tem cache independente (já era assim)

## Phase 5 Addendum — Cache-Optimal Reorder (2026-04-11)

### Contexto adicional

Após a validação de Phases 0-4 em produção (`prosauai/004-router-mece`, live monitoring), inspecionando o campo `cache_creation.ephemeral_1h_input_tokens` no output JSON do `claude -p` descobrimos que o **Claude Code CLI usa prompt caching com TTL de 1 HORA** sob OAuth (não 5 minutos). Um ciclo L2 inteiro (~50 tasks × ~2min) cabe confortavelmente dentro de uma única janela de cache.

Porém, o `compose_task_prompt` original (Phases 0-4) colocava conteúdo task-específico (`header` com `task.id`, `recent_done`) no INÍCIO do user prompt. Como o cache da Anthropic é **prefix-based**, o primeiro byte diferente invalidava todo o cache hit. Estávamos pagando full price em ~44KB de `plan+spec` idêntico toda task.

### Decisão

Adicionar flag `MADRUGA_CACHE_ORDERED=1` (default on) que ativa uma segunda ordenação de seções no `compose_task_prompt`:

**Nova ordem sob `CACHE_ORDERED=1`:**
```
──── STABLE PREFIX (cacheável) ────
1. cue            — constante byte-idêntica `_CACHE_PREFIX_CUE` em dag_executor.py
2. plan.md
3. spec.md
4. data-model.md  — FORCE-INCLUDED (sem gating)
5. contracts/*.md — FORCE-INCLUDED (sem gating)

──── VARIABLE SUFFIX ────
6. tasks.md       — checkboxes flipam → suffix
7. recent_done
8. analyze-report (sliced per task)
9. file:* (inlined)
10. header        — task card LAST (leverage recency bias)
```

**Ordem legacy sob `CACHE_ORDERED=0`** (byte-idêntica ao pré-Phase-5) permanece como safety net.

### Decisão controversa: force-include `data_model` + `contracts`

A gating de Action 3a (só injetar se task tocar `models/`/`api/`) economiza ~12-20KB em tasks que não tocam — mas **fragmenta o prefixo**: T001 tem contracts, T003 não, prefixo diverge em byte ~44K, cache miss a partir dali.

**Math**: prefixo uniforme 64KB × 0.9 (cache_read cost) = 58KB economizados por task 2+ vs prefixo fragmentado 44KB × 0.9 = 40KB. **Net +18KB por task cacheada**. Amortizado sobre ~50 tasks do epic, a economia de prefixo uniforme supera o custo de re-incluir docs não-usadas.

Trade-off aceito. Legacy path preserva gating para rollback.

### Consequencias adicionais

#### Positivas (Phase 5)
- **Esperada redução adicional de -50% a -70%** em `tokens_in` cumulative para tasks 2..N (cache hit no prefixo de ~64KB). Combinado com Phases 0-4: projetada redução total ~80% vs baseline original de 2.6M/task
- **Cache metrics visíveis**: `parse_claude_output` agora expõe `cache_read` e `cache_create` como chaves separadas no dict retornado, permitindo validação empírica do cache hit rate
- **`prompt_composed` log inclui `cache_ordered=True|False`** — permite correlacionar a flag ao tamanho observado
- **Rollback byte-equal preservado** — teste `test_compose_task_prompt_cache_ordered_rollback_legacy_layout` garante que `MADRUGA_CACHE_ORDERED=0` restaura o comportamento pré-Phase-5 sem drift

#### Negativas (Phase 5)
- **Task card (`header`) no final do prompt** — quebra a convenção "instrução no topo", mitigada pelo `_CACHE_PREFIX_CUE` no byte 0 que sinaliza ao modelo que o task card está no final
- **~20KB de I/O de disco desperdiçado** por task não-touching (força a leitura de `data-model.md` + `contracts/*.md` mesmo quando irrelevantes). Custo: ~2ms por task na Linux page cache, negligível vs multi-second `claude -p`
- **Função `compose_task_prompt` cresceu para ~130 LOC** com as duas branches. Drift risk entre branches é o preço do rollback byte-equal — aceito

### Riscos adicionais (Phase 5)

- **Claude pode perder foco com header no final** — teoria de recency bias sugere o oposto, mas requer validação empírica. Mitigação: `_CACHE_PREFIX_CUE` no início + monitoramento manual das primeiras 5 dispatches pós-switch
- **`tasks.md` no suffix perde cache hit nessa seção** — aceito por design (mark_task_done flipa checkboxes). Prefix cache ainda cobre plan+spec+data_model+contracts
- **Resume path degrada graciosamente** — sem prefixo estável (plan/spec já na history da sessão), apenas `cue` + suffix. Teste `test_compose_task_prompt_cache_ordered_resume_no_prefix` cobre

### Tests adicionais (6 novos em test_dag_executor.py)

- `test_compose_task_prompt_cache_ordered_prefix_comes_first` — asserts plan before header
- `test_compose_task_prompt_cache_ordered_stable_prefix_byte_equal` — **invariante crítica**: prefixo byte-idêntico entre T001 (model task) e T999 (readme task)
- `test_compose_task_prompt_cache_ordered_rollback_legacy_layout` — rollback via `CACHE_ORDERED=0`
- `test_compose_task_prompt_cache_ordered_resume_no_prefix` — resume path consistente
- `test_compose_task_prompt_cache_ordered_missing_data_model` — degradação graciosa
- `test_compose_task_prompt_cache_ordered_log_field` — `prompt_composed` log inclui `cache_ordered=True`

### Rollback

Padrão idêntico às phases anteriores:
```ini
# ~/.config/systemd/user/madruga-easter.service.d/override.conf
[Service]
Environment=MADRUGA_CACHE_ORDERED=0
```
`systemctl --user restart madruga-easter`. Rollback em <10 segundos.

### Pendente (post-merge)

Validação empírica em ciclo L2 real: esperar `004-router-mece` terminar, ativar flag no próximo epic, medir `cache_read_input_tokens` trajectory. **Sinal de sucesso**: mediana de `cache_read` para T002+ ≥ 40,000 tokens e `tokens_in` mediana ≤ 350K (vs ~625K atual). Threshold de abort: se judge/qa failure rate subir 5% ou mais, rollback.

---

## Referencias

- Plan: `/home/gabrielhamu/.claude/plans/goofy-humming-mitten.md` (seções Phase 0-4 + Phase 5 addendum)
- Baseline empírico: `/tmp/madruga-token-baseline.json` (46 tasks do epic 003, 4.96MB agregado)
- Live monitoring de 004-router-mece com prompt_composed logs (media 78KB/task pre-Phase-5)
- [ADR-010: Claude -p Subprocess como Interface Programatica](./ADR-010-claude-p-subprocess.md)
- [Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-reference)
- [Anthropic Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- Tests:
  - `.specify/scripts/tests/test_dag_executor.py::test_bare_lite_*` (7 tests)
  - `.specify/scripts/tests/test_dag_executor.py::test_task_needs_*` (4 tests)
  - `.specify/scripts/tests/test_dag_executor.py::test_compose_task_prompt_*gated*` (4 tests)
  - `.specify/scripts/tests/test_dag_executor.py::test_*_rollback` / `*_legacy_*` (4 tests)
  - `.specify/scripts/tests/test_dag_executor.py::test_compose_task_prompt_cache_ordered_*` (6 tests — Phase 5)
