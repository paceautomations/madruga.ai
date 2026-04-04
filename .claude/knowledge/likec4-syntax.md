# LikeC4 Syntax Reference

Quick reference for generating valid `.likec4` files in this repository.
For full docs, use Context7 with library ID `likec4`.

---

## File Structure (per platform)

Each platform has these files in `model/`:

| File | Content | Rules |
|------|---------|-------|
| `spec.likec4` | Element types, relationship kinds, tags | **Copier-synced — NEVER edit or redefine** |
| `likec4.config.json` | `{"name": "<platform>"}` | Required for multi-project |
| `actors.likec4` | `person` elements | `model { }` block |
| `externals.likec4` | `externalService` elements | `model { }` block |
| `infrastructure.likec4` | `database`, `cache`, `proxy` elements | `model { }` block |
| `platform.likec4` | `platform` with nested containers | `model { }` block |
| `ddd-contexts.likec4` | `boundedContext` with nested `module` | `model { }` block |
| `relationships.likec4` | All relationships (C4 + DDD + pipeline) | `model { }` block |
| `views.likec4` | ALL views (structural + dynamic) | `views { }` block |
| `output/likec4.json` | Exported JSON (auto-generated) | `likec4 export json` |

**Key rules:**
- `specification {}` ONLY in `spec.likec4` — NEVER add in other files
- `views {}` ONLY in `views.likec4` — NEVER add views in other files
- Relationships ONLY in `relationships.likec4`

## Element Types (from spec.likec4)

These are the ONLY valid element types. NEVER use `softwareSystem`, `container`, `component`, `aggregate`, `entity`, or `valueObject`.

| Type | Usage | Example |
|------|-------|---------|
| `person` | Actor / user | `architect = person 'Arquiteto' { ... }` |
| `platform` | System boundary (C4 L1) | `myApp = platform 'My App' { ... }` |
| `api` | API service (inside platform) | `restApi = api 'REST API' { technology 'FastAPI' }` |
| `worker` | Async worker (inside platform) | `executor = worker 'DAG Executor' { ... }` |
| `frontend` | Web app (inside platform) | `portal = frontend 'Portal' { ... }` |
| `database` | Storage | `db = database 'PostgreSQL' { ... }` |
| `cache` | Cache / queue | `redis = cache 'Redis' { ... }` |
| `proxy` | Gateway / proxy | `nginx = proxy 'Nginx' { ... }` |
| `externalService` | Third-party | `stripe = externalService 'Stripe' { ... }` |
| `boundedContext` | DDD context | `sales = boundedContext 'Sales' { #core }` |
| `module` | Module inside BC | `billing = module 'Billing' { ... }` |

**Syntax:**
```likec4
model {
  myId = elementType 'Display Name' {
    technology 'Tech stack'
    description 'What it does'
    #tagName
    link ../path/to/file.md 'Label'
    metadata { key 'value' }
  }
}
```

## Relationship Kinds (from spec.likec4)

| Kind | Syntax | When to use |
|------|--------|-------------|
| `acl` | `-[acl]->` | Anti-Corruption Layer — isolate external model |
| `conformist` | `-[conformist]->` | Conform to external API format |
| `customerSupplier` | `-[customerSupplier]->` | Customer consumes, supplier provides |
| `pubSub` | `-[pubSub]->` | Async, decoupled events |
| `sync` | `-[sync]->` | Synchronous call |
| `async` | `-[async]->` | Asynchronous call |

Plain `->` (no kind) is valid for C4 container relationships. DDD relationships MUST use `-[kind]->`.

```likec4
model {
  // C4 relationship (plain)
  user -> myApp.api 'Uses' { technology 'HTTPS' }

  // DDD relationship (typed)
  sales.billing -[customerSupplier]-> payments.processor 'Customer-Supplier' {
    description 'Why this pattern was chosen'
  }
}
```

## Tags

```likec4
element = boundedContext 'Name' {
  #core            // DDD core domain
  #supporting      // DDD supporting domain
  #generic         // DDD generic domain
  #critical        // Business-critical
}
```

## Views + navigateTo

### Structural Views

```likec4
views {
  // System Landscape (C4 L1)
  view index {
    title 'My App — System Landscape'
    description 'Overview of actors, platform, and external systems'
    include actors, myPlatform, externals
  }

  // Container View (C4 L2) — scoped to platform
  view containers of myPlatform {
    title 'C4 L2 — Containers'
    include *
    include actors, externals, infra
  }

  // Context Map — scoped includes with children
  view contextMap {
    title 'DDD Context Map'
    include sales, sales.*
    include payments, payments.*
    include externals
  }

  // Detail View — scoped to bounded context
  view salesDetail of sales {
    title 'Sales — Core Domain'
    include *
    include relevantExternals
  }
}
```

### navigateTo (auto-generated)

LikeC4 **automatically generates** `navigateTo` when a scoped view exists:
- `view containers of myPlatform` → `myPlatform` node gets `navigateTo: "containers"`
- `view salesDetail of sales` → `sales` node gets `navigateTo: "salesDetail"`

**No explicit `with { navigateTo }` syntax needed** — just create the scoped view.

### MANDATORY Rules for Detail Views

1. **Every `boundedContext` in `ddd-contexts.likec4` MUST have a `view <name>Detail of <name>` in `views.likec4`**
2. **Every `<name>Detail` view MUST be registered in `platform.yaml` under `views.structural`**

Why: The portal's `buildViewPaths()` generates URLs only for views registered in `platform.yaml`. Missing registration = navigation silently fails (no URL generated, `onNavigateTo` callback gets `undefined`).

```yaml
# platform.yaml
views:
  structural:
    - id: salesDetail
      label: "Sales (zoom)"
```

### Dynamic Views

`autoLayout` is ONLY valid in `dynamic view` blocks. NEVER use in structural views.

```likec4
views {
  dynamic view businessFlow {
    title 'Business Process'
    autoLayout TopBottom

    moduleA -> moduleB 'Step 1' {
      notes '''
        **Description**
        - Detail 1
        - Detail 2
      '''
    }

    parallel {
      moduleB -> moduleC 'Path A'
      moduleB -> moduleD 'Path B'
    }
  }
}
```

## Conventions in This Repo

1. **Variable names**: camelCase (`platformScaffold`, `specDomain`)
2. **Display names**: Single quotes (`'Display Name'`) — NEVER double quotes
3. **Descriptions**: PT-BR for domain content, EN for technical metadata
4. **Tags**: `#core`, `#supporting`, `#generic` for DDD classification
5. **Config**: `model/likec4.config.json` with `{"name": "<platform>"}` for multi-project

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Unexpected token` | Missing quotes around display name | Add single quotes: `'Name'` |
| `Element not found` | Wrong ID reference | Use variable name (left of `=`), not display name |
| `Duplicate identifier` | Same name in same scope | Rename one |
| View `X` not found (portal) | View exists in views.likec4 but not registered in platform.yaml | Add to `views.structural` in platform.yaml |
| Navigation broken (click does nothing) | `<name>Detail` view missing or not in platform.yaml | Create view + register |
| `autoLayout` in structural view | `autoLayout` only works in `dynamic view` | Remove from structural view |
| `specification {}` in wrong file | Types redefined outside spec.likec4 | Delete block — types come from Copier-synced spec.likec4 |
| Disconnected layout | Too many unrelated elements in one view | Reduce includes or add relationships |

## Validation

After generating or modifying `.likec4` files:

```bash
cd platforms/<name>/model && likec4 build 2>&1
```

Fix all errors before proceeding to the gate.
