# Research: Runtime QA & Testing Pyramid

**Epic**: 026-runtime-qa-testing-pyramid  
**Branch**: `epic/madruga-ai/026-runtime-qa-testing-pyramid`  
**Fase**: Phase 0 — Resolução de desconhecidos técnicos

---

## Decisão 1: Polling de Health Checks com stdlib

**Pergunta**: Como implementar um poller de health checks com timeout e backoff usando apenas `urllib.request`?

**Decisão**: Loop `time.sleep(2)` com `time.monotonic()` para controle de deadline.

**Rationale**: A stdlib já expõe `urllib.request.urlopen(url, timeout=N)` que lança `urllib.error.URLError` em timeout de conexão e `http.client.RemoteDisconnected` em reset. O padrão correto:

```python
import time
import urllib.request
import urllib.error

def wait_for_health(url: str, timeout_sec: int, label: str) -> bool:
    deadline = time.monotonic() + timeout_sec
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception as exc:
            last_exc = exc
        time.sleep(2)
    return False
```

**Alternativas consideradas**:
- `requests` (mais ergonômico) — rejeitado por violar ADR-004 (nenhuma dep externa nova)
- `asyncio` + `aiohttp` — over-engineering para um script CLI sequencial
- `subprocess.run(["curl", "--retry"])` — frágil, depende de curl no PATH

---

## Decisão 2: Formato YAML-in-Markdown para journeys.md

**Pergunta**: Como estruturar `journeys.md` de forma machine-readable sem criar um arquivo YAML separado?

**Decisão**: Bloco de código YAML fenced por ```` ```yaml ```` com campo `id` fixo para indexação por `pyyaml`.

**Formato definido (parseável por pyyaml)**:

````markdown
## J-001 — Nome da Jornada

```yaml
id: J-001
title: "Nome da Jornada"
required: true
steps:
  - type: api
    action: "GET http://localhost:8050/health"
    assert_status: 200
  - type: browser
    action: "navigate http://localhost:3000"
    screenshot: true
  - type: browser
    action: "assert_contains Login"
```
````

**Parser em `qa_startup.py`**:

```python
import re, yaml

def parse_journeys(content: str) -> list[dict]:
    """Extract YAML journey blocks from journeys.md content."""
    blocks = re.findall(r"```yaml\n(.*?)```", content, re.DOTALL)
    journeys = []
    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict) and "id" in data and data["id"].startswith("J-"):
                journeys.append(data)
        except yaml.YAMLError:
            pass
    return journeys
```

**Rationale**: YAML fenced blocks são padrão no ecossistema Markdown (ex: `mermaid`, `yaml` no GitHub). O QA skill (LLM) lê o mesmo arquivo como contexto para steps de browser. `pyyaml.safe_load` é threadsafe e já é dependência do projeto.

**Alternativas consideradas**:
- Arquivo separado `journeys.yaml` — cria mais arquivos; a spec decidiu por `journeys.md` como documento textual + machine-readable
- TOML inline — não é stdlib; menos familiar para o público-alvo
- JSON fenced blocks — menos legível para humanos

---

## Decisão 3: Extensão do Schema de `_lint_platform` para `testing:` block

**Pergunta**: Como adicionar validação do bloco `testing:` ao `platform_cli.py` sem quebrar retrocompatibilidade?

**Decisão**: Bloco `testing:` é **opcional**. Se presente, validar campos obrigatórios do sub-schema. Se ausente, lint passa sem erro (retrocompatibilidade total).

**Schema mínimo validado quando presente**:

```python
TESTING_STARTUP_TYPES = {"docker", "npm", "make", "venv", "script", "none"}

def _lint_testing_block(testing: dict, platform_name: str) -> bool:
    ok = True
    startup = testing.get("startup", {})
    stype = startup.get("type")
    if stype not in TESTING_STARTUP_TYPES:
        _error(f"testing.startup.type '{stype}' inválido. Valores: {TESTING_STARTUP_TYPES}")
        ok = False
    if stype == "script" and not startup.get("command"):
        _error("testing.startup.type 'script' requer testing.startup.command")
        ok = False
    health_checks = testing.get("health_checks", [])
    for hc in health_checks:
        if "url" not in hc or "label" not in hc:
            _error("health_check sem 'url' ou 'label'")
            ok = False
    return ok
```

**Chamada**: Em `_lint_platform`, após validar os campos top-level do `platform.yaml`:
```python
if "testing" in manifest:
    _lint_testing_block(manifest["testing"], name)
```

**Alternativas consideradas**:
- `jsonschema` para validação declarativa — dep externa, violaria ADR-004
- Pydantic — idem
- YAML anchors — não relevante aqui

---

## Decisão 4: Detecção de Startups Já Rodando

**Pergunta**: Como diferenciar "serviços já rodando e saudáveis" de "serviços ainda não iniciados"?

**Decisão**: Ao `--start`, tentar o health check **primeiro** (timeout=5s por check). Se todos passam imediatamente → "já rodando, pulando startup". Se qualquer um falha → executar o comando de startup, então aguardar pelo `ready_timeout`.

**Fluxo**:

```
start():
  1. quick_check() → tenta cada health_check com timeout=3s
  2. Se todos OK → return {status: "ok", skipped_startup: true}
  3. Senão → execute_startup_command()
  4. poll_health_checks() com ready_timeout
  5. Se timeout → BLOCKER com logs de diagnóstico
```

**Diagnóstico de falha de startup**: O BLOCKER inclui:
- Qual health check falhou (label + URL + status recebido ou tipo de exceção)
- Saída de `docker compose logs --tail 50 <service>` quando type=docker
- Sugestão de comando manual para diagnóstico

**Alternativas consideradas**:
- Sempre rodar o comando de startup (pode falhar se container já existe) — rejeitado
- Usar `--force-restart` flag — over-engineering; por padrão não reiniciar é o comportamento correto

---

## Decisão 5: REPO_ROOT Discovery em qa_startup.py

**Pergunta**: Como `qa_startup.py` descobre o path do `platform.yaml` quando executado com `--cwd <external_repo>`?

**Decisão**: `REPO_ROOT` via variável de ambiente `MADRUGA_REPO_ROOT` (já usada como padrão em outros scripts), com fallback para `Path(__file__).resolve().parents[2]`.

**Padrão extraído de `config.py`**:
```python
REPO_ROOT = Path(os.environ.get("MADRUGA_REPO_ROOT", "")) or Path(__file__).resolve().parents[2]
platform_yaml = REPO_ROOT / "platforms" / platform_name / "platform.yaml"
```

**CWD para execução de comandos**: passado via `--cwd` (obrigatório quando diferente de REPO_ROOT). Se `--cwd` ausente, usa o CWD atual.

**Alternativas consideradas**:
- Caminhos relativos — frágil, depende do cwd do caller
- Passar o path completo do platform.yaml via CLI — ergonomia pior, mais verbose

---

## Decisão 6: Output JSON de env diff — Keys only, Zero Values

**Pergunta**: Como garantir que `qa_startup.py --validate-env` nunca expõe valores de variáveis sensíveis?

**Decisão**: Ler apenas as **keys** do `.env` real (split por `=`, pegar parte esquerda), nunca os valores. O output JSON contém apenas:
```json
{
  "env_missing": ["JWT_SECRET"],
  "env_present": ["DATABASE_URL", "REDIS_URL"]
}
```

**Parser de .env** (stdlib only):
```python
def _read_env_keys(env_path: Path) -> set[str]:
    """Return set of variable names from .env file, never values."""
    keys = set()
    if not env_path.exists():
        return keys
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys
```

**Alternativas consideradas**:
- `python-dotenv` para parsing — dep externa; o parser acima é suficiente e correto
- Incluir valores mascarados (`JWT_SECRET=***`) — ainda vaza o fato de qual secret está presente com qual tamanho; keys-only é mais seguro

---

## Decisão 7: Detecção de Placeholder HTML

**Pergunta**: Quais critérios determinísticos (sem LLM) para classificar uma resposta HTTP como "placeholder"?

**Decisão**: Lógica sequencial (OR):
1. `len(body.strip()) < 500` — corpo muito curto
2. Qualquer literal presente: `"You need to enable JavaScript"`, `"React App"`, `"Vite + React"`, `"Welcome to nginx"`, `"It works!"`
3. Body não contém tag `<body` com conteúdo real (apenas whitespace entre `<body` e `</body>`)
4. `Content-Type` não é `text/html` para URL declarada como `type: frontend`

**Implementação**:
```python
PLACEHOLDER_STRINGS = [
    "You need to enable JavaScript",
    "React App",
    "Vite + React",
    "Welcome to nginx",
    "It works!",
]

def _is_placeholder(body: str, content_type: str, url_type: str) -> bool:
    if len(body.strip()) < 500:
        return True
    if any(p in body for p in PLACEHOLDER_STRINGS):
        return True
    if url_type == "frontend" and "text/html" not in content_type:
        return True
    return False
```

**Alternativas consideradas**:
- Heurísticas de DOM parsing (`html.parser`) — over-engineering; o pattern matching é suficiente
- Machine learning para classificação de conteúdo — claramente fora do escopo

---

## Decisão 8: Logging Estruturado em qa_startup.py

**Princípio IX (Constitution)**: todo script deve emitir logs estruturados.

**Decisão**: `qa_startup.py` usa `print(json.dumps(...), file=sys.stderr)` para logs de debug/info e `print(json.dumps(result))` para o output final (stdout). O `--json` flag suprime mensagens de progresso em stderr.

**Rationale**: Scripts CLI do projeto usam `log_utils.py` com structlog, mas `qa_startup.py` é um script standalone que pode rodar em contexto externo (CI, plataformas externas). Usar apenas stdlib para logging evita imports de módulos do madruga.ai em contextos onde o PYTHONPATH pode não estar configurado.

**Alternativas consideradas**:
- `log_utils.setup_logging()` do madruga.ai — requer PYTHONPATH correto; risco em CI externo
- `logging` stdlib com formatter JSON custom — aceitável, mas mais verbose; `print` para stderr é suficiente para um script

---

## Resumo de Decisões por Componente

| Componente | Decisão chave | Alternativa rejeitada |
|------------|--------------|----------------------|
| `qa_startup.py` health poll | `time.monotonic()` + `urllib.request` | `requests` (dep externa) |
| journeys.md parser | regex + `pyyaml.safe_load` em blocos fenced | arquivo .yaml separado |
| lint testing: block | validação opcional in-process | jsonschema (dep externa) |
| startup detection | quick_check antes de startup | sempre reiniciar |
| REPO_ROOT discovery | env var + `Path(__file__).parents[2]` | caminhos relativos |
| env diff output | keys-only, nunca valores | valores mascarados |
| placeholder detection | 4 critérios OR, stdlib puro | html.parser |
| logging | stderr JSON + stdout result | log_utils (PYTHONPATH dep) |
