---
title: 'ADR-018: Data Retention e LGPD Compliance'
status: Accepted
decision: Retention 90d + consent + SAR
alternatives: Sem retention policy (guardar tudo indefinidamente), Retention fixa
  (mesmo prazo para todos), Anonimizacao total (sem retention de dados identificaveis)
rationale: Compliance com LGPD e GDPR desde o dia 1 — nao eh retrofit
---
# ADR-018: Data Retention e LGPD Compliance
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
ProsaUAI processa dados pessoais de usuarios finais via WhatsApp (e futuros canais) em nome de multiplos tenants. Isso coloca a plataforma sob LGPD (Brasil) e potencialmente GDPR (se tenants atenderem usuarios europeus).

Contexto regulatorio (Marco 2026):
- **ANPD** aplicou +EUR 12M em multas no Q1/2025, targeting uso de dados pessoais para treinar AI sem consentimento
- **EDPB** rejeitou posicao de que LLMs sao automaticamente anonimos — se modelo reteve informacao, precisa de base legal
- **CVE-2025-48757**: 170+ apps com dados PII expostos por misconfiguracao de database (Supabase)
- Subject Access Requests (SARs) ficam complexos quando dados fluem por conversas, embeddings, vector stores e logs

Dados pessoais no ProsaUAI aparecem em:
1. Conversas (mensagens de texto, audio transcrito, imagens)
2. Embeddings na knowledge base (pgvector)
3. Redis (sessoes ativas, cache)
4. Logs (LangFuse traces, application logs)
5. Metadata (numero WhatsApp, timestamps, tenant association)

## Decisao
We will implementar data retention e compliance como parte core da plataforma, nao como afterthought.

### 1. Retention Policy por Tenant

| Dado | Retention Default | Configuravel | Storage |
|------|------------------|-------------|---------|
| Conversas (mensagens) | 90 dias | Sim (30-365 dias) | Supabase |
| Sessoes ativas | 24h | Nao | Redis (TTL) |
| Knowledge base (embeddings) | Permanente (ate tenant deletar) | Sim | Supabase pgvector |
| LangFuse traces | 90 dias | Sim | ClickHouse |
| Application logs | 30 dias | Nao | Log rotation |
| Audit trail (security) | 365 dias | Nao (compliance) | Supabase |

Cron job diario para purge automatico de dados expirados. Tenant pode ajustar retention no admin panel (ADR-010).

### 2. Consent no Primeiro Contato

```
Primeiro contato via WhatsApp:
┌─────────────────────────────────────────┐
│ Ola! Sou o assistente da [Empresa].     │
│                                         │
│ Para te ajudar, preciso processar suas  │
│ mensagens com inteligencia artificial.  │
│ Suas conversas sao armazenadas por      │
│ [90] dias e voce pode solicitar         │
│ exclusao a qualquer momento.            │
│                                         │
│ Politica de Privacidade:                │
│ [link]                                  │
│                                         │
│ Ao continuar, voce concorda com o       │
│ processamento dos seus dados.           │
│                                         │
│ [Continuar] [Nao aceito]               │
└─────────────────────────────────────────┘
```

- Registro de aceite no Supabase: `user_consents(user_id, tenant_id, consented_at, channel, version)`
- Se usuario nao aceita: agente responde apenas com fallback generico, nao processa dados
- Mensagem de consent customizavel por tenant (texto e link da politica)
- Re-consent necessario se politica de privacidade mudar

### 3. Subject Access Request (SAR) Endpoint

API para tenant exportar todos os dados de um end-user:

```
GET /api/v1/tenants/{tenant_id}/users/{phone_hash}/export

Response:
{
  "user": { "phone_hash": "sha256:...", "first_contact": "2026-03-01" },
  "conversations": [...],
  "knowledge_mentions": [...],  // chunks onde user aparece
  "consents": [...],
  "metadata": { "total_messages": 142, "last_active": "2026-03-20" }
}
```

- Identificacao por hash do numero WhatsApp (nao plain text)
- Inclui conversas, metadata, consents, e referencias em knowledge base
- Resposta em JSON (exportavel para CSV pelo admin panel)
- SLA: resposta em ate 15 dias (LGPD permite 15 dias uteis)

### 4. Deletion Cascade

Ao receber pedido de exclusao (usuario ou encerramento de tenant):

```
Pedido de exclusao
    │
    ├── Supabase: DELETE conversas WHERE user_phone_hash = ?
    │   └── RLS garante isolamento (ADR-011)
    │
    ├── Redis: DEL tenant:{id}:user:{hash}:*
    │   └── Sessoes, cache, state
    │
    ├── pgvector: DELETE knowledge_chunks WHERE metadata->>'source_user' = ?
    │   └── Embeddings associados ao usuario
    │
    ├── LangFuse: Redact traces (substituir PII por [REDACTED])
    │   └── Traces nao sao deletados (compliance), mas PII removido
    │
    └── Logs: PII redaction via log rotation
        └── Logs antigos ja purgados por retention
```

Deletion confirmada via callback ao tenant. Prazo: 72h apos pedido.

### 5. PII Detection no Input

Antes de armazenar qualquer conversa:

```python
# Layer 1 do guardrail (ADR-016) detecta PII
pii_patterns = {
    "cpf": r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
    "phone": r"\+?\d{10,13}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "credit_card": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
}

# Armazena versao original (com PII, retention limitada)
# + versao redacted (para analytics, retention longa)
```

- Versao original: retention policy do tenant (default 90 dias)
- Versao redacted: disponivel para analytics e treinamento de evals sem PII
- PII detection configuravel por tenant (blocklist de patterns extras)

### 6. Proibicoes

- **NUNCA fine-tunar modelos com dados de tenant** sem contrato especifico e consentimento explicito
- **NUNCA compartilhar embeddings entre tenants** — namespace isolation obrigatoria (ADR-013)
- **NUNCA armazenar numero WhatsApp em plain text** em logs ou traces — usar hash SHA-256
- **NUNCA reter dados alem do periodo configurado** — cron job de purge e obrigatorio, nao opcional

## Alternativas consideradas

### Sem retention policy (guardar tudo indefinidamente)
- Pros: Dados disponiveis para analytics e melhoria continua
- Cons: Violacao direta da LGPD (principio de minimizacao). Multa de ate 2% do faturamento. Risco reputacional. Custo de storage crescente. Inaceitavel

### Retention fixa (mesmo prazo para todos)
- Pros: Mais simples de implementar, sem configuracao por tenant
- Cons: Inflexivel — tenant de saude pode precisar de 5 anos, tenant de varejo pode querer 30 dias. Nao atende requisitos regulatorios variados por industria

### Anonimizacao total (sem retention de dados identificaveis)
- Pros: Maximo de compliance, zero risco de vazamento de PII
- Cons: Impossibilita funcionalidades core (historico de conversa, personalizacao, SAR). Anonimizacao de verdade eh extremamente dificil — EDPB considera que LLMs nao atingem standard de anonimizacao

## Consequencias
- [+] Compliance com LGPD e GDPR desde o dia 1 — nao eh retrofit
- [+] Consent registrado = base legal para processamento
- [+] SAR endpoint atende direito de acesso do usuario final
- [+] Deletion cascade garante right to erasure em todas as camadas
- [+] PII detection reduz risco de exposicao acidental
- [+] Retention configuravel permite atender regulacoes de diferentes industrias
- [-] Cron job de purge adiciona complexidade operacional
- [-] PII detection regex tem falsos positivos/negativos (mitiga: ML detector em v2)
- [-] Consent message adiciona fricao no primeiro contato (mitiga: mensagem curta e clara)
- [-] SAR endpoint precisa buscar em multiplas fontes (Supabase, Redis, pgvector, logs) — implementacao nao trivial
- [-] Deletar embeddings remove o vetor, mas se embedding foi usado em resposta cacheada, a informacao pode persistir brevemente (mitiga: TTL curto no cache)

## Referencias
- [LGPD — Lei 13.709/2018](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [EDPB — Right to Erasure Coordinated Enforcement (Mar/2025)](https://www.edpb.europa.eu/our-work-tools/our-documents/other/coordinated-enforcement-framework-right-erasure_en)
- [GDPR and AI Right to Be Forgotten](https://keferboeck.com/en-gb/articles/gdpr-and-ai-right-to-be-forgotten-now-means-unlearning)
- [CVE-2025-48757 — Supabase RLS Exposure](https://mattpalmer.io/posts/2025/05/CVE-2025-48757/)

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
