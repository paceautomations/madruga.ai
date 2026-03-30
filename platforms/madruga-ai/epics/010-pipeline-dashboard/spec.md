# Feature Specification: Pipeline Dashboard

**Feature Branch**: `epic/madruga-ai/010-pipeline-dashboard`
**Created**: 2026-03-30
**Status**: Draft
**Input**: User description: "Dashboard visual no portal Starlight para acompanhar pipeline L1+L2 de todas as plataformas"

## User Scenarios & Testing

### User Story 1 — CLI Status Export (Priority: P1)

Como desenvolvedor, quero rodar `platform.py status` no terminal e ver o progresso de cada plataforma no pipeline — tanto em formato tabela (humano) quanto JSON (máquina) — para alimentar dashboards e scripts de automação.

**Why this priority**: É o MVP e a fundação de tudo. Sem o export JSON, não há dados para o portal. Entrega valor imediato no terminal antes de qualquer UI.

**Independent Test**: Pode ser testado 100% via CLI, sem portal: `python3 .specify/scripts/platform.py status fulano` imprime tabela; `status --all --json` retorna JSON válido.

**Acceptance Scenarios**:

1. **Given** plataforma "fulano" existe no DB com 7/13 nós done, **When** rodo `platform.py status fulano`, **Then** vejo tabela com 13 linhas mostrando node_id, status, layer, gate para cada nó L1.
2. **Given** 2 plataformas existem, **When** rodo `platform.py status --all`, **Then** vejo tabelas para ambas as plataformas com progress summary.
3. **Given** 2 plataformas existem, **When** rodo `platform.py status --all --json`, **Then** recebo JSON válido no stdout com array `platforms[]`, cada uma com `l1.nodes[]` e `l2.epics[].nodes[]`.
4. **Given** plataforma tem epics com nós L2 registrados, **When** rodo `status <name> --json`, **Then** JSON inclui seção `l2` com status de cada epic e seus nós.
5. **Given** plataforma "xyz" não existe, **When** rodo `platform.py status xyz`, **Then** vejo mensagem de erro e exit code 1.
6. **Given** DB não existe ou está vazio, **When** rodo `platform.py status --all`, **Then** vejo mensagem "Nenhuma plataforma encontrada" (não crash).

---

### User Story 2 — Heatmap de Progresso por Plataforma (Priority: P2)

Como arquiteto, quero acessar `/dashboard` no portal e ver um heatmap colorido mostrando o status de cada nó do pipeline para cada plataforma — verde (done), amarelo (pending), vermelho (blocked), cinza (skipped), laranja (stale) — para ter visão instantânea do progresso geral.

**Why this priority**: É a visualização mais valiosa com menor complexidade. Uma tabela HTML com cores comunica o estado de N plataformas em um olhar.

**Independent Test**: Navegar para `http://localhost:4321/dashboard/` e verificar que a tabela renderiza com cores corretas para cada célula.

**Acceptance Scenarios**:

1. **Given** portal buildado com dados de 2 plataformas, **When** acesso `/dashboard`, **Then** vejo tabela com linhas por plataforma e colunas por nó L1, cada célula colorida por status.
2. **Given** nó "vision" está done e "containers" está pending, **When** vejo o heatmap, **Then** "vision" está verde e "containers" está amarelo.
3. **Given** nenhuma plataforma existe, **When** acesso `/dashboard`, **Then** vejo mensagem "Nenhuma plataforma encontrada" em vez de tabela vazia.
4. **Given** plataforma tem nós stale (dependência completou depois), **When** vejo o heatmap, **Then** nó stale aparece em laranja.

---

### User Story 3 — DAG Interativo do Pipeline (Priority: P3)

Como desenvolvedor, quero ver o pipeline como um grafo dirigido interativo na página `/dashboard` — com nós coloridos por status, edges mostrando dependências, e click para navegar ao artefato — para entender o fluxo de trabalho e identificar gargalos.

**Why this priority**: Complementa o heatmap com a dimensão de dependências. O heatmap mostra "o quê", o DAG mostra "por quê" (qual nó bloqueia qual).

**Independent Test**: Na página `/dashboard`, o DAG renderiza com layout hierárquico, nós têm cores corretas, clicar em um nó navega para a página do artefato no portal.

**Acceptance Scenarios**:

1. **Given** portal buildado com dados L1 de "fulano", **When** vejo o DAG, **Then** 13 nós aparecem com edges corretos (ex: vision → solution-overview, blueprint → domain-model).
2. **Given** nó "domain-model" está done, **When** clico nele no DAG, **Then** sou redirecionado para `/fulano/engineering/domain-model/`.
3. **Given** 2 plataformas existem, **When** uso o dropdown de filtro, **Then** o DAG mostra apenas os nós da plataforma selecionada.
4. **Given** plataforma tem epics com nós L2, **When** ativo o toggle "Mostrar L2", **Then** o DAG expande para incluir nós do ciclo L2 conectados ao nó `epic-breakdown`.
5. **Given** nó tem status "blocked", **When** vejo o DAG, **Then** nó aparece em vermelho com tooltip mostrando dependências faltantes.

---

### User Story 4 — Burndown por Epic (Priority: P4)

Como desenvolvedor, quero ver um gráfico Gantt mostrando o progresso de cada epic ao longo do tempo — nós completados vs. tempo — para acompanhar a velocidade de entrega.

**Why this priority**: Complementar. Só faz sentido quando há dados históricos no DB (events table). Menor valor imediato mas útil para retrospectivas.

**Independent Test**: Na página `/dashboard`, abaixo do DAG, vejo gráficos Mermaid Gantt para cada epic que tenha ≥2 eventos registrados.

**Acceptance Scenarios**:

1. **Given** epic "009-decision-log-bd" tem 5 nós completados com timestamps, **When** vejo a seção burndown, **Then** gráfico Gantt mostra barras para cada nó completado na timeline correta.
2. **Given** epic "001-channel-pipeline" não tem nenhum evento, **When** vejo a seção burndown, **Then** vejo mensagem "Sem dados históricos para este epic" em vez de Gantt vazio.
3. **Given** epic tem todos os 11 nós completados, **When** vejo o Gantt, **Then** todas as barras estão preenchidas e epic marcado como "Completo".

---

### Edge Cases

- O que acontece quando o `pipeline-status.json` não existe no build? Portal exibe estado vazio sem quebrar o build.
- O que acontece quando uma plataforma tem `pipeline.nodes` no YAML mas nenhum registro no DB? Mostra todos como "pending".
- O que acontece com nós opcionais (ex: `codebase-map` com `optional: true`)? Aparecem no heatmap/DAG mas com indicador visual de "opcional".
- O que acontece com caracteres especiais no título da plataforma (acentos, emojis)? JSON escapa corretamente via `json.dumps(ensure_ascii=False)`.
- O que acontece com plataformas que não têm `epic_cycle` no YAML? Seção L2 omitida, apenas L1 mostrado.

## Requirements

### Functional Requirements

- **FR-001**: Sistema DEVE oferecer comando `platform.py status <name>` que exibe tabela com node_id, status, layer, gate para todos os nós L1 da plataforma.
- **FR-002**: Sistema DEVE oferecer flag `--all` que exibe status de todas as plataformas descobertas.
- **FR-003**: Sistema DEVE oferecer flag `--json` que retorna dados em formato JSON no stdout com schema documentado.
- **FR-004**: Output JSON DEVE incluir timestamp de geração (`generated_at`), array de plataformas com metadados (id, title, lifecycle) e nós L1/L2 com status.
- **FR-005**: Portal DEVE ter página acessível em `/dashboard` que renderiza dados de pipeline de todas as plataformas.
- **FR-006**: Dashboard DEVE exibir heatmap Platform×Node como tabela HTML com células coloridas por status (5 cores: done, pending, blocked, skipped, stale).
- **FR-007**: Dashboard DEVE exibir DAG interativo com nós coloridos por status e edges representando dependências entre nós.
- **FR-008**: Nós do DAG DEVEM ser clicáveis, navegando para a página do artefato correspondente no portal.
- **FR-009**: Dashboard DEVE oferecer dropdown para filtrar por plataforma e toggle para mostrar/ocultar nós L2.
- **FR-010**: Dashboard DEVE exibir gráficos Gantt (Mermaid) para epics com ≥2 eventos históricos.
- **FR-011**: Dashboard DEVE mostrar estados vazios graceful quando não há plataformas, não há epics, ou não há dados históricos.
- **FR-012**: Dados do dashboard DEVEM ser gerados em build-time via script npm (`prebuild`/`predev`), sem necessidade de API runtime.

### Key Entities

- **PipelineStatus**: Snapshot completo do estado de todas as plataformas — inclui plataformas[], cada uma com nós L1 e epics L2 com seus nós.
- **PipelineNode**: Um nó do pipeline com id, status (done/pending/blocked/skipped/stale), layer, gate, depends[], e link para artefato.
- **EpicProgress**: Um epic com id, title, nós L2 com status, e eventos históricos para burndown.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Desenvolvedor consegue visualizar o progresso de qualquer plataforma em menos de 5 segundos (via CLI ou portal).
- **SC-002**: Dashboard mostra o estado correto de 100% dos nós do pipeline (zero divergência entre DB e visualização).
- **SC-003**: Portal build completa em menos de 30 segundos com o dashboard incluído (NFR Q4 do blueprint).
- **SC-004**: Nenhuma página existente do portal tem degradação de performance (island isolation).
- **SC-005**: Desenvolvedor identifica o próximo passo do pipeline em menos de 10 segundos olhando o dashboard (via heatmap ou DAG).

## Assumptions

- SQLite DB (`.pipeline/madruga.db`) existe e contém dados de pelo menos 1 plataforma (seed via `post_save.py --reseed-all`).
- Python 3.11+ está disponível no ambiente de build do portal (necessário para `prebuild` script).
- Portal já tem React integration configurada (confirmado em `astro.config.mjs` via `react()`).
- `astro-mermaid` já está no bundle do portal (confirmado em `package.json`).
- Nós do pipeline têm campo `depends` derivável do `platform.yaml` (não armazenado diretamente no DB — o CLI export faz o merge).
- O dashboard não precisa de dados real-time — build-time refresh é suficiente (dados mudam 1-2x/dia).

---
handoff:
  from: specify
  to: clarify
  context: "Spec completa com 4 user stories, 12 FRs, 5 SCs. Verificar se há clarificações necessárias antes de plan."
  blockers: []
