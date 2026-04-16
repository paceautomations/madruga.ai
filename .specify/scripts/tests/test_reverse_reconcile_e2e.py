"""End-to-end: fake remote repo → ingest → triage → aggregate → auto-mark → apply → mark.

Covers V2: branch scoping + chronological collapse + doc-self-edit auto-reconcile.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _init_repo(tmp_path: Path, branch: str, commits: list[tuple[str, dict]]) -> Path:
    """Initialize a repo on `branch` with sequential commits, push to bare origin.

    Each entry in commits: (msg, {path: content or None=delete}).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", branch, "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    for msg, files in commits:
        for path, content in files.items():
            full = repo / path
            if content is None:
                if full.exists():
                    full.unlink()
            else:
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg, "--allow-empty"], cwd=repo, check=True)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    return repo


@pytest.fixture
def fresh_db(tmp_path):
    import db_core

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    conn.close()
    return db_file


def _bind(monkeypatch, repo: Path, branch: str) -> None:
    import reverse_reconcile_aggregate as agg_mod
    import reverse_reconcile_ingest as ingest_mod

    for mod in (ingest_mod, agg_mod):
        monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p, _r=repo: _r)
        monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p, _b=branch: {"base_branch": _b})


def test_full_pipeline_with_aggregate(tmp_path, fresh_db, monkeypatch):
    """Baseline pipeline with mix of noise / doc-self-edit / code commits."""
    import reverse_reconcile_apply as apply_mod
    import reverse_reconcile_aggregate as agg_mod
    import reverse_reconcile_classify as classify_mod
    import reverse_reconcile_ingest as ingest_mod
    import reverse_reconcile_mark as mark_mod

    repo = _init_repo(
        tmp_path,
        "develop",
        [
            # 1) noise: typo
            ("fix: typo", {"README.md": "v1\n"}),
            # 2) noise: lockfile
            ("chore: deps", {"pnpm-lock.yaml": "lock\n"}),
            # 3) code change
            ("feat: add router", {"src/router.py": "def route(): pass\n"}),
            # 4) doc-self-edit (should NOT feed LLM)
            (
                "docs: containers",
                {"platforms/testplat/engineering/containers.md": "# Containers\n\n## API\n"},
            ),
        ],
    )
    _bind(monkeypatch, repo, "develop")

    # Seed candidate docs in the real REPO_ROOT so _candidate_docs (which now
    # filters by Path.exists) does not fall back to blueprint.md.
    real_engineering = agg_mod.REPO_ROOT / "platforms" / "testplat" / "engineering"
    real_engineering.mkdir(parents=True, exist_ok=True)
    (real_engineering / "context-map.md").write_text("# context map\n")
    (real_engineering / "containers.md").write_text("# containers\n")

    try:
        # Ingest
        result = ingest_mod.ingest("testplat", db_path=fresh_db)
        assert result["inserted"] == 4
        assert result["branch"] == "develop"

        # Classify
        triage = classify_mod.triage("testplat", db_path=fresh_db)
        noise_shas = [n["sha"] for n in triage["triage"]["none"]]
        doc_shas = [e["sha"] for e in triage["triage"]["doc_self_edits"]]
        assert len(noise_shas) == 2
        assert len(doc_shas) == 1
        assert len(triage["triage"]["clusters"]["code"]) == 1

        # Aggregate
        work = agg_mod.aggregate("testplat", triage, db_path=fresh_db)
        assert work["doc_self_edits"]["count"] == 1
        assert len(work["code_items"]) == 1
        assert work["code_items"][0]["target_file"] == "src/router.py"
        # src/router.py → routers rule → context-map.md first
        assert work["code_items"][0]["candidate_docs"][0].endswith("context-map.md")

        # Auto-mark: noise + doc-self-edits
        n1 = mark_mod.mark_shas("testplat", noise_shas, db_path=fresh_db)
        n2 = mark_mod.mark_shas("testplat", work["doc_self_edits"]["shas_to_auto_reconcile"], db_path=fresh_db)
        assert n1 + n2 == 3

        # Apply a fake LLM patch for the code_item
        docdir = tmp_path / "wd" / "platforms" / "testplat" / "engineering"
        docdir.mkdir(parents=True)
        (docdir / "context-map.md").write_text("# Context Map\n\n## Routing\n\nOld.\n", encoding="utf-8")
        patches = [
            {
                "file": "platforms/testplat/engineering/context-map.md",
                "operation": "replace",
                "anchor_before": "## Routing\n\n",
                "anchor_after": "",
                "new_content": "## Routing\n\nNew router added (commit sha_ref).\n",
                "reason": "router code added at HEAD",
                "sha_refs": work["code_items"][0]["touched_by_shas"],
                "layer": "engineering",
            }
        ]
        apply_mod.apply_patches(patches, tmp_path / "wd", commit=True)
        assert "New router added" in (docdir / "context-map.md").read_text()

        # Mark applied
        mark_mod.mark_shas("testplat", patches[0]["sha_refs"], db_path=fresh_db)
        assert mark_mod.count_unreconciled("testplat", db_path=fresh_db) == 0
    finally:
        import shutil

        shutil.rmtree(agg_mod.REPO_ROOT / "platforms" / "testplat", ignore_errors=True)


def test_chronological_collapse(tmp_path, fresh_db, monkeypatch):
    """The chronological guarantee: A→B→C→D→E on same file collapses to 1 work item, HEAD-only.

    Scenario: commits all on develop, same file `src/service.py`:
        A: add section X
        B: add section Y (now X+Y)
        C: modify section X (modified X + Y)
        D: delete section X (only Y)
        E: add section Z (Y+Z)

    Aggregate must:
      - emit ONE code_item for src/service.py
      - touched_by_shas has all 5 SHAs
      - head_content_snippet reflects HEAD (Y + Z, NOT X)
    """
    import reverse_reconcile_aggregate as agg_mod
    import reverse_reconcile_classify as classify_mod
    import reverse_reconcile_ingest as ingest_mod

    repo = _init_repo(
        tmp_path,
        "develop",
        [
            ("A: add section X", {"src/service.py": "# X\nsection X original\n"}),
            ("B: add section Y", {"src/service.py": "# X\nsection X original\n# Y\nsection Y content\n"}),
            ("C: modify section X", {"src/service.py": "# X\nsection X MODIFIED\n# Y\nsection Y content\n"}),
            ("D: delete section X", {"src/service.py": "# Y\nsection Y content\n"}),
            ("E: add section Z", {"src/service.py": "# Y\nsection Y content\n# Z\nsection Z content\n"}),
        ],
    )
    _bind(monkeypatch, repo, "develop")

    ingest_mod.ingest("testplat", db_path=fresh_db)
    triage = classify_mod.triage("testplat", db_path=fresh_db)
    assert len(triage["triage"]["clusters"]["code"]) == 5  # 5 commits into code cluster

    work = agg_mod.aggregate("testplat", triage)
    assert len(work["code_items"]) == 1
    item = work["code_items"][0]
    assert item["target_file"] == "src/service.py"
    assert len(item["touched_by_shas"]) == 5

    snippet = item["head_content_snippet"]
    # HEAD state: Y + Z present
    assert "section Y content" in snippet
    assert "section Z content" in snippet
    # Intermediate states absent
    assert "section X original" not in snippet
    assert "section X MODIFIED" not in snippet


def test_chronological_delete_goes_to_deleted_files(tmp_path, fresh_db, monkeypatch):
    """File that existed in earlier commits but not at HEAD → deleted_files."""
    import reverse_reconcile_aggregate as agg_mod
    import reverse_reconcile_classify as classify_mod
    import reverse_reconcile_ingest as ingest_mod

    repo = _init_repo(
        tmp_path,
        "develop",
        [
            ("A: add", {"src/tmp.py": "x\n"}),
            ("B: modify", {"src/tmp.py": "y\n"}),
            ("C: delete", {"src/tmp.py": None}),
        ],
    )
    _bind(monkeypatch, repo, "develop")

    ingest_mod.ingest("testplat", db_path=fresh_db)
    triage = classify_mod.triage("testplat", db_path=fresh_db)
    work = agg_mod.aggregate("testplat", triage)

    assert len(work["code_items"]) == 0
    assert len(work["deleted_files"]) == 1
    assert work["deleted_files"][0]["path"] == "src/tmp.py"
    assert len(work["deleted_files"][0]["touched_by_shas"]) == 3
