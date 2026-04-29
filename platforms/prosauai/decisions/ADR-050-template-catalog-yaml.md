---
id: ADR-050
title: "Template Catalog: YAML-Managed, Manual Ops, Auto-Sync Adiado"
status: reviewed
deciders: [gabrielhamu]
date: 2026-04-29
supersedes: ~
---
# ADR-050 — Template Catalog: YAML-Managed, Manual Ops, Auto-Sync Adiado

## Status: reviewed

## Contexto

Mensagens proativas no WhatsApp exigem uso de **HSM templates** pre-aprovados pelo
Meta Business Manager. As opcoes para gestao desses templates foram:

1. **YAML-managed** — ops cadastra manualmente no `tenants.yaml`; auto-sync adiado
2. **Tabela DB** — `template_catalog` com RLS; UI de gerenciamento admin
3. **Auto-sync via Graph API** — busca templates aprovados automaticamente na API do Meta

Volume v1: ~2-5 templates por tenant. DB + UI adiciona ~1 semana de implementacao
sem valor imediato. Auto-sync via Graph API exige OAuth de negocio que ainda nao foi
instrumentado na plataforma.

## Decisao

Templates HSM catalogados em `tenants.yaml templates.*` com campos:
`name, language, components, approval_id, cost_usd`.

Manual ops: apos aprovacao do template no Meta Business Manager, ops adiciona ao YAML.
Hot-reload <60s via config_poller — sem restart necessario.

Auto-sync via Graph API adiado para 016.1+ apos validacao Ariel (primeiros 30 dias
com template real em producao).

## Consequencias

**Positivas:**
- Zero nova infra — reutiliza config_poller existente
- Auditoria via git (YAML versionado) — quem adicionou, quando, aprovacao explícita
- Sem UI de gerenciamento a implementar em v1

**Negativas / Trade-offs:**
- Operacional manual — ops precisa editar YAML e aguardar hot-reload (aceitavel em v1)
- Auto-sync adiado — se template for desaprovado pelo Meta, plataforma continua tentando
  envia-lo ate ops remover do YAML (mitigado por error log + alerta critico)
- Self-service em epic 018 precisara expor editor YAML ou implementar tabela DB

## Refs

- decisions.md D3, D11, D16
- [ADR-049](ADR-049-trigger-engine-cron-design.md) (Trigger Engine Cron Design)
- [judge-report.md](../epics/016-trigger-engine/judge-report.md)
