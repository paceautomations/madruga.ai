---
epic: 027-screen-flow-canvas
phase: phase-1
created: 2026-05-05
sidebar:
  order: 4
---

# Quickstart — Screen Flow Canvas

Guia operacional pós-epic. Como habilitar a feature numa plataforma, como rodar capture localmente e via CI, como debugar e como interpretar estados.

---

## 1. Habilitar a feature numa plataforma

### 1.1. Editar `platforms/<name>/platform.yaml`

```yaml
screen_flow:
  enabled: true
  capture:
    base_url: "https://staging.<minha-plataforma>.com"
    device_profile: iphone-15           # ou: desktop
    test_user_marker: "demo+playwright@<minha-plataforma>.com"
    auth:
      type: storage_state
      setup_command: "npx playwright test --project=auth-setup"
      storage_state_path: "e2e/.auth/user.json"
      test_user_env_prefix: "MINHAPLATAFORMA"
    determinism:
      freeze_time: "2026-01-01T12:00:00Z"
      random_seed: 42
      disable_animations: true
      clear_service_workers: true     # crítico se app tem SW
      clear_cookies_between_screens: true
      mock_routes:
        - { match: "**/api/notifications/unread", body: { count: 0 } }
    expo_web:
      enabled: true                    # se aplicável
    path_rules:
      - { pattern: 'app/\(auth\)/(\w+)\.tsx', screen_id_template: '{1}' }
      - { pattern: 'src/screens/(\w+)Screen\.tsx', screen_id_template: '{1}' }
```

### 1.2. Validar o lint

```bash
python3 .specify/scripts/platform_cli.py lint <name>
```

Saída esperada: `✓ Platform <name> manifest valid (screen_flow: enabled, capture configured)`.

### 1.3. Gerar `business/screen-flow.yaml` via skill

```bash
/madruga:business-screen-flow <name>
```

A skill:
1. Verifica que `platforms/<name>/business/process.md` existe (rejeita se ausente).
2. Lê as user journeys do process.md.
3. Propõe um conjunto inicial de screens derivadas das jornadas.
4. (Opcional) Parseia `e2e/tests/**/*.spec.ts` e sugere `testid` disponíveis.
5. Pede confirmação humana antes de gravar `screen-flow.yaml`.

Saída: `platforms/<name>/business/screen-flow.yaml` com `schema_version: 1`, telas em `status: pending`.

### 1.4. Habilitar a aba no portal

Nada a fazer — o portal detecta `screen_flow.enabled: true` + presença de `business/screen-flow.yaml` automaticamente e adiciona entry "Screens" ao sidebar.

---

## 2. Capturar telas localmente

### 2.1. Configurar credenciais do test user

```bash
export MINHAPLATAFORMA_TEST_EMAIL=demo+playwright@<minha-plataforma>.com
export MINHAPLATAFORMA_TEST_PASSWORD=...
```

> Use **prefixo** declarado em `auth.test_user_env_prefix` no `platform.yaml`.

### 2.2. Gerar storageState (uma vez)

Se `e2e/.auth/user.json` ainda não existe ou está expirado:

```bash
cd <repo-da-plataforma>
npx playwright test --project=auth-setup
```

Isso loga o test user e grava cookies/localStorage. Reusable em todos os capture runs subsequentes.

### 2.3. Rodar capture

```bash
cd /home/gabrielhamu/repos/paceautomations/madruga.ai
python3 .specify/scripts/capture/screen_capture.py <name>
```

Saída esperada:
- Logs JSONL no stdout (filtre com `jq` se quiser)
- PNGs em `platforms/<name>/business/shots/<screen_id>.png`
- `screen-flow.yaml` atualizado (status `captured` + bloco `capture` populado)

### 2.4. Capture de uma tela só (debug)

```bash
python3 .specify/scripts/capture/screen_capture.py <name> --screen login --dry-run
```

Modo `--dry-run` simula sem escrever PNG nem alterar YAML — útil para iterar mocks/determinism config.

---

## 3. Capturar via CI (GitHub Actions)

```bash
gh workflow run capture-screens.yml -f platform=<name>
```

O workflow:
1. Checkout do repo da plataforma (com `lfs: true` apenas pra ler a baseline).
2. Roda Playwright contra `base_url` (ou `serve.command` se declarado).
3. Aplica `concurrency: { group: "capture-<name>", cancel-in-progress: false }` — segundo dispatch enfileira.
4. Executa capture script.
5. Commit + push do YAML atualizado e PNGs (LFS) na branch epic ou main (conforme config).

### Acompanhar progresso

```bash
gh run list --workflow=capture-screens.yml -L 5
gh run view --log-failed     # se falhar
```

### 3.1. Configurar GH Secrets para o pilot resenhai (T072)

O workflow `capture-screens.yml` precisa de credenciais do test user da plataforma para reusar o `storageState` Playwright. Para o pilot resenhai, configurar 2 secrets na org `paceautomations`:

```bash
gh secret set RESENHAI_TEST_EMAIL    --org paceautomations --body "demo+playwright@resenhai.com"
gh secret set RESENHAI_TEST_PASSWORD --org paceautomations --body "<senha-do-test-user>"
```

Confirmar que o repo `madruga.ai` tem visibilidade dos secrets:

```bash
gh secret list --org paceautomations | grep RESENHAI
```

Para outras plataformas, usar o prefixo declarado em `platform.yaml.screen_flow.capture.auth.test_user_env_prefix` — o workflow lê `<PREFIX>_TEST_EMAIL` e `<PREFIX>_TEST_PASSWORD` do environment.

### 3.2. Storage state setup no resenhai-expo

O `storageState` real é gerado pelo arquivo `e2e/auth.setup.ts` que **já existe** no repo `paceautomations/resenhai-expo`. O workflow assume que o test user é válido e o `setup_command` regenera o JSON quando necessário.

Pré-condição manual (uma vez por janela do epic):

```bash
# No clone do resenhai-expo
cd /path/to/resenhai-expo
RESENHAI_TEST_EMAIL=... RESENHAI_TEST_PASSWORD=... \
  npx playwright test --project=auth-setup
git diff e2e/.auth/user.json   # confirmar geração
```

Se o test user não existir mais no Supabase staging, recriar via console e atualizar `RESENHAI_TEST_PASSWORD` antes de re-rodar o workflow.

### 3.3. Troubleshooting de PNG noise

| Sintoma | Causa provável | Remediation |
|---------|---------------|-------------|
| md5 muda entre runs (>20% das telas) | Element não-determinístico não coberto por mocks | Adicionar `mock_route` em `determinism.mock_routes` para a request volátil; OU declarar `[data-volatile]` no app (escalada gradual conforme Decision #8) |
| `reason: sw_cleanup_failed` recorrente | Service Worker não responde a `unregister()` | Forçar hard-reload antes do cleanup; investigar bug do app — não-fatal mas degrada determinism |
| `reason: timeout` em telas autenticadas | Auth expirada em meio à corrida | Regenerar `e2e/.auth/user.json` (§3.2) e re-disparar workflow |
| PNG >500KB rejeitado pelo pre-commit | Imagens decorativas pesadas no DOM real | (a) reduzir viewport, (b) declarar `mock_route` retornando placeholder leve, (c) capturar `clip:` no spec ao invés de `fullPage` (já é default false) |
| Workflow exits 1 mas YAML committado | ≥1 tela com `status: failed` (esperado per FR-046) | Ler `failure.reason` na YAML, decidir entre re-rodar workflow OU ajustar config |
| `auth_setup_failed` no log do orchestrator | `<PREFIX>_TEST_EMAIL`/`_PASSWORD` ausente | Configurar GH Secrets (§3.1) ou exportar localmente |

---

## 4. Visualizar no portal

```bash
cd portal && npm run dev
# abre http://localhost:4321/<name>/screens
```

Interações disponíveis:
- **Pan**: arrastar mouse / `WASD`
- **Zoom**: scroll / `+` `-`
- **Click em hotspot numerado**: anima aresta e move câmera para tela destino
- **Tecla `H`**: toggla visibilidade dos hotspots (autor pode tirar screenshot "limpa")
- **Tab + Enter**: keyboard navigation (a11y compliant)

### Modo dev com fixture (sem YAML real)

```text
http://localhost:4321/<name>/screens?fixture=true
```

Carrega `portal/src/test/fixtures/screen-flow.example.yaml` — útil para desenvolver renderer sem depender de captura real.

---

## 5. Interpretar estados

### 5.1. Badges no canvas

| Badge | Significado |
|-------|-------------|
| `WIREFRAME` | Tela em mockup (status: pending OR sem image) |
| `AGUARDANDO` | Drift detectado, aguarda próximo capture (status: pending após reverse-reconcile) |
| `WEB BUILD v<x>` | Captura web do Expo Web ou web puro |
| `iOS v<x>` | Captura native (não usado no v1, reservado pra futuro) |
| `WEB v<x>` | Captura desktop web |
| `FALHOU` | Status: failed; tooltip mostra `failure.reason` |

### 5.2. `status: failed` no YAML

```yaml
- id: home
  status: failed
  failure:
    reason: timeout
    occurred_at: "2026-05-05T14:32:00Z"
    retry_count: 3
    last_error_message: "page.goto: Timeout 30000ms exceeded."
```

Próximas ações:
1. **Investigar a `reason`**: timeout → staging instável; auth_expired → regenerar storageState; mock_route_unmatched → revisar `mock_routes`.
2. **Re-rodar capture** (`gh workflow run capture-screens.yml -f platform=<name>`) — basta a tela voltar para `pending` (drift) ou status mudar diretamente.
3. **Status `failed` permanente** se app está broken — autor revisa pitch da plataforma.

---

## 6. Drift detection

Após mudanças em arquivos de tela do app:

```bash
# No clone da plataforma (ex: paceautomations/resenhai-expo)
git commit -am "feat: redesign login form"
git push

# No madruga.ai
python3 .specify/scripts/reverse_reconcile_ingest.py --platform resenhai-expo
python3 .specify/scripts/reverse_reconcile_classify.py --platform resenhai-expo --out triage.json
python3 .specify/scripts/reverse_reconcile_aggregate.py --platform resenhai-expo --triage triage.json --out work.json
# Aggregate lê path_rules e enfileira patches para screen_flow_mark_pending.py

python3 .specify/scripts/reverse_reconcile_apply.py --patches work.json --commit
# Reescreve screen-flow.yaml setando capture.status: pending nas telas afetadas
```

Próximo capture run (manual ou auto-trigger) recaptura.

---

## 7. Test pyramid (DoD do epic)

### Layer (a) — Unit Python

```bash
make test
# ou: pytest .specify/scripts/screen_flow_validator_test.py -v
```

≥30 casos cobrindo: vocabulário inválido, refs broken, ID duplicado, schema_version desconhecido, charset errado, scale limits.

### Layer (b) — Component React

```bash
cd portal && npm run test:component
# ou: npx vitest run src/test/unit/
```

ScreenNode (3 estados), ActionEdge (4 styles), Hotspot (numerado + dashed).

### Layer (c) — Visual

```bash
cd portal && npm run test:visual
# ou: npx playwright test src/test/visual/
```

Snapshot do canvas com fixture de 8 telas, toleração 1px diff via `jest-image-snapshot`.

### Layer (d) — E2E

```bash
cd portal && npm run test:e2e
# ou: npx playwright test src/test/e2e/
```

1 spec integrando capture→commit→render contra fixture mock. Pode rodar offline (sem credentials reais).

---

## 8. Bundle budget gate

```bash
cd portal && npm run size
# ou: npx size-limit
```

Saída esperada:
```text
✓ /<platform>/screens/* —  812 KB (limit: 900 KB)
✓ /<platform>/index.astro — 245 KB (limit: 280 KB)
```

Falha de build se exceder. Plano B se inflar: code splitting interno (lazy import `Chrome.tsx` + `WireframeBody.tsx`).

---

## 9. Opt-out de uma plataforma

Se a plataforma não tem "telas" no sentido tradicional (ex: tooling, headless API):

```yaml
# platforms/<name>/platform.yaml
screen_flow:
  enabled: false
  skip_reason: |
    Plataforma de tooling — não tem app de usuário no sentido tradicional.
    Reabilitar quando aplicável.
```

Resultado:
- Aba **Screens** não aparece no portal pra essa plataforma
- Skill `madruga:business-screen-flow` rejeita execução
- Reverse-reconcile skipa silenciosamente o módulo screen-flow

---

## 10. Troubleshooting comum

| Problema | Diagnóstico | Solução |
|----------|-------------|---------|
| `lint` falha: `screen_flow.skip_reason required when enabled=false` | Bloco mal formado | Adicionar `skip_reason` ou setar `enabled: true` |
| `lint` falha: `capture.test_user_marker required when enabled=true` | Marker ausente | Adicionar `test_user_marker: "<email>"` (FR-047) |
| Skill rejeita: `business/process.md not found` | process.md não gerado ainda | Rodar `/madruga:business-process <name>` antes |
| Validator rejeita: `Unknown schema_version: 99` | YAML com versão errada | Corrigir para `schema_version: 1`; check migration path se vier v2 |
| Capture exit 2 + `auth_setup_failed` | env vars de credentials ausentes | Configurar GH Secrets ou exportar localmente |
| 2 runs com PNGs diferentes (md5 mismatch >20%) | Determinism layer insuficiente | Adicionar `mock_route` para endpoint volátil identificado; escalada `data-volatile` no app só em último caso |
| Bundle gate falha em PR não relacionado | Regressão indireta (alguma dep aumentou) | `npm run size --why` mostra culpado; rebaseline ou code split |
| LFS bandwidth próximo de 800MB/mês | Workflows com `lfs: true` excessivo | Migrar pra `actions/checkout@v4` com `lfs: false` exceto onde estritamente necessário |
| Aba Screens não aparece em plataforma habilitada | YAML inexistente OR routeData não detectou | Verificar `platforms/<name>/business/screen-flow.yaml` existe; rebuild portal |

---

## 11. Próximos passos depois do epic

Conforme NO-GO list explícito, fora de escopo v1 mas possíveis follow-ups:

- **Captura native real (Maestro/simulator)** — epic futuro `screen-capture-native`
- **Multi-device matrix** (iPad, Pixel, etc.) — epic futuro
- **Visual regression testing** (Percy/Chromatic) — concern separado
- **Live editing no portal** — atualmente read-only viewer
- **Diff before/after entre captures** — feature explicitamente cortada
- **Migração LFS → Vercel Blob** — quando bandwidth >800MB/mês ou storage >300MB (Decision #22)
