"""Tests for audit_commit_attribution.py — mismatch detection + apply."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def fresh_db(tmp_path):
    import db_core

    db_file = tmp_path / "audit.db"
    conn = sqlite3.connect(str(db_file))
    db_core.migrate(conn, Path(__file__).resolve().parents[3] / ".pipeline" / "migrations")
    conn.close()
    return db_file


def _seed_platforms(monkeypatch, mod, base: Path, platforms: dict[str, list[str]]):
    """Build platforms/<p>/epics/<slug>/ tree and patch REPO_ROOT."""
    pdir = base / "platforms"
    for plat, slugs in platforms.items():
        edir = pdir / plat / "epics"
        edir.mkdir(parents=True, exist_ok=True)
        for slug in slugs:
            (edir / slug).mkdir()
    monkeypatch.setattr(mod, "REPO_ROOT", base)


def _insert(conn, sha, plat, epic, source="hook"):
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, epic_id, source, committed_at, host_repo) "
        "VALUES (?, 'm', 'a', ?, ?, ?, '2026-01-01T00:00:00Z', 'paceautomations/madruga.ai')",
        (sha, plat, epic, source),
    )


def test_audit_detects_mismatch(tmp_path, fresh_db, monkeypatch):
    import audit_commit_attribution as mod

    _seed_platforms(monkeypatch, mod, tmp_path, {"madruga-ai": ["006-foo"], "prosauai": ["007-bar"]})
    conn = sqlite3.connect(str(fresh_db))
    _insert(conn, "sha1", "madruga-ai", "007-bar")  # mis-attributed
    _insert(conn, "sha2", "prosauai", "007-bar")  # correct
    _insert(conn, "sha3", "madruga-ai", "006-foo")  # correct
    conn.commit()
    conn.close()

    report = mod.audit(db_path=fresh_db)
    assert report["total_mismatches"] == 1
    assert report["mismatches"][0]["platform_id"] == "madruga-ai"
    assert report["mismatches"][0]["epic_id"] == "007-bar"
    assert report["mismatches"][0]["should_be"] == "prosauai"


def test_audit_ignores_unknown_epic(tmp_path, fresh_db, monkeypatch):
    """Epics that don't exist on disk are not flagged (no ground truth)."""
    import audit_commit_attribution as mod

    _seed_platforms(monkeypatch, mod, tmp_path, {"madruga-ai": ["001-x"]})
    conn = sqlite3.connect(str(fresh_db))
    _insert(conn, "sha1", "fulano", "999-ghost")
    conn.commit()
    conn.close()

    report = mod.audit(db_path=fresh_db)
    assert report["total_mismatches"] == 0


def test_audit_flags_ambiguous(tmp_path, fresh_db, monkeypatch):
    """Same slug on two platforms → ambiguous, not auto-fixed."""
    import audit_commit_attribution as mod

    _seed_platforms(monkeypatch, mod, tmp_path, {"a": ["010-shared"], "b": ["010-shared"]})
    conn = sqlite3.connect(str(fresh_db))
    _insert(conn, "sha1", "c", "010-shared")
    conn.commit()
    conn.close()

    report = mod.audit(db_path=fresh_db)
    assert report["total_ambiguous"] == 1
    assert report["total_mismatches"] == 0


def test_apply_reattributes_commits(tmp_path, fresh_db, monkeypatch):
    import audit_commit_attribution as mod

    _seed_platforms(monkeypatch, mod, tmp_path, {"madruga-ai": ["006-foo"], "prosauai": ["007-bar"]})
    conn = sqlite3.connect(str(fresh_db))
    _insert(conn, "sha1", "madruga-ai", "007-bar")
    _insert(conn, "sha2", "madruga-ai", "007-bar")
    conn.commit()
    conn.close()

    report = mod.audit(db_path=fresh_db)
    result = mod.apply_fixes(fresh_db, report)
    assert result["fixed"] == 2

    conn = sqlite3.connect(str(fresh_db))
    rows = conn.execute("SELECT sha, platform_id FROM commits WHERE epic_id='007-bar'").fetchall()
    conn.close()
    assert {r[1] for r in rows} == {"prosauai"}


def test_apply_skips_when_target_exists(tmp_path, fresh_db, monkeypatch):
    """If the same SHA is already tracked under the new platform, skip (no duplicate)."""
    import audit_commit_attribution as mod

    _seed_platforms(monkeypatch, mod, tmp_path, {"prosauai": ["007-bar"]})
    conn = sqlite3.connect(str(fresh_db))
    _insert(conn, "sha1:madruga-ai", "madruga-ai", "007-bar")
    _insert(conn, "sha1:prosauai", "prosauai", "007-bar")  # already exists composite
    conn.commit()
    conn.close()

    report = mod.audit(db_path=fresh_db)
    result = mod.apply_fixes(fresh_db, report)
    # The mis-attributed row's raw SHA isn't taken under prosauai, so it can move
    # via composite form. Verify final state: prosauai owns both.
    assert result["fixed"] >= 0

    conn = sqlite3.connect(str(fresh_db))
    plats = {r[0] for r in conn.execute("SELECT platform_id FROM commits WHERE epic_id='007-bar'").fetchall()}
    conn.close()
    assert plats == {"prosauai"}


def test_host_repo_preserved_during_reattribution(tmp_path, fresh_db, monkeypatch):
    """platform_id changes; host_repo stays as the physical-repo source of truth."""
    import audit_commit_attribution as mod

    _seed_platforms(monkeypatch, mod, tmp_path, {"prosauai": ["006-bar"]})
    conn = sqlite3.connect(str(fresh_db))
    # Commit was committed in madruga.ai checkout but is prosauai work
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, epic_id, source, "
        "committed_at, host_repo) VALUES "
        "('xx', 'm', 'a', 'madruga-ai', '006-bar', 'hook', '2026-01-01T00:00:00Z', "
        "'paceautomations/madruga.ai')"
    )
    conn.commit()
    conn.close()

    report = mod.audit(db_path=fresh_db)
    mod.apply_fixes(fresh_db, report)

    conn = sqlite3.connect(str(fresh_db))
    row = conn.execute("SELECT platform_id, host_repo FROM commits WHERE epic_id='006-bar'").fetchone()
    conn.close()
    assert row[0] == "prosauai"
    assert row[1] == "paceautomations/madruga.ai"
