"""Tests for reverse_reconcile_aggregate.py — per-file collapse + HEAD state + candidate docs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _init_repo(tmp_path: Path, commits: list[tuple[str, dict[str, str]]]) -> Path:
    """Create a git repo, apply commits sequentially, push to bare `origin`.

    Each commit: (message, {path: content or None(=delete)})
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "develop", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    for msg, files in commits:
        for path, content in files.items():
            full = repo / path
            if content is None:
                full.unlink(missing_ok=True)
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
def mock_binding(monkeypatch):
    import reverse_reconcile_aggregate as mod

    def _bind(repo_path):
        monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo_path)
        monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})

    return _bind


def _sha_of(repo: Path, ref: str) -> str:
    out = subprocess.run(["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True)
    return out.stdout.strip()


def _list_shas(repo: Path, ref: str) -> list[str]:
    out = subprocess.run(["git", "log", ref, "--format=%H", "--reverse"], cwd=repo, capture_output=True, text=True)
    return [s for s in out.stdout.splitlines() if s]


@pytest.mark.slow
def test_file_touched_by_3_commits_collapses_to_1_item(tmp_path, mock_binding):
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(
        tmp_path,
        [
            ("feat: v1", {"src/router.py": "v1\n"}),
            ("feat: v2", {"src/router.py": "v1\nv2\n"}),
            ("feat: v3", {"src/router.py": "v3 FINAL\n"}),
        ],
    )
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "code": [
                    {"sha": shas[0], "message": "feat: v1", "files": ["src/router.py"]},
                    {"sha": shas[1], "message": "feat: v2", "files": ["src/router.py"]},
                    {"sha": shas[2], "message": "feat: v3", "files": ["src/router.py"]},
                ]
            },
        }
    }
    result = mod.aggregate("testplat", triage)
    assert len(result["code_items"]) == 1
    item = result["code_items"][0]
    assert item["target_file"] == "src/router.py"
    assert item["touched_by_shas"] == shas
    assert "v3 FINAL" in item["head_content_snippet"]
    assert "v1" not in item["head_content_snippet"]  # HEAD only
    assert item["head_sha"] == _sha_of(repo, "origin/develop")


@pytest.mark.slow
def test_file_added_then_deleted_goes_to_deleted_files(tmp_path, mock_binding):
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(
        tmp_path,
        [
            ("feat: add handler", {"src/old_handler.py": "x\n"}),
            ("feat: rm handler", {"src/old_handler.py": None}),
        ],
    )
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "code": [
                    {"sha": shas[0], "message": "feat: add handler", "files": ["src/old_handler.py"]},
                    {"sha": shas[1], "message": "feat: rm handler", "files": ["src/old_handler.py"]},
                ]
            },
        }
    }
    result = mod.aggregate("testplat", triage)
    assert len(result["code_items"]) == 0
    assert len(result["deleted_files"]) == 1
    assert result["deleted_files"][0]["path"] == "src/old_handler.py"
    assert set(result["deleted_files"][0]["touched_by_shas"]) == set(shas)


@pytest.mark.slow
def test_doc_self_edit_passes_through_to_auto_reconcile(tmp_path, mock_binding):
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("seed", {"README.md": "x\n"})])
    mock_binding(repo)
    triage = {
        "triage": {
            "doc_self_edits": [
                {"sha": "abc", "message": "docs", "files": ["platforms/p/engineering/x.md"]},
                {"sha": "def", "message": "docs2", "files": ["platforms/p/business/y.md"]},
            ],
            "clusters": {"code": []},
        }
    }
    result = mod.aggregate("testplat", triage)
    assert result["doc_self_edits"]["count"] == 2
    assert set(result["doc_self_edits"]["shas_to_auto_reconcile"]) == {"abc", "def"}
    assert len(result["code_items"]) == 0


@pytest.mark.slow
def test_aba_revert_sequence_still_one_item_with_all_shas(tmp_path, mock_binding):
    """A→B→A' sequence: file returns to A's state. 1 item, all 3 SHAs in touched_by_shas.

    LLM downstream sees HEAD content (=A) + history, decides whether any patch is needed.
    The aggregate doesn't try to detect reverts; it just reports HEAD.
    """
    import reverse_reconcile_aggregate as mod

    content_a = "state A\n"
    content_b = "state B\n"
    repo = _init_repo(
        tmp_path,
        [
            ("feat: A", {"src/x.py": content_a}),
            ("feat: B", {"src/x.py": content_b}),
            ("revert: back to A", {"src/x.py": content_a}),
        ],
    )
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "code": [
                    {"sha": shas[0], "message": "feat: A", "files": ["src/x.py"]},
                    {"sha": shas[1], "message": "feat: B", "files": ["src/x.py"]},
                    {"sha": shas[2], "message": "revert: back to A", "files": ["src/x.py"]},
                ]
            },
        }
    }
    result = mod.aggregate("testplat", triage)
    assert len(result["code_items"]) == 1
    item = result["code_items"][0]
    assert item["touched_by_shas"] == shas
    assert content_a.strip() in item["head_content_snippet"]
    assert content_b.strip() not in item["head_content_snippet"]


@pytest.mark.slow
def test_candidate_docs_for_models_path(tmp_path, mock_binding):
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat", {"src/models/user.py": "class User: ...\n"})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "feat", "files": ["src/models/user.py"]}]},
        }
    }
    result = mod.aggregate("prosauai", triage)
    cand = result["code_items"][0]["candidate_docs"]
    assert cand[0].endswith("domain-model.md")
    assert any("blueprint.md" in c for c in cand)


@pytest.mark.slow
def test_candidate_docs_for_api_path(tmp_path, mock_binding):
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat", {"src/api/endpoints.py": "x\n"})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "feat", "files": ["src/api/endpoints.py"]}]},
        }
    }
    result = mod.aggregate("prosauai", triage)
    cand = result["code_items"][0]["candidate_docs"]
    assert cand[0].endswith("context-map.md")


@pytest.mark.slow
def test_candidate_docs_filters_missing_files(tmp_path, mock_binding):
    """Candidate docs pointing to files that don't exist get filtered out.

    Prosauai's engineering/ has no data-model.md but has domain-model.md.
    Heuristic for migrations returns [data-model, domain-model] — we want
    the non-existent one dropped so apply_patch never fails FileNotFound.
    """
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat", {"migrations/001_init.sql": "create table\n"})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "feat", "files": ["migrations/001_init.sql"]}]},
        }
    }
    result = mod.aggregate("prosauai", triage)
    cand = result["code_items"][0]["candidate_docs"]
    # data-model.md doesn't exist in prosauai, domain-model.md does → only the second survives
    assert all("data-model.md" not in c for c in cand)
    assert any("domain-model.md" in c for c in cand)


@pytest.mark.slow
def test_candidate_docs_fallback_when_all_missing(tmp_path, mock_binding):
    """If no candidate exists on disk, fall back to blueprint.md unconditionally."""
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat", {"migrations/002.sql": "x\n"})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "feat", "files": ["migrations/002.sql"]}]},
        }
    }
    # Use a platform name that has no docs in the real filesystem
    result = mod.aggregate("nonexistent-platform-xyz", triage)
    cand = result["code_items"][0]["candidate_docs"]
    assert len(cand) == 1
    assert cand[0].endswith("blueprint.md")


@pytest.mark.slow
def test_head_snippet_truncates_large_file(tmp_path, mock_binding):
    import reverse_reconcile_aggregate as mod

    big = "\n".join(f"line {i}" for i in range(200))
    repo = _init_repo(tmp_path, [("feat: big", {"src/big.py": big})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "feat: big", "files": ["src/big.py"]}]},
        }
    }
    result = mod.aggregate("testplat", triage)
    snippet = result["code_items"][0]["head_content_snippet"]
    assert "truncated" in snippet
    assert "line 0" in snippet
    assert "line 199" in snippet


@pytest.mark.slow
def test_binding_branch_override(tmp_path, monkeypatch):
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("seed", {"src/x.py": "x\n"})])
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    # Don't configure binding; pass branch explicitly
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})
    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "seed", "files": ["src/x.py"]}]},
        }
    }
    # Explicit branch="develop" overrides binding's "main"
    result = mod.aggregate("testplat", triage, branch="develop")
    assert result["branch"] == "develop"
    assert len(result["code_items"]) == 1


@pytest.mark.slow
def test_aggregate_raises_on_reconciled_leak(tmp_path, mock_binding):
    """Invariant 6: a reconciled commit appearing in triage MUST raise AssertionError."""
    import sqlite3

    import db_core
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat: x", {"src/x.py": "x\n"})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")
    sha = shas[0]

    db_file = tmp_path / "leak.db"
    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    # Seed a reconciled commit for this platform
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at, reconciled_at) "
        "VALUES (?, 'feat: x', 'a', 'testplat', 'external-fetch', '2026-01-01T00:00:00Z', "
        "'2026-01-02T00:00:00Z')",
        (sha,),
    )
    conn.commit()
    conn.close()

    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": sha, "message": "feat: x", "files": ["src/x.py"]}]},
        }
    }
    with pytest.raises(AssertionError, match="Aggregate invariant violated"):
        mod.aggregate("testplat", triage, db_path=db_file)


@pytest.mark.slow
def test_aggregate_passes_when_no_leak(tmp_path, mock_binding):
    """Empty triage or all-unreconciled SHAs must pass the invariant."""
    import sqlite3

    import db_core
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat: x", {"src/x.py": "x\n"})])
    mock_binding(repo)
    shas = _list_shas(repo, "develop")

    db_file = tmp_path / "ok.db"
    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at) "
        "VALUES (?, 'feat: x', 'a', 'testplat', 'external-fetch', '2026-01-01T00:00:00Z')",
        (shas[0],),
    )
    conn.commit()
    conn.close()

    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {"code": [{"sha": shas[0], "message": "feat: x", "files": ["src/x.py"]}]},
        }
    }
    # Should not raise
    result = mod.aggregate("testplat", triage, db_path=db_file)
    assert len(result["code_items"]) == 1
