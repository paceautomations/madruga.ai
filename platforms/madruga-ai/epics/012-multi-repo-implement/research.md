# Research — Epic 012: Multi-repo Implement

**Date**: 2026-03-31 | **Status**: Complete

## R1: Git Worktree via subprocess

**Decision**: Usar `git worktree add` via `subprocess.run()` (stdlib).

**Racional**: Git worktree e nativo, nao requer dependencia. Cria copia real do repo com branch independente. Overhead ~2-3s. Crash recovery: worktree sobrevive, pode ser reutilizado (`git worktree list` para detectar).

**Alternativas consideradas**:
- `git clone --branch` separado → duplica .git objects, mais lento, mais disco
- Symlinks → fragil, nao isola estado git
- Docker volume mount → over-engineering para single-operator CLI

**Comandos chave**:
```bash
# Criar worktree com nova branch
git worktree add <path> -b <branch> <base_branch>

# Criar worktree com branch existente
git worktree add <path> <existing_branch>

# Listar worktrees
git worktree list --porcelain

# Remover worktree
git worktree remove <path>

# Cleanup stale
git worktree prune
```

## R2: Clone SSH → HTTPS fallback

**Decision**: Tentar SSH primeiro (`git@github.com:{org}/{name}.git`), capturar returncode != 0, retry com HTTPS (`https://github.com/{org}/{name}.git`).

**Racional**: SSH e padrao para devs com chaves configuradas. HTTPS como fallback robusto (token auth ou public repos). Sem necessidade de detectar auth method antecipadamente — try/except e mais simples.

**Alternativas consideradas**:
- Apenas SSH → falha para quem nao tem chave configurada
- Apenas HTTPS → requer token explicitamente para repos privados
- `gh repo clone` → requer gh auth, adiciona dependencia implicita

## R3: Serializacao de operacoes concorrentes

**Decision**: `fcntl.flock()` (stdlib) em arquivo lock por repo (`{repo_path}.lock`).

**Racional**: Previne corrupcao se daemon (epic 016) tentar clonar o mesmo repo simultaneamente. `fcntl.flock()` e stdlib, funciona em Linux/macOS. Lockfile adjacente ao repo: `{repos_base_dir}/{org}/{name}.lock`.

**Alternativas consideradas**:
- `filelock` package → dependencia externa, viola NFR-001
- Sem lock → risco de clone concorrente corrompido (edge case baixo agora, real no daemon)
- PID file → mais complexo, precisa cleanup manual se crash

**Nota**: `fcntl` nao existe no Windows. Aceitavel — target e Linux/macOS (WSL conta como Linux).

## R4: Invocacao do claude -p

**Decision**: `subprocess.run(["claude", "-p", prompt, "--cwd", worktree_path], timeout=timeout)`.

**Racional**: `claude -p` aceita prompt via argumento e `--cwd` para working directory. O prompt contem os artefatos do epic (spec+plan+tasks concatenados). Timeout configuravel via `MADRUGA_IMPLEMENT_TIMEOUT` (default 1800s = 30min).

**Consideracoes**:
- Prompt pode ser grande (spec+plan+tasks = ~15-30KB tipicamente) — dentro do limite do shell
- Se exceder ARG_MAX (~2MB no Linux), usar `--stdin` para passar via pipe
- `claude -p` retorna stdout com resultado da implementacao
- Returncode 0 = sucesso, != 0 = falha

## R5: Integracao com platform.py (CLI)

**Decision**: Adicionar subcomandos `ensure-repo` e `worktree` em `platform.py`. Orquestrador `implement_remote.py` como script separado.

**Racional**: `platform.py` ja e o CLI central para operacoes de plataforma. `ensure-repo` e `worktree` sao operacoes atomicas que fazem sentido como subcomandos. `implement_remote.py` e orquestrador de nivel mais alto — script separado evita inchar o CLI.

**Alternativas consideradas**:
- Tudo em platform.py → incha o CLI com logica de orquestracao
- Tudo separado → perde a discoverability do CLI
- Makefile → menos flexivel, nao combina com o padrao Python do repo

## R6: Self-referencing detection

**Decision**: Reusar `resolve_repo_path()` do `db.py`. Ja detecta `repo_name == "madruga.ai"` e retorna `REPO_ROOT`. Para worktree: se self-ref, pular criacao de worktree e operar diretamente (comportamento atual).

**Racional**: Logica ja existe e esta testada. Nao duplicar.

## R7: Prompt composition strategy

**Decision**: Concatenar artefatos na ordem: context.md → spec.md → plan.md → tasks.md. Preceder cada um com header markdown (`## Context`, `## Spec`, etc.). Truncar context.md se total > 100KB (conforme spec edge case).

**Racional**: Ordem segue o fluxo natural de entendimento: contexto → o que → como → tarefas. tasks.md nunca truncado (mais actionable). context.md e o mais dispensavel.
