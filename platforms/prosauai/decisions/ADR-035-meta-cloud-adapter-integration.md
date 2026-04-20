---
title: 'ADR-035: Meta Cloud adapter integration (architectural proof of the
  channel abstraction, test-first)'
status: Accepted
decision: >-
  Implement the second inbound channel — WhatsApp via Meta Cloud API
  (Graph API v19.0) — as a new ``MetaCloudAdapter`` implementing the
  ``ChannelAdapter`` Protocol (ADR-031). The adapter is written
  **test-first** against captured real payloads **before** PR-A is merged,
  and PR-C's merge gate is a binary check — **zero diff** in
  ``apps/api/prosauai/pipeline.py``, ``apps/api/prosauai/processors/**``
  and ``apps/api/prosauai/core/router/**``. If any of those files change,
  the adapter Protocol (ADR-031) is considered leaky and must be revised
  before the epic closes.
alternatives: >-
  Evolution-only v1 with a "shim" for future channels; merge
  Meta Cloud directly into ``prosauai.api.webhooks`` with ad-hoc branching;
  separate microservice gateway (Go / Node) that normalises inbound
  webhooks to a gRPC call to prosauai; postpone Meta Cloud entirely and
  validate the abstraction with a synthetic "FakeChannelAdapter" in tests.
rationale: >-
  ADR-031 formalises the abstraction, but an abstraction that is
  only exercised by one real caller cannot prove it holds. Meta Cloud is
  the natural second caller — it is fundamentally different from Evolution
  in payload shape (batch of messages, ``entry[*].changes[*].value``),
  authentication (HMAC-SHA256 vs. shared secret header) and binary
  delivery (URL fetch with bearer token vs. inline base64). Writing
  ``MetaCloudAdapter`` test-first against real fixtures before finishing
  the Evolution migration forces any hidden Evolution-isms in the
  Canonical / adapter surface to surface early, when fixing them is
  cheap. The SC-013 gate ("diff zero in core") turns the validation into
  a deterministic, machine-checked assertion on the merge commit.
---

# ADR-035: Meta Cloud adapter integration (architectural proof of the channel abstraction, test-first)

**Status:** Accepted | **Data:** 2026-04-19 | **Supersede:** — | **Relaciona:** [ADR-030](ADR-030-canonical-inbound-message.md), [ADR-031](ADR-031-multi-source-channel-adapter.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md)

> **Escopo:** Epic 009 (Channel Ingestion + Content Processing) PR-C. Esta ADR formaliza **por que** o epic coloca o Meta Cloud Adapter como último PR mas o **escreve primeiro** em nível de fixture + teste, e **como** esse PR serve de *regression test arquitetural* contra o ADR-031.

## Contexto

Três fatos convergem:

1. **ADR-031 é uma hipótese até ser testada.** Toda abstração que nunca foi exercitada por um segundo caller é, na prática, uma generalização de *um* caso particular. Em Python, `Protocol` + `runtime_checkable` ajuda, mas é satisfeito por qualquer shape conformante — inclusive por abstrações que "parecem genéricas" mas carregam premissas Evolution. Exemplos concretos de premissas que só aparecem quando um segundo adapter é implementado:
   - *"Um webhook request contém uma única mensagem."* Evolution entrega exatamente uma; Meta Cloud entrega batches via ``entry[*].changes[*].value.messages[*]``. Se o Protocol assumir 1:1, quebra.
   - *"`source_instance` é um human-readable slug."* Evolution usa o instance name (``ariel``); Meta Cloud usa o ``phone_number_id`` numérico (``107348371915028``). Se qualquer lookup trata isso como "o slug do tenant", quebra.
   - *"Autenticação é um header de secret constante."* Evolution usa ``X-Webhook-Secret``; Meta Cloud usa HMAC-SHA256 do body inteiro + handshake GET com ``hub.challenge``. Se o handler tem um único dependency FastAPI, quebra.
   - *"Binário da mídia vem inline em base64."* Evolution frequentemente manda ``data.message.base64``; Meta Cloud **nunca** manda — sempre requer ``GET /v19.0/{media_id}`` autenticado com access token para resolver a URL, e *depois* um segundo ``GET`` nessa URL. Se o processor assume `block.data_base64 or block.url → download`, quebra em Meta Cloud.
   - *"Um external message id é global."* Não é — dois canais podem emitir IDs que colidem. É por isso que o ``idempotency_key`` é ``sha256(source + source_instance + external_id)`` (decisão D11).

2. **O epic 009 precisa entregar Meta Cloud de qualquer forma.** Não como volume-de-tráfego em v1 (Ariel e ResenhAI continuam via Evolution por padrão), mas como **opção operacional**: uma conta de teste do ResenhAI está em onboarding na WhatsApp Business Platform, e queremos poder alternar canal por tenant sem deploy se algum dia Evolution cair ou mudar modelo comercial.

3. **PR-A + PR-B têm ciclo longo** (~4 semanas combinadas). Se esperarmos até PR-C começar (semana 5) para descobrir uma premissa leaky no Canonical ou no Protocol, o custo de consertar é alto: precisaríamos mexer em EvolutionAdapter, pipeline, router e observability tudo junto, com o tráfego real já fluindo pelo novo caminho.

A conclusão do trade-off (formalizada em [decisions.md D21](../epics/009-channel-ingestion-and-content-processing/decisions.md) e no [pitch §Suggested Approach](../epics/009-channel-ingestion-and-content-processing/pitch.md)) foi: **antecipar a prova arquitetural** escrevendo ``MetaCloudAdapter.normalize()`` contra fixtures reais **durante PR-A**, mesmo que o merge do adapter em produção só aconteça em PR-C. Os testes de contrato rodam vermelhos até PR-C, mas o *código* existe e exercita o schema — garantindo que qualquer viés de Evolution no Canonical ou no Protocol apareça cedo.

## Decisão

Esta ADR formaliza **três compromissos** que, juntos, tornam o ADR-031 falsificável:

### 1. Test-first ordering

Durante PR-A:
- **T190** (``tests/fixtures/captured/meta_cloud_*.input.json``) captura 4 payloads reais Meta Cloud de um sandbox da conta de teste do prosauai: um texto puro, um áudio, uma imagem com caption e um interactive reply (button/list).
- **T191–T195** (``tests/contract/test_channel_adapter_contract.py``) incluem ``MetaCloudAdapter`` na parametrização *desde o início*, junto com ``EvolutionAdapter``. Os testes rodam vermelhos para Meta Cloud até PR-C, mas já *verificam o shape* esperado do Canonical. Qualquer expansão indevida do Canonical durante PR-A quebra esses testes.

Resultado operacional: o dev que estiver escrevendo ``EvolutionAdapter`` vê o impacto em ``MetaCloudAdapter`` no mesmo PR, não três semanas depois.

### 2. SC-013: diff zero nos "core files"

O merge de PR-C só é aceito se ``git diff develop..HEAD --stat`` sobre os seguintes caminhos produzir **zero bytes de output**:

- ``apps/api/prosauai/pipeline.py``
- ``apps/api/prosauai/pipeline/`` (todo o pacote)
- ``apps/api/prosauai/processors/`` (todo o pacote)
- ``apps/api/prosauai/core/router/`` (todo o pacote)
- ``apps/api/prosauai/observability/step_record.py``
- ``apps/api/prosauai/channels/canonical.py``
- ``apps/api/prosauai/channels/base.py``

Arquivos que PR-C **pode** (e deve) tocar:
- ``apps/api/prosauai/channels/inbound/meta_cloud/*`` (adapter + auth + __init__)
- ``apps/api/prosauai/api/webhooks/meta_cloud.py`` (novo FastAPI router)
- ``apps/api/prosauai/main.py`` (uma linha: ``register(MetaCloudAdapter(...))``)
- ``apps/api/prosauai/config.py`` (ler ``META_CLOUD_APP_SECRET`` / ``META_CLOUD_VERIFY_TOKEN`` do env)
- ``apps/api/tests/fixtures/captured/meta_cloud_*.input.json`` (fixtures)
- ``apps/api/tests/unit/channels/test_meta_cloud_adapter.py`` (unit)
- ``platforms/prosauai/decisions/ADR-035-*.md`` (esta ADR)

CI é configurado com um grep step no PR-C para validar o stat — qualquer byte em um "core file" falha o merge.

### 3. Paridade de 14 steps no trace

Mensagens Meta Cloud percorrem os **mesmos 14 steps** emitidos em OTel (``webhook_receive → auth → parse → debounce → save_inbound → content_process → build_context → route → generate → safety_check → save_outbound → send_out → ack``) com os mesmos atributos. A única diferença visível no Trace Explorer é o atributo ``source="meta_cloud"`` vs ``source="evolution"``. Se algum step precisar ganhar um atributo novo **específico do Meta Cloud**, o ADR é invalidado (ver Kill Criteria).

## Alternativas consideradas

### A. Evolution-only v1 + shim "para futuro"

**Descrição.** Mergear epic 009 apenas com Evolution + um ``TODO: ChannelAdapter`` placeholder. Prometer que o próximo canal vem quando necessário.

**Rejeitada por.** É exatamente o padrão que nos trouxe ao problema atual: o antigo ``InboundMessage`` era Evolution-only "por enquanto", e três épicos depois o ``if message.text:`` bloqueou todo conteúdo não-textual. Sem um segundo caller real, a abstração não é testada e vira *"wishful generality"*.

### B. Merge Meta Cloud no ``prosauai.api.webhooks`` existente com branching

**Descrição.** Em ``webhooks.py``, adicionar ``if source == "meta_cloud": ... elif source == "evolution": ...`` e traduzir inline.

**Rejeitada por.** Quebra ADR-031 antes de ele ter chance de existir: `webhooks.py` vira um if-else com tradução, autenticação e normalização misturadas, impossível de testar isoladamente. Foi justamente o tipo de acoplamento que o epic 009 existe para eliminar.

### C. Microservice gateway (Go / Node) traduzindo para gRPC

**Descrição.** Um binário externo recebe webhooks, traduz para uma mensagem protobuf e chama o prosauai via gRPC.

**Rejeitada por.** Stack adicional (runtime + deploy + observability) para um ganho teórico. ADR-011 (pragmatismo) e ADR-031 (Alternative D) já rejeitaram esse padrão pelos mesmos motivos. 2 canais ativos não justificam um gateway.

### D. Validar só com ``FakeChannelAdapter`` em testes

**Descrição.** Em vez de Meta Cloud real, escrever um stub ``FakeChannelAdapter`` que produz payloads "estranhos" (multi-message batches, base64-opcional) e passar a suite.

**Rejeitada por.** Um fake é escrito por alguém que *já sabe* o shape do Canonical. Os fakes tendem a produzir exatamente o que o código do produtor já suporta — é impossível descobrir um edge case que você não conhece. Fixture real do Meta Cloud é produzida pelo Meta, não por nós, e carrega toda a complexidade operacional que queremos testar.

## Consequências

### Positivas

- **Prova arquitetural real**: quando PR-C mergar verde com diff zero em core, o ADR-031 deixa de ser hipótese e vira **verificado**.
- **Descoberta antecipada de vieses**: qualquer premissa Evolution leaky no Canonical surge durante PR-A (testes vermelhos já apontando) em vez de na semana 5.
- **Opção operacional real**: prosauai passa a ter um segundo caminho WhatsApp viável. Se Evolution cair ou mudar modelo comercial, cada tenant pode ser alternado para Meta Cloud via feature flag + reconfig de endpoint.
- **Playbook reproduzível**: com Meta Cloud mergeado, adicionar Telegram/Instagram em um epic futuro vira *"copiar `meta_cloud/`, ajustar `normalize()`, pronto"*. O README de ``channels/`` (T208) documenta isso em 4 passos.
- **CI check barato e binário**: grep por ``git diff --stat`` custa ~50ms e fala uma resposta única (pass/fail) sobre um critério explícito.

### Negativas

- **Dev cost extra em PR-A**: escrever fixture + contract tests para Meta Cloud já em PR-A adiciona ~1 dia de trabalho. Aceito — é menos do que o custo de descobrir um viés na semana 5.
- **Fixtures envelhecem**: se a Meta bumpar Graph API (v19 → v20) e mudar shape, as fixtures viram históricas. Mitigação: ADR-035 indica refresh quando a Meta anunciar major; owner do epic 009 (ou seu sucessor) é responsável.
- **Gate binário é estrito**: se um bug legítimo em ``step_record.py`` for descoberto durante PR-C (ex.: order validation aceita 15 steps quando deveria aceitar 14), o fix precisa ir em PR paralelo e ser mergeado **antes** do PR-C. Aceito — força disciplina sobre refactors oportunistas no PR-C.
- **Conta Meta sandbox é setup manual**: alguém precisa criar a Business App no Meta, aprovar webhook, gerar app secret. Documentado em quickstart.md §3 — não é um blocker, mas exige 1h de onboarding.

### Neutras

- **Performance**: MetaCloudAdapter acrescenta 1 dict lookup no registry (negligível) e, para mídia, 1 HTTP GET extra para resolver ``media_id → url`` (comparado a Evolution que pode vir inline). Esse GET é síncrono no processor step 6 e conta dentro do budget de latência ADR-033 (audio 15s, image 12s). Se passar a importar, envolve caching do media handle no Redis.
- **Escopo**: PR-C não cobre outbound Meta Cloud (envio de respostas via Meta). Isso fica para epic futuro quando algum tenant migrar tráfego real. A spec v1 é inbound-only.

## Kill Criteria

Esta ADR é invalidada — e o epic 009 **não** fecha com sucesso — se:

1. **PR-C precisar tocar um arquivo core listado na §Decisão #2.** Isso prova que o ADR-031 é leaky. Ação: rollback PR-C, revisar Canonical/Protocol, regenerar ADR-031.
2. **Meta Cloud exigir um 15º step no pipeline** para acomodar um passo próprio (ex.: ``resolve_media_id``) que não se encaixa em nenhum processor. Ação: revisar decisão D14 (multi-message debounce) — provavelmente o passo é responsabilidade do adapter, não do pipeline.
3. **Cross-source idempotency falhar** (T194): dois payloads com mesmo external_id em sources diferentes tratados como duplicados. Ação: revisar decisão D11 (idempotency key composition).
4. **Latência p95 Meta Cloud > 2× a de Evolution** no mesmo tenant (benchmark pós-merge PR-C). Ação: verificar se o GET extra de media_id precisa de caching no adapter, ou se o Meta rate-limit está degradando o canal.

## Links

- Implementação: [apps/api/prosauai/channels/inbound/meta_cloud/adapter.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/channels/inbound/meta_cloud/adapter.py)
- Auth handler: [apps/api/prosauai/channels/inbound/meta_cloud/auth.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/channels/inbound/meta_cloud/auth.py)
- Webhook router: [apps/api/prosauai/api/webhooks/meta_cloud.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/prosauai/api/webhooks/meta_cloud.py)
- Fixtures reais: [apps/api/tests/fixtures/captured/meta_cloud_*.input.json](https://github.com/paceautomations/prosauai/tree/develop/apps/api/tests/fixtures/captured)
- Contract test: [apps/api/tests/contract/test_channel_adapter_contract.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/tests/contract/test_channel_adapter_contract.py)
- Dev helper: [apps/api/scripts/sign_meta_webhook.py](https://github.com/paceautomations/prosauai/blob/develop/apps/api/scripts/sign_meta_webhook.py)
- Spec: [epics/009-channel-ingestion-and-content-processing/spec.md — SC-013](../epics/009-channel-ingestion-and-content-processing/spec.md)
- Plan: [epics/009-channel-ingestion-and-content-processing/plan.md — PR-C cut-line](../epics/009-channel-ingestion-and-content-processing/plan.md)
- Decisions: [epics/009-channel-ingestion-and-content-processing/decisions.md D21](../epics/009-channel-ingestion-and-content-processing/decisions.md)
- Contract: [epics/009-channel-ingestion-and-content-processing/contracts/channel-adapter.md §2.2](../epics/009-channel-ingestion-and-content-processing/contracts/channel-adapter.md)
- Quickstart dev flow: [epics/009-channel-ingestion-and-content-processing/quickstart.md §3](../epics/009-channel-ingestion-and-content-processing/quickstart.md)
