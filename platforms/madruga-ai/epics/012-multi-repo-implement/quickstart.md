# Quickstart — Epic 012: Multi-repo Implement

## Prerequisitos

- Python 3.11+, pyyaml
- Git com SSH key configurada (ou HTTPS disponivel)
- `gh` CLI instalado e autenticado (`gh auth status`)
- `claude` CLI instalado com subscription ativa

## Uso Rapido

### 1. Clonar repo externo

```bash
python3 .specify/scripts/platform.py ensure-repo fulano
# → ~/repos/paceautomations/fulano-api/
```

### 2. Criar worktree para um epic

```bash
python3 .specify/scripts/platform.py worktree fulano 001-channel-pipeline
# → ~/repos/fulano-api-worktrees/001-channel-pipeline/
# → branch: epic/fulano/001-channel-pipeline
```

### 3. Implementar remotamente

```bash
# Dry-run (mostra prompt sem executar)
python3 .specify/scripts/implement_remote.py --platform fulano --epic 001-channel-pipeline --dry-run

# Execucao real
python3 .specify/scripts/implement_remote.py --platform fulano --epic 001-channel-pipeline
```

### 4. Cleanup apos merge

```bash
python3 .specify/scripts/platform.py worktree-cleanup fulano 001-channel-pipeline
```

## Self-referencing (madruga-ai)

Para plataformas que operam no proprio repo, os comandos detect self-ref automaticamente:

```bash
python3 .specify/scripts/platform.py ensure-repo madruga-ai
# → /home/user/repos/paceautomations/madruga.ai/ (este repo)
# Sem clone, sem worktree — opera direto
```

## Variaveis de Ambiente

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `MADRUGA_IMPLEMENT_TIMEOUT` | 1800 | Timeout em segundos para claude -p |
