---
description: Create, edit, lint, and audit madruga.ai skills and knowledge files — enforces patterns, dedup, handoff chains, and contract compliance
arguments:
  - name: action
    description: "Action: create | edit | lint | audit | dedup. If empty, prompt."
    required: false
  - name: target
    description: "Skill name (e.g., vision), knowledge file, or 'all' for lint/audit."
    required: false
argument-hint: "[create|edit|lint|audit|dedup] [skill-name|all]"
---

# Skills Management — Pattern Guardian

Create, edit, validate, and audit madruga.ai skills (`.claude/commands/madruga/`), knowledge files (`.claude/knowledge/`), and SpecKit templates (`.specify/templates/`). Enforce consistency across the entire skill system.

## Cardinal Rule: ZERO Duplication of Source-of-Truth Data

Every piece of information lives in exactly ONE canonical file. Skills reference it — never copy it. If the same data exists in two files, one must be deleted or converted to a reference.

**Single Source of Truth Map:**

| Data | Canonical File | Consumers |
|------|---------------|-----------|
| DAG topology (nodes, deps, gates, layers) | `pipeline-dag-knowledge.md` | All skills (via prerequisite check) |
| Execution contract (steps 0-5) | `pipeline-contract-base.md` | All pipeline skills (via `> **Contract**:` reference) |
| Layer personas + rules | `pipeline-contract-{business,engineering,planning}.md` | Skills in that layer |
| LikeC4 syntax | `likec4-syntax.md` | domain-model, containers |
| QA template | `qa-template.md` | qa skill |
| Node status at runtime | SQLite DB (`.pipeline/madruga.db`) | pipeline, post_save.py |
| Platform manifest | `platforms/<name>/platform.yaml` | All skills, portal |

## Persona

Staff engineer + tooling specialist. Obsessive about consistency. Challenge every deviation from the pattern. All skill output is in English (skills are code, not user-facing prose).

## Usage

- `/skills-mgmt create my-skill` — Scaffold a new skill from the correct archetype
- `/skills-mgmt edit vision` — Edit an existing skill with pattern guidance
- `/skills-mgmt lint all` — Validate all skills + knowledge files
- `/skills-mgmt lint vision` — Validate a single skill
- `/skills-mgmt audit` — Full system audit: dedup, handoff chain integrity, coverage
- `/skills-mgmt dedup` — Find and fix data duplication across files

---

## Skill Archetypes

Every skill belongs to exactly one archetype. The archetype determines required sections.

### Archetype 1: Pipeline Skill (15 skills)

Full 6-step contract. Generates an artifact. Has a gate.

**Skills:** vision, solution-overview, business-process, tech-research, codebase-map, adr, blueprint, domain-model, containers, context-map, epic-breakdown, roadmap, epic-context, verify, reconcile.

**Required sections:**

```markdown
---
description: <1-line English — what it generates>
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
  # Add more if needed (e.g., epic for L2 skills)
argument-hint: "[platform-name]"
handoffs:
  - label: <Next Skill Label>
    agent: madruga/<next-skill>
    prompt: "<1-2 sentences context for the next skill>"
---

# <Name> — <Subtitle>

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-<layer>.md`.

<1-2 paragraph description of what this skill does.>

## Cardinal Rule: ZERO <Negative Constraint>

<What this skill NEVER does. Specific, testable.>

**NEVER:**
- <list of forbidden actions>

## Persona

<Who the AI simulates. Layer-specific expertise.> Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/madruga:<skill-name> <platform>` (or `/speckit.<skill-name>` for SpecKit nodes) — Direct mode
- `/madruga:<skill-name>` (or `/speckit.<skill-name>`) — Interactive mode (prompt for platform)

## Output Directory

Save to `platforms/<name>/<path>`.

## Instructions

### 1. Collect Context + Ask Questions
<Skill-specific context collection. References contract-base Step 1.>

### 2. Generate <Artifact>
<Skill-specific artifact template. All prose in PT-BR, code/YAML in EN.>

### Auto-Review Additions
<Skill-specific checks beyond the contract-base checks.>

## Error Handling

| Problem | Action |
|---------|--------|
| <problem> | <action> |
```

**Validation rules:**
- Frontmatter MUST have: description, arguments, argument-hint, handoffs
- Handoff `agent:` target MUST match an existing `.claude/commands/madruga/<name>.md` or `speckit.<name>`
- MUST reference contract-base via `> **Contract**:` blockquote
- MUST have: Cardinal Rule, Persona, Usage, Output Directory, Instructions, Error Handling
- Instructions MUST have sections 1 (context) and 2 (generate) — steps 0, 3, 4, 5 come from contract-base
- Persona MUST include "Write all generated artifact content in Brazilian Portuguese (PT-BR)"
- Auto-Review Additions table MUST exist (even if only artifact-specific checks)
- Cardinal Rule MUST be testable (not vague)
- ZERO contract steps duplicated from pipeline-contract-base.md

### Archetype 2: Specialist Skill (2 skills)

Phase-based structure. Own workflow. References applicable contract steps.

**Skills:** qa, reconcile (partially — reconcile is mostly pipeline but has phases).

**Required sections:**

```markdown
---
description: <1-line English>
arguments: [...]
argument-hint: "<hint>"
handoffs:
  - label: <next>
    agent: madruga/<next>
    prompt: "<context>"
---

# <Name> — <Subtitle>

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

## Cardinal Rule: ZERO <Constraint>

## Persona

## Usage

## Instructions
### Phase 0: <Setup>
### Phase 1-N: <Phases>

## Error Handling
```

**Validation rules:**
- MUST reference at least steps 0 and 5 from contract-base
- Phases are numbered (Phase 0, Phase 1, etc.)
- MUST have Cardinal Rule, Persona, Usage, Error Handling
- QA specifically: MUST have `disable-model-invocation: true`

### Archetype 3: Utility Skill (3 skills)

Lightweight. No artifact generation. No gate.

**Skills:** pipeline, checkpoint, getting-started.

**Required sections:**

```markdown
---
description: <1-line English>
arguments: [...]
argument-hint: "<hint>"
---

# <Name> — <Subtitle>

## Persona

## Usage

## Instructions

## Error Handling
```

**Validation rules:**
- Frontmatter: description, arguments, argument-hint (handoffs optional)
- No contract reference required (but allowed)
- pipeline skill: MUST NOT generate artifacts or execute pipeline steps
- checkpoint: MUST base everything on git log / filesystem (no invented data)

---

## Instructions by Action

### Action: `create`

1. **Ask for skill details:**
   - Name (kebab-case)
   - Purpose (1-2 sentences)
   - Archetype (pipeline / specialist / utility) — suggest based on purpose
   - Layer (business / research / engineering / planning / utility) — determines which contract extension applies
   - Gate type (human / auto / 1-way-door / auto-escalate)
   - DAG position (depends on which skills, feeds into which skills)

2. **Check for conflicts:**
   - Does a skill with this name already exist?
   - Does this skill's purpose overlap with an existing skill? (Check descriptions)
   - Is the DAG position valid? (Dependencies must exist)

3. **Scaffold the skill** using the archetype template above.

4. **Update dependent files:**
   - Add the node to `pipeline-dag-knowledge.md` (L1 or L2 table)
   - If pipeline skill: update `check-platform-prerequisites.sh` if needed
   - If pipeline skill: update `pipeline-contract-base.md` ONLY if this skill introduces a new contract step (very rare)
   - Update CLAUDE.md pipeline tables ONLY if the L1/L2 table changed

5. **Run lint** on the new skill (see lint action below).

6. **Report:**
   ```
   ## Skill Created

   **File:** .claude/commands/madruga/<name>.md
   **Archetype:** pipeline | specialist | utility
   **Layer:** <layer>
   **Gate:** <gate>
   **DAG position:** after <deps> → before <next>

   ### Checklist
   - [x] Skill file created
   - [x] DAG node added to pipeline-dag-knowledge.md
   - [x] Handoff chain valid
   - [x] Lint passed
   ```

### Action: `edit`

1. **Read the target skill** completely.
2. **Identify its archetype** from the classification above.
3. **Apply the requested change** while enforcing:
   - No duplication of contract-base content
   - Handoff targets still valid after edit
   - Frontmatter fields complete
   - Archetype-required sections present
4. **Run lint** on the edited skill.
5. **Check cascading impact:** Does this edit affect other skills? (e.g., changing a handoff target, renaming an artifact path)

### Action: `lint`

Run the validation script:

```bash
python3 .specify/scripts/skill-lint.py [--skill <name> | --all]
```

If the script does not exist, perform manual validation:

**For each target skill, check:**

| # | Check | Severity | How |
|---|-------|----------|-----|
| 1 | YAML frontmatter parses correctly | BLOCKER | Parse YAML between `---` markers |
| 2 | Required frontmatter fields present (per archetype) | BLOCKER | Check description, arguments, argument-hint |
| 3 | `handoffs.agent` target exists as a file | BLOCKER | Glob `.claude/commands/madruga/<name>.md` or check speckit |
| 4 | Contract reference present (pipeline/specialist) | WARNING | Grep for `> **Contract**:` |
| 5 | All archetype-required sections present | WARNING | Grep for section headings |
| 6 | No contract-base steps duplicated in skill body | WARNING | Check for step 0/3/4/5 content that belongs in contract-base |
| 7 | Persona includes PT-BR directive | NIT | Grep for "Brazilian Portuguese" or "PT-BR" |
| 8 | Error Handling table present | NIT | Grep for "Error Handling" + table markers |
| 9 | Description is 1 line, English, under 120 chars | NIT | Check frontmatter |
| 10 | argument-hint matches arguments list | NIT | Cross-reference |

**For knowledge files, check:**

| # | Check | Severity |
|---|-------|----------|
| 1 | No data duplicated across knowledge files | BLOCKER |
| 2 | Every knowledge file is referenced by at least one skill | WARNING |
| 3 | No orphan knowledge files | WARNING |

**Report format:**

```
## Lint Report

| Skill | Archetype | Status | Issues |
|-------|-----------|--------|--------|
| vision | pipeline | PASS | — |
| qa | specialist | WARN | Missing PT-BR directive |
| ... | ... | ... | ... |

### Issues
- [BLOCKER] <skill>: <description>
- [WARNING] <skill>: <description>
- [NIT] <skill>: <description>

**Result:** X PASS, Y WARN, Z BLOCKER
```

### Action: `audit`

Full system-wide audit. Runs lint on all skills PLUS:

1. **Handoff chain integrity:**
   - Start from `platform-new` (L1 root) and follow handoffs to the end
   - Every pipeline skill must be reachable from the root
   - No broken links, no orphan skills (except utilities)
   - L2 chain: epic-context → speckit.specify → ... → reconcile

2. **DAG ↔ Skills consistency:**
   - Every node in `pipeline-dag-knowledge.md` has a matching `.md` file
   - Every `.md` file in `commands/madruga/` is either in the DAG or classified as utility
   - Gate types in DAG match what the skill implements

3. **Knowledge file coverage:**
   - Every `pipeline-contract-*.md` is referenced by at least one skill
   - No knowledge file contains data that belongs in another file (per SSOT map)

4. **Archetype compliance:**
   - Each skill classified into its archetype
   - Deviations flagged with recommendation

5. **Report** with all findings, organized by severity.

### Action: `dedup`

Scan for data duplication across all files in `.claude/knowledge/`, `.claude/commands/madruga/`, and `CLAUDE.md`.

**Known duplication hotspots:**

| Data | Likely duplicated in | Canonical source |
|------|---------------------|-----------------|
| L1/L2 node tables | CLAUDE.md, pipeline-dag-knowledge.md | `pipeline-dag-knowledge.md` |
| Gate types | CLAUDE.md, pipeline-dag-knowledge.md, pipeline-contract-base.md | `pipeline-dag-knowledge.md` |
| 6-step contract | pipeline-dag-knowledge.md, pipeline-contract-base.md | `pipeline-contract-base.md` |
| Structured questions | pipeline-dag-knowledge.md, pipeline-contract-base.md | `pipeline-contract-base.md` |
| Auto-review checklist | pipeline-dag-knowledge.md, pipeline-contract-base.md | `pipeline-contract-base.md` |
| Handoff examples | pipeline-dag-knowledge.md | `pipeline-dag-knowledge.md` |

**For each duplication found:**
1. Identify the canonical source (per SSOT map)
2. Show the duplicate with file + line
3. Propose: remove from non-canonical file, or convert to a reference (`See pipeline-contract-base.md Step 1`)
4. Present all proposals for approval before making changes

---

## Frontmatter Field Reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `description` | ALL | string | 1-line English. What the skill does. Under 120 chars. |
| `arguments` | ALL | array | Each: name, description, required (bool) |
| `argument-hint` | ALL | string | Usage hint shown in help (e.g., "[platform-name]") |
| `handoffs` | Pipeline, Specialist | array | Each: label, agent, prompt. Forward edge of DAG. |
| `disable-model-invocation` | QA only | bool | Prevents auto-invocation. Only for human-gated specialists. |

---

## Knowledge File Conventions

| Convention | Rule |
|------------|------|
| Naming | `pipeline-contract-*.md` for contracts, `pipeline-dag-*.md` for DAG, `*-syntax.md` for language refs, `qa-*.md` for QA |
| Language | English (knowledge files are technical, not user-facing) |
| Cross-references | Use relative paths: `See pipeline-contract-base.md Step 1` |
| No prose duplication | If two knowledge files describe the same concept, one must reference the other |

---

## Future Improvements (encode in skill, implement later)

These patterns are documented here for future implementation. Do NOT implement them during create/edit actions unless explicitly requested.

### PostToolUse Hook for post_save.py

Automate SQLite recording via Claude Code hooks. Add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write",
      "hooks": [{
        "type": "command",
        "command": "FILE=$(cat | jq -r '.tool_input.file_path // empty'); if echo \"$FILE\" | grep -qE 'platforms/[^/]+/(business|engineering|decisions|research|planning|epics)/'; then python3 .specify/scripts/post_save.py --detect-from-path \"$FILE\" 2>/dev/null; fi"
      }]
    }]
  }
}
```

**Status:** Requires `--detect-from-path` flag in post_save.py (not yet implemented). PostToolUse hooks have known reliability issues (GitHub #5314, #6305).

### Trigger Precision Testing

Use skill-creator eval mode to verify skill descriptions don't overlap. Priority for skills with similar names (e.g., vision vs. solution-overview, verify vs. qa).

### Multi-File Skill Format Migration

Migrate from `.claude/commands/madruga/*.md` to `.claude/skills/madruga/*/SKILL.md` with co-located `references/` directories. This would co-locate knowledge files with their consuming skills. Not urgent — current convention-based approach works.

### agnix Integration

Run `agnix` linter alongside custom `skill-lint.py` for broader validation (304 rules). Requires external dependency.

---

## Error Handling

| Problem | Action |
|---------|--------|
| Skill name conflicts with existing | Suggest alternative name or confirm overwrite |
| Handoff target does not exist | BLOCKER — create target first or fix handoff |
| Archetype unclear | Ask user: "Does this skill generate an artifact? Does it have a gate?" |
| Knowledge file referenced but missing | BLOCKER — create it or fix reference |
| Dedup found but canonical source unclear | Ask user which file should be canonical |
| Lint script not found | Fall back to manual validation (inline checks) |
| CLAUDE.md out of sync with DAG | Propose minimal update to CLAUDE.md (summary only, not full tables) |
