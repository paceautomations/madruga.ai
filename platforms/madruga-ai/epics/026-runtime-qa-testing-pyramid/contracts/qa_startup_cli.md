# Contrato CLI: qa_startup.py

**Localização**: `.specify/scripts/qa_startup.py`  
**Consumidores**: skill `madruga/qa.md` (invocação via Bash), scripts de CI, developers locais

---

## Interface CLI

```
qa_startup.py --platform <name> [--cwd <path>] [--json] <operation>

Arguments:
  --platform NAME    Nome da plataforma (localiza platform.yaml em REPO_ROOT/platforms/NAME/)
  --cwd PATH         Diretório de trabalho para comandos de startup (default: cwd atual)
  --json             Saída JSON em stdout; logs de progresso vão para stderr

Operations (mutual exclusive, exceto --full):
  --parse-config     Lê e valida o bloco testing: do platform.yaml; exit 0 se válido
  --start            Inicia serviços e aguarda health checks
  --validate-env     Compara required_env vs .env real; emite BLOCKER se vars ausentes
  --validate-urls    Valida reachability de todas as URLs em testing.urls
  --full             Sequência: --start → --validate-env → --validate-urls
```

## Exit Codes

| Code | Significado |
|------|-------------|
| 0 | OK — status ok ou warn |
| 1 | BLOCKER encontrado |
| 2 | Erro de configuração (platform.yaml inválido, testing: ausente) |
| 3 | Erro inesperado (exception não capturada) |

## Contratos de Saída JSON

Todos os outputs seguem o schema `StartupResult` definido em `data-model.md`.  
**Invariante de segurança**: `env_present` e `env_missing` contêm **apenas nomes de variáveis (keys)**, nunca valores.

### Exemplo: `--start` bem-sucedido

```json
{
  "status": "ok",
  "findings": [],
  "health_checks": [
    {"label": "API Backend", "url": "http://localhost:8050/health", "status": "ok", "detail": ""},
    {"label": "Admin Frontend", "url": "http://localhost:3000", "status": "ok", "detail": ""}
  ],
  "env_missing": [],
  "env_present": [],
  "urls": [],
  "skipped_startup": false
}
```

### Exemplo: `--start` com BLOCKER (health check timeout)

```json
{
  "status": "blocker",
  "findings": [
    {
      "level": "BLOCKER",
      "message": "Health check 'API Backend' falhou após 120s",
      "detail": "http://localhost:8050/health → ConnectionRefusedError. Logs: [ultimas 50 linhas de docker compose logs]"
    }
  ],
  "health_checks": [
    {"label": "API Backend", "url": "http://localhost:8050/health", "status": "timeout", "detail": "ConnectionRefusedError"},
    {"label": "Admin Frontend", "url": "http://localhost:3000", "status": "ok", "detail": ""}
  ],
  "env_missing": [],
  "env_present": [],
  "urls": [],
  "skipped_startup": false
}
```

### Exemplo: `--validate-env` com required vars ausentes

```json
{
  "status": "blocker",
  "findings": [
    {
      "level": "BLOCKER",
      "message": "JWT_SECRET ausente — variável obrigatória declarada em testing.required_env",
      "detail": ""
    },
    {
      "level": "WARN",
      "message": "SENTRY_DSN ausente em .env (declarado em .env.example mas não em required_env)",
      "detail": ""
    }
  ],
  "health_checks": [],
  "env_missing": ["JWT_SECRET"],
  "env_present": ["DATABASE_URL", "REDIS_URL", "ADMIN_BOOTSTRAP_EMAIL"],
  "urls": [],
  "skipped_startup": false
}
```

### Exemplo: `--validate-urls` com URL inacessível

```json
{
  "status": "blocker",
  "findings": [
    {
      "level": "BLOCKER",
      "message": "http://localhost:3000/login inacessível — ConnectionRefusedError",
      "detail": "Tipo docker: verifique 'docker compose ps' e port bindings no docker-compose.override.yml"
    },
    {
      "level": "WARN",
      "message": "http://localhost:3000 responde mas conteúdo parece placeholder",
      "detail": "Body < 500 bytes após strip"
    }
  ],
  "health_checks": [],
  "env_missing": [],
  "env_present": [],
  "urls": [
    {"url": "http://localhost:8050/health", "label": "Health Check", "status_code": 200, "ok": true, "detail": ""},
    {"url": "http://localhost:3000", "label": "Root", "status_code": 200, "ok": false, "detail": "placeholder detected"},
    {"url": "http://localhost:3000/login", "label": "Login page", "status_code": null, "ok": false, "detail": "ConnectionRefusedError"}
  ],
  "skipped_startup": false
}
```

## Comportamento por Startup Type

| Type | Comando padrão | Override | Diagnóstico de falha |
|------|----------------|----------|----------------------|
| `docker` | `docker compose up -d` | `testing.startup.command` | `docker compose logs --tail 50` |
| `npm` | `npm run dev` | `testing.startup.command` | stderr do processo |
| `make` | `make run` | `testing.startup.command` | stderr do make |
| `venv` | detecta entry point em pyproject.toml | `testing.startup.command` (obrigatório) | stderr do processo |
| `script` | — | `testing.startup.command` (obrigatório) | stderr do script |
| `none` | nenhum | — | N/A |

## Invariantes

1. **Nunca destruir estado**: `qa_startup.py` jamais executa `docker compose down`, `docker stop`, ou qualquer comando destrutivo.
2. **Nunca expor valores de env**: `env_present` e `env_missing` contêm apenas nomes (keys).
3. **Exit code consistente**: exit 1 se `status == "blocker"`, exit 0 caso contrário (ok ou warn).
4. **Idempotente**: pode ser chamado múltiplas vezes sem efeitos colaterais (startup é pulado se serviços já estão saudáveis).
