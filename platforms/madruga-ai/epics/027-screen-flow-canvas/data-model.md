---
epic: 027-screen-flow-canvas
phase: phase-1
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 2
---

# Data Model — Phase 1

Modelo de dados do epic. 11 entidades, com atributos, relações, regras de validação e estados.

> Convenções:
> - Tipos seguem TypeScript-style: `string`, `number`, `boolean`, `enum<...>`, `array<T>`, `record<K, V>`, `optional<T>`, `regex<...>`.
> - Validações marcadas `[V]` são enforced pelo `screen_flow_validator.py`; `[L]` enforced pelo `platform_cli.py lint`.
> - Estados marcados `[S]` são state machines (transições documentadas).

---

## E1. ScreenFlow

Documento YAML por plataforma — raiz do artefato.

**Source**: `platforms/<name>/business/screen-flow.yaml`

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `schema_version` | `enum<1>` | Sim | [V] Rejeita ausência ou versão desconhecida (FR-002) |
| `meta` | `MetaConfig` | Sim | [V] Validado contra subschema |
| `screens` | `array<Screen>` | Sim | [V] `1 <= len <= 100` (warn `>50`, hard reject `>100` — FR-049) |
| `flows` | `array<Flow>` | Sim | [V] Pode ser `[]` mas campo obrigatório |

**MetaConfig**:

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `device` | `enum<mobile, desktop>` | Sim | — |
| `capture_profile` | `enum<iphone-15, desktop>` | Sim | [V] Tem que casar com `platform.yaml.screen_flow.capture.device_profile` |
| `layout_direction` | `enum<DOWN, RIGHT>` | Não (default `DOWN`) | — |

**Validações cross-field**:
- [V] Todos os `screens[].id` são únicos no documento
- [V] Todos os `flows[].from` e `flows[].to` referenciam `screens[].id` existentes
- [V] Não há ciclos no DAG dos flows OU `screens` envolvidas em ciclos têm `position` manual declarada
- [V] `meta.capture_profile` casa com `screens[].meta.capture_profile` quando declarado

---

## E2. Screen

Tela individual.

**Source**: item de `screens[]` em ScreenFlow

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `id` | `regex<^[a-z][a-z0-9_]{0,63}$>` | Sim | [V] Charset locked (FR-048, SC-021) |
| `title` | `string` (1-100 chars) | Sim | — |
| `status` | `enum<pending, captured, failed>` | Sim | [V] [S] State machine — ver abaixo |
| `body` | `array<BodyComponent>` | Sim | [V] `len >= 1` (tela vazia = erro) |
| `image` | `optional<string>` (path relativo) | Só quando `status=captured` | [V] Path bate com `business/shots/<id>.png` |
| `position` | `optional<{x: number, y: number}>` | Não | [V] Override manual, usado quando ELK não consegue (ciclo) |
| `meta` | `optional<ScreenMeta>` | Não | — |
| `failure` | `optional<CaptureFailure>` | Só quando `status=failed` | [V] Bloco populado quando status=failed |
| `capture` | `optional<CaptureRecord>` | Só quando `status=captured` | [V] Populado por capture script |

**ScreenMeta**:

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `route` | `optional<string>` | Não | Path relativo ao `base_url` (ex: `/login`) — usado pelo capture |
| `entrypoint` | `optional<string>` | Não | Alternative: chamada de `Linking.openURL()` ou navegação programática |
| `capture_profile` | `optional<enum>` | Não | Override do default da plataforma |
| `wait_for` | `optional<string>` | Não | CSS selector para aguardar antes de capturar |

**State Machine [S] — Screen.status**:

```text
                  +---> captured (capture sucesso) ---+
                  |                                    |
[start] -> pending +---> failed (3 retries esgotados)  +---> pending (drift via reverse-reconcile)
                  |                                    |
                  +-< (retorna pending após drift) ----+
```

Transições válidas:
- `pending → captured` (capture script grava image + capture record)
- `pending → failed` (3 retries esgotados; failure record populado)
- `captured → pending` (drift detection via reverse-reconcile reescreve YAML)
- `failed → captured` (próximo capture run sucesso após fix)
- `failed → pending` (drift detection sobrescreve estado de falha)

Transições inválidas (rejeitadas pelo validator/script):
- `captured → failed` direto (deve passar por `pending` se quer-se reprocessar)

---

## E3. BodyComponent

Componente do corpo de uma tela.

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `type` | `enum<heading, text, input, button, link, list, card, image, divider, badge>` | Sim | [V] Vocabulário fechado de 10 — Decision #5 |
| `id` | `regex<^[a-z][a-z0-9_]{0,63}$>` | Não | [V] Mesmo charset de Screen.id |
| `text` | `optional<string>` | Não | Conteúdo textual exibido no wireframe |
| `testid` | `optional<string>` | Só quando referenciado por `Flow.on` | [V] Identifier do `data-testid` no DOM real (FR-028) |
| `meta` | `optional<record<string, any>>` | Não | Metadata livre (ex: `{ variant: 'primary' }`) |

**Regras**:
- `id` é obrigatório APENAS quando o componente é referenciado por `Flow.on`
- `testid` é obrigatório APENAS para componentes referenciados por `Flow.on` em telas `status: captured` (capture usa `[data-testid="<id>"]` para boundingBox de hotspot)

---

## E4. Flow / Edge

Aresta entre telas.

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `from` | `regex<^[a-z][a-z0-9_]{0,63}$>` | Sim | [V] Casa com algum `screens[].id` |
| `to` | `regex<^[a-z][a-z0-9_]{0,63}$>` | Sim | [V] Casa com algum `screens[].id` |
| `on` | `regex<^[a-z][a-z0-9_]{0,63}$>` | Sim | [V] Casa com algum `body[].id` da tela `from` |
| `style` | `enum<success, error, neutral, modal>` | Sim | [V] Vocabulário fechado de 4 — Decision #5 |
| `label` | `optional<string>` (1-50 chars) | Não | Texto exibido sobre a aresta |

**Regras visuais (renderer)**:
- `success`: verde sólido
- `error`: vermelho tracejado
- `neutral`: cinza pontilhado
- `modal`: azul sólido grosso (3px)
- Pattern adicional à cor pra color-blind (FR-021, SC-008)

---

## E5. Hotspot (derivado)

Marcador visual sobre tela capturada — derivado de `Flow` + `BodyComponent.testid` em runtime/build.

| Campo | Tipo | Origem | Validação |
|-------|------|--------|-----------|
| `flow_ref` | `Flow` (referência) | — | — |
| `coords` | `{x, y, w, h}` (todos `0-1`) | Capture script via `boundingBox` | [V] Todos no range `[0, 1]` |
| `badge_index` | `number` (1-N) | Renderer atribui | Numeração sequencial dentro da tela |
| `aria_label` | `string` | Renderer deriva (`flow.label || ` "Vai para tela ${flow.to}"`) | — |

**Não é serializado no YAML** — é derivado em build-time pelo renderer e em runtime pelo capture.

---

## E6. CaptureProfile

Configuração de viewport e captura.

**Source**: enum closed em `screen-flow.schema.json`

| Profile | Width | Height | Device descriptor (Playwright) |
|---------|-------|--------|-------------------------------|
| `iphone-15` | 393 | 852 | `'iPhone 15'` (built-in Playwright preset) |
| `desktop` | 1440 | 900 | `null` (configuração manual de `viewport`) |

**Extensibilidade**: novos profiles são adições aditivas ao schema (incrementam `schema_version` se removerem profile existente). Caso de uso atual: 2 profiles cobrem 100% das plataformas-alvo do v1.

---

## E7. PlatformScreenFlowConfig

Bloco em `platform.yaml`.

**Source**: `platforms/<name>/platform.yaml` campo `screen_flow:`

| Campo | Tipo | Obrigatório quando | Validação |
|-------|------|-------------------|-----------|
| `enabled` | `boolean` | Sempre (quando bloco presente) | — |
| `skip_reason` | `optional<string>` (10-500 chars) | Quando `enabled: false` | [L] Vazio inválido (FR-006) |
| `capture` | `optional<CaptureConfig>` | Quando `enabled: true` | [L] Estrutura validada (FR-007) |

**Bloco `CaptureConfig`**:

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `base_url` | `string` (URL) | Sim | URL pública do staging (ex: `https://dev.resenhai.com`) |
| `serve` | `optional<{command, ready_url, ready_timeout}>` | Não | Para CI rodar build local antes de capturar (não usado no resenhai-expo, staging é permanente) |
| `device_profile` | `enum<iphone-15, desktop>` | Sim | Profile default da plataforma |
| `auth` | `AuthConfig` | Sim | Ver E11 |
| `determinism` | `DeterminismConfig` | Sim | Ver E10 |
| `expo_web` | `optional<{enabled: bool, incompatible_deps?: array<string>}>` | Não | Hint pra CI saber se precisa rodar `expo export -p web` |
| `path_rules` | `array<PathRule>` | Sim | Ver E8 — drift detection |
| `test_user_marker` | `string` | Sim | [L] Identificador do test user para auditoria PII (FR-047) |

---

## E8. PathRule

Regra de mapeamento arquivo→screen (drift detection).

**Source**: item de `platform.yaml.screen_flow.capture.path_rules[]`

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `pattern` | `string` (regex válida) | Sim | [L] Compila como regex Python — sintaxe inválida rejeitada |
| `screen_id_template` | `string` | Sim | Suporta placeholders `{1}`, `{2}` referenciando grupos da regex |

**Exemplos** (resenhai-expo):
```yaml
path_rules:
  - { pattern: 'app/\(auth\)/(\w+)\.tsx',          screen_id_template: '{1}' }
  - { pattern: 'app/\(app\)/(\w+)\.tsx',           screen_id_template: '{1}' }
  - { pattern: 'app/\(app\)/(\w+)/(\w+)\.tsx',     screen_id_template: '{1}_{2}' }
```

**Aplicação em `reverse_reconcile_aggregate.py`**:
1. Para cada arquivo modificado em commit, tenta cada `pattern` em ordem
2. Primeiro match resolve `screen_id_template` substituindo grupos
3. Resultado vira chave para enfileirar patch JSON em `screen_flow_mark_pending.py`

---

## E9. DeterminismConfig

Configuração para captura reprodutível.

**Source**: `platform.yaml.screen_flow.capture.determinism`

| Campo | Tipo | Default | Aplicação no capture script |
|-------|------|---------|----------------------------|
| `freeze_time` | `optional<ISO8601 string>` | None (no freeze) | `addInitScript` overrides `Date.now()` retornando timestamp parseado |
| `random_seed` | `optional<number>` | None (no override) | `addInitScript` overrides `Math.random()` com PRNG seeded (xorshift) |
| `disable_animations` | `boolean` | `true` | `addStyleTag` injeta `*, *::before, *::after { animation-duration: 0s !important; transition-duration: 0s !important; }` |
| `clear_service_workers` | `boolean` | `false` | Pré-`page.goto` chama `serviceWorker.unregister()` + `caches.delete()` (FR-031) |
| `clear_cookies_between_screens` | `boolean` | `false` | Pré-`page.goto` chama `context.clearCookies()` |
| `mock_routes` | `array<MockRoute>` | `[]` | Cada item registra `page.route(match, fulfill(body))` |

**MockRoute**:

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `match` | `string` (glob ou regex Playwright) | Sim | Ex: `**/api/notifications/unread` |
| `body` | `optional<any>` | Um de body/status | JSON body de retorno |
| `status` | `optional<number>` | Um de body/status | HTTP status code (default 200) |

---

## E10. AuthConfig

Configuração de autenticação para capture.

**Source**: `platform.yaml.screen_flow.capture.auth`

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `type` | `enum<storage_state>` | Sim | v1 só suporta storage_state |
| `setup_command` | `string` | Sim | Comando para regerar storageState (ex: `npx playwright test --project=auth-setup`) |
| `storage_state_path` | `string` | Sim | Path relativo ao repo da plataforma (ex: `e2e/.auth/user.json`) |
| `test_user_env_prefix` | `string` (CAPS) | Sim | Prefixo de env vars (ex: `RESENHAI` → `RESENHAI_TEST_EMAIL` + `RESENHAI_TEST_PASSWORD`) |

**Validação operacional**:
- Credenciais SEMPRE via env vars; arquivo `.json` do storageState contém apenas cookies/localStorage (artefato gerado, não checked-in)
- `setup_command` é executado quando o capture detecta storageState ausente ou expirado (>24h de idade)

---

## E11. CaptureRecord & CaptureFailure

**CaptureRecord** (preenchido quando `Screen.status = captured`):

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `captured_at` | `ISO8601 string` | Sim | Timestamp de conclusão do capture |
| `app_version` | `string` (git sha curto) | Sim | SHA do commit do app no momento da captura |
| `image_md5` | `string` (hex) | Sim | MD5 do PNG final — usado para verificar determinism nos próximos runs |
| `viewport` | `{w: number, h: number}` | Sim | Dimensões reais usadas |

**CaptureFailure** (preenchido quando `Screen.status = failed`):

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `reason` | `enum<timeout, auth_expired, network_error, app_crash, sw_cleanup_failed, mock_route_unmatched, unknown>` | Sim | FR-045 |
| `occurred_at` | `ISO8601 string` | Sim | Timestamp da última falha |
| `retry_count` | `number` (0-3) | Sim | Quantos retries foram tentados |
| `last_error_message` | `optional<string>` (max 500 chars) | Não | Stack trace truncada |

---

## Relacionamentos

```text
PlatformYaml
  └─ screen_flow: PlatformScreenFlowConfig (E7)
        ├─ capture: CaptureConfig
        │     ├─ auth: AuthConfig (E10)
        │     ├─ determinism: DeterminismConfig (E9)
        │     │     └─ mock_routes: array<MockRoute>
        │     └─ path_rules: array<PathRule> (E8)
        │           └─ usado por reverse_reconcile_aggregate.py
        └─ enabled / skip_reason

ScreenFlow (E1) [YAML por plataforma]
  ├─ meta: MetaConfig
  ├─ screens: array<Screen> (E2)
  │     ├─ body: array<BodyComponent> (E3)
  │     ├─ capture: CaptureRecord (E11) [quando status=captured]
  │     └─ failure: CaptureFailure (E11) [quando status=failed]
  └─ flows: array<Flow> (E4)
        └─ on: refers BodyComponent.id
        └─ from/to: refers Screen.id

Hotspot (E5) [derivado em build-time/runtime]
  ├─ flow_ref: Flow (E4)
  └─ coords: derivado via Playwright boundingBox de [data-testid="<BodyComponent.testid>"]
```

---

## Validações Globais (`screen_flow_validator.py`)

Implementadas em camada acima do JSON Schema (cross-field):

1. **Charset de IDs** — todos os `screen.id` e `body[].id` casam com regex `^[a-z][a-z0-9_]{0,63}$`
2. **Refs consistentes** — `flow.from`/`flow.to` casam com `screens[].id`; `flow.on` casa com `body[].id` da tela `from`
3. **IDs únicos** — sem duplicatas em `screens[].id`; sem duplicatas em `body[].id` dentro da mesma tela
4. **Status consistency** — `image` populado ⇔ `status=captured`; `failure` populado ⇔ `status=failed`
5. **Acyclic OR positioned** — DAG de flows sem ciclos OU telas em ciclos têm `position` manual
6. **Capture profile match** — `meta.capture_profile` consistente com `platform.yaml.screen_flow.capture.device_profile`
7. **Schema version known** — `schema_version` é uma das versões suportadas (atualmente só `1`)
8. **Scale limits** — warn em `len(screens) > 50`, hard reject em `> 100`
9. **Body non-empty** — `screens[].body` tem `len >= 1`
10. **testid presence** — para flows referenciando body components em telas `status=captured`, o body tem `testid` declarado

---

## Estados e Transições — Resumo

| Entidade | Campo | Estados | Transições válidas |
|----------|-------|---------|-------------------|
| Screen | `status` | `pending`, `captured`, `failed` | Ver E2 state machine |
| PlatformScreenFlowConfig | `enabled` | `false`, `true` | Mudança requer review humano + ADR (1-way-door) |

---

## Notas Adicionais

- **Imutabilidade de IDs**: `screen.id` é considerada parte do contrato externo (referenciada em flows, em path_rules, em filenames de PNGs). Renomear é breaking change — exige migração explícita.
- **Versionamento de telas**: NÃO modelado no v1. Se a UX da tela mudar drasticamente, autor pode (a) atualizar o YAML in-place (drift detection captura), ou (b) deprecar `id` antigo e introduzir novo (manual).
- **Multi-language**: PT-BR para `title`, `text`, `label`. Vocabulário enum (types, styles, badges) sempre em inglês para consistência code/yaml/schema.
