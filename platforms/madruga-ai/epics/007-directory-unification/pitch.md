---
id: 007
title: "Directory Unification — SpecKit Opera em epics/, DAG Dois Níveis"
status: proposed
phase: pitch
appetite: small-batch
priority: now
---
# Directory Unification — SpecKit Opera em epics/, DAG Dois Níveis

## Problema

SpecKit e Madruga operam em diretórios separados: SpecKit cria artifacts em `specs/<NNN>/` enquanto Madruga gera pitch.md e context.md em `platforms/<name>/epics/<NNN>/`. Isso causa:

1. **Dois mundos** — spec.md, plan.md, tasks.md vivem em `specs/` enquanto pitch.md, context.md, verify-report.md vivem em `epics/`. Sem lineage unificado
2. **DAG incompleto** — 10 skills do ciclo per-epic (epic-context, specify, plan, tasks, analyze, implement, verify, qa, reconcile) não são nós do DAG. Zero observabilidade per-epic
3. **Nomes confusos** — discuss, adr-gen, test-ai, vision-one-pager, folder-arch são nomes vagos ou inconsistentes
4. **Pipeline fragmentado** — pipeline-status e pipeline-next são 2 skills separadas que fazem o mesmo. Não cobrem per-epic
5. **Sem HANDOFF blocks** — context entre skills se perde. Decisions não propagam

## Appetite

1-2 semanas (small batch). Ajustes cirúrgicos em scripts + renaming + HANDOFF + /pipeline unificado.

## Solução

1. **Scripts SpecKit ganham `--base-dir`** — `create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh` aceitam path customizado (default: `specs/`, novo: `platforms/<name>/epics/<NNN>/`)
2. **`epic_cycle` no Copier template** — `platform.yaml.jinja` ganha seção com 10 nós do ciclo per-epic
3. **`--epic` flag** no `check-platform-prerequisites.sh` para checar nós do epic cycle no BD
4. **Rename skills** — discuss→epic-context, adr-gen→adr, test-ai→qa, vision-one-pager→vision
5. **Merge folder-arch em blueprint** — eliminar skill, absorver como seção
6. **HANDOFF blocks** — template no contrato base, todas skills incluem bloco YAML no artefato
7. **`/pipeline` unificado** — merge status+next em uma skill, lê SQLite para ambos DAG levels
8. **Migrar artifacts** — mover specs/002-sqlite-foundation/ para epics/006-sqlite-foundation/

## Rabbit Holes

- NÃO reescrever lógica interna do SpecKit (specify, plan, tasks, implement permanecem)
- NÃO implementar knowledge files em camadas (epic 008)
- NÃO implementar auto-review tiered (epic 008)
- NÃO adicionar elements/relationships ao BD (fase futura)

## Acceptance Criteria

1. `create-new-feature.sh --base-dir platforms/fulano/epics/001-test` cria spec.md no epic dir
2. `platform.yaml` gerado pelo Copier tem seção `epic_cycle` com 10 nós
3. `check-platform-prerequisites.sh --json --platform fulano --epic 001 --use-db` retorna status do epic cycle
4. `discuss.md` não existe; `epic-context.md` existe e funciona
5. `folder-arch.md` não existe; `blueprint.md` inclui seção Folder Structure
6. `/pipeline madruga-ai` mostra DAG nível 1 + progresso per-epic do BD
7. Todas skills com gate human têm HANDOFF block no template de output
