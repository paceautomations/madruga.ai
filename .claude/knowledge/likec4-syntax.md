# LikeC4 Syntax Reference

Quick reference for generating valid `.likec4` files in this repository.
For full docs, use Context7 with library ID `likec4`.

---

## File Structure

Every `.likec4` file contains either `model { }` or `views { }` blocks (or both).
Files are automatically discovered by the LikeC4 compiler — no imports needed.

```likec4
// model/actors.likec4
model {
  // elements go here
}

// model/views.likec4
views {
  // views go here
}
```

## Element Types

```likec4
model {
  // Person (actor)
  user = person 'Display Name' {
    description 'What this actor does'
  }

  // Software System
  system = softwareSystem 'System Name' {
    description 'What this system does'
  }

  // Container (inside a system)
  system = softwareSystem 'System' {
    webapp = container 'Web App' {
      technology 'React, TypeScript'
      description 'Frontend SPA'
    }
    api = container 'API' {
      technology 'Python, FastAPI'
      description 'REST API backend'
    }
    db = container 'Database' {
      technology 'PostgreSQL'
      description 'Persistent storage'
      #database
    }
  }

  // Bounded Context (DDD)
  ctx = boundedContext 'Context Name' {
    #core  // or #supporting, #generic
    description 'Domain description'

    mod = module 'Module Name' {
      description 'Module description'
    }
  }

  // External Service
  ext = externalService 'Service Name' {
    technology 'REST API'
    description 'Third-party service'
  }
}
```

## Tags

Tags start with `#` and are used for styling and filtering:

```likec4
element = container 'Name' {
  #database        // built-in: database shape
  #core            // custom: DDD core domain
  #supporting      // custom: DDD supporting domain
  #generic         // custom: DDD generic domain
}
```

## Relationships

```likec4
model {
  // Inside model block, after element definitions
  user -> webapp 'Uses' {
    description 'Accesses via browser'
  }

  webapp -> api 'Calls' {
    technology 'REST/JSON'
  }

  api -> db 'Reads/Writes' {
    technology 'SQL'
  }
}
```

## Views

```likec4
views {
  // System Landscape (C4 Level 1)
  view index {
    title 'System Landscape'
    include *
  }

  // Container View (C4 Level 2)
  view containers of system {
    title 'Containers'
    include *
  }

  // Detail View (zoom into a bounded context)
  view contextDetail of ctx {
    title 'Context Detail'
    include *
  }

  // Dynamic View (sequence/flow)
  view businessFlow {
    title 'Business Process'
    include *

    // Ordered steps
    user -> webapp 'Step 1: Opens app'
    webapp -> api 'Step 2: Sends request'
    api -> db 'Step 3: Queries data'
  }
}
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Unexpected token` | Missing quotes around display name | Add single quotes: `'Name'` |
| `Element not found` | Referencing element by wrong ID | Use the variable name (left side of `=`), not display name |
| `Duplicate identifier` | Same variable name in same scope | Rename one of them |
| `Expected '{'` after element | Missing opening brace | Add `{` after `'Name'` |
| `Unknown tag` | Using `#` tag that's not defined | Tags are auto-defined on first use — check spelling |

## Conventions in This Repo

1. **One file per concern**: `actors.likec4`, `ddd-contexts.likec4`, `platform.likec4`, `externals.likec4`, `views.likec4`, `spec.likec4` (synced from template)
2. **Variable names**: camelCase (`platformScaffold`, `specDomain`)
3. **Display names**: Human-readable with quotes (`'Platform Scaffold'`)
4. **Descriptions**: PT-BR for domain content, EN for technical metadata
5. **Tags**: `#core`, `#supporting`, `#generic` for DDD. `#database` for storage elements.
6. **Config**: Each platform has `model/likec4.config.json` with `{"name": "<platform>"}` for multi-project

## Validation

After generating or modifying `.likec4` files, validate with:

```bash
cd platforms/<name>/model && likec4 build 2>&1
```

Fix all errors before proceeding to the gate.
