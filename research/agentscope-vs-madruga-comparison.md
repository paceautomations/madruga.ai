# AgentScope vs madruga.ai -- Comparative Analysis

> **Date**: 2026-04-14
> **Purpose**: Identify improvement opportunities by comparing architectural approaches

---

## 1. Executive Summary

AgentScope and madruga.ai solve **different problems with overlapping concerns**:
- **AgentScope**: General-purpose multi-agent framework (library) for building LLM applications
- **madruga.ai**: Domain-specific architectural documentation pipeline (system) with 25-skill DAG orchestration

Despite different scopes, both tackle memory management, hooks, orchestration, token optimization, observability, and tool integration. Each has clear strengths the other lacks.

---

## 2. Comparison Matrix

| Dimension | AgentScope | madruga.ai | Winner |
|-----------|-----------|------------|--------|
| **Orchestration** | Sequential + Fan-out only. No DAG, no gates, no conditional branching | 25-node DAG with topological sort, 4 gate types, checkpoint/resume, phase dispatch | **madruga.ai** |
| **Memory -- Working** | 4 backends (in-memory, Redis, SQLAlchemy, Tablestore) with mark/tag system | File-based (Markdown) + SQLite bidirectional sync via PostToolUse hooks | **AgentScope** |
| **Memory -- Long-term** | Mem0 (Qdrant) + ReMe with 3 specialized subtypes. Agent-controlled or automatic | Claude Code auto-memory (.md files) + DB sync. No vector/semantic search | **AgentScope** |
| **Memory Compression** | LLM-powered summarization with structured schema (`SummarySchema`) and configurable threshold | Prompt prefix caching (MADRUGA_CACHE_ORDERED), context windowing, scoped context filtering | **Tie** (different strategies) |
| **Hook System** | Metaclass-based AOP: 10 hook points (reply/observe/print + reasoning/acting), class + instance level | PostToolUse shell hooks: post_save, skill_lint, validate_placement, sync_memory | **AgentScope** (programmatic) |
| **Token Optimization** | Per-provider token counters, compression threshold trigger. No prompt caching | Prefix cache ordering (Phase 5), scoped context filtering, cost tracking per dispatch, session resume caps | **madruga.ai** |
| **Cost Tracking** | `ChatUsage` per call (input/output tokens, time). No aggregation | Full cost pipeline: per-dispatch tokens, cache read/creation, USD estimation, trend analysis in DB | **madruga.ai** |
| **Observability** | OTel tracing (5 span types), Studio UI, evaluation framework | structlog + journald, trace/span model in SQLite, portal API, 90-day retention, Telegram alerts | **Tie** (AgentScope broader; madruga deeper ops) |
| **Agent Types** | 5 built-in (ReAct, User, A2A, Realtime, base). Extensible via subclassing | 25 skills as Claude Code slash commands. Personas per pipeline layer | **AgentScope** (programmatic agents) |
| **Tool Integration** | Toolkit registry with auto-schema from docstrings, MCP clients, middleware chain | Per-node tool restrictions (`--tools`), skill-level tool contracts, MCP via Claude Code | **AgentScope** (richer framework) |
| **Multi-Agent Communication** | MsgHub (pub/sub), subscriber model, ChatRoom | Dispatch-based (isolated subprocesses), no inter-agent messaging | **AgentScope** |
| **Configuration** | Code-first (`agentscope.init()`), ContextVar-backed | Declarative (YAML manifests, pipeline.yaml, env vars, settings.json) | **madruga.ai** (declarative > code-first for ops) |
| **RAG** | KnowledgeBase with 5 vector stores, 6 document readers, query rewriting | None (relies on Claude Code's built-in context + skill knowledge files) | **AgentScope** |
| **Retry/Resilience** | None at framework level (delegates to SDK) | Exponential backoff, circuit breaker (deterministic/transient/unknown), zombie sweep | **madruga.ai** |
| **Gate/Approval System** | None | 4 types: human, auto, 1-way-door, auto-escalate. Per-decision confirmation | **madruga.ai** |
| **Distribution** | A2A protocol, Nacos discovery, multi-process | Single-machine daemon (easter), branch isolation per epic | **AgentScope** |
| **Evaluation** | Built-in benchmark framework (evaluators, metrics, ACE benchmark) | Judge skill (4 personas + judge pass), reconcile drift detection | **AgentScope** (formal framework) |
| **Finetuning** | Trinity-RFT integration | None | **AgentScope** |
| **Voice/Realtime** | RealtimeAgent with WebSocket support | None | **AgentScope** |

---

## 3. What AgentScope Does Better

### 3.1 Memory Architecture (HIGH PRIORITY)

**Gap**: madruga.ai has no vector/semantic memory, no structured long-term memory, and no agent-controlled memory modes.

**What AgentScope offers**:
- Two-tier memory (working + long-term) with 4 working memory backends
- Mem0 integration for vector-based semantic retrieval with knowledge graph extraction
- ReMe integration with 3 specialized memory types (personal, task, tool)
- Agent-controlled vs. automatic memory modes
- Message marking/tagging system for fine-grained memory management

**Opportunity**: Implement a structured long-term memory system for madruga.ai pipelines. Currently, memory is flat Markdown files with SQLite sync. A vector-backed semantic memory could help the pipeline learn from past epic executions (e.g., "what worked in epic 003 that's similar to this new epic?").

### 3.2 Programmatic Hook System (MEDIUM PRIORITY)

**Gap**: madruga.ai hooks are shell-based PostToolUse scripts -- powerful but limited to file-save events with no programmatic interception of agent behavior.

**What AgentScope offers**:
- 10 hook points covering the full agent lifecycle (pre/post reply, observe, print, reasoning, acting)
- Both class-level and instance-level registration
- Hooks can **modify** inputs and outputs (interceptor pattern)
- Metaclass-based -- automatic and inescapable

**Opportunity**: For prosauai (the runtime agent platform), adopt a programmatic hook system that allows middleware-style interception of agent conversations. The current shell hooks work well for the documentation pipeline but would be insufficient for a production agent runtime.

### 3.3 Multi-Agent Communication (MEDIUM PRIORITY)

**Gap**: madruga.ai dispatches skills as isolated subprocesses. No inter-agent messaging, pub/sub, or shared context during execution.

**What AgentScope offers**:
- MsgHub for group conversations with auto-broadcast
- Subscriber model for reactive inter-agent communication
- ChatRoom for real-time multi-agent scenarios

**Opportunity**: For complex epics where multiple skills need to share context (e.g., implement + judge running iteratively), a pub/sub mechanism could reduce redundant context loading.

### 3.4 RAG / Knowledge Base (MEDIUM PRIORITY)

**Gap**: madruga.ai relies entirely on Claude Code's built-in context window + knowledge files. No vector search, no document retrieval beyond skill knowledge.

**What AgentScope offers**:
- `KnowledgeBase` with 5 vector store backends
- 6 document readers (PDF, Word, Excel, PowerPoint, Image, Text)
- Query rewriting for better recall
- Integrated into agent reasoning loop

**Opportunity**: As platforms accumulate documentation (ADRs, specs, blueprints, epic artifacts), a RAG layer could enable semantic search across the entire documentation corpus, improving context relevance for downstream skills.

### 3.5 Formal Evaluation Framework (LOW PRIORITY)

**Gap**: madruga.ai has the Judge skill (4 personas) and reconcile, but no formal benchmarking or metrics framework.

**What AgentScope offers**:
- Pluggable evaluators with standardized metrics
- ACE benchmark for agent capabilities
- Storage-backed evaluation results

**Opportunity**: Build an eval framework that tracks Judge scores over time, enabling regression detection across epic cycles.

### 3.6 A2A / Distribution (LOW PRIORITY for now)

**Gap**: madruga.ai is single-machine (easter daemon). No cross-machine agent communication.

**What AgentScope offers**:
- Google's Agent-to-Agent protocol
- Service discovery (Nacos, file-based, well-known URIs)
- Multi-process support

**Opportunity**: Future consideration for scaling madruga.ai across teams or enabling external agent systems to participate in the pipeline.

---

## 4. What madruga.ai Does Better

### 4.1 DAG Orchestration (AgentScope's biggest gap)

**madruga.ai advantage**: Full 25-node DAG with topological sort, dependency tracking, 4 gate types (human/auto/1-way-door/auto-escalate), checkpoint/resume, phase dispatch, and retry with circuit breakers.

**AgentScope limitation**: Only `SequentialPipeline` and `FanoutPipeline`. No conditionals, no gates, no checkpointing. Complex workflows require manual Python code.

**Impact**: AgentScope cannot express workflows like "run specify, then clarify, then plan (which depends on clarify), pause for human approval, then proceed to tasks." This is madruga.ai's core strength.

### 4.2 Declarative Configuration

**madruga.ai advantage**: `pipeline.yaml` defines the entire DAG declaratively. `platform.yaml` declares platform metadata. Environment variables provide runtime knobs with documented kill-switches.

**AgentScope limitation**: Everything is code-first via `agentscope.init()`. No YAML/JSON config. Limits no-code/low-code adoption and makes pipeline modification require code changes.

### 4.3 Token Cost Optimization (Prompt Caching)

**madruga.ai advantage**: Phase 5 prefix cache ordering (`MADRUGA_CACHE_ORDERED`) reorders prompt sections to maximize Claude API's 1-hour TTL prefix cache. Tracks `cache_read_input_tokens` vs. `cache_creation_input_tokens` empirically. Context scoping (`MADRUGA_SCOPED_CONTEXT`) filters irrelevant sections. Session resume caps at 700k tokens.

**AgentScope limitation**: No prompt caching awareness. No prefix ordering. No context scoping. Only has compression (summarization) as a cost strategy.

**Impact**: For multi-task epics (tasks 2..N within the same dispatch), madruga.ai gets significant cache hits because stable context (spec, plan, data model) is force-included at the prompt start. AgentScope pays full price on every call.

### 4.4 Retry and Resilience

**madruga.ai advantage**: `dispatch_with_retry_async` with exponential backoff, 3-class error classification (deterministic/transient/unknown), different retry limits per class, zombie sweep, and escalation to human.

**AgentScope limitation**: Zero framework-level retry. Delegates entirely to SDK client libraries.

### 4.5 Gate/Approval System

**madruga.ai advantage**: 4 gate types with per-decision confirmation for irreversible choices (1-way-door). Telegram notifications for pending gates. Auto-escalate for conditional human involvement.

**AgentScope limitation**: No gate or approval system. Human involvement is only through `UserAgent` (inline input), not workflow-level gates.

### 4.6 Operational Maturity

**madruga.ai advantage**:
- 24/7 daemon (easter) with systemd integration, health checks, degradation modes
- Full cost tracking with USD estimation and trend analysis
- 90-day data retention with backup rotation
- Telegram alerting for gates, errors, and status
- Portal with trace/span visualization

**AgentScope limitation**: Studio UI for development-time debugging. No production operations story (no daemon, no alerting, no cost aggregation).

### 4.7 Skill Contracts and Validation

**madruga.ai advantage**: Every skill follows a uniform 6-section contract (Cardinal Rule, Persona, Usage, Output, Instructions, Auto-Review). Skill-lint validates frontmatter, handoff chains, and archetype compliance. Dedup checks prevent redundant skills.

**AgentScope limitation**: Agents are Python classes with no enforced structure beyond `reply()`. No contract system, no validation, no auto-review.

---

## 5. What's Similar

| Aspect | AgentScope | madruga.ai |
|--------|-----------|------------|
| **Structured output** | Pydantic models for agent output | Markdown templates with YAML frontmatter |
| **Tool restrictions** | Toolkit groups (activate/deactivate) | Per-node `--tools` flag in dispatch |
| **Personas** | Agent-level system prompts | Layer-level behavioral directives (Business/Research/Engineering/Planning) |
| **State persistence** | Session backends (JSON/Redis/Tablestore) | SQLite WAL + checkpoint/resume |
| **OTel integration** | Native tracing decorators | Via prosauai epic (002-observability) |
| **Plan/Task tracking** | PlanNotebook with SubTask | tasks.md + phase dispatch |

---

## 6. Improvement Opportunities for madruga.ai

### HIGH PRIORITY

| # | Opportunity | Inspired by | Effort | Impact |
|---|-----------|-------------|--------|--------|
| 1 | **Semantic memory for pipeline learning** | AgentScope's Mem0/ReMe long-term memory | Large | Pipeline skills could learn from past epic outcomes. "Epic 003 had a similar domain model -- here's what worked." |
| 2 | **Structured compression for dispatch context** | AgentScope's `CompressionConfig` + `SummarySchema` | Medium | When context exceeds threshold, generate structured summary instead of current truncation. Better than losing context silently. |
| 3 | **Programmatic hooks for prosauai runtime** | AgentScope's metaclass-based hook system | Medium | prosauai agents need pre/post reply hooks for middleware (auth, rate limiting, tenant isolation, tracing). Shell hooks insufficient. |

### MEDIUM PRIORITY

| # | Opportunity | Inspired by | Effort | Impact |
|---|-----------|-------------|--------|--------|
| 4 | **RAG over documentation corpus** | AgentScope's KnowledgeBase | Medium | Semantic search across all platform artifacts (ADRs, specs, blueprints). Improves context relevance for downstream skills. |
| 5 | **Agent-controlled memory modes** | AgentScope's `long_term_memory_mode` | Small | Let skills choose when to record/retrieve from long-term memory instead of always-automatic sync. |
| 6 | **Toolkit auto-schema from docstrings** | AgentScope's `Toolkit` class | Small | Auto-generate tool schemas from Python docstrings. Reduces manual tool definition boilerplate. |
| 7 | **Formal eval metrics framework** | AgentScope's `evaluate/` module | Medium | Track Judge scores, reconcile drift scores, and cache hit rates as time-series metrics with regression alerts. |

### LOW PRIORITY (Future consideration)

| # | Opportunity | Inspired by | Effort | Impact |
|---|-----------|-------------|--------|--------|
| 8 | **Inter-skill messaging** | AgentScope's MsgHub | Large | For iterative skill loops (implement <-> judge), reduce context reload overhead via shared message bus. |
| 9 | **A2A protocol support** | AgentScope's A2A module | Large | Enable external agent systems to participate in the pipeline (e.g., customer's agents triggering epics). |
| 10 | **Embedding cache** | AgentScope's `FileEmbeddingCache` | Small | If/when RAG is implemented, cache embeddings with LRU eviction. |

---

## 7. What madruga.ai Should NOT Copy

| Aspect | Why not |
|--------|---------|
| **Code-first-only configuration** | madruga.ai's declarative YAML pipeline is a strength. Code-first is harder to audit, version, and operate. |
| **No retry at framework level** | madruga.ai's circuit breaker + error classification is superior. Don't regress. |
| **No gate system** | Gates are essential for the documentation pipeline's human-in-the-loop quality assurance. |
| **Heavy dependency footprint** | AgentScope requires anthropic, dashscope, openai, tiktoken, numpy, sounddevice in core. madruga.ai's stdlib + pyyaml philosophy is better for reliability. |
| **Flat test structure** | madruga.ai's test organization is already better. |

---

## 8. Conclusion

**AgentScope excels as an agent runtime** -- rich memory abstractions, programmatic hooks, multi-agent communication, and broad provider support. Its weakness is orchestration (no DAG, no gates, no resilience).

**madruga.ai excels as an orchestration system** -- sophisticated DAG pipeline, declarative configuration, cost optimization, operational maturity. Its weakness is agent-level abstractions (no semantic memory, no programmatic hooks, no inter-agent communication).

The two systems are **complementary, not competing**. The highest-value improvements for madruga.ai are:
1. Adopting AgentScope-inspired semantic memory for pipeline learning
2. Building programmatic hooks for the prosauai runtime (not replacing shell hooks for the documentation pipeline)
3. Adding RAG over the documentation corpus as it grows

These improvements address real gaps without sacrificing madruga.ai's strengths in orchestration, cost control, and operational maturity.
