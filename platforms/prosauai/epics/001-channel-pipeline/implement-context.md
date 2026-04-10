### T001 — DONE
- Create project root with pyproject.toml (FastAPI >=0.115, uvicorn, pydantic 2.x, pydantic-settings, redis[hiredis] >=5.0, httpx, structlog; dev: pytest, pytest-asyncio, pytest-cov, ruff) in prosauai/p
- Tokens in/out: 17/3578

### T002 — DONE
- Create folder structure: prosauai/{__init__,main,config}.py, prosauai/core/{__init__,formatter,router,debounce}.py, prosauai/channels/{__init__,base,evolution}.py, prosauai/api/{__init__,webhooks,heal
- Tokens in/out: 18/4591

### T003 — DONE
- [P] Create .env.example with all Settings fields (EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE_NAME, REDIS_URL, DEBOUNCE_SECONDS, MENTION_PHONE, MENTION_KEYWORDS, WEBHOOK_SECRET) in prosau
- Tokens in/out: 12/2773

### T004 — DONE
- [P] Create Dockerfile with multi-stage build (builder + runtime) in prosauai/Dockerfile
- Tokens in/out: 16/2944

### T005 — DONE
- [P] Configure ruff (select rules, line-length, target-version) and pytest (asyncio_mode=auto) in prosauai/pyproject.toml
- Tokens in/out: 75/2196

### T006 — DONE
- Implement Settings class with pydantic-settings (all env vars, mention_keywords_list property, SettingsConfigDict) in prosauai/config.py
- Tokens in/out: 14/3018

### T007 — DONE
- [P] Implement ParsedMessage (BaseModel), MessageRoute (str Enum, 6 values), RouteResult (dataclass with agent_id), WebhookResponse, HealthResponse in prosauai/core/router.py and prosauai/core/formatte
- Tokens in/out: 9/2199

### T008 — DONE
- [P] Implement MessagingProvider ABC (send_text, send_media abstract methods) in prosauai/channels/base.py
- Tokens in/out: 11/2131

### T009 — DONE
- [P] Configure structlog with JSON output, processors (timestamper, add_log_level), and uvicorn integration in prosauai/main.py
- Tokens in/out: 14/3382

### T010 — DONE
- [P] Create test fixtures with realistic Evolution API payloads (text, extendedText, image, document, video, audio, sticker, contact, location, group text, group mention, group event, from_me) in tests
- Tokens in/out: 15/7348

### T011 — DONE
- [P] Create shared test fixtures (mock settings, mock redis, test client factory, HMAC signature helper) in tests/conftest.py
- Tokens in/out: 14/4312

### T012 — DONE
- [P] [US1] Unit tests for parse_evolution_message() — text, extendedText, image with caption, media without text, unknown type in tests/unit/test_formatter.py
- Tokens in/out: 1991/4985

### T013 — DONE
- [P] [US1] Unit tests for EvolutionProvider — send_text success, send_text failure (log+drop), send_media success in tests/unit/test_evolution_provider.py
- Tokens in/out: 9/4381

### T014 — DONE
- [P] [US1] Integration test for full webhook flow — individual message → 200 queued + echo sent in tests/integration/test_webhook.py
- Tokens in/out: 12/4134

### T015 — DONE
- [US1] Implement parse_evolution_message() — extract fields from Evolution API payload for all message types (text, extendedText, image, document, video, audio, sticker, contact, location) in prosauai/
- Tokens in/out: 8/4101

### T016 — DONE
- [US1] Implement format_for_whatsapp() — format echo text for WhatsApp output in prosauai/core/formatter.py
- Tokens in/out: 6/814

### T017 — DONE
- [US1] Implement EvolutionProvider (httpx async client) — send_text (POST /message/sendText/{instance}), send_media (POST /message/sendMedia/{instance}), error handling with structlog in prosauai/chann
- Tokens in/out: 7/2231

### T018 — DONE
- [US1] Implement basic route_message() — from_me check (first!), individual → SUPPORT classification in prosauai/core/router.py
- Tokens in/out: 7/1471

### T019 — DONE
- [US1] Implement webhook endpoint POST /webhook/whatsapp/{instance_name} — parse payload, route, return WebhookResponse (status queued/ignored) in prosauai/api/webhooks.py
- Tokens in/out: 9/3403

### T020 — DONE
- [US1] Implement echo processing — for SUPPORT route: send echo via EvolutionProvider, log result with structlog (phone_hash, message_id, route) in prosauai/api/webhooks.py
- Tokens in/out: 6/963

### T021 — DONE
- [US1] Wire FastAPI app with lifespan (Redis init placeholder), include webhook and health routers in prosauai/main.py
- Tokens in/out: 6/1978

### T022 — DONE
- [P] [US2] Unit tests for verify_webhook_signature — valid signature, invalid signature, missing header, empty body in tests/unit/test_hmac.py
- Tokens in/out: 17/4301

### T023 — DONE
- [P] [US2] Integration tests — webhook with valid HMAC → 200, without HMAC → 401, with wrong HMAC → 401 in tests/integration/test_webhook.py
- Tokens in/out: 12/4529

### T024 — DONE
- [US2] Implement verify_webhook_signature() dependency — compute HMAC-SHA256 over raw request body bytes, compare_digest, raise HTTPException(401) on failure, return raw body on success in prosauai/api
- Tokens in/out: 6/1476

### T025 — DONE
- [US2] Integrate HMAC dependency into webhook endpoint — add Depends(verify_webhook_signature), use returned raw body for JSON parsing in prosauai/api/webhooks.py
- Tokens in/out: 13/6094

### T026 — DONE
- [P] [US3] Unit tests for route_message() group paths — group+mention by phone JID, group+mention by keyword, group without mention, group event (join/leave), multiple mentions, from_me in group in tes
- Tokens in/out: 14/3034

### T027 — DONE
- [P] [US3] Integration tests — group message with @mention → 200 queued + echo, group without mention → 200 ignored + log only, group event → 200 ignored in tests/integration/test_webhook.py
- Tokens in/out: 8/3216

### T028 — DONE
- [US3] Extend route_message() with group classification — is_group_event → GROUP_EVENT, is_group + @mention (phone JID or keywords regex case-insensitive) → GROUP_RESPOND, is_group no mention → GROUP_S
- Tokens in/out: 10/2991

### T029 — DONE
- [US3] Implement structured logging for GROUP_SAVE_ONLY — log with phone_hash (SHA256 of phone), group_id, route, timestamp via structlog in prosauai/api/webhooks.py
- Tokens in/out: 6/1199

### T030 — DONE
- [US3] Update webhook handler to process GROUP_RESPOND (echo via EvolutionProvider) and GROUP_SAVE_ONLY (log only, no response) in prosauai/api/webhooks.py
- Tokens in/out: 8/2258

### T031 — DONE
- [P] [US4] Unit tests for DebounceManager — append to buffer (Lua script mock), flush on expiry (GETDEL), buffer key format, jitter range, fallback when Redis down in tests/unit/test_debounce.py
- Tokens in/out: 25/8613

### T032 — DONE
- [P] [US4] Integration test — send 3 messages within 2s → single concatenated echo response in tests/integration/test_webhook.py
- Tokens in/out: 18/11761

### T033 — DONE
- [US4] Implement DebounceManager class — Lua script (APPEND to buf: key + SET tmr: key with PEXPIRE + safety TTL on buf: key), buffer key generation from (phone, group_id|"direct") in prosauai/core/deb
- Tokens in/out: 12/4274

### T034 — DONE
- [US4] Implement keyspace notifications subscriber — psubscribe __keyevent@0__:expired, filter tmr: keys, GETDEL buf: key, call flush handler in prosauai/core/debounce.py
- Tokens in/out: 17/4530

### T035 — DONE
- [US4] Implement fallback — when Redis unavailable during append, process message immediately without debounce, log warning in prosauai/core/debounce.py
- Tokens in/out: 10/2732

### T036 — DONE
- [US4] Integrate debounce into FastAPI lifespan — initialize Redis connection, register Lua script, start keyspace listener as asyncio task, cleanup on shutdown in prosauai/main.py
- Tokens in/out: 12/3592

### T037 — DONE
- [US4] Update webhook handler — for SUPPORT/GROUP_RESPOND routes: append to debounce buffer instead of processing immediately, return "queued" status in prosauai/api/webhooks.py
- Tokens in/out: 9/1533

### T038 — DONE
- [US4] Implement flush handler — on buffer expiry: retrieve concatenated messages, send echo via EvolutionProvider, log with structlog in prosauai/api/webhooks.py or prosauai/core/debounce.py
- Tokens in/out: 6/1774

### T039 — DONE
- [P] [US5] Integration tests for /health — healthy (Redis up) → 200 ok, degraded (Redis down) → 200 degraded in tests/integration/test_health.py
- Tokens in/out: 20/4301

### T040 — DONE
- [US5] Implement health check endpoint GET /health — check Redis connectivity (PING), return HealthResponse with status ok/degraded and redis boolean in prosauai/api/health.py
- Tokens in/out: 8/2327

### T041 — DONE
- [US5] Implement get_redis() dependency — return Redis client from app.state, handle connection errors gracefully in prosauai/api/dependencies.py
- Tokens in/out: 5/1249

### T042 — DONE
- [US5] Create docker-compose.yml — api service (build from Dockerfile, port 8040, env_file, depends_on redis healthy), redis service (redis:7-alpine, --notify-keyspace-events Ex, port 6379, healthcheck
- Tokens in/out: 5/944

### T043 — DONE
- [US5] Add healthcheck to Dockerfile — install curl, CMD curl -f http://localhost:8040/health in prosauai/Dockerfile
- Tokens in/out: 3/420

### T044 — DONE
- [P] [US6] Unit test for HANDOFF_ATIVO stub — route returns IGNORE with reason "handoff not implemented" in tests/unit/test_router.py
- Tokens in/out: 18/5339

### T045 — DONE
- [US6] Add HANDOFF_ATIVO detection logic in route_message() — stub that returns RouteResult(route=IGNORE, reason="handoff not implemented") in prosauai/core/router.py
- Tokens in/out: 8/3368

### T046 — DONE
- [P] Add edge case handling — malformed payload → 400, unknown message type → IGNORE + log, unicode/emoji preservation, messages without text in prosauai/core/formatter.py and prosauai/api/webhooks.py
- Tokens in/out: 35/8677

### T047 — DONE
- [P] Integration test for edge cases — malformed payload → 400, from_me → ignored, unknown type → ignored in tests/integration/test_webhook.py
- Tokens in/out: 17/6459

### T048 — DONE
- Run ruff check and ruff format across entire codebase — zero errors required
- Tokens in/out: 18/2556

### T049 — DONE
- Create README.md with reference to quickstart.md and basic project description in prosauai/README.md
- Tokens in/out: 14/3841

### T050 — DONE
- Run full test suite (pytest) — verify 14+ tests passing (target: ~24 tests)
- Tokens in/out: 11/1814

### T051 — DONE
- Validate docker compose up — api + redis start without errors, /health returns 200 OK within 30s
- Tokens in/out: 37/5925

### T052 — DONE
- Run quickstart.md validation — follow manual webhook test steps from quickstart.md, verify expected responses
- Tokens in/out: 31/8770

