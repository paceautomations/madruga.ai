---
id: 005
title: "Unificacao de Namespace speckit.* → madruga.*"
status: proposed
phase: pitch
appetite: small-batch
priority: later
arch:
  modules: [specifyPhase, planPhase, tasksPhase, clarifyEngine, analyzeEngine]
  contexts: [specification, documentation]
  containers: [speckitSkills, speckitBridge, copierTemplates]
---
# Unificacao de Namespace speckit.* em madruga.*

## Problema

O sistema tem dois namespaces que confundem usuarios e LLMs:

1. **speckit.\*** — skills do pipeline spec-to-code (specify, plan, tasks, clarify, analyze, etc.)
2. **madruga.\*** — skills de arquitetura (platform-new, architecture-portal, vision-one-pager, solution-overview)

Isso causa:
- **Confusao de naming** — usuario digita `/speckit.specify` mas pensa "madruga". Ou vice-versa.
- **Duas identidades** — o sistema e "Madruga AI", mas metade das skills se chamam "speckit"
- **Documentacao fragmentada** — README explica SpecKit como subsistema separado, quando na verdade e parte do Madruga
- **LLMs confusos** — ao sugerir skills, Claude precisa escolher entre dois prefixos para o mesmo sistema

## Appetite

1-2 semanas (small batch). E rename mecanico + atualizacao de docs. Nao ha mudanca de comportamento.

## Solucao

Unificar tudo sob namespace `madruga.*`:

1. Renomear skills em `.claude/commands/`:
   - `speckit.specify.md` → `madruga.specify.md`
   - `speckit.plan.md` → `madruga.plan.md`
   - `speckit.tasks.md` → `madruga.tasks.md`
   - `speckit.clarify.md` → `madruga.clarify.md`
   - `speckit.analyze.md` → `madruga.analyze.md`
   - `speckit.implement.md` → `madruga.implement.md`
   - `speckit.taskstoissues.md` → `madruga.taskstoissues.md`
   - `speckit.constitution.md` → `madruga.constitution.md`
   - `speckit.checklist.md` → `madruga.checklist.md`

2. Renomear templates em `.specify/templates/`:
   - Manter estrutura interna, apenas prefixo externo muda

3. Atualizar referencias:
   - CLAUDE.md
   - README.md
   - Todos os skills que referenciam outros skills
   - SpeckitBridge → MadrugaBridge (ou manter nome interno, so renomear skills)

4. Manter backward compatibility temporaria:
   - Symlinks `speckit.* → madruga.*` por 30 dias
   - Warning no stderr quando skill antiga e invocada

## Rabbit Holes

- **Nao renomear internals do SpeckitBridge** — nomes internos (classes, funcoes) podem ficar como estao. O rename e apenas na interface publica (nomes de skills)
- **Nao renomear `.specify/` directory** — e o diretorio de templates, nao o namespace publico. Manter.
- **Nao fazer rename parcial** — ou renomeia tudo de uma vez, ou nao faz. Namespace misto e pior que dois namespaces

## Criterios de Aceitacao

- [ ] Todas as skills acessiveis via `/madruga.*`
- [ ] Symlinks backward-compatible para `/speckit.*` funcionando
- [ ] Warning emitido quando skill antiga e usada
- [ ] CLAUDE.md atualizado com namespace unificado
- [ ] Nenhuma skill quebrada apos rename (teste: executar cada skill 1x)
- [ ] SpeckitBridge encontra skills no novo path
