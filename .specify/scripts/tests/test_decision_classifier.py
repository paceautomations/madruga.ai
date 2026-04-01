"""Tests for decision_classifier.py — risk score calculation, pattern matching, and YAML config validation."""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decision_classifier import RiskScore, THRESHOLD, classify_decision


class TestRiskScore:
    """Test the RiskScore dataclass."""

    def test_is_oneway_true(self):
        rs = RiskScore("test", 5, 5, 25, "1-way-door")
        assert rs.is_oneway() is True

    def test_is_oneway_false(self):
        rs = RiskScore("test", 1, 1, 1, "2-way-door")
        assert rs.is_oneway() is False

    def test_frozen(self):
        rs = RiskScore("test", 1, 1, 1, "2-way-door")
        try:
            rs.score = 99  # type: ignore
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestThreshold:
    """Test threshold constant."""

    def test_threshold_is_15(self):
        assert THRESHOLD == 15


class TestCalibrationCases:
    """Test all 7 calibration cases from plan.md R4."""

    def test_sqlite_wal_mode_equivalent(self):
        """ADR-012 equivalent: add column (low risk, reversible)."""
        result = classify_decision("add column status to pipeline_runs")
        assert result.score < THRESHOLD
        assert result.classification == "2-way-door"

    def test_drop_column(self):
        """Drop column = irreversible data loss."""
        result = classify_decision("drop column legacy_id from users table")
        assert result.score == 25
        assert result.classification == "1-way-door"
        assert result.is_oneway()

    def test_copier_templates_equivalent(self):
        """ADR-002 equivalent: new dependency (moderate risk, reversible)."""
        result = classify_decision("add dependency copier for template management")
        assert result.score < THRESHOLD
        assert result.classification == "2-way-door"

    def test_rename_internal_variable(self):
        """Trivial rename = lowest risk."""
        result = classify_decision("rename internal variable from x to descriptive_name")
        assert result.score == 1
        assert result.classification == "2-way-door"

    def test_remove_public_endpoint(self):
        """Removing a public endpoint = 1-way-door."""
        result = classify_decision("remove endpoint /api/v1/legacy from public API")
        assert result.score == 15
        assert result.classification == "1-way-door"
        assert result.is_oneway()

    def test_delete_production_data(self):
        """Deleting production data = catastrophic 1-way-door."""
        result = classify_decision("delete data from production users table")
        assert result.score == 25
        assert result.classification == "1-way-door"

    def test_change_public_api_contract(self):
        """Changing public API contract = irreversible breaking change."""
        result = classify_decision("change contract for /api/v2/orders response format")
        assert result.score == 25
        assert result.classification == "1-way-door"


class TestThresholdBoundary:
    """Test boundary conditions around threshold=15."""

    def test_score_14_is_two_way(self):
        """Score just below threshold = 2-way-door."""
        # remove_feature: risk=4 × reversibility=3 = 12 < 15
        result = classify_decision("remove feature legacy notifications")
        assert result.score == 12
        assert result.classification == "2-way-door"
        assert not result.is_oneway()

    def test_score_15_is_one_way(self):
        """Score exactly at threshold = 1-way-door (inclusive)."""
        # remove_public_endpoint: risk=5 × reversibility=3 = 15
        result = classify_decision("remove endpoint /health from API")
        assert result.score == 15
        assert result.classification == "1-way-door"
        assert result.is_oneway()


class TestUnknownPattern:
    """Test behavior when no pattern matches."""

    def test_unknown_defaults_to_two_way(self):
        result = classify_decision("do something completely unknown and unusual")
        assert result.pattern == "unknown"
        assert result.classification == "2-way-door"
        assert result.score == 4  # default 2*2

    def test_score_minimum_is_zero_or_positive(self):
        """Score is always >= 0 (risk and reversibility are both >= 1)."""
        result = classify_decision("some random action")
        assert result.score >= 0


class TestPatternMatching:
    """Test that patterns match correctly."""

    def test_case_insensitive(self):
        result = classify_decision("DROP COLUMN id FROM users")
        assert result.pattern == "schema_drop"
        assert result.is_oneway()

    def test_truncate_matches_delete_data(self):
        result = classify_decision("truncate the events table")
        assert result.pattern == "delete_production_data"
        assert result.is_oneway()

    def test_change_auth(self):
        result = classify_decision("change auth mechanism from JWT to OAuth2")
        assert result.pattern == "change_auth_security"
        assert result.score == 20
        assert result.is_oneway()

    def test_new_endpoint_is_safe(self):
        result = classify_decision("add endpoint /api/v2/health for monitoring")
        assert result.classification == "2-way-door"

    def test_add_index_is_safe(self):
        result = classify_decision("add index on users.email column")
        assert result.classification == "2-way-door"

    def test_refactor_is_safe(self):
        result = classify_decision("refactor the auth module for clarity")
        assert result.classification == "2-way-door"
        assert result.score == 1


# --- YAML config validation tests (T025) ---


class TestJudgeConfigValidation:
    """Test YAML config structure validation."""

    def _load_config(self):
        import yaml

        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", ".claude", "knowledge", "judge-config.yaml"
        )
        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_valid_config_has_review_teams(self):
        config = self._load_config()
        assert "review_teams" in config
        assert len(config["review_teams"]) >= 1

    def test_engineering_team_has_required_fields(self):
        config = self._load_config()
        team = config["review_teams"]["engineering"]
        assert "name" in team
        assert "personas" in team
        assert "runs_at" in team
        assert len(team["personas"]) == 4

    def test_each_persona_has_required_fields(self):
        config = self._load_config()
        for persona in config["review_teams"]["engineering"]["personas"]:
            assert "id" in persona, f"Missing 'id' in persona: {persona}"
            assert "role" in persona, f"Missing 'role' in persona: {persona}"
            assert "prompt" in persona, f"Missing 'prompt' in persona: {persona}"

    def test_persona_prompt_files_exist(self):
        config = self._load_config()
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
        for persona in config["review_teams"]["engineering"]["personas"]:
            prompt_path = os.path.join(repo_root, persona["prompt"])
            assert os.path.isfile(prompt_path), f"Prompt file not found: {persona['prompt']}"

    def test_multiple_teams_config_structure(self):
        """Verify that config supports multiple teams (even if only engineering exists now)."""
        import yaml

        multi_config = yaml.safe_load("""
review_teams:
  engineering:
    name: "Tech Reviewers"
    personas:
      - id: arch-reviewer
        role: "Arch"
        prompt: "a.md"
    runs_at: [tier3-l1]
  product:
    name: "Product Reviewers"
    personas:
      - id: pm-reviewer
        role: "PM"
        prompt: "b.md"
    runs_at: [specify]
""")
        assert len(multi_config["review_teams"]) == 2
        assert "engineering" in multi_config["review_teams"]
        assert "product" in multi_config["review_teams"]
