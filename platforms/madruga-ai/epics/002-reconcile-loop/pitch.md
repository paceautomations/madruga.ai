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

Adicionar fase RECONCILE como ultimo step do pipeline, apos IMPLEMENT:

1. Pipeline runner detecta que IMPLEMENT concluiu com sucesso
2. Executa `likec4 export json` para gerar JSON atualizado
3. Executa `vision-build.py <platform>` para re-popular AUTO markers
4. Se houve mudancas nos docs, cria commit adicional no PR: "docs: reconcile vision after implementation"
5. Se `--validate-only` falhar (markers inconsistentes), notifica via WhatsApp como WARNING

O reconcile roda de forma idempotente — se nao ha mudancas, nao cria commit vazio.

## Rabbit Holes

- **Nao tentar reconciliar docs que nao tem AUTO markers** — apenas docs que ja usam o sistema sao atualizados
- **Nao bloquear PR se reconcile falhar** — e WARNING, nao BLOCKER. O PR pode ser mergeado e reconcile feito manualmente
- **Nao reconciliar plataformas nao afetadas** — apenas a plataforma do epic em questao

## Criterios de Aceitacao

- [ ] Fase RECONCILE executa automaticamente apos IMPLEMENT bem-sucedido
- [ ] `vision-build.py` roda e popula AUTO markers corretamente
- [ ] Commit "docs: reconcile" aparece no PR quando ha mudancas
- [ ] Nenhum commit vazio quando nao ha mudancas
- [ ] WARNING enviado via WhatsApp se `--validate-only` falhar
- [ ] Pipeline nao falha se reconcile falhar (graceful degradation)
