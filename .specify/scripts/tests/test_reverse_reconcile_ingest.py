"""Tests for reverse_reconcile_ingest.py — remote walk, dedup, assume-reconciled."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _init_fake_repo(tmp_path: Path) -> Path:
    """Create a git repo with 3 commits. Returns repo path."""
    repo = tmp_path / "fake"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    for i in range(1, 4):
        (repo / f"f{i}.txt").write_text(f"content {i}")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"commit {i}"], cwd=repo, check=True)
    # Simulate a remote so `git log --all --remotes` picks commits up
    bare = tmp_path / "bare"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    return repo


@pytest.fixture
def fake_repo(tmp_path):
    return _init_fake_repo(tmp_path)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB with all migrations applied."""
    import db_core

    db_file = tmp_path / "test.db"
    import sqlite3

    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    conn.close()
    return db_file


def test_list_remote_shas_returns_three_commits(fake_repo):
    from reverse_reconcile_ingest import _list_remote_shas

    commits = _list_remote_shas(fake_repo, "main")
    assert len(commits) == 3
    assert all("sha" in c and "message" in c and "files" in c for c in commits)
    # Newest first
    assert commits[0]["message"] == "commit 3"
    assert "f3.txt" in commits[0]["files"]


def test_ingest_inserts_all_new_commits(fake_repo, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})
    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["inserted"] == 3
    assert result["already_tracked"] == 0

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    rows = conn.execute(
        "SELECT sha, source, reconciled_at FROM commits WHERE platform_id=?",
        ("testplat",),
    ).fetchall()
    assert len(rows) == 3
    assert all(r[1] == "external-fetch" for r in rows)
    assert all(r[2] is None for r in rows)
    conn.close()


def test_ingest_is_idempotent(fake_repo, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})
    mod.ingest("testplat", db_path=fresh_db)
    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["inserted"] == 0
    assert result["already_tracked"] == 3


def test_dry_run_does_not_insert(fake_repo, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})
    result = mod.ingest("testplat", dry_run=True, db_path=fresh_db)
    assert result["would_insert"] == 3
    assert result["dry_run"] is True

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    count = conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    conn.close()
    assert count == 0


def test_ingest_respects_composite_sha_dedup(fake_repo, fresh_db, monkeypatch):
    """If a commit is already in the table under composite form <sha>:<plat>, skip it."""
    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})
    commits = mod._list_remote_shas(fake_repo, "main")
    target_sha = commits[0]["sha"]

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at) "
        "VALUES (?, 'x', 'x', 'testplat', 'hook', '2026-01-01T00:00:00Z')",
        (f"{target_sha}:testplat",),
    )
    conn.commit()
    conn.close()

    result = mod.ingest("testplat", db_path=fresh_db)
    # composite already tracked → 2 new (not 3)
    assert result["inserted"] == 2


def _init_multi_branch_repo(tmp_path: Path) -> Path:
    """Repo with `main`, `develop`, and `feature/xyz` branches, each diverging."""
    repo = tmp_path / "multi"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

    def _commit(name: str, msg: str):
        (repo / name).write_text(msg)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)

    # Shared root
    _commit("root.txt", "root")
    # main-only commits
    _commit("main_a.txt", "main commit 1")
    _commit("main_b.txt", "main commit 2")
    # Branch off develop from root
    subprocess.run(["git", "checkout", "-q", "-b", "develop", "HEAD~2"], cwd=repo, check=True)
    _commit("dev_a.txt", "develop commit 1")
    _commit("dev_b.txt", "develop commit 2")
    _commit("dev_c.txt", "develop commit 3")
    # feature off develop
    subprocess.run(["git", "checkout", "-q", "-b", "feature/xyz"], cwd=repo, check=True)
    _commit("feat_a.txt", "feature commit 1")
    _commit("feat_b.txt", "feature commit 2")

    # Create bare remote + push all
    bare = tmp_path / "bare_multi.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    return repo


def test_ingest_scopes_to_base_branch_only(tmp_path, fresh_db, monkeypatch):
    """Only commits reachable from origin/<base_branch> should be ingested."""
    import reverse_reconcile_ingest as mod

    repo = _init_multi_branch_repo(tmp_path)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})

    result = mod.ingest("multi", db_path=fresh_db)
    # develop = root + 3 develop commits = 4 total
    assert result["branch"] == "develop"
    assert result["inserted"] == 4

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    msgs = {r[0] for r in conn.execute("SELECT message FROM commits").fetchall()}
    conn.close()
    # feature/xyz commits NOT included
    assert "feature commit 1" not in msgs
    assert "feature commit 2" not in msgs
    # main-only commits NOT included (base_branch was develop)
    assert "main commit 1" not in msgs
    assert "main commit 2" not in msgs


def test_ingest_main_branch_excludes_develop(tmp_path, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    repo = _init_multi_branch_repo(tmp_path)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    result = mod.ingest("multi", db_path=fresh_db)
    # main = root + 2 main commits
    assert result["branch"] == "main"
    assert result["inserted"] == 3


def test_ingest_cli_branch_override(tmp_path, fresh_db, monkeypatch):
    """--branch overrides platform.yaml base_branch."""
    import reverse_reconcile_ingest as mod

    repo = _init_multi_branch_repo(tmp_path)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    # Pass branch="develop" explicitly despite base_branch=main
    result = mod.ingest("multi", branch="develop", db_path=fresh_db)
    assert result["branch"] == "develop"
    assert result["inserted"] == 4


def test_ingest_uses_composite_sha_when_other_platform_owns_raw(fake_repo, fresh_db, monkeypatch):
    """If a SHA exists in DB under platform X, ingesting same SHA for Y uses <sha>:Y form.

    Required for the self-ref case: madruga-ai main commits may already be tracked under
    prosauai/fulano via the hook's platform detection from file paths.
    """
    import sqlite3

    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    commits = mod._list_remote_shas(fake_repo, "main")
    target_sha = commits[0]["sha"]

    conn = sqlite3.connect(str(fresh_db))
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at) "
        "VALUES (?, 'x', 'x', 'other-platform', 'hook', '2026-01-01T00:00:00Z')",
        (target_sha,),
    )
    conn.commit()
    conn.close()

    # Should NOT raise UNIQUE constraint error
    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["inserted"] == 3  # all 3 commits stored, composite where needed

    conn = sqlite3.connect(str(fresh_db))
    rows = conn.execute("SELECT sha, platform_id FROM commits WHERE sha LIKE ?", (f"{target_sha}%",)).fetchall()
    conn.close()
    shas = {r[0]: r[1] for r in rows}
    # Raw SHA still owned by other-platform; composite form owned by testplat
    assert shas[target_sha] == "other-platform"
    assert shas[f"{target_sha}:testplat"] == "testplat"


def test_ingest_reconciles_orphan_shas(fake_repo, fresh_db, monkeypatch):
    """SHAs tagged for a platform but absent from its base_branch get auto-reconciled.

    Simulates the cross-repo attribution case: hook tagged a madruga-ai commit
    to prosauai (via file path), but the sha is not in prosauai/origin/develop.
    """
    import sqlite3

    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    # Seed an orphan SHA (not in fake_repo's main) tagged for testplat
    conn = sqlite3.connect(str(fresh_db))
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at) "
        "VALUES ('deadbeefcafe', 'phantom', 'a', 'testplat', 'hook', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()

    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["orphans_reconciled"] == 1

    conn = sqlite3.connect(str(fresh_db))
    reconciled_at = conn.execute("SELECT reconciled_at FROM commits WHERE sha = 'deadbeefcafe'").fetchone()[0]
    conn.close()
    assert reconciled_at is not None


def test_ingest_orphan_reconcile_ignores_valid_shas(fake_repo, fresh_db, monkeypatch):
    """SHAs that ARE in the base branch must not be touched by orphan reconcile."""
    import sqlite3

    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)  # ingest all 3

    conn = sqlite3.connect(str(fresh_db))
    null_count = conn.execute("SELECT COUNT(*) FROM commits WHERE reconciled_at IS NULL").fetchone()[0]
    conn.close()
    # All 3 ingested commits are legitimately on main → untouched by orphan sweep
    assert null_count == 3


def test_ingest_missing_branch_raises(fake_repo, fresh_db, monkeypatch):
    import pytest as _pytest

    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "nonexistent"})
    with _pytest.raises(SystemExit, match="branch 'nonexistent' not found"):
        mod.ingest("testplat", db_path=fresh_db)


def _init_repo_with_tagged_commits(tmp_path: Path, messages: list[str]) -> Path:
    """Create a repo with one commit per message; push to origin."""
    repo = tmp_path / "tagged"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    for i, msg in enumerate(messages):
        (repo / f"f{i}.txt").write_text(str(i))
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)
    bare = tmp_path / "bare_tag.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    return repo


def _seed_platform_dir(base: Path, platform_id: str, epic_slugs: list[str], with_report: list[str]) -> Path:
    """Build a fake `platforms/<p>/epics/<slug>/` tree; mark some with report."""
    plat = base / "platforms" / platform_id / "epics"
    plat.mkdir(parents=True)
    for slug in epic_slugs:
        (plat / slug).mkdir()
    for slug in with_report:
        (plat / slug / "reconcile-report.md").write_text("# report\n")
    return base / "platforms"


def _patch_platforms_dir(monkeypatch, mod, platforms_dir: Path):
    monkeypatch.setattr(mod, "REPO_PLATFORMS_DIR", platforms_dir)


def test_ingest_tag_in_subject(tmp_path, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:042-bar]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)
    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    epic_id = conn.execute("SELECT epic_id FROM commits WHERE platform_id='testplat'").fetchone()[0]
    conn.close()
    assert epic_id == "042-bar"


def test_ingest_tag_slug_digits_only(tmp_path, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:042]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=["042-bar"])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)
    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    epic_id = conn.execute("SELECT epic_id FROM commits WHERE platform_id='testplat'").fetchone()[0]
    conn.close()
    assert epic_id == "042-bar"


def test_ingest_trailer_in_body(tmp_path, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    # Commit message with subject + trailer in body
    repo = tmp_path / "trailer"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "feat: do x", "-m", "Long body line\n\nEpic: 042-bar"],
        cwd=repo,
        check=True,
    )
    bare = tmp_path / "bare_trail.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)

    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)
    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    epic_id = conn.execute("SELECT epic_id FROM commits WHERE platform_id='testplat'").fetchone()[0]
    conn.close()
    assert epic_id == "042-bar"


def test_ingest_squash_no_tag_stays_null(tmp_path, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x (#123)"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)
    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    row = conn.execute("SELECT epic_id, reconciled_at FROM commits WHERE platform_id='testplat'").fetchone()
    conn.close()
    assert row[0] is None
    assert row[1] is None


def test_ingest_tag_mismatch_logs_warning(tmp_path, fresh_db, monkeypatch, caplog):
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:999-ghost]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    import logging as _lg

    with caplog.at_level(_lg.WARNING, logger="reverse_reconcile_ingest"):
        mod.ingest("testplat", db_path=fresh_db)
    assert any("999-ghost" in r.getMessage() for r in caplog.records)

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    epic_id = conn.execute("SELECT epic_id FROM commits WHERE platform_id='testplat'").fetchone()[0]
    conn.close()
    assert epic_id is None


def test_ingest_merge_commit_resolves_children(tmp_path, fresh_db, monkeypatch):
    """A traditional merge commit attributes its branch's children to the epic."""
    import reverse_reconcile_ingest as mod

    repo = tmp_path / "merge_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    # base
    (repo / "base.txt").write_text("base")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    # epic branch with 2 children, no tags
    subprocess.run(["git", "checkout", "-q", "-b", "epic/testplat/042-bar"], cwd=repo, check=True)
    for i in range(2):
        (repo / f"e{i}.txt").write_text(str(i))
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"feat: child {i}"], cwd=repo, check=True)
    # merge into main with --no-ff
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", "Merge branch 'epic/testplat/042-bar'", "epic/testplat/042-bar"],
        cwd=repo,
        check=True,
    )
    bare = tmp_path / "bare_merge.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)

    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    rows = conn.execute(
        "SELECT message, epic_id FROM commits WHERE platform_id='testplat' AND message LIKE 'feat: child%'"
    ).fetchall()
    conn.close()
    assert len(rows) == 2
    assert all(r[1] == "042-bar" for r in rows)


def test_ingest_tag_beats_merge_map(tmp_path, fresh_db, monkeypatch):
    """Subject tag overrides merge-commit attribution."""
    import reverse_reconcile_ingest as mod

    repo = tmp_path / "merge_tag_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "base.txt").write_text("b")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "epic/testplat/042-bar"], cwd=repo, check=True)
    (repo / "child.txt").write_text("c")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # Child commit tags a DIFFERENT epic explicitly
    subprocess.run(["git", "commit", "-q", "-m", "feat: child [epic:050-other]"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", "Merge branch 'epic/testplat/042-bar'", "epic/testplat/042-bar"],
        cwd=repo,
        check=True,
    )
    bare = tmp_path / "bare_mt.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)

    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar", "050-other"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    epic_id = conn.execute(
        "SELECT epic_id FROM commits WHERE platform_id='testplat' AND message LIKE 'feat: child%'"
    ).fetchone()[0]
    conn.close()
    assert epic_id == "050-other"


def test_ingest_merge_map_only_one_git_call_for_graph(tmp_path, fresh_db, monkeypatch):
    """_build_merge_map must use a single `git log --format=%H %P %s` subprocess."""
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: a", "feat: b"])
    platforms = _seed_platform_dir(tmp_path, "testplat", [], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    calls: list[list[str]] = []
    real_run = mod._run_git

    def spy(args, cwd):
        calls.append(list(args))
        return real_run(args, cwd)

    monkeypatch.setattr(mod, "_run_git", spy)
    mod.ingest("testplat", db_path=fresh_db)

    graph_calls = [c for c in calls if c[:2] == ["log", "origin/main"] and "--format=%H%x1f%P%x1f%s" in c]
    assert len(graph_calls) == 1


def test_ingest_auto_marks_when_report_exists(tmp_path, fresh_db, monkeypatch):
    """epic_id resolved + reconcile-report.md present → reconciled_at set on INSERT."""
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:042-bar]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=["042-bar"])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["auto_marked_on_insert"] == 1

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    reconciled_at = conn.execute("SELECT reconciled_at FROM commits WHERE platform_id='testplat'").fetchone()[0]
    conn.close()
    assert reconciled_at is not None


def test_ingest_no_report_stays_null(tmp_path, fresh_db, monkeypatch):
    """Same scenario but without the report → reconciled_at NULL."""
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:042-bar]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["auto_marked_on_insert"] == 0

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    row = conn.execute("SELECT epic_id, reconciled_at FROM commits WHERE platform_id='testplat'").fetchone()
    conn.close()
    assert row[0] == "042-bar"
    assert row[1] is None


def test_ingest_retroactive_upgrade_after_report_added(tmp_path, fresh_db, monkeypatch):
    """Commit ingested before report exists → next ingest upgrades reconciled_at."""
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:042-bar]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=[])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)
    # Now add the report and re-ingest
    (platforms / "testplat" / "epics" / "042-bar" / "reconcile-report.md").write_text("# r\n")
    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["retroactively_marked"] == 1

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    reconciled_at = conn.execute("SELECT reconciled_at FROM commits WHERE platform_id='testplat'").fetchone()[0]
    conn.close()
    assert reconciled_at is not None


def test_retroactive_skips_already_reconciled(tmp_path, fresh_db, monkeypatch):
    """Idempotency: rows already reconciled are not re-touched by retroactive UPDATE."""
    import reverse_reconcile_ingest as mod

    repo = _init_repo_with_tagged_commits(tmp_path, ["feat: x [epic:042-bar]"])
    platforms = _seed_platform_dir(tmp_path, "testplat", ["042-bar"], with_report=["042-bar"])
    _patch_platforms_dir(monkeypatch, mod, platforms)
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})

    mod.ingest("testplat", db_path=fresh_db)
    # Re-run: nothing new to insert, nothing to upgrade
    result = mod.ingest("testplat", db_path=fresh_db)
    assert result["inserted"] == 0
    assert result["retroactively_marked"] == 0


def test_load_approved_epics_scans_filesystem(tmp_path, monkeypatch):
    import reverse_reconcile_ingest as mod

    platforms = _seed_platform_dir(
        tmp_path, "testplat", ["042-bar", "043-baz", "044-qux"], with_report=["042-bar", "044-qux"]
    )
    _patch_platforms_dir(monkeypatch, mod, platforms)
    approved = mod._load_approved_epics("testplat")
    assert approved == {"042-bar", "044-qux"}


def test_assume_reconciled_before_marks_ancestors(fake_repo, fresh_db, monkeypatch):
    import reverse_reconcile_ingest as mod

    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: fake_repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "main"})
    mod.ingest("testplat", db_path=fresh_db)
    commits = mod._list_remote_shas(fake_repo, "main")
    # commit 2 is ancestors (commit 2 + commit 1) = 2 commits
    middle_sha = commits[1]["sha"]
    n = mod.assume_reconciled_before("testplat", middle_sha, db_path=fresh_db)
    assert n == 2

    import sqlite3

    conn = sqlite3.connect(str(fresh_db))
    null_count = conn.execute("SELECT COUNT(*) FROM commits WHERE reconciled_at IS NULL").fetchone()[0]
    conn.close()
    assert null_count == 1  # only the newest stays unreconciled
