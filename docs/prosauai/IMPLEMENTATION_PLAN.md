# Plano de Implementação — Auth Multi-Tenant + Deploy Strategy

**Status:** Aprovado — pronto para implementação
**Data:** 2026-04-10
**Autor:** Gabriel Hamu + Claude
**Branch alvo:** `develop` → `feat/multi-tenant-auth`
**Epic relacionado:** `epic/prosauai/001-channel-pipeline` (já mergeado)
**Hipótese-chave validada:** ✅ sim (ver seção 4.5)

---

## 0. Sumário Executivo (TL;DR)

O código atual do ProsauAI exige um `WEBHOOK_SECRET` e implementa validação HMAC-SHA256 no endpoint `POST /webhook/whatsapp/{instance_name}`. **Essa arquitetura não funciona com a Evolution API** — a Evolution nunca suportou assinatura HMAC de webhooks e não vai suportar (issue upstream aberto em 2023, fechado sem implementação em 2025).

Além disso, capturamos 36 webhooks reais (de 2 instâncias Evolution distintas: Ariel e ResenhAI) e descobrimos que o parser do epic 001 diverge da realidade em **12 pontos críticos** — do nome de `messageType` ao formato de sender em grupo, passando pelo lugar onde `mentionedJid` vive no payload. Ver §7.6.2.1 e §7.6.8 para o detalhamento com evidências.

E o end-state do produto é **multi-tenant**: expor `https://api.prosauai.com/webhook/whatsapp/{instance}` para múltiplos clientes, cada um com sua própria instância Evolution.

Este documento propõe:

1. **Remover** a validação HMAC do código (feature impossível de usar com Evolution).
2. **Introduzir** uma abstração de `Tenant` desde o início — mesmo operando com 2 tenants hoje (Ariel + ResenhAI), o código já suporta N amanhã.
3. **Autenticar** webhooks via header compartilhado (`X-Webhook-Secret`) por tenant, configurado no próprio webhook da Evolution (validado empiricamente — §4.5).
4. **Corrigir o parser** pra bater com os payloads reais da Evolution v2.3.0: suporte a `@lid`/`senderPn`/`senderLid`, `mentionedJid` em `data.contextInfo`, `groups.upsert` (data como lista), `group-participants.update` (data sem key), rota pra `reactionMessage`, extração de `quotedMessage`, etc. Ver tasks T6b → T6j.
5. **Adicionar idempotência** em Redis para neutralizar os retries agressivos da Evolution (até 10 tentativas).
6. **Isolar via rede** (Docker network privada ou Tailscale) como camada principal de defesa.
7. **Faseá-lo** em 3 entregas: Fase 1 (multi-tenant estrutural, 2 tenants internos), Fase 2 (expor para clientes externos), Fase 3 (operação em produção).

**Catálogo de fixtures de teste pronto:** 26 fixture pairs committáveis em [`tests/fixtures/captured/`](tests/fixtures/captured/), gerados a partir dos 36 webhooks reais capturados e anonimizados deterministicamente. A fixture sintética antiga (`evolution_payloads.json`) será substituída por esse catálogo durante a refatoração (tasks T6b-T6j).

A implementação desta fase 1 é **pré-requisito** para qualquer outro epic — sem ela, o serviço (1) rejeita 100% dos webhooks reais por HMAC imaginário e (2) mesmo corrigindo a auth, o parser falha silenciosamente em 50% das mensagens por não conhecer os `messageType` reais.

---

## 1. Contexto

### 1.1. O que é o ProsauAI

Serviço Python/FastAPI que recebe webhooks da Evolution API (WhatsApp) e roteia mensagens para diferentes fluxos de processamento (support individual, grupo com menção, eventos de grupo, etc.). A arquitetura inicial foi entregue no epic `001-channel-pipeline`.

### 1.2. Estado atual do código (pós-merge do epic 001)

Arquivos relevantes:

- [prosauai/config.py](prosauai/config.py) — Settings via `pydantic-settings`. Campos obrigatórios globais: `evolution_api_url`, `evolution_api_key`, `evolution_instance_name`, `mention_phone`, `webhook_secret`.
- [prosauai/api/webhooks.py](prosauai/api/webhooks.py) — Endpoint `POST /webhook/whatsapp/{instance_name}`. Chama `verify_webhook_signature()` antes de processar.
- [prosauai/api/dependencies.py](prosauai/api/dependencies.py) — Valida HMAC-SHA256 no header `x-webhook-signature` usando `settings.webhook_secret`.
- [prosauai/core/formatter.py](prosauai/core/formatter.py) — Parser de payload. **Com 12 divergências confirmadas em relação à realidade dos payloads** (ver §7.6.8).
- [prosauai/core/router.py](prosauai/core/router.py) — Classifica mensagens em 6 rotas (SUPPORT, GROUP_RESPOND, GROUP_SAVE_ONLY, GROUP_EVENT, HANDOFF_ATIVO, IGNORE).
- [prosauai/core/debounce.py](prosauai/core/debounce.py) — Agrupa mensagens rápidas do mesmo `phone+group_id` via Redis + Lua. **Não faz dedupe por `message_id`.**
- [prosauai/channels/evolution.py](prosauai/channels/evolution.py) — Cliente HTTP para a Evolution API (envio de mensagens).
- [prosauai/main.py](prosauai/main.py) — Lifespan FastAPI: configura logging, Redis, debounce listener.
- [docker-compose.yml](docker-compose.yml) — Sobe a API na porta `8050` (bind `0.0.0.0` por padrão) + Redis 7.
- [tests/fixtures/evolution_payloads.json](tests/fixtures/evolution_payloads.json) — **Fixture sintética 100% desalinhada com a realidade**. Será substituída pelo catálogo committável `tests/fixtures/captured/` gerado a partir de 36 capturas reais (ver §7.6.7 e §7.6.8).
- [tests/fixtures/captured/](tests/fixtures/captured/) — **Catálogo novo, gerado 2026-04-10**: 26 fixture pairs (`.input.json` + `.expected.yaml`) anonimizados a partir de payloads reais da Evolution v2.3.0. Cobertura MECE: 3 eventos × 2 tenants × 2 contextos × 4 formatos de sender × 13 content types. Ver [tests/fixtures/captured/README.md](tests/fixtures/captured/README.md).
- [tools/payload_capture.py](tools/payload_capture.py) — **Tool temporário** (descartável) usado pra capturar payloads reais (ver §7.6.6).
- [tools/anonymize_captures.py](tools/anonymize_captures.py) — **Script de geração de fixtures**: lê raw captures, anonimiza deterministicamente, gera os `.input.json` + `.expected.yaml` em `tests/fixtures/captured/`.

### 1.3. O problema que motivou este plano

Ao tentar subir o serviço com `docker compose up` e configurar a Evolution API para enviar webhooks, dois problemas bloqueantes surgiram:

**Problema 1 — Falta `.env`.**
O `docker-compose.yml` depende de um `.env` com 5 variáveis obrigatórias (`EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE_NAME`, `MENTION_PHONE`, `WEBHOOK_SECRET`).

**Problema 2 — `WEBHOOK_SECRET` não existe no mundo real.**
O código assume que a Evolution API envia um header `x-webhook-signature` com HMAC-SHA256 do body. **Isso nunca foi verdade.** Nenhuma versão da Evolution API (v1.x ou v2.x) assina webhooks. O `WEBHOOK_SECRET` é uma feature imaginária.

Investigação confirmou (ver seção 4):

- Source code da Evolution v2.3.7 não tem nenhuma chamada a `createHmac`, `signature`, ou qualquer lógica de assinatura em `src/api/integrations/event/webhook/webhook.controller.ts`.
- Issue [#102 "HMAC Signature in all webhooks"](https://github.com/EvolutionAPI/evolution-api/issues/102) foi aberta em 2023-09-08 pedindo exatamente essa feature e **fechada em 2025-09-09 sem implementação**.
- A única "auth" que a Evolution suporta é enviar headers customizados estáticos configurados pelo usuário (opcional) ou incluir um JWT HS256 via a chave especial `jwt_key` nos headers — mas o JWT assina um payload fixo, não o body, então não protege contra tampering.

Consequência: **o serviço, do jeito que está hoje, rejeita 100% dos webhooks reais da Evolution com HTTP 401.**

### 1.4. Visão de produto (end-state)

A partir da conversa de planejamento:

> "em algum momento eu deveria criar um http/api.prosauai.com/webhook para disponibilizar para clientes diferentes"

O ProsauAI não é um serviço interno permanente. É uma plataforma multi-tenant onde:

- Cada cliente tem sua própria instância da Evolution API (ou compartilha a nossa).
- Cada cliente configura o webhook da Evolution para apontar para `https://api.prosauai.com/webhook/whatsapp/{instance-do-cliente}`.
- O ProsauAI identifica o tenant pelo `instance_name` no path, aplica regras de roteamento/auth/rate limit do tenant, e devolve resposta.

Isso é um **requisito arquitetural** que precisa ser refletido no código **agora**, não depois. Trazer multi-tenancy como refatoração posterior é caro — toca `config.py`, `webhooks.py`, `dependencies.py`, `debounce.py`, `main.py` e todos os testes associados.

---

## 2. Objetivos e Não-Objetivos

### 2.1. Objetivos desta implementação

| # | Objetivo | Prioridade |
|---|---|---|
| O1 | Serviço consegue receber e processar webhooks reais da Evolution | P0 (bloqueante) |
| O2 | Código já suporta múltiplos tenants, mesmo que hoje só exista 1 | P0 |
| O3 | Auth via header compartilhado por tenant (configurável na Evolution via webhook `headers`) | P0 |
| O4 | Idempotência por tenant + message_id em Redis (mitiga retries da Evolution) | P0 |
| O5 | Deploy seguro: porta nunca exposta na internet pública, nem em dev nem em prod | P0 |
| O6 | Dev ergonomics: rodar `docker compose up` funciona para o Gabriel sem configs mágicas | P1 |
| O7 | Testes cobrem auth por tenant, idempotência, e rejeição de tenants desconhecidos | P1 |
| O8 | Fase 2 (expor publicamente) é só deploy + Caddy, zero refactor de código | P1 |

### 2.2. Não-objetivos

- **Não** implementar admin API (`CRUD de tenants`) nesta fase — tenants vêm de arquivo YAML.
- **Não** implementar rate limiting por tenant — fica para Fase 2.
- **Não** implementar billing/usage tracking.
- **Não** implementar Postgres — YAML é suficiente enquanto temos < 5 tenants.
- **Não** implementar o fluxo HMAC "real" (assinatura do body) — Evolution não suporta.
- **Não** implementar mTLS.
- **Não** quebrar compatibilidade com a estrutura do epic 001 (o `router`, `debounce`, `formatter` ficam intocados — só o que está acima deles muda).

---

## 3. Modelo de Ameaças

### 3.1. Cenários de deploy

**Cenário A — Dev local (WSL)**
- ProsauAI roda na máquina do Gabriel (`ntb-25-0543`, Tailscale IP `100.77.80.33`)
- Evolution API roda remota (`evolutionapi.pace-ia.com`)
- Evolution precisa conseguir alcançar a máquina de dev para enviar webhooks

**Cenário B — Produção single-tenant (interno Pace)**
- ProsauAI + Evolution rodam na mesma VPS Hostinger
- Docker network privada compartilhada entre os dois containers
- Nenhuma porta exposta na internet

**Cenário C — Produção multi-tenant (futuro)**
- ProsauAI exposto em `https://api.prosauai.com` via Caddy/Traefik
- Tenants externos apontam webhooks de suas próprias Evolutions para essa URL
- Tráfego vem da internet

### 3.2. Atores e ameaças

| Ator | Ameaça | Mitigação |
|---|---|---|
| Atacante externo (Cenário A/B) | Alcançar o webhook diretamente | **Impossível:** não há rota de rede. Porta só escuta em interface privada (Tailscale ou Docker network). |
| Atacante externo (Cenário C) | Enviar webhook forjado | **Header secret por tenant** + idempotência. Cliente ignora se secret errado. |
| Atacante externo (Cenário C) | Replay attack com webhook capturado | **Idempotência** por `(tenant_id, message_id)` em Redis por 24h. |
| Atacante externo (Cenário C) | DoS via flood de webhooks válidos | **Rate limit por tenant** (Fase 2) + Caddy rate limit por IP. |
| Atacante externo (Cenário C) | Confusão de tenants (enviar webhook de A para endpoint de B) | Cada tenant tem secret próprio — secret de B não autoriza webhook para A. |
| Tenant malicioso | Usar API para abusar de outros tenants | Isolamento lógico: cada tenant só vê suas próprias chaves Redis, logs, filas. |
| Tenant malicioso | Vazar sua própria API key da Evolution | Responsabilidade do tenant. Blast radius: só a instância dele. |
| VPS comprometida | Roubar tenants.yaml / credentials | Game over. Nenhuma camada de app salva. Mitigação: backups, hardening da VPS, secrets em volume separado. |
| Supply chain (Evolution comprometida) | Enviar payloads maliciosos com credenciais válidas | Não há defesa prática. Monitoramento + observabilidade para detectar anomalias. |

### 3.3. O que NÃO é ameaça real

- **"E se atacante descobrir o `EVOLUTION_API_KEY`?"** — Essa key é usada só *outbound* (ProsauAI → Evolution). Se vazar, o blast radius é a instância Evolution (não o ProsauAI). Não é usada para autenticar webhooks *inbound*.
- **"E se Evolution vazar o `apikey` no body?"** — O `apikey` no body é info contextual, não credencial. Validar no body é teatro de segurança.

---

## 4. Descobertas-Chave sobre Evolution API

### 4.1. Evolution NÃO assina webhooks

**Verificação no source (v2.3.7, commit `cd800f2`):**

- `src/api/integrations/event/webhook/webhook.controller.ts`, linhas 125-224: dispatcher de webhook usa `axios.post('', webhookData)` sem nenhuma etapa de assinatura.
- `src/api/integrations/event/webhook/webhook.schema.ts`: schema de config do webhook expõe apenas `enabled`, `url`, `headers`, `byEvents`, `base64`, `events`. Nenhum campo `secret` ou `signing_key`.
- Grep em todo `src/` por `hmac|HMAC|createHmac|X-Signature|signature`: **zero hits em código de webhook**.
- Mesmo padrão em v1.8.2 (`src/api/services/channel.service.ts:689-1053`).

**Issue upstream:** [EvolutionAPI/evolution-api#102 "HMAC Signature in all webhooks"](https://github.com/EvolutionAPI/evolution-api/issues/102) — aberta 2023-09-08, fechada sem implementação 2025-09-09.

### 4.2. Mecanismos de auth que Evolution oferece (todos fracos)

**4.2.1. Headers customizados estáticos**

Ao configurar um webhook via `POST /webhook/set/{instance}`, você passa um objeto `headers` que é incluído literalmente em toda requisição:

```json
{
  "webhook": {
    "enabled": true,
    "url": "https://api.prosauai.com/webhook/whatsapp/cliente-acme",
    "headers": {
      "X-Webhook-Secret": "<secret-longo-aleatório-deste-tenant>"
    },
    "events": ["MESSAGES_UPSERT"]
  }
}
```

Receiver valida em constant-time. **Este é o mecanismo que vamos usar.**

**4.2.2. JWT via `jwt_key`** (v2.2+, PR #1318)

Se `headers` incluir a chave especial `jwt_key`, Evolution gera automaticamente um JWT HS256 a cada webhook e envia como `Authorization: Bearer <jwt>`. Payload: `{iat, exp (+600s), app:"evolution", action:"webhook"}`.

**Problemas:**
- JWT assina um **payload fixo**, não o body da requisição. Atacante com um JWT válido pode mutar o body por até 10 minutos.
- Não resolve o problema real (body tampering).
- Onboarding mais complexo para clientes.

**Decisão:** **Não** usar. Header estático + idempotência dá segurança equivalente com menos complexidade.

**4.2.3. Campo `apikey` no body**

Toda requisição inclui `body.apikey` com a API key da instância Evolution. **Não é credencial de auth** — é info contextual. Também está em logs, proxies, e vaza em MITM. Validar isso é teatro de segurança.

### 4.3. Headers que Evolution envia de fato

Por padrão, **só o que axios adiciona:**

- `Content-Type: application/json`
- `Accept: application/json, text/plain, */*`
- `User-Agent: axios/<version>`
- `Content-Length`, `Host`, `Accept-Encoding`

Nenhum `X-Evolution-*`, nenhum `apikey`, nenhum `Authorization`, a menos que o usuário tenha configurado em `headers`.

### 4.4. Retries agressivos — por que idempotência é obrigatória

`webhook.controller.ts:203-285` (método `retryWebhookRequest`) retenta webhooks **até 10 vezes** com backoff exponencial em caso de erro de rede ou HTTP 5xx. Sem idempotência no receiver:

- Mesma mensagem é processada múltiplas vezes.
- Debounce agrupa múltiplas vezes (resultando em echo duplicado).
- Se houver efeitos colaterais (DB writes, cobranças), vira caos.

**A idempotência resolve isso deduplicando por `(tenant_id, message_id)` em Redis com TTL de 24h.**

### 4.5. Validação empírica da hipótese (2026-04-10)

Antes de commitar com a arquitetura, validamos ao vivo que a Evolution v2.3.0 da Pace (`evolutionapi.pace-ia.com`) aceita e encaminha headers customizados via o campo `webhook.headers`.

**Procedimento:**

1. Configurado webhook temporário na instância `Ariel` apontando para `https://webhook.site/<uuid>` com `headers: {"X-Webhook-Secret": "<secret>"}` via `POST /webhook/set/Ariel`.
2. Enviada mensagem real pelo WhatsApp para o número do bot.
3. Verificado no painel do webhook.site que o header `x-webhook-secret: d9b945d1...` apareceu exatamente como configurado.

**Resultado:** ✅ Confirmado. A abordagem de auth por `X-Webhook-Secret` estático (seção 6.6) funciona em produção com a versão específica da Evolution que usamos.

**Descobertas colaterais do payload real:**

- **Formato `@lid`** — `remoteJid` veio como `"200759773786203@lid"` (novo formato "Linked ID" do WhatsApp). O telefone real do remetente está em `senderPn: "5521979685845@s.whatsapp.net"`. O parser atual do epic 001 (`parse_evolution_message`) só conhece `@s.whatsapp.net` e `@g.us`. **Será necessário** um fallback `remoteJid (lid) → senderPn` durante o refactor (task T6 ou nova task T6b).
- **`sender` field contém o número do bot** — `"5511910375690@s.whatsapp.net"`. Esse virou o `mention_phone` do tenant `pace-internal` (confirmado por Gabriel em 2026-04-10).
- **Campos Chatwoot** — `chatwootMessageId`, `chatwootInboxId`, `chatwootConversationId` aparecem no payload porque a Evolution está integrada com Chatwoot. Puramente informativo; o parser deve ignorar.
- **Campos de device metadata** — `messageContextInfo.deviceListMetadata` tem chaves de criptografia irrelevantes para nosso fluxo. Ignorar.
- **`instanceId` UUID** — `"7a56eefd-45a3-4f59-baf3-86af4bda9d42"` é um identificador mais robusto que o `instance_name`. Útil como tiebreaker em logs, mas não precisamos usar como chave de lookup no Fase 1.

**Secret de dev gerado:** `d9b945d117bddb5b85480802e39d0d17b216aab7b03e7f9549107eeabc7e5b75` (armazenado em `.env` local, gitignored).

**Webhook apontado para Tailscale:** após a validação, o webhook foi reconfigurado para `http://100.77.80.33:8050/webhook/whatsapp/Ariel` (IP Tailscale da máquina de dev). Enquanto o serviço não estiver rodando, a Evolution vai acumular retries que falham com connection refused — **não enviar mensagens de teste** até `docker compose up` estar funcional.

---

## 5. Alternativas Avaliadas

Cada alternativa é uma combinação de (a) modelo de auth, (b) modelo de tenancy, (c) topologia de rede.

### 5.1. Alternativa A — "4 camadas paranoicas"

**Descrição:** Manter HMAC (desabilitando só se `WEBHOOK_SECRET` vazio) + validar `body.apikey` + header secret + rate limit + idempotência.

**Prós:**
- "Defense in depth" clássico.
- Muita camada.

**Contras:**
- HMAC é inútil porque Evolution não assina nada.
- Validar `body.apikey` é teatro (não é credencial real).
- Código inflado, testes complexos.
- Multi-tenancy não é resolvida — ainda é single-tenant.

**Rejeitada:** combina 2 camadas sem valor real (HMAC + apikey) com as camadas que valem (rede + secret + idempotência).

### 5.2. Alternativa B — "Solução enxuta single-tenant"

**Descrição:** Remover HMAC. Confiar na rede (Docker network / Tailscale). Adicionar idempotência. **Sem** conceito de tenant.

**Prós:**
- Mínimo código possível (~15 linhas de auth).
- Fácil de entender.
- Suficiente para o uso interno atual.

**Contras:**
- Quando chegar a hora de abrir para clientes externos, precisa refatorar `config.py` (de globais para por-tenant), `webhooks.py` (resolver tenant), `dependencies.py`, `debounce.py` (isolar keys por tenant), `main.py` (carregar tenant store), e **todos os testes**.
- Refatoração de multi-tenancy é historicamente uma das mais dolorosas em codebases que começaram single-tenant (chave primária dupla, isolamento de dados, auth quebrada em N lugares).

**Rejeitada:** dívida técnica garantida e previsível. Gabriel já disse que multi-tenant é o end-state.

### 5.3. Alternativa C — "Multi-tenant completo desde o dia 1"

**Descrição:** Abstração `Tenant`, tenant store em YAML, auth por header per-tenant, idempotência por `(tenant_id, message_id)`, isolamento de rede. Admin API, Postgres, rate limit, billing — **tudo já nesta fase**.

**Prós:**
- Zero refactor futuro.

**Contras:**
- Escopo enorme. ~2000+ linhas de código novo.
- Complica o deploy atual (Postgres, migrations, admin UI, etc.).
- Gasta esforço em features que ainda não têm cliente real.

**Rejeitada:** overengineering. Muitos desses itens (admin API, Postgres, rate limit) só fazem sentido quando houver tenants reais para gerenciar.

### 5.4. Alternativa D — "Multi-tenant estrutural + operação single-tenant" ⭐

**Descrição:** Implementar a **estrutura** multi-tenant (tenant, tenant store, resolver, auth per-tenant, idempotência per-tenant, keys isoladas) **agora**, mas operar com **1 tenant** (Pace). Admin API, Postgres, rate limit, billing **ficam para Fase 2/3**.

**Prós:**
- Todo código já é multi-tenant — refatoração futura é zero.
- Escopo controlado: só o que é necessário para suportar N tenants eventualmente.
- Fase 2 (abrir para externos) é só **adicionar Caddy + endpoints admin** — nenhum código de domínio muda.
- Dev ergonomics: tenant store em YAML é trivial de editar.

**Contras:**
- ~400-600 linhas a mais do que a Alternativa B.
- Precisa pensar na abstração de `Tenant` desde já (nome, campos, storage).

**Escolhida.** Esta é a proposta deste documento.

### 5.5. Tabela comparativa

| Critério | A (4 camadas) | B (enxuta ST) | C (MT completo) | **D (MT estrutural)** ⭐ |
|---|---|---|---|---|
| Funciona com Evolution real | ❌ (HMAC imaginário) | ✅ | ✅ | ✅ |
| Suporta multi-tenant | ❌ | ❌ | ✅ | ✅ |
| Refactor futuro necessário | alto | alto | zero | zero |
| Linhas de código (estimado) | ~600 | ~200 | ~2000+ | ~800 |
| Teatro de segurança | sim (HMAC, apikey) | não | não | não |
| Escopo cabe em 1 PR | não | sim | não | sim (grande) |
| Dev ergonomics | ruim | ótimo | ruim | bom |

---

## 6. Arquitetura Escolhida (Alternativa D)

### 6.1. Modelo conceitual

```
┌─────────────────────────────────────────────────────────────┐
│                          ProsauAI                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  FastAPI: POST /webhook/whatsapp/{instance_name}     │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼────────────────────────────────┐   │
│  │  TenantResolver: instance_name → Tenant              │   │
│  │  (404 se desconhecido)                               │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼────────────────────────────────┐   │
│  │  Auth: validate X-Webhook-Secret == tenant.secret   │   │
│  │  (constant-time compare; 401 se inválido)           │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼────────────────────────────────┐   │
│  │  Idempotency: Redis SETNX                            │   │
│  │  key: seen:{tenant.id}:{message_id}                  │   │
│  │  TTL: 24h                                            │   │
│  │  se já existe → 200 OK + status="duplicate"         │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼────────────────────────────────┐   │
│  │  Parse → Route → Debounce (keys: buf:{tenant}:...)  │   │
│  │  (código existente do epic 001, só trocando keys)   │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼────────────────────────────────┐   │
│  │  EvolutionProvider (tenant.evolution_url + api_key)  │   │
│  │  envia echo/resposta                                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 6.2. Novo arquivo: `config/tenants.yaml`

Tenant store inicial, versionado apenas como **template** (`config/tenants.example.yaml`). O real (`config/tenants.yaml`) fica **gitignored** e montado via volume Docker no container em `/app/config/tenants.yaml`.

**Por que `config/` em vez de raiz?** Separação "código × configuração", convenção Docker (`./config:/app/config:ro` é mount de pasta inteira, escalável quando adicionarmos `routing_rules.yaml`, `prompts/`, etc.), e raiz do repo fica limpa.

```yaml
# config/tenants.yaml (já criado — real values)
tenants:
  - id: pace-internal
    instance_name: Ariel
    evolution_api_url: https://evolutionapi.pace-ia.com
    evolution_api_key: ${PACE_EVOLUTION_API_KEY}  # interpolado do env
    webhook_secret: ${PACE_WEBHOOK_SECRET}
    mention_phone: "5511910375690"  # número real do Ariel (validado 2026-04-10)
    mention_keywords:
      - "@ariel"
    enabled: true
```

**Vantagem do YAML:** fácil de editar manualmente, suporta comentários, interpolação de env vars mantém segredos fora do VCS.

**Status atual:** arquivo **já criado** em `config/tenants.yaml` (gitignored) e `config/tenants.example.yaml` (template commitável). Esperando o `TenantStore` ser implementado para ser consumido.

### 6.3. Nova abstração: `Tenant`

```python
# prosauai/core/tenant.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Tenant:
    """Immutable tenant configuration.

    Mention detection strategy:
    - In modern group messages, WhatsApp mentions carry opaque @lid
      strings (e.g. "146102623948863@lid") in
      `data.contextInfo.mentionedJid`. Compare with `mention_lid_opaque`.
    - In legacy group messages, mentions carry phone JIDs
      ("5511999999999@s.whatsapp.net"). Compare with `mention_phone`.
    - As a last resort, do a case-insensitive substring match of any
      element in `mention_keywords` against the message text.

    Discovery: see IMPLEMENTATION_PLAN.md §7.6.2.1 (Descoberta #4) for
    how to find `mention_lid_opaque` for a new tenant.
    """

    id: str
    instance_name: str
    evolution_api_url: str
    evolution_api_key: str
    webhook_secret: str
    mention_phone: str                          # E.164 phone (legacy group mention)
    mention_lid_opaque: str                     # 15-digit opaque LID (modern group mention)
    mention_keywords: tuple[str, ...] = field(default=())
    enabled: bool = True
```

### 6.4. Tenant store (file-backed)

```python
# prosauai/core/tenant_store.py
class TenantStore:
    """In-memory cache of tenants loaded from YAML at startup."""

    def __init__(self, tenants: list[Tenant]):
        self._by_id: dict[str, Tenant] = {t.id: t for t in tenants}
        self._by_instance: dict[str, Tenant] = {t.instance_name: t for t in tenants}

    @classmethod
    def load_from_file(cls, path: Path) -> TenantStore:
        """Load tenants.yaml, interpolating ${ENV_VAR} references."""
        ...

    def find_by_instance(self, instance_name: str) -> Tenant | None:
        return self._by_instance.get(instance_name) if \
               (t := self._by_instance.get(instance_name)) and t.enabled else None

    def get(self, tenant_id: str) -> Tenant | None:
        return self._by_id.get(tenant_id)
```

### 6.5. Novo `config.py` — separação global vs per-tenant

```python
class Settings(BaseSettings):
    """Global application settings.

    Note: tenant-specific config (evolution_*, webhook_secret, mention_*)
    has been moved to tenants.yaml. Only truly global settings remain here.
    """

    # Server
    host: str = "0.0.0.0"
    port: int = 8050
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Debounce
    debounce_seconds: float = 3.0
    debounce_jitter_max: float = 1.0

    # Tenant store
    tenants_file: str = "/app/config/tenants.yaml"

    # Idempotency
    idempotency_ttl_seconds: int = 86400  # 24h
```

**Nenhum** campo tenant-specific. A `Settings` não mais conhece Evolution.

### 6.6. Novo `dependencies.py` — resolver tenant + valida secret

```python
async def resolve_tenant_and_authenticate(
    request: Request,
    instance_name: str,
) -> tuple[Tenant, bytes]:
    """Resolve tenant from path and validate webhook secret.

    Returns:
        (tenant, raw_body) — body returned to avoid re-reading stream.

    Raises:
        404 if instance_name unknown or tenant disabled.
        401 if X-Webhook-Secret missing or wrong.
    """
    tenant_store: TenantStore = request.app.state.tenant_store

    tenant = tenant_store.find_by_instance(instance_name)
    if tenant is None:
        raise HTTPException(404, "Unknown instance")

    provided = request.headers.get("x-webhook-secret", "")
    if not hmac.compare_digest(provided, tenant.webhook_secret):
        raise HTTPException(401, "Invalid webhook secret")

    body = await request.body()
    return tenant, body
```

### 6.7. Novo helper: idempotência

```python
async def check_and_mark_seen(
    redis: Redis,
    tenant_id: str,
    message_id: str,
    ttl_seconds: int,
) -> bool:
    """Return True if this is the first time we see this message, False if duplicate.

    Uses Redis SETNX atomically.
    Key format: seen:{tenant_id}:{message_id}
    """
    key = f"seen:{tenant_id}:{message_id}"
    return bool(await redis.set(key, "1", nx=True, ex=ttl_seconds))
```

### 6.8. Novo `webhooks.py` — fluxo completo

```python
@router.post("/webhook/whatsapp/{instance_name}")
async def webhook_whatsapp(instance_name: str, request: Request) -> WebhookResponse:
    tenant, body = await resolve_tenant_and_authenticate(request, instance_name)

    payload = _parse_json(body)

    try:
        message = parse_evolution_message(payload)
    except MalformedPayloadError as exc:
        raise HTTPException(400, f"Invalid payload: {exc.detail}") from exc

    # Idempotency check (before routing)
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        is_new = await check_and_mark_seen(
            redis, tenant.id, message.message_id,
            ttl_seconds=request.app.state.settings.idempotency_ttl_seconds,
        )
        if not is_new:
            return WebhookResponse(
                status="duplicate", route="ignore", message_id=message.message_id,
            )

    result = route_message(message, tenant)  # router recebe Tenant, não Settings

    # ... resto igual ao código atual, mas com keys/config vindas de `tenant`
```

### 6.9. Mudanças em `debounce.py` — keys isoladas por tenant

Hoje:
```
buf:{phone}:{ctx}
tmr:{phone}:{ctx}
```

Novo:
```
buf:{tenant_id}:{phone}:{ctx}
tmr:{tenant_id}:{phone}:{ctx}
```

**Motivo:** evita colisão entre tenants quando 2 clientes tiverem instâncias Evolution com usuários coincidentes (mesmo phone number em 2 instâncias diferentes). E facilita debug (`redis-cli keys 'buf:cliente-acme:*'`).

O listener `parse_expired_key` precisa ser ajustado para extrair `tenant_id` também.

### 6.10. Mudanças em `router.py` — receber Tenant em vez de Settings

Hoje:
```python
def route_message(message: ParsedMessage, settings: Settings) -> RouteResult:
    ...
    if settings.mention_phone in message.mentioned_phones:
```

Novo — com detecção de mention em 3 estratégias (baseada nas descobertas
§7.6.2.1 Descoberta #4):

```python
def route_message(message: ParsedMessage, tenant: Tenant) -> RouteResult:
    ...
    if _is_bot_mentioned(message, tenant):
        return RouteResult(route=MessageRoute.GROUP_RESPOND)
    ...


def _is_bot_mentioned(message: ParsedMessage, tenant: Tenant) -> bool:
    """Three-strategy mention detection for the bot.

    Strategy 1 (primary, modern): compare the @lid opaque IDs in
    `message.mentioned_jids` against `tenant.mention_lid_opaque`. This
    works for all group messages where WhatsApp carries structured
    mentions (seen in 100% of our captured mentions).

    Strategy 2 (fallback, legacy): compare phone JIDs in
    `message.mentioned_jids` against `tenant.mention_phone`. Kept for
    any future payloads where the mention list contains
    `<phone>@s.whatsapp.net` entries instead of `<lid>@lid`.

    Strategy 3 (last resort): case-insensitive substring match of any
    `tenant.mention_keywords` inside `message.text`. Used when no
    structured mention is present but the user wrote "@ariel" as plain
    text.
    """
    # Strategy 1: opaque LID match (primary path — all modern groups)
    target_lid = f"{tenant.mention_lid_opaque}@lid"
    if target_lid in message.mentioned_jids:
        return True

    # Strategy 2: legacy phone JID match
    target_phone = f"{tenant.mention_phone}@s.whatsapp.net"
    if target_phone in message.mentioned_jids:
        return True

    # Strategy 3: keyword substring match
    text_lower = (message.text or "").lower()
    return any(kw.lower() in text_lower for kw in tenant.mention_keywords)
```

**Nota:** `message.mentioned_jids` (novo nome — antes era
`mentioned_phones`) contém os JIDs exatamente como vieram em
`data.contextInfo.mentionedJid`, que já é uma lista de strings no
formato `<lid>@lid`. Não há conversão — comparamos literalmente. Isso
está validado pela fixture `resenhai_msg_group_text_mention_jid`.

### 6.11. Mudanças em `main.py` — lifespan carrega tenant store

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    settings = Settings()
    app.state.settings = settings

    # Load tenants
    tenant_store = TenantStore.load_from_file(Path(settings.tenants_file))
    app.state.tenant_store = tenant_store
    logger.info("tenants_loaded", count=len(tenant_store._by_id))

    # ... resto igual (Redis, debounce)
```

### 6.12. `.env` simplificado

**Status atual:** arquivo **já criado** em `.env` (gitignored) com os valores reais. `.env.example` commitável como template.

```bash
# -- Server --
HOST=0.0.0.0
PORT=8050
DEBUG=true

# -- Redis --
REDIS_URL=redis://localhost:6379

# -- Debounce (global defaults) --
DEBOUNCE_SECONDS=3.0
DEBOUNCE_JITTER_MAX=1.0

# -- Tenant Store --
TENANTS_FILE=/app/config/tenants.yaml

# -- Idempotency --
IDEMPOTENCY_TTL_SECONDS=86400

# -- Tenant secrets (interpolados em config/tenants.yaml) --
PACE_EVOLUTION_API_KEY=2C7A1C0AAECC-4E26-AE91-7848C8B69002
PACE_WEBHOOK_SECRET=d9b945d117bddb5b85480802e39d0d17b216aab7b03e7f9549107eeabc7e5b75
```

**Nenhum** campo tenant-específico aqui fora de secrets. As URLs, nomes, keywords, etc. estão todas no YAML.

---

## 7. Estratégia de Deploy (Rede)

### 7.1. Desenvolvimento local (WSL, Gabriel)

**Problema:** Evolution API remota (`evolutionapi.pace-ia.com`) precisa alcançar o ProsauAI rodando na máquina do Gabriel.

**Solução:** bind do Docker só na interface Tailscale.

```yaml
# docker-compose.override.yml (gitignored, específico do dev)
services:
  api:
    ports:
      - "100.77.80.33:8050:8050"  # IP Tailscale do ntb-25-0543
```

Webhook na Evolution aponta para `http://ntb-25-0543:8050/webhook/whatsapp/Ariel` (via MagicDNS) ou `http://100.77.80.33:8050/...`.

Proteção: Tailscale ACLs restringem acesso à porta 8050 apenas ao nó Evolution (`srv764430`).

### 7.2. Produção single-tenant (VPS Hostinger — Fase 1)

**Topologia:** Evolution API + ProsauAI + Redis na mesma VPS, mesma Docker network, nenhuma porta exposta.

```yaml
# docker-compose.yml (sem override em prod)
services:
  api:
    build: .
    networks: [pace-net]
    # NOTE: sem "ports" — não exposto no host
    volumes:
      - ./config/tenants.yaml:/app/config/tenants.yaml:ro
    env_file: .env
    depends_on:
      redis: {condition: service_healthy}

  redis:
    image: redis:7-alpine
    networks: [pace-net]
    command: redis-server --notify-keyspace-events Ex

networks:
  pace-net:
    external: true  # criada manualmente, compartilhada com a Evolution
```

Evolution (rodando na mesma rede) aponta webhook para `http://api:8050/webhook/whatsapp/Ariel` — resolve via DNS interno do Docker. Tráfego nunca sai do host.

**Risco mitigado:** não há interface para um atacante externo sequer alcançar `8050`.

### 7.3. Produção multi-tenant (Fase 2)

Adiciona Caddy/Traefik na frente:

```yaml
# adição em Fase 2
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    networks: [pace-net]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data

# Caddyfile
api.prosauai.com {
    reverse_proxy api:8050
    rate_limit {zone tenants 100r/m}  # rate limit global
}
```

**Fluxo de tráfego externo:** Cliente → Internet → Caddy (TLS + rate limit) → ProsauAI (rede privada) → Redis.

**Importante:** a VPS **ainda** só expõe 80/443 (via Caddy). A porta 8050 continua sem `ports:`. Caddy é o único jeito de bater no ProsauAI de fora.

### 7.4. Comparação dos cenários

| Config | Dev (WSL+Tailscale) | Prod Fase 1 | Prod Fase 2 |
|---|---|---|---|
| `docker-compose.yml` base | sem `ports` | sem `ports` | sem `ports` |
| `docker-compose.override.yml` | bind Tailscale | *(não existe)* | *(não existe)* |
| Porta pública | só Tailscale | nenhuma | 443 (Caddy) |
| Evolution webhook URL | `http://ntb-25-0543:8050/...` | `http://api:8050/...` | `https://api.prosauai.com/...` |
| Caddy | não | não | sim |
| Tenants | 1 (Pace) | 1 (Pace) | N |

**Propriedade importante:** o **mesmo** `docker-compose.yml` base funciona nos 3 cenários. A diferença está em `override.yml` (dev) e em um `docker-compose.prod.yml` adicional (Fase 2).

### 7.5. Decisão de porta: 8050

**Contexto:** a máquina de dev do Gabriel já roda vários serviços em portas do padrão `80X0`:

| Porta | Serviço | Notas |
|---|---|---|
| 8010 | automation-api | Tennis booking (ilarme). systemd. |
| 8020 | doc-api | Doc converter + PDF password crack. Docker compose. |
| 8030 | wpp-bridge | WhatsApp bridge (systemd). |
| 8040 | madruga-ai | Daemon 24/7 + dashboard. |
| 8765 | personal_os | Browser dashboard p/ skills. systemd user. |

**Problema:** o epic 001 tinha deixado o ProsauAI na porta `8040`, já ocupada pelo `madruga-ai`.

**Decisão:** usar **`8050`** — próxima da sequência após `8040`. Motivos:

- Continua o padrão sequencial Pace (`80X0`).
- Evita conflito.
- Evita também a porta `8080` (padrão do Evolution Manager), que seria confuso.
- Deixa o range `8050-8059` mentalmente reservado para sub-serviços do ProsauAI (ex: admin UI em `8051` no futuro).

**Alternativas consideradas e rejeitadas:**

- `9040` — quebra o padrão de portas do Gabriel.
- Porta aleatória alta (ex: `38400`) — difícil de lembrar, sem vantagem real.
- `8080` — é a porta default do Evolution Manager, risco de confusão operacional.

**Arquivos afetados por essa mudança** (já aplicada):

- `.env` / `.env.example` — `PORT=8050` + comentário explicando a convenção
- `docker-compose.yml` — `ports: "8050:8050"` (base; em prod vai ficar sem ports)
- `Dockerfile` — `EXPOSE 8050`, healthcheck, CMD uvicorn
- `prosauai/config.py` — `port: int = 8050` (default)
- `tests/conftest.py` — fixture `mock_settings` com `port=8050`
- `README.md` — todas as referências atualizadas
- Webhook da Evolution — já reapontado para `http://100.77.80.33:8050/webhook/whatsapp/Ariel`

---

## 7.6. Trabalho Já Executado (estado inicial antes de começar o código)

Esta seção documenta **tudo** que foi feito antes do primeiro commit da branch `feat/multi-tenant-auth`, para que qualquer pessoa pegando o projeto depois entenda o ponto de partida sem precisar reler a conversa de planejamento.

### 7.6.1. Investigação e validação de hipóteses

| Item | Descrição | Resultado |
|---|---|---|
| Source-dive Evolution API | Confirmar se HMAC signing existe nativamente | ❌ Não existe (seção 4.1). Issue #102 fechada sem implementação. |
| Teste empírico de `X-Webhook-Secret` | Configurar webhook real com `headers` e verificar se Evolution encaminha | ✅ Funciona (seção 4.5). Validado via webhook.site com Evolution v2.3.0. |
| Captura de payload real | Mandar WhatsApp real e analisar JSON | Descobriu `@lid` format, `senderPn`, campos Chatwoot, número do Ariel. |

### 7.6.2. Configurações da Evolution API

A Evolution v2.3.0 da Pace (`https://evolutionapi.pace-ia.com`) hospeda
**duas instâncias** que vamos validar como tenants distintos. Cada uma
tem **API key diferente**, **número diferente**, e **webhook secret
diferente**:

| Tenant ID | Instância | API Key | Bot phone | Webhook Secret |
|---|---|---|---|---|
| `pace-internal` | `Ariel` | `2C7A1C0A...B69002` | `5511910375690` | `d9b945d1...b75` |
| `resenha-internal` | `ResenhAI` | `6665FC68...CA72B` | `5511970972463` | `1f15920e...8cb7` |

Os valores completos estão em `.env` (gitignored).

**Por que duas instâncias desde o dia 1:** garante que a refatoração
multi-tenant é validada com tenants reais isolados em paralelo, não com
mocks. Pega bugs que single-tenant esconde — cross-tenant key collision
no Redis, cache global por engano, escolha errada de credencial em logs,
etc.

**Webhook config — Ariel (pace-internal):**

```bash
curl -X POST 'https://evolutionapi.pace-ia.com/webhook/set/Ariel' \
  -H 'apikey: 2C7A1C0AAECC-4E26-AE91-7848C8B69002' \
  -H 'Content-Type: application/json' \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "http://100.77.80.33:8050/webhook/whatsapp/Ariel",
      "headers": {
        "X-Webhook-Secret": "d9b945d117bddb5b85480802e39d0d17b216aab7b03e7f9549107eeabc7e5b75"
      },
      "events": ["MESSAGES_UPSERT", "GROUPS_UPSERT"],
      "webhookByEvents": false,
      "webhookBase64": true
    }
  }'
```

**Webhook config — ResenhAI (resenha-internal):**

```bash
curl -X POST 'https://evolutionapi.pace-ia.com/webhook/set/ResenhAI' \
  -H 'apikey: 6665FC687A7A-428F-AAFC-ABF05FBCA72B' \
  -H 'Content-Type: application/json' \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "http://100.77.80.33:8050/webhook/whatsapp/ResenhAI",
      "headers": {
        "X-Webhook-Secret": "1f15920e077262db7ab4cf5c4f25c80c484342ce58f97f0cd62cec49a5bb8cb7"
      },
      "events": ["MESSAGES_UPSERT", "GROUPS_UPSERT"],
      "webhookByEvents": false,
      "webhookBase64": true
    }
  }'
```

**Estado atual dos webhooks** (validado via `GET /webhook/find/{instance}`):

| Instance | URL atual | Aponta para | instanceId |
|---|---|---|---|
| Ariel | `http://100.77.80.33:8051/capture/Ariel` | **Capture tool** (porta 8051) | `7a56eefd-45a3-4f59-baf3-86af4bda9d42` |
| ResenhAI | `http://100.77.80.33:8051/capture/ResenhAI` | **Capture tool** (porta 8051) | `5da597e9-7511-44a0-8ead-a90f859aaf73` |

**Importante:** durante a fase de captura de fixtures, ambos os webhooks
apontam para `:8051` (capture tool), **não** para `:8050` (serviço real).
Quando a captura terminar e o serviço real estiver rodando, ambos voltam
para `:8050/webhook/whatsapp/{instance}`. Os comandos de rollback estão
em [tools/README.md](tools/README.md) seção "Cleanup".

### 7.6.2.1. Estrutura de payload — descobertas críticas (**validadas empiricamente com 36 capturas reais**)

Capturamos 36 webhooks reais (ver §7.6.8) que **contradizem várias
premissas** do parser do epic 001. Todas as descobertas abaixo estão
representadas em fixtures committáveis em
[`tests/fixtures/captured/`](tests/fixtures/captured/).

#### Descoberta #1 — Eventos observados na Evolution v2.3.0 (tipos reais)

Total de **3 eventos distintos** observados em 36 capturas:

| Evento | Ocorrências | Shape de `data` | Uso |
|---|---|---|---|
| `messages.upsert` | 32 (89%) | **dict** com `key`, `message`, `messageType`, ... | Mensagens de chat (texto, mídia, interativo) |
| `groups.upsert` | 3 (8%) | **lista** de objetos group | Snapshot completo da metadata do grupo (disparado em qualquer mudança) |
| `group-participants.update` | 1 (3%) | **dict** sem `key`, com `{id, author, action, participants[]}` | Add/remove/promote/demote de participante |

**Nenhum `groups.update` observado.** O epic 001 assumia que esse evento
existia (`_is_group_event` testa `event == "groups.update"`); é uma
suposição **errada**. O evento real é `group-participants.update` (com
hífen, não underscore).

#### Descoberta #2 — `messageType` values NÃO são `image`/`video`/etc.

O parser do epic 001 (`prosauai/core/formatter.py:46-52`) mapeia
`messageType` para `*Message` keys assumindo valores curtos (`image`,
`document`, `video`, `audio`, `sticker`). **Não bate com a realidade.**

Valores reais observados:

| messageType real | Captures |
|---|---|
| `conversation` | 16 ✓ (único que bate) |
| `imageMessage` | 3 |
| `stickerMessage` | 2 |
| `audioMessage` | 2 |
| `reactionMessage` | 2 |
| `videoMessage` | 1 |
| `documentMessage` | 1 |
| `locationMessage` | 1 |
| `liveLocationMessage` | 1 |
| `contactMessage` | 1 |
| `pollCreationMessageV3` | 1 |
| `eventMessage` | 1 |
| (vazio) | 1 |

**16 das 32 mensagens (50%)** caem em "unknown message type" com o
parser atual, retornam `text=""` e `media_type=None` silenciosamente.
Bug catastrófico.

#### Descoberta #3 — `messages.upsert`: individual vs grupo

```jsonc
// INDIVIDUAL com @lid (formato novo)
{
  "data": {
    "key": {
      "remoteJid": "200759773786203@lid",        // @lid opaco (15 dígitos)
      "fromMe": false,
      "id": "3A523E3773D0DD417D2C",
      "senderPn": "5521979685845@s.whatsapp.net" // phone real — ESPELHO
    },
    "message": {"conversation": "Oi"}
  }
}

// INDIVIDUAL com @s.whatsapp.net (formato legacy)
{
  "data": {
    "key": {
      "remoteJid": "5521979685845@s.whatsapp.net", // phone real
      "fromMe": false,
      "id": "3EB07D614C300B85360585",
      "senderLid": "200759773786203@lid"            // @lid — ESPELHO
    },
    "message": {"conversation": "..."}
  }
}

// GRUPO
{
  "data": {
    "key": {
      "remoteJid": "120363421904721723@g.us",    // group JID
      "fromMe": false,
      "id": "3AC37624058F2396953A",
      "participant": "200759773786203@lid"        // quem mandou (@lid)
      // NOTE: NÃO há senderPn nem senderLid em grupo
    },
    "message": {"conversation": "Vdd"}
  }
}
```

**Regras extraídas:**

| Situação | sender_phone | sender_lid_opaque | group_id |
|---|---|---|---|
| Individual `@lid` + `senderPn` presente | `key.senderPn` | `key.remoteJid.split('@')[0]` | `null` |
| Individual `@s.whatsapp.net` + `senderLid` presente | `key.remoteJid.split('@')[0]` | `key.senderLid.split('@')[0]` | `null` |
| Grupo (participant é @lid) | **`null`** (não disponível) | `key.participant.split('@')[0]` | `key.remoteJid.split('@')[0]` |
| `fromMe: true` em individual @lid | `null` (não relevante) | `key.remoteJid.split('@')[0]` | `null` |

**Implicação crítica pro debounce/idempotência:** em grupo o phone real
**não está disponível inline**. A chave de identidade tem que usar o
**`@lid` opaco** (que é estável — mesma pessoa sempre tem o mesmo
`@lid`). Chave canônica do sender:

```python
sender_key = sender_lid_opaque or sender_phone
```

Esse `sender_key` entra nas chaves Redis do debounce
(`buf:{tenant_id}:{sender_key}:{ctx}`).

#### Descoberta #4 — `mentionedJid` vive em `data.contextInfo`, não em `extendedTextMessage`

O parser do epic 001 (`formatter.py:254-258`) extrai mentions assim:

```python
if message_type == "extendedText":
    ext = message.get("extendedTextMessage", {})
    ctx = ext.get("contextInfo", {})
    return ctx.get("mentionedJid", [])
```

**Errado duas vezes:**

1. O `messageType` real é `extendedTextMessage` (não `extendedText`) —
   nunca matcha. Mas mesmo se corrigíssemos:
2. Na realidade, **mentions chegam em mensagens `conversation`** (não
   `extendedTextMessage`), e o `mentionedJid` vive em
   **`data.contextInfo.mentionedJid`** — um nível acima do esperado,
   diretamente em `data`, não dentro da sub-message.

Exemplo real (fixture `resenhai_msg_group_text_mention_jid`):

```jsonc
{
  "data": {
    "key": {"remoteJid": "...@g.us", "participant": "...@lid"},
    "message": {"conversation": "@146102623948863 me ajuda"},
    "contextInfo": {
      "mentionedJid": ["146102623948863@lid"]  // ← aqui
    },
    "messageType": "conversation"
  }
}
```

Consequências:

1. **Toda detecção de @mention do bot está quebrada** no epic 001 —
   `mentioned_phones` vira `[]`, router nunca roteia pra `GROUP_RESPOND`.
2. Parser precisa ler `data.contextInfo.mentionedJid` **independente**
   do `messageType`.
3. O texto cru tem `@<lid_opaco>` (ex: `@146102623948863`), não
   `@<phone>`. Pra detectar mention via keyword fallback, o parser teria
   que cruzar com `participants[]` do grupo — complicado. **Estratégia
   primária: sempre olhar `mentionedJid` estruturado.**

#### Descoberta #5 — `groups.upsert` tem `data` como LISTA

```jsonc
{
  "event": "groups.upsert",
  "instance": "ResenhAI",
  "data": [                            // ← LISTA, não dict!
    {
      "id": "120363421904721723@g.us",
      "subject": "Resenha-group",
      "subjectOwner": "200759773786203@lid",
      "subjectOwnerJid": "5521979685845@s.whatsapp.net",
      "owner": "200759773786203@lid",
      "ownerJid": "5521979685845@s.whatsapp.net",
      "desc": "Mudei a descrição",
      "participants": [
        {
          "id": "200759773786203@lid",
          "jid": "5521979685845@s.whatsapp.net",
          "admin": "superadmin"
        },
        {
          "id": "146102623948863@lid",
          "jid": "5511970972463@s.whatsapp.net",
          "admin": null
        }
      ],
      "author": "200759773786203@lid"
    }
  ]
}
```

O parser atual (`formatter.py:115-117`) **crasha** aqui:

```python
data: dict[str, Any] = payload.get("data", {})
if not isinstance(data, dict) or not data:
    raise MalformedPayloadError("Missing or empty 'data' field in payload")
```

`data` é lista → `isinstance(data, dict)` é False → HTTP 400 em todo
`groups.upsert`. **Zero do fluxo de grupo funciona** na versão atual.

Padrões observados:

- **Pares `*Owner`/`*OwnerJid`** — toda referência a pessoa no
  `groups.upsert` vem em par: `subjectOwner` (@lid) + `subjectOwnerJid`
  (phone). O parser pode usar o `*Jid` como fonte do phone real.
- **`participants[]`** — lista de membros com `id` (@lid), `jid`
  (phone), e `admin` (`null`, `"admin"`, `"superadmin"`).
- **`author`** (top-level do objeto do grupo) — quem disparou a
  mudança que gerou o snapshot.

#### Descoberta #6 — `group-participants.update` é o evento granular de add/remove

```jsonc
{
  "event": "group-participants.update",
  "instance": "ResenhAI",
  "data": {                            // ← dict, mas SEM `key`
    "id": "120363421904721723@g.us",
    "author": "200759773786203@lid",
    "participants": ["103487874539537@lid"],
    "action": "add"
  }
}
```

- `data` é dict mas **não tem campo `key`** → parser do epic 001 crasha
  em `"Missing or empty 'data.key' field in payload"`.
- Ações observadas: `add`. Ainda não vimos `remove`, `promote`, `demote`
  — documentação Baileys confirma que esses 4 são os valores possíveis.
- `participants` é **lista** mesmo com 1 elemento.
- Não há `jid` (phone) — só `@lid`. Resolver phone real exige cruzar
  com um `groups.upsert` recente.

Fluxo observado quando adicionou o bot Ariel ao grupo Resenha-group:

```
T+0:   group-participants.update   (ResenhAI webhook)  action=add
T+0:   groups.upsert  (ResenhAI webhook)  participants=3  ← snapshot
T+0:   groups.upsert  (Ariel webhook)     participants=3  ← cross-tenant!
```

**3 webhooks num único add.** O router precisa tratar os 3 como
`GROUP_EVENT` (IGNORE/log), e a idempotência precisa deduplicar
corretamente usando `(tenant_id, event_id)` — não dá pra confundir o
`groups.upsert` do ResenhAI com o do Ariel (mesmo grupo, tenants
diferentes).

#### Descoberta #7 — Cross-tenant: um evento, dois tenants

Quando dois bots (Ariel e ResenhAI) compartilham um grupo, **qualquer
evento no grupo dispara webhook para AMBOS os tenants**. Evidências nas
fixtures:

- `resenhai_groups_upsert_initial_2p`: evento no tenant ResenhAI,
  antes do Ariel ser adicionado (2 participants).
- `ariel_groups_upsert_after_add_3p`: **mesmo grupo**, evento no
  tenant Ariel, pós-add (3 participants). O tenant Ariel "descobriu" o
  grupo no momento em que seu bot foi adicionado.

Implicação: o tenant store não pode ter assunção de "1 grupo = 1
tenant". Múltiplos tenants podem ver o mesmo `group_id`. Idempotência e
debounce **precisam** ser prefixados por `tenant_id` (já está no plano
§6.9). Logs devem incluir `tenant_id` para desambiguar.

#### Descoberta #8 — Reply: `data.contextInfo.quotedMessage`

```jsonc
// fixture: ariel_msg_individual_lid_text_reply
{
  "data": {
    "key": {...},
    "message": {"conversation": "Obrigado"},  // texto da resposta
    "contextInfo": {                           // no TOPO de data
      "stanzaId": "A5A62669C4C6CC567D00CCC5D7927E00",  // ID da msg original
      "participant": "103487874539537@lid",   // quem mandou a original
      "quotedMessage": {                       // cópia da mensagem original
        "imageMessage": { ... }                // pode ser qualquer tipo
      }
    }
  }
}
```

- Reply usa o mesmo `messageType: conversation`. O que distingue é a
  presença de `data.contextInfo.quotedMessage`.
- O `stanzaId` aponta pra mensagem original — útil pra contexto do
  agente LLM.
- `quotedMessage` carrega a **mensagem original inteira** (se é
  imagem, carrega `imageMessage`; se texto, `conversation`; etc.).
- Mesmo `contextInfo` top-level que carrega `mentionedJid` (§4) — é um
  sub-objeto genérico que pode ter `{stanzaId, participant,
  quotedMessage, mentionedJid, ...}`.

#### Descoberta #9 — Texto longo e URL continuam `conversation`

Contradiz o fixture sintético do epic 001, que assumia
`extendedTextMessage` pra links. **No mundo real**, textos com URLs e
até blocos grandes (>200 chars, múltiplas linhas) vêm como simples
`conversation`:

```jsonc
// fixture: resenhai_msg_group_text_with_link
{
  "data": {
    "message": {
      "conversation": "ops:summary skill\nWeb Fetchhttps://valor.globo.com/..."
    },
    "messageType": "conversation"
  }
}
```

**Nem um único `extendedTextMessage` foi capturado.** Pode existir em
casos específicos (link preview explícito?) mas não é o caminho comum.
O parser **deve** tratar `conversation` como universal pra texto e
preparar branch `extendedTextMessage` como fallback.

#### Descoberta #10 — `reactionMessage` tem alvo

```jsonc
// fixture: ariel_msg_individual_lid_reaction
{
  "data": {
    "key": {...},
    "message": {
      "reactionMessage": {
        "key": {
          "id": "A5A62669C4C6CC567D00CCC5D7927E00"  // ID da mensagem reagida
        },
        "text": "❤️"   // o emoji
      }
    },
    "messageType": "reactionMessage"
  }
}
```

- `reactionMessage.text` é o emoji.
- `reactionMessage.key.id` aponta pra **outra** mensagem (a que está
  sendo reagida).
- **Decisão de roteamento:** reaction não deve disparar echo. Possível
  nova rota `REACTION` ou reutilizar `IGNORE` com reason específico.
  **Pendente decidir** — anotado na fixture como `_note`.

#### Descoberta #11 — Mídia com `base64` inline

Com `webhookBase64: true` (como nos nossos webhooks configurados), a
Evolution inclui o binário inteiro na payload:

```jsonc
{
  "data": {
    "message": {
      "imageMessage": { "url": "...", "mimetype": "image/jpeg", ... },
      "base64": "/9j/4AAQSkZJRgABAQAAAQABAAD/..."  // ← base64 inteiro aqui
    }
  }
}
```

- **`base64` está em `data.message.base64`** (não no topo de `data`
  como eu supus inicialmente — corrigido).
- Tamanho típico: imagem 120KB, vídeo 500KB+, áudio 30KB+, sticker
  160KB.
- **Parser NÃO deve depender de `base64`** — com `webhookBase64: false`
  o campo some. Parser usa `imageMessage.url` como referência,
  `base64` é acessório.

#### Descoberta #12 — Campos que o parser deve ignorar silenciosamente

Presentes em **toda** mensagem mas irrelevantes pro roteamento:

| Campo | Origem | Propósito |
|---|---|---|
| `messageContextInfo.deviceListMetadata` | WhatsApp E2E | Chaves de criptografia |
| `messageContextInfo.messageSecret` | WhatsApp E2E | Secret per-msg |
| `data.chatwootMessageId` | Chatwoot integration | ID no Chatwoot |
| `data.chatwootInboxId` | Chatwoot integration | Inbox ID |
| `data.chatwootConversationId` | Chatwoot integration | Conversation ID |
| `data.source` | Evolution | `ios`, `android`, `web`, etc. |
| `data.instanceId` | Evolution | UUID da instância (logar, não roteado) |
| `data.status` | Evolution | `DELIVERY_ACK`, `SERVER_ACK`, etc. |

Parser deve ler o que precisa e **ignorar** tudo o resto. **Não
falhar** se algum desses ausentes (outros deploys podem não ter Chatwoot
integration, por exemplo).

#### Descoberta #13 — `instanceId` UUID por instância

| Instância (anonimizada) | `instanceId` |
|---|---|
| Ariel | `anon-ariel-instance-0000-0000-000000000000` |
| ResenhAI | `anon-resenhai-instance-0000-0000-000000000000` |

Esse UUID é um identificador mais estável que o `instance_name` (não
muda se a instância for renomeada). **Decisão para Fase 1:** mantemos
`instance_name` como chave de lookup no path do webhook
(`/webhook/whatsapp/{instance_name}`), mas **logamos `instanceId` em
todo evento processado** para facilitar debug e auditoria.

### 7.6.3. Arquivos de configuração criados

| Arquivo | Commitável? | Status | Conteúdo |
|---|---|---|---|
| `.env` | ❌ gitignored | **Criado** | Global settings + secrets do tenant `pace-internal` (`PACE_EVOLUTION_API_KEY`, `PACE_WEBHOOK_SECRET`) |
| `.env.example` | ✅ commitado | **Criado** | Template sem segredos, instruções de `openssl rand -hex 32` |
| `config/tenants.yaml` | ❌ gitignored | **Criado** | Tenant `pace-internal` real com `${VAR}` interpolation para secrets |
| `config/tenants.example.yaml` | ✅ commitado | **Criado** | Template com exemplo fictício e instruções completas de onboarding de novo tenant (incluindo `curl` para configurar webhook na Evolution) |
| `.gitignore` | ✅ commitado | **Atualizado** | Adiciona `config/tenants.yaml` e `docker-compose.override.yml` à lista de ignorados |

**Conteúdo atual de `config/tenants.yaml`** (os segredos são interpolados de `.env` no load):

```yaml
tenants:
  - id: pace-internal
    instance_name: Ariel
    evolution_api_url: https://evolutionapi.pace-ia.com
    evolution_api_key: ${PACE_EVOLUTION_API_KEY}
    webhook_secret: ${PACE_WEBHOOK_SECRET}
    mention_phone: "5511910375690"  # real do Ariel, confirmado via payload
    mention_keywords:
      - "@ariel"
    enabled: true
```

### 7.6.4. Decisões operacionais congeladas

| Decisão | Valor | Rationale |
|---|---|---|
| ID do tenant 1 | `pace-internal` | Nome estável, não muda se Ariel virar outro número |
| `instance_name` tenant 1 | `Ariel` | Mesmo nome da instância Evolution |
| `mention_phone` Ariel | `5511910375690` | Descoberto no campo `sender` de webhook real (2026-04-10) |
| Secret webhook (Pace) | `d9b945d1...b75` | Gerado via `openssl rand -hex 32` (2026-04-10) |
| ID do tenant 2 | `resenha-internal` | Segundo tenant, para validar isolamento multi-tenant em produção |
| `instance_name` tenant 2 | `ResenhAI` | Mesmo nome da instância Evolution |
| `mention_phone` ResenhAI | `5511970972463` | Descoberto via `participants[].jid` em payload `groups.upsert` real |
| `mention_keywords` ResenhAI | `["@resenhai", "@resenha"]` | Placeholder, ajustável depois |
| Secret webhook (Resenha) | `1f15920e...8cb7` | Gerado via `openssl rand -hex 32` (2026-04-10) |
| API key tenant 2 | `6665FC68...CA72B` | Diferente do tenant 1 — cada instância Evolution tem sua própria |
| Porta do serviço | `8050` | Sequência Pace `80X0`, evita conflito com `madruga-ai` |
| Porta do capture tool | `8051` | `8050+1`, fica fora do caminho do serviço real |
| Tenant store | YAML em `config/tenants.yaml` | Ver seção 9.1 |
| Idempotência TTL | 86400s (24h) | Ver seção 9.5 |
| Secret rotation | Manual (editar `.env` + re-rodar `curl` acima) | Automação fica para Fase 2 |

### 7.6.5. Mudanças de porta já aplicadas no código existente

O epic 001 tinha deixado a porta `8040` hardcoded em vários lugares. **Todos** foram atualizados para `8050` **antes** de começar a branch `feat/multi-tenant-auth`, para não misturar a mudança de porta com a refatoração multi-tenant:

- `docker-compose.yml` — `ports: "8050:8050"` + comentário
- `Dockerfile` — `EXPOSE 8050`, healthcheck, CMD uvicorn
- `prosauai/config.py` — `port: int = 8050` default
- `tests/conftest.py` — fixture `mock_settings(port=8050)`
- `README.md` — todas as referências e exemplos

**Nota:** o README ainda contém exemplos antigos com HMAC que **serão reescritos** na task T15. A mudança de porta foi pontual para manter consistência; a reescrita completa fica para quando o código estiver implementado.

### 7.6.6. Tool de captura de payloads (`tools/payload_capture.py`)

Antes de começar a refatoração multi-tenant, criamos um tool descartável
para construir um catálogo de fixtures realistas a partir de webhooks
reais da Evolution. Está documentado em [tools/README.md](tools/README.md).

**O que faz:** sobe um FastAPI minúsculo na porta `8051` que aceita
`POST /capture/{instance_name}`, valida `X-Webhook-Secret` contra **uma
lista** de secrets aceitos (um por tenant), e salva cada payload como
`tools/captures/NNN_{instance}_{event}_{description}_{HHMMSS}.json`.

**Multi-tenant desde o capture:** o tool aceita N secrets simultaneamente
(hardcoded no script: Ariel + ResenhAI). Isso permite capturar payloads
de **ambos os tenants em paralelo** sem mexer em config — basta ambos os
webhooks Evolution apontarem para o mesmo endpoint, cada um com seu
secret. Os filenames distinguem tenant via `_ariel_` ou `_resenhai_`.

**Por que existe:** o `tests/fixtures/evolution_payloads.json` herdado do
epic 001 contém payloads **sintéticos** (ver linha 9: "Realistic Evolution
API v2.x webhook payloads"). Já descobrimos durante a validação que
existem formatos não cobertos (`@lid`, `senderPn`, campos Chatwoot). Sem
um catálogo real, vamos continuar descobrindo edge cases dolorosamente em
produção.

**Por que é descartável:** o arquivo é totalmente standalone (zero imports
de `prosauai/*`). Quando o catálogo estiver completo, basta `rm -rf
tools/` e o serviço continua funcionando normalmente. Os payloads
capturados ficam **gitignored** (telefones reais, mensagens reais).

**Estado dos webhooks durante a captura:**

A partir de 2026-04-10 ~11:30 BRT, **ambos** os webhooks foram reapontados
para o capture tool em `8051`:

- `Ariel` → `http://100.77.80.33:8051/capture/Ariel` (secret pace-internal)
- `ResenhAI` → `http://100.77.80.33:8051/capture/ResenhAI` (secret resenha-internal)

Quando a captura terminar e o serviço real estiver rodando, ambos voltam
para `http://100.77.80.33:8050/webhook/whatsapp/{instance}`. Comandos de
rollback em [tools/README.md](tools/README.md) seção "Cleanup".

**Estratégia de teste com fixtures anonimizadas:**

Adotamos o padrão "fixture pairs" (golden files) para evitar acoplar
testes a valores específicos:

```
tests/fixtures/captured/
  text_individual.input.json       ← payload anonimizado
  text_individual.expected.yaml    ← assertivas hand-written
  image_with_caption.input.json
  image_with_caption.expected.yaml
  ...
```

Cada `.expected.yaml` declara explicitamente o que o sistema **deve**
fazer com o payload: campos extraídos pelo parser, rota classificada,
ações disparadas, status HTTP esperado. Um único teste paramétrico
carrega todos os pares e roda assertivas.

**Por que essa abordagem em vez de snapshot/property-based:**

| Abordagem | Por que rejeitada |
|---|---|
| Snapshot testing (`syrupy`) | Frágil — qualquer mudança quebra tudo. Revisão é "tudo verde / tudo vermelho", não dá pra entender o que mudou. |
| Property-based (`hypothesis`) | Inadequado — queremos validar shapes reais, não invariantes em inputs gerados. |
| Behavior assertions hardcoded | Verboso — cada caso vira ~30 linhas de teste. |
| **Fixture pairs (golden files)** ⭐ | Adicionar caso novo = 2 arquivos. Diff-friendly. Auto-documentado. Anonimização não quebra (tests checam comportamento). |

**Fluxo do workflow de captura → fixture:**

1. Capturar payloads brutos com o tool → `tools/captures/*.json` (gitignored)
2. Anonimizar (script de sanitização) → `tests/fixtures/captured/<nome>.input.json`
3. Escrever `expected.yaml` correspondente baseado no comportamento desejado
4. Implementar código com TDD: rodar fixture pairs, ver falhas, implementar até passar
5. Bug futuro descoberto? Capturar o payload, criar par, fica como teste de regressão pra sempre

### 7.6.7. Catálogo de fixtures de teste — **gerado em 2026-04-10**

Como ponte entre o mundo real capturado e os testes automatizados, já
geramos um catálogo committável de fixtures baseado em payloads reais
anonimizados. Localização:

```
tests/fixtures/captured/
├── README.md                                 # matriz MECE de cobertura
├── <nome_do_caso>.input.json                 # payload anonimizado
├── <nome_do_caso>.expected.yaml              # assertivas hand-written
└── ...                                       # 26 pares = 52 arquivos
```

**Status:** gerado e validado. Cada fixture foi:

1. **Extraído** de uma captura real em `tools/captures/*.json`
   (gitignored).
2. **Anonimizado deterministicamente** pelo
   [tools/anonymize_captures.py](tools/anonymize_captures.py):
   - Phones: `5521979685845` → `5521999999001`,
     `5511910375690` → `5511999999100`,
     `5511970972463` → `5511999999200`
   - `@lid` opacos: `200759773786203` → `100000000000001`, etc.
   - Group ID: `120363421904721723` → `999999999999999999`
   - API keys: `2C7A1C0A...` → `ANON-PACE-API-KEY-...`
   - `instanceId` UUIDs: `7a56eefd-...` → `anon-ariel-instance-...`
   - `pushName "Gabriel"` → `Test User`
3. **Validado** contra o payload bruto — o script
   `tools/anonymize_captures.py` + teste manual confirmaram zero PII
   vazada em 26 fixtures, 52 arquivos.
4. **Pareado com `.expected.yaml`** descrevendo:
   - `description`: 1 linha
   - `tags`: classificação MECE
   - `parsed`: campos que o parser **deve** extrair
   - `route`: rota que o router **deve** classificar
   - (opcional) `response`: body HTTP esperado

**Importante — base64 NÃO é truncado.** Mídia binária inline (imagens,
vídeos, áudios) é mantida completa nas fixtures porque:

1. Não é confidencial (decisão de Gabriel, 2026-04-10).
2. Dá cobertura completa do shape do payload pro parser.
3. Permite testar handling de payloads grandes sem simulação.

**Cobertura MECE (ver [tests/fixtures/captured/README.md](tests/fixtures/captured/README.md) para matriz completa):**

| Dimensão | Valores cobertos |
|---|---|
| Eventos | `messages.upsert`, `groups.upsert`, `group-participants.update` — 3/3 |
| Tenants | Ariel + ResenhAI — 2/2 |
| Contextos | individual + grupo — 2/2 |
| Sender JID | `@lid+senderPn`, `@lid` (fromMe), `@s.whatsapp.net+senderLid`, grupo `participant=@lid` — 4 variantes |
| Content types | text, image, video, audio (PTT), document, sticker, location (static+live), contact, poll, event, reaction, group metadata — 13 |
| Modificadores | `fromMe: true` (5 variantes), reply, mention via `mentionedJid`, URL longa, base64 inline — 5 |

**Total: 26 fixture pairs.**

**Lacunas conhecidas (não bloqueantes):**

- `extendedTextMessage` real (nunca capturado — usuários mandam links
  dentro de `conversation`)
- `editedMessage` / `protocolMessage REVOKE` (edit/delete)
- Forwarded messages (`isForwarded` flag)
- `group-participants.update` com `remove`/`promote`/`demote`
- Mudança de nome/descrição de grupo — **confirmado empiricamente** que
  Evolution v2.3.0 **NÃO emite webhook** pra isso
- Non-PTT audio (áudio enviado da galeria)
- `contactsArrayMessage` (múltiplos contatos)

**Fluxo de uso (quando a refatoração começar):**

1. Um único teste paramétrico em
   `tests/integration/test_captured_fixtures.py` (task T16) vai carregar
   cada par `.input.json` + `.expected.yaml` e rodar assertions.
2. Adicionar novo caso = rodar o capture tool, gravar novo payload,
   adicionar entrada no `CATALOG` do anonymizer, rodar o script,
   editar o `.expected.yaml` gerado. Zero toque em código de teste.
3. Bug em produção → capturar o payload problemático, virar fixture,
   fica como teste de regressão pra sempre.

### 7.6.8. Auditoria de aderência — código atual vs. payloads reais

Antes de começar a refatoração, fizemos uma auditoria **campo por
campo** do epic 001 contra as 36 capturas reais. Resultado:

| # | Local | Suposição atual | Realidade | Impacto |
|---|---|---|---|---|
| **D1** | `formatter.py` `_MEDIA_TYPES` / `_KNOWN_MESSAGE_TYPES` | `messageType == "image"` etc. | Real: `imageMessage`, `videoMessage`, `audioMessage`, `documentMessage`, `stickerMessage`, `locationMessage`, `liveLocationMessage`, `contactMessage`, `reactionMessage`, `pollCreationMessageV3`, `eventMessage` | **50% das mensagens** caem em "unknown" → text vazio, media_type None |
| **D2** | `formatter.py` `_extract_content()` | `messageType == "extendedText"` | Real: `extendedTextMessage` (quando aparece) | Nunca matcharia mesmo se aparecesse |
| **D3** | `formatter.py` `_extract_mentions()` | `mentionedJid` em `message.extendedTextMessage.contextInfo` | Real: em `data.contextInfo` (top-level), dentro de mensagens `conversation` | Mention detection **100% quebrada** → GROUP_RESPOND nunca dispara |
| **D4** | `formatter.py` `_is_group_event` | `event == "groups.update"` | Real: eventos de grupo são `groups.upsert` e `group-participants.update`. `groups.update` nunca observado. | Eventos de grupo caem no branch errado |
| **D5** | `formatter.py` validação inicial | `data` é sempre dict | Real: `groups.upsert` tem `data` como lista | HTTP 400 em todo `groups.upsert` |
| **D6** | `formatter.py` resolução de sender | `phone = key.get("participant") or payload.get("sender") or remote_jid` | Fallback pra `payload.sender` é errado — `payload.sender` é o **bot**, não o sender. Para individual `@lid`, usar `key.senderPn`; pra grupo, usar `key.participant` (@lid opaco). | `ParsedMessage.phone` fica com o `@lid` opaco como valor → debounce/idempotência trocam identidade por engano |
| **D7** | `formatter.py` `MalformedPayloadError` pra `data.key` ausente | Toda mensagem tem `data.key` | `group-participants.update` tem `data` sem `key` | HTTP 400 em todo add/remove de participante |
| **D8** | `ParsedMessage.phone` como único identificador | Phone sempre disponível | Em grupo, só temos `@lid` opaco — phone **não está** inline | Schema precisa aceitar `sender_lid_opaque` como fallback de identidade |
| **D9** | `tests/fixtures/evolution_payloads.json` | Payloads sintéticos "baseados na documentação" | 100% desalinhado: usa `messageType: "image"` não `"imageMessage"`; sem `@lid`, `senderPn`, Chatwoot fields, base64 inline; `mentionedJid` em lugar errado | Todos os testes unitários do epic 001 passam contra dados que **não existem** no mundo real |
| **D10** | `router.py` `_is_bot_mentioned()` | Usa `message.mentioned_phones` + `tenant.mention_phone` (E.164) | Em grupo, `mentioned_phones` estaria vazio (D3) e mention real vem como `@lid` opaco — precisa comparar com `tenant.mention_lid` | Router nunca detecta mention no grupo |
| **D11** | Tenant config (`config/tenants.yaml` atual) | Tem `mention_phone`, `mention_keywords` | Falta `mention_lid_opaque` — sem isso, não dá pra comparar `mentionedJid` com o bot | Tenant schema incompleto |

**Também descobrimos que o epic 001 NÃO prevê:**

- **Reactions** — precisa decidir se vira nova rota ou IGNORE com
  reason específico.
- **Replies** — `quotedMessage` não é extraído; precisa decidir se
  entra no `ParsedMessage`.
- **Polls, events** — tipos interativos desconhecidos; vão virar
  `SUPPORT` sem texto se tratados como mensagem normal.

### 7.6.9. Estado do repositório Git

- Branch atual ao começar: `develop`
- Branch `main` e `develop` estão no mesmo ponto (tudo do epic 001 mergeado)
- Branch `epic/prosauai/001-channel-pipeline` continua existindo como "save point"
- Próxima branch a criar: `feat/multi-tenant-auth`
- **Nenhum commit foi feito ainda** após os ajustes de `.env`, `config/tenants.yaml`, `.gitignore`, porta. Tudo está como working-tree uncommitted na `develop`.

**Alternativa considerada:** commitar esses ajustes em `develop` antes de criar a branch de feature. **Rejeitada** porque:
- `.env` é gitignored, nada a commitar.
- `config/tenants.yaml` é gitignored, nada a commitar.
- Ajustes de porta podem ir na mesma branch da refatoração (commit separado "chore: migrate to port 8050"), o que mantém histórico linear.

---

## 8. Plano de Implementação Faseado

### Fase 0 — Especificações Canônicas (resolução dos gaps de implementação)

Esta fase **não tem código novo** — é o último passo de design antes da
codificação. Resolve os 7 gaps identificados na auditoria de
completude do plano (2026-04-10) que poderiam fazer o implementador
parar pra perguntar durante a Fase 1.

**Objetivo:** garantir que ao começar a Fase 1, **toda decisão técnica
já tenha resposta canônica neste documento**. Zero ambiguidade.

#### 8.0.1. Schema canônico do `ParsedMessage` refatorado

Hoje (`prosauai/core/formatter.py:14-36`) o `ParsedMessage` tem 12
campos. Pós-refatoração ele cresce pra ~22 campos para acomodar as
descobertas §7.6.2.1. Este é o schema **completo final** — qualquer
campo adicionado deve ser justificado contra um fixture real.

```python
# prosauai/core/formatter.py — pós-refatoração
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "messages.upsert",
    "groups.upsert",
    "group-participants.update",
]

MediaType = Literal[
    "image", "video", "audio", "document", "sticker",
    "location", "live_location", "contact",
    "poll", "event", "reaction",
]


class ParsedMessage(BaseModel):
    """Canonical representation of any Evolution webhook event.

    Generalized from epic 001's "message-only" model to also handle
    `groups.upsert` (snapshot) and `group-participants.update`
    (granular event) — see Descobertas §7.6.2.1 #5 and #6.

    The `phone` field of epic 001 was REMOVED. Sender identity is now
    compound (sender_phone, sender_lid_opaque) because in groups the
    real phone is not inline. The `sender_key` property gives the
    stable identity used by debounce/idempotency.
    """

    # ── Tenant context (set by webhook handler, not parser) ──────────
    tenant_id: str = Field(..., description="Tenant ID resolved by handler")

    # ── Event metadata ───────────────────────────────────────────────
    event: EventType
    instance_name: str = Field(..., description="From payload.instance")
    instance_id: str | None = Field(default=None, description="From data.instanceId — log only")
    message_id: str = Field(..., description="From data.key.id; for non-message events, synthetic from event payload")
    timestamp: datetime

    # ── Sender identity (compound — see Descoberta #3) ───────────────
    sender_phone: str | None = Field(default=None, description="E.164 phone if available; None in groups")
    sender_lid_opaque: str | None = Field(default=None, description="15-digit opaque @lid; None for legacy-only senders")
    sender_name: str | None = Field(default=None, description="From data.pushName")
    from_me: bool = Field(default=False)

    # ── Conversation context ─────────────────────────────────────────
    is_group: bool = Field(default=False)
    group_id: str | None = Field(default=None, description="Group JID without @g.us suffix")

    # ── Content ──────────────────────────────────────────────────────
    text: str = Field(default="", description="Extracted text (caption or body); empty for non-text")
    media_type: MediaType | None = Field(default=None)
    media_url: str | None = Field(default=None, description="CDN URL when media")
    media_mimetype: str | None = Field(default=None)
    media_is_ptt: bool = Field(default=False, description="Push-to-talk flag for audio")
    media_duration_seconds: int | None = Field(default=None, description="For audio/video")
    media_has_base64_inline: bool = Field(default=False, description="True if data.message.base64 present")

    # ── Mentions (see Descoberta #4) ─────────────────────────────────
    mentioned_jids: list[str] = Field(
        default_factory=list,
        description="From data.contextInfo.mentionedJid — raw strings (typically '<lid>@lid')",
    )

    # ── Reply (see Descoberta #8) ────────────────────────────────────
    is_reply: bool = Field(default=False)
    quoted_message_id: str | None = Field(default=None, description="From data.contextInfo.stanzaId")

    # ── Reaction (see Descoberta #10) ────────────────────────────────
    reaction_emoji: str | None = Field(default=None, description="From message.reactionMessage.text")
    reaction_target_id: str | None = Field(default=None, description="From message.reactionMessage.key.id")

    # ── Group event (groups.upsert + group-participants.update) ──────
    is_group_event: bool = Field(default=False)
    group_subject: str | None = Field(default=None, description="From groups.upsert data[0].subject")
    group_participants_count: int | None = Field(default=None, description="From groups.upsert data[0].participants length")
    group_event_action: str | None = Field(
        default=None,
        description="From group-participants.update data.action: add|remove|promote|demote",
    )
    group_event_participants: list[str] = Field(
        default_factory=list,
        description="From group-participants.update data.participants — list of @lid strings",
    )
    group_event_author_lid: str | None = Field(
        default=None,
        description="From group-participants.update data.author (without @lid suffix)",
    )

    # ── Derived helper ───────────────────────────────────────────────

    @property
    def sender_key(self) -> str:
        """Stable identity for debounce/idempotency keys.

        Prefers @lid opaque (universal — works in both individual and
        group, since @lid is the same for the same person across
        contexts) and falls back to phone for legacy-only senders.

        Used in Redis keys:
            buf:{tenant_id}:{sender_key}:{ctx}
            tmr:{tenant_id}:{sender_key}:{ctx}
            seen:{tenant_id}:{message_id}  ← message_id, NOT sender_key
        """
        return self.sender_lid_opaque or self.sender_phone or "unknown"
```

**Diff em relação ao epic 001:**

| Campo | epic 001 | pós-refatoração | Razão |
|---|---|---|---|
| `phone` | obrigatório (str) | **removido** | Misleading: em grupo é o `participant` opaco; quem precisar usa `sender_phone` ou `sender_key` |
| `text` | obrigatório | mantido (default `""`) | Mesma semântica |
| `sender_name` | mantido | mantido | OK |
| `message_id` | obrigatório | obrigatório | OK |
| `is_group` | bool | bool | OK |
| `group_id` | str (full JID) | str (sem `@g.us`) | Normalização — id puro |
| `from_me` | bool | bool | OK |
| `mentioned_phones` | list[str] | **renomeado** `mentioned_jids` | Conteúdo são JIDs (`<lid>@lid` ou `<phone>@s.whatsapp.net`), não phones puros |
| `media_type` | str | Literal | Type-safe |
| `media_url` | str | str | OK |
| `timestamp` | datetime | datetime | OK |
| `instance` | str | renomeado `instance_name` | Clareza |
| `is_group_event` | bool | bool | Semântica expandida pra cobrir 2 eventos novos |
| `tenant_id` | — | **NOVO** | Multi-tenant |
| `instance_id` | — | **NOVO** | Audit logging |
| `sender_phone`, `sender_lid_opaque` | — | **NOVO** | Compound identity (Descoberta #3) |
| `media_mimetype`, `media_is_ptt`, `media_duration_seconds`, `media_has_base64_inline` | — | **NOVO** | Cobertura completa de mídia |
| `is_reply`, `quoted_message_id` | — | **NOVO** | Reply (Descoberta #8) |
| `reaction_emoji`, `reaction_target_id` | — | **NOVO** | Reaction (Descoberta #10) |
| `group_subject`, `group_participants_count` | — | **NOVO** | groups.upsert (Descoberta #5) |
| `group_event_action`, `group_event_participants`, `group_event_author_lid` | — | **NOVO** | group-participants.update (Descoberta #6) |
| `event` | — | **NOVO** | Distinguir messages.upsert vs groups.upsert vs group-participants.update |

**Total:** 7 campos do epic 001 mantidos (alguns renomeados), 1 removido, 14 adicionados → 22 campos finais.

#### 8.0.2. Schema canônico do `expected.yaml`

Cada fixture em `tests/fixtures/captured/*.expected.yaml` segue este
schema. **O test loader (T16) ignora qualquer chave não declarada
aqui**, então adicionar chaves novas requer também atualizar o loader.

```yaml
# === Required fields ===
description: <string>                    # 1 line, human-readable
tags: [<string>, ...]                    # MECE classification tags

# === Parser assertions ===
parsed:                                  # required dict; only declared fields are checked
  # All fields below are OPTIONAL — only the ones present are asserted.
  # This allows partial assertions per fixture without forcing all
  # fields to be filled in for every case.

  # Identity
  is_group: <bool>
  is_group_event: <bool>
  from_me: <bool>
  message_id: <string>

  # Sender (compound — see ParsedMessage spec §8.0.1)
  sender_phone: <string|null>
  sender_lid_opaque: <string|null>
  group_id: <string|null>

  # Content
  text: <string|null>
  media_type: <string|null>              # one of: image|video|audio|document|sticker|location|live_location|contact|poll|event|reaction
  media_mimetype: <string|null>
  media_is_ptt: <bool>
  media_duration_seconds: <int>
  media_has_base64_inline: <bool>

  # Mentions
  mentioned_jids: [<string>, ...]        # exact set match (sorted)

  # Reply
  is_reply: <bool>
  quoted_message_id: <string|null>

  # Reaction
  reaction_emoji: <string|null>

  # Group event
  group_subject: <string|null>
  group_participants_count: <int>
  group_event_action: <string|null>
  group_event_participants: [<string>]
  group_event_author_lid: <string|null>

  # Informational only — NOT asserted (loader ignores keys starting with `_`)
  _note: <string>

# === Router assertion ===
route: <string>                          # one of the MessageRoute enum values
route_reason: <string>                   # optional; if present, asserted

# === HTTP response (optional, for end-to-end tests) ===
response:
  status_code: <int>
  body:                                  # partial dict match — only declared keys checked
    status: <string>
    route: <string>

# === Free-form documentation (never asserted) ===
_note: <string>
```

**Loader rules:**

1. **Partial assertion:** missing fields in `parsed:` are NOT asserted.
   You only need to declare what you want to validate. This makes
   adding minimal fixtures cheap.
2. **Underscore-prefix fields are informational:** `_note`, `_*` are
   ignored by the loader. Use them to leave context for human readers.
3. **Lists use sorted equality:** `mentioned_jids: [a, b]` matches
   `[b, a]`.
4. **`route` matches the enum string value** (`support`, `group_save`,
   `group_respond`, `group_event`, `ignore`, `handoff_ativo`).
5. **`route_reason`, when present, must match exactly** — useful for
   distinguishing different `IGNORE` causes (`from_me` vs `reaction`).

#### 8.0.3. Decisão de rota para `reactionMessage`

**Decisão:** rotear `reactionMessage` como `IGNORE` com
`reason="reaction"`. **Não criar nova `MessageRoute`**.

**Razão:**

- Reactions são "ambient signal", não pedidos de ação. Echoar uma
  reação pro usuário é UX estranha.
- O agente LLM pode ler reações no histórico do chat depois pra
  contexto, sem precisar processar elas no fluxo de webhook.
- Adicionar uma rota `REACTION` complica o enum sem benefício
  imediato. Se eventualmente quisermos um fluxo dedicado (ex:
  notificar o agente quando alguém reage à sua mensagem), aí
  promovemos pra rota própria.

**Implementação:** check em `route_message()` **logo após**
`from_me` e **antes** de toda outra lógica:

```python
def route_message(message: ParsedMessage, tenant: Tenant) -> RouteResult:
    # 1. from_me first (FR-005)
    if message.from_me:
        return RouteResult(route=MessageRoute.IGNORE, reason="from_me")

    # 2. Reaction — ambient signal, never echo
    if message.media_type == "reaction":
        return RouteResult(route=MessageRoute.IGNORE, reason="reaction")

    # 3. ... rest unchanged
```

**Validação:** fixtures `ariel_msg_individual_lid_reaction` e
`ariel_msg_individual_lid_reaction_fromme` ambas devem rotear como
`ignore` (a primeira por reaction, a segunda por from_me — qualquer
das duas razões satisfaz).

#### 8.0.4. Fluxo do flush callback per-tenant

§6.11 do plano fala em "lifespan carrega TenantStore" e §9.8 explica
por quê remover o `_flush_echo` global. Aqui está o **fluxo exato**
com código:

**Como funciona hoje** (epic 001, `prosauai/main.py:143-194`):

1. Lifespan cria `_flush_echo` como closure capturando `app.state.settings` (config global).
2. Listener do debounce passa `(phone, group_id, text)` pro callback.
3. Callback usa `settings.evolution_api_url` + `settings.evolution_api_key` + `settings.evolution_instance_name` (todos GLOBAIS).

**Por que quebra com multi-tenant:** as credenciais são per-tenant
agora. O callback precisa **resolver** qual tenant é dono da mensagem
flushada — informação que vinha implícita na chave Redis original
(`buf:{phone}:{ctx}`) e que agora vem explícita (`buf:{tenant_id}:{sender_key}:{ctx}`).

**Como funciona pós-refatoração:**

```python
# prosauai/main.py — pós-refatoração
def _make_flush_callback(app: FastAPI) -> FlushCallback:
    """Build the per-tenant flush callback for the debounce listener.

    The callback signature is (tenant_id, sender_key, group_id, text).
    The tenant_id comes from parsing the expired Redis key (see
    DebounceManager.parse_expired_key — also refactored to extract
    tenant_id as the first segment of the key).

    The closure captures `app` so it can access app.state.tenant_store
    at call time (not at creation time).
    """
    async def _flush_echo(
        tenant_id: str,
        sender_key: str,
        group_id: str | None,
        text: str,
    ) -> None:
        tenant_store: TenantStore = app.state.tenant_store
        tenant = tenant_store.get(tenant_id)
        if tenant is None:
            logger.warning(
                "flush_unknown_tenant",
                tenant_id=tenant_id,
                sender_key=sender_key,
            )
            return

        # Resolve recipient JID for the EvolutionProvider call:
        # - In group: use the group JID (need to add @g.us suffix back)
        # - In individual: use sender_key, which is the @lid or phone
        if group_id is not None:
            recipient = f"{group_id}@g.us"
        else:
            # sender_key is either @lid opaque or a phone
            # EvolutionProvider expects full JID
            if sender_key.isdigit() and len(sender_key) >= 12:
                # Phone format
                recipient = f"{sender_key}@s.whatsapp.net"
            else:
                # @lid opaque
                recipient = f"{sender_key}@lid"

        provider = EvolutionProvider(
            base_url=tenant.evolution_api_url,
            api_key=tenant.evolution_api_key,
        )
        try:
            echo = format_for_whatsapp(text)
            await provider.send_text(tenant.instance_name, recipient, echo)
            logger.info(
                "echo_sent",
                tenant_id=tenant_id,
                instance=tenant.instance_name,
                sender_key=sender_key,
                group_id=group_id,
                text_length=len(text),
            )
        except Exception:
            logger.exception(
                "echo_failed",
                tenant_id=tenant_id,
                sender_key=sender_key,
                group_id=group_id,
            )
        finally:
            await provider.close()

    return _flush_echo
```

**Mudança correlata em `debounce.py`:**

```python
# Old key parsing (epic 001, debounce.py:272-307):
#   tmr:{phone}:{ctx} → (phone, group_id)
#
# New key parsing (post-refactor):
#   tmr:{tenant_id}:{sender_key}:{ctx} → (tenant_id, sender_key, group_id)

@staticmethod
def parse_expired_key(key: str) -> tuple[str, str, str | None] | None:
    """Extract (tenant_id, sender_key, group_id) from an expired timer key."""
    if not key.startswith("tmr:"):
        return None
    rest = key[4:]
    # Split into 3 parts max — sender_key may contain colons in theory
    parts = rest.split(":", 2)
    if len(parts) != 3:
        return None
    tenant_id, sender_key, ctx = parts
    if not tenant_id or not sender_key:
        return None
    group_id = None if ctx == "direct" else ctx
    return tenant_id, sender_key, group_id
```

And the listener loop in `start_listener()` passes the 3 values to
the callback instead of the old 2.

#### 8.0.5. Spec do `test_captured_fixtures.py` (T16)

Implementação canônica do test loader paramétrico. Quando T16 for
codificado, deve seguir esta estrutura.

```python
# tests/integration/test_captured_fixtures.py
"""Parametric integration tests using real (anonymized) Evolution payloads.

This is the source of truth for parser+router correctness. Every
fixture in tests/fixtures/captured/ is loaded as a parametrized test
case. Adding a new case = drop a new (.input.json, .expected.yaml)
pair, no test code changes needed.

See tests/fixtures/captured/README.md for the MECE coverage matrix.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from prosauai.core.formatter import parse_evolution_message
from prosauai.core.router import route_message
from prosauai.core.tenant import Tenant

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "captured"

# ---------------------------------------------------------------------------
# Fixture pair discovery
# ---------------------------------------------------------------------------


def _load_fixture_pairs() -> list[tuple[str, Path, Path]]:
    """Discover all (.input.json, .expected.yaml) pairs in the catalog."""
    pairs: list[tuple[str, Path, Path]] = []
    for input_file in sorted(FIXTURES_DIR.glob("*.input.json")):
        name = input_file.name.removesuffix(".input.json")
        expected_file = FIXTURES_DIR / f"{name}.expected.yaml"
        if not expected_file.exists():
            raise FileNotFoundError(
                f"Fixture {name}.input.json has no corresponding "
                f".expected.yaml — every input must have an expected"
            )
        pairs.append((name, input_file, expected_file))
    if not pairs:
        raise FileNotFoundError(
            f"No fixture pairs found in {FIXTURES_DIR}. "
            f"Run tools/anonymize_captures.py to generate them."
        )
    return pairs


# ---------------------------------------------------------------------------
# Test tenants — anonymized credentials matching the fixtures
# ---------------------------------------------------------------------------

# These match exactly the values produced by tools/anonymize_captures.py
# (PHONE_MAP, LID_MAP, etc.). If you change the anonymizer mappings,
# you MUST update these too.
TEST_TENANTS: dict[str, Tenant] = {
    "Ariel": Tenant(
        id="pace-internal",
        instance_name="Ariel",
        evolution_api_url="https://evolution.test.local",
        evolution_api_key="ANON-PACE-API-KEY-0000-0000-000000000000",
        webhook_secret="anon-secret-pace",
        mention_phone="5511999999100",
        mention_lid_opaque="100000000000100",
        mention_keywords=("@ariel",),
        enabled=True,
    ),
    "ResenhAI": Tenant(
        id="resenha-internal",
        instance_name="ResenhAI",
        evolution_api_url="https://evolution.test.local",
        evolution_api_key="ANON-RESENHA-API-KEY-0000-0000-000000000000",
        webhook_secret="anon-secret-resenha",
        mention_phone="5511999999200",
        mention_lid_opaque="100000000000200",
        mention_keywords=("@resenhai", "@resenha"),
        enabled=True,
    ),
}

# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def _assert_parsed(name: str, msg: Any, expected_parsed: dict[str, Any]) -> None:
    """Assert each declared field in expected_parsed matches the parsed message.

    Rules:
    - Underscore-prefixed keys are informational (not asserted)
    - Missing fields are NOT asserted (partial assertion allowed)
    - Lists are compared as sorted (set-like) equality
    """
    for field, expected_value in expected_parsed.items():
        if field.startswith("_"):
            continue
        actual = getattr(msg, field, "<MISSING ATTRIBUTE>")
        if actual == "<MISSING ATTRIBUTE>":
            pytest.fail(
                f"{name}: ParsedMessage has no attribute '{field}'. "
                f"Either fix the fixture's expected.yaml or add this "
                f"field to the ParsedMessage schema."
            )
        if isinstance(expected_value, list) and isinstance(actual, list):
            assert sorted(actual) == sorted(expected_value), (
                f"{name}: field '{field}' list mismatch — "
                f"expected (sorted) {sorted(expected_value)}, "
                f"got (sorted) {sorted(actual)}"
            )
        else:
            assert actual == expected_value, (
                f"{name}: field '{field}' expected {expected_value!r}, "
                f"got {actual!r}"
            )


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,input_path,expected_path",
    _load_fixture_pairs(),
    ids=[p[0] for p in _load_fixture_pairs()],
)
def test_captured_fixture(
    name: str,
    input_path: Path,
    expected_path: Path,
) -> None:
    """Validate parser + router output against a real anonymized payload."""
    payload = json.loads(input_path.read_text())
    expected = yaml.safe_load(expected_path.read_text())

    instance = payload.get("instance", "")
    tenant = TEST_TENANTS.get(instance)
    assert tenant is not None, (
        f"{name}: no test tenant configured for instance {instance!r}. "
        f"Add it to TEST_TENANTS in this file."
    )

    # ── Parse ────────────────────────────────────────────────────────
    msg = parse_evolution_message(payload)
    # The handler normally sets tenant_id; mimic that here.
    msg = msg.model_copy(update={"tenant_id": tenant.id})

    parsed_expected = expected.get("parsed") or {}
    _assert_parsed(name, msg, parsed_expected)

    # ── Route ────────────────────────────────────────────────────────
    if "route" in expected:
        result = route_message(msg, tenant)
        assert result.route.value == expected["route"], (
            f"{name}: route expected {expected['route']!r}, "
            f"got {result.route.value!r}"
        )
        if "route_reason" in expected:
            assert result.reason == expected["route_reason"], (
                f"{name}: route_reason expected {expected['route_reason']!r}, "
                f"got {result.reason!r}"
            )
```

**Notas de implementação:**

- Usa **PyYAML** como dev dependency (`pyyaml>=6.0` em `pyproject.toml`
  `[project.optional-dependencies] dev`).
- O `_load_fixture_pairs()` é chamado **2 vezes** no decorator
  parametrize — uma vez pra os parâmetros, outra pra os IDs. Aceitável
  porque são 26 arquivos, leitura é trivial. Se ficar lento, cachear.
- O `model_copy(update={"tenant_id": ...})` simula o que o webhook
  handler faz (o parser por si só não conhece o tenant).
- Erros de assertiva incluem o `name` da fixture pra debugging
  imediato.

#### 8.0.6. Glossário expandido (substitui §14.2)

| Termo | Definição |
|---|---|
| **Tenant** | Cliente isolado lógico no ProsauAI. Cada tenant = 1 instância Evolution + 1 secret + 1 conjunto de regras de mention. Identificado por `id` (lowercase, kebab-case). |
| **Instance name** | Identificador da instância na Evolution API (ex: `Ariel`). Usado como chave pública para identificar o tenant no path do webhook. |
| **Webhook secret** | Secret compartilhado entre Evolution (que envia no header `X-Webhook-Secret`) e ProsauAI (que valida). Per-tenant. Não é HMAC, é shared static secret. |
| **Idempotência** | Garantia de que processar o mesmo `(tenant_id, message_id)` duas vezes produz o mesmo resultado que processar uma vez. Implementada com Redis SETNX, TTL 24h. |
| **Debounce** | Agrupar mensagens rápidas do mesmo `(tenant_id, sender_key, group_id)` em um buffer antes de processar (feature do epic 001). |
| **Retry storm** | Situação onde Evolution retenta um webhook múltiplas vezes em sequência por erro transiente. Mitigada por idempotência. |
| **Fase 0 / 1 / 2 / 3** | Entregas faseadas: 0=especificações canônicas, 1=fundação multi-tenant, 2=abrir para externos, 3=operação em produção. |
| **`@lid`** (Linked-ID) | Novo formato de JID do WhatsApp introduzido em 2024+. Usuários são representados por um ID opaco de 15 dígitos seguido de `@lid` em vez de `<phone>@s.whatsapp.net`. Mesma pessoa sempre tem o mesmo `@lid` (estável). |
| **`@s.whatsapp.net`** (legacy JID) | Formato antigo do JID, ainda usado em alguns chats. Contém o phone number direto (`<phone>@s.whatsapp.net`). |
| **`@g.us`** (group JID) | Formato do JID de grupos. `<group_id_18_digits>@g.us`. |
| **`senderPn`** (sender phone number) | Campo em `data.key` que carrega o phone real do sender quando `remoteJid` está em `@lid`. É o "espelho" do `@lid` opaco. |
| **`senderLid`** | Campo em `data.key` que carrega o `@lid` opaco quando `remoteJid` está em formato legacy `@s.whatsapp.net`. Espelho oposto do `senderPn`. |
| **`participant`** | Campo em `data.key` (apenas em mensagens de grupo) que carrega o JID do sender real dentro do grupo. Pode ser `@lid` opaco ou (raramente) `<phone>@s.whatsapp.net`. **Em grupo NÃO há `senderPn`** — o phone real do participante não está disponível inline. |
| **`mention_lid_opaque`** | Campo per-tenant em `tenants.yaml`. Armazena o `@lid` opaco (15 dígitos, sem sufixo) do bot daquele tenant. Usado pra detectar quando o bot é mencionado em grupo via `@`-mention real do WhatsApp (que carrega o `mentionedJid` como `<lid>@lid`). |
| **`mentioned_jids`** | Campo de `ParsedMessage` (renomeado de `mentioned_phones` do epic 001). Lista de strings com os JIDs mencionados na mensagem, exatamente como vieram em `data.contextInfo.mentionedJid`. Tipicamente `<lid>@lid`. |
| **`sender_lid_opaque`** | Campo de `ParsedMessage`. Armazena o `@lid` opaco do sender (15 dígitos, sem sufixo `@lid`). `None` se a mensagem é legacy-only. |
| **`sender_phone`** | Campo de `ParsedMessage`. Armazena o phone E.164 do sender. `None` em mensagens de grupo onde o phone real não está disponível. |
| **`sender_key`** | Property derivada de `ParsedMessage`. Retorna `sender_lid_opaque or sender_phone or "unknown"`. Identidade canônica do sender pra debounce/idempotency keys. |
| **`quotedMessage`** | Sub-objeto em `data.contextInfo` quando a mensagem é uma reply. Contém a mensagem original inteira (qualquer tipo). |
| **`stanzaId`** | Campo em `data.contextInfo` (em replies) que carrega o `message_id` da mensagem original sendo respondida. |
| **`instanceId`** | UUID da instância Evolution, em `data.instanceId`. Estável, mais robusto que `instance_name`. Logamos pra debug; não usamos como chave de lookup. |
| **`webhookBase64`** | Flag de configuração do webhook na Evolution. Quando `true`, mídia binária é incluída inline no payload em `data.message.base64`. Quando `false`, só vem `imageMessage.url` e o receiver tem que baixar. Usamos `true` em dev pra ter shape completo nas fixtures. |
| **`fromMe`** | Flag em `data.key`. `true` quando a mensagem foi enviada pelo próprio bot (o WhatsApp do tenant). Sempre roteada como `IGNORE` com `reason=from_me` pra prevenir loop de echo. |
| **fixture pair** | Padrão de teste: `<name>.input.json` (payload anonimizado) + `<name>.expected.yaml` (assertions hand-written). Único teste paramétrico carrega todos os pares. |
| **golden file** | Termo equivalente a "fixture pair". Um arquivo `.expected.*` que serve como "verdade absoluta" pra comparação em testes. |
| **anonimização determinística** | Cada token real (phone, lid, apikey, etc.) tem um substituto fixo. Re-rodar o anonymizer produz o mesmo output. Implementado em `tools/anonymize_captures.py` via `PHONE_MAP`, `LID_MAP`, etc. |
| **MECE** | Mutually Exclusive, Collectively Exhaustive. Princípio de classificação onde cada item cai em **exatamente uma** categoria, e todas as categorias juntas cobrem **todos** os casos possíveis. Usado pra organizar a matriz de cobertura das fixtures. |
| **`messages.upsert`** | Evento principal da Evolution: chega quando uma mensagem nova entra na instância. `data` é dict com `key`, `message`, `messageType`, etc. |
| **`groups.upsert`** | Evento da Evolution: chega quando metadata do grupo muda (nome, desc, participants). `data` é uma **lista** de objetos group. **Nada a ver com `groups.update` (que NÃO existe).** |
| **`group-participants.update`** | Evento da Evolution: chega especificamente quando alguém é adicionado/removido/promovido/demovido no grupo. `data` é dict com `{id, author, action, participants[]}` — **sem `key`**. |
| **MessageRoute** | Enum em `prosauai/core/router.py`. Valores: `SUPPORT`, `GROUP_RESPOND`, `GROUP_SAVE_ONLY`, `GROUP_EVENT`, `HANDOFF_ATIVO`, `IGNORE`. |

#### 8.0.7. Naming consistency

Padronização de termos pra evitar confusão durante a implementação:

| ✅ Use | ❌ Evite | Onde |
|---|---|---|
| `mention_lid_opaque` | `bot_lid`, `tenant_lid`, `lid_id` | Tenant config (`tenants.yaml`, `Tenant` dataclass) |
| `sender_lid_opaque` | `lid_opaque`, `lid`, `linked_id` | `ParsedMessage` |
| `sender_phone` | `phone`, `phone_number`, `e164` | `ParsedMessage` |
| `sender_key` | `id`, `identity`, `sender_id` | `ParsedMessage` property + Redis keys |
| `mentioned_jids` | `mentioned_phones`, `mentions`, `mention_list` | `ParsedMessage` (renomeado do epic 001) |
| `tenant_id` | `tenant`, `client_id` | em logs, Redis keys, function args |
| `instance_name` | `instance`, `inbox` | nas APIs e config |
| `instance_id` | `instance_uuid`, `evo_id` | logs only |
| `quoted_message_id` | `reply_to`, `parent_id` | `ParsedMessage` |
| `media_type` | `attachment_type`, `content_type` | `ParsedMessage` |
| `media_is_ptt` | `is_voice`, `is_audio_message` | `ParsedMessage` |
| `group_id` | `group_jid`, `chat_id` (when group) | sem sufixo `@g.us` |

**Regra de ouro:** se um nome descreve **o que é** (`sender_lid_opaque`)
em vez de **o que faz** (`bot_lid`), prefira o descritivo. Os nomes
ficam mais longos mas a ambiguidade desaparece.

---

### Fase 1 — Fundação multi-tenant (esta implementação)

**Escopo:** código já é multi-tenant, operando com 1 tenant. Deploy em dev (Tailscale) e prod single-tenant interno (VPS).

#### 8.1.1. Ordem de implementação e PR única

Sugestão: **1 PR grande** em vez de vários pequenos, porque a refatoração toca várias camadas interdependentes. Dividir em PRs pequenos criaria estados intermediários quebrados.

| # | Tarefa | Arquivos | Testes |
|---|---|---|---|
| T1 | Criar `Tenant` dataclass | `prosauai/core/tenant.py` (novo) | `tests/unit/test_tenant.py` (novo) |
| T2 | Criar `TenantStore` com loader YAML | `prosauai/core/tenant_store.py` (novo), `pyproject.toml` (add `pyyaml`) | `tests/unit/test_tenant_store.py` (novo) |
| T3 | Criar `tenants.example.yaml` + `tenants.yaml` (gitignored) | root | — |
| T4 | Refatorar `Settings` — remover campos tenant-specific | `prosauai/config.py` | `tests/unit/test_config.py` (se existir) |
| T5 | Criar `check_and_mark_seen()` helper de idempotência | `prosauai/core/idempotency.py` (novo) | `tests/unit/test_idempotency.py` (novo) |
| T6 | Reescrever `dependencies.py` — remover HMAC, adicionar `resolve_tenant_and_authenticate` | `prosauai/api/dependencies.py` | `tests/unit/test_auth.py` (renomear de `test_hmac.py`) |
| **T6b** | **Reescrever `_MEDIA_TYPES` e `_KNOWN_MESSAGE_TYPES`** com nomes reais (`imageMessage`, `videoMessage`, `audioMessage`, `documentMessage`, `stickerMessage`, `locationMessage`, `liveLocationMessage`, `contactMessage`, `reactionMessage`, `pollCreationMessageV3`, `eventMessage`, `extendedTextMessage`, `conversation`). **D1, D2** | `prosauai/core/formatter.py` | Fixtures `tests/fixtures/captured/*_image*`, `*_video*`, `*_audio_ptt*`, etc. |
| **T6c** | **Implementar resolução de sender multi-formato** em `parse_evolution_message()`: para `@lid+senderPn` usar `key.senderPn`; para `@s.whatsapp.net+senderLid` usar `remoteJid`; para grupo (`@g.us`) usar `key.participant`. Expor `sender_phone` (opcional) **e** `sender_lid_opaque` no `ParsedMessage`. **D6, D8** | `prosauai/core/formatter.py` + `ParsedMessage` schema | Fixtures individual lid, legacy, group |
| **T6d** | **Adicionar branch para `event=groups.upsert`** no parser — `data` é **lista**, sem `key`, com `participants[]` e pares `*Owner`/`*OwnerJid`. Extrair `group_id`, `subject`, `participants_count`. **D4, D5** | `prosauai/core/formatter.py` | Fixtures `resenhai_groups_upsert_*`, `ariel_groups_upsert_after_add_3p` |
| **T6e** | **Adicionar branch para `event=group-participants.update`** — `data` é dict sem `key`, com `{id, action, author, participants[]}`. Extrair ação + lista de @lid afetados. **D4, D7** | `prosauai/core/formatter.py` | Fixture `resenhai_group_participants_update_add` |
| **T6f** | **Corrigir extração de `mentionedJid`** — ler de `data.contextInfo.mentionedJid` (top-level), não de `message.extendedTextMessage.contextInfo`. Funciona pra `conversation` e `extendedTextMessage`. **D3** | `prosauai/core/formatter.py` | Fixture `resenhai_msg_group_text_mention_jid` |
| **T6g** | **Extrair `quotedMessage` (reply)** de `data.contextInfo.quotedMessage`. Adicionar `is_reply: bool` e `quoted_message_id: str \| None` ao `ParsedMessage`. | `prosauai/core/formatter.py` + `ParsedMessage` | Fixture `ariel_msg_individual_lid_text_reply` |
| **T6h** | **Adicionar `mention_lid_opaque`** ao `Tenant` dataclass e ao schema de `tenants.yaml`. Atualizar `_is_bot_mentioned()` pra comparar `mentioned_jids` contra `tenant.mention_lid_opaque` primeiro, depois fallback pra `mention_phone` (legacy paths) e `mention_keywords`. **D10, D11** | `prosauai/core/tenant.py`, `prosauai/core/router.py`, `config/tenants.yaml`, `config/tenants.example.yaml` | Fixture com mention + testes do router |
| **T6i** | **Ignorar silenciosamente** campos irrelevantes: `messageContextInfo`, `chatwoot*`, `deviceListMetadata`, `status`, `source`, `instanceId` (logar como metadado), `data.message.base64` (existe mas parser não precisa) | `prosauai/core/formatter.py` | Fixtures existentes (garantir que nada quebra) |
| **T6j** | **Decidir rota pra `reactionMessage`** — sugestão: nova rota `REACTION` ou `IGNORE` com reason=`reaction`. Documentar a decisão no router. Extrair `reaction_emoji` e `reaction_target_id` no `ParsedMessage` para referência futura. | `prosauai/core/router.py`, `ParsedMessage` | Fixtures `*_reaction*` |
| T7 | Refatorar `route_message()` para receber `Tenant` em vez de `Settings` | `prosauai/core/router.py` | `tests/unit/test_router.py` |
| T8 | Refatorar `webhooks.py` — integra resolver tenant + idempotência + passa tenant adiante | `prosauai/api/webhooks.py` | `tests/integration/test_webhook.py` |
| T9 | Refatorar `debounce.py` — prefixar keys com `tenant_id` | `prosauai/core/debounce.py` | `tests/unit/test_debounce.py` |
| T10 | Refatorar `main.py` lifespan — carregar TenantStore | `prosauai/main.py` | — |
| T11 | Refatorar `_flush_echo` — usa `Tenant` em vez de `Settings` para credenciais | `prosauai/main.py` | testes integração debounce |
| T12 | Atualizar `docker-compose.yml` — remover `ports`, adicionar volume do `tenants.yaml` | `docker-compose.yml` | — |
| T13 | Criar `docker-compose.override.yml` (gitignored) para dev + exemplo template | `docker-compose.override.example.yml` (novo) | — |
| T14 | Atualizar `.env` e criar `.env.example` | `.env.example` (novo), `.gitignore` | — |
| T15 | Atualizar `README.md` — como rodar dev (Tailscale), como rodar prod (Docker network), como configurar novo tenant (workflow completo de discovery do `mention_lid_opaque`), como adicionar nova fixture | `README.md` | — |
| **T16** | **Criar `test_captured_fixtures.py`** — teste paramétrico com `pytest.mark.parametrize` carregando todos os pares `tests/fixtures/captured/*.input.json` + `*.expected.yaml`. Usa `yaml.safe_load` (pode adicionar `pyyaml` como dev-dep, ou escrever loader custom simples). Pra cada fixture, chama `parse_evolution_message(input)` → compara cada campo em `expected.parsed` via loop; depois chama `route_message(msg, tenant)` → compara com `expected.route`. | `tests/integration/test_captured_fixtures.py` (novo), `tests/conftest.py` (helper), `pyproject.toml` (add pyyaml dev dep se preciso) | Valida contra todos os 26 pares |
| **T17** | **Deletar fixture sintética** `tests/fixtures/evolution_payloads.json` + todos os testes que dependem dela (depois que T6b-T6j + T16 estiverem passando contra as fixtures reais). | `tests/fixtures/evolution_payloads.json` (deletar) | — |

#### 8.1.2. Impacto nos testes existentes

| Teste | Ação |
|---|---|
| `tests/unit/test_hmac.py` | **Deletar** ou reescrever como `test_auth.py` (validação de X-Webhook-Secret). |
| `tests/unit/test_router.py` | Atualizar fixtures: criar `Tenant` em vez de `Settings`. Adicionar cenários de mention via `mention_lid_opaque` (não só `mention_phone`). Trocar `mentioned_phones` por `mentioned_jids` no schema. |
| `tests/unit/test_debounce.py` | Atualizar assertivas de keys: agora são `buf:{tenant_id}:{sender_key}:{ctx}` onde `sender_key` é `sender_lid_opaque or sender_phone`. |
| `tests/unit/test_formatter.py` | **Reescrita substancial** — os asserts atuais batem com a fixture sintética `evolution_payloads.json` que **não reflete a realidade**. A nova suíte vai ser **paramétrica** carregando os 26 pares em `tests/fixtures/captured/`. Ver T16. |
| **`tests/fixtures/evolution_payloads.json`** | **Deletar** — substituída por `tests/fixtures/captured/`. |
| `tests/unit/test_evolution_provider.py` | Intocado — provider recebe URL + key, não conhece tenant. |
| `tests/integration/test_webhook.py` | Reescrever substancialmente: mock `TenantStore`, adicionar testes de 404 (instance desconhecida), 401 (secret errado), duplicate (idempotência), cross-tenant isolation. |
| `tests/integration/test_health.py` | Pequeno ajuste: health pode reportar `tenants_loaded: N`. |
| **`tests/integration/test_captured_fixtures.py`** | **Arquivo novo** (T16). Teste paramétrico que carrega todos os pares `tests/fixtures/captured/*.input.json` + `*.expected.yaml`, parseia o input, compara contra o expected. Single source of truth pra regressão. |
| `tests/conftest.py` | Adicionar fixtures `sample_tenant`, `tenant_store`, `redis_idempotency_store`. Remover fixtures de `webhook_secret`. Adicionar helper `load_captured_fixture_pair(name)`. |

#### 8.1.3. Critérios de aceite Fase 1

**Auth + infra:**

- [ ] `docker compose up` sobe sem erro com `.env` + `tenants.yaml` mínimos.
- [ ] Request sem header `X-Webhook-Secret` → 401.
- [ ] Request com `instance_name` desconhecido → 404.
- [ ] Request com secret errado → 401.
- [ ] Porta 8050 **não** exposta em `0.0.0.0` em produção (apenas Docker network ou Tailscale em dev).

**Fixture-driven parser correctness (crítico — os testes agora usam payloads reais):**

- [ ] **Todas as 26 fixtures** em `tests/fixtures/captured/*.input.json` parseadas sem exceção.
- [ ] Para cada fixture, os campos declarados em `.expected.yaml` `parsed:` batem com o `ParsedMessage` gerado (comparação paramétrica em `test_captured_fixtures.py`).
- [ ] Para cada fixture, a rota declarada em `.expected.yaml` `route:` bate com `route_message()`.
- [ ] **16 de 16 mídias** reconhecidas por `messageType` real (`imageMessage`, `videoMessage`, `audioMessage`, etc.) — validado pelas fixtures `*_image*`, `*_video*`, `*_audio_ptt*`, etc.
- [ ] **`mentionedJid` em `data.contextInfo`** é lido corretamente — validado pela fixture `resenhai_msg_group_text_mention_jid`: router classifica como `group_respond`.
- [ ] **`@lid` + `senderPn`**: fixture `ariel_msg_individual_lid_text_simple` extrai `sender_phone=5521999999001`, `sender_lid_opaque=100000000000001`.
- [ ] **`@s.whatsapp.net` + `senderLid`**: fixture `ariel_msg_individual_legacy_text` extrai `sender_phone` do `remoteJid` e `sender_lid_opaque` do `senderLid`.
- [ ] **Grupo com `participant=@lid`**: fixture `resenhai_msg_group_text_no_mention` extrai `group_id`, `sender_lid_opaque`, `sender_phone=None`, rota `group_save`.
- [ ] **`groups.upsert` com `data` como lista**: fixtures `resenhai_groups_upsert_initial_2p`, `ariel_groups_upsert_after_add_3p` parsed sem crash, rota `group_event`.
- [ ] **`group-participants.update` sem `key`**: fixture `resenhai_group_participants_update_add` parsed sem crash, `action=add`, rota `group_event`.
- [ ] **Reply com `quotedMessage`**: fixture `ariel_msg_individual_lid_text_reply` extrai `is_reply=True`, `quoted_message_id`.
- [ ] **`fromMe: true` ignorado**: todas as 5 fixtures `*_fromme` roteadas como `ignore` com reason `from_me`.
- [ ] **Reaction**: fixture `ariel_msg_individual_lid_reaction` extrai `reaction_emoji="❤️"` e é roteada conforme decisão da T6j (não echo).

**Idempotência + debounce:**

- [ ] Envio do **mesmo** `message_id` duas vezes (mesmo tenant) → segundo request retorna `status=duplicate`, sem processar.
- [ ] Envio do mesmo `message_id` em **tenants diferentes** → ambos processam (chave Redis prefixada por tenant).
- [ ] Debounce key format: `buf:{tenant_id}:{sender_key}:{ctx}` onde `sender_key = sender_lid_opaque or sender_phone`.

**Cross-tenant validation:**

- [ ] Com 2 tenants configurados (Ariel + ResenhAI), uma mensagem pro Ariel **não** é recebida pelo ResenhAI (isolamento lógico).
- [ ] Um `groups.upsert` que dispara webhooks pros 2 tenants é processado independentemente em cada um (fixtures `resenhai_groups_upsert_*` e `ariel_groups_upsert_after_add_3p` demonstram).

**End-to-end real:**

- [ ] Evolution real envia webhook para `http://<host>:8050/webhook/whatsapp/Ariel` com header `X-Webhook-Secret` correto → processa com sucesso, envia echo.
- [ ] Mesma validação para ResenhAI.

**Documentação:**

- [ ] README atualizado com fluxo real (não mais o exemplo HMAC).
- [ ] README documenta onboarding de um novo tenant (copiar template, editar YAML, gerar secret, configurar webhook na Evolution).
- [ ] `tests/fixtures/captured/README.md` mantido como source-of-truth da matriz MECE.

**Todos:**

- [ ] Todos os testes unitários passam.
- [ ] Todos os testes de integração passam.
- [ ] Todos os testes `test_captured_fixtures.py` passam (26 casos paramétricos).

### Fase 2 — Abertura para clientes externos

**Quando:** quando existir um primeiro cliente real disposto a pagar/testar.

**Escopo:**

1. Adicionar Caddy ao `docker-compose.prod.yml`.
2. Configurar DNS: `api.prosauai.com` → IP da VPS.
3. TLS automático via Let's Encrypt (Caddy faz sozinho).
4. Implementar admin API: `POST/GET/DELETE /admin/tenants` com auth via token master.
5. Rate limiting por tenant via `slowapi` ou middleware custom.
6. Métricas básicas por tenant (requests/s, errors, debounces flushed).
7. Onboarding doc para clientes: "como configurar webhook na sua Evolution".

**Impacto no código:** pequeno. Adiciona `prosauai/api/admin.py` e um middleware de rate limit. Nada no domínio muda.

### Fase 3 — Operação em produção

**Escopo:**

1. Migrar `TenantStore` de YAML para Postgres (quando ≥ 5 tenants).
2. UI admin (opcional — provavelmente só API + scripts).
3. Billing/usage tracking (contagem de mensagens processadas por tenant).
4. Alertas por tenant (Prometheus/Grafana).
5. Auditoria (log imutável de operações administrativas).
6. Backup/restore do estado dos tenants.
7. Circuit breaker por tenant (se a Evolution de um tenant está down, não sobrecarregar retries).

**Trigger para iniciar:** dor operacional real. Não antes.

---

## 9. Decisões de Design Explícitas

### 9.1. Por que YAML e não Postgres para tenants?

- Tenant store raramente muda (minutos/horas de latência ao editar não é problema).
- Até ~20 tenants, YAML em volume Docker + hot reload é suficiente.
- Postgres adiciona: migrations, backup, ORM, testes mais complexos — complexidade desproporcional no início.
- Migração para Postgres na Fase 3 é trivial: `TenantStore.load_from_file()` vira `TenantStore.load_from_db()`. Interface do `TenantStore` não muda.

### 9.2. Por que interpolar `${VAR}` em YAML?

Secrets (API keys, webhook secrets) **não** podem ser versionados. YAML interpola env vars no load:

```yaml
evolution_api_key: ${PACE_EVOLUTION_API_KEY}
```

Ao carregar, `TenantStore` resolve `${PACE_EVOLUTION_API_KEY}` a partir do ambiente. YAML pode ser commitado (como exemplo), env tem os segredos reais.

### 9.3. Por que header secret e não JWT?

Evolution oferece `jwt_key` nativamente (v2.2+). Avaliado e rejeitado porque:

- JWT assina payload fixo, **não o body** — atacante com 1 JWT pode mutar body por 10min.
- UX de onboarding pior (cliente precisa entender o que é `jwt_key`).
- Segurança efetiva **igual** a header estático + idempotência (ambos dependem de secret estático + dedupe).

Header estático é mais simples e não perde nada.

### 9.4. Por que idempotência por `message_id` e não por hash do body?

- `message_id` é único por mensagem na Evolution (garantido pelo Baileys/WhatsApp).
- Hash do body varia se qualquer campo auxiliar mudar (timestamp de retry, por exemplo), furando a dedupe.
- Prefixo por tenant (`seen:{tenant_id}:{message_id}`) evita colisão entre tenants.

### 9.5. Por que 24h de TTL na idempotência?

- Retries da Evolution: até 10 tentativas com backoff exponencial → janela máxima ~algumas horas.
- 24h é folga confortável, não cria pressão no Redis.
- Memory cost: ~30 bytes por mensagem × mensagens/dia × N tenants. Mesmo com 10k msg/dia/tenant e 100 tenants = 30MB. Irrelevante.

### 9.6. Por que `docker-compose.override.yml` (dev) em vez de flag de build?

- Docker Compose aplica `override.yml` automaticamente se presente. Zero fricção.
- Arquivo é gitignored, então cada dev tem o seu (Tailscale IP diferente por máquina).
- `docker-compose.override.example.yml` commitado serve de template.

### 9.7. Por que refatorar `router.py` para receber `Tenant` em vez de `Settings`?

Hoje, `route_message()` precisa de `mention_phone` e `mention_keywords_list`. Ambos são **per-tenant**. Passar `Settings` globais deixaria esses campos misturados com config global, quebrando o isolamento.

### 9.8. Por que remover `_flush_echo` do `main.py`?

Hoje o closure captura `app.state.settings` globais. No novo modelo, precisa capturar o `tenant` específico da conversa que está sendo flushada. A keys de debounce já incluem `tenant_id`, então o callback pode resolver: `tenant_id → tenant → credenciais`.

---

## 10. Riscos e Mitigações

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | Refatoração grande introduz regressões no router/debounce | Média | Alto | Testes unitários do epic 001 continuam rodando; cobertura em `test_webhook.py` expandida. |
| R2 | `tenants.yaml` com sintaxe inválida derruba o app no startup | Média | Médio | Validação no load + log claro do erro + fail fast (melhor quebrar no startup que silenciosamente processar sem tenants). |
| R3 | Dev esquece de criar `docker-compose.override.yml` e expõe porta | Baixa | Alto | `.gitignore` inclui override; README instrui; `docker-compose.yml` base **nunca** tem `ports`. |
| R4 | Evolution muda protocolo e quebra tudo | Baixa | Alto | Fora de escopo; mitigado por ter fixtures reais em `tests/fixtures/evolution_payloads.json`. |
| R5 | Vazamento do `PACE_WEBHOOK_SECRET` | Baixa | Médio | Rotação: trocar no `.env` + atualizar webhook na Evolution. Se vazar, atacante ainda precisa estar na mesma rede (Fase 1) — pouco risco. |
| R6 | Clock skew entre Evolution e ProsauAI afeta idempotência | Baixa | Baixo | Não usamos timestamp como parte da key — só `message_id`. Imune. |
| R7 | Redis cai → idempotência falha open (permite duplicates) | Média | Médio | Aceitável. Debounce já trata Redis-down como fallback imediato. Echo duplicado é chato mas não catastrófico. Logar warning. |
| R8 | Multi-tenant fica pela metade (ex: debounce isolado mas logs não) | Média | Médio | Checklist de isolamento na Fase 1 (seção 6): **toda** key Redis prefixada, **todo** log inclui `tenant_id`. |

---

## 11. Métricas de Sucesso

Não adiciona telemetria formal nesta fase (Prometheus vem na Fase 3), mas logs estruturados precisam **obrigatoriamente** incluir:

- `tenant_id` em todo log de webhook processado
- `instance_id` (UUID da Evolution instance — logar como metadado pra debug cross-reference com o Manager)
- `message_id` em todo log de idempotência
- `sender_key` (= `sender_lid_opaque or sender_phone`) para privacy — **não logar o phone bruto**
- `route` classificada
- `status` (processed / duplicate / ignored)
- `event` (`messages.upsert` / `groups.upsert` / `group-participants.update`)

Isso permite `grep` e agregação ad-hoc no journalctl/`docker logs` sem ferramentas extras.

**Ground truth dos testes:** o critério objetivo de "o parser tá certo"
não é mais uma fixture sintética nossa — é o comportamento observado em
payloads reais. Qualquer regressão num dos 26 casos de
`tests/fixtures/captured/` é falha. Esse é o contrato.

---

## 12. Plano de Rollout

### 12.1. Dev → Prod Fase 1

**Pré-condições (já atendidas em 2026-04-10):**

- Hipótese `X-Webhook-Secret` validada empiricamente.
- `.env` e `config/tenants.yaml` criados com valores reais.
- Webhook da Evolution já apontando para Tailscale IP com header secret configurado.
- Aguardando apenas o código ser implementado para que `docker compose up` funcione.

**Sequência:**

1. **Branch:** criar `feat/multi-tenant-auth` a partir de `develop`.
2. **Desenvolvimento:** tarefas T1-T16 em sequência. Commits atômicos por tarefa.
3. **PR:** único PR grande com título `feat: multi-tenant foundation + remove impossible HMAC auth`. Descrição linka este documento.
4. **Review:** auto-review + rodar testes locais. Sem outros reviewers no momento (Gabriel é solo).
5. **Validação dev (Tailscale):**
   - `docker compose up` na máquina dev (`ntb-25-0543`, WSL).
   - Criar `docker-compose.override.yml` com `ports: "100.77.80.33:8050:8050"` (ou usar o template).
   - Enviar mensagem real pelo WhatsApp → verificar logs + echo de volta.
6. **Merge:** `develop` → testes passam → merge em `main` quando Fase 1 estiver validada localmente.
7. **Deploy VPS (quando VPS provisionada):**
   - Criar VPS com Docker + Docker Compose.
   - Clonar repo.
   - Criar `.env` com secrets reais (copiar do `.env.example`).
   - Criar `config/tenants.yaml` baseado no `config/tenants.example.yaml`.
   - **Não** criar `docker-compose.override.yml` em prod.
   - Criar Docker network `pace-net` manualmente (`docker network create pace-net`).
   - Subir Evolution na mesma network.
   - Subir ProsauAI: `docker compose up -d`.
   - Reconfigurar webhook na Evolution apontando para `http://api:8050/webhook/whatsapp/Ariel` (DNS interno Docker).
   - Enviar mensagem de teste no WhatsApp → verificar echo + logs.
8. **Monitoramento inicial:** `docker compose logs -f` por 24h olhando por erros.

### 12.2. Rollback plan

Se algo quebrar após merge em `main`:

- `git revert <merge-commit>` em `main`.
- Redeploy na VPS.
- Código volta para o estado do epic 001 (com HMAC quebrado, mas estável para fixtures de teste).

Backup: a branch `epic/prosauai/001-channel-pipeline` continua existindo e é o "save point" garantido.

---

## 13. Checklist de Pré-Implementação

Status atualizado em 2026-04-10 antes de iniciar a branch `feat/multi-tenant-auth`:

- [x] Gabriel aprova a arquitetura (Alternativa D).
- [x] Tenant 1 definido: `pace-internal` / instância `Ariel`.
- [x] Tenant 2 definido: `resenha-internal` / instância `ResenhAI`.
- [x] `mention_phone` Ariel: `5511910375690` (via campo `sender`).
- [x] `mention_phone` ResenhAI: `5511970972463` (via `participants[].jid`).
- [x] **`mention_lid_opaque` Ariel:** `103487874539537` (via `participants[].id` em groups.upsert capture #035 quando o bot foi adicionado ao grupo).
- [x] **`mention_lid_opaque` ResenhAI:** `146102623948863` (via `mentionedJid` nas captures #025 e #038).
- [x] Secret Ariel: `d9b945d1...b75` (armazenado em `.env`).
- [x] Secret ResenhAI: `1f15920e...8cb7` (armazenado em `.env`).
- [x] Hipótese `X-Webhook-Secret` validada empiricamente via webhook.site (§4.5).
- [x] Webhooks Ariel + ResenhAI revertidos para serviço real (`http://100.77.80.33:8050/webhook/whatsapp/{instance}`) após fim da captura.
- [x] `.env` final criado + `.env.example` template commitável.
- [x] `config/tenants.yaml` final criado com 2 tenants (incluindo `mention_lid_opaque`) + `config/tenants.example.yaml` template commitável e instruído a discover.
- [x] `.gitignore` atualizado (exclui `config/tenants.yaml`, `.env`, `docker-compose.override.yml`, `tools/captures/*.json`).
- [x] Capture tool (`tools/payload_capture.py`) implementado, multi-secret, com filename por instância, tratando tanto `messages.upsert` (dict) quanto `groups.upsert` (list) quanto `group-participants.update`.
- [x] **36 payloads reais capturados** (26 Ariel + 10 ResenhAI, cobrindo 3 eventos × 2 tenants × 2 contextos × 4 formatos sender × 13 content types).
- [x] **Catálogo de fixtures gerado** em `tests/fixtures/captured/`: 26 pares `.input.json`+`.expected.yaml`, 52 arquivos committáveis, anonimizados deterministicamente, 0 PII vazada (validado automaticamente), base64 inline preservado.
- [x] **Auditoria de aderência** código atual × realidade: 12 divergências documentadas (§7.6.8) com tasks corrigindo cada uma.
- [x] README do catálogo escrito em `tests/fixtures/captured/README.md` com matriz MECE completa.
- [x] Anonymizer (`tools/anonymize_captures.py`) committável como ferramenta reexecutável — re-rodar regenera o catálogo todo.
- [ ] Docker network `pace-net` criada (adiado — só relevante no deploy VPS).
- [ ] VPS Hostinger provisionada (adiado — Fase 1 opera em dev via Tailscale até então).

---

## 14. Apêndices

### 14.1. Links e referências

- **Evolution API repo:** https://github.com/EvolutionAPI/evolution-api
- **Issue HMAC upstream:** https://github.com/EvolutionAPI/evolution-api/issues/102 (fechada sem implementação)
- **PR que adicionou `jwt_key`:** #1318 ("Tornando Webhook mais seguro com JWT token")
- **Arquivo fonte do dispatcher de webhook:** `src/api/integrations/event/webhook/webhook.controller.ts` (v2.3.7)
- **Documentação oficial:** https://doc.evolution-api.com/v2/en/configuration/webhooks
- **Tailscale ACLs:** https://tailscale.com/kb/1018/acls

### 14.2. Glossário

- **Tenant** — Cliente isolado lógico no ProsauAI. Cada tenant = 1 instância Evolution + 1 secret + 1 conjunto de regras de mention.
- **Instance name** — Identificador da instância na Evolution API (ex: `Ariel`). Usado como chave pública para identificar o tenant no path do webhook.
- **Webhook secret** — Secret compartilhado entre Evolution (que envia no header) e ProsauAI (que valida). Per-tenant.
- **Idempotência** — Garantia de que processar o mesmo `message_id` duas vezes produz o mesmo resultado que processar uma vez.
- **Debounce** — Agrupar mensagens rápidas do mesmo sender em um buffer antes de processar (feature do epic 001).
- **Retry storm** — Situação onde Evolution retenta um webhook múltiplas vezes em sequência por erro transiente.
- **Fase 1/2/3** — Entregas faseadas: fundação multi-tenant → abrir para externos → operação em produção.

### 14.3. Status de cada decisão

| Decisão | Status |
|---|---|
| Remover HMAC | Decidido |
| Adicionar `Tenant` abstração | Decidido |
| Tenant store em YAML, localização `config/tenants.yaml` | Decidido (localização confirmada por Gabriel em 2026-04-10) |
| Auth via `X-Webhook-Secret` estático | Decidido + **validado empiricamente** (seção 4.5) |
| Idempotência por `(tenant_id, message_id)` com TTL 24h | Decidido |
| Prefixar keys Redis com `tenant_id` | Decidido |
| Bind Docker só em interface privada (Tailscale/Docker network) | Decidido |
| 1 PR grande vs muitos pequenos | 1 PR grande (decidido) |
| `mention_phone` do tenant `pace-internal` = `5511910375690` | Confirmado com payload real |
| Adicionar segundo tenant `resenha-internal` (instância `ResenhAI`) desde o dia 1 | Decidido em 2026-04-10 — valida isolamento real entre tenants |
| `mention_phone` do tenant `resenha-internal` = `5511970972463` | Confirmado via `participants[].jid` em payload real |
| **Adicionar `mention_lid_opaque` ao Tenant schema** | **Necessário** — detecção de mention em grupo moderno usa `@lid` opaco em `mentionedJid`, não phone. Tasks T6h, T6f. |
| `mention_lid_opaque` Ariel = `103487874539537` | Descoberto no capture #035 |
| `mention_lid_opaque` ResenhAI = `146102623948863` | Descoberto nos captures #025/#038 |
| **messageType real** é `imageMessage`/`videoMessage`/etc. (não `image`/`video`) | Task T6b — reescrita total de `_MEDIA_TYPES` |
| **`mentionedJid` vive em `data.contextInfo`**, não em `extendedText.contextInfo` | Task T6f — parser tinha mentions no lugar errado |
| **Parser deve ler `conversation` como universal** (texto longo e URL chegam como `conversation`, não `extendedTextMessage`) | Validado empiricamente em 4 captures |
| Parser `@lid` em individual: usa `key.senderPn` | Task T6c |
| Parser `@s.whatsapp.net` legacy: usa `key.senderLid` como espelho do lid | Task T6c |
| Parser em grupo: sender é `key.participant` (@lid opaco, sem phone inline) | Task T6c — implica mudar `ParsedMessage` schema (T6c) |
| Parser `groups.upsert`: branch novo, `data` é **lista** | Task T6d |
| Parser `group-participants.update`: branch novo, `data` é dict **sem** `key` | Task T6e |
| Parser ignora `messageContextInfo`, `chatwoot*`, `deviceListMetadata`, `status`, `source` | Task T6i |
| Parser extrai `data.contextInfo.quotedMessage` pra replies | Task T6g |
| Rota pra `reactionMessage` — pendente decidir se `IGNORE` ou nova | Task T6j |
| Sender key no debounce = `sender_lid_opaque or sender_phone` | Necessário pra sobreviver a grupo onde phone não está disponível |
| Capture tool aceita múltiplos secrets simultâneos | Decidido — captura paralela de N tenants sem reconfigurar |
| Secrets de dev gerados (`PACE_*` e `RESENHA_*`) e armazenados em `.env` | Feito |
| Webhooks Ariel + ResenhAI revertidos para `:8050/webhook/whatsapp/{instance}` após captura | Feito |
| **36 capturas reais** coletadas cobrindo 3 eventos, 2 tenants, 2 contextos, 4 sender formats, 13 content types | Feito |
| **26 fixture pairs** committáveis gerados em `tests/fixtures/captured/` | Feito |
| **Fixture sintética do epic 001** (`tests/fixtures/evolution_payloads.json`) será substituída pelas fixtures reais | Decidido — mantida em disco até a refatoração remover, pra não quebrar os testes antigos intermediariamente |
| base64 inline preservado nas fixtures (não truncar) | Decidido em 2026-04-10 — não é confidencial, dá cobertura completa de shape |
| Anonimização determinística com mapping reutilizável via `tools/anonymize_captures.py` | Decidido — permite regeneração idempotente do catálogo |
| Fase 2 (admin API, Caddy, rate limit) | Adiado |
| Fase 3 (Postgres, metrics, billing) | Adiado |
| Usar `jwt_key` da Evolution | Rejeitado |

---

## 15. Próximos Passos Imediatos

Após aprovação deste plano (toda a fase de preparação já foi feita —
ver §7.6.1 a §7.6.9):

1. **Criar branch `feat/multi-tenant-auth`** a partir de `develop`.
2. **Bloco 1: fundação multi-tenant** (T1-T5) — `Tenant`, `TenantStore`, `Settings` refactor, idempotência helper, testes unitários.
3. **Bloco 2: auth + roteamento fiel aos payloads reais** (T6-T6j) — o core da refatoração. Nessa ordem:
   - T6: reescrever `dependencies.py` (remover HMAC, adicionar resolver de tenant)
   - T6b: reescrever `_MEDIA_TYPES` com nomes reais (`imageMessage`, ...)
   - T6c: resolução de sender multi-formato (@lid+senderPn, legacy+senderLid, group participant)
   - T6d: branch de `groups.upsert` (data é lista)
   - T6e: branch de `group-participants.update` (data sem key)
   - T6f: corrigir `mentionedJid` pra ler de `data.contextInfo`
   - T6g: extrair `quotedMessage` de reply
   - T6h: `mention_lid_opaque` no Tenant + router 3-strategy detection
   - T6i: ignorar campos irrelevantes silenciosamente
   - T6j: decidir rota pra reactions
4. **Bloco 3: integração** (T7-T11) — refactor de `router.py`, `webhooks.py`, `debounce.py`, `main.py`, `_flush_echo`.
5. **Bloco 4: deploy** (T12-T14) — `docker-compose.yml`, `.env`, `.gitignore`, override.
6. **Bloco 5: testes e docs** (T15-T17) —
   - T15: README reescrito (sem HMAC, com workflow de novo tenant)
   - **T16: `test_captured_fixtures.py`** — teste paramétrico contra as 26 fixtures reais. **É o critério final de correção do parser.**
   - T17: deletar `tests/fixtures/evolution_payloads.json` (sintética, desalinhada)
7. **Validação dev (Tailscale)** — rodar `docker compose up`, mandar mensagem real de WhatsApp pros 2 bots, verificar echo de volta + logs com `tenant_id` + `instance_id`.
8. **Deploy em prod VPS** (quando tiver VPS provisionada) — Docker network privada, sem `ports:`.

**O que está pronto ANTES de iniciar a branch:**

- ✅ Arquitetura aprovada (Alternativa D)
- ✅ Hipótese `X-Webhook-Secret` validada
- ✅ 2 tenants reais configurados na Evolution com secrets distintos
- ✅ `mention_lid_opaque` de ambos os tenants descoberto e documentado
- ✅ `.env` + `config/tenants.yaml` + `.gitignore` + `.env.example` + `tenants.example.yaml`
- ✅ Porta 8050 aplicada em todo o código
- ✅ 36 payloads reais capturados
- ✅ 26 fixture pairs committáveis gerados e validados
- ✅ 12 divergências do parser vs. realidade documentadas
- ✅ Anonimizador reexecutável committado
- ✅ Webhooks apontando pra produção (`:8050/webhook/whatsapp/{instance}`)
- ✅ Plano de implementação 100% consistente com a realidade dos payloads

---

**Fim do documento.**

Qualquer pessoa lendo isto deve ter contexto suficiente para: (a) entender por que o código está sendo refatorado, (b) reproduzir a arquitetura, (c) saber exatamente o que cada task tem que fazer e contra o que validar, (d) estender para a Fase 2 quando chegar a hora.
