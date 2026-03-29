# CLI Contract: check-platform-prerequisites.sh

## Synopsis

```bash
.specify/scripts/bash/check-platform-prerequisites.sh [OPTIONS]
```

## Options

| Flag | Required | Description |
|------|----------|-------------|
| `--platform <name>` | Yes | Platform name (e.g., `madruga-ai`, `fulano`) |
| `--skill <id>` | No* | Pipeline node ID to check prerequisites for |
| `--status` | No* | Show full pipeline status (all nodes) |
| `--json` | No | Output in JSON format (default: text) |
| `--help`, `-h` | No | Show help message |

*One of `--skill` or `--status` is required.

## Mode 1: Skill Prerequisites (`--skill`)

### Input
- Platform name
- Skill (node) ID

### Process
1. Resolve repo root via `common.sh:get_repo_root()`
2. Read `platforms/<name>/platform.yaml`
3. Parse `pipeline.nodes` via `python3 -c yaml.safe_load`
4. Find node matching `--skill` ID
5. Resolve all `depends` → get their `outputs` file paths
6. For each dependency output: check file existence under `platforms/<name>/`
7. For `output_pattern` dependencies: use `find` with glob matching (≥1 match = exists)
8. For `optional: true` dependencies: skip (don't block)
9. Return result

### JSON Output

```json
{
  "platform": "madruga-ai",
  "platform_dir": "/abs/path/platforms/madruga-ai",
  "skill": "domain-model",
  "ready": true,
  "missing": [],
  "available": [
    "business/vision.md",
    "business/solution-overview.md",
    "business/process.md",
    "engineering/blueprint.md"
  ],
  "depends_on": ["blueprint", "business-process"],
  "outputs": ["engineering/domain-model.md", "model/ddd-contexts.likec4"]
}
```

### Text Output

```
Platform: madruga-ai
Skill: domain-model
Status: READY

Dependencies:
  ✓ blueprint → engineering/blueprint.md
  ✓ business-process → business/process.md

Outputs (will generate):
  engineering/domain-model.md
  model/ddd-contexts.likec4
```

### Error Cases

| Condition | Exit Code | JSON Error |
|-----------|-----------|------------|
| Platform dir not found | 1 | `{"error": "Platform 'X' not found", "suggestion": "Run platform.py list to see available platforms"}` |
| No pipeline section | 1 | `{"error": "No pipeline section in platform.yaml", "suggestion": "Run copier update or add pipeline: section manually"}` |
| Skill ID not found in pipeline | 1 | `{"error": "Node 'X' not found in pipeline", "available_nodes": ["vision", "blueprint", ...]}` |
| python3 not available | 1 | `{"error": "python3 required for YAML parsing"}` |

## Mode 2: Pipeline Status (`--status`)

### Input
- Platform name

### Process
1. Same steps 1-3 as Mode 1
2. For EACH node in pipeline:
   a. Check if outputs exist → `done`
   b. Check if all non-optional deps are done → `ready` (if own outputs don't exist)
   c. Otherwise → `blocked` (list missing deps)
3. Identify `next` nodes (status = ready)
4. Calculate progress counts

### JSON Output

```json
{
  "platform": "madruga-ai",
  "nodes": [
    {"id": "platform-new", "status": "done", "layer": "business", "gate": "human"},
    {"id": "vision", "status": "done", "layer": "business", "gate": "human"},
    {"id": "solution-overview", "status": "done", "layer": "business", "gate": "human"},
    {"id": "business-process", "status": "ready", "layer": "business", "gate": "human"},
    {"id": "tech-research", "status": "blocked", "layer": "research", "gate": "1-way-door", "missing_deps": ["business-process"]},
    {"id": "codebase-map", "status": "skipped", "layer": "research", "gate": "auto", "optional": true}
  ],
  "next": ["business-process"],
  "progress": {"done": 3, "ready": 1, "blocked": 9, "skipped": 1, "total": 14}
}
```

### Text Output

```
Pipeline Status: madruga-ai
Progress: 3/14 nodes done (21%)

| Layer       | Skill              | Status  | Gate        | Missing           |
|-------------|--------------------|---------+-------------|-------------------|
| business    | platform-new       | ✅ done | human       | —                 |
| business    | vision             | ✅ done | human       | —                 |
| business    | solution-overview  | ✅ done | human       | —                 |
| business    | business-process   | 🟡 READY| human       | —                 |
| research    | tech-research      | 🔴 blocked| 1-way-door | business-process |
| research    | codebase-map       | ⬜ skip | auto        | — (optional)      |
...

Next available: /business-process madruga-ai
```

## Dependencies

- `common.sh` (get_repo_root, json_escape, has_jq)
- `python3` with `yaml` module (for YAML parsing)
- `find` (for glob pattern matching)

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (ready=true for --skill, or --status completed) |
| 1 | Error (platform not found, no pipeline, skill not found) |
| 2 | Prerequisites not met (ready=false for --skill) — useful for scripting |
