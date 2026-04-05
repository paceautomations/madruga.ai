---
title: "Domain Model"
updated: 2026-04-02
---
# Modelo de Dominio + Schema

Consolidacao dos 6 bounded contexts do Madruga AI: entidades, diagramas de classe, schemas de storage e invariantes. Para a visao estrategica (Context Map), veja [Context Map](/madruga-ai/context-map/).

---

## Documentation (Core) — Portal, Platforms, LikeC4 Models

Responsavel por gerenciar plataformas documentadas, o portal Astro/Starlight, modelos LikeC4, e a populacao automatica de tabelas via AUTO markers.

### Modelo de Dominio

```mermaid
classDiagram
    class Platform {
        +string slug
        +string display_name
        +string lifecycle_stage
        +string[] views
        +map commands
        +path root_dir
        +string repo_org
        +string repo_name
        +string base_branch
        +string epic_branch_prefix
        +string[] tags
        +load_manifest()
        +validate_structure() bool
        +resolve_repo_path() path
    }

    class PlatformManifest {
        +string name
        +string lifecycle
        +string[] views
        +map build_commands
        +parse(yaml_path) PlatformManifest
    }

    class LikeC4Model {
        +string project_name
        +path workspace_dir
        +path config_path
        +LikeC4Element[] elements
        +LikeC4Relation[] relations
        +LikeC4View[] views
        +compile() json
        +export_json() path
        +export_png() path[]
    }

    class LikeC4Element {
        +string id
        +string kind
        +string title
        +string description
        +string technology
        +string[] tags
    }

    class LikeC4Relation {
        +string source_id
        +string target_id
        +string title
        +string technology
        +string description
    }

    class LikeC4View {
        +string id
        +string title
        +string view_of
        +string[] include_elements
    }

    class AutoMarker {
        +string marker_name
        +string file_path
        +int start_line
        +int end_line
        +string generated_content
        +populate(json_data)
        +validate() bool
    }

    class MarkdownDoc {
        +path file_path
        +string frontmatter
        +AutoMarker[] markers
        +string raw_content
        +find_markers() AutoMarker[]
        +replace_marker_content(name, content)
    }

    class PortalSite {
        +Platform[] platforms
        +map sidebar_config
        +path symlinks_dir
        +discover_platforms() Platform[]
        +build_sidebar() map
        +create_symlinks()
    }

    Platform "1" --> "1" PlatformManifest : defined by
    Platform "1" --> "1" LikeC4Model : has model
    Platform "1" --> "*" MarkdownDoc : contains
    LikeC4Model "1" --> "*" LikeC4Element : contains
    LikeC4Model "1" --> "*" LikeC4Relation : connects
    LikeC4Model "1" --> "*" LikeC4View : renders
    MarkdownDoc "1" --> "*" AutoMarker : has markers
    PortalSite "1" --> "*" Platform : discovers
```

### Storage Model

Persistencia hibrida: **filesystem** (source of truth para escrita) + **SQLite** (state store, cache, leitura rapida).

| Artefato | Formato | Caminho |
|----------|---------|---------|
| Manifesto da plataforma | YAML | `platforms/<slug>/platform.yaml` |
| Pipeline state | SQLite | `.pipeline/madruga.db` |
| Contexto da plataforma | Markdown | `platforms/<slug>/CLAUDE.md` |
| Modelo de arquitetura | `.likec4` | `platforms/<slug>/model/*.likec4` |
| Config LikeC4 | JSON | `platforms/<slug>/model/likec4.config.json` |
| Documentos de engenharia | Markdown | `platforms/<slug>/engineering/*.md` |
| Documentos de negocio | Markdown | `platforms/<slug>/business/*.md` |
| ADRs | Markdown | `platforms/<slug>/decisions/*.md` |
| Epics | Markdown | `platforms/<slug>/epics/NNN-slug/` |
| JSON exportado | JSON | `platforms/<slug>/model/output/likec4.json` |

#### SQLite Tables (madruga.db)

| Tabela | Propósito | Chave Primaria |
|--------|-----------|----------------|
| `platforms` | Registro de plataformas (name, lifecycle, repo binding) | `platform_id` |
| `pipeline_nodes` | Estado L1 de cada node do pipeline | `(platform_id, node_id)` |
| `epics` | Registro de epics (title, status, appetite, branch) | `(platform_id, epic_id)` |
| `epic_nodes` | Estado L2 de cada node do ciclo de epic | `(platform_id, epic_id, node_id)` |
| `pipeline_runs` | Historico de execucoes (tokens, custo, duracao) | `run_id` |
| `events` | Event log (entity_type, action, payload) | `event_id` |
| `artifact_provenance` | Hash e origem de cada artefato gerado | `(platform_id, file_path)` |
| `decisions` | Decisions como source of truth (21 campos, FTS5) | `decision_id` |
| `decision_links` | Links entre decisions (supersedes, relates, etc) | `(from_id, to_id, type)` |
| `memory_entries` | Memory entries com FTS5 full-text search | `memory_id` |
| `local_config` | Config local (active_platform, etc) | `key` |
| `_migrations` | Controle de migrations aplicadas | `name` |

### Invariantes

- Toda plataforma **deve** ter `platform.yaml` com campos `name`, `lifecycle` e `views`. Campos opcionais: `repo:` (org, name, base_branch, epic_branch_prefix) e `tags:[]`
- O campo `name` no `likec4.config.json` **deve** coincidir com o slug da plataforma
- AUTO markers **sempre** existem em pares: `<!-- AUTO:name -->` e `<!-- /AUTO:name -->`
- Conteudo entre AUTO markers **nunca** deve ser editado manualmente
- Symlinks do portal **devem** apontar para `platforms/<slug>` (criados por `setup.sh`)
- Cada plataforma **deve** ter pelo menos os diretorios: `business/`, `engineering/`, `decisions/`, `model/`

---

## Specification (Core) — SpecKit Pipeline, Skills, Templates

Responsavel pelo pipeline de especificacao (specify -> clarify -> plan -> tasks -> implement), skills consumidos pelo Claude Code, templates reutilizaveis, e a constituicao do projeto.

### Modelo de Dominio

```mermaid
classDiagram
    class Skill {
        +string name
        +string category
        +path file_path
        +string prompt_template
        +string[] required_context
        +string[] output_artifacts
        +load() string
    }

    class SpecKitTemplate {
        +string name
        +path file_path
        +string[] placeholders
        +string content
        +render(context: map) string
    }

    class Constitution {
        +string[] principles
        +string[] conventions
        +string[] constraints
        +path file_path
        +load() Constitution
        +validate_against(spec: Spec) Issue[]
    }

    class Spec {
        +string feature_name
        +string description
        +string[] user_stories
        +string[] acceptance_criteria
        +string[] open_questions
        +string status
        +create()
        +update()
        +clarify(questions: Question[])
    }

    class Plan {
        +string spec_ref
        +string[] design_decisions
        +string[] components
        +string[] risks
        +generate_from(spec: Spec) Plan
    }

    class TaskList {
        +string plan_ref
        +Task[] tasks
        +string[] dependency_order
        +generate_from(plan: Plan) TaskList
        +to_github_issues() Issue[]
    }

    class Task {
        +int order
        +string title
        +string description
        +string[] dependencies
        +string status
        +string[] acceptance_criteria
    }

    class SpeckitBridge {
        +Skill[] skills
        +SpecKitTemplate[] templates
        +Constitution constitution
        +compose_prompt(skill: Skill, context: map) string
        +transform_interactive_to_autonomous(skill: Skill) string
    }

    class CopierTemplate {
        +path template_dir
        +map questions
        +string[] skip_if_exists
        +scaffold(dest: path, answers: map)
        +update(dest: path)
    }

    Skill --> SpecKitTemplate : uses
    SpeckitBridge --> Skill : composes
    SpeckitBridge --> SpecKitTemplate : reads
    SpeckitBridge --> Constitution : loads
    Spec --> Plan : feeds
    Plan --> TaskList : generates
    TaskList "1" --> "*" Task : contains
    CopierTemplate --> Platform : scaffolds
```

### Storage Model

| Artefato | Formato | Caminho |
|----------|---------|---------|
| Skills (Madruga) | Markdown | `.claude/commands/madruga/*.md` |
| Skills (SpecKit) | Markdown | `.claude/commands/speckit.*.md` |
| Templates SpecKit | Markdown | `.specify/templates/*.md` |
| Constituicao | Markdown | `.specify/memory/constitution.md` |
| Template Copier | Jinja2 + YAML | `.specify/templates/platform/` |
| Spec de feature | Markdown | gerado sob demanda |
| Plan de feature | Markdown | gerado sob demanda |
| Tasks de feature | Markdown | gerado sob demanda |

### Invariantes

- Skills **devem** ser arquivos Markdown validos em `.claude/commands/`
- A constituicao **deve** existir em `.specify/memory/constitution.md`
- Templates Copier **devem** ter `copier.yml` com definicao de perguntas
- Campos marcados com `_skip_if_exists` no Copier **nao** sao sobrescritos em `copier update`
- O unico arquivo de modelo que sincroniza entre plataformas e `model/spec.likec4`
- Pipeline segue ordem estrita: specify -> clarify -> plan -> tasks -> implement

---

## Pipeline State (Supporting) — SQLite BD, Migrations, CLI Status

Responsavel pelo estado do pipeline: BD SQLite com WAL mode, migrations incrementais, seed do filesystem, e CLI de status. Implementado nos epics 006 (SQLite Foundation) e 010 (Pipeline Dashboard).

### Modelo de Dominio

```mermaid
classDiagram
    class PipelineDB {
        +path db_path
        +get_conn() Connection
        +migrate(conn) void
        +seed_from_filesystem(conn) void
    }

    class PipelineNode {
        +string platform_id
        +string node_id
        +string status
        +string output_hash
        +string input_hashes
        +string[] output_files
        +string completed_at
        +string completed_by
        +int line_count
    }

    class Epic {
        +string platform_id
        +string epic_id
        +string title
        +string status
        +string appetite
        +int priority
        +string branch_name
        +string file_path
    }

    class EpicNode {
        +string platform_id
        +string epic_id
        +string node_id
        +string status
        +string output_hash
        +string completed_at
        +string completed_by
    }

    class PipelineRun {
        +string run_id
        +string platform_id
        +string epic_id
        +string node_id
        +string status
        +string agent
        +int tokens_in
        +int tokens_out
        +float cost_usd
        +int duration_ms
    }

    class Event {
        +int event_id
        +string platform_id
        +string entity_type
        +string entity_id
        +string action
        +string actor
        +string payload
    }

    class ArtifactProvenance {
        +string platform_id
        +string file_path
        +string generated_by
        +string epic_id
        +string output_hash
    }

    PipelineDB --> PipelineNode : manages
    PipelineDB --> Epic : manages
    PipelineDB --> EpicNode : manages
    PipelineDB --> PipelineRun : logs
    PipelineDB --> Event : emits
    PipelineDB --> ArtifactProvenance : tracks
    Epic "1" --> "*" EpicNode : has L2 nodes
```

### Invariantes

- BD usa **WAL mode** + `busy_timeout=5000ms` + `foreign_keys=ON`
- Migrations sao incrementais em `.pipeline/migrations/` e controladas pela tabela `_migrations`
- `seed_from_filesystem()` popula BD a partir de `platform.yaml` e arquivos existentes
- Status de pipeline node e derivado de file existence + content hash
- Epic status: `proposed` → `drafted` → `in_progress` → `shipped` (transicoes unidirecionais). `drafted` = artefatos planejados em main sem branch
- Epic nodes seguem o ciclo L2: epic-context → specify → clarify → plan → tasks → analyze → implement → analyze → judge → qa → reconcile
- Toda mutacao gera um evento na tabela `events`

---

## Decision & Memory (Supporting) — BD Source of Truth, FTS5, Import/Export

Responsavel por decisions (ADRs) e memory entries como source of truth no BD, com FTS5 full-text search e sincronizacao bidirecional com markdown. Implementado no epic 009 (Decision Log BD).

### Modelo de Dominio

```mermaid
classDiagram
    class Decision {
        +string decision_id
        +string platform_id
        +string epic_id
        +string skill
        +string slug
        +string title
        +int number
        +string status
        +string superseded_by
        +string file_path
        +string decisions_json
        +string assumptions_json
        +string open_questions_json
        +string decision_type
        +string context
        +string consequences
        +string tags_json
        +string body
        +string content_hash
    }

    class DecisionLink {
        +string from_decision_id
        +string to_decision_id
        +string link_type
    }

    class MemoryEntry {
        +string memory_id
        +string platform_id
        +string type
        +string name
        +string description
        +string content
        +string source
        +string file_path
        +string content_hash
    }

    class DecisionsFTS {
        +search(query) Decision[]
    }

    class MemoryFTS {
        +search(query) MemoryEntry[]
    }

    Decision "1" --> "*" DecisionLink : links to
    Decision --> DecisionsFTS : indexed by
    MemoryEntry --> MemoryFTS : indexed by
```

### Invariantes

- BD e **source of truth** para decisions e memory — markdown e view layer exportada
- Toda decision tem `content_hash` para detectar drift entre BD e arquivo
- `import-adrs` parseia markdown Nygard e insere/atualiza no BD
- `export-adrs` gera markdown Nygard a partir do BD
- FTS5 indexa `title`, `context`, `consequences` (decisions) e `name`, `description`, `content` (memory)
- Decision links suportam tipos: `supersedes`, `amends`, `relates-to`
- Status de decision: `proposed` → `accepted` → `superseded` (ou `deprecated`)

---

## Intelligence (Supporting) — Subagent Judge, Decision System, Stress Test

Responsavel por garantir qualidade de specs e decisoes via review automatizado. Subagent Paralelo + Judge Pattern (ADR-019): 4 personas executam em paralelo via Claude Code Agent tool (Architecture Reviewer, Bug Hunter, Simplifier, Stress Tester), 1 juiz filtra noise por Accuracy/Actionability/Severity. Implementado nos epics 014-015.

### Modelo de Dominio

```mermaid
classDiagram
    class SubagentJudge {
        +string[] persona_ids
        +string judge_criteria
        +run_parallel_review(artifact: string) ReviewResult[]
        +judge_filter(reviews: ReviewResult[]) ConsolidatedReview
    }

    class ReviewResult {
        +string persona_id
        +string persona_role
        +Issue[] issues
        +string summary
    }

    class Issue {
        +string severity
        +string description
        +string location
        +string suggestion
        +is_actionable() bool
    }

    class ConsolidatedReview {
        +Issue[] blockers
        +Issue[] warnings
        +Issue[] nits
        +string verdict
        +float confidence_score
        +should_block() bool
    }

    class DecisionClassifier {
        +classify(decision: string) DoorType
        +register_adr(decision: string, type: DoorType)
        +escalate_to_human(decision: string, reason: string)
    }

    class DoorType {
        <<enumeration>>
        ONE_WAY_DOOR
        TWO_WAY_DOOR
    }

    class StressTestRunner {
        +string[] scenarios
        +run(spec: string, scenarios: string[]) StressResult[]
        +generate_scenarios(spec: string) string[]
    }

    class StressResult {
        +string scenario
        +string finding
        +string severity
        +string mitigation
    }

    SubagentJudge --> ReviewResult : produces
    ReviewResult --> Issue : contains
    SubagentJudge --> ConsolidatedReview : consolidates into
    ConsolidatedReview --> Issue : filters
    DecisionClassifier --> DoorType : classifies as
    StressTestRunner --> StressResult : produces
```

### Storage Model

Intelligence nao possui storage proprio — consome artefatos de Specification e persiste resultados via Execution (SQLite events + pipeline_runs).

| Dado | Destino | Formato |
|------|---------|---------|
| Review consolidado | `pipeline_runs` (SQLite) | JSON payload |
| Decisoes classificadas | `decisions` (SQLite) | Row com `decision_type` |
| Stress test results | `events` (SQLite) | Event log |

### Invariantes

- Subagent Judge **sempre** executa 4 personas em paralelo (Architecture Reviewer, Bug Hunter, Simplifier, Stress Tester) — ADR-019
- Judge pass filtra por 3 criterios: Accuracy (factual?), Actionability (fixavel?), Severity (impacta producao?)
- Toda decisao 1-way-door **deve** gerar ADR automaticamente (ADR-013)
- Stress test **deve** cobrir pelo menos: scale 10x, failure modes, edge cases, security threats
- Review results sao **imutaveis** apos consolidacao (append-only em events)

---

## Integration (Generic) — Telegram Adapter, GitHub Ops, Claude API, Sentry

Responsavel pela comunicacao com sistemas externos. Cada integracao tem uma Anti-Corruption Layer (ACL) que isola contratos externos do dominio interno.

### Modelo de Dominio

```mermaid
classDiagram
    class ClaudeAPIClient {
        +string model
        +int max_tokens
        +execute_prompt(prompt: string) string
        +execute_skill(skill_name: string, context: map) string
    }

    class TelegramAdapter {
        +string bot_token
        +int chat_id
        +send(chat_id: int, message: string)
        +ask_choice(chat_id: int, question: string, options: string[]) string
        +alert(chat_id: int, level: string, message: string)
    }

    class GitHubClient {
        +string repo
        +string token
        +create_pr(title: string, body: string, branch: string) PR
        +create_issue(title: string, body: string, labels: string[]) Issue
        +list_issues(labels: string[]) Issue[]
    }

    class LikeC4CLI {
        +path workspace
        +compile(project: string) bool
        +export_json(project: string) path
        +export_png(project: string, views: string[]) path[]
        +serve(project: string, port: int)
    }

    class SentryAdapter {
        +string dsn
        +init_sdk(fastapi_app)
        +capture_exception(error)
        +set_context(key: string, value: map)
    }

    class ACLAdapter {
        <<interface>>
        +translate_inbound(external_data) internal_model
        +translate_outbound(internal_model) external_format
    }

    ClaudeAPIClient ..|> ACLAdapter : implements
    TelegramAdapter ..|> ACLAdapter : implements
    GitHubClient ..|> ACLAdapter : implements
    LikeC4CLI ..|> ACLAdapter : implements
    SentryAdapter ..|> ACLAdapter : implements
```

### Storage Model

Este contexto nao possui storage proprio. Todas as interacoes sao **passthrough** para sistemas externos:

| Sistema | Protocolo | Dados Trafegados |
|---------|-----------|------------------|
| Claude API | `claude -p` (subprocess) | Prompts compostos, respostas de texto |
| Telegram | HTTPS (Telegram Bot API) | Notificacoes, decisoes (inline buttons), alertas |
| GitHub | `gh` CLI / REST API | Issues, PRs, labels, comments |
| LikeC4 CLI | Subprocess | JSON export, PNG export, compilation |
| Sentry | HTTPS (sentry-sdk) | Error events, performance traces, breadcrumbs |

### Invariantes

- Toda chamada a sistema externo **deve** passar pela ACL correspondente
- Falhas em sistemas externos **nao** devem propagar excecoes para o dominio (fail gracefully)
- Claude API e invocado via `claude -p` como subprocess (nao via SDK direto — ADR-010)
- Telegram Bot usa outbound HTTPS only — sem porta inbound, sem exposicao de rede (ADR-018)
- Telegram notifications sao **fire-and-forget** (sem confirmacao de leitura)
- Sentry opera como fire-and-forget — falha de envio nao afeta o easter (ADR-016)
- GitHub operations **devem** respeitar rate limits (backoff exponencial em 429)

---

## Observability — Tracing, Evals & Dashboard

Responsavel por visibilidade completa do pipeline: traces hierarquicos por run, eval scoring por node, metricas de custo/tokens, dashboard no portal e CLI status. Implementado nos epics 010 (Pipeline Dashboard) e 017 (Observability, Tracing & Evals).

### Modelo de Dominio

```mermaid
classDiagram
    class Trace {
        +string trace_id PK
        +string platform_id FK
        +string epic_id
        +string mode (l1|l2)
        +string status (running|completed|failed|cancelled)
        +int total_nodes
        +int completed_nodes
        +int total_tokens_in
        +int total_tokens_out
        +float total_cost_usd
        +int total_duration_ms
        +datetime started_at
        +datetime completed_at
    }

    class PipelineRun {
        +string run_id PK
        +string trace_id FK
        +string platform_id
        +string epic_id
        +string node_id
        +string status
        +int tokens_in
        +int tokens_out
        +float cost_usd
        +int duration_ms
        +int output_lines
        +string gate_status
    }

    class EvalScore {
        +string score_id PK
        +string trace_id FK
        +string platform_id FK
        +string node_id
        +string run_id FK
        +string dimension (quality|adherence_to_spec|completeness|cost_efficiency)
        +float score (0-10)
        +string metadata JSON
        +datetime evaluated_at
    }

    class DashboardPage {
        +Platform[] platforms
        +render_pipeline_dag() Mermaid
        +render_epic_table() HTML
        +filter_by_platform() void
    }

    class ObservabilityDashboard {
        +string activeTab (Runs|Traces|Evals|Cost)
        +poll_interval_ms = 10000
        +fetch_traces() void
        +fetch_stats() void
        +fetch_evals() void
    }

    class EvalScorer {
        +score_node(conn, platform_id, node_id, run_id, output_path, metrics) list~dict~
        +quality_heuristic(output, judge_score) float
        +adherence_heuristic(output, node_id) float
        +completeness_heuristic(output, expected_lines) float
        +cost_efficiency_heuristic(cost, avg_budget) float
    }

    class PipelineStatusExporter {
        +get_platform_status(name) StatusTable
        +get_all_status_json() JSON
    }

    Trace "1" --> "*" PipelineRun : groups as spans
    PipelineRun "1" --> "4" EvalScore : scored on 4 dimensions
    Trace "1" --> "*" EvalScore : contains
    ObservabilityDashboard --> Trace : fetches via /api/traces
    ObservabilityDashboard --> EvalScore : fetches via /api/evals
    EvalScorer --> EvalScore : produces
    DashboardPage --> PipelineStatusExporter : reads data from
```

### API Endpoints (Easter)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/api/traces` | GET | Lista traces com filtros (platform_id, status, limit, offset) |
| `/api/traces/{trace_id}` | GET | Detalhe do trace com spans e eval scores |
| `/api/stats` | GET | Agregados por dia (runs, custo, tokens, duracao) |
| `/api/evals` | GET | Eval scores com filtros (platform_id, node_id, dimension) |
| `/api/export/csv` | GET | Export CSV de traces, spans ou evals |

### Invariantes

- Trace agrupa PipelineRuns (spans) de uma execucao completa do pipeline
- Um PipelineRun pertence a exatamente um Trace (FK trace_id)
- Cada node completado recebe 4 eval scores heuristicos (best-effort, nunca bloqueia)
- Eval scores clamped a [0, 10] — quality normaliza Judge score quando disponivel
- Cleanup automatico remove registros > 90 dias (traces, runs, eval_scores)
- Dashboard consome API REST do easter (polling 10s) — nao mais dados estaticos
- CLI `status` le diretamente do SQLite (read-only)
- Context threading: analyze-post → judge → qa → reconcile recebem reports upstream no prompt
