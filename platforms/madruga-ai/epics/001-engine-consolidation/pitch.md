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

Migrar o runtime engine (~10K LOC Python + 51 testes) de `general/services/madruga-ai/` para `madruga.ai/engine/` com a seguinte estrutura:

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

- **Nao refatorar durante a migracao** — mover primeiro, refatorar depois. O objetivo e plug-and-play: copiar os arquivos, ajustar paths de config, rodar testes. Refactors cosmeticos sao ok, mudancas estruturais nao.
- **Nao migrar dados do SQLite** — criar db novo, dados historicos ficam no repo antigo como arquivo morto
- **Nao mexer em systemd configs ainda** — fazer funcionar localmente primeiro, production deploy e fase 2

## No-gos

- **Nao reescrever o daemon** — o codebase tem ~10K LOC e 51 testes passando. Nao e hora de reescrever nada. Move first, refactor later.
- **Nao unificar dependencias** — se o engine usa versoes diferentes de libs, manter. Unificacao de deps e escopo separado.
- **Nao alterar a interface do SpeckitBridge** — ele ja le de `.claude/commands/` e `.specify/templates/`, que sao os mesmos paths no novo repo. Se a interface nao precisa mudar, nao mude.

## Criterios de Aceitacao

- [ ] `src/`, `tests/`, `prompts/`, `config.yaml`, `server.py`, `deploy/` migrados para `madruga.ai/engine/`
- [ ] Paths de config ajustados para nova localizacao
- [ ] `python engine/daemon.py` inicia o daemon sem erros
- [ ] Todos os 51 testes existentes passam no novo local
- [ ] SpeckitBridge le skills de `../.claude/commands/` e templates de `../.specify/templates/` corretamente
- [ ] Pipeline completo (specify → implement) executa com sucesso em pelo menos 1 epic
- [ ] Modelo LikeC4 atualizado reflete a nova estrutura
- [ ] Repo antigo (`general/services/madruga-ai`) marcado como deprecated com README apontando para novo local
