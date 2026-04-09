# Data Model: AI Infrastructure as Code

**Epic**: 019-ai-infra-as-code  
**Date**: 2026-04-04  
**Status**: Complete

## Overview

This epic is primarily file-creation and tooling extension. There are no database changes or new persistent entities. The "data model" consists of:
1. A computed in-memory knowledge graph (T3)
2. A YAML schema extension for `platform.yaml` (T6)
3. Static governance files (T1, T7, T8, T9)

## Entity: Knowledge Graph (computed, in-memory)

Built at runtime by `build_knowledge_graph()` in `skill-lint.py`.

```
KnowledgeGraph = dict[str, set[str]]
  key: knowledge filename (e.g., "pipeline-contract-base.md")
  value: set of skill names that reference it (e.g., {"vision", "adr", ...})
```

**Construction**:
- Scan each `.md` file in `COMMANDS_DIR` (`.claude/commands/madruga/`)
- Extract references via regex: `\.claude/knowledge/([\w.-]+\.(?:md|yaml))`
- Build reverse map: filename → {skill_names}

**Usage**: `cmd_impact_of(path)` extracts the filename from the given path, looks it up in the graph, and prints a table of (skill_name, archetype) pairs.

**Lifecycle**: Created on each invocation of `--impact-of`. Not cached or persisted.

## Entity: Knowledge Declaration (YAML in platform.yaml)

New `knowledge:` section in `platform.yaml`:

```yaml
knowledge:
  - file: <string>           # filename relative to .claude/knowledge/
    consumers: <string|list>  # skill IDs or "all-pipeline" shorthand
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | string | yes | Knowledge filename (e.g., `pipeline-contract-base.md`) |
| `consumers` | string or list[string] | yes | Skill IDs that consume this file, or `"all-pipeline"` shorthand |

**Validation rules** (implemented in `lint_knowledge_declarations()`):
1. `file` must exist as a file in `.claude/knowledge/`
2. Each consumer (if explicit list) should be a valid `pipeline.nodes[].id` or `pipeline.epic_cycle.nodes[].id`
3. `"all-pipeline"` resolves dynamically to all L1 + L2 node IDs from `pipeline.nodes[]` and `pipeline.epic_cycle.nodes[]`

**Cross-check**:
- For each skill, scan body for `.claude/knowledge/<filename>` references
- If a skill references a knowledge file NOT in `knowledge:` declarations → WARNING
- If a declared file doesn't exist on disk → WARNING

## Entity: CODEOWNERS (static file)

```
# .github/CODEOWNERS
/.claude/                          @gabrielhamu
/CLAUDE.md                         @gabrielhamu
/platforms/*/CLAUDE.md             @gabrielhamu
/.specify/scripts/skill-lint.py    @gabrielhamu
```

No computed logic. GitHub interprets path patterns natively.

## Entity: Security Scan Patterns (CI config)

Dangerous code patterns (grep regex):
```
eval\(
exec\(
subprocess\.call\(.*shell=True
PRIVATE.KEY
password\s*=\s*["'][^"']
```

Secret patterns (grep regex):
```
sk-[a-zA-Z0-9]{20,}     # OpenAI/Anthropic API keys
AKIA[A-Z0-9]{16}         # AWS access key IDs
```

File detection:
```
.env files anywhere in repo (excluding .git/, node_modules/)
```

## Relationships

```
platform.yaml
  └── knowledge: []
        ├── file → .claude/knowledge/<filename>  (existence check)
        └── consumers → pipeline.nodes[].id      (cross-reference)

skill-lint.py
  ├── build_knowledge_graph()
  │     ├── reads: .claude/commands/madruga/*.md
  │     └── produces: dict[str, set[str]]
  ├── cmd_impact_of(path)
  │     ├── uses: build_knowledge_graph()
  │     └── uses: get_archetype(name)
  └── lint_knowledge_declarations()
        ├── reads: platform.yaml → knowledge[]
        ├── checks: .claude/knowledge/<file> exists
        └── cross-checks: skill body references vs declarations
```

## No Database Changes

This epic does not modify `.pipeline/madruga.db`, migrations, or `db.py`. All data is either:
- Static files (CODEOWNERS, SECURITY.md, CONTRIBUTING.md, PR template)
- YAML configuration (platform.yaml knowledge section)
- Computed in-memory (knowledge graph)
- CI configuration (ci.yml jobs)
