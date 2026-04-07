# Research: Directory Unification

## R1. epic_nodes table — already exists

**Decision**: Nenhuma nova migration necessária.
**Rationale**: `001_initial.sql` já criou `epic_nodes` com schema completo (platform_id, epic_id, node_id, status, output_hash, completed_at, completed_by). `db.py` já tem `upsert_epic_node()`, `get_epic_nodes()`, `get_epic_status()`.
**Alternatives considered**: Nova migration `002_epic_cycle_nodes.sql` — descartada pois a tabela já existe com o schema necessário. Renomear para `epic_cycle_nodes` — overhead desnecessário, `epic_nodes` é suficientemente claro.

## R2. `--base-dir` approach — env var vs flag

**Decision**: Flag `--base-dir <path>` nos scripts + env var `SPECIFY_BASE_DIR` como override em `common.sh`.
**Rationale**: Flag é explícita (preferível para scripts). Env var é útil para skills que chamam múltiplos scripts em sequência sem repetir a flag.
**Alternatives considered**: Apenas flag (sem env var) — operador teria que passar `--base-dir` em cada invocação. Apenas env var — menos visível, fácil esquecer de setar.

## R3. `find_feature_dir_by_prefix` with `--base-dir`

**Decision**: Quando `SPECIFY_BASE_DIR` é setado, `find_feature_dir_by_prefix` retorna `$base_dir` diretamente sem prefix matching.
**Rationale**: No modo epic dir, o path completo já é conhecido (ex: `platforms/prosauai/epics/001-channel-pipeline/`). Prefix matching é desnecessário e potencialmente incorreto (branch name não corresponde a epic dir name).
**Alternatives considered**: Aplicar prefix matching dentro do epic dir — complicação desnecessária, pois epic dirs já têm naming definido por `epic-breakdown`.

## R4. Copier `_skip_if_exists` for epic_cycle

**Decision**: `epic_cycle` não precisa de `_skip_if_exists` porque vive dentro de `platform.yaml`, que já é `_skip_if_exists`.
**Rationale**: O arquivo inteiro é protegido. `copier update` não sobrescreve `platform.yaml` existente. Operador adiciona `epic_cycle` manualmente ou via script.
**Alternatives considered**: Arquivo separado `epic_cycle.yaml` — fragmentação desnecessária, viola single-manifest principle.

## R5. Mermaid dynamic color mapping

**Decision**: Mapear status→class CSS no Mermaid: done→green, in-progress→yellow, pending→gray, blocked→red, skipped→lightgray, stale→orange.
**Rationale**: Padrão visual reconhecível universalmente (semáforo).
**Alternatives considered**: Apenas tabela sem diagrama — perde visão de dependências. ASCII art — não renderiza no portal Starlight.

## R6. Mapping specs/ → epics/

**Decision**: `specs/001-atomic-skills-dag-pipeline/` → `platforms/madruga-ai/epics/005-atomic-skills-dag/`, `specs/002-sqlite-foundation/` → `platforms/madruga-ai/epics/006-sqlite-foundation/`.
**Rationale**: Epic 005 = atomic skills dag (confirmado pelo roadmap/pitch). Epic 006 = sqlite foundation (confirmado). Mapeamento 1:1.
**Alternatives considered**: Manter numbering original (001, 002) — conflitaria com epic numbering existente em `epics/`.
