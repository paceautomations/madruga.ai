"""Tests for the business-screen-flow skill markdown.

Source task: T041 (epic 027-screen-flow-canvas Phase 4 / US2).

Skills are markdown files (no executable Python). These tests assert that the
skill file:
- Exists at the expected path.
- Has the contractual frontmatter (description, handoffs, output dir).
- States its Cardinal Rule about NEVER inventing screens without process.md.
- Mentions the opt-out behaviour (FR-014) and process.md dependency (FR-012).
- Documents the schema_version: 1 output requirement (FR-002).
- Passes the project-wide skill-lint with zero BLOCKER findings (FR-046).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_PATH = REPO_ROOT / ".claude" / "commands" / "madruga" / "business-screen-flow.md"

sys.path.insert(0, str(REPO_ROOT / ".specify" / "scripts"))

# skill-lint.py has a hyphen — load via importlib.
_spec = importlib.util.spec_from_file_location(
    "skill_lint",
    REPO_ROOT / ".specify" / "scripts" / "skill-lint.py",
)
skill_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skill_lint)


@pytest.fixture(scope="module")
def skill_text() -> str:
    if not SKILL_PATH.exists():
        pytest.fail(f"Skill markdown not found at {SKILL_PATH}")
    return SKILL_PATH.read_text(encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────────
# File existence + frontmatter
# ───────────────────────────────────────────────────────────────────────────────


def test_skill_file_exists():
    assert SKILL_PATH.exists(), f"Missing skill: {SKILL_PATH}"


def test_frontmatter_parseable(skill_text):
    fm = skill_lint.parse_frontmatter(skill_text)
    assert fm is not None, "Frontmatter unparseable"
    assert fm.get("description"), "Frontmatter missing 'description'"


def test_frontmatter_has_handoffs(skill_text):
    fm = skill_lint.parse_frontmatter(skill_text)
    handoffs = fm.get("handoffs") or []
    assert handoffs, "Skill must declare at least one handoff"
    for h in handoffs:
        assert h.get("agent"), f"Handoff missing 'agent': {h}"


def test_frontmatter_arguments_block(skill_text):
    fm = skill_lint.parse_frontmatter(skill_text)
    args = fm.get("arguments") or []
    assert args, "Skill must declare arguments block"
    assert any(a.get("name") == "platform" for a in args), "Arguments must include 'platform'"


# ───────────────────────────────────────────────────────────────────────────────
# Body / required content
# ───────────────────────────────────────────────────────────────────────────────


def test_has_cardinal_rule_about_process_md(skill_text):
    assert "## Cardinal Rule" in skill_text or "Cardinal Rule" in skill_text
    assert "process.md" in skill_text, "Skill must reference process.md as input"


def test_rejects_when_process_md_missing(skill_text):
    """FR-012 — skill MUST fail clearly if business/process.md does not exist."""
    lower = skill_text.lower()
    assert "process.md" in lower
    # Either explicit ERROR/abort wording or directs the user to run business-process
    assert any(
        token in lower
        for token in ("não encontrado", "missing", "execute /madruga:business-process", "business-process")
    ), "Skill must explain to run business-process when process.md is absent"


def test_rejects_opt_out_platforms(skill_text):
    """FR-014 — when screen_flow.enabled is false, skill MUST exit gracefully."""
    lower = skill_text.lower()
    assert "enabled" in lower or "opt-out" in lower or "skip_reason" in lower, (
        "Skill must mention the opt-out path via screen_flow.enabled / skip_reason"
    )


def test_mentions_schema_version_one(skill_text):
    """FR-002 — output YAML must declare schema_version: 1."""
    assert "schema_version" in skill_text


def test_mentions_closed_vocabulary(skill_text):
    """FR-001 — skill must reference the closed vocabulary (10 body types, 4 edges)."""
    # Skill should mention either the vocabulary file or core enums
    has_vocab_ref = (
        "screen-flow-vocabulary" in skill_text
        or "vocabulário" in skill_text.lower()
        or "vocabulary" in skill_text.lower()
        or "screen-flow.schema.json" in skill_text
    )
    assert has_vocab_ref


def test_output_directory_section(skill_text):
    assert "## Output Directory" in skill_text
    assert "business/screen-flow.yaml" in skill_text


def test_persona_section_present(skill_text):
    assert "## Persona" in skill_text


def test_instructions_section_present(skill_text):
    assert "## Instructions" in skill_text


def test_auto_review_section_present(skill_text):
    # Pipeline-archetype skills must include an auto-review section
    assert "Auto-Review" in skill_text or "Auto-review" in skill_text


def test_pt_br_directive_in_persona(skill_text):
    # Per pipeline contract, persona MUST instruct PT-BR output
    assert "PT-BR" in skill_text or "Brazilian Portuguese" in skill_text or "português" in skill_text.lower()


# ───────────────────────────────────────────────────────────────────────────────
# Project skill-lint integration
# ───────────────────────────────────────────────────────────────────────────────


def test_skill_lint_no_blockers():
    """T046 acceptance — skill must pass `skill-lint` with zero BLOCKER findings."""
    findings = skill_lint.lint_skill("business-screen-flow", SKILL_PATH)
    blockers = [f for f in findings if f.get("severity") == "BLOCKER"]
    assert not blockers, f"skill-lint reported BLOCKERs: {blockers}"


# ───────────────────────────────────────────────────────────────────────────────
# Integration with pipeline.yaml
# ───────────────────────────────────────────────────────────────────────────────


def test_pipeline_yaml_registers_business_screen_flow():
    """Skill MUST be wired into pipeline.yaml as an optional L1 node depending on business-process."""
    import yaml

    pipeline_path = REPO_ROOT / ".specify" / "pipeline.yaml"
    data = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data.get("nodes", [])}
    assert "business-screen-flow" in nodes, "business-screen-flow node missing in pipeline.yaml"
    node = nodes["business-screen-flow"]
    assert node.get("optional") is True, "business-screen-flow must be optional"
    assert "business-process" in (node.get("depends") or []), "must depend on business-process"
    assert "business/screen-flow.yaml" in (node.get("outputs") or []), (
        "must declare business/screen-flow.yaml as output"
    )
    assert node.get("skill") == "madruga:business-screen-flow"
