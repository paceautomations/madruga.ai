"""Apply JSON semantic patches to markdown docs.

Patch format (one patch)::

    {
      "file": "platforms/prosauai/engineering/containers.md",
      "operation": "replace" | "insert_after" | "delete" | "append",
      "anchor_before": "unique text that exists in the file",
      "anchor_after": "text that must come after anchor_before (replace/delete only)",
      "new_content": "markdown content to write",
      "reason": "human explanation",
      "sha_refs": ["abc123"],
      "layer": "engineering"
    }

Operations:
  - replace: delete content between anchor_before (inclusive) and anchor_after (exclusive), insert new_content
  - insert_after: insert new_content immediately after anchor_before
  - delete: same as replace with new_content=""
  - append: append new_content to end of file (anchor_before ignored)

Anchor matching: exact substring first; if not found, fuzzy match via
`difflib.SequenceMatcher` with 90% threshold on lines near the expected region.
Ambiguous anchors (multiple exact matches) abort the patch.

Modes:
  - default (dry-run): writes <file>.proposed next to the target
  - --commit: overwrites the target file

Usage:
    python3 reverse_reconcile_apply.py --patches patches.json [--commit]
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("reverse_reconcile_apply")

_FUZZY_THRESHOLD = 0.90


class PatchError(Exception):
    """Base for patch application failures."""


class AnchorNotFound(PatchError):
    pass


class AmbiguousAnchor(PatchError):
    pass


@dataclass
class PatchResult:
    file: str
    status: str  # "applied", "skipped", "error"
    detail: str
    output_path: Path | None = None


def _find_anchor(text: str, anchor: str) -> int:
    """Return char offset of anchor in text. Raises on miss or ambiguity."""
    exact_matches = []
    start = 0
    while True:
        idx = text.find(anchor, start)
        if idx == -1:
            break
        exact_matches.append(idx)
        start = idx + 1
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise AmbiguousAnchor(f"anchor matched {len(exact_matches)} times (positions: {exact_matches[:5]})")
    # Fuzzy fallback on line sequences
    lines = text.splitlines(keepends=True)
    anchor_lines = anchor.splitlines(keepends=True)
    if not anchor_lines:
        raise AnchorNotFound("empty anchor")
    window = len(anchor_lines)
    best = (0.0, -1)
    for i in range(len(lines) - window + 1):
        window_text = "".join(lines[i : i + window])
        ratio = difflib.SequenceMatcher(None, window_text, anchor).ratio()
        if ratio > best[0]:
            best = (ratio, i)
    if best[0] < _FUZZY_THRESHOLD:
        raise AnchorNotFound(f"no exact match, best fuzzy ratio {best[0]:.2f} < {_FUZZY_THRESHOLD}")
    return sum(len(line) for line in lines[: best[1]])


def _apply_one(
    patch: dict,
    repo_root: Path,
    content_cache: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Return (new_content, detail). Does not write.

    content_cache maps file rel-path → already-patched content so that
    multiple patches on the same file are chained rather than each starting
    from the on-disk original.
    """
    op = patch["operation"]
    file_rel = patch["file"]
    target = repo_root / file_rel
    if content_cache is not None and file_rel in content_cache:
        original = content_cache[file_rel]
    elif not target.exists():
        if op == "append":
            original = ""
        else:
            raise PatchError(f"file not found: {target}")
    else:
        original = target.read_text(encoding="utf-8")

    if op == "append":
        return original + patch["new_content"], "appended"

    anchor_before = patch.get("anchor_before") or ""
    if not anchor_before:
        raise PatchError("anchor_before required for non-append operations")
    start = _find_anchor(original, anchor_before)

    if op == "insert_after":
        insert_at = start + len(anchor_before)
        new = original[:insert_at] + patch["new_content"] + original[insert_at:]
        return new, f"inserted at char {insert_at}"

    # replace / delete require anchor_after
    anchor_after = patch.get("anchor_after") or ""
    if not anchor_after:
        # Lenient: replace the anchor_before block itself
        end = start + len(anchor_before)
    else:
        end = original.find(anchor_after, start + len(anchor_before))
        if end == -1:
            raise AnchorNotFound(f"anchor_after not found after anchor_before (pos {start})")
    replacement = "" if op == "delete" else patch["new_content"]
    new = original[:start] + replacement + original[end:]
    return new, f"replaced chars {start}..{end}"


def apply_patches(
    patches: list[dict],
    repo_root: Path,
    *,
    commit: bool = False,
) -> list[PatchResult]:
    """Apply each patch. Returns per-patch results. Never raises — records errors.

    Multiple patches targeting the same file are chained: each patch reads from
    the already-patched content of the previous patch on that file (content_cache),
    so the final proposed/written file contains ALL changes, not just the last one.
    """
    results: list[PatchResult] = []
    content_cache: dict[str, str] = {}
    for patch in patches:
        file_rel = patch.get("file", "<unknown>")
        try:
            new_content, detail = _apply_one(patch, repo_root, content_cache)
        except PatchError as exc:
            results.append(PatchResult(file=file_rel, status="error", detail=str(exc)))
            continue
        content_cache[file_rel] = new_content
        target = repo_root / file_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if commit:
            target.write_text(new_content, encoding="utf-8")
            results.append(PatchResult(file=file_rel, status="applied", detail=detail, output_path=target))
        else:
            proposed = target.with_suffix(target.suffix + ".proposed")
            proposed.write_text(new_content, encoding="utf-8")
            results.append(
                PatchResult(
                    file=file_rel,
                    status="applied",
                    detail=f"{detail} (dry-run → {proposed.name})",
                    output_path=proposed,
                )
            )
    return results


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--patches", type=Path, required=True, help="JSON file with `patches` array")
    p.add_argument("--commit", action="store_true", help="Write to target files (default: .proposed)")
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    data = json.loads(args.patches.read_text(encoding="utf-8"))
    patches = data.get("patches") if isinstance(data, dict) else data
    if not isinstance(patches, list):
        print("ERROR: expected {'patches': [...]}", file=sys.stderr)
        return 2

    results = apply_patches(patches, args.repo_root, commit=args.commit)
    summary = {
        "total": len(results),
        "applied": sum(1 for r in results if r.status == "applied"),
        "errors": sum(1 for r in results if r.status == "error"),
        "commit": args.commit,
        "results": [{"file": r.file, "status": r.status, "detail": r.detail} for r in results],
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for r in results:
            print(f"[{r.status}] {r.file}: {r.detail}")
        print(f"\n{summary['applied']}/{summary['total']} applied, {summary['errors']} errors")
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
