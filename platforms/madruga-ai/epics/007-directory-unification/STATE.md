# STATE — Epic 007: Directory Unification

**Session**: 2026-03-29
**Branch**: `003-directory-unification`

## Completed

### Phase 1: Setup/Migration (3/3)
- [x] T001 — Movido `specs/001-atomic-skills-dag-pipeline/` → `epics/005-atomic-skills-dag/`
- [x] T002 — Movido `specs/002-sqlite-foundation/` → `epics/006-sqlite-foundation/`
- [x] T003 — Verificado git log --follow

### Phase 2: Foundational — `--base-dir` (9/9)
- [x] T006-T008 — Testes escritos em `.specify/scripts/bash/tests/test_base_dir.sh`
- [x] T009-T010 — `SPECIFY_BASE_DIR` env var em `common.sh` (find_feature_dir_by_prefix + get_feature_paths)
- [x] T011 — `--base-dir` flag em `create-new-feature.sh`
- [x] T012 — `--base-dir` flag em `setup-plan.sh`
- [x] T013 — `--base-dir` flag em `check-prerequisites.sh`
- [x] T014 — Testes rodados: 4/4 PASS

### Phase 3: Skill Renaming (parcial — 4/9)
- [x] T015 — Renomeado `vision-one-pager.md` → `vision.md` (git mv + refs internas)
- [x] T016 — Renomeado `discuss.md` → `epic-context.md` (git mv + refs internas)
- [x] T017 — Renomeado `adr-gen.md` → `adr.md` (git mv + refs internas)
- [x] T018 — Renomeado `test-ai.md` → `qa.md` (git mv + refs internas)
- [ ] T019-T023 — Atualizar referências em CLAUDE.md, knowledge, platform.yaml, templates

### Phase 4: Merge folder-arch (parcial — 5/8)
- [x] T024-T025 — Seção "Folder Structure" adicionada ao blueprint template
- [x] T026 — Deletado `folder-arch.md` skill
- [x] T027 — Deletado `folder-structure.md.jinja` template
- [x] T028-T029 — Removido nó `folder-arch` de `platform.yaml` e template Copier
- [ ] T030-T031 — Atualizar DAG knowledge e CLAUDE.md (14→13 nós)

**Total**: 12 tasks completas / 82 total (15%)

## Decisions Made

1. `epic_nodes` table já existe em 001_initial.sql — nenhuma nova migration necessária (research R1)
2. `SPECIFY_BASE_DIR` env var como mecanismo de override em `common.sh` (research R2)
3. Quando `SPECIFY_BASE_DIR` setado, bypass de prefix matching — retorna path diretamente (research R3)
4. `folder-structure.md.jinja` absorvido como seção §5 no blueprint template
5. Renaming atômico de 4 skills via git mv + edição de refs internas

## Issues and Solutions

1. **Agents de rename não podiam editar** — Agentes rodaram `git mv` mas não tinham permissão de Edit. Corrigido manualmente após agentes retornarem.
2. **`qa.md` ainda tinha referências a `test-ai`** — Agente renomeou arquivo mas não atualizou todas as refs internas. Corrigido com `replace_all`.
3. **`folder-structure.md` não existia no live platform** — Arquivo nunca foi gerado para madruga-ai. Apenas o template Copier existia. Absorvido no blueprint template sem necessidade de migrar conteúdo live.

## Next Steps

### Fase 3 (completar — T019-T023)
- Atualizar CLAUDE.md com novos nomes de skills
- Atualizar pipeline-dag-knowledge.md (DAG 14→13 nós, nomes atualizados)
- Atualizar skill names em platform.yaml e template Copier
- Grep de validação final

### Fase 5: US1 — SpecKit no epic dir (T032-T037)
- Atualizar prompts dos 6 skills SpecKit para exportar `SPECIFY_BASE_DIR`

### Fase 6: US8 — epic_cycle no Copier (T038-T042)
- Adicionar `epic_cycle` section ao template e manifesto live

### Fase 7: US4 — `--epic` flag (T043-T047)
- Implementar `--epic` em check-platform-prerequisites.sh

### Fase 8: US5 — HANDOFF blocks (T048-T063)
- Adicionar handoff_template ao DAG knowledge + HANDOFF blocks em 14 skills

### Fase 9: US2 — `/pipeline` unificado (T064-T070)
- Criar skill pipeline.md, deletar pipeline-status.md e pipeline-next.md

### Fase 10-11: Cleanup + Polish (T071-T082)
- Mover specs/003 → epics/007, deletar specs/, validação final

## Changed Files

### Staged (git mv)
- `.claude/commands/madruga/adr-gen.md` → `adr.md`
- `.claude/commands/madruga/discuss.md` → `epic-context.md`
- `.claude/commands/madruga/test-ai.md` → `qa.md`
- `.claude/commands/madruga/vision-one-pager.md` → `vision.md`
- `specs/001-*` → `platforms/madruga-ai/epics/005-atomic-skills-dag/`
- `specs/002-*` → `platforms/madruga-ai/epics/006-sqlite-foundation/`

### Modified
- `.specify/scripts/bash/common.sh` — `SPECIFY_BASE_DIR` support
- `.specify/scripts/bash/create-new-feature.sh` — `--base-dir` flag
- `.specify/scripts/bash/setup-plan.sh` — `--base-dir` flag
- `.specify/scripts/bash/check-prerequisites.sh` — `--base-dir` flag
- `.specify/templates/platform/template/engineering/blueprint.md.jinja` — §5 Folder Structure
- `platforms/madruga-ai/platform.yaml` — folder-arch node removed
- `.specify/templates/platform/template/platform.yaml.jinja` — folder-arch node removed

### Created
- `.specify/scripts/bash/tests/test_base_dir.sh` — testes para --base-dir
- `specs/003-directory-unification/` — spec, plan, tasks, research, data-model, context, checklists

### Deleted
- `.claude/commands/madruga/folder-arch.md`
- `.specify/templates/platform/template/engineering/folder-structure.md.jinja`
