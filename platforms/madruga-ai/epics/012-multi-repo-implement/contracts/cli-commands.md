# CLI Contracts — Epic 012

## platform.py ensure-repo

```
Usage: platform.py ensure-repo <name>

Argumentos:
  name    Nome da plataforma (ex: prosauai)

Comportamento:
  1. Le repo.org e repo.name de platforms/<name>/platform.yaml
  2. Se self-ref (repo.name == "madruga.ai") → print path atual, exit 0
  3. Resolve path: {repos_base_dir}/{org}/{name}
  4. Se path existe com .git valido → git fetch --all --prune, exit 0
  5. Se path existe sem .git → remove dir, continua para clone
  6. Adquire lock ({path}.lock via fcntl.flock)
  7. Clone SSH: git clone git@github.com:{org}/{name}.git {path}
  8. Se SSH falha → Clone HTTPS: git clone https://github.com/{org}/{name}.git {path}
  9. Release lock

Exit codes:
  0  Sucesso (clonado ou atualizado)
  1  Erro (platform.yaml sem repo:, clone falhou, etc.)

Stdout:
  Path absoluto do repositorio (ultima linha)
```

## platform.py worktree

```
Usage: platform.py worktree <name> <epic-slug>

Argumentos:
  name        Nome da plataforma (ex: prosauai)
  epic-slug   Slug do epic (ex: 001-channel-pipeline)

Comportamento:
  1. Resolve repo path (via ensure-repo se necessario)
  2. Se self-ref → skip, print repo path atual
  3. Calcula worktree path: {repos_base_dir}/{name}-worktrees/{epic-slug}/
  4. Calcula branch: {epic_branch_prefix}{epic-slug}
  5. Se worktree ja existe → print path, exit 0 (crash recovery)
  6. git fetch origin (no repo principal)
  7. git worktree add {wt_path} -b {branch} origin/{base_branch}
     Se branch ja existe no remote: git worktree add {wt_path} {branch}

Exit codes:
  0  Sucesso (criado ou reutilizado)
  1  Erro

Stdout:
  Path absoluto do worktree (ultima linha)
```

## platform.py worktree-cleanup

```
Usage: platform.py worktree-cleanup <name> <epic-slug>

Comportamento:
  1. Resolve worktree path
  2. git worktree remove {wt_path}
  3. git branch -d {branch} (local only)
  4. Remove dir se sobrou

Exit codes:
  0  Sucesso
  1  Erro
```

## implement_remote.py

```
Usage: implement_remote.py --platform <name> --epic <NNN-slug> [--timeout <seconds>] [--dry-run]

Argumentos:
  --platform   Nome da plataforma
  --epic       Slug do epic
  --timeout    Timeout em segundos (default: MADRUGA_IMPLEMENT_TIMEOUT ou 1800)
  --dry-run    Mostra o prompt composto sem executar claude -p

Comportamento:
  1. ensure_repo(platform)
  2. create_worktree(platform, epic)
  3. Le artefatos: context.md, spec.md, plan.md, tasks.md
  4. Compoe prompt (concatena com headers)
  5. Se --dry-run → print prompt, exit 0
  6. Invoca: claude -p "{prompt}" --cwd {worktree_path}
  7. Captura stdout/stderr
  8. Reporta resultado

Exit codes:
  0  claude -p retornou 0
  1  Erro de setup (repo/worktree)
  2  claude -p retornou erro
  3  Timeout

Stdout:
  Output do claude -p
```
