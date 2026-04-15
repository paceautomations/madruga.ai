# AgentScope -- Architecture Analysis

> **Repository**: [agentscope-ai/agentscope](https://github.com/agentscope-ai/agentscope)
> **Origin**: Alibaba Tongyi Lab (SysML team) | **License**: Apache-2.0 | **Python**: 3.10+
> **Paper**: arXiv 2402.14034
> **Date**: 2026-04-14

---

## 1. Overview

AgentScope is a **Python-first multi-agent framework** for building LLM-powered agent applications. It provides abstractions for agents, tools, memory, pipelines, and observability -- all async-native. The framework emphasizes flexibility through code-first configuration (no YAML/JSON declarative config) and broad ecosystem integration (MCP, A2A, RAG, finetuning, evaluation).

### Module Map

| Module | Responsibility |
|--------|---------------|
| `agent/` | Agent abstractions: `AgentBase`, `ReActAgent`, `UserAgent`, `A2AAgent`, `RealtimeAgent` |
| `model/` | LLM backends: OpenAI, Anthropic, DashScope, Ollama, Gemini, Trinity |
| `tool/` | `Toolkit` registry + built-in tools (code exec, file ops, multimodal) |
| `memory/` | Working memory (in-memory, Redis, SQLAlchemy, Tablestore) + long-term (Mem0, ReMe) |
| `pipeline/` | Workflow orchestration: `MsgHub`, `SequentialPipeline`, `FanoutPipeline`, `ChatRoom` |
| `mcp/` | MCP client implementations (stdio, HTTP stateful/stateless) |
| `a2a/` | Agent-to-Agent protocol with pluggable resolvers (file, Nacos, well-known) |
| `session/` | State persistence: JSON file, Redis, Tablestore backends |
| `tracing/` | OpenTelemetry-based tracing with granular decorators |
| `evaluate/` | Benchmarking framework with evaluators, metrics, and ACE benchmark |
| `plan/` | Planning notebook abstraction for agent task decomposition |
| `formatter/` | Message format adapters per provider |
| `hooks/` | Pre/post hooks on agent lifecycle |
| `realtime/` | Realtime voice agent support (WebSocket-based) |
| `rag/` | Knowledge base + vector store integrations |
| `tune/` | Model finetuning integration (Trinity-RFT) |

---

## 2. Memory Management

### 2.1 Two-Tier Architecture

AgentScope separates memory into **Working Memory** (short-term conversation buffer) and **Long-Term Memory** (persistent semantic storage). Both are async-first.

#### Working Memory Backends

| Backend | Class | Storage |
|---------|-------|---------|
| In-memory list | `InMemoryMemory` | Python `list[tuple[Msg, list[str]]]` |
| Redis | `RedisMemory` | Redis lists/sets, scoped by `user_id:session_id` |
| SQL (any) | `AsyncSQLAlchemyMemory` | SQLAlchemy async ORM (SQLite, Postgres, MySQL) |
| Tablestore | `TablestoreMemory` | Alibaba Tablestore |

All implement: `add`, `delete`, `delete_by_mark`, `get_memory`, `clear`, `size`. Messages are tagged with "marks" -- arbitrary string labels for filtering (e.g., `COMPRESSED`, `HINT`).

**Isolation**: Redis and SQLAlchemy scope operations to `(user_id, session_id)`. In-memory is per-agent-instance.

#### Long-Term Memory Backends

| Backend | Library | Storage |
|---------|---------|---------|
| **Mem0** | `mem0ai` | Qdrant vector store (on-disk) |
| **ReMe** | `reme-ai` | DashScope/OpenAI-backed semantic memory |

**Mem0** features:
- Uses 3-tier fallback strategy for recording: user-role -> assistant-role -> raw (no extraction)
- Retrieval is keyword-based semantic search via parallel async queries
- Extracts knowledge graph relations (`source -- relationship -- destination`)
- Scoped by `agent_id`, `user_id`, `run_id`

**ReMe** provides 3 specialized subclasses:
- `ReMePersonalLongTermMemory` -- user preferences, habits
- `ReMeTaskLongTermMemory` -- execution trajectories, task learnings
- `ReMeToolLongTermMemory` -- tool execution patterns

**Long-term memory modes** (on `ReActAgent`):
- `agent_control` -- agent decides when to record/retrieve via tool calls
- `static_control` -- automatic retrieval on input, automatic recording after reply
- `both` -- both modes active

### 2.2 Compression / Eviction

The `ReActAgent` implements `_compress_memory_if_needed`:
- **Trigger**: when token count of uncompressed messages exceeds `compression_config.trigger_threshold`
- **Strategy**: keeps recent N messages, generates structured summary via LLM
- **Summary schema**: `task_overview`, `current_state`, `important_discoveries`, `next_steps`, `context_to_preserve` (each capped at 200-300 chars)
- **Supports separate compression model** (e.g., cheaper model for summarization)
- Old messages marked with `_MemoryMark.COMPRESSED` and excluded from prompts
- Summary prepended as system message on retrieval

This is **eviction-by-summarization** -- not windowing or truncation.

### 2.3 RAG Integration

Separate from memory, with `KnowledgeBase` abstract class:
- **Vector stores**: Qdrant, MilvusLite, OceanBase, MongoDB, Alibaba Cloud MySQL
- **Document readers**: Text, PDF, Image, Word, Excel, PowerPoint
- Integrated into `ReActAgent._retrieve_from_knowledge()` -- retrieves on each input, optionally rewrites query via LLM
- RAG and long-term memory are independent systems

---

## 3. Hook System

### 3.1 Two-Level Hooks (Class + Instance)

Implemented via metaclass `_AgentMeta` which automatically wraps `reply()`, `observe()`, `print()` at class creation time.

**6 hook points on AgentBase**:
- `pre_reply` / `post_reply`
- `pre_print` / `post_print`
- `pre_observe` / `post_observe`

**4 extended hooks for ReAct agents**:
- `pre__reasoning` / `post__reasoning`
- `pre__acting` / `post__acting`

### 3.2 Registration API

```python
# Class-level (all instances)
AgentBase.register_class_hook(hook_type, name, callable)

# Instance-level (one agent)
agent.register_instance_hook(hook_type, name, callable)
```

- Hooks stored in `OrderedDict`, executed in insertion order
- **Pre-hooks**: receive `(self, kwargs_dict)`, can return modified kwargs (interceptor pattern)
- **Post-hooks**: receive `(self, kwargs_dict, output)`, can return modified output
- Instance hooks execute first, then class hooks
- Built-in hook: `as_studio_forward_message_pre_print_hook` forwards messages to Studio UI

### 3.3 Design Pattern

This is **AOP (Aspect-Oriented Programming)** via Python metaclasses. Zero boilerplate for cross-cutting concerns. The wrapping is automatic and inescapable once the metaclass is applied.

---

## 4. Pipelines and Orchestration

### 4.1 Pipeline Classes

| Pipeline | Behavior |
|----------|----------|
| **SequentialPipeline** | Chain: output of agent N becomes input to agent N+1 |
| **FanoutPipeline** | Broadcast: same input (deep-copied) to all agents, concurrent via `asyncio.gather()` |

**No built-in**: DAG executor, conditional branching, loops, or gate system. Complex workflows require manual Python code.

### 4.2 Multi-Agent Communication

- **MsgHub**: Context-manager pub/sub group. All participants auto-observe each other's replies. Supports dynamic `add()`/`delete()` and manual `broadcast()`.
- **ChatRoom**: Real-time variant for `RealtimeAgent` instances with event forwarding loop.
- **Subscriber model**: Each agent has `_subscribers` dict; after `reply()`, results broadcast via `observe()`.

### 4.3 Plan Module

`PlanNotebook` with `SubTask`/`Plan` models -- flat sequential task tracking (todo/in_progress/done/abandoned). No dependency graph between subtasks.

---

## 5. Agents and Tools

### 5.1 Built-in Agent Types

| Agent | Purpose |
|-------|---------|
| **AgentBase** | Abstract base. Async-first. Defines `reply()`, `observe()`, hooks, broadcasting. |
| **ReActAgent** | Full implementation: tool calling (parallel), memory compression, structured output, RAG, plan notebook, long-term memory, TTS, streaming. The workhorse. |
| **UserAgent** | Human-in-the-loop. Pluggable input (`TerminalUserInput`, `StudioUserInput`). |
| **A2AAgent** | Agent-to-Agent protocol client. Cross-framework communication. |
| **RealtimeAgent** | Voice/realtime streaming agent. |

### 5.2 Custom Agent Interface

```python
class MyAgent(AgentBase):
    async def observe(self, msg: Msg | list[Msg] | None) -> None: ...
    async def reply(self, *args, **kwargs) -> Msg: ...
```

### 5.3 Toolkit System

Central `Toolkit` class with:
- **Auto-schema**: Parses docstrings into JSON tool schemas automatically
- **Tool groups**: Group-wise activation/deactivation
- **Agent skills**: Directory-based skills with `SKILL.md` files loaded into system prompts
- **MCP clients**: Register tools from any MCP server
- **Middleware chain**: Async generator middlewares wrap tool execution
- **Parallel execution**: `ReActAgent` supports parallel tool calls via `asyncio.gather()`

### 5.4 Built-in Tools

- **Code execution**: `execute_python_code`, `execute_shell_command`
- **File operations**: `view_text_file`, `write_text_file`, `insert_text_file`
- **Multimodality**: Text-to-image, text-to-audio, image-to-text (DashScope + OpenAI)

---

## 6. Token Optimization and Cost Management

### 6.1 Token Counting

Dedicated `token/` module with provider-specific counters:
- **OpenAI**: `tiktoken`-based, including vision token calculations (tile-based for GPT-4o)
- **Anthropic**, **Gemini**, **HuggingFace**, **Char-based**: separate implementations
- Usage tracked per-call via `ChatUsage` (input_tokens, output_tokens, time)

### 6.2 Context Window Management

Primary strategy is **memory compression** (see section 2.2). No prompt caching, no prefix ordering optimization, no context windowing beyond the compression threshold.

### 6.3 Model Providers (6)

| Class | Provider |
|-------|---------|
| `OpenAIChatModel` | OpenAI + Azure OpenAI + Qwen-omni |
| `AnthropicChatModel` | Anthropic Claude (including extended thinking) |
| `GeminiChatModel` | Google Gemini |
| `DashScopeChatModel` | Alibaba DashScope |
| `OllamaChatModel` | Ollama (local models) |
| `TrinityChatModel` | Trinity |

### 6.4 Caching

- **Embedding cache only**: `FileEmbeddingCache` with SHA-256 hashed filenames, LRU eviction
- **No LLM response caching**

### 6.5 Retry / Rate Limiting

**Minimal**: No framework-level retry or rate limiting. Delegated to underlying SDK clients (openai, anthropic libraries).

---

## 7. Observability

### 7.1 Logging

Standard Python `logging` module with named logger `"as"`, configurable level and file output.

### 7.2 Tracing

Full **OpenTelemetry** integration via OTLP HTTP exporter with granular trace decorators:
- `trace_llm` -- LLM API calls
- `trace_reply` -- agent reply lifecycle
- `trace_format` -- message formatting
- `trace_toolkit` -- tool execution
- `trace_embedding` -- embedding calls

Compatible with Phoenix, Langfuse, and AgentScope Studio's built-in trace viewer.

### 7.3 Evaluation

Built-in benchmark framework under `evaluate/` with pluggable evaluators, metrics, and storage. Includes the ACE benchmark.

### 7.4 Studio

Web UI connected via `studio_url` parameter. Agents push messages to it; `StudioUserInput` receives input. Provides message visualization, trace viewing, and interactive debugging.

---

## 8. Configuration and Distribution

### 8.1 Configuration

**Code-first** via `agentscope.init()` -- no YAML/JSON config files. Runtime state uses `ContextVar`-backed config (thread-safe, async-safe).

### 8.2 Distribution

- **A2A protocol**: Expose agents as A2A servers for cross-framework communication
- **Service discovery**: Nacos, file-based, well-known URIs
- No standalone CLI binary -- interaction is Python-API-driven

### 8.3 Session Persistence

`SessionBase` with backends: JSON file, Redis, Tablestore. Enables checkpoint/restore of agent state.

---

## 9. Design Patterns Summary

| Pattern | Where |
|---------|-------|
| **AOP via Metaclass** | Hook system (`_AgentMeta`) |
| **Template Method** | `AgentBase.reply()` / `ReActAgentBase._reasoning()/_acting()` |
| **Strategy** | Memory backends, session backends, model backends |
| **Registry** | `Toolkit` for tools, `formatter/` for message adapters |
| **Observer/Pub-Sub** | `MsgHub`, subscriber broadcasting |
| **State Module** | Serializable agent state for session persistence |

---

## 10. Strengths and Weaknesses

### Strengths

1. **Elegant hook system**: Metaclass-based AOP with zero boilerplate for cross-cutting concerns
2. **Async-native**: ContextVar-based config is async/thread safe -- superior to global singletons
3. **First-class OTel tracing**: Granular span types integrated at every layer
4. **Broad ecosystem**: MCP, A2A, realtime voice, finetuning, RAG, evaluation all in one framework
5. **Clean provider separation**: `formatter/` adapters isolate model-specific message formatting
6. **Two-tier memory**: Clean separation of working memory vs. long-term semantic memory
7. **Compression strategy**: LLM-powered summarization with structured schema

### Weaknesses

1. **No declarative configuration**: Everything is Python code -- limits no-code/low-code use cases
2. **No DAG orchestration**: Only sequential and fan-out pipelines. No conditional branching, loops, or gates
3. **No retry/rate limiting**: Framework delegates entirely to SDK clients
4. **No LLM response caching**: Only embedding cache exists
5. **No prompt caching optimization**: No prefix ordering or API-level cache strategies
6. **Heavy dependency footprint**: anthropic, dashscope, openai, tiktoken, sounddevice, numpy all required
7. **Flat test structure**: No separation of unit vs integration tests
8. **ReActAgent complexity**: 600+ LOC with acknowledged need for simplification
