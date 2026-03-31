---
title: "Implementation Context — Epic 012"
updated: 2026-03-31
---
# Epic 012 — Multi-repo Implement — Implementation Context

## Captured Decisions

| # | Area | Decision | Referencia Arquitetural |
|---|------|---------|------------------------|
| 1 | Estrategia de isolamento | **Git worktree** para operacoes em repos externos. Cria worktree temporario, implementa la, cria PR via `gh`. Nao interfere no working tree do dev. | ADR-010 (claude -p cwd), general/src/git/worktree.py |
| 2 | Auto-clone | **ensure_repo()** clona automaticamente se repo nao existe (SSH first, fallback HTTPS). Fetch se ja existe. Per-repo lock para serializar. | general/src/git/worktree.py:53, platform.yaml repo binding |
| 3 | Repo binding | **platform.yaml** como source of truth: `repo.org`, `repo.name`, `repo.base_branch`, `repo.epic_branch_prefix`. Ja existe em fulano e madruga-ai. | domain-model (Platform entity), db.py resolve_repo_path() |
| 4 | Separacao docs/codigo | **Docs em madruga.ai, codigo em repo externo.** spec.md/plan.md/tasks.md ficam em `platforms/<name>/epics/NNN/`. Codigo vai para worktree do repo externo. | blueprint (filesystem-first), ADR-004 (file-based storage) |
| 5 | Implementacao | **Script wrapper** (~100-200 LOC Python) em `.specify/scripts/`. Faz ensure_repo → create_worktree → injeta contexto (spec/plan/tasks) → invoca `claude -p --cwd=worktree`. Skills SpecKit nao mudam. | ADR-010 (claude -p), general/src/phases/implement.py |
| 6 | PR creation | **`gh pr create`** com `cwd=worktree_path`. Push branch, cria PR no repo correto. Base branch vem de platform.yaml. | general/src/git/pr.py, blueprint (CI/CD) |
| 7 | Branch naming | **`epic/<platform>/<NNN-slug>`** no repo externo (configuravel via `repo.epic_branch_prefix`). Consistente com o padrao do madruga.ai. | platform.yaml, CLAUDE.md |

## Resolved Gray Areas

### 1. Como o claude -p no repo externo sabe o contexto do epic?

**Pergunta:** speckit.implement assume que spec/plan/tasks estao no CWD. No repo externo eles nao existem.

**Resposta:** O script wrapper le os artefatos de `platforms/<name>/epics/NNN/` (madruga.ai) e injeta como contexto no prompt do `claude -p`. O `claude -p` roda com `--cwd=worktree` (repo externo) mas recebe o conteudo dos docs como parte do prompt. Padrão identico ao `compose_*_prompt()` do SpeckitBridge no general.

**Racional:** Desacopla localidade dos docs da localidade do codigo. Docs sempre em madruga.ai (versionados, portal), codigo sempre no repo-alvo.

### 2. Worktree ou branch direto?

**Pergunta:** Duas opcoes para operar em repo externo.

**Resposta:** Worktree. Mesmo padrao do general.

**Racional:** Isolamento total (nao interfere em mudancas locais), crash recovery (worktree sobrevive), concorrencia futura (daemon pode ter N worktrees), overhead aceitavel (~2-3s criar).

### 3. Auto-clone: como saber org/repo/branch?

**Pergunta:** De onde vem as informacoes do repo externo?

**Resposta:** `platform.yaml > repo:` block. Ja existe:
```yaml
repo:
  org: paceautomations
  name: fulano-api
  base_branch: main
  epic_branch_prefix: "epic/fulano/"
```

**Racional:** Source of truth unico. `resolve_repo_path()` no db.py ja usa esses campos. `ensure_repo()` recebe org+name e resolve o path. Convention: `{repos_base_dir}/{org}/{repo_name}` (default: `~/repos/`).

### 4. Qual a relacao entre speckit.implement e o script wrapper?

**Pergunta:** speckit.implement e uma skill SpecKit generica. Como integra com multi-repo?

**Resposta:** Duas camadas:
1. **Interativo (humano invoca `/speckit.implement`):** A skill le tasks.md e implementa. Para multi-repo, o humano precisa estar no worktree correto ou usar o wrapper.
2. **Autonomo (daemon invoca):** O script wrapper (`implement-remote.py` ou similar) orquestra: ensure_repo → create_worktree → compoe prompt (spec+plan+tasks+context) → `claude -p --cwd=worktree -p "prompt"`. O `claude -p` executa a implementacao no repo externo.

O wrapper NAO modifica speckit.implement.md — ele compoe o prompt e delega.

### 5. Cleanup de worktrees

**Pergunta:** Quando e como limpar worktrees?

**Resposta:** Apos merge do PR. `cleanup_worktree()` remove o worktree e deleta a branch local. Mesmo padrao do general. Se crash antes do cleanup, o worktree sobrevive e e reusado na proxima execucao (crash recovery).

## Applicable Constraints

| Constraint | Fonte | Impacto no Epic |
|-----------|-------|-----------------|
| Zero deps novas | blueprint (stdlib-only) | Script wrapper usa stdlib Python + subprocess git/gh |
| claude -p max 3 concorrentes | ADR-010 | Semaforo no wrapper se daemon usar (futuro, epic 013) |
| SQLite WAL mode | ADR-012 | post_save.py ja funciona — gravar estado apos implement |
| Filesystem source of truth | ADR-004 | Docs em madruga.ai, codigo em repo externo |
| repos_base_dir convention | general/config.py, db.py | Default `~/repos/`, configuravel via local_config |

## Suggested Approach

### Entregaveis

1. **`ensure_repo.py`** (~80 LOC) — Clone/fetch de repos via subprocess git. SSH first, fallback HTTPS. Per-repo locking (filelock ou flock). Path: `.specify/scripts/ensure_repo.py`

2. **`worktree.py`** (~60 LOC) — Create/cleanup worktrees. Branch naming via platform.yaml. Crash recovery (reusa worktree existente). Path: `.specify/scripts/worktree.py`

3. **`implement_remote.py`** (~120 LOC) — Orquestrador: le platform.yaml → resolve repo → ensure_repo → create_worktree → le spec/plan/tasks de epics/ → compoe prompt → invoca `claude -p --cwd=worktree -p "prompt"`. Path: `.specify/scripts/implement_remote.py`

4. **`pr.py`** (~40 LOC) — Push branch + `gh pr create` com cwd=worktree. Path: `.specify/scripts/pr.py`

5. **Updates em `db.py`** — Garantir que `resolve_repo_path()` funciona end-to-end. Adicionar `repos_base_dir` em `local_config` se nao existir.

6. **Updates em `platform.py`** — Comando `platform.py clone <name>` para trigger manual de ensure_repo. `platform.py worktree <name> <epic>` para criar worktree manualmente.

7. **Testes** — pytest para ensure_repo (mock git), worktree (mock git), implement_remote (integration com temp dir).

### Sequencia

```
T1: ensure_repo.py + testes
T2: worktree.py + testes
T3: implement_remote.py (orquestrador)
T4: pr.py + integracao com worktree
T5: platform.py clone/worktree commands
T6: integration test end-to-end (fulano-api)
T7: post_save.py update + docs
```

### O que NAO esta no scope

- DAG executor / SpeckitBridge (epic 013)
- Telegram notifications (epic 014)
- Modificacoes em speckit.implement.md (skill permanece generica)
- Multi-tenant / auth (nao existe, single-operator)

---
handoff:
  from: epic-context
  to: speckit.specify
  context: "Decisoes de implementacao capturadas. Specify deve detalhar a spec com base neste contexto — worktree workflow, script wrapper, auto-clone, PR creation."
  blockers: []
  confidence: Alta
  kill_criteria: "Se claude -p nao suportar --cwd para repos externos, abordagem inteira precisa ser revista"
