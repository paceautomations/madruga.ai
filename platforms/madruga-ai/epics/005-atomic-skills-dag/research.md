# Research: Atomic Skills DAG Pipeline

**Date**: 2026-03-29
**Feature**: 001-atomic-skills-dag-pipeline

---

## 1. DAG Schema Design

### Decision: YAML declarative nodes with filesystem-based status detection

### Rationale
After analyzing DAG patterns across Makefile, dbt, Nx, Airflow, and GitHub Actions:

- **Makefile**: Target → prerequisites → recipe. Status = file modification time. Simplest model — our closest match since we also use filesystem.
- **dbt**: YAML config with `ref()` for dependencies. Opinionated about SQL but the declarative YAML model is elegant.
- **Nx**: `project.json` with `dependsOn` arrays. Graph-based with affected detection.
- **Airflow**: Python DAG definitions with `>>` operator. Too complex for our needs (code-based, not declarative).
- **GitHub Actions**: `needs:` array per job. Simple, declarative, YAML-native. Closest to what we want.

### Schema chosen: GitHub Actions-inspired with Makefile status detection

```yaml
pipeline:
  nodes:
    - id: vision                      # Unique identifier
      skill: madruga:vision-one-pager # Skill to invoke
      outputs: [business/vision.md]   # Files produced (relative to platform dir)
      depends: [platform-new]         # Node IDs that must be done
      layer: business                 # Grouping for display
      gate: human                     # Approval type
```

Key design decisions:
- **No `targets` or `recipes`** — skills ARE the recipes, referenced by `skill:` field
- **File existence = done** — like Makefile, but without timestamp comparison (simpler)
- **`output_pattern` for globs** — extends beyond Makefile/GH Actions to handle `ADR-*.md`
- **`optional: true`** — not found in any reference system; custom addition for brownfield flexibility
- **`gate` field** — unique to our system; no equivalent in build tools (they're all auto)

### Alternatives considered

| Alternative | Pros | Cons | Why rejected |
|-------------|------|------|-------------|
| Makefile-style (actual Makefile) | Battle-tested, parallel execution built-in | Can't express gates, no YAML, poor readability | Gates are core requirement |
| Airflow-style (Python code) | Full expressiveness, conditional logic | Over-engineering for 14 nodes, requires runtime | Violates pragmatism principle |
| Flat sequential list | Simplest possible | Can't express parallelism or optional nodes | Missing DAG capabilities |

---

## 2. Skill Prompt Engineering

### Decision: 6-section uniform contract with persona-driven questioning

### Rationale
After analyzing existing skills (`vision-one-pager.md`, `solution-overview.md`, `speckit.plan.md`, `speckit.analyze.md`):

**What makes skills produce GOOD output:**
- **Persona with expertise boundary** — "Estrategista Bain/McKinsey" in vision-one-pager constrains the AI to business language. Without persona, output is generic.
- **Regra Cardinal (negative constraint)** — "ZERO conteudo tecnico" in vision forces the AI to stay in lane. Negative rules are more effective than positive ones.
- **Structured output template** — exact sections, tables, line limits. The more constrained, the better.
- **Auto-review with grep-able checks** — vision-one-pager greps for tech terms. Concrete checks > vague "ensure quality".

**Questioning phase best practices:**
- Ask ALL questions at once (not one by one) — proven pattern in both vision and solution-overview skills
- Read existing artifacts BEFORE asking — reduces redundant questions
- 4 categories (Premissas, Trade-offs, Gaps, Provocação) — structured enough to be useful, not so rigid it's annoying
- Mark unknowns with `[VALIDAR]` — lets the pipeline continue without blocking on every gap

**Gate approval flow:**
- Present summary of what was generated (not the full artifact)
- List decisions taken with alternatives considered
- Ask 2-3 specific validation questions
- For 1-way-door: require per-decision confirmation

### Contract structure

```
0. Prerequisites (check-platform-prerequisites.sh + constitution)
1. Context Collection + Structured Questions (read deps, identify assumptions, research, ask)
2. Generate Artifact (follow template, include alternatives, mark [VALIDAR])
3. Auto-Review (checklist: alternatives?, assumptions marked?, research done?, trade-offs?)
4. Gate Approval (summary, decisions, validation Qs; 1-way-door: per-decision confirm)
5. Save + Report (path, lines, checks, next handoff)
```

---

## 3. ADR Format

### Decision: Nygard format (Context, Decision, Alternatives, Consequences)

### Rationale
- **Nygard**: Original, widely adopted, simple. 4 sections. Good for our case.
- **MADR (Markdown ADR)**: More structured (Status, Context, Decision Drivers, Options, Pros/Cons). Better for large teams but over-engineered for our use.
- **Y-statements**: "In the context of X, facing Y, we decided Z, to achieve W, accepting Q." Good for summaries but lacks detail.

Nygard is already the standard in the repo (see existing ADRs in `platforms/madruga-ai/decisions/`). No reason to change.

### Auto-generation from tech-research
The `/adr-gen` skill reads `research/tech-alternatives.md` (decision matrix) and generates one ADR per decision:
- Context ← from business layer + decision description
- Decision ← the chosen alternative
- Alternatives ← all evaluated alternatives with pros/cons
- Consequences ← impact on downstream artifacts

### Numbering: `ADR-NNN-kebab-case.md` (sequential, 3-digit padded)

---

## 4. DDD Documentation

### Decision: Bounded contexts in markdown + LikeC4 DSL for visual model

### Rationale
Best practices for DDD documentation:
- **Bounded Context** = markdown section with: purpose, key entities, invariants, relationships to other contexts
- **Context Map** = relationships between BCs (upstream/downstream, conformist, ACL, shared kernel, etc.)
- **LikeC4 DSL** = visual representation of BCs, modules, and relationships

Two outputs per DDD skill:
1. `engineering/domain-model.md` — prose with Mermaid class diagrams, invariants, SQL schemas
2. `model/ddd-contexts.likec4` — LikeC4 DSL for interactive diagrams in portal

### Context mapping patterns to support
| Pattern | When to use |
|---------|-------------|
| Upstream/Downstream | Default relationship between BCs |
| Conformist | Downstream accepts upstream's model as-is |
| Anti-Corruption Layer (ACL) | Downstream translates upstream's model |
| Shared Kernel | Two BCs share a subset of the domain model |
| Customer/Supplier | Downstream has influence on upstream's priorities |

---

## 5. Shape Up Pitch Format

### Decision: Standard Shape Up format with acceptance criteria addition

### Rationale
Shape Up pitch structure (from Basecamp):
1. **Problem** — what's broken or missing
2. **Appetite** — how much time/effort we're willing to invest (2-week or 6-week cycle)
3. **Solution** — high-level approach with fat marker sketches
4. **Rabbit Holes** — known risks and complexities to avoid
5. **No-gos** — what's explicitly out of scope

Addition for our pipeline: **Acceptance Criteria** — testable conditions for "done". This bridges the gap between Shape Up (strategic) and SpecKit (tactical).

---

## 6. Bash YAML Parsing

### Decision: Python3 inline for YAML parsing, bash for file operations

### Rationale
The `check-platform-prerequisites.sh` script needs to:
1. Parse `platform.yaml` YAML (nodes, depends, outputs)
2. Check file existence for outputs
3. Resolve dependencies transitively
4. Output JSON

**Pattern (from existing `common.sh`):**
```bash
# Use python3 -c for YAML → JSON conversion
pipeline_json=$(python3 -c "
import yaml, json, sys
with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)
nodes = data.get('pipeline', {}).get('nodes', [])
json.dump(nodes, sys.stdout)
" "$platform_yaml")
```

**Glob matching for output_pattern:**
```bash
# Use bash globbing for pattern matching
shopt -s nullglob
matches=($platform_dir/$output_pattern)
if [ ${#matches[@]} -gt 0 ]; then done=true; fi
```

**Error handling:** return JSON error objects, never raw stderr:
```json
{"error": "No pipeline section found", "suggestion": "Run copier update or add pipeline manually"}
```

Reuse `common.sh` functions: `get_repo_root`, `json_escape`, `has_jq`.
