#!/usr/bin/env python3
"""screen_flow_mark_pending.py — flip `screens[id=X].status` to `pending` (drift).

Implements FR-037 of epic 027-screen-flow-canvas. Driven by reverse-reconcile when
a code commit (matched against `platform.yaml.screen_flow.capture.path_rules`) maps
to a screen whose stored capture is now stale. The renderer surfaces a `AGUARDANDO`
badge for screens in `pending` until the next capture run promotes them back to
`captured`.

Two implementation paths:

1. **ruamel.yaml available** → full round-trip preservation (comments, quoting,
   key order, indent style). Preferred when present.
2. **Fallback (line-based regex)** → preserves comments and order trivially since
   the script only ever rewrites a single line. Scope-aware: the search advances
   into the matching screen record and modifies the FIRST `status:` key found at
   the screen's top-level indent level, refusing to descend into nested mappings
   (`capture.status`, `body[].nested.status`, …).

CLI:
    python3 screen_flow_mark_pending.py --platform <name> --screen-id <id>

Exit codes:
- 0 → success (status flipped, or already `pending` and no-op)
- 1 → BLOCKER: YAML missing, screen_id not found, or parse error
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

log = logging.getLogger("screen_flow_mark_pending")

try:  # pragma: no cover — exercised when ruamel.yaml is on the path
    from ruamel.yaml import YAML  # type: ignore

    _HAS_RUAMEL = True
except ImportError:
    _HAS_RUAMEL = False


def _yaml_path(platform: str) -> Path:
    return REPO_ROOT / "platforms" / platform / "business" / "screen-flow.yaml"


def _screen_exists(text: str, screen_id: str) -> bool:
    """Cheap pre-check using pyyaml — avoids touching the file when the id isn't there."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return False
    for s in data.get("screens") or []:
        if isinstance(s, dict) and s.get("id") == screen_id:
            return True
    return False


def _current_status(text: str, screen_id: str) -> str | None:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    for s in data.get("screens") or []:
        if isinstance(s, dict) and s.get("id") == screen_id:
            return s.get("status")
    return None


# ── ruamel.yaml round-trip path ─────────────────────────────────────────────


def _mark_with_ruamel(path: Path, screen_id: str) -> bool:
    """Round-trip with ruamel.yaml. Returns True if a write occurred."""
    yml = YAML()
    yml.preserve_quotes = True
    yml.indent(mapping=2, sequence=4, offset=2)
    with path.open("r", encoding="utf-8") as fh:
        data = yml.load(fh)
    for s in data.get("screens") or []:
        if s.get("id") == screen_id:
            if s.get("status") == "pending":
                return False
            s["status"] = "pending"
            with path.open("w", encoding="utf-8") as fh:
                yml.dump(data, fh)
            return True
    return False


# ── Line-based fallback ─────────────────────────────────────────────────────

# Matches a screen entry header at the first level under `screens:`. Captures the
# leading indent so the scope-aware status search knows the boundary of the
# current screen record.
_SCREEN_HEADER_RE = re.compile(r"^(?P<indent>\s*)-\s+id:\s*[\"']?(?P<id>[a-z][a-z0-9_]{0,63})[\"']?\s*$")
# Matches a top-level `status:` line. The `value` group strips optional quotes so
# we can normalise to bare `pending`.
_STATUS_LINE_RE = re.compile(r"^(?P<indent>\s*)status:\s*[\"']?(?P<value>[a-z]+)[\"']?\s*$")


def _scope_indent(header_indent: str) -> str:
    """Items of a `- id:` record sit two columns deeper than the dash."""
    # `-` + space = 2 chars, so the inner record indent is header_indent + "  ".
    return header_indent + "  "


def _mark_line_based(path: Path, screen_id: str) -> bool | None:
    """Scope-aware line-based replacement.

    Returns:
        True  → a line was modified and the file was rewritten
        False → screen found but already pending (no-op)
        None  → screen_id not found in the file
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    target_idx: int | None = None
    record_indent: str | None = None
    for i, raw in enumerate(lines):
        m = _SCREEN_HEADER_RE.match(raw.rstrip("\n"))
        if not m:
            continue
        if m.group("id") == screen_id:
            target_idx = i
            record_indent = _scope_indent(m.group("indent"))
            break

    if target_idx is None or record_indent is None:
        return None

    # Walk forward from the header. Stop at next sibling/parent-level item.
    # The target is the FIRST `status:` line at exactly `record_indent`.
    found_status_idx: int | None = None
    for j in range(target_idx + 1, len(lines)):
        raw = lines[j].rstrip("\n")
        if not raw.strip():
            continue
        # Reached another sibling screen header or popped out of the screens block?
        sibling = _SCREEN_HEADER_RE.match(raw)
        if sibling and len(sibling.group("indent")) <= len(record_indent) - 2:
            break
        # Any non-blank line at indent <= record_indent - 2 means we left the screen.
        leading = len(raw) - len(raw.lstrip())
        if leading < len(record_indent) and not raw.lstrip().startswith("#"):
            break
        sm = _STATUS_LINE_RE.match(raw)
        if sm and sm.group("indent") == record_indent:
            found_status_idx = j
            break

    if found_status_idx is None:
        # Defensive: schema requires `status` so this should not happen on valid input.
        return None

    line = lines[found_status_idx]
    sm = _STATUS_LINE_RE.match(line.rstrip("\n"))
    assert sm is not None  # guarded above
    if sm.group("value") == "pending":
        return False

    # Preserve trailing newline if present.
    has_newline = line.endswith("\n")
    new_line = f"{record_indent}status: pending" + ("\n" if has_newline else "")
    lines[found_status_idx] = new_line
    path.write_text("".join(lines), encoding="utf-8")
    return True


# ── Public API ──────────────────────────────────────────────────────────────


def mark_pending(platform: str, screen_id: str) -> int:
    """Flip `screens[id=screen_id].status` to `pending` for the given platform.

    Returns POSIX-style exit code (0 success / no-op, 1 error).
    """
    path = _yaml_path(platform)
    if not path.exists():
        log.error(
            "screen-flow.yaml not found at %s — platform may not have screen_flow enabled "
            "or the artefact has not been generated yet (run /madruga:business-screen-flow)",
            path,
        )
        return 1

    text = path.read_text(encoding="utf-8")
    if not _screen_exists(text, screen_id):
        log.error(
            "screen id %r not found in %s — refusing to modify file",
            screen_id,
            path,
        )
        return 1

    current = _current_status(text, screen_id)
    if current == "pending":
        log.info("screen %r already pending — no-op", screen_id)
        return 0

    if _HAS_RUAMEL:
        try:
            changed = _mark_with_ruamel(path, screen_id)
        except Exception as exc:  # pragma: no cover — defensive
            log.warning("ruamel.yaml round-trip failed (%s); falling back to line-based", exc)
            changed = None
        if changed is True:
            log.info("marked %r → pending (ruamel round-trip)", screen_id)
            return 0
        if changed is False:
            log.info("screen %r already pending — no-op", screen_id)
            return 0

    result = _mark_line_based(path, screen_id)
    if result is True:
        log.info("marked %r → pending (line-based)", screen_id)
        return 0
    if result is False:
        log.info("screen %r already pending — no-op", screen_id)
        return 0
    log.error("could not locate `status:` line for screen %r in %s", screen_id, path)
    return 1


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, help="Platform name (e.g. resenhai)")
    parser.add_argument("--screen-id", required=True, help="Screen id to flip to pending")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    return mark_pending(args.platform, args.screen_id)


if __name__ == "__main__":
    sys.exit(main())
