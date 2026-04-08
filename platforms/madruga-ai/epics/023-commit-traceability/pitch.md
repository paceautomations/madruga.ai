---
title: "023 — Commit Traceability"
epic_id: 023-commit-traceability
platform: madruga-ai
status: shipped
created: 2026-04-08
updated: 2026-04-08
branch: epic/madruga-ai/023-commit-traceability
delivered_at: 2026-04-08
---
# Epic 023 — Commit Traceability

> Cada commit no repositorio deve estar vinculado a um epic ou marcado como ad-hoc. Visibilidade total de mudancas — passadas e futuras — no DB e no portal.

## Problema

Hoje o madruga.ai rastreia **execucao de skills** (artifact_provenance, pipeline_runs, traces) mas nao sabe **qual commit mudou o que**. Commits feitos fora do ciclo L2 (hotfixes, melhorias ad-hoc, ajustes diretos em main) sao completamente invisíveis no DB e no portal.

Consequencias:
1. **Sem rastreabilidade**: nao ha como responder "quais commits compuseram o epic 012?" sem rodar `git log` manualmente
2. **Commits ad-hoc perdidos**: melhorias feitas fora de epics (ex: pedir um ajuste no chat e commitar) nao aparecem em lugar nenhum da plataforma
3. **Portal incompleto**: dashboard mostra nodes e traces, mas nao mostra commits — a unidade fundamental de mudanca
4. **Reconcile limitado**: usa `git diff` em tempo real mas nao persiste historico de commits no DB

## Apetite

2 semanas. Escopo fechado: tabela `commits`, hook, backfill, aba no portal. Sem integracao com GitHub API (PR linking) — isso seria epic futuro.

## Solucao

### 1. Tabela `commits` no SQLite

Nova migration adicionando:

```sql
CREATE TABLE commits (
    id          INTEGER PRIMARY KEY,
    sha         TEXT NOT NULL UNIQUE,
    message     TEXT NOT NULL,
    author      TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    epic_id     TEXT,  -- NULL = ad-hoc; sem FK hard (epic pode nao existir no DB ainda)
    source      TEXT NOT NULL DEFAULT 'hook',  -- hook | backfill | manual
    committed_at TEXT NOT NULL,  -- ISO8601
    files_json  TEXT,  -- ["path1", "path2"]
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_commits_platform ON commits(platform_id);
CREATE INDEX idx_commits_epic ON commits(epic_id);
CREATE INDEX idx_commits_committed ON commits(committed_at);
```

Referencia: ADR-012 (SQLite WAL mode), padrao de migrations em db_core.py.

### 2. Git post-commit hook (Python)

Script Python invocado por `.git/hooks/post-commit`:

1. Le `git log -1 --format` do HEAD (sha, message, author, date, files)
2. **Identifica plataforma** (prioridade):
   - Branch match `epic/<platform>/<NNN>` → plataforma do branch
   - Senao: detecta `platforms/<X>/` nos arquivos tocados → plataforma X
   - Senao: plataforma `madruga-ai` (tudo que nao eh platform-specific pertence ao proprio madruga.ai)
3. **Identifica epic** (prioridade):
   - Branch match `epic/<platform>/<NNN-slug>` → epic NNN
   - Tag `[epic:NNN]` na mensagem de commit → epic NNN (override manual)
   - Senao: epic_id = NULL (ad-hoc)
4. **Commits multi-plataforma**: se toca `platforms/X/` E `platforms/Y/`, registra uma row por plataforma
5. Grava no SQLite via funcao em db_pipeline.py
6. Fallback: se hook falha, commit nao eh bloqueado (hook eh best-effort)

Referencia: padrao existente de hooks (hook_post_save.py, hook_skill_lint.py).

### 3. Backfill retroativo

Script `backfill_commits.py` que roda uma unica vez para popular o historico:

**Estrategia hibrida (merge history + first-parent):**
- Epic branches (merge commits): `git log main --merges` identifica merges de branches `epic/*`, depois `git log <merge>^..<merge>` lista commits de cada epic
- Commits diretos em main (first-parent): `git log --no-merges --first-parent main` → classificados como ad-hoc
- Commits pre-006 (5f62946..d6befe0): todos linkados ao epic `001-inicio-de-tudo`
- Plataforma: inferida por file path, fallback `madruga-ai`

Aceita re-execucao idempotente (INSERT OR IGNORE no sha UNIQUE).

### 4. Portal: aba "Changes" no control panel

Nova aba no control panel existente (ao lado de Execution e Observability):

- **Tabela de commits** com colunas: SHA (link GitHub), mensagem, plataforma, epic (ou "ad-hoc"), data
- **Filtros**: por plataforma, por epic, por tipo (epic/ad-hoc), por periodo
- **Stats**: total commits por epic, % ad-hoc vs epic
- **Dados**: via JSON export (mesmo padrao de pipeline-status.json)

Fase futura (nao neste epic): commits inline na view de cada epic.

### 5. Reseed como fallback

Estender `post_save.py --reseed` para incluir sync de commits via `git log`. Se o hook falhou ou commits foram feitos em outro ambiente, o reseed corrige.

## Rabbit Holes

- **GitHub API integration**: nao neste epic. Linkar commits a PRs seria natural mas adiciona dependencia externa e autenticacao. Candidato a epic futuro.
- **Commit-level diffs no portal**: mostrar `git diff` por commit no browser eh feature de GitHub, nao nossa. Link para GitHub basta.
- **Validacao de commit message**: enforcar conventional commits via commit-msg hook. Alta friccao, baixo valor — o agente Claude ja segue a convencao.
- **Webhook/cron approach**: descartado em favor de post-commit hook por ser mais simples e usar infra existente.

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Hook adiciona latencia ao commit | Hook eh Python (~200ms), aceitavel. Se problematico, mover para background |
| Hook falha silenciosamente | Reseed corrige; logs em stderr para debug |
| Backfill impreciso para commits antigos sem branch | Commits pre-006 vao para epic 001; pos-006 usa merge history — precisao ~95% |
| Commits squashados perdem granularidade | Registrar merge commit com referencia ao branch de origem |

## Criterios de Aceite

1. [ ] Tabela `commits` criada via migration
2. [ ] Funcoes CRUD em db_pipeline.py (insert_commit, get_commits_by_epic, get_commits_by_platform, get_adhoc_commits)
3. [ ] Post-commit hook instalavel (com instrucoes no README ou Makefile target)
4. [ ] Backfill script popula historico desde epic 001 ate HEAD
5. [ ] Epic 001 registrado no DB com seus 21 commits linkados
6. [ ] Portal: aba "Changes" no control panel com tabela + filtros
7. [ ] Reseed inclui sync de commits
8. [ ] Testes: hook logic, backfill idempotencia, DB queries, classificacao platform/epic

## Dependencias

- Epic 001 (Inicio de Tudo) — precisa existir no DB para linkar commits retroativos
- Epics 006-022 — ja shipped, branches/merges existem no git history

## Restricoes Arquiteturais

| Restricao | Origem | Impacto |
|-----------|--------|---------|
| SQLite WAL mode, busy_timeout=5000ms | ADR-012 | Hook deve ser rapido para nao bloquear writer |
| Python stdlib + pyyaml only | ADR-004 | Sem libs externas para git parsing (usar subprocess) |
| Portal consome JSON estatico | Blueprint | Exportar commits para JSON no reseed/post_save |
| Scripts < 300 LOC | CLAUDE.md | Hook + backfill devem ser enxutos |

## Captured Decisions

| # | Area | Decisao | Referencia Arquitetural |
|---|------|---------|----------------------|
| 1 | Persistencia | Estender BC Pipeline State (nao criar BC novo) | domain-model.md BC #2 |
| 2 | Naming | Tabela `commits` (nao `changes`) — acoplamento a git eh aceitavel | ADR-004 (git como VCS) |
| 3 | Hook | Python post-commit hook (nao shell) — consistencia com stack | ADR-004, blueprint |
| 4 | Backfill | Historico desde epic 001 (nao todo o git log pre-001) | Convencao de epic branches |
| 5 | Plataforma | Branch first, fallback file path, default madruga-ai | platform.yaml repo binding |
| 6 | Epic link | Branch pattern + tag `[epic:NNN]` override | Pipeline contract (branch guard) |
| 7 | Multi-plataforma | 1 row por plataforma afetada (aceitar duplicatas) | Pragmatismo > elegancia |
| 8 | Portal | Nova aba "Changes" no control panel (nao componente separado) | Blueprint deploy topology |
| 9 | Fallback | Hook best-effort + reseed como safety net | Padrao existente (post_save --reseed) |

## Resolved Gray Areas

**1. Onde vivem commits de infra (.claude/, portal/, .specify/)?**
Resposta: pertencem a plataforma `madruga-ai`. O repositorio EH a plataforma — nao existe categoria "infrastructure" separada. Regra: se nao toca `platforms/X/`, pertence a `madruga-ai`.

**2. Como lidar com commits multi-plataforma?**
Resposta: registrar 1 row por plataforma afetada, com flag implicito (mesmo sha aparece em multiplas plataformas). Duplicacao eh aceitavel — perda de informacao nao.

**3. Profundidade do backfill retroativo?**
Resposta: desde o primeiro commit (5f62946). Commits pre-006 (5f62946..d6befe0) vinculados ao epic `001-inicio-de-tudo`. Commits pos-006 usam merge history para identificar epics. Commits em main sem branch epic = ad-hoc.

**4. Hook bloqueia commit se falhar?**
Resposta: nao. Post-commit hook eh best-effort — se falha, commit ja foi feito. Reseed corrige inconsistencias. Stderr para debug.

**5. FK da tabela commits referencia epics.id diretamente?**
Resposta: nao usar FK hard. O campo `epic_id` eh TEXT sem constraint FK — porque epics podem ainda nao existir no DB quando o hook roda (ex: epic 001 retroativo). Validacao eh logica, nao structural.

## Applicable Constraints

| Restricao | Origem | Impacto neste epic |
|-----------|--------|--------------------|
| SQLite WAL mode, busy_timeout=5000ms | ADR-012 | Hook deve completar em <500ms para nao bloquear writer; INSERT unico por commit |
| Python stdlib + pyyaml only | ADR-004 | subprocess.run para git commands, json stdlib para files_json parsing |
| Portal consome JSON estatico | Blueprint (deploy topology) | Novo arquivo `commits-status.json` gerado no reseed, consumido pelo portal |
| Scripts < 300 LOC | CLAUDE.md | Hook ~150 LOC, backfill ~200 LOC, DB functions ~80 LOC (em db_pipeline.py) |
| Migrations incrementais | db_core.py padrao | Nova migration numerada sequencialmente (provavelmente 012 ou 013) |
| Post-commit hooks nao sao versionados pelo git | Git design | Precisa de `make install-hooks` ou similar para instalar; documentar no README |

## Suggested Approach

1. Migration + DB functions (dia 1-2)
2. Post-commit hook + testes (dia 3-4)
3. Backfill script + execucao retroativa (dia 5-6)
4. Portal aba Changes (dia 7-8)
5. Reseed integration + testes E2E (dia 9)
6. Judge + QA (dia 10)
