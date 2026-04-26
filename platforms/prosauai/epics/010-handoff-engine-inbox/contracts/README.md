# Contracts — Epic 010 Handoff Engine

**Feature Branch**: `epic/prosauai/010-handoff-engine-inbox`
**Date**: 2026-04-23

## Documentos

| Arquivo | Escopo | Stability |
|---------|--------|-----------|
| [helpdesk-adapter.md](./helpdesk-adapter.md) | `HelpdeskAdapter` Protocol (Python) + `ChatwootAdapter` + `NoneAdapter` behaviors + contract tests | STABLE apos PR-A merge |
| [openapi.yaml](./openapi.yaml) | OpenAPI 3.1 dos 4 endpoints novos (1 webhook Chatwoot + 3 admin) | STABLE apos PR-C merge |

## Gates de contrato

- **PR-A merge**: `helpdesk-adapter.md` define o Protocol; contract test `test_helpdesk_adapter_contract.py` valida `isinstance(ChatwootAdapter, HelpdeskAdapter)` e `isinstance(NoneAdapter, HelpdeskAdapter)`.
- **PR-B merge**: webhook `POST /webhook/helpdesk/chatwoot/{tenant_slug}` implementado conforme `openapi.yaml`; integration test valida HMAC + idempotency + 2 event types.
- **PR-C merge**: admin endpoints (`/mute`, `/unmute`, `/reply`) implementados conforme `openapi.yaml`; E2E Playwright valida fluxo completo US3 + US5.

## Breaking changes policy

Qualquer mudanca no Protocol `HelpdeskAdapter` pos-PR-A merge e **breaking change** — exige:
1. Revisao dos 2 adapters v1 (`ChatwootAdapter`, `NoneAdapter`).
2. Re-run contract tests.
3. Nota em `decisions.md` justificando.
4. Se epic 010.1 (Blip/Zendesk) ja estiver em flight, coordenar cutover.

Mudancas na OpenAPI spec (adicao de fields opcionais, novos endpoints) NAO sao breaking. Remocao de endpoints ou mudanca de shape de response body e breaking — exige bump de versao da API (aditivo v2 em paralelo ate deprecation).
