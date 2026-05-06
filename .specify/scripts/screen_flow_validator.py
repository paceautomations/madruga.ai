#!/usr/bin/env python3
"""screen_flow_validator.py — validate screen-flow.yaml + platform.yaml.screen_flow block.

Implements FR-002, FR-003, FR-048, FR-049 of epic 027-screen-flow-canvas:
- Validates screen-flow.yaml against `.specify/schemas/screen-flow.schema.json` (closed
  vocabulary v1: 10 body types, 4 edge styles, 3 capture states, schema_version=1).
- Cross-field lint: refs (from/to/on) consistency, ID uniqueness inside a screen, scale
  limits (warn >50 screens, hard reject >100), capture_profile match.
- Helper for `platform_cli.py lint`: validate `screen_flow:` block + compile path_rules
  regex (FR-010).

Outputs:
- exit 0 → valid (warnings allowed)
- exit 1 → BLOCKER finding(s) detected
- Findings include JSON-pointer path; line numbers are best-effort (pyyaml does not
  preserve full provenance for semantic errors).

CLI:
    python3 screen_flow_validator.py <yaml-path> [--platform-block] [--json]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover — jsonschema is a documented runtime dep
    jsonschema = None
    Draft202012Validator = None

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_DIR = REPO_ROOT / ".specify" / "schemas"
SCREEN_FLOW_SCHEMA = SCHEMA_DIR / "screen-flow.schema.json"
PLATFORM_SCHEMA = SCHEMA_DIR / "platform-yaml-screen-flow.schema.json"

ID_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Closed vocabulary mirrored from screen-flow.schema.json — kept here for fast checks
# without re-walking the schema. Source of truth is the JSON file.
BODY_TYPES = {
    "heading",
    "text",
    "input",
    "button",
    "link",
    "list",
    "card",
    "image",
    "divider",
    "badge",
}
EDGE_STYLES = {"success", "error", "neutral", "modal"}
CAPTURE_STATES = {"pending", "captured", "failed"}
SUPPORTED_SCHEMA_VERSIONS = {1}

WARN_SCREEN_COUNT = 50  # FR-049 — warn threshold
MAX_SCREEN_COUNT = 100  # FR-049 — hard reject

log = logging.getLogger("screen_flow_validator")


# ───────────────────────────────────────────────────────────────────────────────
# Findings model
# ───────────────────────────────────────────────────────────────────────────────


def _finding(severity: str, path: str, message: str, line: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"severity": severity, "path": path, "message": message}
    if line is not None:
        out["line"] = line
    return out


# ───────────────────────────────────────────────────────────────────────────────
# Schema loading
# ───────────────────────────────────────────────────────────────────────────────


def load_schema(path: Path = SCREEN_FLOW_SCHEMA) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_platform_schema() -> dict[str, Any]:
    return load_schema(PLATFORM_SCHEMA)


# ───────────────────────────────────────────────────────────────────────────────
# Custom (cross-field) validation — runs AFTER jsonschema
# ───────────────────────────────────────────────────────────────────────────────


def _check_schema_version(data: dict) -> list[dict]:
    """FR-002 — schema_version is mandatory and must be a known version."""
    findings: list[dict] = []
    sv = data.get("schema_version")
    if sv is None:
        findings.append(
            _finding(
                "BLOCKER",
                "schema_version",
                f"Field 'schema_version' missing. Add 'schema_version: 1' at the top. "
                f"Supported versions: {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
            )
        )
    elif sv not in SUPPORTED_SCHEMA_VERSIONS:
        findings.append(
            _finding(
                "BLOCKER",
                "schema_version",
                f"Unknown schema_version={sv!r}. Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
            )
        )
    return findings


def _check_screen_id_charset(data: dict) -> list[dict]:
    """FR-048 — screen.id and body.id must match ^[a-z][a-z0-9_]{0,63}$."""
    findings: list[dict] = []
    for i, screen in enumerate(data.get("screens") or []):
        sid = screen.get("id")
        if sid is not None and not ID_REGEX.match(str(sid)):
            findings.append(
                _finding(
                    "BLOCKER",
                    f"screens[{i}].id",
                    f"Invalid id {sid!r}. Allowed charset: lowercase letters, digits, "
                    f"underscores; must start with a letter; max 64 chars (regex {ID_REGEX.pattern}).",
                )
            )
        for j, body in enumerate(screen.get("body") or []):
            bid = body.get("id")
            if bid is not None and not ID_REGEX.match(str(bid)):
                findings.append(
                    _finding(
                        "BLOCKER",
                        f"screens[{i}].body[{j}].id",
                        f"Invalid id {bid!r}. Same charset rule as screen.id.",
                    )
                )
    for k, flow in enumerate(data.get("flows") or []):
        for field in ("from", "to", "on"):
            v = flow.get(field)
            if v is not None and not ID_REGEX.match(str(v)):
                findings.append(
                    _finding(
                        "BLOCKER",
                        f"flows[{k}].{field}",
                        f"Invalid id {v!r}. Same charset rule as screen.id.",
                    )
                )
    return findings


def _check_unique_screen_ids(data: dict) -> list[dict]:
    findings: list[dict] = []
    seen: dict[str, int] = {}
    for i, screen in enumerate(data.get("screens") or []):
        sid = screen.get("id")
        if sid is None:
            continue
        if sid in seen:
            findings.append(
                _finding(
                    "BLOCKER",
                    f"screens[{i}].id",
                    f"Duplicate screen id {sid!r} (first defined at screens[{seen[sid]}]).",
                )
            )
        else:
            seen[sid] = i
    return findings


def _check_unique_body_ids(data: dict) -> list[dict]:
    findings: list[dict] = []
    for i, screen in enumerate(data.get("screens") or []):
        seen: dict[str, int] = {}
        for j, body in enumerate(screen.get("body") or []):
            bid = body.get("id")
            if bid is None:
                continue
            if bid in seen:
                findings.append(
                    _finding(
                        "BLOCKER",
                        f"screens[{i}].body[{j}].id",
                        f"Duplicate body.id {bid!r} within screen {screen.get('id')!r} (first at body[{seen[bid]}]).",
                    )
                )
            else:
                seen[bid] = j
    return findings


def _check_flow_refs(data: dict) -> list[dict]:
    """FR-003 — every flow.from/to references an existing screen.id; flow.on references
    an existing body.id of the source screen."""
    findings: list[dict] = []
    screen_index: dict[str, dict] = {}
    for screen in data.get("screens") or []:
        sid = screen.get("id")
        if isinstance(sid, str):
            screen_index[sid] = screen
    declared = sorted(screen_index)
    for k, flow in enumerate(data.get("flows") or []):
        src_id = flow.get("from")
        dst_id = flow.get("to")
        on_id = flow.get("on")
        if src_id and src_id not in screen_index:
            findings.append(
                _finding(
                    "BLOCKER",
                    f"flows[{k}].from",
                    f"flow.from {src_id!r} does not match any declared screen.id. Available: {declared}",
                )
            )
        if dst_id and dst_id not in screen_index:
            findings.append(
                _finding(
                    "BLOCKER",
                    f"flows[{k}].to",
                    f"flow.to {dst_id!r} does not match any declared screen.id. Available: {declared}",
                )
            )
        # flow.on must reference a body.id of the source screen
        if on_id and src_id and src_id in screen_index:
            body_ids = {b.get("id") for b in (screen_index[src_id].get("body") or []) if b.get("id")}
            if on_id not in body_ids:
                findings.append(
                    _finding(
                        "BLOCKER",
                        f"flows[{k}].on",
                        f"flow.on {on_id!r} does not match any body.id in screen "
                        f"{src_id!r}. Available body ids: {sorted(body_ids)}",
                    )
                )
    return findings


def _check_scale_limits(data: dict) -> list[dict]:
    """FR-049 — warn >50, reject >100."""
    findings: list[dict] = []
    screens = data.get("screens") or []
    n = len(screens)
    if n > MAX_SCREEN_COUNT:
        findings.append(
            _finding(
                "BLOCKER",
                "screens",
                f"Too many screens ({n} > {MAX_SCREEN_COUNT}). Split into multiple "
                f"screen-flow*.yaml files by bounded context.",
            )
        )
    elif n > WARN_SCREEN_COUNT:
        findings.append(
            _finding(
                "WARNING",
                "screens",
                f"Screen count ({n}) exceeds soft limit ({WARN_SCREEN_COUNT}). "
                f"Consider splitting by bounded context before reaching {MAX_SCREEN_COUNT}.",
            )
        )
    return findings


def _check_capture_profile_match(data: dict) -> list[dict]:
    """meta.capture_profile must match every screens[].meta.capture_profile when set."""
    findings: list[dict] = []
    meta = data.get("meta") or {}
    expected = meta.get("capture_profile")
    if not expected:
        return findings
    for i, screen in enumerate(data.get("screens") or []):
        smeta = screen.get("meta") or {}
        sp = smeta.get("capture_profile")
        if sp is not None and sp != expected:
            findings.append(
                _finding(
                    "BLOCKER",
                    f"screens[{i}].meta.capture_profile",
                    f"capture_profile {sp!r} does not match meta.capture_profile {expected!r}.",
                )
            )
    return findings


def _check_status_consistency(data: dict) -> list[dict]:
    """status=captured ⇔ image+capture present; status=failed ⇔ failure present."""
    findings: list[dict] = []
    for i, screen in enumerate(data.get("screens") or []):
        st = screen.get("status")
        has_image = "image" in screen
        has_capture = "capture" in screen
        has_failure = "failure" in screen
        if st == "captured":
            if not has_image:
                findings.append(_finding("BLOCKER", f"screens[{i}].image", "status=captured requires 'image'"))
            if not has_capture:
                findings.append(
                    _finding(
                        "BLOCKER",
                        f"screens[{i}].capture",
                        "status=captured requires 'capture' record",
                    )
                )
        if st == "failed" and not has_failure:
            findings.append(_finding("BLOCKER", f"screens[{i}].failure", "status=failed requires 'failure' block"))
    return findings


# ───────────────────────────────────────────────────────────────────────────────
# JSON Schema validation
# ───────────────────────────────────────────────────────────────────────────────


def _jsonschema_findings(data: Any, schema: dict) -> list[dict]:
    if Draft202012Validator is None:
        return [_finding("BLOCKER", "$", "jsonschema package not installed — cannot validate schema")]
    validator = Draft202012Validator(schema)
    findings: list[dict] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path_parts = [str(p) for p in err.absolute_path]
        path_str = ".".join(path_parts) if path_parts else "$"
        findings.append(_finding("BLOCKER", path_str, err.message))
    return findings


# ───────────────────────────────────────────────────────────────────────────────
# Top-level validation entry points
# ───────────────────────────────────────────────────────────────────────────────


def _check_yaml11_boolean_collision(data: Any) -> list[dict]:
    """YAML 1.1 treats `on/off/yes/no` as booleans. Unquoted `on: cta_x` in flows
    parses to ``{True: "cta_x"}`` which then trips JSON Schema with the cryptic
    message ``"Additional properties not allowed (True was unexpected)"``.

    Detect ``True`` (or other boolean) keys at the flow level and emit an
    actionable hint pointing the author at the quoting fix.
    """
    findings: list[dict] = []
    if not isinstance(data, dict):
        return findings
    flows = data.get("flows")
    if not isinstance(flows, list):
        return findings
    for i, flow in enumerate(flows):
        if not isinstance(flow, dict):
            continue
        if True in flow or False in flow:
            findings.append(
                _finding(
                    "BLOCKER",
                    f"flows.{i}",
                    "YAML 1.1 boolean key collision: `on:` parsed as Python True. "
                    'Quote the key: `"on": cta_xxx` (PyYAML aliases on/off/yes/no '
                    "to booleans). See screen-flow.yaml flows examples in "
                    ".claude/commands/madruga/business-screen-flow.md.",
                )
            )
    return findings


def validate_screen_flow_dict(data: Any) -> list[dict]:
    """Validate a parsed screen-flow YAML (already loaded as dict).

    Schema version is checked first (gate); other checks are run independently
    so the user sees as many errors as possible per run.
    """
    if not isinstance(data, dict):
        return [_finding("BLOCKER", "$", f"Top-level YAML must be a mapping, got {type(data).__name__}")]

    findings: list[dict] = []
    # Run BEFORE jsonschema so the YAML 1.1 hint shows above generic schema errors.
    findings.extend(_check_yaml11_boolean_collision(data))
    findings.extend(_check_schema_version(data))
    # Run JSON Schema validation regardless — even with bad schema_version it
    # gives more information about other structural issues.
    schema = load_schema()
    findings.extend(_jsonschema_findings(data, schema))
    findings.extend(_check_screen_id_charset(data))
    findings.extend(_check_unique_screen_ids(data))
    findings.extend(_check_unique_body_ids(data))
    findings.extend(_check_flow_refs(data))
    findings.extend(_check_scale_limits(data))
    findings.extend(_check_capture_profile_match(data))
    findings.extend(_check_status_consistency(data))
    return _dedupe(findings)


def validate_path_rules(rules: list[dict]) -> list[dict]:
    """FR-010 — every PathRule.pattern must compile as a Python regex."""
    findings: list[dict] = []
    for i, rule in enumerate(rules or []):
        pat = rule.get("pattern") if isinstance(rule, dict) else None
        if not pat:
            continue
        try:
            re.compile(pat)
        except re.error as exc:
            findings.append(
                _finding(
                    "BLOCKER",
                    f"capture.path_rules[{i}].pattern",
                    f"Invalid regex {pat!r}: {exc}",
                )
            )
    return findings


def validate_platform_screen_flow_block(block: Any) -> list[dict]:
    """Validate `platform.yaml.screen_flow:` against platform schema + path_rules regex."""
    if block is None:
        return []  # absence is allowed — feature is opt-in
    if not isinstance(block, dict):
        return [_finding("BLOCKER", "screen_flow", f"screen_flow must be a mapping, got {type(block).__name__}")]
    findings: list[dict] = []
    findings.extend(_jsonschema_findings(block, load_platform_schema()))
    capture = block.get("capture") if isinstance(block, dict) else None
    if isinstance(capture, dict):
        findings.extend(validate_path_rules(capture.get("path_rules") or []))
    return _dedupe(findings)


def validate_yaml_string(text: str) -> list[dict]:
    """Parse a YAML string then validate. Surface YAML parse errors as findings."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        line = None
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        return [_finding("BLOCKER", "$", f"YAML parse error: {exc}", line=line)]
    return validate_screen_flow_dict(data)


def validate_file(path: Path, *, mode: str = "screen-flow") -> tuple[int, list[dict]]:
    """Validate a YAML file. mode='screen-flow' or 'platform-block'."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return 1, [_finding("BLOCKER", str(path), f"Cannot read file: {exc}")]

    if mode == "platform-block":
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return 1, [_finding("BLOCKER", "$", f"YAML parse error: {exc}")]
        block = (data or {}).get("screen_flow")
        findings = validate_platform_screen_flow_block(block)
    else:
        findings = validate_yaml_string(text)
    blockers = [f for f in findings if f["severity"] == "BLOCKER"]
    return (1 if blockers else 0), findings


_TESTID_RE = re.compile(r"""testID=["']([^"']+)["']""")


def scan_source_testids(source_root: Path) -> set[str]:
    """Walk the bound repo's source files and collect every `testID="..."` string.

    Used by ``--check-testids`` to flag YAML body components whose ``testid``
    references don't exist in the actual app — silent drift between the spec
    and reality (capture pipeline FR-028 requires the testID to exist).
    """
    found: set[str] = set()
    if not source_root.exists():
        return found
    for ext in ("*.tsx", "*.ts", "*.jsx", "*.js"):
        for path in source_root.rglob(ext):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found.update(_TESTID_RE.findall(text))
    return found


def check_testids_against_source(data: dict, source_root: Path) -> list[dict]:
    """Walk YAML body components and warn when their `testid` is not declared
    in the source. Best-effort — missing source dir returns []."""
    actual = scan_source_testids(source_root)
    if not actual:
        return []
    findings: list[dict] = []
    screens = data.get("screens") or []
    for s_idx, screen in enumerate(screens):
        if not isinstance(screen, dict):
            continue
        for b_idx, body in enumerate(screen.get("body") or []):
            if not isinstance(body, dict):
                continue
            tid = body.get("testid")
            if tid and tid not in actual:
                findings.append(
                    _finding(
                        "WARNING",
                        f"screens.{s_idx}.body.{b_idx}.testid",
                        f"testid {tid!r} not found in source — capture pipeline (FR-028) "
                        f'will fail to bind hotspot. Either add `testID="{tid}"` to the '
                        f"component or remove from YAML.",
                    )
                )
    return findings


def _dedupe(findings: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for f in findings:
        key = (f.get("severity"), f.get("path"), f.get("message"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


# ───────────────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────────────


def _print_findings(path: Path, findings: list[dict]) -> None:
    for f in findings:
        loc = f"line {f['line']}" if f.get("line") else f["path"]
        print(f"  {f['severity']:7s}  {loc}  {f['message']}", file=sys.stderr)
    blockers = sum(1 for f in findings if f["severity"] == "BLOCKER")
    warnings = sum(1 for f in findings if f["severity"] == "WARNING")
    if blockers or warnings:
        print(f"{path}: {blockers} blocker(s), {warnings} warning(s)", file=sys.stderr)
    else:
        print(f"{path}: ok", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml_path", help="Path to YAML file to validate")
    parser.add_argument(
        "--platform-block",
        action="store_true",
        help="Treat the file as platform.yaml; validate the screen_flow: block",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument(
        "--check-testids",
        metavar="SOURCE_ROOT",
        help="Path to bound repo source (e.g. ../resenhai-expo). When set, warn "
        "for every body.testid not found in the source's testID= attributes.",
    )
    args = parser.parse_args(argv)

    path = Path(args.yaml_path)
    mode = "platform-block" if args.platform_block else "screen-flow"
    code, findings = validate_file(path, mode=mode)
    if args.check_testids and mode == "screen-flow":
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            extra = check_testids_against_source(data, Path(args.check_testids))
            findings.extend(extra)
        except (OSError, yaml.YAMLError):
            pass
    if args.json:
        print(json.dumps({"ok": code == 0, "findings": findings}, indent=2))
    else:
        _print_findings(path, findings)
    return code


if __name__ == "__main__":
    sys.exit(main())
