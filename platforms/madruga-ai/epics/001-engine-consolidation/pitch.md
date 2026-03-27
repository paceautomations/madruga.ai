---
id: 001
title: "Consolidar Runtime Engine no Repo madruga.ai"
status: proposed
phase: pitch
appetite: big-batch
priority: now
arch:
  modules: [daemonProcess, orchestratorSlots, pipelineRunner, kanbanPoller]
  contexts: [execution, integration]
  containers: [runtimeDaemon, orchestrator, pipelinePhases, speckitBridge]
---
# Consolidar Runtime Engine no Repo madruga.ai

## Problema

O runtime engine (daemon asyncio, orchestrator, pipeline runner) vive atualmente em `general/services/madruga-ai`, separado do repo principal `madruga.ai`. Isso causa:

1. **Drift constante** entre modelo arquitetural (LikeC4 no repo madruga.ai) e implementacao real (no repo general)
2. **Deploy fricionado** — mudancas no pipeline requerem coordenar 2 repos
3. **Skills desconectadas** — `.claude/commands/` no madruga.ai nao conseguem acessar o codigo do engine diretamente
4. **Testes fragmentados** — nao da para rodar integration tests que cruzem skills + engine
5. **Context rot acelerado** — LLMs precisam carregar 2 codebases, desperdicando context window

## Appetite

4-6 semanas (big batch). Envolve migrar codigo, reestruturar imports, atualizar systemd configs, validar que daemon funciona no novo local, e atualizar toda a documentacao.

## Solucao

Migrar o runtime engine para `madruga.ai/engine/` com a seguinte estrutura:

```
engine/
  daemon.py          # Entry point (asyncio main loop)
  orchestrator.py    # Slot-based scheduler
  pipeline/          # 7 fases como modulos Python
    specify.py
    clarify.py
    plan.py
    tasks.py
    implement.py
    reconcile.py
    analyze.py
  bridge.py          # SpeckitBridge compositor
  integrations/      # Adapters para externos
    obsidian.py
    whatsapp.py
    github.py
    claude.py
  db/                # SQLite models + migrations
    models.py
    migrations/
  config.py          # Settings (Pydantic)
```

O SpeckitBridge passa a ler skills e templates do mesmo repo (`../.claude/commands/` e `../.specify/templates/`), eliminando a necessidade de paths absolutos ou config externa.

## Rabbit Holes

- **Nao reescrever o daemon** — migrar codigo existente, nao recriar do zero. Refactors cosmeticos sao ok, mas o foco e mover, nao melhorar.
- **Nao migrar dados do SQLite** — criar db novo, dados historicos ficam no repo antigo como arquivo
- **Nao mexer em systemd configs ainda** — fazer funcionar localmente primeiro, production deploy e fase 2

## Criterios de Aceitacao

- [ ] Todo o codigo do engine vive em `madruga.ai/engine/`
- [ ] `python engine/daemon.py` inicia o daemon sem erros
- [ ] SpeckitBridge le skills de `../.claude/commands/` corretamente
- [ ] Pipeline completo (specify → implement) executa com sucesso em pelo menos 1 epic
- [ ] Modelo LikeC4 atualizado reflete a nova estrutura
- [ ] Repo antigo (`general/services/madruga-ai`) marcado como deprecated com README apontando para novo local
