---
id: 002
title: "RECONCILE: Auto-Update de Vision apos Implementacao"
status: proposed
phase: pitch
appetite: small-batch
priority: next
arch:
  modules: [autoMarkers, modelPipeline, pipelineRunner]
  contexts: [documentation, execution]
  containers: [visionBuild, pipelinePhases]
---
# RECONCILE: Auto-Update de Vision apos Implementacao

## Problema

Apos a fase IMPLEMENT, os docs de Vision (engineering/) ficam desatualizados. O modelo LikeC4 pode ter mudado (novos containers, relacionamentos), mas os AUTO markers nos markdowns nao sao re-populados. Resultado:

1. **Docs desatualizados** — tabelas de containers e relacionamentos nao refletem o estado real
2. **Drift silencioso** — ninguem percebe que docs estao stale ate alguem ler
3. **Trabalho manual** — arquiteto precisa lembrar de rodar `vision-build.py` depois de cada implementacao
4. **Confianca corroida** — se docs podem estar errados, ninguem confia neles

## Appetite

1-2 semanas (small batch). A infra ja existe (vision-build.py, AUTO markers). O trabalho e integrar como fase automatica no pipeline.

## Solucao

Fechar o loop apos implementacao: ler o PR diff, comparar contra a arquitetura (modelo LikeC4, docs de engineering), calcular `drift_score`, e decidir automaticamente o proximo passo.

### Trigger

Epic com `phase=review_done`. O RECONCILE e ativado quando a implementacao foi revisada e aprovada.

### Fluxo

1. Pipeline runner detecta que epic esta em `phase=review_done`
2. Le o PR diff e compara contra modelo LikeC4 + docs de engineering
3. Calcula `drift_score` (0.0 = perfeita aderencia, 1.0 = divergencia total)
4. **Se drift < 0.3**: auto-update dos Vision artifacts (executa `vision-build.py`, atualiza AUTO markers, cria commit no PR)
5. **Se drift >= 0.3**: escala para humano via notificacao WhatsApp com detalhes do drift

### Safety Gates (3 portoes)

1. **Skip se nao ha `platform_id`** — epic sem plataforma associada nao dispara reconcile
2. **Threshold check** — drift_score abaixo do limiar permite auto-update; acima escala
3. **1-way door check** — mudancas que alteram contratos publicos (API, eventos, schemas) sempre escalam, independente do drift_score

O reconcile roda de forma idempotente — se nao ha mudancas, nao cria commit vazio.

## Rabbit Holes

- **Nao tentar auto-update de arquivos LikeC4 (.likec4)** — o modelo LikeC4 e complexo demais para update automatico. RECONCILE atualiza apenas docs markdown via AUTO markers.
- **Nao tentar reconciliar docs que nao tem AUTO markers** — apenas docs que ja usam o sistema sao atualizados
- **Nao bloquear PR se reconcile falhar** — e WARNING, nao BLOCKER. O PR pode ser mergeado e reconcile feito manualmente
- **Nao reconciliar plataformas nao afetadas** — apenas a plataforma do epic em questao

## No-gos

- **Nao auto-update com drift >= 0.3** — divergencia significativa requer julgamento humano. O sistema escala, nao decide.
- **Nao modificar codigo fonte** — RECONCILE atualiza documentacao, nunca codigo. Se o codigo divergiu da arquitetura, e problema para o arquiteto resolver.
- **Nao inventar drift_score sofisticado na v1** — comece com heuristica simples (contagem de elementos novos/removidos vs total). Refinar depois com dados reais.

## Criterios de Aceitacao

- [ ] Fase RECONCILE dispara automaticamente quando epic atinge `phase=review_done`
- [ ] 3 safety gates implementados: skip sem `platform_id`, threshold check, 1-way door check
- [ ] drift_score calculado corretamente a partir do diff vs modelo arquitetural
- [ ] Auto-update de Vision artifacts quando drift < 0.3
- [ ] Escalacao para humano via WhatsApp quando drift >= 0.3
- [ ] Apenas docs markdown atualizados (nunca arquivos .likec4)
- [ ] Commit "docs: reconcile vision after implementation" aparece no PR quando ha mudancas
- [ ] Nenhum commit vazio quando nao ha mudancas
- [ ] Pipeline nao falha se reconcile falhar (graceful degradation)
