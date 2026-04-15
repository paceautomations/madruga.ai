# Referência Completa de Comandos

## Platform Management

```bash
python3 .specify/scripts/platform_cli.py list                    # listar plataformas
python3 .specify/scripts/platform_cli.py new <name>              # scaffold nova plataforma (copier)
python3 .specify/scripts/platform_cli.py lint <name>             # validar estrutura
python3 .specify/scripts/platform_cli.py lint --all              # validar todas
python3 .specify/scripts/platform_cli.py sync                    # copier update todas
python3 .specify/scripts/platform_cli.py register <name>         # registrar plataforma + validar
python3 .specify/scripts/platform_cli.py import-adrs <name>      # importar ADRs markdown → DB
python3 .specify/scripts/platform_cli.py export-adrs <name>      # exportar decisions DB → markdown
python3 .specify/scripts/platform_cli.py import-memory           # importar .claude/memory/*.md → DB
python3 .specify/scripts/platform_cli.py export-memory           # exportar memory entries → markdown
python3 .specify/scripts/platform_cli.py use <name>              # definir plataforma ativa
python3 .specify/scripts/platform_cli.py current                 # mostrar plataforma ativa
python3 .specify/scripts/platform_cli.py status <name>           # pipeline status (tabela)
python3 .specify/scripts/platform_cli.py status --all --json     # todas plataformas (JSON)
```

## Portal

```bash
cd portal && npm install     # instalar deps (symlinks auto-managed por Vite plugin)
cd portal && npm run dev     # http://localhost:4321
cd portal && npm run build   # production build
```

## DAG Executor

```bash
python3 .specify/scripts/dag_executor.py --platform <name> --dry-run     # print execution order
python3 .specify/scripts/dag_executor.py --platform <name>                # executar L1
python3 .specify/scripts/dag_executor.py --platform <name> --epic <slug>  # executar L2 epic
python3 .specify/scripts/dag_executor.py --platform <name> --resume       # resume checkpoint
python3 .specify/scripts/platform_cli.py gate list <name>                     # listar gates pendentes
python3 .specify/scripts/platform_cli.py gate approve <run-id>                # aprovar gate
```

## Reverse-Reconcile (drift detection from external commits)

```bash
python3 .specify/scripts/reverse_reconcile_ingest.py --platform <name>                    # walks origin/<base_branch> from platform.yaml
python3 .specify/scripts/reverse_reconcile_ingest.py --platform <name> --dry-run --json   # preview without insert
python3 .specify/scripts/reverse_reconcile_ingest.py --platform <name> --branch <name>    # override base branch (debug only)
python3 .specify/scripts/reverse_reconcile_ingest.py --platform <name> --assume-reconciled-before <sha>  # backlog cutter

python3 .specify/scripts/reverse_reconcile_classify.py --platform <name> --out triage.json  # deterministic triage (noise/doc-self-edit/code)
python3 .specify/scripts/reverse_reconcile_aggregate.py --platform <name> --triage triage.json --out work.json  # per-file collapse, HEAD snippets
python3 .specify/scripts/reverse_reconcile_apply.py --patches patches.json                  # dry-run → .proposed files
python3 .specify/scripts/reverse_reconcile_apply.py --patches patches.json --commit         # write to target files

python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> --shas sha1,sha2          # mark specific SHAs reconciled
python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> --epic <epic-id>          # mark all commits of an epic
python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> --count-unreconciled --json  # count drift
```

## DB State (post-save)

```bash
python3 .specify/scripts/post_save.py --platform <name> --node <id> --skill <skill> --artifact <path>
python3 .specify/scripts/post_save.py --reseed --platform <name>   # re-seed plataforma
python3 .specify/scripts/post_save.py --reseed-all                 # re-seed todas
```

## Skill Management

```bash
python3 .specify/scripts/skill-lint.py                 # lint all skills
python3 .specify/scripts/skill-lint.py --skill <name>  # lint one skill
python3 .specify/scripts/skill-lint.py --json           # JSON output
```

## Make Targets

```bash
make test          # pytest
make lint          # lint all platforms
make ruff          # ruff check
make ruff-fix      # auto-fix ruff
make status        # pipeline status todas plataformas
make status-json   # export JSON para portal
make seed          # re-seed todas plataformas
make portal-dev    # portal dev server
make portal-build  # portal production build
make portal-install # instalar deps portal
```

## Prerequisite Check

```bash
.specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform <name>
```
