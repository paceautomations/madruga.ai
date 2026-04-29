---
epic: 016-trigger-engine
node: roadmap-reassess
created: 2026-04-29
---

# Roadmap Reassess — Epic 016 (Trigger Engine)

## Status

Epic 016 shipped. Roadmap atualizado em `planning/roadmap.md` durante a fase de reconcile.

## Alterações Aplicadas

### Epics Entregues
- **016** (Trigger Engine): `in_progress` → `shipped`. Ariel agente-piloto com shadow mode ativo.

### Próximos Passos (roadmap atualizado)
- **017** (Reconcile 010-012): Fechar ciclos L2 dos epics implementados sem reconcile formal.
- **018** (Primeiro Deploy VPS): Após validação shadow Ariel + DPO sign-off LGPD.

### Novos Riscos Adicionados
| Risco | Severidade | Status |
|-------|-----------|--------|
| S1 — LGPD hard-delete ON DELETE CASCADE sem validação DPO | Alto | ABERTO |
| W5 — Circuit breaker Evolution API não testado sob 5xx storm | Médio | A verificar |

### Epics Futuros Renumerados
Slots 015/016 ocupados — epics futuros renumerados para 017–024 no roadmap.

## Carry-forwards

- **S1 (DPO)**: Validar `ON DELETE CASCADE` aceitável antes de `mode: live` em Ariel.
- **W5 (CB)**: Load test Evolution API com 5xx consecutivos antes do rollout live.
