# De Files para DB-First: Evolucao do madruga.ai

Data: 2026-03-29
Status: Proposta (aguardando decisao)

---

## Contexto

O madruga.ai hoje armazena TODO o estado como arquivos markdown em git: plataformas, epics, ADRs, specs, modelos LikeC4. Isso funcionou ate agora (2 plataformas, 1 operador), mas cria friccao crescente:

- **Descobrir plataformas**: `fs.readdirSync` + parse YAML a cada render
- **Listar epics**: `glob('epics/*/pitch.md')` + parse frontmatter de cada arquivo
- **Status de um epic**: ler arquivo, parsear YAML frontmatter, extrair campo
- **Buscar "quais ADRs mencionam Redis?"**: `grep -r` no filesystem
- **Relacionar epic com ADR**: referencia manual em prose — sem vinculo estruturado
- **Tracking de custo/performance**: nao existe
- **Dashboard de progresso**: nao existe
- **Cross-platform queries**: scripts custom por query

## Pesquisa: Como os lideres resolvem isso

### Frameworks DB-backed (alta performance)

| Framework | Storage | Destaque |
|-----------|---------|----------|
| **Paperclip** (26K stars) | PostgreSQL | Multi-company, custo por agent/task/projeto, org charts |
| **Devin** (Cognition) | Proprietario cloud | Machine Snapshots, Notes persistentes, Session Insights. Goldman Sachs, Nubank |
| **StrongDM Attractor** | Specs + event stream | 3 pessoas -> 32K linhas de producao sem escrever codigo |
| **Backstage** (Spotify/CNCF) | PostgreSQL | Catalog-info YAML em git -> indexado no DB. Netflix, Spotify |
| **Gas Town** (Yegge) | SQLite/Dolt + Git | 20-30 Claude Code em paralelo. Migrando para Dolt (MySQL + Git semantics) |
| **OpenHands** (64K stars) | Event-sourced (RAM/disk) | Event log imutavel. 72% SWE-Bench |

### Frameworks file-only (limitados)

| Framework | Storage | Limitacao |
|-----------|---------|-----------|
| **SpecKit** (GitHub, 72K stars) | Markdown files | Sem DB, sem sessao, sem cross-project |
| **BMAD** | Markdown files | Agent-as-Code. Multi-domain WIP |
| **GSD** v1 | XML/Markdown | Specs + git como checkpoints |
| **Cursor Rules** | `.mdc` files | Sem task tracking |
| **Cline/Roo Code** | Memory Bank (6 .md files) | Reload completo a cada sessao |

### Tendencia clara

Os frameworks de **alta performance** sao todos DB-backed. Os file-only sao ferramentas individuais, nao plataformas de gestao. A industria converge para:

> **Git = source of truth para conteudo (prose, codigo, modelos)**
> **DB = source of truth para estado, metadados, relacoes, tracking**

## Alternativas avaliadas

### Caminho A: SQLite Materializado (descartado)

DB como cache/indice dos files. Git continua source of truth para tudo.

- **Pro**: zero migracao
- **Contra**: dual-source, rebuild constante, nao resolve o problema fundamental
- **Quem usa**: ninguem relevante (pattern de transicao)

### Caminho B: DB-First com Supabase (recomendado)

DB e a source of truth para estado e metadados. Files mantidos apenas para conteudo narrativo.

- **Pro**: queries poderosas, IDs unicos, tracking, grafo de relacoes, real-time, dashboard nativo
- **Contra**: migracao de mindset (files -> DB para metadados)
- **Quem usa**: Paperclip, Devin, Backstage, StrongDM

### Caminho C: Hybrid SQLite Shadow (descartado)

SQLite local como "shadow" dos files. Sync bidirecional.

- **Pro**: conservador, zero breaking change
- **Contra**: dual-source, complexidade de sync, SQLite single-writer, sem real-time, precisa de FastAPI wrapper
- **Quem usa**: Gas Town (e esta migrando para Dolt/MySQL)

## Decisao: Caminho B com Supabase

### Por que Supabase e nao SQLite

| Aspecto | SQLite | Supabase (Postgres) |
|---------|--------|---------------------|
| Queries | SQL basico | SQL completo + mais poderoso |
| Multi-user | Single-writer | Multi-writer, RLS, real-time |
| Infra | Zero | Managed (ja usamos para Fulano) |
| Real-time | Nao | Sim (subscriptions) |
| Auth | Nao | Sim (built-in) |
| API | Precisa FastAPI wrapper | REST + auto-gerado |
| Vectors/embeddings | Nao | pgvector (ja usado no Fulano) |
| Portal integration | Precisa wrapper | fetch direto do JS client |
| Experiencia do time | Nenhuma | **Ja usamos para Fulano** |

Argumento decisivo: ja temos Supabase rodando, ja pagamos, ja temos experiencia. Criar um schema `madruga` no mesmo projeto ou um projeto Supabase separado e trivial.

### Arquitetura proposta

```
Skills / CLI / platform.py
        │
        ▼
┌─────────────────────────────────┐
│   Supabase (PostgreSQL)         │
│                                 │
│   platforms ─┬─ epics           │
│              ├─ decisions       │
│              ├─ elements        │
│              ├─ relationships   │
│              └─ blueprint_data  │
│                                 │
│   pipeline_runs                 │
│   agent_runs                    │
│   events (append-only log)      │
│   tags (cross-reference)        │
└───────────┬─────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│   Portal (Astro + Starlight)    │
│   Lê metadata do Supabase      │
│   Lê conteudo prose do Git     │
│   Dashboard em real-time        │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│   Git (repositorio)             │
│                                 │
│   platforms/*/                  │
│     ├─ business/*.md    (prose) │
│     ├─ engineering/*.md (prose) │
│     ├─ epics/*/pitch.md (prose) │
│     ├─ decisions/*.md   (prose) │
│     └─ model/*.likec4   (model) │
└─────────────────────────────────┘
```

### Schema proposto

```sql
-- ══════════════════════════════════════
-- Core entities (source of truth no DB)
-- ══════════════════════════════════════

CREATE TABLE platforms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,        -- kebab-case: "fulano"
    title       TEXT NOT NULL,               -- "Fulano — Agentes WhatsApp"
    description TEXT,
    lifecycle   TEXT NOT NULL DEFAULT 'design'
                CHECK (lifecycle IN ('design', 'development', 'production', 'deprecated')),
    version     TEXT,
    repo_path   TEXT NOT NULL,               -- "platforms/fulano"
    metadata    JSONB DEFAULT '{}',          -- views, serve, build configs
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE epics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,               -- "001-channel-pipeline"
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    phase       TEXT DEFAULT 'pitch'
                CHECK (phase IN ('pitch', 'spec', 'plan', 'tasks', 'implement', 'done')),
    appetite    TEXT,                         -- "6 weeks", "2 weeks"
    priority    INT,
    file_path   TEXT,                        -- "epics/001-channel-pipeline/pitch.md"
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (platform_id, slug)
);

CREATE TABLE decisions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,               -- "ADR-011-pool-rls-multi-tenant"
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'accepted', 'deprecated', 'superseded')),
    superseded_by UUID REFERENCES decisions(id),
    file_path   TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (platform_id, slug)
);

-- ══════════════════════════════════════
-- Architecture graph (from LikeC4 model)
-- ══════════════════════════════════════

CREATE TABLE elements (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    likec4_id   TEXT NOT NULL,               -- "fulanoApi", "bcChannel.debounce"
    kind        TEXT NOT NULL,               -- "api", "worker", "boundedContext", "module"
    name        TEXT NOT NULL,
    technology  TEXT,
    description TEXT,
    tags        TEXT[],
    metadata    JSONB DEFAULT '{}',
    UNIQUE (platform_id, likec4_id)
);

CREATE TABLE element_relationships (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    source_id   UUID NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
    target_id   UUID NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,               -- "acl", "conformist", "customerSupplier", "uses"
    title       TEXT,
    technology  TEXT,
    metadata    JSONB DEFAULT '{}',          -- frequency, data, fallback
    UNIQUE (platform_id, source_id, target_id, kind)
);

-- ══════════════════════════════════════
-- Cross-references (grafo de relacoes)
-- ══════════════════════════════════════

CREATE TABLE tags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('epic', 'decision', 'element')),
    source_id   UUID NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('epic', 'decision', 'element')),
    target_id   UUID NOT NULL,
    relation    TEXT DEFAULT 'related',      -- "implements", "motivates", "impacts", "related"
    UNIQUE (source_type, source_id, target_type, target_id)
);

-- ══════════════════════════════════════
-- Tracking (agent runs, pipeline, events)
-- ══════════════════════════════════════

CREATE TABLE pipeline_runs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    epic_id     UUID NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    phase       TEXT NOT NULL,               -- "specify", "plan", "tasks", "implement"
    status      TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    agent       TEXT,                        -- "claude-opus-4-6", "claude-sonnet-4-6"
    tokens_in   INT,
    tokens_out  INT,
    cost_usd    NUMERIC(10,4),
    duration_ms INT,
    error       TEXT,
    started_at  TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID REFERENCES platforms(id),
    entity_type TEXT NOT NULL,               -- "platform", "epic", "decision", "pipeline"
    entity_id   UUID NOT NULL,
    action      TEXT NOT NULL,               -- "created", "status_changed", "phase_advanced", "built"
    actor       TEXT DEFAULT 'system',       -- "human", "claude-opus-4-6", "system"
    payload     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ══════════════════════════════════════
-- Indexes
-- ══════════════════════════════════════

CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_epics_status ON epics(status);
CREATE INDEX idx_decisions_platform ON decisions(platform_id);
CREATE INDEX idx_elements_platform ON elements(platform_id);
CREATE INDEX idx_elements_kind ON elements(kind);
CREATE INDEX idx_tags_source ON tags(source_type, source_id);
CREATE INDEX idx_tags_target ON tags(target_type, target_id);
CREATE INDEX idx_pipeline_runs_epic ON pipeline_runs(epic_id);
CREATE INDEX idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX idx_events_platform ON events(platform_id);
CREATE INDEX idx_events_created ON events(created_at);
```

### O que fica onde

| Dado | Source of truth | Por que |
|------|----------------|---------|
| Platform metadata (nome, lifecycle, views) | **Supabase** | Estruturado, queryavel, ID unico |
| Epic metadata (status, phase, prioridade) | **Supabase** | Estado muda frequentemente, queries cross-platform |
| ADR metadata (status, superseded_by) | **Supabase** | Relacoes entre ADRs, queries |
| Architecture graph (elements, relationships) | **Supabase** (sync do LikeC4) | Grafo queryavel, impacto analysis |
| Pipeline runs (tokens, custo, duracao) | **Supabase** | Tracking, otimizacao, dashboard |
| Events (log de acoes) | **Supabase** | Auditoria, timeline, analytics |
| Cross-references (epic <-> ADR <-> element) | **Supabase** | Grafo de relacoes |
| Vision, pitch, spec, plan prose | **Git (markdown)** | Conteudo narrativo, diff-friendly, LLM-consumivel |
| Domain model, blueprint prose | **Git (markdown)** | Conteudo narrativo |
| LikeC4 model files | **Git (.likec4)** | DSL, diff-friendly, compilavel |
| Templates (Copier, SpecKit) | **Git** | Versionados, compartilhados |

### O que muda no workflow

**Hoje (file-only)**:
```
/platform-new fulano
  → copier cria platforms/fulano/ com .md files
  → setup.sh cria symlinks no portal

/speckit.specify
  → cria epics/001/spec.md
  → frontmatter YAML no topo do arquivo
```

**Proposto (DB-first)**:
```
/platform-new fulano
  → INSERT INTO platforms (...) → retorna UUID
  → copier cria platforms/fulano/ com .md files (prose)
  → setup.sh cria symlinks no portal

/speckit.specify
  → INSERT INTO epics (...) → retorna UUID
  → cria epics/001/spec.md com conteudo prose
  → INSERT INTO pipeline_runs (phase='specify', ...)
  → ao concluir: UPDATE pipeline_runs SET status='completed'

/speckit.plan
  → UPDATE epics SET phase='plan'
  → INSERT INTO pipeline_runs (phase='plan', ...)
  → cria epics/001/plan.md
  → INSERT INTO events (action='phase_advanced', ...)
```

**Portal**:
```javascript
// Hoje: filesystem scan
const platforms = discoverPlatforms(); // fs.readdirSync + yaml.load

// Proposto: Supabase query
const { data: platforms } = await supabase
  .from('platforms')
  .select('*, epics(count), decisions(count)')
  .order('name');
```

### Queries que se tornam possiveis

```sql
-- Progresso geral: quantos epics por fase por plataforma
SELECT p.name, e.phase, COUNT(*)
FROM epics e JOIN platforms p ON e.platform_id = p.id
GROUP BY p.name, e.phase;

-- Custo total de SpecKit por plataforma
SELECT p.name, SUM(pr.cost_usd) as total_cost, SUM(pr.tokens_in + pr.tokens_out) as total_tokens
FROM pipeline_runs pr
JOIN epics e ON pr.epic_id = e.id
JOIN platforms p ON e.platform_id = p.id
GROUP BY p.name;

-- Quais ADRs impactam o bounded context "Channel"?
SELECT d.title, d.status
FROM decisions d
JOIN tags t ON t.source_type = 'decision' AND t.source_id = d.id
JOIN elements el ON t.target_type = 'element' AND t.target_id = el.id
WHERE el.name = 'Channel' AND el.kind = 'boundedContext';

-- Timeline de eventos de um epic
SELECT action, actor, payload, created_at
FROM events
WHERE entity_type = 'epic' AND entity_id = ?
ORDER BY created_at;

-- Epics bloqueados com mais de 7 dias
SELECT p.name, e.title, e.updated_at
FROM epics e JOIN platforms p ON e.platform_id = p.id
WHERE e.status = 'blocked' AND e.updated_at < now() - interval '7 days';
```

### Implementacao incremental

| Fase | Escopo | Resultado |
|------|--------|-----------|
| **F1** | Schema Supabase + `platform.py sync-to-db` (importa estado atual dos files) | DB populado com dados existentes |
| **F2** | Skills SpecKit escrevem no DB (specify, plan, tasks, implement) | Pipeline tracking funcional |
| **F3** | `vision-build.py` popula element_graph do LikeC4 JSON | Architecture graph queryavel |
| **F4** | Portal le metadata do Supabase (sidebar, index, dashboard) | Dashboard de progresso |
| **F5** | Cross-references: epic <-> ADR <-> element via `tags` | Impact analysis |
| **F6** | Events log + agent run tracking | Custo/performance analytics |

### Riscos e mitigacoes

| Risco | Mitigacao |
|-------|----------|
| DB fora do ar impede trabalho | Files continuam funcionando como fallback. Skills operam em "offline mode" |
| Dessincronia DB <-> files | `platform.py sync-to-db` como CI check. Lint valida consistencia |
| Custo Supabase | Free tier suporta esse volume. Pro ($25/mo) se precisar |
| Complexidade de migracao | Incremental: F1-F6 podem ser feitas uma por vez, cada fase entrega valor |

---

## Referencias

- [Paperclip](https://github.com/paperclipai/paperclip) — PostgreSQL-backed multi-agent orchestrator
- [Gas Town](https://github.com/steveyegge/gastown) — SQLite/Dolt + Git hybrid (Steve Yegge)
- [StrongDM Attractor](https://github.com/strongdm/attractor) — Software factory, specs como source of truth
- [Backstage](https://backstage.io/) — YAML em git -> indexado em PostgreSQL
- [Turso AgentFS](https://turso.tech/blog/agentfs) — SQLite per-agent para estado
- [FINOS CALM](https://calm.finos.org/) — Architecture-as-code schema padrao (Morgan Stanley)
- [Martin Fowler: Spec-Driven Development](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) — Analise de SpecKit, Tessl, Kiro
- [Anthropic 2026 Agentic Coding Trends](https://resources.anthropic.com/2026-agentic-coding-trends-report) — 60% do trabalho dev com IA
