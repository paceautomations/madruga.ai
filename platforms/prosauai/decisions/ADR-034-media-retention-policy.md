---
title: 'ADR-034: Media retention policy (raw never, URL 14d, transcript 90d)'
status: Accepted
decision: >-
  Never persist raw media bytes (audio/image/document) — bytes exist
  only in memory during processing and are discarded after
  ``ContentProcessor.process()`` returns. Persist provider-signed URLs in
  ``public.media_analyses.source_url`` for a maximum of 14 days (aligned with
  WhatsApp signed-URL expiration). Persist extracted text
  (``text_result``) + marker/metadata for 90 days and then hard-delete. The
  daily retention cron (introduced in ADR-018 + epic 006) grows a new step
  that nulls ``source_url`` + ``raw_response`` at day 14 and deletes the row
  at day 90. Raw bytes NEVER hit object storage, disk or logs.
alternatives: >-
  Persist raw bytes in S3/MinIO (replay on demand); Persist base64
  inline in media_analyses.raw_response; Persist only text_result (drop
  source_url entirely); Per-tenant retention override (like
  ADR-018 message retention); Encrypt-at-rest raw bytes in Supabase.
rationale: >-
  LGPD Art. 6º (minimização) + Art. 9º (transparência) + ADR-018
  (principle — no PII plain-text in logs beyond retention purpose). Raw media
  has no ongoing purpose after transcript/description is extracted — storing
  it would be retention without necessity. 14d URL retention matches the
  natural provider expiration window, so we do not *extend* exposure. 90d
  transcript retention matches ADR-018 conversation retention so deletion
  cascade stays consistent.
---

# ADR-034: Media retention policy (raw never, URL 14d, transcript 90d)

**Status:** Accepted | **Data:** 2026-04-19 | **Supersede:** — | **Extends:** [ADR-018](ADR-018-data-retention-lgpd.md) | **Relaciona:** [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-030](ADR-030-canonical-inbound-message.md), [ADR-032](ADR-032-content-processing-strategy.md), [ADR-033](ADR-033-openai-stt-vision-provider.md)

> **Escopo:** Epic 009 (Channel Ingestion + Content Processing). Esta ADR formaliza a política de retenção da **camada nova de mídia** (áudio, imagem, documento) que o epic 009 introduz. Estende o regime de retenção de conversas do ADR-018 para cobrir os artefatos específicos do processamento de conteúdo.

## Contexto

O epic 009 introduz a tabela `public.media_analyses` (ADR-027 carve-out) que armazena 1 linha por análise de mídia realizada pelo pipeline. Os campos relevantes para retenção são:

| Campo | Tipo | Origem | Sensibilidade |
|-------|------|--------|---------------|
| `source_url` | TEXT | URL signed do provider (WhatsApp / Meta CDN) | Contém token de acesso temporário |
| `text_result` | TEXT | Transcript do Whisper OU descrição do gpt-4o-mini vision OU texto extraído de PDF/DOCX | Pode conter PII falada pelo usuário |
| `raw_response` | JSONB | Resposta completa do provider (whisper/vision) truncada em 32KB | Inclui metadados técnicos; pode conter PII |
| `content_sha256` | CHAR(64) | Hash dos bytes da mídia | Anônimo (irreversível) |
| `cost_usd` / `latency_ms` / `cache_hit` | — | Métricas técnicas | Não sensíveis |

Raw bytes (PCM do áudio, pixels da imagem, conteúdo binário do PDF) **não existem em `media_analyses`**. Mas em runtime o pipeline os carrega em memória (via `ContentProcessor._fetch_bytes`) — a pergunta operacional é: onde mais esses bytes podem vazar (logs, trace_steps, dump de debug) e por quanto tempo os artefatos derivados ficam?

Três frentes regulatórias que informam a decisão:

1. **LGPD Art. 6º** (princípio da finalidade e minimização): dado pessoal só pode ser mantido enquanto servir ao propósito declarado. Transcript serve ao propósito (o LLM precisou dele para gerar resposta; admin audita incidentes). Raw bytes, uma vez processados, **não têm propósito residual** — revoto ao ADR-018 §6 "nunca reter além do período configurado".
2. **ADR-018 §2.6 (carve-out customers.phone)**: plain text só é aceito se (a) tem uso operacional legítimo, (b) é acessado exclusivamente via pool_admin autenticado, (c) nunca sai em logs/traces. O mesmo padrão se aplica aqui para `text_result` de mídia — fica em `media_analyses` (pool_admin only, carve-out ADR-027), nunca vai para logs.
3. **WhatsApp signed URL**: a URL Meta expira em ~14 dias naturalmente — depois disso o replay fica impossível. Persistir a URL depois disso seria reter um campo já inválido (*dead data*).

Spec do epic 009 FR-027 ("Bytes raw NUNCA persistidos") + FR-028 ("Transcript 90d / URL 14d") — esta ADR formaliza os detalhes operacionais, cron jobs e testes de validação.

## Decisão

### 1. Raw bytes — NEVER persist

- **Memória apenas**: `ContentProcessor._fetch_bytes(block)` retorna bytes via `httpx` (áudio/imagem/doc). Variável local, garbage-collected após `process()` retornar.
- **Zero disco**: nenhum `open(path, "wb")` é permitido em `processors/`. Enforce via CI regex (ver §Testing).
- **Zero S3/MinIO/object storage**: plataforma não monta volume para bytes de mídia.
- **Zero structlog / OTel**: bytes nunca aparecem em `trace_steps.input_jsonb` (input é apenas `{kind, url_hash, size_bytes}`) nem em log lines.
- **Replay?** Se precisarmos re-executar um processor para debug, confiamos na URL provider enquanto válida (<14d). Após isso, o debug é inviável — custo aceito em troca de minimização.

### 2. `source_url` — 14 days

Campo `public.media_analyses.source_url` é setado na insert fire-and-forget com a URL original. A URL já expira naturalmente em ~14d no provider Meta. Nosso cron diário **nula** `source_url` + `raw_response` em `created_at < now() - interval '14 days'` para:

- Evitar incluir token expirado em exports/SARs (UX limpo).
- Reduzir superfície de dado "morto" no DB.
- Alinhar TTL do cache Redis (`proc:*` key, 14d) — consistência lógica.

```sql
-- cron job step (extends retention step from ADR-018)
-- Runs daily 03:00 UTC via retention-cron container
UPDATE public.media_analyses
   SET source_url   = NULL,
       raw_response = NULL
 WHERE (source_url IS NOT NULL OR raw_response IS NOT NULL)
   AND created_at < now() - interval '14 days';
```

### 3. `text_result` + metadata — 90 days

Campo `public.media_analyses.text_result` (transcript/description/extracted text) + `marker`, `status`, `provider`, `cost_usd`, `latency_ms`, `cache_hit`, `prompt_version` ficam por 90 dias. Hard DELETE após isso:

```sql
DELETE FROM public.media_analyses
 WHERE created_at < now() - interval '90 days';
```

90 dias alinha com retenção de `prosauai.conversations` (ADR-018 §1). Se um usuário solicitar SAR depois disso, resposta é "sem registro disponível" (LGPD aceita — retenção é direito, não obrigação).

### 4. `content_sha256` — mantido até DELETE da row

`content_sha256` não é PII (hash irreversível). Fica enquanto a row existir. Usado para dedup de cache (`proc:*` key) e correlação com `processor_usage_daily`.

### 5. Cache Redis `proc:*`

TTL 14d — mesma janela da URL signed. Não há cron de cache (Redis LRU já gerencia). Bump de `prompt_version` invalida naturalmente (chave muda).

### 6. Trace Explorer deep-link

O admin (epic 008) mostra `trace_steps.output_jsonb` truncado em 8KB para `content_process` com preview de 500 chars do `text_representation`. Clique "ver completo" abre `media_analyses.text_result` via pool_admin. Se a row foi deletada (>90d), admin recebe 404 estruturado: `{"error": "media_analysis_expired", "retention_policy": "ADR-034"}`.

### 7. Carve-out vs. tenant-level override

`prosauai.conversations` retenção é **configurável por tenant** (ADR-018 §1 30-365d). `media_analyses` retenção é **fixa** 14d/90d na v1.

- Justificativa: volume 10k/mês/tenant já estressa o storage; per-tenant override seria complexidade extra sem demanda de nenhum tenant atual.
- Revisão: se 1º tenant pedir retenção estendida (>90d) para compliance industria (ex.: saúde), adicionamos `tenants.settings.media_retention_days` em epic futuro.

## Alternativas consideradas

### A. Persistir raw bytes em S3/MinIO

- Pros: replay 100% garantido em qualquer momento; simplifica debug pós-mortem.
- Cons:
  - **Viola LGPD minimização** — bytes sem propósito residual.
  - Infra nova (MinIO container ou S3 external) + keys + IAM.
  - LGPD SAR: export de 10k arquivos binários é complexo vs. export de 10k rows em media_analyses.
  - DELETE cascade com links signed vira operation.
- **Rejeitada porque**: o ganho (debug post-14d) não justifica o custo regulatório + infra.

### B. Persistir base64 inline em `media_analyses.raw_response`

- Pros: zero infra nova; replay via campo JSONB.
- Cons:
  - JSONB cresce com base64 (overhead 33%+ do tamanho binário).
  - 10k áudios/mês × 300KB médio × 1.33 × 2 tenants × 3 meses ≈ 24 GB só em `raw_response`.
  - Quebra princípio FR-027 "raw nunca persistido".
  - Truncar em 32KB já não preserva áudio real (áudio 10s ~= 80KB).
- **Rejeitada porque**: mesmo resultado de alternativa A com performance pior e mesmo problema regulatório.

### C. Persistir apenas `text_result` (drop `source_url` entirely)

- Pros: máxima minimização — zero URL armazenada.
- Cons:
  - Perde capacidade de "ouvir áudio original" no Trace Explorer durante a janela <14d — UX degradada para admin (FR-032).
  - Debug de bug ("o transcript não bate com o áudio") fica impossível desde o minuto 1.
- **Rejeitada porque**: URL signed expira naturalmente; guardá-la 14d é ortogonal à retenção do transcript e permite UX admin útil.

### D. Per-tenant retention override desde v1

- Pros: atende antecipadamente tenant de saúde/jurídico que possa exigir 5 anos.
- Cons: YAGNI — nenhum tenant atual pediu. Fixa default 90d cobre Ariel + ResenhAI.
- **Rejeitada (YAGNI)** — aditiva: adicionar `tenants.settings.media_retention_days` leva 2h quando demandado.

### E. Encrypt-at-rest raw bytes em Supabase

- Pros: bytes protegidos por KMS mesmo se persistidos.
- Cons: assume que persistimos bytes (não persistimos). Resolve problema que a decisão principal elimina.
- **Rejeitada**: orthogonal ao problema.

## Consequências

### Positivas

- **LGPD-first**: raw bytes nunca tocam disco/object storage — retenção mínima = 0s.
- **Alinhamento com natural expiration**: URL 14d = janela real do Meta signed URL. Nada é guardado além do que já está morto no provider.
- **Consistency com ADR-018**: transcript 90d = conversation 90d — deletion cascade tem comportamento previsível.
- **Storage previsível**: sem S3, sem volume dedicado; `media_analyses` cabe em ~300MB estáveis (ver data-model §3.1).
- **Auditoria completa durante janela**: admin tem 14d para replay + áudio; 90d para texto + metadata.
- **Compatível com SAR**: SAR endpoint consulta `media_analyses` por `tenant_id + message_id`; dados disponíveis enquanto dentro dos 90d.

### Negativas

- **Debug >14d inviável**: pós-14d, transcript existe mas áudio não — engenheiro não consegue ouvir para contestar descrição. Aceito porque tenants reportam incidentes cedo (dentro de horas, não semanas).
- **Re-processar mídia antiga impossível**: bump de prompt_version só afeta mídia futura; mídia já processada mantém o texto antigo.
- **Cron job mais complexo**: retention-cron do ADR-018 cresce 2 queries novas (nullify + delete). Overhead desprezível (< 1s runtime).

### Neutras

- **Volume aceitável**: 240k rows/ano × ~8KB médio (`text_result` 2KB + `raw_response` 6KB enquanto dentro de 14d) = ~2GB/ano bruto, ~300MB steady-state após retention kick-in.
- **SC-008 (SAR dentro de janela)**: atendível com query direta em `media_analyses` filtrada por `tenant_id`.

## Implementação

### Extensão do retention cron

Arquivo `apps/api/prosauai/ops/retention.py` (existente desde epic 006). Adiciona-se função:

```python
async def purge_media_analyses(conn: asyncpg.Connection, dry_run: bool) -> dict:
    """Retention ADR-034:
    1. NULLIFY source_url + raw_response at 14d.
    2. DELETE rows at 90d.
    """
    nullified = await conn.fetchval(
        """
        UPDATE public.media_analyses
           SET source_url = NULL, raw_response = NULL
         WHERE (source_url IS NOT NULL OR raw_response IS NOT NULL)
           AND created_at < now() - interval '14 days'
        RETURNING count(*) OVER ()
        """,
    ) if not dry_run else 0

    deleted = await conn.fetchval(
        """
        DELETE FROM public.media_analyses
         WHERE created_at < now() - interval '90 days'
        RETURNING count(*) OVER ()
        """,
    ) if not dry_run else 0

    return {"nullified": nullified, "deleted": deleted}
```

### Testes (não-negociáveis)

1. **CI regex** (pre-commit hook): proíbe `open(` + escrita binária em `apps/api/prosauai/processors/`:

   ```bash
   # .pre-commit-hooks/no-raw-media-writes.sh
   grep -rn --include="*.py" -E 'open\([^)]+["'"'"']wb["'"'"']' apps/api/prosauai/processors/ && exit 1
   exit 0
   ```

2. **Unit test**: `test_retention_media_analyses.py`
   - Insere 3 rows: 5d ago, 15d ago, 91d ago.
   - Run `purge_media_analyses(dry_run=False)`.
   - Assert: 5d row intacta; 15d row com `source_url IS NULL` e `raw_response IS NULL`; 91d row deletada.

3. **Integration test**: `test_audio_end_to_end.py` verifica que após processar áudio, `media_analyses.text_result` existe mas **nenhum arquivo é criado em `/tmp/`** (fixture `tmp_path` permanece vazia).

4. **Structlog audit**: log lines do `AudioProcessor` em `dev` mode são inspecionadas via `caplog` — asserta ausência de campo `audio_bytes` ou `raw_base64` em qualquer record.

## Kill criteria

Esta ADR é invalidada se:

1. **Tenant de indústria regulada** (saúde, jurídico) exigir retenção >90d de transcripts por compliance — força adicionar `tenants.settings.media_retention_days` override (aditivo, não breaking).
2. **Cron job de retention ultrapassar 5min de runtime diário** em prod — força batching (LIMIT 1000 DELETE loop). Hoje previsto < 30s.
3. **Auditoria externa concluir que 14d de URL é janela insuficiente** — força encurtar para 7d. Não previsto porque URL Meta já expira naturalmente em ~14d.

## Links

- Migration: [apps/api/db/migrations/20260420_create_media_analyses.sql](https://github.com/paceautomations/prosauai/blob/develop/apps/api/db/migrations/20260420_create_media_analyses.sql)
- Cron implementation: [apps/api/prosauai/ops/retention.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/ops/retention.py)
- Data model: [epics/009-channel-ingestion-and-content-processing/data-model.md §3.1 (media_analyses) + §7.4 (LGPD)](../epics/009-channel-ingestion-and-content-processing/data-model.md)
- Spec §FR-027/FR-028: [epics/009-channel-ingestion-and-content-processing/spec.md](../epics/009-channel-ingestion-and-content-processing/spec.md)
