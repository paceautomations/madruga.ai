"""
decision_classifier.py — Risk score calculation for decision classification.

Classifies decisions as 1-way-door (irreversible, score >= 15) or
2-way-door (reversible, score < 15) based on pattern matching against
a risk patterns table.

Score formula: Risk (1-5) × Reversibility (1-5)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

THRESHOLD = 15  # score >= 15 = 1-way-door


@dataclass(frozen=True)
class RiskScore:
    """Result of classifying a decision."""

    pattern: str
    risk: int
    reversibility: int
    score: int
    classification: str  # "1-way-door" or "2-way-door"

    def is_oneway(self) -> bool:
        return self.classification == "1-way-door"


# --- Risk Patterns Table ---
# Each entry: (pattern_name, keywords_regex, risk, reversibility)
# Keywords are matched case-insensitively against the decision description.

RISK_PATTERNS: list[tuple[str, str, int, int]] = [
    (
        "schema_drop",
        r"drop\s+(column|table)|delete\s+column|remove\s+column",
        5,
        5,
    ),
    (
        "delete_production_data",
        r"delete\s+data|truncate|purge\s+data|wipe\s+data",
        5,
        5,
    ),
    (
        "change_public_api_contract",
        r"change\s+contract|modify\s+api\s+contract|change\s+schema\s+public|breaking\s+api",
        5,
        5,
    ),
    (
        "change_auth_security",
        r"change\s+auth|modify\s+security|change\s+encryption|replace\s+auth",
        5,
        4,
    ),
    (
        "remove_public_endpoint",
        r"remove\s+endpoint|delete\s+endpoint|deprecate\s+endpoint|remove\s+route",
        5,
        3,
    ),
    (
        "remove_feature",
        r"remove\s+feature|breaking\s+change|remove\s+support|drop\s+feature",
        4,
        3,
    ),
    (
        "add_public_endpoint",
        r"add\s+endpoint|new\s+endpoint|new\s+route|create\s+endpoint",
        3,
        2,
    ),
    (
        "new_dependency",
        r"add\s+dependency|new\s+library|new\s+package|add\s+package",
        3,
        2,
    ),
    (
        "schema_add",
        r"add\s+column|add\s+nullable|add\s+index|create\s+table|new\s+migration",
        2,
        1,
    ),
    (
        "rename_refactor",
        r"rename|refactor|move\s+file|reorganize",
        1,
        1,
    ),
]

# Default when no pattern matches
_DEFAULT_RISK = 2
_DEFAULT_REVERSIBILITY = 2


def classify_decision(description: str) -> RiskScore:
    """Classify a decision description against the risk patterns table.

    Returns a RiskScore with the matched pattern, risk/reversibility scores,
    calculated score, and classification (1-way-door or 2-way-door).

    If no pattern matches, returns a safe default (2-way-door, score=4).
    """
    desc_lower = description.lower()

    for pattern_name, keywords_re, risk, reversibility in RISK_PATTERNS:
        if re.search(keywords_re, desc_lower):
            score = risk * reversibility
            classification = "1-way-door" if score >= THRESHOLD else "2-way-door"
            return RiskScore(
                pattern=pattern_name,
                risk=risk,
                reversibility=reversibility,
                score=score,
                classification=classification,
            )

    # No pattern matched — safe default
    score = _DEFAULT_RISK * _DEFAULT_REVERSIBILITY
    classification = "1-way-door" if score >= THRESHOLD else "2-way-door"
    return RiskScore(
        pattern="unknown",
        risk=_DEFAULT_RISK,
        reversibility=_DEFAULT_REVERSIBILITY,
        score=score,
        classification=classification,
    )
