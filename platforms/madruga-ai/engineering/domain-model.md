---
title: "Domain Model"
updated: 2026-03-27
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
        +load_manifest()
        +validate_structure() bool
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

Nao ha banco de dados neste contexto. Toda persistencia e baseada em **filesystem**:

| Artefato | Formato | Caminho |
|----------|---------|---------|
| Manifesto da plataforma | YAML | `platforms/<slug>/platform.yaml` |
| Modelo de arquitetura | `.likec4` | `platforms/<slug>/model/*.likec4` |
| Config LikeC4 | JSON | `platforms/<slug>/model/likec4.config.json` |
| Documentos de engenharia | Markdown | `platforms/<slug>/engineering/*.md` |
| Documentos de negocio | Markdown | `platforms/<slug>/business/*.md` |
| ADRs | Markdown | `platforms/<slug>/decisions/*.md` |
| Epics | Markdown | `platforms/<slug>/epics/NNN-slug/pitch.md` |
| JSON exportado | JSON | `platforms/<slug>/model/output/likec4.json` |

### Invariantes

- Toda plataforma **deve** ter `platform.yaml` com campos `name`, `lifecycle` e `views`
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

## Execution (Supporting) — Daemon, Orchestrator, Kanban Poller, Pipeline Phases

Responsavel pela execucao autonoma do pipeline: daemon 24/7, orquestrador de fases, polling do kanban Obsidian, e execucao das 7 fases do pipeline.

### Modelo de Dominio

```mermaid
classDiagram
    class Daemon {
        +bool running
        +asyncio.Loop event_loop
        +Orchestrator orchestrator
        +KanbanPoller poller
        +start()
        +stop()
        +health_check() HealthStatus
    }

    class Orchestrator {
        +Epic[] active_epics
        +PipelinePhase[] phases
        +execute_epic(epic: Epic)
        +advance_phase(epic: Epic)
        +handle_failure(epic: Epic, error: Error)
    }

    class KanbanPoller {
        +path vault_path
        +int poll_interval_sec
        +timestamp last_poll
        +poll() KanbanCard[]
        +detect_changes(previous: KanbanCard[], current: KanbanCard[]) Change[]
    }

    class KanbanCard {
        +string title
        +string column
        +string[] tags
        +string body
        +string epic_ref
    }

    class Epic {
        +string id
        +string title
        +string status
        +PipelinePhase current_phase
        +timestamp started_at
        +timestamp updated_at
        +map context
        +advance()
        +fail(reason: string)
        +complete()
    }

    class PipelinePhase {
        <<enumeration>>
        SPECIFY
        PLAN
        TASKS
        IMPLEMENT
        PERSONA_INTERVIEW
        REVIEW
        VISION
    }

    class PhaseExecutor {
        +PipelinePhase phase
        +execute(epic: Epic, context: map) PhaseResult
        +validate_preconditions(epic: Epic) bool
    }

    class PhaseResult {
        +bool success
        +string[] artifacts_produced
        +string[] errors
        +map output_context
    }

    Daemon "1" --> "1" Orchestrator : manages
    Daemon "1" --> "1" KanbanPoller : runs
    Orchestrator "1" --> "*" Epic : executes
    KanbanPoller --> KanbanCard : reads
    Epic --> PipelinePhase : tracks current
    Orchestrator --> PhaseExecutor : delegates to
    PhaseExecutor --> PhaseResult : produces
```

### Schema SQL (SQLite — madruga.db)

```sql
CREATE TABLE IF NOT EXISTS epics (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    priority TEXT DEFAULT 'P2',
    target_repo TEXT DEFAULT 'general',
    phase TEXT DEFAULT 'inbox',
    status TEXT DEFAULT 'pending',
    scope TEXT DEFAULT '',
    acceptance_criteria TEXT DEFAULT '',
    estimated_tasks INTEGER DEFAULT 0,
    spec_path TEXT DEFAULT '',
    plan_path TEXT DEFAULT '',
    tasks_path TEXT DEFAULT '',
    pr_number INTEGER,
    milestone_id TEXT,
    cost_usd REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epic_id TEXT REFERENCES epics(id),
    phase TEXT,
    model TEXT NOT NULL,
    call_type TEXT NOT NULL DEFAULT 'claude_p',
    duration_ms INTEGER,
    throttled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Invariantes

- O daemon **deve** rodar como processo asyncio unico (sem multiprocessing)
- Polling do kanban ocorre a cada **60 segundos** (configuravel)
- Um epic so avanca de fase se a fase atual completou com sucesso (`PhaseResult.success == true`)
- Fases **devem** ser executadas na ordem definida pelo enum `PipelinePhase`
- Se uma fase falha 3x consecutivas, o epic e marcado como `blocked`
- O campo `context` do epic acumula output de cada fase (append-only dentro de uma execucao)
- O daemon **deve** responder a health checks mesmo durante execucao de fases longas

---

## Intelligence (Supporting) — Debate Engine, Decision System, Clarify Engine

Responsavel por mecanismos de inteligencia: debates multi-persona com convergencia, classificacao de decisoes (1-way/2-way door), gates de aprovacao, e motor de clarificacao.

### Modelo de Dominio

```mermaid
classDiagram
    class Debate {
        +string id
        +string topic
        +Persona[] participants
        +DebateRound[] rounds
        +string convergence_status
        +string final_position
        +start(topic: string, personas: Persona[])
        +add_round(round: DebateRound)
        +check_convergence() bool
        +summarize() string
    }

    class Persona {
        +string name
        +string role
        +string perspective
        +float accuracy_score
        +generate_argument(topic: string, context: string) Argument
    }

    class DebateRound {
        +int round_number
        +Argument[] arguments
        +string moderator_summary
        +bool converged
    }

    class Argument {
        +string persona_name
        +string position
        +string[] supporting_evidence
        +string[] counterpoints
        +float confidence
    }

    class Decision {
        +string id
        +string title
        +string description
        +DoorType door_type
        +string[] alternatives
        +string chosen_alternative
        +string rationale
        +GateResult gate_result
        +classify() DoorType
        +evaluate_alternatives() Alternative[]
    }

    class DoorType {
        <<enumeration>>
        ONE_WAY
        TWO_WAY
    }

    class Gate {
        +string decision_id
        +GateType gate_type
        +bool requires_human
        +string[] approvers
        +evaluate(decision: Decision) GateResult
    }

    class GateType {
        <<enumeration>>
        AUTO_APPROVE
        HUMAN_REVIEW
        CRITICAL_STOP
    }

    class GateResult {
        +bool approved
        +string approver
        +string reason
        +timestamp decided_at
    }

    class ClarifyEngine {
        +string spec_ref
        +Question[] questions
        +identify_gaps(spec: Spec) Question[]
        +encode_answers(answers: Answer[])
    }

    class Question {
        +int priority
        +string text
        +string category
        +string[] options
    }

    Debate "1" --> "*" DebateRound : has rounds
    Debate "1" --> "*" Persona : involves
    DebateRound "1" --> "*" Argument : contains
    Argument --> Persona : authored by
    Decision --> DoorType : classified as
    Decision --> Gate : evaluated by
    Gate --> GateResult : produces
    ClarifyEngine --> Question : generates
```

### Schema SQL (SQLite — madruga.db)

```sql
CREATE TABLE IF NOT EXISTS debates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epic_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    round INTEGER NOT NULL,
    critic TEXT NOT NULL,
    severity TEXT NOT NULL,
    finding TEXT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epic_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    title TEXT NOT NULL,
    door_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    alternatives TEXT DEFAULT '',
    chosen TEXT DEFAULT '',
    rationale TEXT DEFAULT '',
    adr_path TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    pattern TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS learning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    lesson TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    applied_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS persona_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona TEXT NOT NULL,
    topic TEXT NOT NULL,
    predicted TEXT,
    actual TEXT,
    accurate INTEGER,
    evaluated_at TEXT NOT NULL
);
```

### Invariantes

- Debates **devem** ter no minimo 2 personas participantes
- Convergencia e declarada quando todas as personas alinham posicao ou apos **5 rounds** (o que vier primeiro)
- Decisoes 1-way door **sempre** exigem gate `HUMAN_REVIEW` ou `CRITICAL_STOP`
- Decisoes 2-way door **podem** ser auto-aprovadas (`AUTO_APPROVE`)
- Gates do tipo `CRITICAL_STOP` **devem** notificar via WhatsApp
- O ClarifyEngine gera no maximo **5 perguntas** por iteracao
- Accuracy score de personas e atualizado apos cada review retrospectiva

---

## Integration (Generic) — Obsidian CRUD, WhatsApp Bridge, GitHub Ops, Claude API

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

    class ObsidianBridge {
        +path vault_path
        +read_file(relative_path: string) string
        +write_file(relative_path: string, content: string)
        +read_kanban(board_path: string) KanbanBoard
        +update_kanban(board_path: string, changes: Change[])
    }

    class KanbanBoard {
        +string title
        +KanbanColumn[] columns
        +KanbanCard[] cards
    }

    class KanbanColumn {
        +string name
        +int position
        +KanbanCard[] cards
    }

    class WhatsAppBridge {
        +string api_url
        +send_notification(phone: string, message: string)
        +send_critical_alert(phone: string, decision: Decision)
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

    class ACLAdapter {
        <<interface>>
        +translate_inbound(external_data) internal_model
        +translate_outbound(internal_model) external_format
    }

    ObsidianBridge --> KanbanBoard : reads/writes
    KanbanBoard "1" --> "*" KanbanColumn : has
    KanbanColumn "1" --> "*" KanbanCard : contains
    ClaudeAPIClient ..|> ACLAdapter : implements
    ObsidianBridge ..|> ACLAdapter : implements
    WhatsAppBridge ..|> ACLAdapter : implements
    GitHubClient ..|> ACLAdapter : implements
    LikeC4CLI ..|> ACLAdapter : implements
```

### Storage Model

Este contexto nao possui storage proprio. Todas as interacoes sao **passthrough** para sistemas externos:

| Sistema | Protocolo | Dados Trafegados |
|---------|-----------|------------------|
| Claude API | `claude -p` (subprocess) | Prompts compostos, respostas de texto |
| Obsidian Vault | Filesystem (read/write) | Markdown files, kanban boards |
| WhatsApp | HTTP/API | Notificacoes de texto, alertas criticos |
| GitHub | `gh` CLI / REST API | Issues, PRs, labels, comments |
| LikeC4 CLI | Subprocess | JSON export, PNG export, compilation |

### Invariantes

- Toda chamada a sistema externo **deve** passar pela ACL correspondente
- Falhas em sistemas externos **nao** devem propagar excecoes para o dominio (fail gracefully)
- Claude API e invocado via `claude -p` como subprocess (nao via SDK direto)
- Obsidian bridge opera somente dentro do `vault_path` configurado (sem path traversal)
- WhatsApp notifications sao **fire-and-forget** (sem confirmacao de leitura)
- GitHub operations **devem** respeitar rate limits (backoff exponencial em 429)

---

## Observability (Generic) — Dashboard, Health Checks, Metrics

Responsavel por visibilidade operacional: dashboard web, health checks do daemon, e metricas de execucao do pipeline.

### Modelo de Dominio

```mermaid
classDiagram
    class Dashboard {
        +FastAPI app
        +int port
        +serve()
        +get_epic_status() EpicSummary[]
        +get_phase_metrics() PhaseMetrics
        +get_health() HealthStatus
    }

    class HealthStatus {
        +bool daemon_running
        +bool poller_active
        +timestamp last_poll
        +int active_epics
        +string[] errors
        +check() HealthStatus
    }

    class EpicSummary {
        +string epic_id
        +string title
        +string status
        +string current_phase
        +timestamp last_activity
        +int phases_completed
        +int total_phases
    }

    class PhaseMetrics {
        +map phase_durations_avg
        +map phase_success_rates
        +int total_runs
        +int failed_runs
        +timestamp window_start
        +calculate(window_hours: int) PhaseMetrics
    }

    class EventBus {
        +publish(event: DomainEvent)
        +subscribe(event_type: string, handler: callable)
    }

    class DomainEvent {
        +string event_type
        +string source_context
        +timestamp occurred_at
        +map payload
    }

    Dashboard --> HealthStatus : displays
    Dashboard --> EpicSummary : lists
    Dashboard --> PhaseMetrics : shows
    EventBus --> DomainEvent : routes
    Dashboard --> EventBus : subscribes to
```

### Storage Model

Observability consome dados do SQLite (`madruga.db`) em modo **read-only**. Nao possui tabelas proprias.

O dashboard e servido via FastAPI com templates HTML embutidos — sem SPA, sem build frontend.

### Invariantes

- Dashboard **deve** ser acessivel mesmo quando o daemon esta sob carga
- Health check **deve** responder em menos de **500ms**
- Metricas sao calculadas sob demanda (sem pre-agregacao)
- EventBus opera como **pub-sub fire-and-forget** (sem garantia de entrega)
- Dashboard **nao** expoe endpoints de mutacao (somente leitura)
- Logs estruturados (JSON) para toda operacao do daemon
