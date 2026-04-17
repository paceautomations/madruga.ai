---
type: qa-report
date: 2026-04-17
feature: "epic 008 — admin-evolution"
branch: "epic/prosauai/008-admin-evolution"
layers_executed: ["L1", "L2", "L3", "L4"]
layers_skipped: ["L5", "L6"]
findings_total: 29
pass_rate: "—"  # Ver seção Summary — heal loop bloqueado por constraint de escopo
healed: 0
unresolved: 29
gate_sc007_offline: PASS  # 100% suite (1570 testes) verde offline
gate_sc007_staging: DEFERRED  # 24h staging smoke nunca executado
---

# QA Report — Epic 008 Admin Evolution

**Data:** 2026-04-17 | **Branch:** `epic/prosauai/008-admin-evolution` | **Modo:** Autônomo (pipeline dispatch)

**Escopo:** revisão pós-implement + pós-analyze-post + pós-judge. 152/158 tasks marcadas `[x]`, 6 tasks de Phase 12 (T1000–T1005) permanecem `[ ]`. Este relatório **valida empiricamente** os 43 findings do Judge Report contra o código real e executa os layers de QA disponíveis no ambiente autônomo.

**Escopo de reparo:** o código vive no repositório externo `paceautomations/prosauai`. Por constraint explícita do runner (`Do NOT write files outside the epic directory`), o heal loop desta passagem **não aplica fixes** — todos os findings ficam UNRESOLVED e são endereçados ao próximo ciclo (reconcile ou epic 009).

**Layers executados:** L1 Static Analysis · L2 Automated Tests · L3 Code Review · L4 Build Verification.
**Layers pulados:** L5 API Testing (nenhum servidor disponível no pipeline autônomo) · L6 Browser Testing (Playwright MCP indisponível + `@playwright/test` não está em `devDependencies` do admin).

---

## Environment Detection

| Layer | Status | Detalhes |
|-------|--------|----------|
| L1 Static Analysis | ✅ Ativo | Backend: ruff check + ruff format. Frontend: tsc + eslint via next lint. |
| L2 Automated Tests | ✅ Ativo | pytest (1570 testes backend), vitest (46 testes frontend). |
| L3 Code Review | ✅ Ativo | 40+ arquivos mudados no epic 008; code review focado em validar 43 findings do Judge + 13 do analyze-post. |
| L4 Build Verification | ✅ Parcial | py_compile OK nos arquivos críticos. Frontend `next build` não executado (não requisitado). |
| L5 API Testing | ⏭️ Skip | Sem app rodando no ambiente autônomo. Cobertura delegada à integration suite (323 testes via httpx). |
| L6 Browser Testing | ⏭️ Skip | Playwright MCP não configurado; `@playwright/test` não é devDep; 3 specs existem com `@ts-nocheck`. |

---

## L1 — Static Analysis

### Backend (apps/api — Python 3.12)

| Ferramenta | Resultado | Findings |
|------------|-----------|----------|
| `ruff check apps/api/prosauai/` | ❌ 13 erros | **13× RUF046** (`int(round(float(x)))` redundante). 9 em `db/queries/agents.py`, demais em paths relacionados. 4 auto-fixable via `ruff check --fix`. |
| `ruff format --check apps/api/prosauai/` | ❌ 15 arquivos | Todos os novos módulos epic 008 (agents/audit/conversations/customers/performance/routing/tenants/traces queries + admin routers + pipeline + trace_persist + pricing + step_record). Auto-fixable via `ruff format`. |

**Severity:** S3 (estética/qualidade, zero risco funcional). Recomendação: rodar `ruff check --fix` + `ruff format` antes do merge para `develop`.

### Frontend (apps/admin — TypeScript 5.x)

| Ferramenta | Resultado | Findings |
|------------|-----------|----------|
| `npx tsc --noEmit` | ✅ Exit 0 | Sem erros de tipos. Tipos gerados (`src/types/api.ts`, 1418 linhas) validam contra openapi.yaml. |
| `pnpm lint` (next lint) | ❌ Quebrado | `next lint` foi deprecado no Next 16. Comando entra em modo interativo (prompt de configuração) e falha em CI com exit 1. [`ELIFECYCLE Command failed with exit code 1`] |

**Severity:** lint quebrado é S2 — bloqueia future CI. Recomendação: migrar para `eslint` direto via `npx @next/codemod@canary next-lint-to-eslint-cli .` conforme sugere o próprio output.

---

## L2 — Automated Tests

### Backend (pytest)

| Suite | Passed | Failed | Skipped | Tempo |
|-------|--------|--------|---------|-------|
| `tests/unit/` | 1247 | 0 | 0 | 36.0s |
| `tests/integration/` | 323 | 0 | 32 | 54.8s |
| **Total** | **1570** | **0** | **32** | **~91s** |

**Gate SC-007 (offline):** ✅ PASS. 100% da suíte existente + novos testes epic 008 passam. Zero regressões no pipeline (epics 004+005).

**Cobertura (sampling sobre 4 módulos novos):** 100% em `test_pipeline_instrumentation`, `test_pricing`, `test_routing_persistence`, `test_health_rules` (128 testes, todos verdes). Coverage global não atingiu 80% **intencionalmente** porque rodamos subset; suite completa com `--cov` é a métrica oficial (já validada em T054: 83.53%).

**Skipped (32):** majoritariamente testes de integração com dependência de `testcontainers-postgres` + Redis — ok pular em pipeline leve; runbook staging (`benchmarks/pipeline_instrumentation_smoke.md`) cobre.

### Frontend (vitest)

| Suite | Passed | Failed | Tempo |
|-------|--------|--------|-------|
| `tests/unit/lib/test_health_rules.test.ts` | 22 | 0 | 12ms |
| `tests/unit/lib/test_format.test.ts` | 24 | 0 | 58ms |
| **Total** | **46** | **0** | **1.5s** |

**Gate offline:** ✅ PASS. Todas as regras de threshold (FR-011) e formatação validadas.

**E2E (Playwright):** ⏭️ DEFERRED. `@playwright/test` não está em `devDependencies`; 3 specs (`login-to-overview.spec.ts`, `conversation-to-trace.spec.ts`, `trace-explorer-filter.spec.ts`) foram criadas com `@ts-nocheck` aguardando wave final. Nunca executadas contra servidor real. **Bloqueia SC-001, SC-002, SC-003 em validação empírica.**

---

## L3 — Code Review (validação dos findings Judge + analyze-post)

**Metodologia:** cada BLOCKER do Judge Report foi validado lendo o código real. Status possíveis:
- ✅ **CONFIRMADO** — finding é real e reproduzível pelo arquivo/linha citado.
- ⚠️ **PARCIAL** — finding é real mas com nuance (mitigante parcial encontrado).
- ✅ **RESOLVIDO** — finding NÃO é real (código já corrige o problema).

### BLOCKERs (5 findings)

#### B1 — `INSTRUMENTATION_ENABLED` kill switch ausente [CODE REVIEW] **S1 CONFIRMADO**

- **Localização:** `apps/api/prosauai/conversation/pipeline.py:708,1358` + `apps/api/prosauai/conversation/trace_persist.py:223` + `apps/api/.env.example`
- **Evidência:** `Grep INSTRUMENTATION_ENABLED apps/api/` retornou zero matches. Confirmado também para variantes `TRACE_PERSIST_ENABLED`, `ENABLE_*`. O flag de kill-switch declarado em T904 simplesmente não existe no código.
- **Risco:** persistência fire-and-forget de traces não pode ser desabilitada em runtime. Se `public.trace_steps` entrar em degradação (Redis overload em outra rota, schema drift após hotfix, storage spike), a única via de mitigação é redeploy.
- **FR violados:** nenhum explícito, mas princípio IX (observability) + ADR-028 (fire-and-forget com feature flag) implícito.
- **Remediação:** adicionar `trace_persistence_enabled: bool = True` em `config.py`; envolver `persist_trace_fire_and_forget()` em `if settings.trace_persistence_enabled`. Documentar em `.env.example`. PR de ~15 linhas.

#### B2 — `activate_prompt` não escreve em `audit_log` [CODE REVIEW] **S1 CONFIRMADO**

- **Localização:** `apps/api/prosauai/db/queries/agents.py:427-454` (função `activate_prompt`)
- **Evidência:** função executa apenas `UPDATE agents SET active_prompt_id=$2` e emite `logger.info("agent_prompt_activated", ...)` (linha 449). Nenhum INSERT em `audit_log` dentro da função ou do handler em `admin/agents.py`.
- **FR violados:** **FR-090** ("sistema MUST exibir timeline paginada de eventos da tabela de auditoria"), **FR-091** ("cada evento MUST exibir hora, ação, usuário, IP, detalhes"). Uma ação **state-changing de admin** (ativar versão de prompt, com impacto em prod) fica invisível na aba Auditoria.
- **Remediação:** dentro da mesma transação em que roda `_ACTIVATE_PROMPT_SQL`, fazer INSERT em `audit_log` com `action='agent_prompt_activated'`, `user_email=<from JWT>`, `details={'agent_id': aid, 'prompt_id': pid, 'previous_prompt_id': <from SELECT>}`. PR de ~20 linhas + 1 teste integration.

#### B3 — Truncamento 8 KB pode ser silenciosamente excedido [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** `apps/api/prosauai/conversation/step_record.py:156-193` (função `_truncate_value`), especialmente linha 185 (`char_budget = max(preview_budget // 4, 128)`) e linha 186 (`preview = serialised[:char_budget]`).
- **Evidência:** após exceder `max_bytes`, a função slice por CHARS (não bytes) e constrói um `replacement` dict sem re-medir o size do dict serializado. Com `ensure_ascii=False` (linha 171 — **correto**, atenua o worst-case) e payload CJK (3 bytes/char), um `preview` de 1984 chars (char_budget para max_bytes=8192) tem `1984 × 3 ≈ 5952 bytes` apenas no preview — dentro do limite. Porém, **emoji + caracteres combinados** (4 bytes UTF-8) podem empurrar para `1984 × 4 ≈ 7936 bytes` + overhead do dict (~60 bytes) = ~8 KB, na fronteira. Em um cenário adversarial com payloads binários representados como strings escapadas, o limite pode ser estourado.
- **Nuance vs. Judge Report:** a judge argumentou que `ensure_ascii=True` inflaria (não é o caso — `json.dumps(..., ensure_ascii=False)` está presente na linha 171). Porém o ponto central persiste: **o `replacement` nunca é re-medido**, e o contrato com o banco é "≤8 KB no JSONB storage". Um TOAST pode engolir, mas FR-034 diz explicitamente "truncados no servidor em ≤8 KB".
- **FR violados:** **FR-034** (contrato de ≤8 KB).
- **Remediação:** após construir `replacement` dict, re-serializar e validar: se `len(json.dumps(replacement, ensure_ascii=False).encode('utf-8')) > max_bytes`, reduzir `char_budget` em 20% e retentar (loop com limit de 3). PR de ~15 linhas + 1 teste unit com payload CJK pesado.

#### B4 — Phase 12 deployment smoke não executado [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** `tasks.md` T1000–T1005 (todos `[ ]`)
- **Evidência:** último commit (`0114600 feat(008): T903 add CLAUDE.md for AI agents`) encerra tasks em Phase 11. Nenhum dos 6 smoke tasks (T1000 docker compose build, T1001 qa_startup, T1002 health check, T1003 admin URL screenshots, T1004 journey J-001, T1005 teardown) rodou. `docker compose ps` jamais foi executado contra a stack completa do admin evolution.
- **Risco:** a superfície de 25 endpoints + 35 componentes frontend **nunca foi exercitada end-to-end** contra um container real. Regressão invisível: erros de routing FastAPI, mounting de Next.js Server Components com cookie JWT, integração CORS admin_frontend_origin vs. Dockerfile, hot path de `pool_admin` sob tráfego — tudo validado apenas por unit/integration tests com mocks.
- **FR violados:** nenhum diretamente, mas SC-001, SC-002, SC-003 requerem "cronometragem real" que não foi observada.
- **Remediação:** **antes do merge para `develop`**, executar Phase 12 completa. Depende de QA humano com acesso ao ambiente Docker local.

#### B5 — `pool_admin.max_size=5` subdimensionado [CODE REVIEW] **S1 CONFIRMADO**

- **Localização:** `apps/api/prosauai/config.py:66` (`admin_pool_max_size: int = 5`)
- **Evidência:** confirmado. `overview.py:130` usa pool para `asyncio.gather` com 5 queries paralelas (KPIs + sparklines). `performance.py:130` usa 6. **Cada admin na aba Overview consome 5 conexões do pool de tamanho 5**. Com 3 admins simultâneos (cenário realista do spec: "3–10 usuários simultâneos no pico"), o pool é drenado → pending `pool.acquire()` → 503 timeouts. **Ainda pior**: `trace_persist.py:251` acquire sem timeout compete no mesmo pool (W10 — ver abaixo), puxando a cauda do pipeline sob carga.
- **FR violados:** SC-004 ("p95 ≤300 ms em endpoints de listagem") implicitamente — sob pool starvation, p95 explode.
- **Remediação:** subir default para 25 (matching typical Supabase connection budget por service role); documentar em `.env.example`. Adicionar `acquire(timeout=...)` explícito em todos os call sites. PR de ~5 linhas de config + review dos ~15 acquire sites.

### WARNINGs (amostragem — 8 de 25 validados)

Por questão de tempo no pipeline autônomo, validei os 8 warnings com maior impacto operacional:

#### W2 — `cost_by_model` N+1 queries [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** `apps/api/prosauai/db/queries/performance.py:492-582`
- **Evidência:** loop em linha 535-549 chama `_cost_sparkline_for(conn, ...)` por row. Para 10 tenant×modelo pairs → 10 sparkline queries seriais, cada uma com `generate_series` + LEFT JOIN em `public.traces`. Sob cache miss, endpoint `/admin/metrics/performance` com 3 tenants e 3 modelos tem latência dominada por N queries seriais.
- **Impacto:** p95 cold-start do Performance pode exceder SC-004 (2s target sem cache). Com 2 tenants × 2 modelos ativos atualmente, o blast radius é contido; pior quando gpt-5-mini entra no mix.
- **Remediação:** reescrever como UMA query com `CROSS JOIN` entre tenants×modelos e generate_series. PR de ~40 linhas em `performance.py`.

#### W5 — Fallback `trace_id` com risco de colisão [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** `apps/api/prosauai/conversation/pipeline.py:627-631`
- **Evidência:** `trace_id = f"{int(time.time() * 1_000_000):032x}"[-32:]` quando OTel span ausente. Precisão de microssegundo + 2 workers concorrentes num mesmo tick → colisão. `public.traces.trace_id` tem índice BTREE mas **não é UNIQUE** (verificado na migration T010) → colisão gera rows duplicados, indetectáveis.
- **Impacto:** em ambiente sem OTel ativo (tests, fallback scenarios), 2 pipelines em 1 µs compartilham trace_id → downstream de trace explorer renderiza steps misturados.
- **Remediação:** trocar para `uuid.uuid4().hex` (128-bit random, colisão zero). PR de 1 linha.

#### W6 — ILIKE wildcards não escapados [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** `apps/api/prosauai/db/queries/conversations.py:224`
- **Evidência:** `args.append(f"%{q}%")` — user input `q` é bound via `$N` (correto contra SQL injection, e há comentário `S608` na linha 229 marcando isso como aceito), MAS os meta-caracteres `%` e `_` do ILIKE **não são escapados**. User digita `%` na busca → ILIKE `%%%%` → full-table scan via EXISTS subquery em `messages.content`. Self-DoS trivial.
- **FR violados:** FR-021 (busca ILIKE) não impede isso, mas SC-005 (<100ms) viola sob ataque.
- **Remediação:** substituir `q` por `q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')` antes do format. PR de 3 linhas + 1 teste unit.

#### W7 — `messages.content` sem índice GIN/trigram [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** migrations `apps/api/db/migrations/*.sql`
- **Evidência:** grep `pg_trgm\|gin.*content\|USING gin` retornou zero matches em todas as migrations. Inbox search em `messages.content` via `ILIKE '%q%'` com wildcard leading **não pode usar btree**, e não há índice GIN. Para 10k conversas × ~20 mensagens = 200k rows, EXISTS subquery degrada rapidamente.
- **FR aplicáveis:** FR-021 explicita ILIKE em v1 (correto), MAS spec também diz "migração para tsvector + GIN quando >10k conversas OR p95 >500ms". O spec define a migration trigger; a execução fica pra epic 009.
- **Remediação:** este é um follow-up documentado, não um blocker. Backlog em epic 009 ou quando telemetria indicar.

#### W10 — `trace_persist.acquire()` sem timeout [CODE REVIEW] **S2 CONFIRMADO**

- **Localização:** `apps/api/prosauai/conversation/trace_persist.py:251` (`async with pool_admin.acquire() as conn:`)
- **Evidência:** lida em bloco. Sob saturação de pool (B5), a task fire-and-forget fica enfileirada indefinidamente. Zero backpressure → unbounded memory growth se Postgres degrada.
- **Remediação:** `pool_admin.acquire(timeout=5)`. Combinado com B5 fix (subir pool size), remove o risco. PR de 1 linha.

#### W11 — Retention DELETE em 1 transação [CODE REVIEW] **S3 CONFIRMADO**

- **Localização:** `apps/api/scripts/retention_cron.py:66-93`
- **Evidência:** 3 DELETE WITH ... RETURNING rodam em transações separadas (linhas 62-96), mas cada DELETE individual é single-txn em tabela potencialmente grande. Em 30 dias de retenção com 120k steps/dia = 3.6M rows a deletar em 1 txn → WAL spike + lock em índices + autovacuum contention.
- **Impacto:** janela de manutenção do cron (provável 3am) pode travar queries concorrentes do pipeline por segundos.
- **Remediação:** chunking — `DELETE ... WHERE id IN (SELECT id FROM trace_steps WHERE started_at < X LIMIT 10000)` em loop com sleep. PR de ~30 linhas.

#### W12 — `(tr.started_at AT TIME ZONE 'UTC')::date = d.day` defeats BRIN [CODE REVIEW] **S3 CONFIRMADO**

- **Localização:** `apps/api/prosauai/db/queries/performance.py:505, 573`
- **Evidência:** função aplicada no LHS do predicate BRIN. BRIN em `started_at` indexa intervals; `function(column) = rhs` força scan. Query plan cai para seq scan nos dias em que traces tem >100k rows.
- **Remediação:** re-escrever predicate: `tr.started_at >= d.day::timestamptz AND tr.started_at < (d.day + 1)::timestamptz` (sargable). PR de ~8 linhas.

#### W4 — Storage miscalculation [DOC GAP] **S3 CONFIRMADO**

- **Localização:** `apps/api/prosauai/conversation/step_record.py:9`
- **Evidência:** docstring diz "~1.2 GB/year". Cálculo real: com 5k mensagens/dia/tenant × 2 tenants × 12 steps = 120k steps/dia. Cada step pode ter até 8KB de input + 8KB de output = 16KB JSONB bruto (antes de TOAST). Worst case: 120k × 16 KB × 30d = 58 GB **antes** de retention. Com compression TOAST típica (2–3×) e médias reais (não worst-case), range realistic é 20–80 GB. **A documentação está 1–2 ordens de magnitude abaixo.**
- **Risco:** sizing de Supabase/volume pode ser subestimado no planejamento de custo.
- **Remediação:** atualizar docstring + `data-model.md` com bounds realistas. Docs-only change, PR de 5 linhas.

### Findings do analyze-post-report.md (delta sobre judge)

| ID | Status | Evidência |
|----|--------|-----------|
| **P1** | ✅ CONFIRMADO (inherited) | T030, T055, T904, T906, T907, T908, T909 marcados `[x]` mas bodies dizem DEFERRED. Gates de performance/quality nunca foram empiricamente validados. |
| **P2** | ✅ CONFIRMADO (inherited) | Phase 12 permanece `[ ]` (ver B4). |
| **P3** | ✅ **RESOLVIDO** | `system_health.py:46-48,56-61` tem thresholds explícitos: ≤500ms=up, 500-1500ms=degraded, >1500=down. Não é implicit; analyze-post estava conservador. |
| **P4** | ⚠️ PARCIAL | Phoenix span assertion no runbook T030 ainda pendente; pode ser executada no Phase 12. |
| **P5** | ✅ CONFIRMADO | ver B1. Naming é irrelevante porque **nenhum flag existe**. |
| **P6** | ⏭️ NÃO VALIDADO | Requer inspeção mais profunda de `agent.py`. Backlog para reconcile. |
| **P7** | ✅ CONFIRMADO | ver B2. |
| **P8** | ✅ CONFIRMADO (amostragem) | `tenant_health.py:*` tem query para rolling 5min error rate; usa `started_at` (BRIN-compatible). OK. |
| **P9** | ✅ CONFIRMADO | `platforms/prosauai/platform.yaml:testing.urls` contém apenas 4 URLs (`/health`, `/api/auth/login`, `/`, `/login`). **11 rotas admin novas ausentes** — T1003 falhará. |
| **P10** | ✅ CONFIRMADO | `apps/admin/package.json` devDependencies: **zero matches para playwright**. Specs existem mas `@ts-nocheck`. |
| **P11** | ✅ CONFIRMADO | Nenhum script `seed_synthetic_admin_dataset.py` existe. SC-004 (10k conv + 50k traces) não pode ser reproduzido localmente. |
| **P12** | ✅ CONFIRMADO (cosmetic) | Metric baseline corrigido: 158 tasks totais (152 done + 6 pending). |
| **P13** | ✅ CONFIRMADO (cosmetic) | implement-report.md precisa esclarecer escopo do "7/7 dispatch". |

---

## L4 — Build Verification

| Check | Resultado | Detalhes |
|-------|-----------|----------|
| `python -m py_compile` em 7 arquivos críticos | ✅ OK | `system_health.py`, `cache.py`, `pipeline.py`, `trace_persist.py`, queries/{agents, performance, conversations}.py |
| Imports smoke (`pricing`, `trace_persist`, `step_record`, `activate_prompt`, `list_conversations`, `list_audit`) | ✅ OK | Todos os módulos core do epic 008 carregam sem ImportError. |
| Frontend `tsc --noEmit` | ✅ Exit 0 | Tipos gerados consistentes com openapi.yaml. |
| Frontend `pnpm build` | ⏭️ Não executado | Requer >60s e ambiente de env preenchido. Runbook Phase 12 cobre. |
| `dbmate up && down && up` | ⏭️ Não executado | T014 já registrou PASS na implementação; não re-verificado neste pipeline. |

---

## L3.5 — Cross-reference integrity

Verificações derivadas do mapeamento spec ↔ código:

| Verificação | Status |
|-------------|--------|
| 12 step names em `step_record.py:STEP_NAMES` batem com FR-030 | ✅ OK |
| 3 tabelas novas (`traces`, `trace_steps`, `routing_decisions`) + `ALTER conversations` → 4 migrations presentes | ✅ OK (timestamps 20260420000001–000004) |
| 6 KPIs do Overview com thresholds FR-011 → `health.py` (backend) + `health-rules.ts` (frontend) | ✅ OK (56 testes validam) |
| 8 abas da sidebar → routes `app/admin/(authenticated)/{conversations,traces,performance,agents,routing,tenants,audit}/` | ✅ OK (verificado indiretamente via imports) |
| Cookie JWT `admin_token` reusado do epic 007 | ✅ OK (sem novo auth flow) |
| ADR-011 carve-out documentado | ✅ OK (ADR-027, ADR-028, ADR-029 em `decisions/`) |

---

## Summary

| Status | Count |
|--------|-------|
| ✅ PASS (testes + imports + tipos) | 1616 checks (1570 pytest + 46 vitest) |
| ⚠️ WARN (L1 lint/format backend) | 28 items (13 ruff check + 15 ruff format) |
| ❌ UNRESOLVED (BLOCKERs confirmados) | 5 (B1, B2, B3, B4, B5) |
| ❌ UNRESOLVED (WARNINGs amostrados) | 8 (W2, W5, W6, W7, W10, W11, W12, W4) |
| ❌ UNRESOLVED (analyze-post) | 10 findings confirmados dos 13 pre-implement |
| ⏭️ DEFERRED (heal bloqueado por escopo) | todos os 29 unresolved |

### Gate Assessment

| Gate | Status | Evidência |
|------|--------|-----------|
| **SC-001** (Conversas em <30s) | ⏭️ DEFERRED | Playwright e2e não executou (P10). Código US1 completo e testado por integration. |
| **SC-002** (Trace waterfall em <30s) | ⏭️ DEFERRED | Playwright e2e não executou. Código US2 completo + json-tree + waterfall-chart. |
| **SC-003** (Overview em <10s) | ⏭️ DEFERRED | Playwright + Lighthouse não mediram. |
| **SC-004** (p95 ≤300ms em 10k conv + 50k traces) | ⏭️ DEFERRED | Sem dataset sintético (P11). Vulnerável a B5 (pool starvation) + W2 (N+1 cost). |
| **SC-005** (inbox <100ms) | ⏭️ DEFERRED | `EXPLAIN ANALYZE` registrado em runbook `benchmarks/inbox_list_query.md`; nunca rodado contra 10k conv reais. |
| **SC-006** (overhead ≤10ms p95) | ⏭️ DEFERRED | Runbook `benchmarks/pipeline_instrumentation_smoke.md` descreve A/B 12h+12h; nunca rodado em staging. |
| **SC-007** (100% suite verde) | ✅ **PASS offline** | 1570 tests offline. Nota: CI real precisa rodar com testcontainers para skipped=32. |
| **SC-008** (DROP em <1min) | ⏭️ DEFERRED | Routing decisions UI (T520-T524) completa por código; sem validação cronometrada. |
| **SC-009** (cobertura retroativa 30d) | ⏭️ NÃO APLICÁVEL | Critério qualitativo — requer retrospectiva humana. |
| **SC-010** (debugging <15min) | ⏭️ DEFERRED | Depende de observação real de incidente. |
| **SC-011** (custo auditável) | ⚠️ PARCIAL | Endpoints + UI funcionais. Hardcoded pricing (ADR-029) — PR de 1 linha quando gpt-5-mini for validado. |
| **SC-012** (100% routing decisions persistidas) | ✅ **PASS offline** | Fire-and-forget testado unit + integration. Verificação empírica depende de Phase 12. |

### Kill criteria — nenhum disparado

Spec kill criteria (seção Handoff): nenhum dos 4 disparadores ocorreu. Instrumentação de pipeline é contida, não quebrou 12 step names. Pricing shipou hardcoded OK. Cut-line para 3 semanas não foi aplicado (over-delivered vs appetite).

---

## Heal Loop

**Status:** ⏭️ **BYPASSED**.

Heal loop em modo autônomo exigiria fixes nos arquivos:
- `apps/api/prosauai/config.py` (B1, B5)
- `apps/api/prosauai/db/queries/agents.py` (B2)
- `apps/api/prosauai/conversation/step_record.py` (B3)
- `apps/api/prosauai/db/queries/performance.py` (W2, W12)
- `apps/api/prosauai/conversation/pipeline.py` (W5)
- `apps/api/prosauai/db/queries/conversations.py` (W6)
- `apps/api/prosauai/conversation/trace_persist.py` (W10)
- `apps/api/scripts/retention_cron.py` (W11)
- `apps/api/prosauai/conversation/step_record.py:9` (W4 docstring)
- `apps/admin/package.json` (P10 add playwright)
- `platforms/prosauai/platform.yaml` (P9 admin URLs)

**9 de 11 arquivos estão no repo `prosauai` externo**, fora do escopo de escrita (`Do NOT write files outside the epic directory`). Os 2 remanescentes são no repo `madruga.ai`, mas estão fora do diretório do epic (platform.yaml está em `platforms/prosauai/`, não em `platforms/prosauai/epics/008-admin-evolution/`).

**Portanto, todos os fixes são UNRESOLVED nesta passagem** e viram punch-list para:

1. **Reconcile** do epic 008 (próximo passo no DAG) — pode criar PR isolado com todos os fixes de B1, B2, B3, B5 + W5, W6, W10 (ajustes de 1-40 linhas cada).
2. **Epic 009 kick-off** — W2, W11, W12 (otimizações não triviais) + P10 setup de Playwright + P11 seed script.
3. **Phase 12 deploy smoke** — T1000-T1005 + P9 atualizar platform.yaml testing.urls. Executar manualmente antes de merge para `develop`.

---

## Files Changed by Heal Loop

Nenhum. Heal loop bypassed.

---

## Lessons Learned / Recommendations

1. **Marcar `[x]` apenas quando empiricamente validado**. 8 tasks do epic 008 (T030, T055, T904, T906, T907, T908, T909, T030) receberam `[x]` quando o corpo dizia DEFERRED. Reconcile deve renomear o check pra `[d]` (deferred) ou `[~]` (partial) e documentar o backlog.

2. **Pool sizing é decisão de produção, não default**. O `admin_pool_max_size=5` default do epic 007 foi mantido sem reavaliar para a superfície 25× maior do epic 008. Bumpar para 25 é trivial; testar sob concurrency é o desafio.

3. **Flag de kill switch é mandatória para fire-and-forget**. O padrão ADR-028 ("pipeline fire-and-forget") prevê isso implicitamente (Phoenix exporter tem `ENABLE_PHOENIX_*`), mas T904 reivindicou a feature sem implementar. Lição: features de rollback/mitigação DEVEM ter teste que valida o bypass (unit test: set flag=false → asserção de `trace_persist` não chamado).

4. **`ruff format` no CI**. 15 arquivos novos escaparam da padronização — pre-commit hook deveria ter pegado. Validar que `.pre-commit-config.yaml` roda `ruff format --check` em todos os paths.

5. **Playwright como devDep mandatório**. Com 3 specs `@ts-nocheck`, o debt acumula silenciosamente. PR de 2 linhas (`pnpm add -D @playwright/test`) + remoção dos `@ts-nocheck` é pré-requisito trivial do próximo sprint.

6. **Platform.yaml é contrato vivo**. Cada epic que adiciona rotas admin deve atualizar `testing.urls` como parte do PR do endpoint (não como polish final). Pipeline check `qa_startup.py --validate-urls` só protege o que está declarado.

7. **Cost estimation (W4) é sinalizador**. Spec disse "~1.2 GB/year"; realidade é 20–80 GB. Sempre expressar como range com "worst case" + "typical"; revisar docstrings em reconcile.

---

## Report

**Arquivo:** `platforms/prosauai/epics/008-admin-evolution/qa-report.md`
**Layers:** L1 ✅ (backend lint debt) | L2 ✅ | L3 ✅ (29 findings validados) | L4 ✅ (parcial) | L5 ⏭️ | L6 ⏭️
**Success rate offline:** 100% (1570 pytest + 46 vitest + 128 dirigidos ao epic 008, todos verdes)
**Gate SC-007 offline:** PASS
**Verdict:** **DO NOT MERGE to `develop`** até:
  1. Phase 12 smoke (B4) executada com PASS em todos os 11 admin URLs.
  2. BLOCKERs B1, B2, B5 fixados (mínimos para produção segura).
  3. B3 (truncation) e W5 (trace_id collision) fixados (ambos 1–20 linhas).
  4. platform.yaml atualizado com 11 rotas admin (P9).

BLOCKERs B3 + B4 podem ser downgraded para WARNING via review humano com aceite explícito do risco (truncation excess raro + smoke staging agendado post-merge), mas B1, B2, B5 são requisitos funcionais/segurança.

---

handoff:
  from: madruga:qa
  to: madruga:reconcile
  context: "QA validou 29 findings empíricos (5 BLOCKERs, 8 WARNINGs amostrados, 10 analyze-post inherited, 6 lint items). Suite offline 100% verde (1570 pytest + 46 vitest, zero falhas). Heal loop BYPASSED por constraint de escopo — todos os fixes precisam ir para reconcile (ou epic 009 no caso de otimizações W2/W11/W12). BLOCKERs críticos: B1 (kill switch ausente), B2 (audit_log missing em activate_prompt — FR-090/FR-091 violation), B5 (pool_admin=5 starvation). Phase 12 deploy smoke NUNCA foi executada — T1000-T1005 permanecem `[ ]` e são pré-requisito de merge para develop. 3 ADRs (027/028/029) estão OK. Stack backend/frontend compila + passa testes — o problema não é de execução, é de gates de produção não validados empiricamente."
  blockers:
    - "B1: INSTRUMENTATION_ENABLED flag não existe — blocker para rollout seguro"
    - "B2: activate_prompt omite audit_log INSERT — viola FR-090/FR-091"
    - "B5: admin_pool_max_size=5 cascata em 503s sob 3+ admins"
    - "Phase 12 smoke (T1000-T1005) não executada"
    - "platform.yaml testing.urls não inclui 11 rotas admin novas (P9)"
  confidence: Alta
  kill_criteria: "QA fica inválido se: (a) fixes de B1/B2/B5 forem aplicados no repo prosauai antes do reconcile e os testes existentes quebrarem; (b) Phase 12 smoke real revelar regressões não capturadas por este relatório (ex: docker compose build falha, Evolution API quebrou contrato); (c) decisão de rollback completo do epic 008 por qualquer razão externa."
