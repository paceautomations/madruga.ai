"""Tests for reverse_reconcile_classify.py — deterministic triage rules."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def fresh_db(tmp_path):
    import db_core

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    conn.close()
    return db_file


def _seed_commit(db_file: Path, sha: str, message: str, files: list[str], platform: str = "plat"):
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at, files_json) "
        "VALUES (?, ?, 'a', ?, 'external-fetch', '2026-01-01T00:00:00Z', ?)",
        (sha, message, platform, json.dumps(files)),
    )
    conn.commit()
    conn.close()


def test_classify_lockfile_only_is_noise():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "chore: update", "files": ["pnpm-lock.yaml"]})
    assert layer == "none"


def test_classify_typo_subject_is_noise():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "fix: typo in README", "files": ["README.md"]})
    assert layer == "none"


def test_classify_business_doc_only_is_self_edit():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "update vision", "files": ["platforms/prosauai/business/vision.md"]})
    assert layer == "doc-self-edit"


def test_classify_engineering_doc_only_is_self_edit():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "arch change", "files": ["platforms/prosauai/engineering/blueprint.md"]})
    assert layer == "doc-self-edit"


def test_classify_decisions_doc_only_is_self_edit():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "new ADR", "files": ["platforms/prosauai/decisions/ADR-020-x.md"]})
    assert layer == "doc-self-edit"


def test_classify_code_change():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "feat: add router", "files": ["src/router.py", "tests/test_router.py"]})
    assert layer == "code"


def test_classify_multi_layer_doc_only_is_self_edit():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit(
        {
            "message": "refactor docs",
            "files": [
                "platforms/prosauai/business/vision.md",
                "platforms/prosauai/engineering/blueprint.md",
            ],
        }
    )
    assert layer == "doc-self-edit"


def test_classify_mixed_doc_and_code_is_code():
    """Commits mixing doc edits + code changes → code wins (code is the drift signal)."""
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit(
        {
            "message": "feat: add endpoint + docs",
            "files": ["platforms/prosauai/engineering/blueprint.md", "src/api.py"],
        }
    )
    assert layer == "code"


def test_classify_empty_files_is_noise():
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit({"message": "merge", "files": []})
    assert layer == "none"


def test_triage_groups_correctly(fresh_db):
    from reverse_reconcile_classify import triage

    _seed_commit(fresh_db, "a1", "feat: code", ["src/x.py"])
    _seed_commit(fresh_db, "a2", "update vision", ["platforms/plat/business/vision.md"])
    _seed_commit(fresh_db, "a3", "chore: typo", ["README.md"])
    _seed_commit(fresh_db, "a4", "engineering update", ["platforms/plat/engineering/blueprint.md"])

    result = triage("plat", db_path=fresh_db)
    assert result["total"] == 4
    assert len(result["triage"]["clusters"]["code"]) == 1
    assert len(result["triage"]["doc_self_edits"]) == 2  # a2 and a4
    assert len(result["triage"]["none"]) == 1
    # No longer routed to business/engineering clusters
    assert len(result["triage"]["clusters"]["business"]) == 0
    assert len(result["triage"]["clusters"]["engineering"]) == 0


def test_triage_doc_self_edits_preserves_files(fresh_db):
    from reverse_reconcile_classify import triage

    _seed_commit(fresh_db, "a1", "docs", ["platforms/plat/engineering/blueprint.md"])
    result = triage("plat", db_path=fresh_db)
    entries = result["triage"]["doc_self_edits"]
    assert len(entries) == 1
    assert entries[0]["sha"] == "a1"
    assert "platforms/plat/engineering/blueprint.md" in entries[0]["files"]


def test_triage_ignores_reconciled(fresh_db):
    from reverse_reconcile_classify import triage

    _seed_commit(fresh_db, "a1", "feat", ["src/x.py"])
    conn = sqlite3.connect(str(fresh_db))
    conn.execute("UPDATE commits SET reconciled_at='2026-01-01T00:00:00Z' WHERE sha='a1'")
    conn.commit()
    conn.close()
    result = triage("plat", db_path=fresh_db)
    assert result["total"] == 0
