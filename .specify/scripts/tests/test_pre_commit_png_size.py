"""Tests for pre_commit_png_size.py — pre-commit hook rejecting PNGs >500KB.

Source task: T060 (epic 027-screen-flow-canvas Phase 6 / US4).

Note on path: project convention puts pytest tests under .specify/scripts/tests/
(see pyproject.toml + Makefile `make test`). The plan/tasks reference
"tests/unit/" but the canonical pytest tree wins so `make test` picks them up.

Implements RED phase for FR-034. Implementation in T067.
"""

from __future__ import annotations

import struct
import subprocess
import sys
import zlib
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "capture"))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOK = REPO_ROOT / ".specify" / "scripts" / "capture" / "pre_commit_png_size.py"

MAX_PNG_BYTES = 500_000


# ───────────────────────────────────────────────────────────────────────────────
# Tiny valid PNG generator (1×1 pixel, padded to a target size)
# ───────────────────────────────────────────────────────────────────────────────


def _png_signature() -> bytes:
    return b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _make_png(target_size: int) -> bytes:
    """Build a syntactically valid PNG of approximately target_size bytes.

    A 1×1 PNG is ~67 bytes; we pad with a tEXt chunk so size hits the target.
    """
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    raw = b"\x00\x00"  # filter byte + 1 grayscale pixel (black)
    idat = zlib.compress(raw)
    base = (
        _png_signature()
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )
    if len(base) >= target_size:
        return base
    # Insert a tEXt chunk before IEND to pad up to target_size.
    iend = _chunk(b"IEND", b"")
    head = base[: -len(iend)]
    pad_needed = target_size - len(base) - 12  # 12 = chunk overhead
    if pad_needed <= 0:
        return base
    text = b"Comment\x00" + (b"x" * (pad_needed - len("Comment\x00")))
    return head + _chunk(b"tEXt", text) + iend


def _run_hook(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


# ───────────────────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────────────────


def test_hook_script_exists():
    """Sanity: the hook lives where pre-commit-config and tasks expect it."""
    assert HOOK.exists(), f"hook missing at {HOOK} — implement in T067"


def test_png_under_limit_is_accepted(tmp_path: Path):
    png = tmp_path / "small.png"
    png.write_bytes(_make_png(10_000))
    assert png.stat().st_size < MAX_PNG_BYTES
    proc = _run_hook(str(png))
    assert proc.returncode == 0, proc.stderr


def test_png_at_limit_boundary_is_accepted(tmp_path: Path):
    """Exactly 500_000 bytes is the limit — the hook treats it as valid."""
    png = tmp_path / "boundary.png"
    png.write_bytes(_make_png(MAX_PNG_BYTES))
    # Tolerate small generator drift; assert <= limit
    if png.stat().st_size > MAX_PNG_BYTES:
        # padding overshot — re-generate slightly smaller
        png.write_bytes(_make_png(MAX_PNG_BYTES - 12))
    assert png.stat().st_size <= MAX_PNG_BYTES
    proc = _run_hook(str(png))
    assert proc.returncode == 0, proc.stderr


def test_png_over_limit_is_rejected(tmp_path: Path):
    png = tmp_path / "huge.png"
    png.write_bytes(_make_png(550_000))
    assert png.stat().st_size > MAX_PNG_BYTES
    proc = _run_hook(str(png))
    assert proc.returncode != 0
    assert "huge.png" in (proc.stdout + proc.stderr)
    # Mensagem operacional: tamanho real + limite
    combined = proc.stdout + proc.stderr
    assert "500" in combined  # cita o limite (500KB / 500_000)


def test_non_png_file_is_ignored(tmp_path: Path):
    """Non-PNG files should pass through (hook scope is *.png only)."""
    other = tmp_path / "data.txt"
    other.write_bytes(b"x" * 1_000_000)
    proc = _run_hook(str(other))
    assert proc.returncode == 0, proc.stderr


def test_multiple_files_mixed_status_rejects_when_any_violates(tmp_path: Path):
    ok = tmp_path / "ok.png"
    bad = tmp_path / "bad.png"
    ok.write_bytes(_make_png(50_000))
    bad.write_bytes(_make_png(550_000))
    proc = _run_hook(str(ok), str(bad))
    assert proc.returncode != 0
    assert "bad.png" in (proc.stdout + proc.stderr)


def test_no_arguments_is_noop():
    """pre-commit may invoke without files; hook must succeed gracefully."""
    proc = _run_hook()
    assert proc.returncode == 0, proc.stderr


def test_missing_file_is_ignored(tmp_path: Path):
    """A non-existing path (e.g. deleted file passed by pre-commit) must not crash."""
    ghost = tmp_path / "deleted.png"
    proc = _run_hook(str(ghost))
    assert proc.returncode == 0, proc.stderr
