# Contracts — Epic 009 Channel Ingestion Normalization + Content Processing

Contratos in-process (Python Protocols) e contratos HTTP (webhooks de entrada) consumidos por este epic.

## Arquivos

- [`channel-adapter.md`](./channel-adapter.md) — Contrato `ChannelAdapter` Protocol. Adapters source-specific (`EvolutionAdapter`, `MetaCloudAdapter`) implementam este contrato. Pipeline NUNCA conhece adapters; só consome `CanonicalInboundMessage`.
- [`content-processor.md`](./content-processor.md) — Contrato `ContentProcessor` Protocol + `ProcessorContext`. Processors por `kind` (`AudioProcessor`, `ImageProcessor`, …) consomem injeção de dependências e produzem `ProcessedContent`.
- [`openapi.yaml`](./openapi.yaml) — OpenAPI 3.1 spec dos webhooks HTTP (Evolution e Meta Cloud). Cobre também o alias legado `/webhook/whatsapp/{instance_name}`.

## Tipos gerados

Não há frontend novo neste epic (o admin é reusado do 008 sem mudança estrutural). Entretanto, o **Admin Performance AI** do 008 passa a ler `media_analyses` e `processor_usage_daily` via endpoints admin novos. Esses endpoints serão adicionados ao `contracts/openapi.yaml` do **epic 008** (via aditivo, não aqui) — decisão tomada para evitar dividir o openapi do admin em dois arquivos.

## Contratos por camada

| Camada | Contrato | Arquivo |
|--------|----------|---------|
| Ingestion (Python) | `ChannelAdapter` | `channel-adapter.md` |
| Processing (Python) | `ContentProcessor`, `ProcessorContext`, `ProcessorProviders` | `content-processor.md` |
| Ingestion (HTTP) | `POST /webhook/evolution/{instance_name}`, `POST /webhook/meta_cloud/{tenant_slug}`, `GET /webhook/meta_cloud/{tenant_slug}` (verify), `POST /webhook/whatsapp/{instance_name}` (alias legado) | `openapi.yaml` |

## Gates de contrato (merge-blocking)

- **PR-A merge**: `ChannelAdapter` Protocol estável; `EvolutionAdapter` implementa 100% das 13 fixtures Evolution reais.
- **PR-B merge**: `ContentProcessor` Protocol estável; processors `audio`, `image`, `document`, `sticker`, `location`, `contact`, `reaction`, `text`, `unsupported` registrados no registry global.
- **PR-C merge**: `MetaCloudAdapter` implementa `ChannelAdapter` sem ampliar o Protocol e sem tocar `pipeline.py`/`processors/`/`core/router/`. Isto é o gate de validação arquitetural (SC-013).
