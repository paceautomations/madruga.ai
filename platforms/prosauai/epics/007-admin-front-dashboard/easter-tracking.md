# Easter Tracking — prosauai 007-admin-front-dashboard

Started: 2026-04-15T20:27:00Z

## Melhoria — madruga.ai

- **DirtyTreeError bloqueia por untracked noise (ensure_repo.py:199-211)**. `git status --porcelain` retorna qualquer arquivo untracked — inclusive lixo de ferramentas (`.claude/`, `.hypothesis/`, `.pytest_cache/`). Epic fica em loop de falha a cada 30s até humano intervir. Proposta: usar `--untracked-files=no` OU lista allow-list de untracked ignoráveis (configurável em platform.yaml). Evita paralizações por noise não-commitável.
- **Sem distinção entre tracked-modified e untracked**. Dirty tree com arquivos modificados tracked é risco real (perda de trabalho). Untracked é ruído. Mensagem de erro + comportamento deveriam diferenciar.
- **Retry backoff exponencial ausente para erros determinísticos**. DirtyTree é determinístico — retry a cada 30s por horas é puro desperdício de CPU e ruído no journal. Deveria escalar backoff ou pausar o epic auto-bloqueando (com notificação Telegram) em vez de log-spam.
- **`claude -p changed branch to 'main', reverted to 'epic/...'` logado como ERROR em todo node completion**. Observado após `specify` (17:30:05) e `clarify` (17:32:57). O dispatched claude está fazendo `git checkout main` apesar do `--disallowedTools Bash(git checkout:*)` — provavelmente via outro mecanismo (MCP tool? skill interno?). `dag_executor.py` reverte e loga como ERROR, mas o node completou. Dois problemas: (a) log level errado (não é erro — foi auto-corrigido); (b) causa raiz: por que o claude ainda troca de branch? Investigar se é hook/skill interno bypassando `--disallowedTools` ou se o disallow não cobre a rota usada.
- **Mesma seção de system prompt repetida em specify/clarify/plan** (27KB/23KB/18KB). Headers contract-base, conventions, uncertainty markers se repetem em todo dispatch da cadeia. Candidato a cache-optimal prefix já identificado em CLAUDE.md (`MADRUGA_CACHE_ORDERED=1`) — verificar se stable prefix está batendo no cache real (1h TTL) entre nodes da mesma epic, ou se há algo quebrando a ordem estável.
- **qa hit `error_max_turns` em 17min** — heal loop da qa (fix code → re-test → fix → re-test) esgotou turns default (~100). Proposta: (a) aumentar `--max-turns` específico p/ qa em epics com >20 arquivos alterados (análogo ao dynamic max-turns de phase dispatch); (b) instrumentar heal loop p/ parar após N iterations sem progresso em vez de esgotar turns; (c) separar `qa:tests` de `qa:review` em nodes distintos, reduzindo context e turns por dispatch.
- **Threshold de 10min para classificar `critical` é baixo demais para phase-based dispatch**. Phase com 10-15 tasks roda 15-25min tranquilo (max-turns=count×20+50). Pair-program precisa diagnosticar CPU/WCHAN antes de classificar como crítico — o heurístico puro de tempo gera falsos positivos. Proposta: threshold adaptativo baseado em `node_id` (`implement:phase-*` tolera até 30min se subprocess `Rl` + CPU crescendo) ou usar watermark de progresso via `pipeline_runs.output_lines`.

## Melhoria — prosauai

(nada ainda — epic acabou de iniciar; coletar durante os ticks)

## Incidents críticos

### Easter em loop por .claude/ untracked (2026-04-15 17:25–17:27)
- **Symptom:** `consecutive_errors=1, backoff_s=30` repetindo a cada 30s desde 17:25:38. Epic 007 não progredia.
- **Detection:** `journalctl --user -u madruga-easter` mostrou `DirtyTreeError: ?? .claude/` em 3 ticks consecutivos.
- **Root cause:** `ensure_repo._checkout_epic_branch` em [ensure_repo.py:199-211](.specify/scripts/ensure_repo.py#L199-L211) usa `git status --porcelain` sem filtrar untracked files. Diretório `~/repos/paceautomations/prosauai/.claude/` (criado pelo claude-code CLI com `scheduled_tasks.lock`) nunca seria commitado, mas quebrava checkout.
- **Fix:** commit `ed757f3` na branch `epic/prosauai/007-admin-front-dashboard` adicionando `.claude/` ao `.gitignore` do repo prosauai. Fix semântico (não hack): claude-code local state não pertence ao repo da aplicação.
- **Test:** verificação manual — `git status --porcelain` clean após commit → easter retomou no tick seguinte (17:27:43 → dispatch `specify` em 17:27:45).
- **Duration lost:** ~2min (3 ticks falhos) + tempo de diagnóstico (~5min).
- **Follow-up madruga.ai:** abrir improvement p/ `ensure_repo.py` tratar untracked separadamente.

### qa error_max_turns no primeiro attempt (2026-04-15 22:24)
- **Symptom:** journal log `Node 'qa' failed: claude_error[error_max_turns]` após 17min rodando.
- **Detection:** `journalctl --user -u madruga-easter` mostrou failure + auto `Retry 1/3 for node 'qa' after 10.2s`.
- **Root cause:** qa heal loop (fix code → re-run tests → fix again) esgotou `--max-turns` (default ~100). Epic com muitos arquivos alterados (monorepo split + migrations + auth + frontend) amplifica iterações.
- **Fix:** nenhum fix aplicado — retry automático 1/3 passou (`qa completed` em 6.5min na segunda tentativa), provavelmente porque parte do heal já foi feita no primeiro attempt.
- **Test:** N/A (auto-retry succeeded).
- **Duration lost:** ~17min (failed attempt) + ~10s backoff.
- **Follow-up madruga.ai:** max-turns dinâmico p/ qa (proporcional a arquivos alterados) ou split `qa:tests`/`qa:review`.

## Síntese (2026-04-15)

Epic `007-admin-front-dashboard` **shipped** em ~2h24min wall-clock (17:25 → 19:45 locais), 18 pipeline runs completados, 29 ticks de pair-program. 8 fases de implement (via phase-based dispatch) no lugar das 5 fases originais do pitch — tasks granularizados por speckit.tasks.

**Métricas:**
- Nodes dispatched: 18 (specify, clarify, plan, tasks, analyze, 8× implement:phase-N, analyze-post, judge, qa, reconcile, roadmap-reassess)
- Incidents críticos: 2
- Tempo perdido aprox: ~19min (2min DirtyTree + 17min qa failed attempt)
- Fixes commitados: 1 (`ed757f3` em prosauai)
- Testes adicionados por pair-program: 0 (implement phases adicionaram os seus)
- Nodes com duração > 10min: 4 (implement:phase-1 13m, implement:phase-6 10.5m, judge 14.3m, qa 6.5m retry + 17m falhado)

**Causas raiz agrupadas:**

1. **Ruído de ferramenta local bloqueando git state check** — `.claude/` dir do claude-code CLI em repo externo é untracked. `git status --porcelain` em [ensure_repo.py:199-211](.specify/scripts/ensure_repo.py#L199-L211) não discrimina noise de mudança real. Fix pontual: gitignore (commit `ed757f3`). Fix estrutural pendente: ensure_repo tolerar untracked noise via allow-list ou flag.

2. **`--max-turns` estático inadequado para heal loops de escopo variável** — qa com `--max-turns=100` esgota em epics grandes (heal fix→test→fix se estende). Retry passou por circunstância (parcial do heal já feito). Fix estrutural pendente: max-turns dinâmico ou split `qa` em sub-nodes.

**Melhorias consolidadas (madruga.ai):**

- `ensure_repo._checkout_epic_branch`: diferenciar tracked-modified de untracked noise; permitir allow-list em platform.yaml.
- Backoff exponencial para erros determinísticos (DirtyTree retry a cada 30s é desperdício + log-spam).
- `claude -p changed branch to 'main', reverted to epic/...` aparece como ERROR em todo node — auto-corrigido, não deveria ser ERROR; e investigar por que claude troca de branch apesar de `--disallowedTools Bash(git checkout:*)` (hook interno? MCP? skill?).
- System prompt 18-40KB repetido entre nodes — auditar hit real do prefix cache (1h TTL) com `MADRUGA_CACHE_ORDERED=1`.
- Threshold `running > 10min = critical` é heurístico demais para phase-dispatch e skills API-bound — usar CPU/WCHAN/output_lines watermark.
- `--max-turns` dinâmico p/ qa (proporcional a escopo) ou split em `qa:static`, `qa:tests`, `qa:review`.

**Melhorias — plataforma prosauai:** nenhuma observação bloqueante durante execução — spec→plan→tasks→implement passaram sem retry exceto incidente qa. Sinal de epic bem dimensionado pelo pitch + resolved gray areas sólidas.

**Próximo passo:** revisar diff de `epic/prosauai/007-admin-front-dashboard`, rodar `/madruga:ship` para push e PR para `develop`.
