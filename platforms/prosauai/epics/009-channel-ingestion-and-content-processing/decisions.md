---
epic: 009-channel-ingestion-and-content-processing
created: 2026-04-17
updated: 2026-04-17
---
# Registro de Decisões — Epic 009

1. `[2026-04-17 epic-context]` Substituir `InboundMessage` (Evolution-specific) por `CanonicalInboundMessage` source-agnostic com `ContentBlock` discriminado por `kind`; compatibility strategy em 3 fases (PR-A1/A2/A3). (ref: ADR-030 novo)
2. `[2026-04-17 epic-context]` Cada source implementa `ChannelAdapter` Protocol (`verify_webhook()` + `normalize()`); registry lookup por `source`; adapters são tradutores puros sem DB/LLM. (ref: ADR-031 novo; `channels/base.py`)
3. `[2026-04-17 epic-context]` UX de transcrição inline: usuário espera +2-5s (áudio) ou +3-6s (imagem); sem follow-up async; revisitar em retro se p95 > 5s. (ref: §11 risks EPIC009_full_escope.md)
4. `[2026-04-17 epic-context]` Provider STT default: OpenAI `whisper-1` ($0.006/min); upgrade a `gpt-4o-mini-transcribe` documentado mas fora de escopo v1. (ref: ADR-033 novo)
5. `[2026-04-17 epic-context]` Provider vision default: OpenAI `gpt-4o-mini` via Responses API com `detail: "low"` (85 tokens, $0.013/img); configurável para `"high"` via `processor_config.image.detail`. (ref: ADR-033 novo)
6. `[2026-04-17 epic-context]` Retenção mídia: transcript 90d (retenção messages); URL WhatsApp 14d (expiração natural signed URL Meta); cache dedup por sha256. (ref: ADR-034 novo; estende ADR-018)
7. `[2026-04-17 epic-context]` Volume esperado alto (10k+ mídias/mês/tenant); força cache obrigatório, budget per-tenant, circuit breaker, retry com jitter. (ref: §9 cost analysis EPIC009_full_escope.md)
8. `[2026-04-17 epic-context]` Scope-out explícito: Instagram, Telegram, video frames, PDF tabular, streaming transcription → épicos 010-012. (ref: §1 D6 EPIC009_full_escope.md)
9. `[2026-04-17 epic-context]` Download binário via `httpx` stream para memória, max 25MB (limite Whisper), timeout 10s GET + 15s Whisper; rejeita antes de baixar se `content-length > 25MB`. (ref: §6.4 algoritmos)
10. `[2026-04-17 epic-context]` Base64 inline: pular download quando Evolution enviar `data.message.base64`; reduz latência ~100-300ms. (ref: §6.4 audio step 4)
11. `[2026-04-17 epic-context]` Idempotency key canônico: `sha256(source + source_instance + external_message_id)`; evita colisão cross-source. (ref: §4.1 `CanonicalInboundMessage.idempotency_key`)
12. `[2026-04-17 epic-context]` Feature flag granular por tenant: `content_processing.{enabled, audio_enabled, image_enabled, document_enabled, daily_budget_usd}`; rollback sem deploy. (ref: §6.6 tenants.yaml schema)
13. `[2026-04-17 epic-context]` Pricing register: estender `pricing.py` (ADR-029) com `whisper-1` $0.006/min e `gpt-4o-mini` vision rates; Admin Performance tab mostra custo por processor. (ref: estende ADR-029)
14. `[2026-04-17 epic-context]` Debounce multi-message merge: pipeline recebe `list[CanonicalInboundMessage]`; cada uma processada em step 6; concatenada em `text_representation` única. (ref: §5.5 decisão crítica)
15. `[2026-04-17 epic-context]` `ConversationRequest` carrega `canonical_messages: list[CanonicalInboundMessage]`; remove `text: str`; helpers derivados mantêm compat de uso. (ref: §7.3)
16. `[2026-04-17 epic-context]` Pipeline 12 → 14 steps: insere `content_process` como step #6 entre `save_inbound` (5) e `build_context` (7); `STEP_NAMES` ganha 2 entries; traces antigos mantêm 12 steps. (ref: §7.1, §7.2)
17. `[2026-04-17 epic-context]` Tabela `media_analyses` persiste cada análise completa (não-truncada) para audit; admin-only sem RLS via `pool_admin`; retention cron URL=NULL após 14d, DELETE após 90d. (ref: §6.8; carve-out ADR-027)
18. `[2026-04-17 epic-context]` Tabela `processor_usage_daily` agrega (tenant, kind, provider) por data; suporta enforcement de `daily_budget_usd`; query single-row antes de cada processor run. (ref: §6.6)
19. `[2026-04-17 epic-context]` Cache strategy: key `proc:{kind}:v{prompt_version}:{sha256}` em Redis; TTL 14d; versão do prompt na key → bump invalida cache quando prompt muda. (ref: §6.5)
20. `[2026-04-17 epic-context]` Budget fallback gracioso: estourado → `ProcessedContent(error="budget_exceeded", text_representation="[áudio recebido — limite diário atingido, responderei manualmente]")`. LLM contorna na resposta. (ref: §6.6)
21. `[2026-04-17 epic-context]` PR-C (Meta Cloud) é stress test arquitetural: adapter escrito contra fixtures ANTES de terminar EvolutionAdapter; gate de merge = zero mudança em pipeline/processors/router. (ref: ADR-035 novo; §14 PR-C)
22. `[2026-04-17 epic-context]` Retrocompat webhook URL: manter alias `/webhook/whatsapp/{instance_name}` → chama `evolution.py`; zero-break deploy; remover em épico futuro após métricas confirmarem zero tráfego. (ref: §5.1 T020)
