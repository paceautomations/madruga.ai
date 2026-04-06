"""Tests for sync_memory.py — the sync() function and find_memory_dirs()."""

import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import sync_memory
from helpers import init_mem_db as _init_db, write_memory_md as _write_memory_md


class TestFindMemoryDirs:
    def test_finds_home_claude_memory_dir(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        slug = str(repo_root).replace("/", "-").replace(".", "-")
        memory_dir = tmp_path / "home" / ".claude" / "projects" / slug / "memory"
        memory_dir.mkdir(parents=True)

        with (
            patch.object(sync_memory, "REPO_ROOT", repo_root),
            patch("pathlib.Path.home", return_value=tmp_path / "home"),
        ):
            dirs = sync_memory.find_memory_dirs()

        assert len(dirs) >= 1
        assert memory_dir in dirs

    def test_finds_repo_claude_memory_dir(self, tmp_path):
        repo_root = tmp_path / "repo"
        memory_dir = repo_root / ".claude" / "projects" / "some-slug" / "memory"
        memory_dir.mkdir(parents=True)

        with (
            patch.object(sync_memory, "REPO_ROOT", repo_root),
            patch("pathlib.Path.home", return_value=tmp_path / "nonexistent"),
        ):
            dirs = sync_memory.find_memory_dirs()

        assert len(dirs) >= 1
        assert memory_dir in dirs

    def test_no_dirs_found(self, tmp_path):
        with (
            patch.object(sync_memory, "REPO_ROOT", tmp_path / "nonexistent"),
            patch("pathlib.Path.home", return_value=tmp_path / "also-nonexistent"),
        ):
            dirs = sync_memory.find_memory_dirs()

        assert dirs == []


class TestSync:
    def test_no_memory_dirs_returns_zeros(self):
        with patch.object(sync_memory, "find_memory_dirs", return_value=[]):
            stats = sync_memory.sync()

        assert stats == {"imported": 0, "exported": 0, "skipped": 0}

    def test_import_new_file(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        _write_memory_md(memory_dir / "user_role.md", "Role", "user", "desc", "body")

        conn = _init_db()

        with (
            patch.object(sync_memory, "find_memory_dirs", return_value=[memory_dir]),
            patch.object(sync_memory, "get_conn", return_value=conn),
            patch.object(sync_memory, "migrate"),
        ):
            stats = sync_memory.sync()

        assert stats["imported"] == 1

    def test_skip_unchanged_file(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        _write_memory_md(memory_dir / "user_role.md", "Role", "user", "desc", "body")

        conn = _init_db()
        # First import
        with (
            patch.object(sync_memory, "find_memory_dirs", return_value=[memory_dir]),
            patch.object(sync_memory, "get_conn", return_value=conn),
            patch.object(sync_memory, "migrate"),
        ):
            sync_memory.sync()

        # Second sync — should skip
        with (
            patch.object(sync_memory, "find_memory_dirs", return_value=[memory_dir]),
            patch.object(sync_memory, "get_conn", return_value=conn),
            patch.object(sync_memory, "migrate"),
        ):
            stats = sync_memory.sync(import_only=True)

        assert stats["skipped"] == 1
        assert stats["imported"] == 0

    def test_skips_memory_md_index(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "MEMORY.md").write_text("# Index\n")

        conn = _init_db()

        with (
            patch.object(sync_memory, "find_memory_dirs", return_value=[memory_dir]),
            patch.object(sync_memory, "get_conn", return_value=conn),
            patch.object(sync_memory, "migrate"),
        ):
            stats = sync_memory.sync(import_only=True)

        assert stats["imported"] == 0
        assert stats["skipped"] == 0

    def test_dry_run_does_not_import(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        _write_memory_md(memory_dir / "entry.md", "Entry", "user", "desc", "body")

        conn = _init_db()

        with (
            patch.object(sync_memory, "find_memory_dirs", return_value=[memory_dir]),
            patch.object(sync_memory, "get_conn", return_value=conn),
            patch.object(sync_memory, "migrate"),
        ):
            stats = sync_memory.sync(dry_run=True)

        assert stats["imported"] == 1  # counted but not actually imported
        # Verify nothing in DB
        rows = conn.execute("SELECT * FROM memory_entries").fetchall()
        assert len(rows) == 0

    def test_export_only_skips_import(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        _write_memory_md(memory_dir / "entry.md", "Entry", "user", "desc", "body")

        conn = _init_db()

        with (
            patch.object(sync_memory, "find_memory_dirs", return_value=[memory_dir]),
            patch.object(sync_memory, "get_conn", return_value=conn),
            patch.object(sync_memory, "migrate"),
        ):
            stats = sync_memory.sync(export_only=True)

        assert stats["imported"] == 0
