# Contrato: journeys.md Schema

**Localização**: `platforms/<name>/testing/journeys.md`  
**Referenciado por**: `platform.yaml` → `testing.journeys_file`  
**Consumidores**: `qa_startup.py` (steps `type: api`), skill `madruga/qa.md` (steps `type: browser`)

---

## Formato do Arquivo

`journeys.md` é um documento Markdown com seções de texto human-readable e blocos YAML fenced machine-readable. Cada jornada tem um título Markdown e um bloco YAML com schema definido.

### Estrutura Completa

````markdown
# Jornadas de Teste — <Platform Name>

> Jornadas de usuário para validação end-to-end. Atualizado por `speckit.tasks` e `reconcile`.

## J-001 — Nome da Jornada

Descrição textual opcional da jornada (ignorada por qa_startup.py).

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
    assert_contains: ["email", "password"]
```

## J-002 — Outra Jornada

```yaml
id: J-002
title: "Outra Jornada"
required: false
steps:
  - type: api
    action: "POST http://localhost:8050/api/auth/login"
    assert_status: 200
```
````

---

## Schema YAML por Journey

```yaml
id: string           # OBRIGATÓRIO. Formato: J-NNN (ex: J-001)
title: string        # OBRIGATÓRIO. Descrição curta
required: boolean    # OBRIGATÓRIO. Se true → BLOCKER em falha; se false → WARN
steps:               # OBRIGATÓRIO. Lista de steps (mínimo 1)
  - type: api|browser  # OBRIGATÓRIO
    action: string     # OBRIGATÓRIO
    
    # Campos opcionais por tipo:
    assert_status: integer          # api only — HTTP status esperado
    assert_redirect: string         # api/browser — URL de redirect esperada
    assert_contains: list[string]   # api/browser — substrings esperadas no body/page
    screenshot: boolean             # browser only — capturar screenshot neste step (default: false)
```

### Tipos de Step

**`type: api`** — Executado por `qa_startup.py` deterministicamente:
- `action` segue o formato `METHOD URL` (ex: `GET http://localhost:8050/health`)
- Assertions disponíveis: `assert_status`, `assert_redirect`, `assert_contains`

**`type: browser`** — Executado pelo QA skill (LLM) via Playwright MCP:
- `action` é texto livre interpretado pelo LLM (ex: `navigate http://localhost:3000`, `click button.login`, `fill_form email=test@test.com`)
- Assertions disponíveis: `assert_contains`, `screenshot`
- Se Playwright MCP indisponível: step marcado como `SKIP` no report; jornada continua com steps de API restantes

---

## Regras de Parsing

`qa_startup.py` extrai blocos YAML usando regex:

```python
import re
import yaml

def parse_journeys(content: str) -> list[dict]:
    blocks = re.findall(r"```yaml\n(.*?)```", content, re.DOTALL)
    journeys = []
    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict) and str(data.get("id", "")).startswith("J-"):
                journeys.append(data)
        except yaml.YAMLError:
            pass  # skip malformed blocks
    return journeys
```

**Invariante**: Apenas blocos cujo campo `id` começa com `J-` são reconhecidos como jornadas.  
Outros blocos YAML no arquivo (ex: exemplos de código) são ignorados silenciosamente.

---

## Exemplos por Plataforma

### madruga-ai (portal Astro)

```yaml
id: J-001
title: "Portal carrega e exibe plataformas"
required: true
steps:
  - type: browser
    action: "navigate http://localhost:4321"
    screenshot: true
  - type: browser
    action: "assert_contains madruga-ai"
  - type: browser
    action: "assert_contains prosauai"
```

### prosauai (FastAPI + Next.js Admin)

```yaml
id: J-001
title: "Admin Login Happy Path"
required: true
steps:
  - type: api
    action: "GET http://localhost:3000"
    assert_redirect: /login
  - type: browser
    action: "navigate http://localhost:3000/login"
    screenshot: true
  - type: browser
    action: "fill_form email=admin@test.com password=testpass"
  - type: browser
    action: "click button[type=submit]"
    screenshot: true
  - type: browser
    action: "assert_contains Dashboard"
```
