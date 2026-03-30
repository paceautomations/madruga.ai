---
title: "Tasks — Epic 010"
updated: 2026-03-30
---
# Epic 010 — Pipeline Dashboard — Tasks

## Fase 1: Setup

- [ ] **T001**: Criar `portal/src/data/.gitignore` com `pipeline-status.json`
- [ ] **T002**: Instalar `@xyflow/react` e `elkjs` no portal (`npm install`)
- [ ] **T003**: Adicionar scripts `predev` e `prebuild` no `portal/package.json` com fallback para JSON vazio

## Fase 2: CLI Status Command (US1 — P1)

- [ ] **T004**: Adicionar `cmd_status()` em `.specify/scripts/platform.py` — single platform, output tabela humana
  - Query `get_pipeline_nodes()` + merge `platform.yaml` para `layer`, `gate`, `depends`, `optional`
  - Tabela: `node_id | status | layer | gate`
  - Mostrar progress summary: `Done: X/Y (Z%)`
- [ ] **T005**: Adicionar flag `--all` em `cmd_status()` — loop por todas as plataformas via `_discover_platforms()`
- [ ] **T006**: Adicionar flag `--json` em `cmd_status()` — output JSON no stdout conforme contract do plan.md
  - Incluir `generated_at`, plataformas com metadados, nós L1, epics L2 com nós
  - Usar `json.dumps(ensure_ascii=False, indent=2)`
- [ ] **T007**: Wiring — adicionar case `"status"` no `main()` de platform.py com parsing de `--all` e `--json`
- [ ] **T008**: Criar testes em `.specify/scripts/tests/test_status.py`
  - Test: single platform table output
  - Test: --all flag
  - Test: --json output é JSON válido com schema correto
  - Test: plataforma inexistente → exit code 1
  - Test: DB vazio → mensagem graceful

## Fase 3: Portal Dashboard + Heatmap (US2 — P2)

- [ ] **T009**: Criar `portal/src/pages/dashboard.astro` usando pattern StarlightPage
  - Importar `pipeline-status.json` como módulo estático
  - Seção 1: Heatmap Platform×Node (tabela HTML)
  - Seção 2: placeholder para DAG (React island)
  - Seção 3: placeholder para Burndown (Mermaid)
- [ ] **T010**: Implementar heatmap como tabela HTML com CSS
  - Linhas: plataformas, Colunas: nós L1
  - Células coloridas via classes CSS: `status-done`, `status-pending`, `status-blocked`, `status-skipped`, `status-stale`
  - Coluna final: progress bar ou percentual
  - Suporte dark mode via CSS custom properties do Starlight
  - Empty state: "Nenhuma plataforma encontrada"

## Fase 4: DAG Interativo (US3 — P3)

- [ ] **T011**: Criar `portal/src/components/dashboard/PipelineDAG.tsx` — estrutura base
  - Props interface: `{ platforms: Platform[] }`
  - State: `selectedPlatform`, `showL2`
  - ErrorBoundary + Suspense (pattern de LikeC4Diagram.tsx)
- [ ] **T012**: Implementar conversão dados → ELK graph → React Flow nodes/edges
  - Converter `PipelineNode[]` para ELK `children[]` e `edges[]`
  - Layout options: `elk.algorithm: layered`, `elk.direction: DOWN`, spacing 40/60
  - Após ELK layout, mapear posições para React Flow `Node[]`
- [ ] **T013**: Implementar custom node component `PipelineNodeComponent`
  - Background colorido por status (STATUS_COLORS do plan.md)
  - Label: node id
  - Badge: layer (business/research/engineering/planning)
  - Indicador visual para nós opcionais
  - Handles: top (target) e bottom (source)
- [ ] **T014**: Implementar click-to-navigate
  - onClick: construir URL a partir de `outputs[0]` — remover `.md`, prepend `/<platform>/`
  - Usar `window.location.href` para navegação
- [ ] **T015**: Implementar filtro por plataforma (dropdown) e toggle L1/L2
  - Dropdown com todas as plataformas + opção "Todas"
  - Toggle checkbox "Mostrar ciclo L2"
  - Quando L2 ativo, adicionar nós do epic_cycle conectados ao nó `epic-breakdown`
- [ ] **T016**: Integrar PipelineDAG no `dashboard.astro` como React island com `client:load`
  - Passar dados do JSON como props
  - Container com height fixa (600px) e overflow

## Fase 5: Burndown (US4 — P4)

- [ ] **T017**: Gerar Mermaid Gantt syntax no `dashboard.astro` server-side
  - Para cada epic com ≥2 nós completados (com `completed_at`)
  - Format: `task_name :done, YYYY-MM-DD, 1d`
  - Nós sem `completed_at` ficam como `:active` ou omitidos
- [ ] **T018**: Renderizar Gantt via astro-mermaid com empty state
  - Se epic tem <2 eventos: "Sem dados históricos para este epic"
  - Se nenhum epic tem dados: omitir seção burndown inteira

## Fase 6: Polish

- [ ] **T019**: Verificar SSG build < 30s (`cd portal && time npm run build`)
- [ ] **T020**: Testar edge cases: DB vazio, 0 plataformas, plataforma sem epics, nós stale, nós opcionais
- [ ] **T021**: Rodar `pytest .specify/scripts/tests/ -v` — todos os testes devem passar

## Dependências entre Tasks

```
T001, T002, T003 (paralelo)
    ↓
T004 → T005 → T006 → T007 → T008
    ↓
T009 → T010
    ↓
T011 → T012 → T013 → T014 → T015 → T016
    ↓
T017 → T018
    ↓
T019, T020, T021 (paralelo)
```

---
handoff:
  from: tasks
  to: analyze
  context: "21 tasks em 6 fases. Fase 2 (CLI) é MVP independente. Fases 3-5 dependem de T003 (build integration)."
  blockers: []
