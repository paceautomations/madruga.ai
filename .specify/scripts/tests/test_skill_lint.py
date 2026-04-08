"""Tests for skill-lint.py extensions (knowledge graph, impact analysis)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util

# skill-lint.py has a hyphen, so we need importlib machinery
_spec = importlib.util.spec_from_file_location(
    "skill_lint",
    Path(__file__).resolve().parent.parent / "skill-lint.py",
)
skill_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skill_lint)


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — parse_frontmatter, get_archetype, resolve_handoff_target, lint_skill
# ──────────────────────────────────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\ndescription: Test skill\narguments: []\n---\n\n# Body"
        result = skill_lint.parse_frontmatter(text)
        assert result is not None
        assert result["description"] == "Test skill"

    def test_no_frontmatter(self):
        result = skill_lint.parse_frontmatter("# No frontmatter here")
        assert result is None

    def test_invalid_yaml(self):
        text = "---\nkey: [unclosed\n---\n\nBody"
        result = skill_lint.parse_frontmatter(text)
        assert result is None


class TestGetArchetype:
    def test_pipeline(self):
        assert skill_lint.get_archetype("vision") == "pipeline"
        assert skill_lint.get_archetype("blueprint") == "pipeline"

    def test_specialist(self):
        assert skill_lint.get_archetype("judge") == "specialist"

    def test_utility(self):
        assert skill_lint.get_archetype("pipeline") == "utility"
        assert skill_lint.get_archetype("getting-started") == "utility"

    def test_unknown(self):
        assert skill_lint.get_archetype("nonexistent-skill") == "unknown"


class TestResolveHandoffTarget:
    def test_existing_madruga_skill(self):
        # vision.md should exist
        result = skill_lint.resolve_handoff_target("madruga/vision")
        assert result is not None

    def test_nonexistent_madruga_skill(self):
        result = skill_lint.resolve_handoff_target("madruga/does-not-exist")
        assert result is None

    def test_speckit_skill_trusted(self):
        result = skill_lint.resolve_handoff_target("speckit.implement")
        assert result == Path("external")

    def test_unknown_prefix(self):
        result = skill_lint.resolve_handoff_target("other/something")
        assert result is None


class TestLintSkill:
    def test_missing_file(self, tmp_path):
        findings = skill_lint.lint_skill("test", tmp_path / "nonexistent.md")
        assert len(findings) == 1
        assert findings[0]["severity"] == "BLOCKER"
        assert "not found" in findings[0]["message"]

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# No frontmatter\nJust a body.")
        findings = skill_lint.lint_skill("test", f)
        assert any(f["severity"] == "BLOCKER" and "frontmatter" in f["message"] for f in findings)

    def test_missing_description(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\narguments: []\n---\n\n# Body")
        findings = skill_lint.lint_skill("test", f)
        assert any("description" in f["message"] for f in findings)

    def test_long_description_nit(self, tmp_path):
        f = tmp_path / "test.md"
        long_desc = "x" * 160
        f.write_text(f"---\ndescription: {long_desc}\narguments: []\n---\n\n# Body")
        findings = skill_lint.lint_skill("test", f)
        assert any("too long" in f["message"] for f in findings)

    def test_valid_pipeline_skill(self, tmp_path):
        f = tmp_path / "vision.md"
        f.write_text(
            "---\n"
            "description: Generate vision\n"
            "arguments:\n"
            "  - name: platform\n"
            "argument-hint: '[platform]'\n"
            "handoffs:\n"
            "  - label: Next\n"
            "    agent: madruga/solution-overview\n"
            "    prompt: Generate\n"
            "---\n\n"
            "# Vision\n"
            "## Cardinal Rule\nNo scope creep\n"
            "## Persona\nBrazilian Portuguese strategist\n"
            "## Usage\n/madruga:vision\n"
            "## Output Directory\nplatforms/<name>/business/\n"
            "## Error Handling\nFail gracefully\n"
            "## Auto-Review\nCheck all\n"
            "pipeline-contract-base\n"
        )
        findings = skill_lint.lint_skill("vision", f)
        blockers = [f for f in findings if f["severity"] == "BLOCKER"]
        assert len(blockers) == 0

    def test_pipeline_missing_handoffs_warning(self, tmp_path):
        f = tmp_path / "vision.md"
        f.write_text("---\ndescription: Test\narguments: []\n---\n\n# Body")
        findings = skill_lint.lint_skill("vision", f)
        assert any("handoffs" in f["message"].lower() for f in findings)

    def test_invalid_gate_value(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ndescription: Test\narguments: []\ngate: invalid_gate\n---\n\n# Body")
        findings = skill_lint.lint_skill("test", f)
        assert any("Invalid gate" in f["message"] for f in findings)

    def test_handoff_to_nonexistent_target(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "---\n"
            "description: Test\n"
            "arguments: []\n"
            "handoffs:\n"
            "  - label: Next\n"
            "    agent: madruga/does-not-exist-at-all\n"
            "    prompt: go\n"
            "---\n\n# Body"
        )
        findings = skill_lint.lint_skill("test", f)
        assert any("does not exist" in f["message"] for f in findings)


class TestLintKnowledgeFiles:
    def test_returns_list(self):
        findings = skill_lint.lint_knowledge_files()
        assert isinstance(findings, list)


class TestLintHandoffChain:
    def test_returns_list(self):
        findings = skill_lint.lint_handoff_chain()
        assert isinstance(findings, list)


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests (existing)
# ──────────────────────────────────────────────────────────────────────────────


def test_build_knowledge_graph():
    """Verify graph matches known references on disk (no mocks)."""
    graph = skill_lint.build_knowledge_graph()

    # pipeline-contract-engineering.md is referenced by at least the core 5 engineering skills
    eng_skills = graph.get("pipeline-contract-engineering.md", set())
    expected_eng = {"adr", "blueprint", "containers", "context-map", "domain-model"}
    assert expected_eng.issubset(eng_skills) and len(eng_skills) >= 5, (
        f"Expected at least {sorted(expected_eng)} in engineering skills, got {sorted(eng_skills)}"
    )

    # pipeline-contract-base.md is referenced by 20 skills
    base_skills = graph.get("pipeline-contract-base.md", set())
    assert len(base_skills) >= 20, (
        f"Expected >=20 skills referencing pipeline-contract-base.md, got {len(base_skills)}: {sorted(base_skills)}"
    )

    # commands.md is a knowledge file but no skill references it
    assert "commands.md" not in graph, f"commands.md should not be in graph, but found: {graph.get('commands.md')}"


def test_impact_of_known_file():
    """cmd_impact_of returns 5 pipeline skills for pipeline-contract-engineering.md."""
    results = skill_lint.cmd_impact_of("pipeline-contract-engineering.md")

    assert len(results) >= 5, f"Expected at least 5 impacted skills, got {len(results)}: {results}"

    expected_skills = {"adr", "blueprint", "containers", "context-map", "domain-model"}
    actual_skills = {r["skill"] for r in results}
    assert expected_skills.issubset(actual_skills), (
        f"Expected skills {sorted(expected_skills)} to be subset of {sorted(actual_skills)}"
    )

    # Every skill should have archetype "pipeline"
    for r in results:
        assert r["archetype"] == "pipeline", f"Skill {r['skill']} has archetype '{r['archetype']}', expected 'pipeline'"


def test_impact_of_unknown_file():
    """cmd_impact_of returns empty list for a file no skill references."""
    results = skill_lint.cmd_impact_of("nonexistent-file.md")

    assert results == [], f"Expected empty list, got {results}"


def test_lint_knowledge_declarations_valid():
    """No warnings when platform.yaml declares knowledge files that exist and match refs."""
    import tempfile
    import textwrap

    # Build the graph to find knowledge files that actually have consumers
    graph = skill_lint.build_knowledge_graph()
    knowledge_dir = skill_lint.KNOWLEDGE_DIR

    # Declare ALL knowledge files that have consumers and exist on disk
    files_with_consumers = [f for f in sorted(graph.keys()) if (knowledge_dir / f).exists()]
    assert len(files_with_consumers) >= 1, "Need at least 1 knowledge file with consumers for this test"

    # Build a valid knowledge: section declaring real files with their real consumers
    entries = []
    for f in files_with_consumers:
        consumers = sorted(graph[f])
        consumer_list = ", ".join(consumers)
        entries.append(f"  - file: {f}\n    consumers: [{consumer_list}]")

    # Minimal platform.yaml with pipeline nodes so all-pipeline can resolve
    knowledge_block = "\n".join(entries)
    yaml_content = (
        textwrap.dedent("""\
        name: test-platform
        pipeline:
          nodes:
            - id: vision
              skill: "madruga:vision"
              outputs: ["business/vision.md"]
          epic_cycle:
            nodes:
              - id: epic-context
                skill: "madruga:epic-context"
                outputs: ["pitch.md"]
        knowledge:
    """)
        + knowledge_block
        + "\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml_content)
        tmp.flush()
        tmp_path = Path(tmp.name)

    try:
        findings = skill_lint.lint_knowledge_declarations(tmp_path)
        warnings = [f for f in findings if f.get("severity") == "WARNING"]
        assert warnings == [], f"Expected no warnings, got {warnings}"
    finally:
        tmp_path.unlink()


def test_lint_knowledge_declarations_missing_file():
    """WARNING when platform.yaml declares a knowledge file that doesn't exist on disk."""
    import tempfile
    import textwrap

    yaml_content = textwrap.dedent("""\
        name: test-platform
        pipeline:
          nodes:
            - id: vision
              skill: "madruga:vision"
              outputs: ["business/vision.md"]
          epic_cycle:
            nodes:
              - id: epic-context
                skill: "madruga:epic-context"
                outputs: ["pitch.md"]
        knowledge:
          - file: this-file-does-not-exist.md
            consumers: [vision]
    """)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml_content)
        tmp.flush()
        tmp_path = Path(tmp.name)

    try:
        findings = skill_lint.lint_knowledge_declarations(tmp_path)

        # Must have at least one finding about the missing file
        missing = [f for f in findings if "this-file-does-not-exist.md" in f.get("message", "")]
        assert len(missing) >= 1, f"Expected WARNING for missing file, got {findings}"

        # Severity must be WARNING, never BLOCKER
        for f in missing:
            assert f["severity"] == "WARNING", f"Expected WARNING severity, got '{f['severity']}' for: {f['message']}"
    finally:
        tmp_path.unlink()


def test_lint_knowledge_declarations_undeclared_ref():
    """WARNING when a skill references a knowledge file not declared in platform.yaml."""
    import tempfile
    import textwrap

    # Build the graph to find a real knowledge file referenced by skills
    graph = skill_lint.build_knowledge_graph()
    knowledge_dir = skill_lint.KNOWLEDGE_DIR

    # Pick a file that exists on disk and has consumers — we'll omit it from declarations
    undeclared_file = None
    for f in sorted(graph.keys()):
        if (knowledge_dir / f).exists() and len(graph[f]) > 0:
            undeclared_file = f
            break
    assert undeclared_file is not None, "Need at least 1 referenced knowledge file for this test"

    # platform.yaml with an empty knowledge section — deliberately missing undeclared_file
    yaml_content = textwrap.dedent("""\
        name: test-platform
        pipeline:
          nodes:
            - id: vision
              skill: "madruga:vision"
              outputs: ["business/vision.md"]
          epic_cycle:
            nodes:
              - id: epic-context
                skill: "madruga:epic-context"
                outputs: ["pitch.md"]
        knowledge: []
    """)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml_content)
        tmp.flush()
        tmp_path = Path(tmp.name)

    try:
        findings = skill_lint.lint_knowledge_declarations(tmp_path)

        # Must have at least one WARNING about the undeclared file
        undeclared = [f for f in findings if undeclared_file in f.get("message", "")]
        assert len(undeclared) >= 1, f"Expected WARNING for undeclared '{undeclared_file}', got {findings}"

        # Severity must be WARNING, never BLOCKER
        for f in undeclared:
            assert f["severity"] == "WARNING", f"Expected WARNING severity, got '{f['severity']}' for: {f['message']}"
    finally:
        tmp_path.unlink()


def test_all_pipeline_resolution():
    """all-pipeline resolves to all L1 + L2 node IDs from pipeline.yaml."""
    import tempfile
    import textwrap
    from unittest.mock import patch

    # pipeline.yaml with known L1 and L2 nodes (top-level keys, no wrapper)
    yaml_content = textwrap.dedent("""\
        nodes:
          - id: vision
            skill: "madruga:vision"
            outputs: ["business/vision.md"]
          - id: adr
            skill: "madruga:adr"
            outputs: ["decisions/ADR-*.md"]
          - id: blueprint
            skill: "madruga:blueprint"
            outputs: ["engineering/blueprint.md"]
        epic_cycle:
          nodes:
            - id: epic-context
              skill: "madruga:epic-context"
              outputs: ["pitch.md"]
            - id: judge
              skill: "madruga:judge"
              outputs: ["judge-report.md"]
    """)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml_content)
        tmp.flush()
        tmp_path = Path(tmp.name)

    try:
        with patch("config.PIPELINE_YAML", tmp_path):
            resolved = skill_lint.resolve_all_pipeline()

        expected = {"vision", "adr", "blueprint", "epic-context", "judge"}
        assert resolved == expected, f"Expected all-pipeline to resolve to {sorted(expected)}, got {sorted(resolved)}"
    finally:
        tmp_path.unlink()
