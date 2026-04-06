"""Tests for memory_consolidate.py — stale detection, duplicates, index health."""

import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import memory_consolidate
from helpers import write_memory_md as _write_memory


class TestScanMemoryFiles:
    def test_valid_entries_parsed(self, tmp_path):
        _write_memory(tmp_path / "user_role.md", "Role", "user", "User role info")
        _write_memory(tmp_path / "feedback_test.md", "Feedback", "feedback", "Some feedback")

        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert len(entries) == 2
        assert len(unparseable) == 0
        names = {e["name"] for e in entries}
        assert names == {"Role", "Feedback"}

    def test_skips_memory_md_index(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("# Index\n- item\n")
        _write_memory(tmp_path / "entry.md", "Entry", "user", "desc")

        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert len(entries) == 1

    def test_no_frontmatter_is_unparseable(self, tmp_path):
        (tmp_path / "bad.md").write_text("No frontmatter here\n")

        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert len(entries) == 0
        assert len(unparseable) == 1

    def test_bad_yaml_is_unparseable(self, tmp_path):
        (tmp_path / "bad.md").write_text("---\nkey: [unclosed\n---\n\nBody\n")

        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert len(entries) == 0
        assert len(unparseable) == 1

    def test_non_dict_frontmatter_is_unparseable(self, tmp_path):
        (tmp_path / "bad.md").write_text("---\n- list\n- item\n---\n\nBody\n")

        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert len(entries) == 0
        assert len(unparseable) == 1

    def test_missing_closing_frontmatter_is_unparseable(self, tmp_path):
        (tmp_path / "bad.md").write_text("---\nname: test\nno closing delimiter\n")

        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert len(entries) == 0
        assert len(unparseable) == 1

    def test_empty_dir(self, tmp_path):
        entries, unparseable = memory_consolidate.scan_memory_files(tmp_path)
        assert entries == []
        assert unparseable == []


class TestFindStale:
    def test_old_entries_marked_stale(self, tmp_path):
        f = _write_memory(tmp_path / "old.md", "Old", "user", "old entry")
        # Make mtime 100 days ago
        old_time = time.time() - (100 * 86400)
        import os

        os.utime(f, (old_time, old_time))

        entries, _ = memory_consolidate.scan_memory_files(tmp_path)
        stale = memory_consolidate.find_stale(entries, threshold_days=90)
        assert len(stale) == 1
        assert stale[0]["age_days"] >= 100

    def test_recent_entries_not_stale(self, tmp_path):
        _write_memory(tmp_path / "new.md", "New", "user", "recent entry")

        entries, _ = memory_consolidate.scan_memory_files(tmp_path)
        stale = memory_consolidate.find_stale(entries, threshold_days=90)
        assert len(stale) == 0


class TestFindPossibleDuplicates:
    def test_similar_same_type_flagged(self, tmp_path):
        _write_memory(tmp_path / "a.md", "A", "user", "user role and responsibilities")
        _write_memory(tmp_path / "b.md", "B", "user", "user role and responsibilities detail")

        entries, _ = memory_consolidate.scan_memory_files(tmp_path)
        duplicates = memory_consolidate.find_possible_duplicates(entries, similarity_threshold=0.4)
        assert len(duplicates) == 1
        assert duplicates[0][2] > 0.4  # Jaccard similarity

    def test_different_types_not_flagged(self, tmp_path):
        _write_memory(tmp_path / "a.md", "A", "user", "user role and responsibilities")
        _write_memory(tmp_path / "b.md", "B", "feedback", "user role and responsibilities")

        entries, _ = memory_consolidate.scan_memory_files(tmp_path)
        duplicates = memory_consolidate.find_possible_duplicates(entries, similarity_threshold=0.4)
        assert len(duplicates) == 0

    def test_dissimilar_entries_not_flagged(self, tmp_path):
        _write_memory(tmp_path / "a.md", "A", "user", "python developer experienced")
        _write_memory(tmp_path / "b.md", "B", "user", "react frontend completely different")

        entries, _ = memory_consolidate.scan_memory_files(tmp_path)
        duplicates = memory_consolidate.find_possible_duplicates(entries, similarity_threshold=0.4)
        assert len(duplicates) == 0

    def test_empty_description_skipped(self, tmp_path):
        _write_memory(tmp_path / "a.md", "A", "user", "single")
        _write_memory(tmp_path / "b.md", "B", "user", "unrelated")

        entries, _ = memory_consolidate.scan_memory_files(tmp_path)
        # Force descriptions to empty to test the guard
        for e in entries:
            e["description"] = ""
        duplicates = memory_consolidate.find_possible_duplicates(entries, similarity_threshold=0.4)
        assert len(duplicates) == 0


class TestCheckIndexHealth:
    def test_missing_index_returns_ok(self, tmp_path):
        health = memory_consolidate.check_index_health(tmp_path)
        assert health["status"] == "OK"
        assert health["lines"] == 0

    def test_small_index_ok(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("# Index\n" + "- item\n" * 10)
        health = memory_consolidate.check_index_health(tmp_path)
        assert health["status"] == "OK"

    def test_warning_threshold(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("line\n" * 185)
        health = memory_consolidate.check_index_health(tmp_path)
        assert health["status"] == "WARNING"

    def test_critical_threshold(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("line\n" * 205)
        health = memory_consolidate.check_index_health(tmp_path)
        assert health["status"] == "CRITICAL"


class TestPrintReport:
    def test_report_contains_expected_sections(self, tmp_path, capsys):
        entries = [
            {"path": tmp_path / "a.md", "name": "A", "type": "user", "description": "desc", "mtime": time.time()}
        ]
        memory_consolidate.print_report(entries, [], [], {"lines": 10, "status": "OK"}, [])
        output = capsys.readouterr().out
        assert "Memory Consolidation Report" in output
        assert "Scanned: 1 files" in output
        assert "INDEX HEALTH" in output

    def test_report_shows_stale_and_duplicates(self, tmp_path, capsys):
        stale = [{"path": tmp_path / "old.md", "name": "Old", "last_modified": "2025-01-01", "age_days": 120}]
        dups = [
            (
                {"path": tmp_path / "a.md", "name": "A", "type": "user"},
                {"path": tmp_path / "b.md", "name": "B", "type": "user"},
                0.85,
            )
        ]
        memory_consolidate.print_report([], stale, dups, {"lines": 10, "status": "OK"}, [])
        output = capsys.readouterr().out
        assert "old.md" in output
        assert "a.md" in output
        assert "ACTIONS SUGGESTED" in output


class TestApplyStaleMarkers:
    def test_inserts_marker_after_frontmatter(self, tmp_path):
        f = _write_memory(tmp_path / "stale.md", "Stale", "user", "desc", "body content")
        stale = [{"path": f}]

        applied = memory_consolidate.apply_stale_markers(stale)
        assert applied == 1

        content = f.read_text()
        assert "[STALE -" in content
        assert "review by" in content

    def test_skips_already_marked(self, tmp_path):
        f = tmp_path / "marked.md"
        f.write_text("---\nname: test\n---\n\n[STALE - review by 2025-12-31]\n\nbody\n")
        stale = [{"path": f}]

        applied = memory_consolidate.apply_stale_markers(stale)
        assert applied == 0

    def test_skips_no_frontmatter(self, tmp_path):
        f = tmp_path / "nofm.md"
        f.write_text("No frontmatter at all\n")
        stale = [{"path": f}]

        applied = memory_consolidate.apply_stale_markers(stale)
        assert applied == 0
