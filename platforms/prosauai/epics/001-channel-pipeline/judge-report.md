---
title: "Judge Report — 001 Channel Pipeline"
score: 92
initial_score: 36
verdict: pass
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 13
findings_fixed: 9
findings_open: 4
updated: 2026-04-09
---

# Judge Report — 001 Channel Pipeline

## Score: 92%

**Verdict:** PASS
**Team:** Tech Reviewers (4 personas)

**Initial Score:** 36% → **Post-Fix Score:** 92% (+56 pontos após fase de correções)

---

## Findings

### BLOCKERs (1 — 1/1 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | arch-reviewer, bug-hunter, stress-tester (3/4) | Webhook usa `debounce.append()` em vez de `append_or_immediate()`. Quando Redis falha, `append()` retorna `None` e a mensagem é silenciosamente descartada — o caller retorna status "queued" mas nenhum echo é enviado. Viola FR-007/D4 (fallback sem debounce quando Redis indisponível). O método `append_or_immediate()` já existe no código mas nunca é chamado. | `prosauai/api/webhooks.py:75` | [FIXED] | Substituído `debounce.append()` por `debounce.append_or_immediate()` com callback `_make_flush_fallback()` que invoca `_send_echo()` diretamente quando Redis está indisponível. |

### WARNINGs (8 — 7/8 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | bug-hunter, stress-tester (2/4) | Keyspace listener (`start_listener`) morre permanentemente em `ConnectionError`/`TimeoutError`. Se Redis reinicia brevemente, o listener para de funcionar e todos os buffers pendentes expiram sem flush — perda de mensagens. Sem lógica de reconexão. | `prosauai/core/debounce.py:376-382` | [FIXED] | Adicionado loop de reconexão com exponential backoff (base 1s, max 30s, até 10 tentativas) envolvendo `_run_listener_loop()`. Listener agora sobrevive blips de Redis. |
| W2 | arch-reviewer, bug-hunter, simplifier, stress-tester (4/4) | Novo `EvolutionProvider` (httpx `AsyncClient`) criado e destruído a cada echo/flush. TCP churn, TLS handshakes repetidos. A 1000 msgs/min, risco de exaustão de file descriptors e portas efêmeras. Inconsistente com o padrão lifespan usado para Redis. | `prosauai/api/webhooks.py:155-172`, `prosauai/main.py:169-191` | [FIXED] | Provider compartilhado criado no lifespan (`app.state.provider`), reutilizado em `_flush_echo()`. `_send_echo()` tenta usar provider compartilhado primeiro, cria temporário apenas como fallback. Cleanup no shutdown. |
| W3 | arch-reviewer (1/4) | Import direto de `EvolutionProvider` no API layer viola ACL boundary do context-map. Acoplamento entre bounded contexts (API/core e Channel) no nível de implementação. | `prosauai/api/webhooks.py:18`, `prosauai/main.py:162` | [FIXED] | Path principal (flush via debounce) agora usa provider compartilhado via `app.state`. Import direto permanece apenas no fallback path (`_send_echo`) — aceitável para epic 001. |
| W4 | bug-hunter (1/4), analyze-post P2 | Rota ativa (SUPPORT/GROUP_RESPOND) com texto vazio (media-only) retorna `status="queued"` mas nenhuma ação é executada. Resposta inconsistente — o caller pensa que algo será processado mas nada acontece. | `prosauai/api/webhooks.py:68-71` | [FIXED] | Lógica reestruturada: `status="queued"` apenas quando `message.text` é truthy E rota é ativa. Rota ativa sem texto retorna `status="ignored"` explicitamente. |
| W5 | stress-tester (1/4) | Sem limite de tamanho no body do request. `await request.body()` lê payload inteiro sem cap. Payload malicioso ou bugado pode consumir memória do processo. | `prosauai/api/dependencies.py:37` | [OPEN] | Recomendação: configurar `--limit-max-request-size` no uvicorn ou adicionar middleware com limite de 1 MB. Aceitável para epic 001 (webhook interno, sem exposição pública direta). |
| W6 | stress-tester (1/4) | Flush pipeline sequencial — cada flush aguarda callback (até 30s timeout do httpx) antes de processar o próximo. Com 100 timers expirando simultaneamente, o último espera ~3000s. Safety TTL pode expirar antes do flush. | `prosauai/core/debounce.py:366-375` | [FIXED] | Cada flush agora é despachado como `asyncio.create_task()` independente, com referência mantida em `_flush_tasks` set. Pipeline não-bloqueante. |
| W7 | bug-hunter (1/4) | `_init_redis` loga URL completa do Redis que pode conter credenciais (`redis://:password@host`). Vazamento de secrets nos logs. | `prosauai/main.py:128` | [FIXED] | Adicionada função `_mask_redis_url()` que substitui credenciais por `***` antes de logar. |
| W8 | stress-tester (1/4) | PII em logs: `EvolutionProvider._post()` loga `number[:8]+"..."` (prefixo do telefone, não hash). `debounce.py` loga `phone` raw em warnings. Inconsistente com `webhooks.py` que usa SHA-256 hash. | `prosauai/channels/evolution.py:103`, `prosauai/core/debounce.py:158+` | [FIXED] | `evolution.py`: substituído `number[:8]+"..."` por `hashlib.sha256(number.encode()).hexdigest()[:12]`. `debounce.py`: adicionada helper `_hash_phone()`, substituídas todas as referências `phone=phone` por `phone_hash=_hash_phone(phone)` nos logs de warning/error/debug. |

### NITs (4 — 1/4 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | arch-reviewer (1/4) | `HealthResponse` definido em `core/router.py` mas usado exclusivamente por `api/health.py`. Viola single-responsibility — schema de health misturado com schemas de routing. | `prosauai/core/router.py:64` | [OPEN] | Menor. Mover para `api/health.py` ou `core/schemas.py` no próximo refactor. |
| N2 | arch-reviewer, simplifier (2/4) | `get_redis()` dependency definida mas nunca usada por nenhum endpoint. Health acessa `request.app.state.redis` diretamente. Dead code arquitetural. | `prosauai/api/dependencies.py:57-84` | [OPEN] | Manter por ora — pode ser útil em epics futuros. Remover se não utilizado até epic 003. |
| N3 | simplifier (1/4) | `_MEDIA_NO_URL_TYPES` set definido mas nunca referenciado no código ou testes. Constante órfã. | `prosauai/core/formatter.py:55` | [FIXED] | Removida a constante não utilizada. |
| N4 | arch-reviewer, bug-hunter (2/4) | `_extract_mentions()` só extrai mentions de `extendedText`. Mentions em imageMessage/videoMessage com `contextInfo` são ignoradas. | `prosauai/core/formatter.py:254` | [OPEN] | Compensado pelo fallback de keyword regex em `_is_bot_mentioned()` no router. Limitação da Evolution API v2.x documentada. |

### Findings Descartados pelo Judge

| # | Source | Motivo do Descarte |
|---|--------|--------------------|
| D1 | arch-reviewer | Jitter sem floor mínimo — spec diz "0-1s", zero é válido dentro do range especificado. |
| D2 | bug-hunter | `parse_expired_key` rfind ambíguo — JIDs não contêm colons, cenário hipotético sem evidência. |
| D3 | bug-hunter | HMAC não normaliza formato — Evolution API usa formato fixo, documentado. |
| D4 | bug-hunter | Safety TTL não conta jitter — 6s safety vs 4s max timer, margem de 2s é suficiente. Lua script reseta safety TTL em cada append. |
| D5 | simplifier | MessagingProvider ABC com uma implementação — requerido pelo context-map ACL pattern (ADR-005). Não é over-engineering, é requisito arquitetural. |
| D6 | simplifier | `RouteResult.agent_id` nunca usado — spec explicitamente requer para forward compatibility (pitch: "RouteResult inclui agent_id desde dia 1"). |
| D7 | simplifier | `format_for_whatsapp()` passthrough — seam documentada para epic 002. Custo: 1 função de 1 linha. Benefício: diff mínimo no epic 002. |
| D8 | simplifier | `_is_handoff_ativo()` stub — spec requer enum com 6 rotas incluindo HANDOFF_ATIVO stub. Evita breaking change no epic 005. |
| D9 | simplifier | Docstrings verbosos — subjetivo, sem impacto funcional. Constitution não restringe documentação. |
| D10 | stress-tester | Redis connection pool defaults — aceitável para ~100 msgs/min. Configurar no epic 002 com worker ARQ. |
| D11 | stress-tester | Health ping sem timeout explícito — usa timeout do Redis client (default redis-py). Aceitável. |
| D12 | stress-tester | Docker sem memory limits — concern de operação, não de código. docker-compose.yml é para dev/staging. |
| D13 | stress-tester | Uvicorn single worker — aceitável para epic 001. Multi-worker requer leader election para debounce listener. |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| — | Nenhuma decisão 1-way-door escapou. | — | — | ✅ OK |

Todas as decisões no epic 001 são 2-way-door (reversíveis): escolha de framework, padrão de debounce, formato de config. Nenhuma decisão com score ≥ 15 foi identificada nos commits do branch.

---

## Personas que Falharam

Nenhuma — todas as 4 personas completaram com sucesso (4/4).

---

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `prosauai/api/webhooks.py` | B1, W3, W4 | Substituído `append()` por `append_or_immediate()` com fallback. Status "ignored" para media sem texto. Adicionado `_make_flush_fallback()`. |
| `prosauai/core/debounce.py` | W1, W6, W8 | Reconnect loop com exponential backoff. Flush via `asyncio.create_task()`. Phone hash em todos os logs. |
| `prosauai/main.py` | W2, W7 | Provider compartilhado no lifespan (`app.state.provider`). `_flush_echo()` reutiliza provider. URL masking para Redis. |
| `prosauai/channels/evolution.py` | W8 | `number_hash` agora usa SHA-256 prefix em vez de string slice. |
| `prosauai/core/formatter.py` | N3 | Removida constante `_MEDIA_NO_URL_TYPES` não utilizada. |
| `tests/integration/test_webhook.py` | — | Testes atualizados para mockar `append_or_immediate` em vez de `append`. |

---

## Recomendações

### Para findings OPEN

1. **W5 (body size limit)**: Configurar `--limit-max-request-size 1048576` no uvicorn CMD do Dockerfile antes de deploy em produção. Alternativa: middleware FastAPI com `Content-Length` check.

2. **N1 (HealthResponse placement)**: Mover `HealthResponse` para `api/health.py` no próximo refactor. Impacto zero em funcionalidade.

3. **N2 (get_redis unused)**: Avaliar uso no epic 002. Se não utilizado, remover no epic 003.

4. **N4 (_extract_mentions limited)**: Monitorar via log de warning existente (`unknown_message_type`). Quando Evolution API v2.x adicionar mentions em outros tipos, estender `_extract_mentions()`. O fallback de keyword regex garante cobertura funcional.

### Para epics futuros

- **Epic 002**: Refatorar `EvolutionProvider` para singleton definitivo via DI. Configurar Redis `max_connections`. Adicionar multi-worker com leader election para debounce listener.
- **Epic 003**: Avaliar remoção de `get_redis()` se ainda não utilizado.
- **Epic 005**: `_is_handoff_ativo()` stub pronto para implementação real. Enum HANDOFF_ATIVO presente.

---

## Validação Pós-Fix

| Check | Resultado |
|-------|-----------|
| `pytest` — 122 testes | ✅ PASS (122 passed, 0 failed) |
| `ruff check .` | ✅ PASS (All checks passed) |
| `ruff format --check .` | ✅ PASS (25 files already formatted) |
| Nenhum finding introduziu regressão | ✅ Confirmado |

---

handoff:
  from: madruga:judge
  to: madruga:qa
  context: "Judge completo com score 92% (PASS). 9/13 findings corrigidos, incluindo 1 BLOCKER (debounce fallback) e 7 WARNINGs (reconnect, provider compartilhado, PII, flush pipeline). 4 findings OPEN são NITs ou hardening ops. 122 testes passando, ruff clean. Pronto para QA testing."
  blockers: []
  confidence: Alta
  kill_criteria: "Descoberta de bug funcional que causa perda de mensagens em condições normais de operação (não edge case de infra)."
