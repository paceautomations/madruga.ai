# De Files para DB-First: Evolucao do madruga.ai

Data: 2026-03-29
Status: **Aprovado — SQLite local**
Decisao anterior: Supabase (revisada para SQLite com base em uso real)

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

### Caminho B: DB-First com Supabase (descartado — over-engineering)

DB e a source of truth para estado e metadados. Supabase (PostgreSQL managed).

- **Pro**: queries poderosas, real-time, dashboard nativo, pgvector
- **Contra**: dependencia de rede, complexidade de auth/RLS/API, custo, over-engineering para CLI single-user
- **Quem usa**: Paperclip, Devin, Backstage, StrongDM
- **Por que descartado**: madruga.ai e CLI single-user local. Supabase resolve problemas (multi-user, real-time, auth) que nao existem hoje. Adicionar rede, API keys, e infra cloud para um pipeline que roda na maquina do usuario e friccao sem valor

### Caminho C: SQLite Local DB-First (aprovado)

SQLite como source of truth para estado e metadados. Files mantidos para conteudo narrativo.

- **Pro**: zero infra, zero dependencia (`sqlite3` built-in no Python), funciona offline, queries reais, constraints, FKs, migracao para PostgreSQL mecanica
- **Contra**: single-writer (aceitavel — CLI single-user), sem real-time (aceitavel — sem portal live dashboard hoje)
- **Quem usa**: Gas Town (Yegge), Turso AgentFS
- **Path de upgrade**: SQLite -> PostgreSQL/Supabase quando precisar multi-user ou portal real-time (~1 dia de migracao)

## Decisao: Caminho C com SQLite

### Por que SQLite e nao Supabase

| Aspecto | SQLite | Supabase (Postgres) |
|---------|--------|---------------------|
| **Infra** | Zero. Um arquivo. Built-in Python | Managed cloud. API key. Rede |
| **Offline** | Sempre funciona | Depende de rede |
| **Dependencias** | `import sqlite3` (built-in) | `pip install supabase` + config |
| **Multi-user** | Single-writer (OK para CLI) | Multi-writer, RLS |
| **Real-time** | Nao | Sim (subscriptions) |
| **Complexidade** | Minima | Auth, RLS, API, migrations |
| **Custo** | Zero | Free tier (limitado) / $25/mo |
| **Migracao para PG** | ~1 dia | N/A (ja e PG) |

**Argumento decisivo**: madruga.ai e um CLI single-user que roda local. SQLite e literalmente o BD desenhado para esse use case. A experiencia com Supabase no Fulano e valida, mas o Fulano e uma app multi-tenant em producao — contexto completamente diferente.

**Quando migrar para Supabase**: quando o portal precisar de dashboard real-time, quando houver multiplos operadores, ou quando pgvector for necessario para busca semantica nos artefatos.

### Arquitetura

```
Skills / CLI / platform.py
        │
        ▼
┌─────────────────────────────────┐
│   .pipeline/madruga.db (SQLite) │
│                                 │
│   platforms ─┬─ pipeline_nodes  │  ← DAG nivel 1 (platform)
│              ├─ epics           │
│              │   └─ epic_nodes  │  ← DAG nivel 2 (per-epic)
│              ├─ decisions       │  ← ADR registry + decision log
│              ├─ artifact_provenance │
│              ├─ pipeline_runs   │  ← tracking tokens/custo
│              ├─ events          │  ← audit log
│              └─ tags            │  ← cross-references
│                                 │
│   elements ──── relationships   │  ← LikeC4 graph (fase futura)
└───────────┬─────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│   Portal (Astro + Starlight)    │
│   Le conteudo prose do Git      │
│   Le metadata do SQLite (build) │
│   (futuro: Supabase real-time)  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│   Git (repositorio)             │
│                                 │
│   platforms/*/                  │
│     ├─ business/*.md    (prose) │
│     ├─ engineering/*.md (prose) │
│     ├─ epics/*/         (prose + spec + plan + tasks) │
│     ├─ decisions/*.md   (prose) │
│     └─ model/*.likec4   (model) │
└─────────────────────────────────┘
```

### Schema

```sql
-- .pipeline/migrations/001_initial.sql

-- ══════════════════════════════════════
-- Core entities
-- ══════════════════════════════════════

CREATE TABLE platforms (
    platform_id TEXT PRIMARY KEY,              -- "fulano" (kebab-case)
    name        TEXT NOT NULL,
    title       TEXT,
    lifecycle   TEXT NOT NULL DEFAULT 'design'
                CHECK (lifecycle IN ('design', 'development', 'production', 'deprecated')),
    repo_path   TEXT NOT NULL,                 -- "platforms/fulano"
    metadata    TEXT DEFAULT '{}',             -- JSON: views, build configs
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE epics (
    epic_id     TEXT NOT NULL,                 -- "001-channel-pipeline"
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id),
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    appetite    TEXT,                           -- "6 weeks"
    priority    INTEGER,
    branch_name TEXT,                          -- feature branch do SpecKit
    file_path   TEXT,                          -- "epics/001-channel-pipeline/pitch.md"
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (platform_id, epic_id)
);

-- ══════════════════════════════════════
-- DAG Nivel 1: Platform nodes
-- ══════════════════════════════════════

CREATE TABLE pipeline_nodes (
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id),
    node_id     TEXT NOT NULL,                 -- "vision", "blueprint", etc.
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'done', 'stale', 'blocked', 'skipped')),
    output_hash TEXT,                          -- SHA256 do conteudo do artefato
    input_hashes TEXT DEFAULT '{}',            -- JSON: {dep_file: hash}
    output_files TEXT DEFAULT '[]',            -- JSON array: ["business/vision.md"]
    completed_at TEXT,
    completed_by TEXT,                         -- skill que gerou
    line_count  INTEGER,
    PRIMARY KEY (platform_id, node_id)
);

-- ══════════════════════════════════════
-- DAG Nivel 2: Epic cycle nodes
-- ══════════════════════════════════════

CREATE TABLE epic_nodes (
    platform_id TEXT NOT NULL,
    epic_id     TEXT NOT NULL,
    node_id     TEXT NOT NULL,                 -- "specify", "plan", "verify", etc.
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'done', 'stale', 'blocked', 'skipped')),
    output_hash TEXT,
    completed_at TEXT,
    completed_by TEXT,
    PRIMARY KEY (platform_id, epic_id, node_id),
    FOREIGN KEY (platform_id, epic_id) REFERENCES epics(platform_id, epic_id)
);

-- ══════════════════════════════════════
-- Decisions (ADR registry + decision log unificados)
-- ══════════════════════════════════════

CREATE TABLE decisions (
    decision_id     TEXT PRIMARY KEY,          -- "adr-001" ou auto-generated
    platform_id     TEXT NOT NULL REFERENCES platforms(platform_id),
    epic_id         TEXT,                      -- NULL para platform-level decisions
    skill           TEXT NOT NULL,             -- "adr", "vision", "epic-context"
    slug            TEXT,                      -- "database-choice" (para ADRs)
    title           TEXT NOT NULL,
    number          INTEGER,                   -- ADR number (para ADRs)
    status          TEXT NOT NULL DEFAULT 'accepted'
                    CHECK (status IN ('accepted', 'superseded', 'deprecated', 'proposed')),
    superseded_by   TEXT REFERENCES decisions(decision_id),
    source_decision_key TEXT,                  -- Liga ao tech-research
    file_path       TEXT,                      -- "decisions/ADR-001-database-choice.md"
    decisions_json  TEXT DEFAULT '[]',         -- JSON array: decisoes tomadas
    assumptions_json TEXT DEFAULT '[]',        -- JSON array: assumptions
    open_questions_json TEXT DEFAULT '[]',     -- JSON array: open questions
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════
-- Artifact provenance
-- ══════════════════════════════════════

CREATE TABLE artifact_provenance (
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    file_path    TEXT NOT NULL,                -- "business/vision.md"
    generated_by TEXT NOT NULL,                -- skill ID
    epic_id      TEXT,                         -- NULL para platform-level
    output_hash  TEXT,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (platform_id, file_path)
);

-- ══════════════════════════════════════
-- Tracking (pipeline runs, cost)
-- ══════════════════════════════════════

CREATE TABLE pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    epic_id      TEXT,
    node_id      TEXT NOT NULL,                -- "vision", "specify", etc.
    status       TEXT NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    agent        TEXT,                         -- "claude-opus-4-6"
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    cost_usd     REAL,
    duration_ms  INTEGER,
    error        TEXT,
    started_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    completed_at TEXT
);

-- ══════════════════════════════════════
-- Events (audit log append-only)
-- ══════════════════════════════════════

CREATE TABLE events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id  TEXT REFERENCES platforms(platform_id),
    entity_type  TEXT NOT NULL,                -- "platform", "epic", "decision", "node"
    entity_id    TEXT NOT NULL,
    action       TEXT NOT NULL,                -- "created", "status_changed", "completed"
    actor        TEXT DEFAULT 'system',        -- "human", "claude-opus-4-6", "system"
    payload      TEXT DEFAULT '{}',            -- JSON
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════
-- Cross-references
-- ══════════════════════════════════════

CREATE TABLE tags (
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    source_type  TEXT NOT NULL CHECK (source_type IN ('epic', 'decision', 'element', 'node')),
    source_id    TEXT NOT NULL,
    target_type  TEXT NOT NULL CHECK (target_type IN ('epic', 'decision', 'element', 'node')),
    target_id    TEXT NOT NULL,
    relation     TEXT DEFAULT 'related',       -- "implements", "motivates", "impacts"
    UNIQUE (source_type, source_id, target_type, target_id)
);

-- ══════════════════════════════════════
-- Architecture graph (fase futura — sync do LikeC4 JSON)
-- ══════════════════════════════════════

CREATE TABLE elements (
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id),
    likec4_id   TEXT NOT NULL,                 -- "fulanoApi", "bcChannel.debounce"
    kind        TEXT NOT NULL,                 -- "api", "worker", "boundedContext"
    name        TEXT NOT NULL,
    technology  TEXT,
    description TEXT,
    tags_json   TEXT DEFAULT '[]',
    metadata    TEXT DEFAULT '{}',
    UNIQUE (platform_id, likec4_id)
);

CREATE TABLE element_relationships (
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id),
    source_id   TEXT NOT NULL,                 -- likec4_id
    target_id   TEXT NOT NULL,                 -- likec4_id
    kind        TEXT NOT NULL,                 -- "acl", "conformist", "uses"
    title       TEXT,
    technology  TEXT,
    metadata    TEXT DEFAULT '{}',
    UNIQUE (platform_id, source_id, target_id, kind)
);

-- ══════════════════════════════════════
-- Indexes
-- ══════════════════════════════════════

CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_epics_status ON epics(status);
CREATE INDEX idx_pipeline_nodes_platform ON pipeline_nodes(platform_id);
CREATE INDEX idx_epic_nodes_epic ON epic_nodes(platform_id, epic_id);
CREATE INDEX idx_decisions_platform ON decisions(platform_id);
CREATE INDEX idx_decisions_epic ON decisions(epic_id);
CREATE INDEX idx_provenance_platform ON artifact_provenance(platform_id);
CREATE INDEX idx_runs_platform ON pipeline_runs(platform_id);
CREATE INDEX idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX idx_events_platform ON events(platform_id);
CREATE INDEX idx_events_created ON events(created_at);
CREATE INDEX idx_elements_platform ON elements(platform_id);
CREATE INDEX idx_elements_kind ON elements(kind);
CREATE INDEX idx_tags_source ON tags(source_type, source_id);
CREATE INDEX idx_tags_target ON tags(target_type, target_id);
```

### O que fica onde

| Dado | Source of truth | Por que |
|------|----------------|---------|
| Platform metadata (nome, lifecycle) | **SQLite** | Estruturado, queryavel, ID unico |
| Pipeline state (nos, status, hashes) | **SQLite** | Queries, staleness detection |
| Epic metadata (status, branch, prioridade) | **SQLite** | Estado muda frequentemente, queries cross-platform |
| Epic cycle progress (specify, plan, etc.) | **SQLite** | DAG nivel 2. Observabilidade por epic |
| ADR registry + decision log | **SQLite** | Idempotencia, lineage, lifecycle |
| Artifact provenance | **SQLite** | Validacao de prerequisites |
| Pipeline runs (tokens, custo, duracao) | **SQLite** | Tracking, otimizacao |
| Events (log de acoes) | **SQLite** | Auditoria, timeline |
| Cross-references (epic <-> ADR <-> element) | **SQLite** | Grafo de relacoes |
| Architecture graph (elements, relationships) | **SQLite** (fase futura, sync do LikeC4) | Grafo queryavel, impact analysis |
| Vision, pitch, spec, plan, tasks prose | **Git (markdown)** | Conteudo narrativo, diff-friendly, LLM-consumivel |
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
  → cria specs/001/spec.md (diretorio separado)
  → frontmatter YAML no topo do arquivo
```

**Aprovado (SQLite + diretorio unificado)**:
```
/platform-new fulano
  → INSERT INTO platforms (...) → platform_id = 'fulano'
  → copier cria platforms/fulano/ com .md files (prose)
  → INSERT INTO pipeline_nodes (13 nos com status 'pending')
  → setup.sh cria symlinks no portal

/epic-breakdown fulano
  → INSERT INTO epics (...) para cada epic
  → cria epics/001/pitch.md (prose)
  → INSERT INTO events (action='created', entity_type='epic')

/speckit.specify fulano --epic 001
  → opera em platforms/fulano/epics/001/ (nao em specs/)
  → cria epics/001/spec.md com conteudo prose
  → UPDATE epic_nodes SET status='done' WHERE node_id='specify'
  → INSERT INTO pipeline_runs (node_id='specify', tokens_in=..., cost_usd=...)
  → INSERT INTO events (action='completed')

/pipeline fulano
  → SELECT * FROM pipeline_nodes WHERE platform_id = 'fulano'
  → SELECT e.epic_id, COUNT(en.status='done') FROM epic_nodes en ...
  → Mostra: platform DAG + epic progress + next step
```

### Queries que se tornam possiveis

```sql
-- Progresso geral: quantos nos done por plataforma
SELECT p.platform_id,
       COUNT(*) as total,
       SUM(CASE WHEN pn.status = 'done' THEN 1 ELSE 0 END) as done
FROM pipeline_nodes pn
JOIN platforms p ON pn.platform_id = p.platform_id
GROUP BY p.platform_id;

-- Epic progress com steps
SELECT e.epic_id, e.title, e.status,
       COUNT(en.node_id) as total_steps,
       SUM(CASE WHEN en.status = 'done' THEN 1 ELSE 0 END) as done_steps
FROM epics e
LEFT JOIN epic_nodes en ON e.epic_id = en.epic_id AND e.platform_id = en.platform_id
WHERE e.platform_id = 'fulano'
GROUP BY e.epic_id;

-- Custo total por plataforma
SELECT platform_id,
       SUM(cost_usd) as total_cost,
       SUM(tokens_in + tokens_out) as total_tokens
FROM pipeline_runs
WHERE status = 'completed'
GROUP BY platform_id;

-- Decisoes com open questions
SELECT platform_id, skill, title, open_questions_json
FROM decisions
WHERE open_questions_json != '[]';

-- Artefatos stale (dependencia mais nova que o no)
SELECT child.node_id as stale_node,
       child.completed_at as node_date
FROM pipeline_nodes child
WHERE child.platform_id = 'fulano'
  AND child.status = 'done'
  AND EXISTS (
    SELECT 1 FROM pipeline_nodes parent
    WHERE parent.platform_id = child.platform_id
      AND parent.completed_at > child.completed_at
      AND parent.node_id IN (
        -- deps do child (lido do platform.yaml em runtime)
        SELECT value FROM json_each(:child_deps)
      )
  );

-- Timeline de um epic
SELECT action, actor, payload, created_at
FROM events
WHERE entity_type = 'epic' AND entity_id = '001-channel-pipeline'
ORDER BY created_at;

-- Epics bloqueados ha mais de 7 dias
SELECT p.platform_id, e.title, e.updated_at
FROM epics e JOIN platforms p ON e.platform_id = p.platform_id
WHERE e.status = 'blocked'
  AND e.updated_at < datetime('now', '-7 days');
```

### Implementacao

#### Modulo `db.py`

```python
# .specify/scripts/db.py — ~200 linhas
# Thin wrapper sobre sqlite3

import sqlite3, os, hashlib, json, uuid
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / '.pipeline' / 'madruga.db'
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / '.pipeline' / 'migrations'

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def migrate():
    """Aplica migrations de .pipeline/migrations/*.sql em ordem."""
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TEXT)")
    applied = {r['name'] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    for sql_file in sorted(MIGRATIONS_DIR.glob('*.sql')):
        if sql_file.name not in applied:
            conn.executescript(sql_file.read_text())
            conn.execute("INSERT INTO _migrations VALUES (?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                        (sql_file.name,))
            conn.commit()
    conn.close()

def upsert_platform(platform_id, name, repo_path, **kwargs): ...
def upsert_pipeline_node(platform_id, node_id, status, **kwargs): ...
def upsert_epic(platform_id, epic_id, title, **kwargs): ...
def upsert_epic_node(platform_id, epic_id, node_id, status, **kwargs): ...
def insert_decision(platform_id, skill, title, **kwargs): ...
def insert_provenance(platform_id, file_path, generated_by, **kwargs): ...
def insert_run(platform_id, node_id, **kwargs): ...
def insert_event(platform_id, entity_type, entity_id, action, **kwargs): ...
def get_platform_status(platform_id): ...
def get_epic_status(platform_id, epic_id): ...
def get_stale_nodes(platform_id): ...

def compute_file_hash(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
```

#### Fases de implementacao

| Fase | Escopo | Resultado | Esforco |
|------|--------|-----------|---------|
| **F1** | Schema SQLite + `db.py` + `migrate()` + `platform.py sync-to-db` (importa estado atual) | BD populado com dados existentes | ~3h |
| **F2** | Skills escrevem no BD (step 5 do contrato: upsert node, insert decision, insert provenance) | Pipeline tracking funcional | ~3h |
| **F3** | `/pipeline` le do BD (status + next + per-epic) | Observabilidade completa | ~2h |
| **F4** | `check-platform-prerequisites.sh` consulta BD em vez de file existence | Prerequisites robustos (hash, provenance, staleness) | ~2h |
| **F5** | `vision-build.py` popula elements/relationships do LikeC4 JSON | Architecture graph queryavel | ~2h |
| **F6** | Cross-references (tags): epic <-> ADR <-> element | Impact analysis | ~2h |

**Total: ~14h** (fases independentes, cada uma entrega valor).

### Migracao futura para PostgreSQL/Supabase

Quando precisar multi-user, portal real-time, ou pgvector:

1. **Schema**: SQLite -> PostgreSQL e mecanico. Ajustar: `TEXT DEFAULT '{}'` -> `JSONB`, `INTEGER PRIMARY KEY AUTOINCREMENT` -> `SERIAL`, timestamps -> `TIMESTAMPTZ`
2. **Codigo**: Trocar `sqlite3.connect()` por `psycopg2.connect()` em `db.py` (~10 linhas)
3. **Features Supabase**: Adicionar RLS, auth, real-time subscriptions, REST API auto-gerado
4. **Portal**: Trocar leitura de SQLite por fetch do Supabase JS client
5. **Estimativa**: ~1 dia de trabalho

### Riscos e mitigacoes

| Risco | Mitigacao |
|-------|----------|
| BD corrompido | WAL mode + backup automatico (cp madruga.db madruga.db.bak) antes de migrations |
| Dessincronia BD <-> files | `platform.py sync-to-db` como CI check. Skills sempre escrevem em ambos |
| BD no .gitignore | Sim — BD e estado local. Migrations (.sql) sao versionadas no git |
| SQLite single-writer | Aceitavel — CLI single-user. Upgrade para PG se precisar |

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
