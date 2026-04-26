#!/usr/bin/env python3
"""Lint madruga.ai skills and knowledge files for pattern compliance.

Usage:
    python3 .specify/scripts/skill-lint.py              # lint all skills
    python3 .specify/scripts/skill-lint.py --skill vision  # lint one skill
    python3 .specify/scripts/skill-lint.py --json          # JSON output
    python3 .specify/scripts/skill-lint.py --impact-of pipeline-contract-base.md  # impact analysis
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from errors import VALID_GATES

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands" / "madruga"
KNOWLEDGE_DIR = REPO_ROOT / ".claude" / "knowledge"
PLATFORMS_DIR = REPO_ROOT / "platforms"

log = logging.getLogger(__name__)

# Archetype classification
PIPELINE_SKILLS = {
    "platform-new",
    "vision",
    "solution-overview",
    "business-process",
    "tech-research",
    "codebase-map",
    "adr",
    "blueprint",
    "domain-model",
    "containers",
    "context-map",
    "roadmap",
    "epic-context",
    "verify",
    "reconcile",
}
SPECIALIST_SKILLS = {"qa", "judge"}
UTILITY_SKILLS = {"pipeline", "checkpoint", "getting-started", "skills-mgmt", "ship", "pair-program"}

SEVERITY_ORDER = {"BLOCKER": 0, "WARNING": 1, "NIT": 2}

# Cache skill file contents for a single lint run (avoids re-reading per function)
_skill_text_cache: dict[str, str] = {}


def _get_skill_texts() -> dict[str, str]:
    """Return {skill_name: file_text} for all skills. Cached per process."""
    if not _skill_text_cache:
        for skill_path in COMMANDS_DIR.glob("*.md"):
            try:
                _skill_text_cache[skill_path.stem] = skill_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                log.warning("UnicodeDecodeError reading %s, skipping", skill_path)
    return _skill_text_cache


def parse_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter between --- markers."""
    match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    if not match:
        return None
    try:
        import yaml

        return yaml.safe_load(match.group(1))
    except Exception:
        return None


def get_archetype(name: str) -> str:
    if name in PIPELINE_SKILLS:
        return "pipeline"
    if name in SPECIALIST_SKILLS:
        return "specialist"
    if name in UTILITY_SKILLS:
        return "utility"
    return "unknown"


def resolve_handoff_target(agent: str) -> Path | None:
    """Check if a handoff agent target exists as a file."""
    if agent.startswith("madruga/"):
        skill_name = agent.split("/", 1)[1]
        path = COMMANDS_DIR / f"{skill_name}.md"
        return path if path.exists() else None
    if agent.startswith("speckit."):
        # SpecKit skills are external — trust they exist
        return Path("external")
    return None


def lint_skill(name: str, path: Path) -> list[dict]:
    """Lint a single skill file. Returns list of findings."""
    findings = []

    def add(severity: str, msg: str):
        findings.append({"skill": name, "severity": severity, "message": msg})

    if not path.exists():
        add("BLOCKER", f"File not found: {path}")
        return findings

    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    archetype = get_archetype(name)

    # --- Frontmatter checks ---
    if fm is None:
        add("BLOCKER", "YAML frontmatter missing or unparseable")
        return findings

    if not fm.get("description"):
        add("BLOCKER", "Missing 'description' in frontmatter")
    elif len(fm["description"]) > 150:
        add("NIT", f"Description too long ({len(fm['description'])} chars, max 120 recommended)")

    if "arguments" not in fm:
        add("WARNING", "Missing 'arguments' in frontmatter")

    if "argument-hint" not in fm:
        add("NIT", "Missing 'argument-hint' in frontmatter")

    # Gate value validation
    gate = fm.get("gate")
    if gate is not None and gate not in VALID_GATES:
        add("ERROR", f"Invalid gate value '{gate}'. Valid: {sorted(VALID_GATES)}")

    # Handoffs check (all archetypes)
    handoffs = fm.get("handoffs", [])
    if archetype in ("pipeline", "specialist"):
        if not handoffs:
            add("WARNING", "Missing 'handoffs' in frontmatter (required for pipeline/specialist)")
    if handoffs:
        for h in handoffs:
            agent = h.get("agent", "")
            target = resolve_handoff_target(agent)
            if target is None:
                add("BLOCKER", f"Handoff target '{agent}' does not exist")
            if not h.get("label"):
                add("NIT", f"Handoff to '{agent}' missing 'label'")
            if not h.get("prompt"):
                add("NIT", f"Handoff to '{agent}' missing 'prompt'")

    # --- Body checks ---
    body = text.split("---", 2)[-1] if text.startswith("---") else text

    # Contract reference (pipeline and specialist)
    if archetype == "pipeline":
        if "pipeline-contract-base" not in body:
            add("WARNING", "No reference to pipeline-contract-base.md")

    if archetype == "specialist":
        if "pipeline-contract-base" not in body:
            add("WARNING", "No reference to pipeline-contract-base.md (at least steps 0 and 5)")

    # Output Directory check (all archetypes)
    if "## Output Directory" not in body:
        add("WARNING", "Missing '## Output Directory' section")

    # Required sections by archetype
    if archetype == "pipeline":
        for section in ["Cardinal Rule", "Persona", "Usage", "Error Handling"]:
            if section not in body:
                add("WARNING", f"Missing required section: '{section}'")
        if "Auto-Review" not in body and "Auto-review" not in body:
            add("WARNING", "Missing Auto-Review section")

    if archetype == "specialist":
        for section in ["Cardinal Rule", "Persona", "Usage", "Error Handling"]:
            if section not in body:
                add("WARNING", f"Missing required section: '{section}'")

    if archetype == "utility":
        for section in ["Usage", "Error Handling"]:
            if section not in body:
                add("NIT", f"Missing recommended section: '{section}'")

    # PT-BR directive in persona
    if archetype in ("pipeline", "specialist"):
        if "Brazilian Portuguese" not in body and "PT-BR" not in body:
            add("NIT", "Persona missing PT-BR language directive")

    # Contract duplication check (pipeline skills should NOT redefine contract steps)
    if archetype == "pipeline":
        # Check for duplicated Step 0 prerequisites boilerplate
        if "### 0. Prerequisites" in body or "### Step 0" in body:
            # Allowed if it's just a reference, not a full redefinition
            step0_section = re.search(r"###\s+(?:Step\s+)?0[.:]\s*Prerequisites(.*?)(?=###|\Z)", body, re.DOTALL)
            if step0_section and len(step0_section.group(1).strip()) > 200:
                add("WARNING", "Step 0 Prerequisites appears duplicated from contract-base (should be a reference)")

    return findings


def lint_knowledge_files() -> list[dict]:
    """Check knowledge files for orphans and cross-references."""
    findings = []

    if not KNOWLEDGE_DIR.exists():
        return findings

    knowledge_files = list(KNOWLEDGE_DIR.glob("*.md"))
    all_skill_text = "".join(_get_skill_texts().values())

    for kf in knowledge_files:
        if kf.name not in all_skill_text and kf.stem not in all_skill_text:
            findings.append(
                {
                    "skill": f"knowledge/{kf.name}",
                    "severity": "WARNING",
                    "message": f"Knowledge file '{kf.name}' not referenced by any skill",
                }
            )

    return findings


def lint_handoff_chain() -> list[dict]:
    """Verify L1 handoff chain from platform-new to roadmap."""
    findings = []
    visited = set()
    current = "platform-new"

    for _ in range(20):  # safety limit
        if current in visited:
            findings.append(
                {
                    "skill": current,
                    "severity": "BLOCKER",
                    "message": f"Handoff cycle detected at '{current}'",
                }
            )
            break
        visited.add(current)

        path = COMMANDS_DIR / f"{current}.md"
        if not path.exists():
            findings.append(
                {
                    "skill": current,
                    "severity": "BLOCKER",
                    "message": f"Handoff chain broken: '{current}' file not found",
                }
            )
            break

        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm or not fm.get("handoffs"):
            break  # end of chain (utility or terminal node)

        next_agent = fm["handoffs"][0].get("agent", "")
        if next_agent.startswith("madruga/"):
            current = next_agent.split("/", 1)[1]
        else:
            break  # crosses into speckit namespace — chain complete for L1

    # Check that key L1 nodes were visited
    expected_l1 = {
        "platform-new",
        "vision",
        "solution-overview",
        "business-process",
        "tech-research",
        "adr",
        "blueprint",
        "domain-model",
        "containers",
        "context-map",
        "roadmap",
    }
    missing = expected_l1 - visited
    if missing:
        findings.append(
            {
                "skill": "handoff-chain",
                "severity": "WARNING",
                "message": f"L1 handoff chain does not reach: {', '.join(sorted(missing))}",
            }
        )

    return findings


def build_knowledge_graph() -> dict[str, set[str]]:
    """Build reverse map: knowledge_filename -> set of skill names that reference it.

    Scans all skill files in COMMANDS_DIR for knowledge file references.
    Only files that are actually referenced appear as keys.
    """
    graph: dict[str, set[str]] = {}

    if not KNOWLEDGE_DIR.exists() or not COMMANDS_DIR.exists():
        return graph

    knowledge_files = {kf.name for kf in KNOWLEDGE_DIR.glob("*.md")}

    for skill_name, text in _get_skill_texts().items():
        for kf_name in knowledge_files:
            if kf_name in text:
                graph.setdefault(kf_name, set()).add(skill_name)

    return graph


def cmd_impact_of(filename: str) -> list[dict]:
    """Return list of {skill, archetype} dicts for skills referencing filename."""
    graph = build_knowledge_graph()
    skill_names = graph.get(filename, set())
    return [{"skill": name, "archetype": get_archetype(name)} for name in sorted(skill_names)]


def _extract_pipeline_node_ids() -> set[str]:
    """Extract all pipeline node IDs from .specify/pipeline.yaml."""
    from config import load_pipeline

    node_ids: set[str] = set()
    pipeline = load_pipeline()
    if not isinstance(pipeline, dict):
        return node_ids
    for node in pipeline.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            node_ids.add(node["id"])
    epic_cycle = pipeline.get("epic_cycle") or {}
    if isinstance(epic_cycle, dict):
        for node in epic_cycle.get("nodes") or []:
            if isinstance(node, dict) and node.get("id"):
                node_ids.add(node["id"])
    return node_ids


def resolve_all_pipeline() -> set[str]:
    """Resolve 'all-pipeline' token to all node IDs from pipeline.yaml."""
    return _extract_pipeline_node_ids()


def lint_knowledge_declarations(yaml_path: Path) -> list[dict]:
    """Check platform.yaml knowledge: section against actual skill references.

    Returns list of finding dicts with keys: skill, severity, message.
    """
    import yaml as _yaml

    findings: list[dict] = []

    try:
        data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        findings.append({"skill": str(yaml_path), "severity": "WARNING", "message": f"Could not parse YAML: {exc}"})
        return findings

    if not isinstance(data, dict):
        return findings

    knowledge_section = data.get("knowledge") or []
    if not isinstance(knowledge_section, list):
        knowledge_section = []

    all_pipeline_nodes = _extract_pipeline_node_ids()

    # Build declared map: {filename -> set of declared consumer skill IDs}
    declared: dict[str, set[str]] = {}
    for entry in knowledge_section:
        if not isinstance(entry, dict):
            continue
        fname = entry.get("file")
        if not fname:
            continue
        consumers = entry.get("consumers", [])
        if consumers == "all-pipeline" or consumers == ["all-pipeline"]:
            declared[fname] = set(all_pipeline_nodes)
        elif isinstance(consumers, list):
            declared[fname] = set(consumers)
        else:
            declared[fname] = set()

        # Check declared files exist on disk
        if not (KNOWLEDGE_DIR / fname).exists():
            findings.append(
                {
                    "skill": f"knowledge/{fname}",
                    "severity": "WARNING",
                    "message": f"Declared knowledge file '{fname}' does not exist in {KNOWLEDGE_DIR}",
                }
            )

    # Build actual reference graph
    graph = build_knowledge_graph()

    # Check that every referenced knowledge file is declared
    for kf_name, skill_names in graph.items():
        if kf_name not in declared:
            findings.append(
                {
                    "skill": f"knowledge/{kf_name}",
                    "severity": "WARNING",
                    "message": (
                        f"Knowledge file '{kf_name}' is referenced by skills "
                        f"({', '.join(sorted(skill_names))}) but not declared in platform.yaml knowledge:"
                    ),
                }
            )

    return findings


def main():
    parser = argparse.ArgumentParser(description="Lint madruga.ai skills")
    parser.add_argument("--skill", help="Lint a single skill by name")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--impact-of", dest="impact_of", metavar="FILE", help="Show skills impacted by a knowledge file"
    )
    args = parser.parse_args()

    # --impact-of: short-circuit, print impact analysis and exit
    if args.impact_of:
        results = cmd_impact_of(args.impact_of)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print(f"No skills reference '{args.impact_of}'")
            else:
                print(f"\n## Impact of {args.impact_of}\n")
                print("| Skill | Archetype |")
                print("|-------|-----------|")
                for r in results:
                    print(f"| {r['skill']} | {r['archetype']} |")
                print(f"\n{len(results)} skill(s) impacted.")
        sys.exit(0)

    all_findings = []

    if args.skill:
        path = COMMANDS_DIR / f"{args.skill}.md"
        all_findings.extend(lint_skill(args.skill, path))
    else:
        # Lint all skills
        for skill_path in sorted(COMMANDS_DIR.glob("*.md")):
            name = skill_path.stem
            all_findings.extend(lint_skill(name, skill_path))

        # Lint knowledge files
        all_findings.extend(lint_knowledge_files())

        # Lint handoff chain
        all_findings.extend(lint_handoff_chain())

    # Sort by severity
    all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))

    if args.json:
        print(json.dumps(all_findings, indent=2))
    else:
        blockers = [f for f in all_findings if f["severity"] == "BLOCKER"]
        warnings = [f for f in all_findings if f["severity"] == "WARNING"]
        nits = [f for f in all_findings if f["severity"] == "NIT"]

        # Summary table
        skills_checked = set()
        skill_status = {}
        for f in all_findings:
            s = f["skill"]
            skills_checked.add(s)
            if f["severity"] == "BLOCKER":
                skill_status[s] = "FAIL"
            elif f["severity"] == "WARNING" and skill_status.get(s) != "FAIL":
                skill_status[s] = "WARN"
            elif s not in skill_status:
                skill_status[s] = "PASS"

        # Add skills with no findings
        if not args.skill:
            for skill_path in sorted(COMMANDS_DIR.glob("*.md")):
                name = skill_path.stem
                if name not in skill_status:
                    skill_status[name] = "PASS"
                    skills_checked.add(name)

        print("\n## Lint Report\n")
        print("| Skill | Archetype | Status |")
        print("|-------|-----------|--------|")
        for name in sorted(skill_status.keys()):
            arch = get_archetype(name) if "/" not in name else "knowledge"
            status = skill_status[name]
            icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[status]
            print(f"| {name} | {arch} | {icon} |")

        if blockers:
            print(f"\n### BLOCKERS ({len(blockers)})")
            for f in blockers:
                print(f"- [{f['severity']}] {f['skill']}: {f['message']}")

        if warnings:
            print(f"\n### WARNINGS ({len(warnings)})")
            for f in warnings:
                print(f"- [{f['severity']}] {f['skill']}: {f['message']}")

        if nits:
            print(f"\n### NITS ({len(nits)})")
            for f in nits:
                print(f"- [{f['severity']}] {f['skill']}: {f['message']}")

        total = len(skill_status)
        passing = sum(1 for v in skill_status.values() if v == "PASS")
        print(
            f"\n**Result:** {passing}/{total} PASS, "
            f"{sum(1 for v in skill_status.values() if v == 'WARN')} WARN, "
            f"{sum(1 for v in skill_status.values() if v == 'FAIL')} FAIL"
        )

    sys.exit(1 if any(f["severity"] == "BLOCKER" for f in all_findings) else 0)


if __name__ == "__main__":
    main()
