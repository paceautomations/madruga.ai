"""Typed error hierarchy and validation primitives for the madruga pipeline."""

from __future__ import annotations

import re

# ── Constants ────────────────────────────────────────────────────────

VALID_GATES = frozenset({"auto", "human", "1-way-door", "auto-escalate"})

PLATFORM_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")

REPO_COMPONENT_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


# ── Error hierarchy ──────────────────────────────────────────────────


class MadrugaError(Exception):
    """Base error for all madruga pipeline failures."""


class ValidationError(MadrugaError):
    """Input validation failure (platform name, path, DAG field)."""


class PipelineError(MadrugaError):
    """DAG structural or execution error (cycle, missing dep)."""


class DispatchError(PipelineError):
    """Skill dispatch failure (subprocess / claude -p)."""


class GateError(PipelineError):
    """Gate evaluation error."""


# ── Validation functions ─────────────────────────────────────────────


def validate_platform_name(name: str) -> None:
    """Raise ValidationError if *name* is not a valid platform name.

    Valid: lowercase ASCII letters, digits, hyphens; must start with a letter.
    """
    if not name or not PLATFORM_NAME_RE.match(name):
        raise ValidationError(
            f"Invalid platform name '{name}'. "
            "Must be kebab-case: lowercase letters, digits, hyphens. Start with a letter."
        )


def validate_path_safe(path: str) -> None:
    """Raise ValidationError if *path* contains '..' segments (path traversal)."""
    if ".." in path.split("/"):
        raise ValidationError(f"Unsafe path '{path}': contains '..' segment (path traversal).")


def validate_repo_component(value: str, label: str = "component") -> None:
    """Raise ValidationError if *value* is not a safe repo org or name.

    Valid: ASCII letters, digits, dots, underscores, hyphens; non-empty.
    """
    if not value or not REPO_COMPONENT_RE.match(value):
        raise ValidationError(
            f"Invalid repo {label} '{value}'. Must contain only letters, digits, dots, underscores, or hyphens."
        )
