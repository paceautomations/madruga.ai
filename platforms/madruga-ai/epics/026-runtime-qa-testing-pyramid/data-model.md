# Data Model: Runtime QA & Testing Pyramid

**Epic**: 026-runtime-qa-testing-pyramid  
**Input**: spec.md (entidades-chave) + research.md (decisões de implementação)

---

## Entidades Principais

### 1. TestingManifest

Configuração declarativa de testes lida do bloco `testing:` em `platform.yaml`.  
Não persistida em BD — carregada em memória a cada invocação de `qa_startup.py`.

```python
from dataclasses import dataclass, field

@dataclass
class StartupConfig:
    type: str                   # docker | npm | make | venv | script | none
    command: str | None         # override do comando padrão por tipo
    ready_timeout: int = 60     # segundos até desistir de health checks

@dataclass
class HealthCheck:
    url: str                         # URL a checar (ex: http://localhost:8050/health)
    method: str = "GET"
    expect_status: int = 200
    expect_body_contains: str | None = None  # substring opcional no body
    label: str = ""                  # descrição human-readable

@dataclass
class URLEntry:
    url: str
    type: str                         # api | frontend
    label: str
    expect_status: int | list[int] = 200
    expect_redirect: str | None = None   # ex: "/login"
    expect_contains: list[str] = field(default_factory=list)
    requires_auth: bool = False

@dataclass
class TestingManifest:
    startup: StartupConfig
    health_checks: list[HealthCheck] = field(default_factory=list)
    urls: list[URLEntry] = field(default_factory=list)
    required_env: list[str] = field(default_factory=list)  # keys only
    env_file: str | None = None       # ex: ".env.example"
    journeys_file: str | None = None  # ex: "testing/journeys.md"
```

**Parsing** (de `platform.yaml`):
```python
def load_manifest(platform_name: str, repo_root: Path) -> TestingManifest | None:
    yaml_path = repo_root / "platforms" / platform_name / "platform.yaml"
    data = yaml.safe_load(yaml_path.read_text())
    testing = data.get("testing")
    if not testing:
        return None
    return _parse_manifest(testing)
```

---

### 2. Journey

Jornada de usuário declarada em `journeys.md`. Parseável por `qa_startup.py` (steps `type: api`) e lida pelo QA skill (steps `type: browser`).

```python
@dataclass
class JourneyStep:
    type: str                              # api | browser
    action: str                            # ex: "GET http://localhost:8050/health"
    assert_status: int | None = None
    assert_redirect: str | None = None
    assert_contains: list[str] = field(default_factory=list)
    screenshot: bool = False

@dataclass
class Journey:
    id: str           # ex: J-001
    title: str
    required: bool = True
    steps: list[JourneyStep] = field(default_factory=list)
```

**Formato em `journeys.md`** (YAML fenced block, parseável por pyyaml):

````markdown
## J-001 — Título da Jornada

```yaml
id: J-001
title: "Título da Jornada"
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

---

### 3. StartupResult

Output estruturado de `qa_startup.py`. Serializado como JSON em stdout.

```python
@dataclass
class Finding:
    level: str    # BLOCKER | WARN | INFO
    message: str
    detail: str = ""

@dataclass
class HealthCheckResult:
    label: str
    url: str
    status: str   # ok | failed | timeout
    detail: str = ""

@dataclass
class URLResult:
    url: str
    label: str
    status_code: int | None = None
    ok: bool = False
    detail: str = ""

@dataclass
class StartupResult:
    status: str                              # ok | warn | blocker
    findings: list[Finding] = field(default_factory=list)
    health_checks: list[HealthCheckResult] = field(default_factory=list)
    env_missing: list[str] = field(default_factory=list)  # keys only, never values
    env_present: list[str] = field(default_factory=list)  # keys only, never values
    urls: list[URLResult] = field(default_factory=list)
    skipped_startup: bool = False
```

**Schema JSON de saída** (stdout de `qa_startup.py --json`):

```json
{
  "status": "ok|warn|blocker",
  "findings": [
    {"level": "BLOCKER|WARN|INFO", "message": "...", "detail": "..."}
  ],
  "health_checks": [
    {"label": "API Backend", "url": "http://localhost:8050/health", "status": "ok", "detail": ""}
  ],
  "env_missing": ["JWT_SECRET"],
  "env_present": ["DATABASE_URL", "REDIS_URL"],
  "urls": [
    {"url": "http://localhost:8050/health", "label": "Health Check", "status_code": 200, "ok": true, "detail": ""}
  ],
  "skipped_startup": false
}
```

---

## Diagrama de Relacionamentos

```
platform.yaml
  └── testing: (optional block)
        ├── startup: → StartupConfig
        ├── health_checks: → list[HealthCheck]
        ├── urls: → list[URLEntry]
        ├── required_env: → list[str]
        ├── env_file: → str (path relativo ao repo da plataforma)
        └── journeys_file: → str (path relativo ao repo madruga.ai)

journeys_file → journeys.md
  └── YAML blocks → list[Journey]
        └── steps → list[JourneyStep]

qa_startup.py operations:
  --parse-config  → TestingManifest
  --start         → StartupResult (health_checks preenchido)
  --validate-env  → StartupResult (env_missing + env_present preenchidos)
  --validate-urls → StartupResult (urls preenchido)
  --full          → StartupResult (todos campos preenchidos)
```

---

## Mapeamento FR → Entidade

| FR | Entidade Afetada | Campo Relevante |
|----|-----------------|-----------------|
| FR-001 | TestingManifest | todos campos |
| FR-002 | TestingManifest | validação em `_lint_platform()` |
| FR-005 | StartupResult | operações CLI |
| FR-006 | StartupConfig | `type` + `command` |
| FR-007 | StartupResult | schema JSON |
| FR-008 | TestingManifest | `--platform` + `--cwd` |
| FR-009/010 | StartupResult | `env_missing`, finding BLOCKER |
| FR-011/012 | StartupResult | `health_checks`, finding BLOCKER |
| FR-013 | StartupResult | `urls`, finding BLOCKER |
| FR-021 | Journey | formato YAML fenced |
| FR-022 | StartupResult | `env_present`/`env_missing` keys-only |
| FR-023 | URLResult | detecção de placeholder |

---

## Extensões do Schema `platform.yaml`

### Bloco `testing:` (adicionado por este epic)

```yaml
testing:
  startup:
    type: docker                    # docker | npm | make | venv | script | none
    command: null                   # override; required se type=script
    ready_timeout: 120              # segundos
  health_checks:
    - url: http://localhost:8050/health
      method: GET
      expect_status: 200
      expect_body_contains: '"status"'  # opcional
      label: "API Backend"
  urls:
    - url: http://localhost:3000
      type: frontend
      label: "Admin Frontend"
      expect_status: 200
      expect_redirect: null
      expect_contains: []
      requires_auth: false
  required_env:
    - JWT_SECRET
    - DATABASE_URL
  env_file: .env.example            # relativo ao repo da plataforma; null = skip
  journeys_file: testing/journeys.md # relativo ao repo madruga.ai (platforms/<name>/)
```

### Template Copier (`platform.yaml.jinja`)

Extensão aditiva ao template existente — o bloco `testing:` é adicionado no final do arquivo:

```jinja
{%- if testing_startup_type is defined and testing_startup_type != 'none' %}
testing:
  startup:
    type: {{ testing_startup_type | default('none') }}
    command: null
    ready_timeout: 60
  health_checks: []
  urls: []
  required_env: []
  env_file: null
  journeys_file: testing/journeys.md
{%- endif %}
```
