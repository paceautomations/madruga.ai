# Contract: Router Public API

**Epic**: 004-router-mece
**Module**: `prosauai/core/router/`

---

## Public Interface

### `route()` — Async Entrypoint

```python
# prosauai/core/router/__init__.py

async def route(
    message: InboundMessage,
    redis: Redis,
    engine: RoutingEngine,
    matchers: MentionMatchers,
    tenant: Tenant,
) -> Decision:
    """
    Route an inbound message through classify + decide.

    1. Load state from Redis (MGET: seen + handoff keys)
    2. Classify message into orthogonal facts (pure, sync)
    3. Decide action based on rules + tenant context

    Args:
        message: Parsed inbound message (anti-corruption layer output)
        redis: Active Redis connection for state lookup
        engine: Pre-loaded routing engine for this tenant
        matchers: Pre-built mention matchers for this tenant
        tenant: Tenant context (includes default_agent_id)

    Returns:
        Decision: One of 5 discriminated union subtypes

    Raises:
        RoutingError: When RESPOND action but no agent_id available
        RedisError: When Redis is unreachable (fail-fast, no fallback)
    """
```

### `classify()` — Pure Function

```python
# prosauai/core/router/facts.py

def classify(
    message: InboundMessage,
    state: StateSnapshot,
    matchers: MentionMatchers,
) -> MessageFacts:
    """
    Pure function: no I/O, no globals, deterministic.

    Extracts orthogonal facts from message + pre-loaded state.
    All invariants validated in MessageFacts.__post_init__.

    Args:
        message: Parsed inbound message
        state: Pre-loaded state snapshot (duplicata + handoff)
        matchers: Tenant-specific mention detection config

    Returns:
        MessageFacts: Frozen dataclass with validated invariants
    """
```

### `RoutingEngine.decide()` — Pure Function

```python
# prosauai/core/router/engine.py

@dataclass(frozen=True)
class RoutingEngine:
    rules: tuple[Rule, ...]
    default: Rule

    def decide(self, facts: MessageFacts, tenant_ctx: Tenant) -> Decision:
        """
        Evaluate rules in priority order; first match wins.
        If no rule matches, apply default.
        For RESPOND actions, resolve agent_id.

        Args:
            facts: Classified message facts
            tenant_ctx: Tenant context for agent resolution

        Returns:
            Decision: Typed decision with action-specific fields

        Raises:
            RoutingError: RESPOND action but no agent (rule or tenant default)
        """
```

---

## Loader API

### `load_routing_config()` — YAML Loader

```python
# prosauai/core/router/loader.py

def load_routing_config(path: Path) -> RoutingEngine:
    """
    Load and validate a tenant routing configuration from YAML.

    Validations:
    1. Schema: pydantic model validates all fields and types
    2. Default: configuration MUST have a default rule
    3. Priority: no duplicate priorities allowed
    4. Overlap: pairwise analysis rejects overlapping rules
    5. Fields: unknown fields rejected (extra="forbid")

    Args:
        path: Path to YAML file (e.g., config/routing/ariel.yaml)

    Returns:
        RoutingEngine: Validated, immutable engine ready for decide()

    Raises:
        RoutingConfigError: Any validation failure (schema, overlap, missing default)
    """
```

---

## CLI API

### `router verify`

```
Usage: prosauai router verify <path>

Validates a routing configuration YAML file.

Exit codes:
  0 — Valid configuration
  1 — Validation error (details printed to stderr)

Output (stdout):
  "✓ {path}: {N} rules loaded, 0 overlaps, default present"
```

### `router explain`

```
Usage: prosauai router explain --tenant <slug> --facts '<json>'

Explains which rule matches a given set of facts.

Output (stdout):
  "Rule '{name}' (priority {N}) matched: action={action}, reason={reason}"
  "Match details: {field}={value} for each when condition"

Exit codes:
  0 — Match found
  1 — Error (invalid facts JSON, missing config)
```

---

## YAML Schema Contract

```yaml
# config/routing/<tenant-slug>.yaml
version: 1                           # Schema version (required)
tenant: <tenant-id>                   # Must match tenants.yaml id (required)

rules:                                # Ordered list of rules (required, non-empty)
  - name: <string>                    # Unique identifier (required)
    priority: <int>                   # Evaluation order, lower = first (required, unique)
    when:                             # Match conditions (required)
      <field>: <value>                # Equality match against MessageFacts field
      # Supported fields:
      #   channel: individual | group
      #   event_kind: message | group_membership | group_metadata | protocol | unknown
      #   content_kind: text | media | structured | reaction | empty
      #   from_me: true | false
      #   has_mention: true | false
      #   is_membership_event: true | false
      #   is_duplicate: true | false
      #   conversation_in_handoff: true | false
      #   instance: <string>          # Optional, absent = wildcard
    action: RESPOND | LOG_ONLY | DROP | BYPASS_AI | EVENT_HOOK  # Required
    agent: <uuid>                     # Optional (RESPOND only). Absent = tenant default
    target: <string>                  # Required for BYPASS_AI and EVENT_HOOK
    reason: <string>                  # Required for DROP, optional for others

default:                              # Catch-all rule (required)
  action: RESPOND | LOG_ONLY | DROP   # Action for unmatched messages
  reason: <string>                    # Optional
```

---

## Error Types

```python
# prosauai/core/router/errors.py

class RoutingError(Exception):
    """Base error for routing failures."""
    pass

class RoutingConfigError(RoutingError):
    """Configuration validation error (schema, overlap, missing default)."""
    pass

class AgentResolutionError(RoutingError):
    """RESPOND action but no agent_id available (rule or tenant default)."""
    pass
```

---

## Integration Points

### Caller (webhooks.py)

```python
# Before (epic 003):
result = route_message(msg, tenant)
if result.route in _ACTIVE_ROUTES:
    debounce.append(...)

# After (epic 004):
decision = await route(msg, redis, engine, matchers, tenant)
match decision:
    case RespondDecision(agent_id=aid, matched_rule=rule):
        debounce.append(...)
    case LogOnlyDecision(matched_rule=rule):
        log.info("log_only", matched_rule=rule)
    case DropDecision(reason=reason, matched_rule=rule):
        log.debug("dropped", reason=reason, matched_rule=rule)
    case BypassAIDecision(target=target, matched_rule=rule):
        log.info("bypass_ai", target=target, matched_rule=rule)
    case EventHookDecision(target=target, matched_rule=rule):
        log.info("event_hook", target=target, matched_rule=rule)
```

### Startup (main.py lifespan)

```python
# Load routing engines + mention matchers at startup
engines: dict[str, RoutingEngine] = {}
matchers: dict[str, MentionMatchers] = {}

for tenant in tenant_store.all_active():
    config_path = Path(f"config/routing/{tenant.id}.yaml")
    if not config_path.exists():
        raise RuntimeError(f"Missing routing config for tenant {tenant.id}")
    engines[tenant.id] = load_routing_config(config_path)
    matchers[tenant.id] = MentionMatchers.from_tenant(tenant)

app.state.engines = engines
app.state.matchers = matchers
```

---

## Open Contracts (para epics futuros)

| Contract | Producer (futuro) | Consumer (004) | Fallback |
|----------|-------------------|----------------|----------|
| `handoff:{tenant_id}:{sender_key}` Redis key | Epic 005 ou 011 | `StateSnapshot.load()` | `False` (nao em handoff) |
| `routing_rules` DB table | Epic 006 | — (004 usa YAML) | N/A |
| Admin panel routing UI | Epic 009 | — (004 usa YAML) | N/A |
