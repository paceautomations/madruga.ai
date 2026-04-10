---
type: qa-report
date: 2026-04-09
feature: "001 — Channel Pipeline"
branch: "epic/prosauai/001-channel-pipeline"
layers_executed: ["L1", "L2", "L3", "L4"]
layers_skipped: ["L5", "L6"]
findings_total: 6
pass_rate: "97%"
healed: 2
unresolved: 0
---

# QA Report — 001 Channel Pipeline

**Data:** 09/04/2026 | **Branch:** epic/prosauai/001-channel-pipeline | **Arquivos alterados:** 32
**Camadas executadas:** L1, L2, L3, L4 | **Camadas ignoradas:** L5 (sem servidor rodando), L6 (Playwright indisponível)

## Resumo

| Status | Quantidade |
|--------|------------|
| ✅ PASS | 128 |
| 🔧 HEALED | 2 |
| ⚠️ WARN | 2 |
| ❌ UNRESOLVED | 0 |
| ⏭️ SKIP | 2 |

---

## Detecção de Ambiente

| Camada | Status | Detalhes |
|--------|--------|----------|
| L1: Análise Estática | ✅ Ativa | ruff check, ruff format |
| L2: Testes Automatizados | ✅ Ativa | pytest (122 testes, 5 arquivos de teste) |
| L3: Revisão de Código | ✅ Ativa | 32 arquivos alterados (14 source, 8 test, 10 config/infra) |
| L4: Build | ✅ Ativa | Import smoke test (sem build script dedicado) |
| L5: API Testing | ⏭️ Skip | Sem servidor rodando |
| L6: Browser Testing | ⏭️ Skip | Playwright indisponível (projeto backend/API) |

---

## L1: Análise Estática

| Ferramenta | Resultado | Achados |
|------------|----------|---------|
| ruff check | ✅ Clean | Zero erros |
| ruff format | ✅ Clean | 25 arquivos formatados corretamente |

---

## L2: Testes Automatizados

| Suite | Passou | Falhou | Ignorados |
|-------|--------|--------|-----------|
| pytest | 122 | 0 | 0 |

**Tempo de execução:** 1.16s

**Distribuição de testes:**
- `tests/unit/test_router.py` — 18 testes (6 rotas + edge cases + handoff stub)
- `tests/unit/test_formatter.py` — 19 testes (10 tipos de mensagem)
- `tests/unit/test_debounce.py` — 23 testes (buffer, flush, jitter, fallback, script)
- `tests/unit/test_evolution_provider.py` — 12 testes (send_text, send_media, erros)
- `tests/unit/test_hmac.py` — 7 testes (HMAC válido, inválido, ausente, constant-time)
- `tests/integration/test_webhook.py` — 38 testes (fluxo completo, grupos, debounce, edge cases)
- `tests/integration/test_health.py` — 5 testes (ok, degradado, timeout)

**Cobertura por User Story:**
- US1 (Mensagem Individual): 10+ testes ✅
- US2 (HMAC Security): 7+ testes ✅
- US3 (Smart Router Grupos): 13+ testes ✅
- US4 (Debounce): 27+ testes ✅
- US5 (Health + Docker): 5+ testes ✅
- US6 (Handoff Stub): 5+ testes ✅

---

## L3: Revisão de Código

| Arquivo | Achado | Severidade | Status |
|---------|--------|-----------|--------|
| `prosauai/core/formatter.py:149` | PII em log: `phone=phone[:8]+"…"` loga prefixo do telefone em vez de hash SHA-256. Inconsistente com o padrão usado em `webhooks.py`, `evolution.py` e `debounce.py` que usam `phone_hash`. Judge report W8 corrigiu os outros módulos mas perdeu este. | S2 | 🔧 HEALED |
| `prosauai/api/webhooks.py:104` | Log duplicado para GROUP_SAVE_ONLY: `group_message_saved` (linha 94) e `webhook_processed` (linha 104) disparam para a mesma mensagem, gerando verbosidade desnecessária. FR-010 exige apenas o primeiro. | S3 | 🔧 HEALED |
| `prosauai/core/router.py:64` | `HealthResponse` definido em `router.py` mas usado exclusivamente por `api/health.py`. Viola single-responsibility — schema de health misturado com routing. | S4 | ⚠️ WARN |
| `prosauai/api/dependencies.py:57-84` | `get_redis()` dependency definida mas nunca usada por nenhum endpoint. Health acessa `request.app.state.redis` diretamente. Dead code arquitetural. | S4 | ⚠️ WARN |

**Análise detalhada dos módulos:**

### `prosauai/core/router.py` — Smart Router
- ✅ `from_me` é o primeiro check (FR-005)
- ✅ 6 rotas com enum StrEnum — correto e extensível
- ✅ `_is_bot_mentioned()` usa dual strategy: phone JID + keyword regex case-insensitive
- ✅ `_is_handoff_ativo()` stub correto — retorna `False`, signature pronta para epic 005
- ✅ `RouteResult.agent_id` presente como `None` (forward-compat epic 003)
- ✅ Regex usa `re.escape()` nas keywords — seguro contra injection

### `prosauai/core/formatter.py` — Message Parser
- ✅ `ParsedMessage` com validação Pydantic (min_length nos campos críticos)
- ✅ Suporta 10 tipos de mensagem (conversation, extendedText, image, document, video, audio, sticker, contact, location, protocolMessage)
- ✅ `MalformedPayloadError` com `detail` para HTTP 400
- ✅ Timestamp com fallback para `datetime.now(UTC)` em caso de parsing error
- ✅ `_extract_mentions()` limitada a extendedText — compensada por keyword regex no router
- ✅ `format_for_whatsapp()` passthrough — seam documentada para epic 002

### `prosauai/core/debounce.py` — Debounce Manager
- ✅ Dual-key pattern (buf: + tmr:) com Lua script atômico
- ✅ Jitter 0-1s no timer TTL (anti-avalanche)
- ✅ Safety TTL 2x no buffer key (garante cleanup)
- ✅ `append_or_immediate()` com fallback para Redis down (FR-007/D4)
- ✅ Keyspace listener com reconnect + exponential backoff (max 10 tentativas, max 30s delay)
- ✅ Flush despachado como `asyncio.create_task()` independente (pipeline não-bloqueante)
- ✅ `_hash_phone()` helper consistente para logs seguros
- ✅ `parse_expired_key()` usa `rfind(":")` para separar phone (contém @) do context

### `prosauai/api/webhooks.py` — Webhook Handler
- ✅ HMAC validação via `verify_webhook_signature()` no início do pipeline
- ✅ `_ACTIVE_ROUTES` frozenset para rotas que geram echo
- ✅ `_make_flush_fallback()` closure para fallback sem debounce
- ✅ `_send_echo()` com provider compartilhado (via `app.state`) + fallback temporário
- ✅ Status "ignored" explícito para rota ativa sem texto (media-only) — fix W4 do judge
- ✅ `phone_hash` SHA-256 em todos os logs

### `prosauai/api/dependencies.py` — HMAC Verification
- ✅ `verify_webhook_signature()` computa HMAC sobre raw body bytes (não JSON re-serializado)
- ✅ `hmac.compare_digest()` para comparação constant-time
- ✅ Retorna raw body para reuso (evita re-leitura do stream)

### `prosauai/channels/evolution.py` — Evolution Provider
- ✅ httpx `AsyncClient` com timeout 30s
- ✅ `apikey` header padronizado
- ✅ Error handling: `HTTPStatusError` e `RequestError` logados e dropped (FR-009)
- ✅ `number_hash` com SHA-256 em logs (fix W8 do judge)
- ✅ `close()` para cleanup do client

### `prosauai/main.py` — App Entrypoint
- ✅ Lifespan com setup e teardown corretos (Redis, DebounceManager, Provider)
- ✅ Provider compartilhado em `app.state.provider` (fix W2 do judge)
- ✅ `_mask_redis_url()` para segurança em logs (fix W7 do judge)
- ✅ structlog configurado com JSON output, timestamper, integração uvicorn
- ✅ `_get_flush_callback()` closure sobre app — flush via provider compartilhado

### `prosauai/config.py` — Settings
- ✅ pydantic-settings com `SettingsConfigDict` (env_file .env)
- ✅ 5 campos required sem default, 7 opcionais com defaults sensatos
- ✅ `mention_keywords_list` property para parsing de keywords comma-separated

### Infraestrutura
- ✅ `Dockerfile` multi-stage (builder + runtime), non-root user, healthcheck
- ✅ `docker-compose.yml` com api + redis, keyspace notifications habilitadas, healthcheck Redis
- ✅ `.env.example` completo com 12 campos documentados
- ✅ `pyproject.toml` com ruff, pytest-asyncio (auto mode), deps versionadas

---

## L4: Build Verification

| Verificação | Resultado | Detalhes |
|------------|----------|---------|
| Import prosauai.main | ✅ PASS | Sem erros de importação |
| Import todos os módulos | ✅ PASS | config, formatter, router, debounce, base, evolution, dependencies, health |
| ruff check (pós-fix) | ✅ PASS | Zero erros |
| ruff format (pós-fix) | ✅ PASS | 25 arquivos formatados |

---

## L5: API Testing

⏭️ Servidor não rodando — camada ignorada.

---

## L6: Browser Testing

⏭️ Projeto backend/API sem interface web. Playwright indisponível.

---

## Heal Loop

| # | Camada | Achado | Iterações | Fix | Status |
|---|--------|--------|-----------|-----|--------|
| 1 | L3 | PII em `formatter.py:149` — `phone[:8]+"…"` em vez de hash | 1 | Substituído por `hashlib.sha256(phone.encode()).hexdigest()[:12]` + adicionado `import hashlib` | 🔧 HEALED |
| 2 | L3 | Log duplicado para GROUP_SAVE_ONLY em `webhooks.py:104` | 1 | Adicionado `if result.route != MessageRoute.GROUP_SAVE_ONLY:` para evitar `webhook_processed` duplicado | 🔧 HEALED |

**Reteste pós-heal:**
- ruff check: ✅ Zero erros
- ruff format: ✅ 25 arquivos formatados
- pytest: ✅ 122 testes passando (1.16s)

---

## Arquivos Alterados (pelo heal loop)

| Arquivo | Linha | Mudança |
|---------|-------|---------|
| `prosauai/core/formatter.py` | 5, 149 | Adicionado `import hashlib`. Substituído `phone=phone[:8]+"…"` por `phone_hash=hashlib.sha256(phone.encode()).hexdigest()[:12]` |
| `prosauai/api/webhooks.py` | 104 | Adicionado guard `if result.route != MessageRoute.GROUP_SAVE_ONLY:` para evitar log duplicado |

---

## Verificação dos Achados Upstream

### analyze-post-report.md — Resolução

| Finding | Status QA | Notas |
|---------|-----------|-------|
| P1 (append vs append_or_immediate) | ✅ Confirmado FIXED | `webhooks.py:75` usa `append_or_immediate()` com `_make_flush_fallback()` |
| P2 (media-only status "queued") | ✅ Confirmado FIXED | Linha 84-86: rota ativa sem texto retorna `status="ignored"` |
| P3 (close no fallback) | ✅ Confirmado FALSO POSITIVO | `finally` garante `close()` |
| P4 (log duplicado GROUP_SAVE_ONLY) | 🔧 HEALED | Corrigido neste QA — guard adicionado |
| P5 (_extract_mentions limitada) | ✅ Confirmado ACEITO | Keyword regex compensa no router |
| P6 (provider novo a cada flush) | ✅ Confirmado FIXED | Provider compartilhado via `app.state.provider` |
| P7 (log de descarte no handler) | ✅ Confirmado ACEITO | Log no provider é suficiente |

### judge-report.md — Resolução

| Finding | Status QA | Notas |
|---------|-----------|-------|
| B1 (append → append_or_immediate) | ✅ Confirmado FIXED | Verificado no código |
| W1 (listener reconnect) | ✅ Confirmado FIXED | Exponential backoff implementado (max 10 tentativas, 30s delay) |
| W2 (provider compartilhado) | ✅ Confirmado FIXED | `app.state.provider` criado no lifespan |
| W3 (ACL boundary) | ✅ Confirmado FIXED | Path principal usa provider compartilhado |
| W4 (media-only status) | ✅ Confirmado FIXED | Retorna "ignored" explicitamente |
| W5 (body size limit) | ⚠️ OPEN | Aceitável para epic 001 — webhook interno |
| W6 (flush sequencial) | ✅ Confirmado FIXED | `asyncio.create_task()` + `_flush_tasks` set |
| W7 (Redis URL em logs) | ✅ Confirmado FIXED | `_mask_redis_url()` implementada |
| W8 (PII em logs) | 🔧 HEALED parcial | evolution.py e debounce.py corrigidos pelo judge. **formatter.py:149 tinha o mesmo problema** — corrigido neste QA |
| N1 (HealthResponse location) | ⚠️ OPEN | Menor — mover no próximo refactor |
| N2 (get_redis unused) | ⚠️ OPEN | Manter por ora — potencialmente útil em epics futuros |
| N3 (_MEDIA_NO_URL_TYPES) | ✅ Confirmado FIXED | Constante removida |
| N4 (_extract_mentions limitada) | ⚠️ OPEN | Compensada por keyword regex |

---

## Cobertura de Requisitos Funcionais

| Requisito | Testado? | Evidência |
|-----------|----------|-----------|
| FR-001 (Webhook endpoint) | ✅ | 38 integration tests |
| FR-002 (HMAC-SHA256) | ✅ | 7 unit + 7 integration |
| FR-003 (Parse payload) | ✅ | 19 unit tests (10 tipos) |
| FR-004 (6 rotas) | ✅ | 18 unit + integration |
| FR-005 (from_me first) | ✅ | Testes explícitos |
| FR-006 (@mention) | ✅ | 6 testes (phone JID + keywords) |
| FR-007 (Debounce 3s+jitter) | ✅ | 23 unit + 4 integration |
| FR-008 (Redis Lua + keyspace) | ✅ | Script SHA + listener tests |
| FR-009 (Echo response) | ✅ | Integration + provider unit |
| FR-010 (Log GROUP_SAVE_ONLY) | ✅ | Integration test explícito |
| FR-011 (GET /health) | ✅ | 5 integration tests |
| FR-012 (Send text + media) | ✅ | 12 unit tests |
| FR-013 (RouteResult agent_id) | ✅ | Testes explícitos |
| FR-014 (Config externalizada) | ✅ | pydantic-settings + .env.example |
| FR-015 (Docker Compose) | ✅ | docker-compose.yml + Dockerfile |

---

## Lições Aprendidas

1. **PII leak pattern**: Judge report W8 corrigiu evolution.py e debounce.py mas perdeu formatter.py:149 — mesmo padrão (`phone[:8]`). QA grep por patterns de PII em todos os módulos revelou o gap. **Recomendação**: criar ruff rule ou grep check no CI para `phone[:\[]` em logs.

2. **Log duplicado sutil**: `webhook_processed` é um log genérico útil, mas para GROUP_SAVE_ONLY há um log específico anterior (`group_message_saved`). Sem o guard, cada mensagem de grupo sem @mention gera 2 linhas de log idênticas em conteúdo. **Impacto**: custo de storage em ambientes com alto volume de mensagens de grupo.

3. **Dead code arquitetural**: `get_redis()` dependency foi implementada como "boa prática" mas nenhum endpoint a consome. Health check acessa `request.app.state.redis` diretamente. Manter como seam para epics futuros é aceitável, mas documentar a intenção.

4. **Upstream findings bem resolvidos**: Os blockers (B1) e warnings críticos (W1-W4, W6-W8) do judge report foram todos corrigidos na implementação. O QA encontrou apenas 1 gap residual (PII em formatter.py) que o judge não cobriu.

---

handoff:
  from: madruga:qa
  to: madruga:reconcile
  context: "QA completo com 122 testes passando, 2 fixes aplicados (PII em formatter.py, log duplicado em webhooks.py). Todos os achados upstream (analyze-post + judge) verificados e confirmados. 97% pass rate. Pronto para reconciliação de documentação — os 2 fixes do QA podem gerar drift com a documentação existente."
  blockers: []
  confidence: Alta
  kill_criteria: "Testes de integração passam a falhar por mudança externa no ambiente (Redis, Evolution API) ou nova vulnerabilidade de segurança descoberta nos padrões de logging."
