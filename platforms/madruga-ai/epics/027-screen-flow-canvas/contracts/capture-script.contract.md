---
epic: 027-screen-flow-canvas
phase: phase-1-contract
created: 2026-05-05
sidebar:
  order: 3
---

# Capture Script — I/O Contract

Contrato formal do `screen_capture.py` (orchestrator Python) e `screen_capture.spec.ts` (Playwright spec). Define entrada, saída, exit codes, formato de logs, e invariantes operacionais.

---

## Visão Geral

```
+------------------------------------------------------------------+
|                                                                  |
|  Inputs                          Outputs                         |
|  ------                          -------                         |
|  - screen-flow.yaml              - screen-flow.yaml (updated)    |
|  - platform.yaml                 - business/shots/<id>.png       |
|  - env vars                      - structured logs (JSON stdout) |
|  - storageState file             - exit code (0 / 1)             |
|                                                                  |
+------------------------------------------------------------------+
              |                              ^
              |                              |
              v                              |
   +------------------+         +-----------------------+
   |  Python          | invokes |  Playwright spec (TS) |
   |  orchestrator    |-------->|                       |
   |  screen_capture  |   IPC   |  screen_capture.spec  |
   |  .py             |  via    |  .ts                  |
   |                  |  JSON   |                       |
   +------------------+         +-----------------------+
```

---

## Inputs

### 1. CLI args (Python orchestrator)

```text
python3 .specify/scripts/capture/screen_capture.py <platform> [--screen <id>] [--dry-run]
```

| Argument | Tipo | Obrigatório | Notas |
|----------|------|-------------|-------|
| `<platform>` | string | Sim | Nome da plataforma (ex: `resenhai-expo`). Tem que ter `screen_flow.enabled: true` |
| `--screen <id>` | string | Não | Captura apenas a tela especificada (debug; default: todas) |
| `--dry-run` | bool | Não | Simula sem escrever PNGs nem atualizar YAML |

### 2. Filesystem inputs

| Path | Lido por | Notas |
|------|----------|-------|
| `platforms/<platform>/platform.yaml` | Python | Bloco `screen_flow.capture` |
| `platforms/<platform>/business/screen-flow.yaml` | Python + TS | Lista de telas a capturar |
| `<storage_state_path>` (relativo ao repo da plataforma) | TS | Cookies/localStorage pre-baked |

### 3. Environment variables

| Env var | Obrigatório | Notas |
|---------|-------------|-------|
| `<PREFIX>_TEST_EMAIL` | Sim (quando `auth.type=storage_state`) | Email do test user (used apenas pelo `auth.setup_command` se storageState ausente) |
| `<PREFIX>_TEST_PASSWORD` | Sim (idem) | Senha do test user |
| `GH_TOKEN` | Não (CI) | Para auto-commit do YAML atualizado |
| `MADRUGA_CAPTURE_TIMEOUT_MS` | Não | Override do timeout default 30000 |

> `<PREFIX>` é o valor de `auth.test_user_env_prefix` (ex: `RESENHAI`).

---

## Outputs

### 1. Modified files

| Path | Quando |
|------|--------|
| `platforms/<platform>/business/screen-flow.yaml` | Sempre (status atualizado por tela) |
| `platforms/<platform>/business/shots/<screen_id>.png` | Quando `status` muda para `captured` |

YAML é reescrito **preservando ordem de chaves e comentários** via biblioteca Python que mantém estilo (ex: `ruamel.yaml`). Se `ruamel.yaml` não estiver disponível, fallback é re-emitir com formatação canônica e header de aviso (perde comentários).

### 2. Structured logs (stdout, JSONL)

Cada linha é um JSON object obedecendo o schema:

```json
{
  "timestamp": "2026-05-05T12:34:56.789Z",
  "level": "INFO|WARN|ERROR|DEBUG",
  "message": "Human readable",
  "correlation_id": "<screen_id>",
  "context": {
    "platform": "resenhai-expo",
    "run_id": "<uuid>",
    "phase": "init|setup|capture|cleanup|commit",
    "screen_id": "<id>",
    "retry_count": 0,
    "duration_ms": 1234
  }
}
```

Eventos críticos (sempre INFO ou acima):
- `phase: init` — start do run, com run_id gerado
- `phase: setup` — leitura de YAMLs, validação preliminar
- `phase: capture` — start/end de cada tela; success ou retry
- `phase: cleanup` — SW unregister, cookies clear
- `phase: commit` — write de YAML + PNGs

### 3. Exit codes

| Code | Significado |
|------|-------------|
| `0` | Todas as telas terminaram com `status=captured` |
| `1` | Pelo menos uma tela terminou com `status=failed` (CI alarm — FR-046). YAML é committed mesmo assim. |
| `2` | Erro fatal antes de iniciar capturas (auth setup falhou, YAML inválido, storageState inexistente e `auth.setup_command` falhou) |
| `3` | Aborted (timeout do workflow ou SIGTERM) |

---

## Invariantes operacionais

### I1. Determinism

Para uma mesma versão do app (mesmo `app_version` git SHA) + mesmas env vars + mesmo `storageState`, 2 runs back-to-back DEVEM produzir PNGs com `image_md5` idêntico em ≥80% das telas (SC-003, FR-033). Telas autenticadas DEVEM passar pelo SW cleanup quando `clear_service_workers: true`.

### I2. Retry policy

| Falha | Comportamento |
|-------|---------------|
| `page.goto` timeout (>30s) | Retry com backoff exponencial 1s/2s/4s, max 3 retries; após esgotar, `status=failed` com `reason=timeout` |
| Network error | Mesmo retry policy; `reason=network_error` |
| Auth expired (storageState rejeitado) | Sem retry — `reason=auth_expired`, exit code 2 fatal (FR-047 violation) |
| App crash (page closed unexpectedly) | Retry; `reason=app_crash` |
| SW cleanup falha | Warn structured log mas captura prossegue; se PNG depois der erro, `reason=sw_cleanup_failed` |
| Mock route não casa nenhum request real | Warn; captura prossegue (não-fatal); `reason=mock_route_unmatched` aparece se outras assertions falharem |

### I3. Concurrency safety

Workflow GH Actions DEVE usar `concurrency.group: "capture-${{ matrix.platform }}"` com `cancel-in-progress: false`. Isso garante que 2 dispatches simultâneos não corrompem `screen-flow.yaml` (FR-035, SC-012).

### I4. Pre-commit gate

Antes de commit do YAML + PNGs, hook Python (`pre_commit_png_size.py`) DEVE rejeitar PNG `>500KB`. Capture script DEVE incluir uma checagem upstream pra falhar fast no run próprio:

```python
if png.stat().st_size > 500_000:
    log_error("png_too_large", screen_id=id, size=png.stat().st_size)
    transition_to_failed(reason="unknown", error_message="PNG exceeded 500KB limit")
```

### I5. PII guard

Capture script DEVE verificar que `platform.yaml.screen_flow.capture.test_user_marker` está populado antes de iniciar. Se ausente quando `enabled: true`, exit code 2.

---

## Erros conhecidos e remediation

| Sintoma | Causa provável | Remediation |
|---------|---------------|-------------|
| Exit 2 + log `auth_setup_failed` | `<PREFIX>_TEST_EMAIL` ou `_PASSWORD` ausente em env | Configurar GH Secrets ou exportar localmente |
| Exit 1 + ≥3 telas com `reason=timeout` | Staging instável ou request lento | Aumentar `MADRUGA_CAPTURE_TIMEOUT_MS`; checar status do staging |
| PNGs diferentes entre runs (md5 mismatch) | Element não-determinístico não coberto por mocks | Adicionar `mock_route` ou `data-volatile` no app (escalada incremental Decision #8) |
| `reason=sw_cleanup_failed` recorrente | Service Worker não resposive a `unregister()` | Hard-reload da página antes do cleanup; bug do app |
| YAML perdeu comentários após capture | `ruamel.yaml` não disponível, fallback canonical | Adicionar `ruamel.yaml` aos deps Python do repo |

---

## Performance budget

| Métrica | Budget | Ação se exceder |
|---------|--------|-----------------|
| Tempo total do workflow | 30 min | Workflow timeout (GH Actions matar run) |
| Tempo por tela (single capture, sem retry) | 60s p95 | Warn structured log; revisar `wait_for` no YAML |
| Tempo de SW cleanup | 5s | Warn + prossegue |
| MD5 calc + PNG write | 2s p95 | Warn + prossegue |
| Storage state setup (quando regenera) | 60s | Falha → exit 2 |

---

## Local invocation example

```bash
cd /home/gabrielhamu/repos/paceautomations/madruga.ai

# Set credentials
export RESENHAI_TEST_EMAIL=demo+playwright@resenhai.com
export RESENHAI_TEST_PASSWORD=...

# Run capture
python3 .specify/scripts/capture/screen_capture.py resenhai-expo

# Inspect logs (filtered to errors)
python3 .specify/scripts/capture/screen_capture.py resenhai-expo 2>&1 | jq 'select(.level == "ERROR")'

# Capture single screen for debugging
python3 .specify/scripts/capture/screen_capture.py resenhai-expo --screen login --dry-run
```

---

## CI invocation example

```bash
gh workflow run capture-screens.yml -f platform=resenhai-expo
```

Workflow lê o input `platform`, dispara o matrix correspondente, executa capture, e auto-commita as mudanças via PR ou push direto na branch do epic dependendo da config.
