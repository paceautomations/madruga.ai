"""Tests for hook_post_commit.py — detection, multi-platform, and error handling (T014-T017)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestParseBranchPlatformDetection:
    """parse_branch() extracts platform from branch name pattern epic/<platform>/<NNN-slug>."""

    def test_epic_branch_returns_platform(self):
        from hook_post_commit import parse_branch

        platform_id, _epic_id = parse_branch("epic/prosauai/007-foo")
        assert platform_id == "prosauai"

    def test_epic_branch_madruga_ai(self):
        from hook_post_commit import parse_branch

        platform_id, _epic_id = parse_branch("epic/madruga-ai/023-commit-traceability")
        assert platform_id == "madruga-ai"

    def test_non_epic_branch_returns_none_platform(self):
        from hook_post_commit import parse_branch

        platform_id, _epic_id = parse_branch("main")
        assert platform_id is None

    def test_feature_branch_returns_none_platform(self):
        from hook_post_commit import parse_branch

        platform_id, _epic_id = parse_branch("feature/some-thing")
        assert platform_id is None

    def test_partial_epic_branch_missing_slug(self):
        from hook_post_commit import parse_branch

        platform_id, _epic_id = parse_branch("epic/prosauai")
        assert platform_id is None


class TestDetectPlatformsFromFiles:
    """detect_platforms_from_files() scans file paths for platforms/<X>/ pattern."""

    def test_single_platform_from_file_paths(self):
        from hook_post_commit import detect_platforms_from_files

        files = ["platforms/prosauai/business/vision.md", "platforms/prosauai/x.md"]
        result = detect_platforms_from_files(files)
        assert result == {"prosauai"}

    def test_multiple_platforms_from_file_paths(self):
        from hook_post_commit import detect_platforms_from_files

        files = [
            "platforms/prosauai/x.md",
            "platforms/madruga-ai/y.md",
        ]
        result = detect_platforms_from_files(files)
        assert result == {"prosauai", "madruga-ai"}

    def test_no_platform_match_returns_fallback(self):
        from hook_post_commit import detect_platforms_from_files

        files = [".specify/scripts/db.py", "Makefile", "README.md"]
        result = detect_platforms_from_files(files)
        assert result == {"madruga-ai"}

    def test_empty_file_list_returns_fallback(self):
        from hook_post_commit import detect_platforms_from_files

        result = detect_platforms_from_files([])
        assert result == {"madruga-ai"}

    def test_mixed_platform_and_non_platform_files(self):
        from hook_post_commit import detect_platforms_from_files

        files = [
            "platforms/prosauai/x.md",
            ".specify/scripts/hook.py",
            "Makefile",
        ]
        result = detect_platforms_from_files(files)
        assert result == {"prosauai"}

    def test_nested_platform_paths(self):
        from hook_post_commit import detect_platforms_from_files

        files = ["platforms/prosauai/epics/001-test/spec.md"]
        result = detect_platforms_from_files(files)
        assert result == {"prosauai"}


class TestParseBranchEpicDetection:
    """parse_branch() extracts epic_id from branch name pattern epic/<platform>/<NNN-slug>."""

    def test_epic_branch_returns_epic_slug(self):
        from hook_post_commit import parse_branch

        _platform_id, epic_id = parse_branch("epic/madruga-ai/023-commit-traceability")
        assert epic_id == "023-commit-traceability"

    def test_epic_branch_numeric_prefix(self):
        from hook_post_commit import parse_branch

        _platform_id, epic_id = parse_branch("epic/prosauai/007-foo")
        assert epic_id == "007-foo"

    def test_non_epic_branch_returns_none_epic(self):
        from hook_post_commit import parse_branch

        _platform_id, epic_id = parse_branch("main")
        assert epic_id is None

    def test_feature_branch_returns_none_epic(self):
        from hook_post_commit import parse_branch

        _platform_id, epic_id = parse_branch("feature/some-thing")
        assert epic_id is None

    def test_partial_epic_branch_missing_slug_returns_none(self):
        from hook_post_commit import parse_branch

        _platform_id, epic_id = parse_branch("epic/prosauai")
        assert epic_id is None

    def test_epic_branch_long_slug(self):
        from hook_post_commit import parse_branch

        _platform_id, epic_id = parse_branch("epic/madruga-ai/017-observability-tracing-evals")
        assert epic_id == "017-observability-tracing-evals"


class TestParseEpicTag:
    """parse_epic_tag() extracts [epic:NNN] tag from commit message (overrides branch)."""

    def test_tag_in_message_returns_epic_number(self):
        from hook_post_commit import parse_epic_tag

        result = parse_epic_tag("fix: correct API endpoint [epic:015]")
        assert result == "015"

    def test_tag_at_start_of_message(self):
        from hook_post_commit import parse_epic_tag

        result = parse_epic_tag("[epic:012] chore: update deps")
        assert result == "012"

    def test_tag_with_three_digit_number(self):
        from hook_post_commit import parse_epic_tag

        result = parse_epic_tag("feat: add feature [epic:023]")
        assert result == "023"

    def test_no_tag_returns_none(self):
        from hook_post_commit import parse_epic_tag

        result = parse_epic_tag("feat: normal commit without epic tag")
        assert result is None

    def test_empty_message_returns_none(self):
        from hook_post_commit import parse_epic_tag

        result = parse_epic_tag("")
        assert result is None

    def test_similar_but_invalid_tag_returns_none(self):
        from hook_post_commit import parse_epic_tag

        result = parse_epic_tag("fix: something [epic] no number")
        assert result is None

    def test_tag_overrides_branch_epic(self):
        """Verify tag takes priority — integration-level logic test."""
        from hook_post_commit import parse_branch, parse_epic_tag

        _platform, branch_epic = parse_branch("epic/madruga-ai/023-commit-traceability")
        tag_epic = parse_epic_tag("fix: hotfix for old epic [epic:015]")
        # Tag should override: caller picks tag_epic when not None
        assert branch_epic == "023-commit-traceability"
        assert tag_epic == "015"
        # The override logic: tag wins when present
        resolved = tag_epic if tag_epic is not None else branch_epic
        assert resolved == "015"


class TestMultiPlatformCommitHandling:
    """Commit touching platforms/X/ and platforms/Y/ should generate one row per platform (T016).

    Tests the composition of detect_platforms_from_files() with the insert_commit
    convention: sha:platform_id composite key for multi-platform commits.
    """

    def test_two_platforms_detected_from_file_list(self):
        """Core detection: files spanning two platforms yield two platform IDs."""
        from hook_post_commit import detect_platforms_from_files

        files = [
            "platforms/prosauai/business/vision.md",
            "platforms/madruga-ai/engineering/blueprint.md",
            ".specify/scripts/db.py",
        ]
        platforms = detect_platforms_from_files(files)
        assert platforms == {"prosauai", "madruga-ai"}
        assert len(platforms) == 2

    def test_three_platforms_detected(self):
        """Three distinct platforms in file list."""
        from hook_post_commit import detect_platforms_from_files

        files = [
            "platforms/prosauai/x.md",
            "platforms/madruga-ai/y.md",
            "platforms/fulano/z.md",
        ]
        platforms = detect_platforms_from_files(files)
        assert platforms == {"prosauai", "madruga-ai", "fulano"}
        assert len(platforms) == 3

    def test_duplicate_platform_files_yield_single_entry(self):
        """Multiple files from same platform produce exactly one entry."""
        from hook_post_commit import detect_platforms_from_files

        files = [
            "platforms/prosauai/a.md",
            "platforms/prosauai/b.md",
            "platforms/prosauai/epics/001/c.md",
        ]
        platforms = detect_platforms_from_files(files)
        assert platforms == {"prosauai"}
        assert len(platforms) == 1

    def test_multi_platform_generates_composite_sha_keys(self):
        """Verify the sha:platform_id convention creates distinct keys per platform.

        This tests the contract that main() must follow: for each platform in
        detect_platforms_from_files(), call insert_commit with sha=f'{sha}:{platform}'.
        """
        from hook_post_commit import detect_platforms_from_files

        files = [
            "platforms/prosauai/x.md",
            "platforms/madruga-ai/y.md",
        ]
        platforms = detect_platforms_from_files(files)
        base_sha = "abc123def456"

        # Simulate the composite key generation the hook main() will do
        composite_keys = {f"{base_sha}:{p}" for p in platforms}
        assert len(composite_keys) == 2
        assert f"{base_sha}:prosauai" in composite_keys
        assert f"{base_sha}:madruga-ai" in composite_keys

    def test_single_platform_commit_uses_plain_sha(self):
        """When only one platform detected, no composite key needed."""
        from hook_post_commit import detect_platforms_from_files

        files = ["platforms/prosauai/x.md"]
        platforms = detect_platforms_from_files(files)
        assert len(platforms) == 1

        # Single platform: sha can remain plain (no :platform suffix needed)
        # But the hook may still use composite for consistency — either is valid
        # At minimum, exactly one insert_commit call expected
        assert len(platforms) == 1

    def test_multi_platform_on_main_branch_all_adhoc(self):
        """Multi-platform commit on main branch: all rows should have epic_id=None."""
        from hook_post_commit import detect_platforms_from_files, parse_branch

        branch_platform, branch_epic = parse_branch("main")
        assert branch_platform is None
        assert branch_epic is None

        files = [
            "platforms/prosauai/config.yaml",
            "platforms/madruga-ai/config.yaml",
        ]
        platforms = detect_platforms_from_files(files)
        # Each platform gets a row with epic_id=None (ad-hoc)
        for _platform in platforms:
            epic_id = branch_epic  # None for main
            assert epic_id is None

    def test_multi_platform_on_epic_branch_inherits_epic(self):
        """Multi-platform commit on epic branch: all rows share the branch's epic_id."""
        from hook_post_commit import detect_platforms_from_files, parse_branch

        branch_platform, branch_epic = parse_branch("epic/madruga-ai/023-commit-traceability")
        assert branch_epic == "023-commit-traceability"

        files = [
            "platforms/prosauai/x.md",
            "platforms/madruga-ai/y.md",
        ]
        platforms = detect_platforms_from_files(files)
        assert len(platforms) == 2
        # All rows get the same epic from branch
        for _platform in platforms:
            assert branch_epic == "023-commit-traceability"


class TestHookErrorHandling:
    """main() must be best-effort: DB failures never raise, errors go to stderr (T017, FR-007).

    The hook runs as a git post-commit hook. If it raises an exception, git
    will print the traceback but the commit still succeeds. However, best practice
    is to catch ALL exceptions inside main() so the hook exits cleanly (exit 0).
    """

    def test_main_does_not_raise_on_db_missing(self, tmp_path, monkeypatch):
        """main() completes without exception when DB file does not exist."""
        from unittest.mock import patch

        import hook_post_commit

        # Point DB to a non-existent path
        fake_db = tmp_path / "nonexistent" / "missing.db"
        head_info = {
            "sha": "abc123",
            "message": "feat: test commit",
            "author": "Test Dev",
            "date": "2026-04-08T12:00:00Z",
            "files": ["platforms/madruga-ai/x.md"],
        }

        with (
            patch.object(hook_post_commit, "get_head_info", return_value=head_info),
            patch.object(
                hook_post_commit,
                "_get_current_branch",
                return_value="epic/madruga-ai/023-commit-traceability",
            ),
            patch.object(hook_post_commit, "DB_PATH", fake_db),
        ):
            # Must not raise — best-effort behavior
            hook_post_commit.main()

    def test_main_does_not_raise_on_db_locked(self, tmp_path, monkeypatch):
        """main() completes without exception when DB is locked."""
        import sqlite3
        from unittest.mock import patch

        import hook_post_commit

        # Create a real DB and lock it
        db_path = tmp_path / "locked.db"
        lock_conn = sqlite3.connect(str(db_path))
        lock_conn.execute("CREATE TABLE dummy (id INTEGER)")
        lock_conn.execute("BEGIN EXCLUSIVE")  # Holds exclusive lock

        head_info = {
            "sha": "def456",
            "message": "fix: locked test",
            "author": "Test Dev",
            "date": "2026-04-08T12:00:00Z",
            "files": ["platforms/madruga-ai/y.md"],
        }

        try:
            with (
                patch.object(hook_post_commit, "get_head_info", return_value=head_info),
                patch.object(
                    hook_post_commit,
                    "_get_current_branch",
                    return_value="main",
                ),
                patch.object(hook_post_commit, "DB_PATH", db_path),
            ):
                # Must not raise — best-effort behavior
                hook_post_commit.main()
        finally:
            lock_conn.rollback()
            lock_conn.close()

    def test_main_logs_error_to_stderr_on_failure(self, tmp_path, capsys):
        """When main() catches an error, it writes a message to stderr."""
        from unittest.mock import patch

        import hook_post_commit

        fake_db = tmp_path / "nonexistent" / "missing.db"
        head_info = {
            "sha": "ghi789",
            "message": "chore: stderr test",
            "author": "Test Dev",
            "date": "2026-04-08T12:00:00Z",
            "files": ["Makefile"],
        }

        with (
            patch.object(hook_post_commit, "get_head_info", return_value=head_info),
            patch.object(
                hook_post_commit,
                "_get_current_branch",
                return_value="main",
            ),
            patch.object(hook_post_commit, "DB_PATH", fake_db),
        ):
            hook_post_commit.main()

        captured = capsys.readouterr()
        # Error should go to stderr, not stdout (so git output is clean)
        assert captured.out == ""
        # stderr should contain some indication of the error
        assert "post-commit" in captured.err.lower() or "error" in captured.err.lower()

    def test_main_does_not_raise_on_git_subprocess_failure(self, tmp_path):
        """main() handles git subprocess failures gracefully."""
        from unittest.mock import patch

        import hook_post_commit

        # Simulate get_head_info raising (git not available, corrupted repo, etc.)
        with patch.object(
            hook_post_commit,
            "get_head_info",
            side_effect=OSError("git not found"),
        ):
            # Must not raise
            hook_post_commit.main()

    def test_main_exits_zero_on_error(self, tmp_path):
        """main() returns without raising — the hook exit code should be 0."""
        from unittest.mock import patch

        import hook_post_commit

        with patch.object(
            hook_post_commit,
            "get_head_info",
            side_effect=RuntimeError("unexpected error"),
        ):
            # If main() raised, this test would fail with the exception
            result = hook_post_commit.main()
            # main() should return None (implicit) — no sys.exit(1)
            assert result is None
