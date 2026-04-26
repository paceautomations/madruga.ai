# Runbook — Production Rollout T092 (Epic 012)

> **Audiencia**: Pace ops + tech lead. Runbook de execucao para o
> rollout produtivo do RAG (T092) em Ariel + ResenhAI.

> **Status (autonomous run, 2026-04-26)**: backlog tecnico inteiro
> (T001-T091) pronto para deploy. T092 e a execucao operacional —
> requer staging real, monitoramento humano e janela de smoke 24h+7d.
> Este documento congela o procedimento; a execucao real depende da
> disponibilidade ops e da janela de manutencao tecnica.

## Pre-rollout (gate)

- [x] PR-A merged (T001-T026): schema + utilities + Bifrost extension.
- [x] PR-B merged (T027-T063): API admin + tool + Trace integration.
- [x] PR-C merged (T064-T081): UI + per-agent toggle + CLI re-embed.
- [x] T082-T091 completos: docs, runbooks, ADRs, baseline doc, e2e tests.
- [x] Migrations 06-09 aplicadas em staging.
- [x] Bifrost extension OpenAI embeddings em prod.
- [x] Test invariant cross-tenant verde (`rag-invariant-nightly` GA workflow).

## Sequencia de execucao

### Fase 1 — Ariel smoke (24h)

Seguir [`apps/api/docs/runbooks/rag-rollout.md`](../../../prosauai/apps/api/docs/runbooks/rag-rollout.md)
no repo `prosauai`. Steps essenciais:

1. Subir 1 FAQ MD curto (`faq-pace.md`) via admin UI ou curl.
2. Habilitar `rag.enabled: true` em `tenants.yaml` para Ariel staging.
3. Toggle `search_knowledge` no agente principal Ariel.
4. Disparar 30 mensagens via simulator -> verificar Trace Explorer.
5. Aguardar 24h em prod com monitoring ativo.
6. Capturar baseline em
   [`apps/api/docs/performance/rag-baseline.md`](../../../prosauai/apps/api/docs/performance/rag-baseline.md).

**Go criteria**:
- SC-002 zero leak (nightly invariant verde).
- SC-003 upload p95 `<=15s`.
- SC-004 search p95 `<=2s`.
- SC-006 chunks cited `>=20%` (medido no fim das 24h).
- SC-010 spend desvio `<=2%`.

### Fase 2 — ResenhAI (7 dias)

Pre-cond: Fase 1 verde + zero incidente.

1. Subir FAQ PDF real (~10-15 paginas) via admin UI.
2. Habilitar `rag.enabled: true` em `tenants.yaml` para ResenhAI.
3. Toggle `search_knowledge` em **2 agentes** distintos.
4. Aguardar 7d com monitoring.
5. Atualizar baseline doc com numeros reais.

**Go criteria** (mesmo da Fase 1, plus):
- 7d de prod sem incidente.
- ResenhAI tenant satisfeito com qualidade de resposta (review human).

### Pos-rollout

- Atualizar `apps/api/docs/performance/rag-baseline.md` com numeros
  observados.
- Marcar epic 012 como **shipped** no DAG via
  `python3 .specify/scripts/post_save.py --platform prosauai --epic 012-tenant-knowledge-base-rag --node implement --skill speckit.implement --artifact rollout-complete`.
- Abrir 012.1 backlog (versionamento de documentos, dedup automatica,
  threshold per-tenant) se 2+ tenants pedirem.

## Reversao (RTO <=60s)

Se qualquer go criterion falhar:

```yaml
# tenants.yaml
tenants:
  ariel:    # ou resenhai
    rag:
      enabled: false   # <-- flip
```

Commit + push -> config_poller hot-reload em <=60s.

Documentos persistidos sao preservados — re-enable mais tarde sem
perda. Documentado em ADR-041.

## Comunicacao

- **Pre-rollout** (24h antes): notificar tenant via email + Slack #ops.
- **Inicio rollout**: anunciar em #releases com link pro runbook.
- **Pos-Fase 1 (24h)**: status update + go/no-go decision.
- **Pos-Fase 2 (7d)**: review + decision sobre rollout demais tenants.
- **Em rollback**: anunciar imediato em #ops + ETA de fix.

## Referencias
- Runbook tecnico: `apps/api/docs/runbooks/rag-rollout.md` (no repo prosauai)
- Performance baseline: `apps/api/docs/performance/rag-baseline.md`
- ADR-041 / ADR-042
- Quickstart: `quickstart.md` Steps 1-13
- Spec: `spec.md` SC-001..SC-012
