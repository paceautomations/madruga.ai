---
type: reconcile-report
epic: 004-router-mece
date: 2026-04-11
branch: epic/prosauai/004-router-mece
drift_score: 50
docs_checked: 10
docs_current: 5
docs_outdated: 5
findings_total: 12
---

# Reconcile Report — Epic 004: Router MECE

**Data:** 11/04/2026 | **Branch:** `epic/prosauai/004-router-mece`
**Commits:** 2 (7f96a3f, 61a17fc) | **Arquivos alterados:** 23

---

## Drift Score: 50%

**Formula:** `docs_current / docs_checked × 100 = 5/10 × 100 = 50%`

O score reflete drift concentrado em documentos de engenharia (blueprint, domain-model) e negocio (process.md) que descrevem o router com terminologia e arquitetura do pre-004. Nenhum drift e funcional (o codigo esta correto); todo drift e documental.

---

## Tabela de Saude da Documentacao

| # | Documento | Categorias | Status | Drift Items |
|---|-----------|-----------|--------|-------------|
| 1 | `business/solution-overview.md` | D1 | CURRENT | 0 — doc de alto nivel, nao detalha router internals |
| 2 | `business/process.md` | D1, D4 | **OUTDATED** | 3 — Fase B descreve `routing_rules` table + `match_conditions JSONB` + `tenants.settings.default_agent_id`; nomenclatura `RouteDecision` enum stale |
| 3 | `engineering/blueprint.md` | D2 | **OUTDATED** | 2 — folder structure lista `formatter.py → ParsedMessage` e `router.py → RouteResult` (ambos removidos/renomeados) |
| 4 | `engineering/domain-model.md` | D4 | **OUTDATED** | 4 — `RouteDecision` enum 6 valores stale; `Router` aggregate methods stale; `RoutingRule` entity stale; `tenants.settings.default_agent_id` JSONB vs flat |
| 5 | `engineering/containers.md` | D3 | **OUTDATED** | 1 — referencia `formatter.py` sem notar rename |
| 6 | `engineering/context-map.md` | D8 | CURRENT | 0 — `InboundMessage → ConversationRequest` ACL consistente |
| 7 | `decisions/ADR-*.md` | D5 | CURRENT | 0 — nenhuma contradicao detectada |
| 8 | `planning/roadmap.md` | D6 | **OUTDATED** | 2 — epic 003 e 004 com status desatualizado |
| 9 | `epics/004-router-mece/decisions.md` | D10 | CURRENT | 0 — 21 decisoes consistentes com ADRs |
| 10 | `README.md` | D9 | N/A | Nao existe — skip |

---

## Matriz de Raio de Impacto

| Area Alterada (git diff) | Docs Diretamente Afetados | Docs Transitivamente Afetados | Esforco |
|--------------------------|--------------------------|------------------------------|---------|
| Router refactor (classify + engine + rip-and-replace) | `domain-model.md`, `blueprint.md`, `process.md` | `containers.md` | **L** (rewrite de secoes inteiras no domain-model) |
| Rename ParsedMessage → InboundMessage | `blueprint.md` (folder structure) | `containers.md` | **S** (string replace) |
| Tenant.default_agent_id flat (nao JSONB) | `domain-model.md` (SQL schema), `process.md` (Fase B) | — | **M** (update schema + descricao) |
| Roadmap status updates | `planning/roadmap.md` | — | **S** (update de status na tabela) |

---

## Deduplicacao com Verify

WARN: `verify-report.md` nao encontrado para este epic. Verify deveria rodar antes de reconcile. Nenhum finding a deduplicate.

---

## Propostas de Atualizacao (D1–D10)

### D1 — Scope Drift

Nenhum drift significativo. `solution-overview.md` nao detalha internals do router — nivel correto de abstracao.

### D2 — Architecture Drift

| # | ID | Affected Doc | Current State | Expected State | Severity |
|---|-----|-------------|---------------|----------------|----------|
| 1 | D2.1 | `engineering/blueprint.md:130` | `formatter.py → ParsedMessage` | `formatter.py → InboundMessage` (classe renomeada) | medium |
| 2 | D2.2 | `engineering/blueprint.md:131` | `router.py → Smart Router (6 rotas), RouteResult` | `router/ → Router MECE module (classify + RoutingEngine + 5 Decision subtypes)` | medium |

**Diff concreto para D2.1 + D2.2** (blueprint.md, folder structure):

```diff
- │   ├── formatter.py       # Evolution API payload → ParsedMessage
- │   ├── router.py          # Smart Router (6 rotas), RouteResult
+ │   ├── formatter.py       # Evolution API payload → InboundMessage
+ │   ├── router/            # Router MECE: classify() + RoutingEngine + Decision
+ │   │   ├── __init__.py    # Public API: route(), classify(), RoutingEngine
+ │   │   ├── facts.py       # MessageFacts, StateSnapshot, enums
+ │   │   ├── matchers.py    # MentionMatchers (tenant-aware)
+ │   │   ├── engine.py      # RoutingEngine, Rule, Decision subtypes
+ │   │   ├── loader.py      # YAML loader + overlap analysis
+ │   │   ├── verify.py      # CLI: router verify | explain
+ │   │   └── errors.py      # RoutingError, RoutingConfigError
```

### D3 — Container Drift

| # | ID | Affected Doc | Current State | Expected State | Severity |
|---|-----|-------------|---------------|----------------|----------|
| 3 | D3.1 | `engineering/containers.md:214` | `formatter.py reescrito (12 correcoes)` | Adicionar nota: `formatter.py: ParsedMessage renomeado para InboundMessage (epic 004); modulo core/router/ substituiu router.py (epic 004)` | low |

### D4 — Domain Drift

| # | ID | Affected Doc | Current State | Expected State | Severity |
|---|-----|-------------|---------------|----------------|----------|
| 4 | D4.1 | `domain-model.md:67-75` | `RouteDecision` enum: SUPPORT, GROUP_RESPOND, GROUP_SAVE_ONLY, GROUP_EVENT, HANDOFF_ATIVO, IGNORE | `Action` enum: RESPOND, LOG_ONLY, DROP, BYPASS_AI, EVENT_HOOK + `MessageFacts` dataclass para classificacao ortogonal | **high** |
| 5 | D4.2 | `domain-model.md:88-96` | `Router.classify(messages) → RouteDecision` + `Router.resolve_agent(decision, rules) → uuid` | `classify(message, state, matchers) → MessageFacts` (funcao pura) + `RoutingEngine.decide(facts, tenant) → Decision` (discriminated union) | **high** |
| 6 | D4.3 | `domain-model.md:77-86` | `RoutingRule`: phone_number, match_conditions JSONB, agent_id, priority | `Rule`: name, priority, when (equality+conjunction dict), action, agent (optional), target, reason. Config em YAML, nao DB table | **high** |
| 7 | D4.4 | `domain-model.md:162-164` | `tenants.settings JSONB` com key `default_agent_id` | `Tenant.default_agent_id: UUID \| None` flat no dataclass (Fase 1 file-backed). SQL schema mantem JSONB para Fase 3 Postgres. | medium |

**Diff concreto para D4.1 + D4.2 + D4.3** (domain-model.md, Channel BC class diagram):

O diagrama Mermaid precisa rewrite significativo. A proposta:

```diff
- class RouteDecision {
-     <<enumeration>>
-     SUPPORT
-     GROUP_RESPOND
-     GROUP_SAVE_ONLY
-     GROUP_EVENT
-     HANDOFF_ATIVO
-     IGNORE
- }
-
- class RoutingRule {
-     +uuid id
-     +uuid tenant_id
-     +string phone_number
-     +json match_conditions
-     +uuid agent_id
-     +int priority
-     +bool is_active
-     +matches(msg: InboundMessage) bool
- }
-
- class Router {
-     +uuid message_id
-     +RouteDecision decision
-     +uuid resolved_agent_id
-     +string reason
-     +json routing_metadata
-     +classify(messages: InboundMessage[]) RouteDecision
-     +resolve_agent(decision: RouteDecision, rules: RoutingRule[]) uuid
- }
+ class MessageFacts {
+     <<frozen dataclass>>
+     +string instance
+     +EventKind event_kind
+     +ContentKind content_kind
+     +Channel channel
+     +bool from_me
+     +string sender_phone
+     +string group_id
+     +bool has_mention
+     +bool is_membership_event
+     +bool is_duplicate
+     +bool conversation_in_handoff
+ }
+
+ class Action {
+     <<enumeration>>
+     RESPOND
+     LOG_ONLY
+     DROP
+     BYPASS_AI
+     EVENT_HOOK
+ }
+
+ class Decision {
+     <<discriminated union>>
+     +Action action
+     +string matched_rule
+     +UUID agent_id (RESPOND only)
+     +string reason
+ }
+
+ class Rule {
+     <<frozen dataclass>>
+     +string name
+     +int priority
+     +dict when
+     +Action action
+     +UUID agent (optional)
+     +string target
+ }
+
+ class RoutingEngine {
+     <<frozen dataclass>>
+     +tuple~Rule~ rules
+     +Rule default
+     +decide(facts: MessageFacts, tenant: Tenant) Decision
+ }
+
+ class MentionMatchers {
+     <<frozen value object>>
+     +string lid_opaque
+     +string phone
+     +tuple~str~ keywords
+     +from_tenant(tenant: Tenant) MentionMatchers
+     +matches(message: InboundMessage) bool
+ }
```

Relacionamentos atualizados:
```diff
- Router --> RouteDecision : classifies
- Router --> RoutingRule : evaluates (priority order)
+ InboundMessage --> MessageFacts : classify() pure
+ MessageFacts --> RoutingEngine : input to decide()
+ RoutingEngine --> Decision : produces
+ RoutingEngine --> Rule : evaluates (priority ASC)
+ MentionMatchers --> MessageFacts : used by classify()
```

**Diff concreto para D4.4** (domain-model.md, tenants table):

```diff
  settings        JSONB NOT NULL DEFAULT '{}',
  -- settings JSONB keys:
  --   default_agent_id: UUID          -- fallback agent when no routing rule matches
+ --   NOTA (epic 004): Na Fase 1 (YAML file-backed), default_agent_id é campo
+ --   flat no dataclass Tenant (type-safe no startup). Na Fase 3 (Postgres),
+ --   este campo JSONB será migrado para coluna tipada.
```

### D5 — Decision Drift

Nenhuma contradicao detectada entre decisoes do epic 004 e ADRs aceitos:

- **ADR-001 (pydantic)**: Decisao 4 usa discriminated union pydantic 2 — **consistente**
- **ADR-003 (Redis)**: Decisao 5 usa Redis MGET para state lookup — **consistente**
- **ADR-006 (Agent-as-Data)**: Decisoes 6, 8, 9 usam regras YAML por tenant com agent resolution — **consistente** (ADR-006 define routing configuravel; epic 004 implementa como YAML, epic 006 migrara para DB)
- **ADR-011 (RLS Multi-Tenant)**: Nao se aplica diretamente (config em YAML, nao DB) — **sem conflito**
- **ADR-017 (Secrets Management)**: Config YAML nao contem secrets — **sem conflito**

### D6 — Roadmap Drift

| # | ID | Affected Doc | Current State | Expected State | Severity |
|---|-----|-------------|---------------|----------------|----------|
| 8 | D6.1 | `planning/roadmap.md:66` | Epic 003: **drafted** | Epic 003: **shipped** (pre-requisito do 004 que esta em andamento) | medium |
| 9 | D6.2 | `planning/roadmap.md:67` | Epic 004: **drafted** | Epic 004: **in-progress** (branch ativa, L2 cycle em reconcile) | medium |

**Revisao detalhada do roadmap:**

| Campo | Planejado (roadmap) | Atual (epic 004) | Drift? |
|-------|-------------------|-------------------|--------|
| Status | drafted | in-progress (L2 cycle quase completo) | **SIM** — atualizar para in-progress |
| Milestone | MVP | MVP | Nao |
| Estimativa | 1 semana | Em andamento (~1 semana correto) | Nao |
| Dependencias | 003 | 003 (confirmado como pre-requisito) | Nao |
| Riscos | "Router nao-MECE hardcoded bloqueia agent resolution" | **Mitigado** — 4 camadas MECE provadas, 947 testes | **SIM** — atualizar status do risco |

**Diff concreto para D6.1 + D6.2** (roadmap.md, epic table):

```diff
- | 3 | 003: Multi-Tenant Foundation (auth + parser reality + deploy) | 002 | medio | MVP | **drafted** (pitch em epics/003-multi-tenant-foundation/) |
- | 4 | 004: Router MECE | 003 | medio | MVP | **drafted** (pitch em epics/004-router-mece/) |
+ | 3 | 003: Multi-Tenant Foundation (auth + parser reality + deploy) | 002 | medio | MVP | **shipped** |
+ | 4 | 004: Router MECE | 003 | medio | MVP | **in-progress** (branch epic/prosauai/004-router-mece, L2 cycle) |
```

**Diff concreto para risco** (roadmap.md, riscos):

```diff
- | Router nao-MECE hardcoded bloqueia agent resolution | **Endereçado (epic 004 draft)** | Alto | — | `classify()` puro + `RoutingEngine` declarativa + garantias MECE em 4 camadas (tipo/schema/runtime/CI) |
+ | Router nao-MECE hardcoded bloqueia agent resolution | **Mitigado (epic 004 in-progress)** | Baixo | — | `classify()` puro + `RoutingEngine` declarativa + garantias MECE em 4 camadas (tipo/schema/runtime/CI). 947 testes passando, 26 fixtures reais com equivalencia comportamental comprovada |
```

**Diff concreto para L2 status** (roadmap.md, status):

```diff
- **L2 Status:** Epic 001 shipped (52 tasks, 122 testes, judge 92%, QA 97%). Epic 002 in-progress. Epics 003 e 004 drafted.
+ **L2 Status:** Epic 001 shipped (52 tasks, 122 testes, judge 92%, QA 97%). Epic 002 shipped. Epic 003 shipped. Epic 004 in-progress (51 tasks, 947 testes, judge 90%, QA 96%).
```

**Diff concreto para progresso MVP** (roadmap.md):

```diff
- **Progresso MVP:** 20% (001 entregue; 002 in-progress; 003, 004, 005 pendentes)
+ **Progresso MVP:** 60% (001 shipped; 002 shipped; 003 shipped; 004 in-progress; 005 pendente)
```

### D7 — Future Epic Drift

| Epic | Pitch Assumption | Como Afetado | Impacto | Acao Necessaria |
|------|-----------------|-------------|---------|-----------------|
| 005: Conversation Core | Espera receber `agent_id` do router para saber qual modelo/prompt usar | **Positivo** — epic 004 resolve `agent_id` corretamente. `Decision.agent_id` (em `RespondDecision`) esta disponivel. Contrato `handoff:{tenant_id}:{sender_key}` documentado como aberto para 005 escrever. | Baixo | Nenhuma — 005 consome `RespondDecision.agent_id` diretamente |
| 006: Configurable Routing DB | Originalmente planejado para criar routing engine + DB | **Simplificado drasticamente** — epic 004 ja entregou RoutingEngine + loader YAML. Epic 006 so precisa trocar o loader de YAML para tabela `routing_rules`. | Alto (positivo) | Atualizar descricao do epic 006 no roadmap para refletir escopo reduzido |
| 009: Trigger Engine | Depende de routing rules configuráveis | **Desacoplado** — trigger engine opera em `routing_rules` separadas das routing rules do M3. Nenhum impacto direto. | Nenhum | Nenhuma |
| 011: Admin Handoff Inbox | Escritor da key Redis `handoff:{tenant_id}:{sender_key}` | **Contrato aberto documentado** — epic 004 le a key com fallback False; epic 011 (ou 005) deve escrever. | Medio | Documentar como pre-requisito: epic 011 deve escrever `handoff:` key |

### D8 — Integration Drift

Nenhum drift detectado. `context-map.md` referencia `InboundMessage → ConversationRequest` ACL — consistente com o rename realizado no epic 004.

### D9 — README Drift

N/A — `platforms/prosauai/README.md` nao existe.

### D10 — Epic Decision Drift

21 decisoes em `decisions.md` analisadas:

**Contradicoes com ADRs:** Nenhuma encontrada.

**Candidatos a promocao para ADR de plataforma:**

| # | Decisao | Significativa? | Acao |
|---|---------|---------------|------|
| 1 | Dec #3: Hit policy UNIQUE (overlap = ERROR) | Sim — afeta todos os epics futuros que adicionem routing rules | Candidata a ADR. Impacto cross-epic. |
| 3 | Dec #14: Garantias MECE em 4 camadas | Sim — define padrao de qualidade para todo o router | Pode ser documentada como extensao do ADR-006 |
| 17 | Dec #17: default_agent_id flat (nao JSONB) | Sim — contradiz SQL schema no domain-model (JSONB settings) | Drift D4.4 ja flagado acima. Quando epic 013 migrar, resolver. |

**Staleness:** Nenhuma decisao stale. Todas as 21 decisoes refletem o estado atual do codigo conforme confirmado pelo Judge (90%) e QA (96%).

---

## Revisao do Roadmap (Obrigatoria)

### Epic Status Table

| Campo | Planejado | Atual | Drift? |
|-------|----------|-------|--------|
| Epic 004 status | drafted | in-progress (L2 cycle: judge + qa + reconcile completos) | **SIM** |
| Appetite planejado | 1 semana | ~1 semana (correto) | Nao |
| Milestone | MVP | MVP | Nao |
| Dependencias | 003 | 003 (shipped, confirmado) | **SIM** — 003 ja shipped, nao drafted |

### Dependencias Descobertas

| De | Para | Tipo | Descoberta em |
|----|------|------|--------------|
| 004 | 005 | `RespondDecision.agent_id` — contrato de saida | pitch (confirmado pela implementacao) |
| 004 | 005/011 | `handoff:{tenant_id}:{sender_key}` Redis key — contrato aberto | pitch + implementacao (StateSnapshot fallback False) |
| 004 | 006 | RoutingEngine + loader — 006 so troca backend (YAML → DB) | pitch (confirmado — escopo do 006 reduzido) |

### Risk Status

| Risco (roadmap) | Status | Detalhes |
|----------------|--------|---------|
| Router nao-MECE hardcoded bloqueia agent resolution | **MITIGADO** | 4 camadas MECE provadas. 947 testes passando. Property tests exaustivos cobrem ~400 combinacoes. |
| Merge conflict entre 003 e 004 | **ELIMINADO** | Epic 003 shipped antes de 004. Sequencia back-to-back sem conflito. |
| Evolution API payload muda | **MITIGADO (001)** | Sem impacto em 004 — classify() consome InboundMessage, nao raw payload. |

### Riscos Novos Descobertos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| `conversation_in_handoff` sempre False ate epic 005/011 escrever a key Redis | Esperado | Baixo | Fallback seguro documentado. Regra `handoff_bypass` no YAML e inativa ate key existir. Teste explicito valida fallback. |
| mypy --strict nao automatizado em CI (W5 do Judge) | Media | Medio | Match/case correto no codigo (5 cases + unreachable guard), mas prova formal nao automatizada. Adicionar ao CI como prioridade MEDIA. |

---

## Impacto em Epics Futuros

| Epic | Assumption no Pitch | Como Afetado pelo 004 | Impacto | Acao |
|------|--------------------|-----------------------|---------|------|
| 005: Conversation Core | `agent_id` disponivel apos roteamento | ✅ Resolvido — `RespondDecision.agent_id` sempre preenchido | Positivo | Nenhuma |
| 006: Configurable Routing DB | Precisa criar engine de routing | ✅ Engine ja entregue — 006 so troca loader YAML→DB | **Alto (escopo reduzido)** | Atualizar descricao do 006 no roadmap |
| 011: Admin Handoff Inbox | Operador marca conversa como handoff | Contrato aberto: 011 deve escrever `handoff:{tenant_id}:{sender_key}` no Redis | Medio | Documentar como requisito do 011 |
| 013: TenantStore Postgres | `default_agent_id` em JSONB settings | Epic 004 usa flat field. Migracao deve preservar campo flat ou migrar para coluna tipada | Baixo | Nenhuma agora — decisao adiada |

---

## Auto-Review

### Tier 1 — Checks Deterministicos

| # | Check | Resultado |
|---|-------|----------|
| 1 | Report file exists and is non-empty | PASS |
| 2 | All 10 drift categories scanned (D1-D10) | PASS — todas as 10 categorias presentes |
| 3 | Drift Score computed | PASS — 50% (5/10 docs current) |
| 4 | No placeholder markers remain | PASS — zero TODO/TKTK/???/PLACEHOLDER |
| 5 | HANDOFF block present at footer | PASS |
| 6 | Impact Radius matrix present | PASS |
| 7 | Roadmap review section present | PASS |

### Tier 2 — Scorecard

| # | Item | Self-Assessment |
|---|------|----------------|
| 1 | Todo drift item tem current vs expected state | Sim — todos os 12 items com before/after |
| 2 | Roadmap review com actual vs planned | Sim — tabela completa |
| 3 | Contradicoes ADR flagadas com recomendacao | Sim — nenhuma contradicao, 3 candidatos a promocao identificados |
| 4 | Impacto em epics futuros avaliado (top 5) | Sim — 4 epics analisados |
| 5 | Diffs concretos fornecidos | Sim — diffs em formato diff para todos os docs |
| 6 | Trade-offs explicitos para cada proposta | Parcial — propostas sao diretas (atualizacao documental, sem alternativas reais) |
| 7 | Confianca e kill criteria | Sim — no HANDOFF block |

---

## Sumario de Propostas

| # | ID | Categoria | Doc Afetado | Severidade | Proposta |
|---|-----|----------|-------------|------------|---------|
| 1 | D2.1 | Architecture | blueprint.md:130 | medium | Rename `ParsedMessage` → `InboundMessage` na folder structure |
| 2 | D2.2 | Architecture | blueprint.md:131 | medium | Substituir `router.py` por `router/` package na folder structure |
| 3 | D3.1 | Container | containers.md:214 | low | Adicionar nota sobre rename e modulo router |
| 4 | D4.1 | Domain | domain-model.md:67-75 | **high** | Substituir `RouteDecision` enum por `Action` enum + `MessageFacts` dataclass |
| 5 | D4.2 | Domain | domain-model.md:88-96 | **high** | Substituir metodos `Router` por `classify()` puro + `RoutingEngine.decide()` |
| 6 | D4.3 | Domain | domain-model.md:77-86 | **high** | Substituir `RoutingRule` entity por `Rule` frozen dataclass + YAML config |
| 7 | D4.4 | Domain | domain-model.md:162-164 | medium | Adicionar nota sobre `default_agent_id` flat vs JSONB |
| 8 | D6.1 | Roadmap | roadmap.md:66 | medium | Epic 003: drafted → shipped |
| 9 | D6.2 | Roadmap | roadmap.md:67 | medium | Epic 004: drafted → in-progress |
| 10 | D6.3 | Roadmap | roadmap.md:139 | medium | Risco router MECE: Enderecado → Mitigado |
| 11 | D6.4 | Roadmap | roadmap.md:26 | medium | Progresso MVP: 20% → 60% |
| 12 | D1.1 | Scope | process.md:86-137 | medium | Atualizar Fase B com terminologia do 004 (classify + RoutingEngine + Decision) |

**Total:** 12 propostas (3 high, 8 medium, 1 low)

---

## Licoes do Epic 004

1. **MECE por construcao funciona**: O investimento em 4 camadas de garantia (tipo, schema, runtime, CI) se pagou — property tests pegaram edge cases que testes manuais nao pegariam.

2. **Rip-and-replace > compat layer**: Remover o enum legado no mesmo PR eliminou ambiguidade. As 26 fixtures reais como regression suite deram confianca.

3. **Contrato aberto e poderoso**: Documentar `conversation_in_handoff` como contrato aberto (leitura sem escritor) permitiu modelar o fact corretamente sem esperar epics futuros.

4. **Drift documental e previsivel**: Todo epic que refatora um modulo core gera drift nos mesmos docs (domain-model, blueprint, process). Automatizar deteccao via grep patterns pode reduzir custo do reconcile.

---

handoff:
  from: reconcile
  to: roadmap-reassess
  context: "Reconcile completo. Drift Score 50% — concentrado em docs de engenharia (domain-model, blueprint) e negocio (process.md) que descrevem router com terminologia pre-004. 12 propostas de atualizacao (3 HIGH no domain-model). Roadmap precisa atualizar status de epics 003 (shipped) e 004 (in-progress). Risco router MECE mitigado. Epic 006 escopo reduzido. Contrato aberto handoff key documentado para epic 005/011."
  blockers: []
  confidence: Alta
  kill_criteria: "Se os docs de engenharia (domain-model, blueprint) forem atualizados por outro epic antes deste reconcile ser aplicado, as propostas de diff ficam stale e precisam ser regeneradas."
