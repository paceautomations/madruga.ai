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

Unificar as 9 skills speckit e as 4 skills de arquitetura sob namespace unico `madruga.*`:

1. **Atualizar referencias primeiro** (antes de renomear arquivos):
   - CLAUDE.md — atualizar toda a secao SpecKit Workflow
   - README.md — atualizar referencias ao namespace
   - Todos os skills que referenciam outros skills internamente
   - SpeckitBridge — atualizar para ler skills dos novos paths `madruga.*`

2. **Renomear skills em `.claude/commands/`** (via migration script):
   - `speckit.specify.md` → `madruga.specify.md`
   - `speckit.plan.md` → `madruga.plan.md`
   - `speckit.tasks.md` → `madruga.tasks.md`
   - `speckit.clarify.md` → `madruga.clarify.md`
   - `speckit.analyze.md` → `madruga.analyze.md`
   - `speckit.implement.md` → `madruga.implement.md`
   - `speckit.taskstoissues.md` → `madruga.taskstoissues.md`
   - `speckit.constitution.md` → `madruga.constitution.md`
   - `speckit.checklist.md` → `madruga.checklist.md`

3. **Renomear templates em `.specify/templates/`**:
   - Manter estrutura interna, apenas prefixo externo muda

4. **Manter backward compatibility temporaria**:
   - Symlinks `speckit.* → madruga.*` por 30 dias
   - Warning no stderr quando skill antiga e invocada

## Rabbit Holes

- **Nao renomear arquivos em disco antes de atualizar todas as referencias** — primeiro atualizar CLAUDE.md, skills que referenciam outros skills, SpeckitBridge config. Depois renomear arquivos. Usar migration script, nao rename manual.
- **Nao renomear internals do SpeckitBridge** — nomes internos (classes, funcoes) podem ficar como estao. O rename e apenas na interface publica (nomes de skills). SpeckitBridge precisa ser atualizado para ler dos novos paths.
- **Nao renomear `.specify/` directory** — e o diretorio de templates, nao o namespace publico. Manter.
- **Nao fazer rename parcial** — ou renomeia tudo de uma vez, ou nao faz. Namespace misto e pior que dois namespaces.

## No-gos

- **Nao mudar comportamento de nenhuma skill** — e rename puro. Se uma skill faz X antes, faz X depois. Zero mudancas funcionais.
- **Nao remover symlinks de backward compatibility antes de 30 dias** — usuarios e automacoes precisam de tempo para migrar.
- **Nao renomear o diretorio `.specify/`** — e infraestrutura interna, nao faz parte do namespace publico que usuarios veem.

## Criterios de Aceitacao

- [ ] Todas as skills acessiveis via `/madruga.*`
- [ ] Symlinks backward-compatible para `/speckit.*` funcionando
- [ ] Warning emitido quando skill antiga e usada
- [ ] CLAUDE.md atualizado com namespace unificado
- [ ] Nenhuma skill quebrada apos rename (teste: executar cada skill 1x)
- [ ] SpeckitBridge encontra skills no novo path
