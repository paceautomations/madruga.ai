# Data Model — Epic 012: Multi-repo Implement

**Date**: 2026-03-31

## Entidades

### RepoBinding (existente em platform.yaml)

```yaml
repo:
  org: str          # GitHub org (ex: "paceautomations")
  name: str         # Repo name (ex: "fulano-api")
  base_branch: str  # Branch base (ex: "main")
  epic_branch_prefix: str  # Prefixo para branches de epic (ex: "epic/fulano/")
```

**Fonte**: `platforms/<name>/platform.yaml > repo:`
**Validacao**: `org` e `name` obrigatorios para plataformas com repo externo. `base_branch` default "main". `epic_branch_prefix` default "epic/{platform}/".

### RepoState (runtime, nao persistido)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| path | Path | Caminho local do repo (`{repos_base_dir}/{org}/{name}`) |
| exists | bool | Se o diretorio existe e tem `.git` valido |
| is_self_ref | bool | Se e o proprio repo madruga.ai |
| remote_url | str | URL usada para clone (SSH ou HTTPS) |

### WorktreeState (runtime, nao persistido)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| path | Path | Caminho do worktree (`{repos_base_dir}/{name}-worktrees/{epic_slug}/`) |
| branch | str | Nome da branch (`{epic_branch_prefix}{epic_slug}`) |
| exists | bool | Se o worktree ja existe |
| base_branch | str | Branch base para criar a nova branch |

### EpicArtifacts (leitura de filesystem)

| Artefato | Path | Obrigatorio |
|----------|------|-------------|
| context.md | `platforms/<name>/epics/<NNN>/context.md` | Nao |
| spec.md | `platforms/<name>/epics/<NNN>/spec.md` | Sim |
| plan.md | `platforms/<name>/epics/<NNN>/plan.md` | Sim |
| tasks.md | `platforms/<name>/epics/<NNN>/tasks.md` | Sim |

## Relacoes

```
Platform 1──1 RepoBinding (declarativo, platform.yaml)
Platform 1──* Epic (epics/NNN-slug/)
RepoBinding 1──1 RepoState (resolvido em runtime)
Epic 1──1 WorktreeState (criado sob demanda)
Epic 1──* EpicArtifacts (filesystem)
```

## Transicoes de Estado

### Repositorio
```
inexistente → clonado (ensure_repo, SSH)
inexistente → clonado (ensure_repo, HTTPS fallback)
clonado → atualizado (ensure_repo, git fetch)
parcial (.git invalido) → removido → clonado
```

### Worktree
```
inexistente → criado (worktree add -b branch base)
criado → em uso (claude -p executando)
em uso → concluido (implementacao terminada)
concluido → PR criado (push + gh pr create)
PR criado → limpo (worktree remove + branch delete)
crash → reutilizado (proximo run detecta e reusa)
```
