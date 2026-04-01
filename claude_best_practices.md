# Claude Code CLI — Architecture Benchmark & Best Practices

> **Source**: [`chatgptprojects/clear-code`](https://github.com/chatgptprojects/clear-code/tree/642c7f944bbe5f7e57c05d756ab7fa7c9c5035cc) — TypeScript source extracted from `@anthropic-ai/claude-code` v2.1.88 npm package (source map unpack).
>
> **Purpose**: Complete architectural analysis — patterns, principles, security model, and engineering best practices from one of the most sophisticated CLI tools ever built.
>
> **Stats**: ~2,215 files | TypeScript + React (Ink) | Bun bundler | Zero runtime dependencies

---

## Table of Contents

1. [Codebase Map](#1-codebase-map)
2. [Core Architecture](#2-core-architecture)
3. [Tool System](#3-tool-system)
4. [Permission & Security Model](#4-permission--security-model)
5. [Agent System](#5-agent-system)
6. [MCP (Model Context Protocol)](#6-mcp-model-context-protocol)
7. [Context & Memory Systems](#7-context--memory-systems)
8. [Conversation Management](#8-conversation-management)
9. [UI Architecture (Ink/React CLI)](#9-ui-architecture-inkreact-cli)
10. [Command & Skill System](#10-command--skill-system)
11. [Plugin System](#11-plugin-system)
12. [Configuration & Settings](#12-configuration--settings)
13. [Bridge System (Remote/IDE)](#13-bridge-system-remoteide)
14. [Telemetry & Analytics](#14-telemetry--analytics)
15. [Error Handling](#15-error-handling)
16. [Performance Engineering](#16-performance-engineering)
17. [Catalog of Patterns & Principles](#17-catalog-of-patterns--principles)
18. [Lessons for Our Codebase](#18-lessons-for-our-codebase)

---

## 1. Codebase Map

```
src/
├── Tool.ts                    # Core tool interface (40+ methods, Zod schemas)
├── Task.ts                    # Background task lifecycle (7 types, 5 states)
├── QueryEngine.ts             # LLM conversation loop (async generator, budget control)
├── commands.ts                # Command registry (~100 commands, 6 sources)
├── query.ts                   # Main query loop (10-stage pipeline)
├── tools.ts                   # Tool registry (pool assembly, deny filtering)
│
├── bootstrap/
│   └── state.ts               # Module-scope singleton (~100 fields, latched flags)
│
├── tools/
│   ├── BashTool/              # ~15 files: security, permissions, sandbox, sed validation
│   ├── GlobTool/              # File pattern matching (100-file cap)
│   ├── GrepTool/              # Ripgrep wrapper (pagination, mtime sort)
│   ├── FileReadTool/          # Text, image, PDF, notebook (dedup cache)
│   ├── FileEditTool/          # Exact string replace (10 validation stages)
│   ├── FileWriteTool/         # Create/overwrite (staleness check)
│   ├── AgentTool/             # Sub-agent spawning (fork, worktree, async)
│   ├── NotebookEditTool/      # Jupyter .ipynb editing
│   ├── WebFetchTool/          # URL fetch (86 preapproved domains)
│   ├── WebSearchTool/         # Web search with domain filtering
│   ├── MCPTool/               # MCP tool bridge (runtime override)
│   ├── TodoWriteTool/         # Task list management
│   └── ToolSearchTool/        # Deferred tool discovery (multi-faceted scoring)
│
├── permissions/               # Permission pipeline, rule matching, path validation
├── sandbox/                   # OS-level sandbox (macOS/Linux/WSL2)
├── hooks/                     # Lifecycle hooks (26 event types, 4 hook types)
│
├── agents/                    # Built-in agent definitions
├── services/
│   ├── mcp/                   # MCP client (9 transports, OAuth, XAA, elicitation)
│   ├── api/                   # Multi-provider API client (Direct, Bedrock, Vertex, Foundry)
│   ├── analytics/             # Dual-backend telemetry (Datadog + 1P)
│   ├── compact/               # 4-layer compaction (full, session-memory, micro, API)
│   ├── extractMemories/       # Background memory extraction (forked agent)
│   └── SessionMemory/         # Structured session notes (10 sections)
│
├── skills/
│   ├── bundled/               # 17+ built-in skills (simplify, verify, dream, etc.)
│   └── loadSkillsDir.ts       # Multi-source skill discovery
│
├── plugins/                   # Plugin system (marketplace, policy, deps)
│
├── bridge/                    # Remote/IDE bridge (v1 WebSocket, v2 SSE/CCR)
│
├── cli/
│   ├── print.ts               # Headless mode (5,594 lines)
│   ├── transports/            # SSE, WebSocket, hybrid transport
│   └── structuredIO.ts        # NDJSON streaming
│
├── commands/                  # ~100 slash commands (each as module)
│   ├── compact/               # /compact
│   ├── config/                # /config
│   ├── plugin/                # /plugin (marketplace UI)
│   ├── mcp/                   # /mcp
│   ├── install-github-app/    # GitHub Actions setup wizard
│   └── ...
│
├── components/                # Ink (React for CLI) UI components
│   ├── App.tsx                # Root (3 providers)
│   ├── Messages.tsx           # Virtual scrolling message list
│   ├── Message.tsx            # 6 message types, React Compiler (94-slot cache)
│   ├── Markdown.tsx           # LRU token cache, streaming split
│   ├── PromptInput/           # ~20 files: input, paste, vim, history
│   ├── Spinner/               # Animated glyph, stall detection
│   └── LogoV2/                # Welcome screen, feed, notices
│
├── context/                   # Dynamic context injection
├── memdir/                    # File-based memory (4 types, frontmatter)
├── utils/                     # ~80 utility modules
│   ├── config.ts              # Layered config (global/project/local)
│   ├── claudemd.ts            # CLAUDE.md discovery (4-tier priority)
│   ├── systemPrompt.ts        # System prompt assembly
│   ├── auth.ts                # Multi-source auth (keychain, env, helper)
│   ├── diff.ts                # Structured diff with timeout
│   ├── worktree.ts            # Git worktree management
│   ├── hooks.ts               # Hook execution engine
│   ├── memoize.ts             # TTL, LRU, stale-while-revalidate
│   ├── abortController.ts     # WeakRef parent-child hierarchy
│   └── ...
│
├── constants/                 # Leaf-of-DAG constants (zero imports)
│   ├── toolLimits.ts          # Output size caps
│   ├── files.ts               # Binary extension set (80+ types)
│   ├── errorIds.ts            # Obfuscated error IDs
│   └── oauth.ts               # OAuth configs per environment
│
├── types/                     # TypeScript type definitions
└── entrypoints/
    └── mcp.ts                 # Claude Code as MCP server
```

---

## 2. Core Architecture

### 2.1 Tool Interface — The Universal Contract

Every tool implements a 40+ method interface via `buildTool()` factory:

```typescript
// Fail-closed defaults — security by default
const TOOL_DEFAULTS = {
  isEnabled: () => true,
  isConcurrencySafe: () => false,   // assume NOT safe
  isReadOnly: () => false,           // assume WRITES
  isDestructive: () => false,
  checkPermissions: (input) => Promise.resolve({ behavior: 'allow', updatedInput: input }),
}
```

**Key methods per tool**: `call()`, `description()`, `inputSchema` (Zod), `checkPermissions()`, `prompt()`, `renderToolUseMessage()`, `mapToolResultToToolResultBlockParam()`, `toAutoClassifierInput()`.

**Pattern**: Builder with type-level spread semantics — `buildTool<D>()` preserves literal types through `BuiltTool<D>`.

### 2.2 QueryEngine — Async Generator Conversation Loop

The `QueryEngine` is the orchestrator for non-interactive mode:

```typescript
async *submitMessage(userMessage): AsyncGenerator<SDKMessage> {
  // 1. Process slash commands
  // 2. Build system prompt (custom + memory + append)
  // 3. Wrap canUseTool to track denials
  // 4. Call query() for API loop
  // 5. Yield normalized SDKMessage events
  // 6. Handle transcription and persistence
  // 7. Enforce budget (max turns, USD, structured output retries)
}
```

**Budget enforcement**: Three independent termination conditions — max turns, max USD, structured output retry limit.

### 2.3 Bootstrap State — Controlled Singleton

Module-scope singleton with **100+ fields**, protected by getter/setter pairs:

```typescript
const STATE: State = getInitialState()

// Never exported directly
export function getSessionId(): SessionId { return STATE.sessionId }
export function setCwdState(cwd: string): void { STATE.cwd = cwd.normalize('NFC') }
```

**Layered warnings in source**:
```typescript
// DO NOT ADD MORE STATE HERE - BE JUDICIOUS WITH GLOBAL STATE
// AND ESPECIALLY HERE
// ALSO HERE - THINK THRICE BEFORE MODIFYING
```

**Prompt cache latches**: Sticky-on flags (`afkModeHeaderLatched`, `fastModeHeaderLatched`, etc.) prevent mode toggles from busting the 50-70K token prompt cache.

### 2.4 Task Management — Security-Conscious IDs

```typescript
// Cryptographically random IDs with type prefix
// 36^8 ~ 2.8 trillion combinations — resists symlink attacks
const bytes = randomBytes(8)  // NOT Math.random
```

| Prefix | Type |
|--------|------|
| `b` | bash |
| `a` | agent |
| `r` | remote |
| `t` | teammate |
| `w` | workflow |
| `m` | monitor |
| `d` | dream |

---

## 3. Tool System

### 3.1 Tool Registry — Three-Stage Assembly

```
getAllBaseTools()     → all tools (feature-gated, env-gated)
  ↓
getTools(perms)      → filtered by mode, deny rules, isEnabled()
  ↓
assembleToolPool()   → merged built-in + MCP, sorted for cache stability
```

**Cache stability**: Built-in tools sorted as contiguous prefix — MCP tools appended after. `uniqBy` ensures built-ins win name conflicts.

### 3.2 Output Size Controls

| Constant | Value | Purpose |
|----------|-------|---------|
| `DEFAULT_MAX_RESULT_SIZE_CHARS` | 50,000 | Per-tool default |
| `MAX_TOOL_RESULT_TOKENS` | 100,000 | Hard token cap |
| `MAX_TOOL_RESULT_BYTES` | 400,000 | ~4 bytes/token |
| `MAX_TOOL_RESULTS_PER_MESSAGE_CHARS` | 200,000 | Per-message aggregate |
| GrepTool max | 20,000 | Tighter for search |

### 3.3 Concurrency Model

`isConcurrencySafe()` defaults to `false`. Only read-only tools opt in: Glob, Grep, FileRead, WebFetch, WebSearch. This **prevents race conditions** in file-mutating operations.

### 3.4 Token Efficiency Patterns

| Pattern | Where | Impact |
|---------|-------|--------|
| Path relativization | All filesystem tools | Shorter paths save tokens |
| File dedup (`file_unchanged`) | FileReadTool | Avoids re-sending identical content |
| Deferred tool loading | ToolSearchTool | Schemas loaded on-demand |
| Head limits (default 250) | GrepTool | Bounds search output |
| Max column width (500) | GrepTool | Prevents minified/base64 bloat |

### 3.5 BashTool — The Most Complex Tool (~15 files)

**Multi-layered security**:

1. **`bashSecurity.ts`** — 23 categories of dangerous pattern detection. Parser-differential-aware (handles cases where `shell-quote` and bash parse differently). Detects: command substitution, backtick expansion, process substitution, variable expansion, brace expansion, ANSI-C quoting, Unicode whitespace injection, `\r` misparsing, IFS injection, `/proc/*/environ` access, zsh-specific dangers.

2. **`bashPermissions.ts`** — Hierarchical resolution: exact match > deny > ask > path constraints > security checks > mode-specific. Safe wrapper stripping (`timeout`, `nice`, `nohup`). Environment variable allowlist (blocks `PATH`, `LD_PRELOAD`, `DYLD_*`).

3. **`readOnlyValidation.ts`** — Declarative allowlist for read-only mode. Validates every flag per command. Blocks `$` in any token. Prevents git hook exploitation and UNC credential leaks.

4. **`sedValidation.ts`** — Dedicated parser allowing only `sed -n '1p'` and `s/pattern/replacement/flags`. Rejects `w`, `W`, `e`, `E` flags.

5. **`destructiveCommandWarning.ts`** — 16 patterns: `git reset --hard`, `rm -rf`, `DROP TABLE`, `kubectl delete`, `terraform destroy`, etc.

### 3.6 FileEditTool — 10-Stage Validation Pipeline

1. Secret detection (`checkTeamMemSecrets()`)
2. No-op prevention (old === new rejected)
3. Permission deny rules
4. UNC path security
5. File size limit (>1 GiB rejected)
6. Encoding detection (UTF-16LE vs UTF-8)
7. File existence check
8. Jupyter notebook redirect
9. **Read-before-edit enforcement** (timestamp tracked)
10. **Staleness detection** (mtime comparison, content hash fallback on Windows)

### 3.7 WebFetchTool — Multi-Tier Permission

1. **Preapproved**: 86 domains (Anthropic, language docs, frameworks, cloud providers)
2. **Deny rules**: Block matching hostnames
3. **Ask rules**: Prompt for matching patterns
4. **Allow rules**: User-configured
5. **Default**: Ask

**Cross-host redirects NOT followed** — returns redirect URL, requires explicit new request (prevents SSRF).

---

## 4. Permission & Security Model

### 4.1 Permission Evaluation Pipeline

Strict ordered pipeline — no lower step overrides a higher one:

```
1a. Tool-wide deny rules              → DENY
1b. Tool-wide ask rules               → ASK
1c. Tool-specific checkPermissions()
1d. Tool denied                        → DENY
1e. User interaction required          → ASK (bypass-immune)
1f. Content-specific ask rules         → ASK (bypass-immune)
1g. Safety checks (.git, .claude)      → ASK (bypass-immune)
2a. bypassPermissions mode             → ALLOW
2b. Tool-wide allow rule               → ALLOW
3.  passthrough                        → ASK (default)
```

**Post-pipeline transformations**: `dontAsk` → deny, `auto` → AI classifier, headless → hooks then deny.

### 4.2 Six Permission Modes

| Mode | Behavior |
|------|----------|
| `default` | Standard: tools ask unless explicitly allowed |
| `plan` | Read-only plan mode |
| `acceptEdits` | Auto-allows file edits within working dir |
| `bypassPermissions` | Allows all except bypass-immune checks |
| `dontAsk` | Converts ask → deny (headless) |
| `auto` | AI classifier decides |

### 4.3 Sandbox Architecture

**OS-level isolation**: macOS (Apple Sandbox), Linux (bubblewrap/bwrap), WSL2.

**Critical protections**:
- **Settings file protection**: All `settings.json` paths in `denyWrite` — prevents sandboxed process from modifying its own permissions (escape prevention)
- **Skills directory protection**: `.claude/skills` blocked — skills have command-level privilege
- **Bare git repo attack mitigation**: Denies writes to `HEAD + objects/ + refs/` files and scrubs planted ones after each command
- **Network isolation**: Allowed/denied domains from WebFetch rules

**Auto-allow**: When sandbox enabled, bash commands auto-approve without prompting — sandbox IS the security boundary.

### 4.4 AI Classifier (Auto Mode)

Two-stage classification:
1. **Stage 1**: Fast check
2. **Stage 2**: Extended thinking (if uncertain)

**Safe tool allowlist**: Read-only tools skip classifier entirely.

**Circuit breakers**: 3 consecutive denials → fallback to user. 20 total denials → fallback. Headless → hard stop.

**Iron gate**: Feature flag for fail-open vs fail-closed when classifier API unavailable. Default: **fail-closed** (deny).

### 4.5 Race-to-Resolve Permission Flow

Five approval sources race concurrently:

```
Local UI ──────┐
Bridge (web) ──┤
Channel relay ─┤──→ atomic claim() ──→ first wins
Hooks ─────────┤
Classifier ────┘
```

`createResolveOnce()` provides `resolve`, `isResolved`, `claim` — atomic guard prevents double-resolution. 200ms grace period prevents accidental keypresses.

### 4.6 Path Security — Defense in Depth

- **UNC path blocking**: Every filesystem tool checks `\\\\` and `//` (NTLM credential leak prevention)
- **Case-insensitive comparison**: macOS/Windows bypass prevention
- **Symlink resolution**: Both original and resolved paths checked
- **Windows-specific**: NTFS Alternate Data Streams, 8.3 short names, DOS device names, trailing dots/spaces
- **Dangerous pattern detection**: root/home/drive deletion, wildcard expansion
- **Device file blocking**: `/dev/zero`, `/dev/stdin`, `/dev/tty`
- **Binary file rejection**: 80+ extension blocklist (except PDFs and images)

### 4.7 Hook System

Four hook types: `command` (shell), `prompt` (sub-agent), `agent` (full session), `http` (POST with SSRF protection).

26 lifecycle events: PreToolUse, PostToolUse, PermissionRequest, Stop, SessionStart/End, FileChanged, etc.

**SSRF Guard**: Blocks private IPs but **intentionally allows loopback** (`127.0.0.0/8`) for local dev policy servers. Validates at DNS lookup time to prevent rebinding.

### 4.8 Shadowed Rule Detection

Automatically detects unreachable rules:
- Allow shadowed by broader deny (severe)
- Allow shadowed by broader ask (moderate, except sandboxed bash)

Provides auto-fix suggestions.

---

## 5. Agent System

### 5.1 Built-in Agent Types

| Type | Model | Tools | Purpose |
|------|-------|-------|---------|
| `general-purpose` | inherit | `*` (all) | Complex multi-step tasks |
| `Explore` | haiku | read-only | Fast codebase exploration |
| `Plan` | inherit | read-only | Implementation plan design |
| `verification` | inherit | read-only + /tmp | Adversarial testing |
| `claude-code-guide` | inherit | Bash, Read, WebFetch, WebSearch | Documentation guidance |
| `statusline-setup` | inherit | specific | Shell PS1 → statusline config |

### 5.2 Fork Subagent System — Cache Optimization

Fork agents inherit parent's full context for **prompt cache maximization**:

```typescript
// buildForkedMessages() creates byte-identical API requests
// "Only the final text block differs per child, maximizing cache hits"
```

**Recursion prevention**: `isInForkChild()` detects fork boilerplate in history.

### 5.3 Worktree Isolation

```typescript
createAgentWorktree(slug)     // Lightweight worktree in main repo's .claude/worktrees/
removeAgentWorktree()         // Cleanup worktree + temp branch
hasWorktreeChanges()          // Fail-closed: returns true on git error
```

**Security**: `validateWorktreeSlug()` prevents path traversal with segment-level allowlist.

**Post-creation**: Copies settings, configures hooks, symlinks `node_modules`, copies `.worktreeinclude` files.

### 5.4 Agent Memory — Three Scopes

| Scope | Path | Shared? |
|-------|------|---------|
| `user` | `~/.claude/agent-memory/` | No |
| `project` | `.claude/agent-memory/` | Yes (git) |
| `local` | `.claude/agent-memory-local/` | No |

### 5.5 Resource Cleanup

Comprehensive `finally` block in agent lifecycle:
- MCP client disconnection
- Session hook deregistration
- File state cache release
- Perfetto tracing deregistration
- TodoWrite orphan key removal
- Background shell task termination

---

## 6. MCP (Model Context Protocol)

### 6.1 Nine Transport Types

| Transport | Use Case |
|-----------|----------|
| `stdio` | Local subprocess server |
| `sse` | Server-Sent Events (remote) |
| `http` | HTTP streaming (remote) |
| `ws` | WebSocket (remote) |
| `sse-ide` / `ws-ide` | IDE extension variants |
| `sdk` | In-process SDK servers |
| `claudeai-proxy` | Claude.ai connector (OAuth) |
| `InProcessTransport` | Linked pair via `queueMicrotask()` |
| `SdkControlTransport` | CLI-to-SDK bridge |

### 6.2 Seven Configuration Scopes

```
enterprise (managed, exclusive control)
  > managed (policy)
    > user (global)
      > local (project override)
        > project (.mcp.json)
          > dynamic (plugins)
            > claudeai (connectors)
```

**Deduplication**: Content-based via server signature — stdio: command arrays, remote: URLs.

### 6.3 Connection Lifecycle

1. Two-phase loading (Claude Code configs fast, claude.ai overlapped)
2. All servers start `pending` (or `disabled`)
3. Connection with concurrency limits (separate local vs remote)
4. Reconnection: exponential backoff (max 5 attempts, 30s max)
5. Stale cleanup on plugin reload
6. Batched state updates (16ms flush window)

### 6.4 Authentication

**OAuth 2.0**: Full lifecycle with PKCE, proactive refresh 5 min before expiry, cross-process file locking, step-up auth on 403.

**XAA (Cross-App Access)**: Four-layer enterprise flow — Discovery (RFC 9728/8414) → Token Exchange (RFC 8693) → JWT Bearer (RFC 7523) → Orchestration.

### 6.5 Elicitation System

MCP servers can request user interaction:
1. Pre-configured hooks respond programmatically
2. If unresolved, queued in AppState for UI rendering
3. Post-response hooks can modify/block
4. Abort handling via signals

### 6.6 Channel Permissions (Telegram/iMessage/Discord)

Permission relay via communication channels. User reply format: `"yes tbxkq"` — 5-letter IDs using 25-char alphabet (excluding `l` to avoid confusion with 1/I).

---

## 7. Context & Memory Systems

### 7.1 CLAUDE.md Discovery — Four-Tier Priority

| Priority | Type | Source |
|----------|------|--------|
| 1 (lowest) | Managed | Policy/org-level |
| 2 | User | `~/.claude/` |
| 3 | Project | `.claude/` (committed) |
| 4 (highest) | Local | `.claude/` (gitignored) |

**Traversal**: Upward from CWD to repo root. Stops at git boundaries.

**`@include` directive**: `@path`, `@./relative`, `@~/home`, `@/absolute`. Max 5 nesting levels. Circular reference prevention.

### 7.2 System Prompt Assembly

Three cache-stable components:
1. **defaultSystemPrompt** — tool-aware, model-aware
2. **userContext** — CLAUDE.md files + current date
3. **systemContext** — git status, branch, recent commits

These form the **API cache-key prefix** — stability is critical for prompt cache hits.

### 7.3 Dynamic Context — Three-Phase Attachment Pipeline

**Phase 1** (User Input): At-mentions, user context

**Phase 2** (Thread-Safe, available to subagents):
- Nested memory (CLAUDE.md for target paths)
- Changed file detection (diff snippets)

**Phase 3** (Main Thread Only):
- Plan mode instructions (throttled: 1 per 5 turns after first)
- Relevant memories (prefetched async during streaming)
- Tool search announcements (delta-based)
- MCP instruction deltas
- Skill/agent discovery listings
- LSP diagnostics
- Token usage annotations
- Midnight crossing detection

### 7.4 Memory — File-Based, Not Database

Four memory types: **User** (profile), **Feedback** (corrections + confirmations), **Project** (ongoing work), **Reference** (external systems).

Format: Individual `.md` files with YAML frontmatter. Index: `MEMORY.md` (~150 char/entry, 200 line cap).

**Relevant Memory Selection**: Uses Claude Sonnet to select up to 5 most relevant memories per query. Enforces 60KB cumulative session limit.

**Staleness**: Memories >1 day old get `<system-reminder>` warning.

### 7.5 Background Memory Extraction

- Runs as **forked agent** (non-blocking)
- Throttled: every N eligible turns (remote-configurable)
- Coalescing: if already running, requests stashed for trailing run
- Mutual exclusion: skips if main agent wrote memory directly
- Efficiency: batch reads on turn 1, writes on turn 2

---

## 8. Conversation Management

### 8.1 Session Persistence — JSONL DAG

Format: JSONL (one JSON entry per line). Messages linked via `parentUuid` forming a DAG.

**Write pipeline**: Buffered → materialized on first user/assistant message → per-file queue (100ms local, 10ms remote) → 100MB chunk limits.

**Recovery**: `recoverOrphanedParallelToolResults()` reattaches siblings that single-parent walks would orphan.

### 8.2 Four-Layer Compaction Strategy

| Layer | Trigger | Strategy |
|-------|---------|----------|
| **API Microcompact** | Server-side thresholds | Clear tool results at 180K input tokens |
| **Microcompact** | Time-based (60 min gap) | Replace older tool results with stubs |
| **Session Memory** | Token threshold | Preserve recent messages, archive older |
| **Full Compaction** | Context window - 13K buffer | Forked agent summarizes entire conversation |

**Full compaction details**:
- Forked agent shares parent's prompt cache
- Produces structured XML summary (`<analysis>` draft → `<summary>` output)
- Re-injects: top 5 recent files, plan attachments, skill content, deferred schemas
- File budget: 50K tokens total, 5K per file, 25K for skills
- PTL retry: drops oldest API-round groups (max 3 retries)

**Circuit breaker**: Stops after 3 consecutive compaction failures.

### 8.3 Session Resume

Restores: full message history, file modification snapshots, commit attribution, todo lists, context collapse state, worktree directory, agent configs.

### 8.4 Query Loop — 10-Stage Pipeline

```
1. Boundary extraction (post-compaction messages)
2. Content budgeting (per-message tool result limits)
3. History snipping (optional older message removal)
4. Microcompaction (selective tool use compression)
5. Context collapse (read-time projection)
6. System prompt composition (default + extras + append)
7. Attachment injection (3-phase pipeline)
8. API call (streaming tool execution)
9. Tool execution (results as attachment messages)
10. Auto-compaction check + max-turn limit
```

---

## 9. UI Architecture (Ink/React CLI)

### 9.1 React Compiler

All components use React Compiler (`_c` from `react/compiler-runtime`). The compiler outputs slot-based memo caches (`$[0]`, `$[1]`, etc.) — automatic memoization eliminates hand-written `useMemo`/`useCallback`.

Example: `Message.tsx` has a **94-slot memoization cache**.

### 9.2 Virtual Scrolling

`VirtualMessageList` with UUID-based scroll anchoring (immune to grouping/compaction length churn).

**Safety cap**: `MAX_MESSAGES_WITHOUT_VIRTUALIZATION` prevents memory death spiral (observed: 59GB RSS at ~2000 messages without it).

### 9.3 Markdown Rendering

- **LRU token cache**: 500 entries, hash-keyed. `marked.lexer` costs ~3ms/call.
- **Fast path**: `hasMarkdownSyntax` regex on first 500 chars skips full GFM parse for plain text.
- **Streaming split**: Splits at last top-level block boundary — stable prefix memoized, only unstable suffix re-parses.

### 9.4 Performance Patterns

| Pattern | Purpose |
|---------|---------|
| `React.memo` on LogoHeader | Prevents Ink's `seenDirtyChild` cascade |
| `OffscreenFreeze` | Wraps non-updating subtrees |
| `Ratchet lock="offscreen"` | Prevents content shrinking |
| `NoSelect` | Prevents ornamental chars from text selection |
| Stall detection | RGB interpolation from base to error red |

### 9.5 State Management

External store via `useSyncExternalStore`-compatible API. `useAppState(selector)` for granular subscriptions. Dual-layer settings: snapshot + live.

---

## 10. Command & Skill System

### 10.1 Command Sources (6 sources, merged in priority)

1. Bundled skills
2. Built-in plugin skills
3. Skill directory commands (`.claude/skills/`)
4. Workflow commands (feature-flagged)
5. Plugin commands
6. Built-in COMMANDS (~80+ static)

### 10.2 Three Command Types

| Type | Behavior |
|------|----------|
| `prompt` | Generates content blocks sent to model |
| `local` | Pure computation, returns text/compact/skip |
| `local-jsx` | Renders Ink (React) UI |

### 10.3 Skill Loading

Skills are `SKILL.md` files with YAML frontmatter. Discovered from managed, user (`~/.claude/skills/`), and project (`.claude/skills/`) directories.

Frontmatter: `name`, `description`, `allowed-tools`, `when_to_use`, `model`, `hooks`, `context`, `agent`, `effort`, `paths` (conditional visibility globs).

### 10.4 Feature-Gated Loading

```typescript
// Dead code elimination via bun:bundle
const voiceCommand = feature('VOICE_MODE')
  ? require('./commands/voice/index.js').default
  : null

// Lazy import for expensive modules
const usageReport: Command = {
  type: 'prompt',
  name: 'insights',
  async getPromptForCommand(args, context) {
    const real = (await import('./commands/insights.js')).default
    return real.getPromptForCommand(args, context)
  },
}
```

---

## 11. Plugin System

### 11.1 Plugin Structure

```
my-plugin/
  plugin.json           # Manifest
  commands/             # Slash commands (.md)
  agents/               # AI agents (.md)
  skills/               # Skills
  hooks/hooks.json      # Hook definitions
  .mcp.json             # MCP server configs
  output-styles/        # Custom output styles
```

### 11.2 Security Model

- **Policy enforcement**: `managed-settings.json` can force-disable plugins
- **23 error types** for comprehensive validation
- **Path traversal detection** (`..` sequences)
- **Trust model**: Frontmatter MCP/hooks gated by source classification
- **Plugin MCP scoping**: `plugin:pluginName:serverName` prefix

### 11.3 Dependency Resolution

DFS-based transitive closure with:
- Cross-marketplace auto-install blocking
- Cycle detection
- Fixed-point demotion loop for unsatisfied deps
- Reverse dependency tracking on uninstall

---

## 12. Configuration & Settings

### 12.1 Three-Layer Cascade

```
policySettings (managed, highest priority)
  > userSettings (~/.claude/settings.json)
    > projectSettings (.claude/settings.json)
      > localSettings (.claude/settings.local.json)
        > cliArgs (runtime)
          > session (in-memory)
```

### 12.2 Concurrency Safety

- File-based locking via `lockfile.lockSync()`
- Write-through caching (immediate memory update)
- Auth loss prevention (`wouldLoseAuthState()`)
- Automatic timestamped backups (up to 5)

### 12.3 Feature Flags (GrowthBook)

Multi-layer cache: env var overrides → local config → in-memory remote → disk-persisted fallback.

Periodic refresh: 6 hours (20 min for internal builds). `checkSecurityRestrictionGate()` waits for re-init after auth changes.

### 12.4 Constants — Leaf-of-DAG

`src/constants/` files have **zero imports** to remain import-cycle-free:

| File | Purpose |
|------|---------|
| `toolLimits.ts` | Output size caps |
| `files.ts` | Binary extension set (80+ types) |
| `errorIds.ts` | Obfuscated error IDs |
| `common.ts` | Memoized dates for cache stability |
| `system.ts` | System prompt prefixes + native attestation |

---

## 13. Bridge System (Remote/IDE)

### 13.1 Two Transport Versions

| Version | Reads | Writes | Auth |
|---------|-------|--------|------|
| v1 (Hybrid) | WebSocket | HTTP POST | OAuth |
| v2 (CCR) | SSE | HTTP | JWT |

### 13.2 Multi-Session Support

Three spawn modes: `single-session`, `same-dir`, `worktree` (each session gets isolated git worktree).

### 13.3 Resilience

- Proactive JWT refresh (5 min before expiry)
- Exponential backoff with jitter
- Sleep/wake detection (resets error budget)
- 10-minute give-up threshold
- `BoundedUUIDSet` — FIFO circular buffer for echo deduplication

### 13.4 Poll Configuration Safety

```typescript
// Zod refinement: 0 means disabled, 1-99 rejected
// Prevents fat-fingered configs (seconds vs milliseconds confusion)
zeroOrAtLeast100: z.number().refine(n => n === 0 || n >= 100)
```

---

## 14. Telemetry & Analytics

### 14.1 PII Protection at Type Level

```typescript
// Type forces explicit verification — prevents accidental code/path logging
type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS = never
// Cannot pass a string without explicit cast through this marker type
```

### 14.2 Dual Backend

| Backend | Access | PII | Purpose |
|---------|--------|-----|---------|
| Datadog | General | `_PROTO_*` stripped | Operational metrics |
| First-Party (1P) | Privileged | Full payload | BigQuery analysis |

### 14.3 Privacy

- Metadata restricted to `boolean | number | undefined` (no strings)
- User ID bucket-hashed to 30 buckets (impact estimation without tracking)
- Analytics disabled for: test envs, 3P providers, privacy opt-out
- Event sampling via GrowthBook dynamic config

---

## 15. Error Handling

### 15.1 Error Hierarchy

```
ClaudeError (base)
  ├── MalformedCommandError
  ├── AbortError
  ├── ConfigParseError (stores file path + default config)
  ├── ShellError (stdout, stderr, exit code, interruption)
  ├── TeleportOperationError
  └── TelemetrySafeError_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
      (separate messages: user display vs telemetry)
```

### 15.2 API Error Recovery

- Interactive vs non-interactive messaging
- Auth differentiation (env API key vs OAuth vs JWT)
- Rate limiting with overage integration and model fallback suggestions
- Contextual recovery: PDFs → "try pdftotext", images → resize, models → fallback versions

### 15.3 Graceful Shutdown

Synchronous cleanup in order:
1. Disable mouse tracking, alt screen, keyboard modes
2. Disable focus events, bracketed paste, cursor visibility
3. Disable iTerm2 progress, tab status, terminal title
4. Unmount Ink **before** exit sequences (avoids double alt-screen)
5. Print resume hint (`claude --resume`)
6. Analytics flush with timeout

---

## 16. Performance Engineering

### 16.1 Memoization Strategies

| Strategy | Behavior |
|----------|----------|
| `memoizeWithTTL` | Write-through, stale-while-revalidate, 5min default |
| `memoizeWithTTLAsync` | + in-flight deduplication for cold misses |
| `memoizeWithLRU` | LRU eviction, bounded memory (default 100) |

### 16.2 AbortController Hierarchy

```typescript
createChildAbortController()  // child aborts when parent aborts, NOT vice versa
// Uses WeakRef — GC-safe, no parent retention of abandoned children
// Module-scope propagateAbort avoids per-call closure allocation
```

### 16.3 Hash Functions

| Function | Runtime | Purpose |
|----------|---------|---------|
| `djb2Hash` | All | Deterministic cross-runtime (cache dirs) |
| `hashContent` | Bun: wyhash, Node: SHA-256 | Fast content hashing |
| `hashPair` | Bun: seed-chained | No temporary concatenation |

**Critical**: Cache dirs use `djb2Hash` NOT `Bun.hash` — stability across upgrades.

### 16.4 V8 Memory Optimization

```typescript
// String flattening: break V8's sliced-string references
// Sliced strings retain large parent strings in memory
'' + line  // forces flat string allocation
```

### 16.5 Interaction Batching

```typescript
// Avoid Date.now() on every keypress
let interactionTimeDirty = false
export function updateLastInteractionTime(immediate?: boolean): void {
  if (immediate) { flushInteractionTime_inner() }
  else { interactionTimeDirty = true }  // deferred flush
}
```

### 16.6 File State Cache

LRU with dual limits: entry count (100) + total byte size (25MB). Timestamp-based conflict resolution (newer wins). `isPartialView` flag signals auto-injected content.

---

## 17. Catalog of Patterns & Principles

### Architecture Patterns

| # | Pattern | Where | Description |
|---|---------|-------|-------------|
| 1 | **Builder with Type-Level Spread** | `buildTool()` | Factory applies defaults while preserving literal types |
| 2 | **Async Generator Loop** | `QueryEngine`, `runAgent()` | Streaming message delivery via `async *` |
| 3 | **Controlled Singleton** | `bootstrap/state.ts` | Module-scope state, getter/setter API, never exported raw |
| 4 | **Dead Code Elimination** | `commands.ts`, `QueryEngine` | `feature()` from `bun:bundle` + conditional `require()` |
| 5 | **Three-Stage Pool Assembly** | `tools.ts` | Base → filtered → merged (cache-stable sort) |
| 6 | **Race-to-Resolve** | Permission flow | 5 sources race via atomic `claim()` guard |
| 7 | **Forked Agent Cache Sharing** | `forkSubagent.ts` | Byte-identical API requests maximize cache hits |
| 8 | **Four-Layer Compaction** | `services/compact/` | Graduated compression (API, micro, session, full) |
| 9 | **Three-Phase Attachment Pipeline** | `context.ts` | User → thread-safe → main-thread-only |
| 10 | **Stale-While-Revalidate** | `memoizeWithTTL` | Return stale immediately, refresh in background |

### Security Principles

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **Fail-Closed Defaults** | `isConcurrencySafe: false`, `isReadOnly: false`, classifier iron gate |
| 2 | **Deny Always Wins** | Pipeline step 1a before anything else |
| 3 | **Bypass-Immune Checks** | Safety checks (1g), content-specific (1f), interaction (1e) survive bypass mode |
| 4 | **Defense in Depth** | Rules + sandbox + classifier + hooks + safety checks |
| 5 | **Sandbox as Security Boundary** | OS-level isolation makes permission prompts unnecessary |
| 6 | **Settings Self-Protection** | Sandbox `denyWrite` on all settings.json paths |
| 7 | **Parser-Differential Awareness** | `bashSecurity.ts` handles shell-quote vs bash divergence |
| 8 | **Type-Level PII Prevention** | `AnalyticsMetadata_I_VERIFIED_...` marker types |
| 9 | **Path Security Stack** | UNC + case-insensitive + symlink + NTFS + device blocking |
| 10 | **Crypto-Random IDs** | `randomBytes(8)` not Math.random (resists symlink attacks) |

### Engineering Principles

| # | Principle | Example |
|---|-----------|---------|
| 1 | **Zero Runtime Dependencies** | Everything bundled — empty `dependencies` in package.json |
| 2 | **Constants as DAG Leaves** | `src/constants/` has zero imports (no circular deps) |
| 3 | **Immutability at Boundaries** | `DeepImmutable<>` on permission context, `readonly Tool[]` |
| 4 | **Cache Stability** | Latched flags, sorted tool prefix, stable system prompt |
| 5 | **Graceful Degradation** | Skill/plugin/MCP loading catch errors → return empty |
| 6 | **Explicit Invalidation Chains** | `clearCommandsCache` → individual cache clears |
| 7 | **Fat-Finger Defense** | Zod refinement rejects 1-99ms poll intervals |
| 8 | **WeakRef for Lifecycle** | AbortController parent-child avoids memory leaks |
| 9 | **Generation Counters** | Prevent stale callbacks in async state machines |
| 10 | **V8 String Flattening** | `'' + str` breaks sliced-string references |

### UX Principles

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **Token Efficiency** | Path relativization, file dedup, deferred loading, head limits |
| 2 | **Read Before Write** | All edit tools require prior read with timestamp tracking |
| 3 | **Progressive Disclosure** | 200ms grace period, 2s speculative wait on permission dialogs |
| 4 | **Prompt Cache Preservation** | Latched headers, stable system prompt prefix |
| 5 | **Virtual Scrolling** | UUID-anchored, capped messages prevent 59GB RSS |
| 6 | **Streaming Markdown** | Stable prefix memoized, only suffix re-parses per delta |

---

## 18. Lessons for Our Codebase

### What to Adopt

1. **Fail-closed security defaults** — Tools should be unsafe by default, requiring explicit opt-in to safety. Our pipeline skills could benefit from this pattern.

2. **Builder pattern for tool/skill registration** — `buildTool()` with typed defaults is cleaner than our current skill YAML. Consider a `buildSkill()` factory.

3. **Three-layer config cascade with policy override** — Our `platform.yaml` → `settings.local.json` could adopt the managed > user > project > local pattern.

4. **Race-to-resolve for approvals** — Our human gates in the DAG executor could race CLI input against webhook/Telegram approval.

5. **File-based memory with frontmatter** — We already use this pattern. Their 4-type taxonomy (user, feedback, project, reference) is worth adopting.

6. **Constants as DAG leaves** — Move our constants to zero-import modules to prevent circular deps.

7. **Type-level PII markers** — For our analytics/telemetry, adopt marker types that force conscious opt-in to logging sensitive data.

8. **Memoize with stale-while-revalidate** — For our platform status queries and LikeC4 model loading.

9. **Deferred tool loading** — Our SpecKit skills could defer schema loading until invoked, reducing startup overhead.

10. **Comprehensive shutdown cleanup** — Our DAG executor should adopt their ordered shutdown pattern for process management.

### What to Avoid

1. **5,594-line headless mode** — Their `print.ts` is a maintenance burden. Keep our non-interactive paths modular.

2. **Module-scope singleton state** — Their `bootstrap/state.ts` works but is fragile. Our SQLite state store is cleaner.

3. **94-slot memoization caches** — React Compiler output is impressive but unreadable. Keep our components hand-optimized for maintainability.

### Key Metrics for Reference

| Metric | Claude Code | Notes |
|--------|-------------|-------|
| Total files | ~2,215 | TypeScript + TSX |
| Runtime deps | 0 | All bundled |
| Tool types | 13+ built-in | + MCP dynamic |
| Permission modes | 6 | default, plan, acceptEdits, bypass, dontAsk, auto |
| MCP transports | 9 | stdio, SSE, HTTP, WS, IDE, SDK, proxy, in-process, bridge |
| Config scopes | 7 | enterprise, managed, user, project, local, dynamic, claudeai |
| Hook events | 26 | Full lifecycle coverage |
| Compaction layers | 4 | API, micro, session-memory, full |
| Preapproved domains | 86 | WebFetch auto-allow |
| Bash security categories | 23 | Parser-differential-aware |
| Memory types | 4 | user, feedback, project, reference |
| Agent types | 6 built-in | + custom from markdown/JSON |
| Slash commands | ~100 | 3 types (prompt, local, local-jsx) |
| Plugin error types | 23 | Comprehensive validation |

---

> **Generated**: 2026-04-01 | **Analyst**: Claude Opus 4.6 (7 parallel research agents) | **Source**: `@anthropic-ai/claude-code` v2.1.88
