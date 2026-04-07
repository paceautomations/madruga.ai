---
id: 010
title: "Pipeline Dashboard"
status: shipped
phase: pitch
appetite: 1w
priority: 5
delivered_at: 2026-03-30
updated: 2026-03-30
---
# Pipeline Dashboard

Dashboard visual no portal Starlight. CLI `status` com tabela + JSON. Mermaid DAG. Filtros por plataforma.



## Resumo

Dashboard visual no portal Starlight para acompanhar o pipeline L1+L2 de todas as plataformas. Composto por: (1) comando CLI `platform.py status --json` que exporta estado do SQLite, (2) página `/dashboard` no portal com heatmap Platform×Node, DAG interativo com `@xyflow/react`, e burndown por epic via Mermaid Gantt, (3) integração build-time via JSON estático.

## Captured Decisions

| # | Área | Decisão | Alternativa Rejeitada | Referência |
|---|------|---------|----------------------|------------|
| 1 | Portal framework | Dashboard como página no Starlight existente, não app separada | FastAPI dashboard (:8080) é para easter ops, não pipeline visibility | ADR-003 |
| 2 | Data source | SQLite → JSON export build-time (SSG), sem API runtime | SSR/API endpoint — pipeline muda ~1-2x/dia, não justifica live data | ADR-004, ADR-012 |
| 3 | Python deps | stdlib only (`sqlite3`, `json`, `pathlib`) para CLI export | Nenhuma lib externa considerada — padrão do repo | Blueprint §3.1 |
| 4 | Heatmap render | `@xyflow/react` — DAG interativo com nós clicáveis, status colorido | HTML table puro (descartado: queremos a versão robusta desde o início) | ADR-003 (React islands) |
| 5 | Burndown charts | Mermaid Gantt (já no bundle via `astro-mermaid`) | `recharts` — dep nova desnecessária, 11 nós por epic não justifica | ADR-003 |
| 6 | Data freshness | Build-time only — JSON gerado no `npm run build` | Real-time polling — overhead injustificado para dados que mudam 1-2x/dia | ADR-004 |
| 7 | Entrega | Epic único com 3 camadas internas (CLI → JSON → Portal) | 3 epics separados — overhead de gestão maior que o código | — |

## Resolved Gray Areas

### G1: Como o portal acessa dados do SQLite?

**Pergunta**: Starlight é SSG (Node.js). SQLite é acessado via Python. Como conectar?

**Resposta**: Pipeline de build em 2 etapas:
1. `python3 .specify/scripts/platform.py status --all --json > portal/src/data/pipeline-status.json`
2. Portal importa o JSON como módulo estático no build

**Justificativa**: Desacopla completamente Python ↔ Node.js. JSON é o contrato. Zero deps cruzadas.

### G2: Onde colocar a página de dashboard?

**Pergunta**: Rota `/dashboard` como página Starlight ou fora do content collection?

**Resposta**: `portal/src/pages/dashboard.astro` — página standalone fora do content collection. Dashboard não é documentação, é ferramenta. Fica no nav principal mas não na sidebar de plataformas.

**Justificativa**: Evita conflito com auto-discovery de plataformas (`platforms.mjs`). Páginas em `src/pages/` são rotas diretas no Astro.

### G3: Como disparar a geração do JSON?

**Pergunta**: Manual, npm script, ou Vite plugin?

**Resposta**: npm script composto — `"prebuild": "python3 ../.specify/scripts/platform.py status --all --json > src/data/pipeline-status.json"`. Também funciona com `predev` para desenvolvimento.

**Justificativa**: Padrão npm, sem mágica. Dev roda `npm run dev` e já tem dados frescos.

### G4: Burndown sem dados históricos

**Pergunta**: `events` table pode estar vazia para plataformas novas.

**Resposta**: Aceitar gracefully — mostrar "Sem dados históricos" em vez de chart vazio. Burndown só aparece quando há ≥2 eventos para o epic.

### G5: `@xyflow/react` — bundle size

**Pergunta**: Adicionamos ~150kb ao bundle. Aceitável?

**Resposta**: Sim. É um Astro island — carrega lazy, só na página `/dashboard`. Não afeta nenhuma outra página do portal. Performance do SSG das outras páginas permanece intacta.

## Applicable Constraints

| Constraint | Fonte | Impacto neste Epic |
|---|---|---|
| Python stdlib only | Blueprint §3.1 | CLI export usa apenas `sqlite3`, `json`, `pathlib` |
| SQLite WAL mode | ADR-012 | Leituras concorrentes OK — export não bloqueia writes |
| Portal SSG build < 30s | Blueprint NFR Q4 | JSON import é instantâneo, `@xyflow/react` island não afeta SSG |
| Zero overhead operacional | ADR-004 | Sem servidor, sem API, sem cron — tudo no build |
| Auto-discovery de plataformas | ADR-003 | Dashboard deve usar `discoverPlatforms()` existente |
| React islands via Astro | ADR-003 | `@xyflow/react` roda como island, client:load |

## Suggested Approach

### Camada 1 — CLI Export (`platform.py`)

Novo subcomando `status`:
```
python3 .specify/scripts/platform.py status prosauai          # 1 plataforma
python3 .specify/scripts/platform.py status --all           # todas (humano)
python3 .specify/scripts/platform.py status --all --json    # todas (máquina)
```

Output JSON:
```json
{
  "generated_at": "2026-03-30T12:00:00Z",
  "platforms": [
    {
      "id": "prosauai",
      "title": "ProsaUAI — Agentes WhatsApp",
      "lifecycle": "design",
      "l1": {
        "total": 13, "done": 7, "pending": 6, "progress_pct": 53.8,
        "nodes": [
          {"id": "platform-new", "status": "done", "layer": "business", "gate": "human", "depends": []},
          ...
        ]
      },
      "l2": {
        "epics": [
          {
            "id": "001-channel-pipeline", "title": "Channel Pipeline",
            "total": 11, "done": 0, "pending": 0, "progress_pct": 0,
            "nodes": [...]
          }
        ]
      }
    }
  ]
}
```

### Camada 2 — Portal Dashboard Page

`portal/src/pages/dashboard.astro`:
- Importa `pipeline-status.json` (build-time)
- Renderiza 3 seções:
  1. **Heatmap Platform×Node** — tabela HTML com cores por status
  2. **DAG interativo** — React island com `@xyflow/react`, nós coloridos por status, edges do `depends`, click abre artefato
  3. **Burndown por epic** — Mermaid Gantt com nós completados vs tempo

### Camada 3 — React DAG Component

`portal/src/components/dashboard/PipelineDAG.tsx`:
- Recebe `nodes[]` com status e `depends` (edges)
- Layout automático com `elkjs` (hierárquico top-down)
- Nós coloridos: verde (done), amarelo (pending), vermelho (blocked), cinza (skipped), laranja (stale)
- Click no nó → abre link para artefato no portal
- Filtro por plataforma (dropdown)
- Toggle L1/L2

### Integração Build

```json
{
  "scripts": {
    "predev": "python3 ../.specify/scripts/platform.py status --all --json > src/data/pipeline-status.json",
    "prebuild": "python3 ../.specify/scripts/platform.py status --all --json > src/data/pipeline-status.json"
  }
}
```

### Dependências Novas (portal)

| Package | Propósito | Bundle Impact |
|---|---|---|
| `@xyflow/react` | DAG interativo | ~150kb (island only) |
| `elkjs` | Layout automático do DAG | ~80kb (island only) |

Nenhuma dependência nova no Python.
