# Screen Flow Vocabulary (v1)

Reference único para autores de `business/screen-flow.yaml` e para o renderer do portal. Vocabulário **fechado** — nenhum tipo, edge style, badge ou capture state fora dos listados aqui é aceito pelo `screen_flow_validator.py` (FR-001, FR-048).

> **Como usar este arquivo**
> - Skill `madruga:business-screen-flow` consulta este doc ao gerar YAML.
> - Renderer (`portal/src/components/screens/`) tem 1 sub-renderer por entrada de `Components` e 1 estilo por entrada de `Edges`.
> - Mudanças neste arquivo são **breaking** — exigem incremento de `schema_version` em `screen-flow.schema.json`.
> - Mudanças requerem ADR + PR através de `/madruga:skills-mgmt edit`.

Schema version atual: **1**.

---

## 1. Components (10) — `screens[].body[].type`

Cada componente tem 1 sub-renderer dedicado em `WireframeBody.tsx`. Paleta wireframe-only (cinza/preto/branco; cores reservadas para edges + badges).

### 1.1 `heading`

Cabeçalho de seção. Renderiza como retângulo com texto em peso `bold`, tamanho relativo maior.

```yaml
- type: heading
  id: title
  text: "Bem-vindo ao app"
```

### 1.2 `text`

Bloco de texto comum. Renderiza linhas de "shimmer" (placeholder) quando `text` ausente; texto real quando presente.

```yaml
- type: text
  text: "Faça login com seu email para continuar."
```

### 1.3 `input`

Campo de entrada. Renderiza retângulo com label flutuante e cursor visual.

```yaml
- type: input
  id: email_input
  testid: input-email
  text: "Email"
```

### 1.4 `button`

Botão acionável. Renderiza retângulo arredondado com texto centralizado. Variant via `meta.variant` (`primary | secondary | destructive`); default `primary`.

```yaml
- type: button
  id: cta_login
  testid: btn-login
  text: "Entrar"
  meta:
    variant: primary
```

### 1.5 `link`

Link textual. Renderiza texto sublinhado, paleta `--screen-accent`.

```yaml
- type: link
  id: forgot_password
  testid: link-forgot
  text: "Esqueci minha senha"
```

### 1.6 `list`

Lista simples. Renderiza N linhas baseadas em `meta.items` ou 3 placeholders se ausente.

```yaml
- type: list
  id: messages_list
  meta:
    items: ["Mensagem 1", "Mensagem 2", "Mensagem 3"]
```

### 1.7 `card`

Bloco agrupador com sombra leve. Renderiza retângulo com borda e padding interno; conteúdo livre via `text`.

```yaml
- type: card
  text: "Resumo do dia: 5 mensagens, 2 não lidas."
```

### 1.8 `image`

Placeholder de imagem. Renderiza retângulo cinza com diagonais (ícone genérico). NÃO aceita URLs reais (paleta wireframe-only).

```yaml
- type: image
  id: hero
  meta:
    aspect_ratio: "16:9"
```

### 1.9 `divider`

Separador horizontal. Renderiza linha de 1px cinza-claro com margem vertical.

```yaml
- type: divider
```

### 1.10 `badge`

Marcador inline pequeno (não confundir com Screen Badges § 3). Usado para indicar status dentro do corpo da tela (ex: "Novo", "3").

```yaml
- type: badge
  text: "Novo"
  meta:
    variant: info
```

---

## 2. Edges (4) — `flows[].style`

Cada edge tem 1 estilo dedicado em `ActionEdge.tsx`. Cor + pattern adicional para acessibilidade color-blind (FR-021, SC-008).

### 2.1 `success`

Caminho feliz / confirmação. **Verde sólido**, espessura 2px.

```yaml
- from: login
  to: home
  on: cta_login
  style: success
  label: "Login OK"
```

### 2.2 `error`

Caminho de falha / validação. **Vermelho tracejado** (`stroke-dasharray: 6 4`), espessura 2px.

```yaml
- from: login
  to: login_error
  on: cta_login
  style: error
  label: "Credenciais inválidas"
```

### 2.3 `neutral`

Navegação informativa / não-decisiva. **Cinza pontilhado** (`stroke-dasharray: 2 3`), espessura 1.5px.

```yaml
- from: home
  to: settings
  on: link_settings
  style: neutral
```

### 2.4 `modal`

Abertura de modal / overlay. **Azul sólido grosso**, espessura 3px.

```yaml
- from: home
  to: confirm_logout
  on: btn_logout
  style: modal
  label: "Confirmar saída"
```

---

## 3. Screen Badges (6) — overlays sobre `ScreenNode`

Marcadores aplicados ao chrome da tela pelo renderer (não serializados como entidade, derivados de `Screen.status` + `meta`). 1 cor + 1 ícone por badge para color-blind safe.

### 3.1 `PENDING` (derivado de `status: pending`)

Tela aguardando primeira captura. **Cinza claro**, ícone hourglass.

```yaml
- id: profile
  title: "Perfil"
  status: pending
  body: [...]
```

### 3.2 `CAPTURED` (derivado de `status: captured`)

Captura mais recente bem-sucedida. **Verde**, ícone checkmark. Combinada com thumbnail PNG no chrome.

```yaml
- id: home
  title: "Home"
  status: captured
  image: shots/home.png
  capture:
    captured_at: "2026-05-05T12:00:00Z"
    app_version: "abc1234"
    image_md5: "..."
    viewport: { w: 393, h: 852 }
  body: [...]
```

### 3.3 `FALHOU` (derivado de `status: failed`)

Última tentativa de captura falhou após 3 retries. **Vermelho**, ícone alert-triangle. Tooltip mostra `failure.reason`.

```yaml
- id: payment
  title: "Pagamento"
  status: failed
  failure:
    reason: timeout
    occurred_at: "2026-05-05T12:30:00Z"
    retry_count: 3
    last_error_message: "page.goto exceeded 30000ms"
  body: [...]
```

### 3.4 `NEW`

Marcador informacional para tela recém-adicionada (delta YAML). Renderer detecta via `meta.first_seen_at` dentro de janela de 14 dias. **Azul**, ícone sparkle.

```yaml
- id: notifications
  title: "Notificações"
  status: pending
  meta:
    first_seen_at: "2026-05-01"
  body: [...]
```

### 3.5 `WIP`

Tela em construção; drift detection silencia patches automáticos. **Amarelo**, ícone wrench. Útil enquanto desenvolvedor itera no app antes de ter capture válido.

```yaml
- id: dashboard_v2
  title: "Dashboard v2"
  status: pending
  meta:
    wip: true
  body: [...]
```

### 3.6 `DEPRECATED`

Tela marcada para remoção. Renderer mostra com 50% opacidade + tarja diagonal. **Cinza-escuro**, ícone archive. Reverse-reconcile ignora drift.

```yaml
- id: legacy_login
  title: "Login (legado)"
  status: captured
  meta:
    deprecated: true
    deprecation_reason: "Substituído por SSO em 027-channel-pipeline"
  body: [...]
```

---

## 4. Capture States (3) — `screens[].status`

Estado da captura da tela. State machine completa em `data-model.md` E2.

### 4.1 `pending`

Default para novas telas; também o estado para o qual `reverse-reconcile` rebobina quando detecta drift. NÃO requer `image` nem `capture`.

```yaml
- id: search
  title: "Busca"
  status: pending
  body:
    - { type: heading, text: "Buscar" }
    - { type: input, id: q, testid: input-search, text: "Termo" }
```

### 4.2 `captured`

Capture script gravou PNG válido + populou `capture` record. EXIGE: `image` (path relativo) + `capture: { captured_at, app_version, image_md5, viewport }`.

```yaml
- id: home
  title: "Home"
  status: captured
  image: shots/home.png
  capture:
    captured_at: "2026-05-05T12:00:00Z"
    app_version: "abc1234"
    image_md5: "d41d8cd98f00b204e9800998ecf8427e"
    viewport: { w: 393, h: 852 }
  body:
    - { type: heading, text: "Bem-vindo" }
```

### 4.3 `failed`

3 retries esgotados. EXIGE bloco `failure: { reason, occurred_at, retry_count, last_error_message? }`. CI exit code = 1 (FR-046). Workflow não bloqueia merge — drift rastreado pelo bloco `failure`.

```yaml
- id: checkout
  title: "Checkout"
  status: failed
  failure:
    reason: network_error
    occurred_at: "2026-05-05T13:15:00Z"
    retry_count: 3
    last_error_message: "net::ERR_INTERNET_DISCONNECTED"
  body:
    - { type: heading, text: "Pagamento" }
```

`failure.reason` é enum fechado: `timeout | auth_expired | network_error | app_crash | sw_cleanup_failed | mock_route_unmatched | unknown`.

---

## 5. Cross-cutting rules

| Regra | Aplicação |
|-------|-----------|
| **IDs charset** | `screen.id` e `body[].id` casam `^[a-z][a-z0-9_]{0,63}$` (FR-048) |
| **Refs consistentes** | `flow.from/to` referenciam `screens[].id`; `flow.on` referencia `body[].id` da tela `from` |
| **`testid` obrigatório** | Para `body` referenciado por `flow.on` em telas `status: captured` (renderer usa `[data-testid="<id>"]` para boundingBox de hotspot) |
| **Body não-vazio** | `screens[].body` tem `len >= 1` (tela vazia = erro de validação) |
| **Limites de escala** | warn em `len(screens) > 50`, hard reject em `> 100` (FR-049) |
| **Texto em PT-BR** | `title`, `text`, `label` em PT-BR; vocabulário enum sempre em inglês |

---

## 6. Composição mínima (template)

YAML mínimo válido para uma plataforma:

```yaml
schema_version: 1
meta:
  device: mobile
  capture_profile: iphone-15
  layout_direction: DOWN

screens:
  - id: login
    title: "Login"
    status: pending
    body:
      - { type: heading, text: "Entrar" }
      - { type: input, id: email, testid: input-email, text: "Email" }
      - { type: input, id: password, testid: input-password, text: "Senha" }
      - { type: button, id: cta_login, testid: btn-login, text: "Entrar", meta: { variant: primary } }
      - { type: link, id: forgot, testid: link-forgot, text: "Esqueci minha senha" }
  - id: home
    title: "Home"
    status: pending
    body:
      - { type: heading, text: "Bem-vindo" }

flows:
  - { from: login, to: home, on: cta_login, style: success, label: "Login OK" }
```

---

## 7. Como mudar este vocabulário

1. Abrir epic dedicado (NÃO lateralizar em outras epics).
2. Atualizar `screen-flow.schema.json` (incluir/remover entrada do enum).
3. Incrementar `schema_version` (1 → 2). Validator rejeita YAMLs antigos quando carregado em runtime do skill.
4. Atualizar este arquivo (vocabulary) e adicionar exemplo.
5. Atualizar renderer (`WireframeBody.tsx`, `ActionEdge.tsx`, `Badge.tsx`).
6. Adicionar migração `screen-flow-yaml-migrate.py` para mover YAMLs `schema_version: 1` → `2`.
7. ADR registra a mudança como 1-way-door (Decision #5 da pitch — vocabulário fechado).
