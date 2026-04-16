"""Tests for reverse_reconcile_apply.py — anchor matching, ops, dry-run."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text(
        "# Header\n\n## Section A\n\nContent of A.\n\n## Section B\n\nContent of B.\n\n## Section C\n\nContent of C.\n",
        encoding="utf-8",
    )
    return p


def test_find_anchor_exact(sample_file):
    from reverse_reconcile_apply import _find_anchor

    text = sample_file.read_text()
    pos = _find_anchor(text, "## Section B")
    assert text[pos : pos + len("## Section B")] == "## Section B"


def test_find_anchor_ambiguous_raises(tmp_path):
    from reverse_reconcile_apply import AmbiguousAnchor, _find_anchor

    text = "foo\nfoo\nfoo\n"
    with pytest.raises(AmbiguousAnchor):
        _find_anchor(text, "foo")


def test_find_anchor_fuzzy(sample_file):
    from reverse_reconcile_apply import _find_anchor

    text = sample_file.read_text()
    # Slight typo
    pos = _find_anchor(text, "## Sectioon B\n\nContent of B.")
    assert "Section B" in text[pos : pos + 30]


def test_find_anchor_not_found(sample_file):
    from reverse_reconcile_apply import AnchorNotFound, _find_anchor

    with pytest.raises(AnchorNotFound):
        _find_anchor(sample_file.read_text(), "completely unrelated text xyz 123")


def test_replace_between_anchors(sample_file, tmp_path):
    from reverse_reconcile_apply import apply_patches

    patch = {
        "file": "doc.md",
        "operation": "replace",
        "anchor_before": "## Section B\n\n",
        "anchor_after": "## Section C",
        "new_content": "NEW B\n\n",
    }
    results = apply_patches([patch], tmp_path, commit=True)
    assert results[0].status == "applied"
    content = sample_file.read_text()
    assert "NEW B" in content
    assert "Content of B" not in content
    assert "Content of A" in content
    assert "Content of C" in content


def test_insert_after(sample_file, tmp_path):
    from reverse_reconcile_apply import apply_patches

    patch = {
        "file": "doc.md",
        "operation": "insert_after",
        "anchor_before": "## Section A\n\nContent of A.\n",
        "new_content": "\nEXTRA LINE\n",
    }
    results = apply_patches([patch], tmp_path, commit=True)
    assert results[0].status == "applied"
    content = sample_file.read_text()
    # EXTRA appears after A, before B
    a_idx = content.find("Content of A")
    extra_idx = content.find("EXTRA LINE")
    b_idx = content.find("Section B")
    assert a_idx < extra_idx < b_idx


def test_delete(sample_file, tmp_path):
    from reverse_reconcile_apply import apply_patches

    patch = {
        "file": "doc.md",
        "operation": "delete",
        "anchor_before": "## Section B\n\nContent of B.\n\n",
        "anchor_after": "## Section C",
    }
    results = apply_patches([patch], tmp_path, commit=True)
    assert results[0].status == "applied"
    content = sample_file.read_text()
    assert "Section B" not in content


def test_append_creates_file(tmp_path):
    from reverse_reconcile_apply import apply_patches

    patch = {
        "file": "new.md",
        "operation": "append",
        "new_content": "# Brand new file\n",
    }
    results = apply_patches([patch], tmp_path, commit=True)
    assert results[0].status == "applied"
    assert (tmp_path / "new.md").read_text() == "# Brand new file\n"


def test_dry_run_does_not_modify_target(sample_file, tmp_path):
    from reverse_reconcile_apply import apply_patches

    original = sample_file.read_text()
    patch = {
        "file": "doc.md",
        "operation": "replace",
        "anchor_before": "## Section B\n\n",
        "anchor_after": "## Section C",
        "new_content": "CHANGED\n\n",
    }
    results = apply_patches([patch], tmp_path, commit=False)
    assert results[0].status == "applied"
    # Original untouched
    assert sample_file.read_text() == original
    # Proposed exists
    proposed = tmp_path / "doc.md.proposed"
    assert proposed.exists()
    assert "CHANGED" in proposed.read_text()


def test_ambiguous_anchor_reports_error(tmp_path):
    from reverse_reconcile_apply import apply_patches

    f = tmp_path / "dup.md"
    f.write_text("X\nX\nX\n")
    patch = {
        "file": "dup.md",
        "operation": "replace",
        "anchor_before": "X",
        "anchor_after": "\n",
        "new_content": "Y",
    }
    results = apply_patches([patch], tmp_path, commit=True)
    assert results[0].status == "error"
    assert "matched" in results[0].detail


def test_missing_file_reports_error(tmp_path):
    from reverse_reconcile_apply import apply_patches

    patch = {
        "file": "missing.md",
        "operation": "replace",
        "anchor_before": "x",
        "new_content": "y",
    }
    results = apply_patches([patch], tmp_path, commit=True)
    assert results[0].status == "error"
    assert "not found" in results[0].detail


def test_multiple_patches_same_file_are_chained(tmp_path):
    """Two patches on the same file must both appear in the final output.
    Previously, the second patch would read from the original on-disk file and
    overwrite the proposed file produced by the first patch, losing patch 1.
    """
    from reverse_reconcile_apply import apply_patches

    doc = tmp_path / "doc.md"
    doc.write_text(
        "# Title\n\nLine A: old-a\n\nLine B: old-b\n",
        encoding="utf-8",
    )

    patches = [
        {
            "file": "doc.md",
            "operation": "replace",
            "anchor_before": "Line A: old-a",
            "new_content": "Line A: new-a",
        },
        {
            "file": "doc.md",
            "operation": "replace",
            "anchor_before": "Line B: old-b",
            "new_content": "Line B: new-b",
        },
    ]
    results = apply_patches(patches, tmp_path, commit=True)

    assert all(r.status == "applied" for r in results)
    final = doc.read_text(encoding="utf-8")
    assert "Line A: new-a" in final, "patch 1 must survive when patch 2 runs"
    assert "Line B: new-b" in final, "patch 2 must be applied"
    assert "old-a" not in final
    assert "old-b" not in final
