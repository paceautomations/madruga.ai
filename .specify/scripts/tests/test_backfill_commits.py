"""Tests for backfill_commits.py — merge detection, pre-006 classification, idempotency (T032-T034).

T032: Mock `git log --merges` output, verify epic extraction from merge commit
      messages referencing `epic/*` branches.
T033: Verify classify_pre006() links commits in the 5f62946..d6befe0 range to
      epic `001-inicio-de-tudo` and returns None for commits after the cutoff.
T034: Run backfill twice against same DB, verify zero duplicate rows.

The backfill script does not exist yet (TDD — tests first, implementation in T035-T039).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# T032 — Merge-based epic detection
# ---------------------------------------------------------------------------


class TestGetMergeCommits:
    """get_merge_commits() parses `git log main --merges` to find epic merges."""

    def _make_git_output(self, entries: list[tuple[str, str, str]]) -> str:
        """Build fake `git log --merges --format=%H%n%s%n%P` output.

        Each entry is (sha, subject, parents_space_separated).
        Git outputs three lines per commit, separated by newlines.
        """
        lines: list[str] = []
        for sha, subject, parents in entries:
            lines.append(sha)
            lines.append(subject)
            lines.append(parents)
        return "\n".join(lines)

    def test_single_epic_merge_detected(self):
        """A merge commit from epic/* branch is detected and epic extracted."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    "Merge branch 'epic/madruga-ai/012-something' into main",
                    "bbb222 ccc333",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        assert len(result) == 1
        assert result[0]["sha"] == "aaa111"
        assert result[0]["epic_id"] == "012-something"
        assert result[0]["platform_id"] == "madruga-ai"

    def test_multiple_epic_merges(self):
        """Multiple merge commits from different epics are all detected."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    "Merge branch 'epic/madruga-ai/012-something' into main",
                    "bbb222 ccc333",
                ),
                (
                    "ddd444",
                    "Merge branch 'epic/prosauai/007-foo-bar' into main",
                    "eee555 fff666",
                ),
                (
                    "ggg777",
                    "Merge branch 'epic/madruga-ai/015-daemon' into main",
                    "hhh888 iii999",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        assert len(result) == 3
        assert result[0]["epic_id"] == "012-something"
        assert result[0]["platform_id"] == "madruga-ai"
        assert result[1]["epic_id"] == "007-foo-bar"
        assert result[1]["platform_id"] == "prosauai"
        assert result[2]["epic_id"] == "015-daemon"
        assert result[2]["platform_id"] == "madruga-ai"

    def test_non_epic_merge_ignored(self):
        """Merge commits from non-epic branches are excluded."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    "Merge branch 'epic/madruga-ai/012-something' into main",
                    "bbb222 ccc333",
                ),
                (
                    "xxx000",
                    "Merge branch 'feature/unrelated' into main",
                    "yyy111 zzz222",
                ),
                (
                    "mmm333",
                    "Merge pull request #42 from user/fix-typo",
                    "nnn444 ooo555",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        # Only the epic merge should be included
        assert len(result) == 1
        assert result[0]["epic_id"] == "012-something"

    def test_empty_merge_history(self):
        """No merge commits returns empty list."""
        from backfill_commits import get_merge_commits

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="", returncode=0)
            result = get_merge_commits()

        assert result == []

    def test_merge_parents_preserved(self):
        """Parent SHAs from the merge are stored for later commit range queries."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    "Merge branch 'epic/madruga-ai/009-decision-log' into main",
                    "bbb222 ccc333",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        assert result[0]["parents"] == ["bbb222", "ccc333"]

    def test_gh_pr_merge_message_format(self):
        """GitHub PR merge messages like 'Merge pull request #N from org/epic/...' are detected."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    "Merge pull request #5 from paceautomations/epic/madruga-ai/012-something",
                    "bbb222 ccc333",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        assert len(result) == 1
        assert result[0]["epic_id"] == "012-something"
        assert result[0]["platform_id"] == "madruga-ai"

    def test_merge_with_double_quoted_branch(self):
        """Merge messages may use double quotes around branch name."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    'Merge branch "epic/madruga-ai/017-observability" into main',
                    "bbb222 ccc333",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        assert len(result) == 1
        assert result[0]["epic_id"] == "017-observability"

    def test_epic_slug_with_multiple_hyphens(self):
        """Epic slugs like '023-commit-traceability' with multiple segments are preserved."""
        from backfill_commits import get_merge_commits

        git_output = self._make_git_output(
            [
                (
                    "aaa111",
                    "Merge branch 'epic/madruga-ai/023-commit-traceability' into main",
                    "bbb222 ccc333",
                ),
            ]
        )

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout=git_output, returncode=0)
            result = get_merge_commits()

        assert result[0]["epic_id"] == "023-commit-traceability"

    def test_git_command_uses_correct_format(self):
        """Verify the exact git command invoked for merge listing."""
        from backfill_commits import get_merge_commits

        with patch("backfill_commits.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="", returncode=0)
            get_merge_commits()

        args = mock_sub.run.call_args
        cmd = args[0][0] if args[0] else args[1].get("args", [])
        # Must query main branch, merges only, with correct format
        assert "main" in cmd
        assert "--merges" in cmd
        assert "--format=%H%n%s%n%P" in cmd


class TestEpicExtractionFromMergeMessage:
    """Verify epic branch pattern extraction from various merge message formats."""

    def _extract(self, message: str) -> tuple[str | None, str | None]:
        """Helper: extract (platform_id, epic_id) from a merge message.

        Imports the extraction function from backfill_commits.
        """
        from backfill_commits import parse_merge_message

        return parse_merge_message(message)

    def test_standard_git_merge_message(self):
        """Standard `git merge` format with single quotes."""
        platform, epic = self._extract("Merge branch 'epic/madruga-ai/012-pipeline-dag' into main")
        assert platform == "madruga-ai"
        assert epic == "012-pipeline-dag"

    def test_github_pr_merge_message(self):
        """GitHub PR merge format: 'Merge pull request #N from org/branch'."""
        platform, epic = self._extract("Merge pull request #1 from paceautomations/epic/prosauai/007-channel-pipeline")
        assert platform == "prosauai"
        assert epic == "007-channel-pipeline"

    def test_no_epic_branch_returns_none(self):
        """Non-epic merge returns (None, None)."""
        platform, epic = self._extract("Merge branch 'feature/add-logging' into main")
        assert platform is None
        assert epic is None

    def test_merge_pr_without_epic(self):
        """PR merge from non-epic branch returns (None, None)."""
        platform, epic = self._extract("Merge pull request #42 from user/fix-typo")
        assert platform is None
        assert epic is None

    def test_double_quoted_branch_name(self):
        """Some git configs use double quotes in merge messages."""
        platform, epic = self._extract('Merge branch "epic/madruga-ai/015-whatsapp-daemon" into main')
        assert platform == "madruga-ai"
        assert epic == "015-whatsapp-daemon"

    def test_epic_with_long_slug(self):
        """Slug with multiple hyphenated words."""
        platform, epic = self._extract("Merge branch 'epic/madruga-ai/017-observability-tracing-evals' into main")
        assert platform == "madruga-ai"
        assert epic == "017-observability-tracing-evals"

    def test_merge_into_different_target(self):
        """Merge into a branch other than main still extracts epic."""
        platform, epic = self._extract("Merge branch 'epic/madruga-ai/012-something' into develop")
        assert platform == "madruga-ai"
        assert epic == "012-something"

    def test_plain_epic_branch_without_into(self):
        """Merge message that just references the branch without 'into X'."""
        platform, epic = self._extract("Merge branch 'epic/prosauai/003-onboarding'")
        assert platform == "prosauai"
        assert epic == "003-onboarding"

    def test_non_merge_message_returns_none(self):
        """Completely non-merge message returns (None, None)."""
        platform, epic = self._extract("feat: add new feature")
        assert platform is None
        assert epic is None

    def test_empty_message_returns_none(self):
        """Empty string returns (None, None)."""
        platform, epic = self._extract("")
        assert platform is None
        assert epic is None


# ---------------------------------------------------------------------------
# T033 — Pre-006 commit classification
# ---------------------------------------------------------------------------


class TestClassifyPre006:
    """classify_pre006() links commits before cutoff SHA d6befe0 to epic 001.

    The backfill uses a sequential scan of git log output.  Commits at or
    before the cutoff SHA (d6befe0) are classified as belonging to epic
    ``001-inicio-de-tudo``.  Commits after the cutoff return None so the
    caller can apply other classification logic (merge-based or ad-hoc).
    """

    # The real first commit in the repo and the cutoff for epic 001
    _FIRST_SHA = "5f62946"
    _CUTOFF_SHA = "d6befe0"

    def test_commit_at_cutoff_returns_epic_001(self):
        """The cutoff SHA itself belongs to epic 001."""
        from backfill_commits import classify_pre006

        result = classify_pre006(self._CUTOFF_SHA, cutoff_sha=self._CUTOFF_SHA)
        assert result == "001-inicio-de-tudo"

    def test_commit_before_cutoff_returns_epic_001(self):
        """A commit known to be before the cutoff returns epic 001.

        classify_pre006 receives a list of ordered SHAs (from git log) and
        a target SHA to classify.  When the target appears at or before the
        cutoff position, it returns the epic.
        """
        from backfill_commits import classify_pre006

        # Simulate ordered SHAs: first_commit ... some_middle ... cutoff ... after
        ordered_shas = [
            "aaa0001",  # oldest
            self._FIRST_SHA,
            "bbb0002",
            self._CUTOFF_SHA,
            "ccc0003",  # after cutoff
            "ddd0004",
        ]
        # A commit before the cutoff
        result = classify_pre006("bbb0002", cutoff_sha=self._CUTOFF_SHA, ordered_shas=ordered_shas)
        assert result == "001-inicio-de-tudo"

    def test_first_commit_returns_epic_001(self):
        """The very first commit (5f62946) belongs to epic 001."""
        from backfill_commits import classify_pre006

        ordered_shas = [
            self._FIRST_SHA,
            "aaa0002",
            self._CUTOFF_SHA,
            "bbb0003",
        ]
        result = classify_pre006(self._FIRST_SHA, cutoff_sha=self._CUTOFF_SHA, ordered_shas=ordered_shas)
        assert result == "001-inicio-de-tudo"

    def test_commit_after_cutoff_returns_none(self):
        """A commit after the cutoff is NOT part of epic 001."""
        from backfill_commits import classify_pre006

        ordered_shas = [
            self._FIRST_SHA,
            self._CUTOFF_SHA,
            "after001",
            "after002",
        ]
        result = classify_pre006("after001", cutoff_sha=self._CUTOFF_SHA, ordered_shas=ordered_shas)
        assert result is None

    def test_commit_not_in_list_returns_none(self):
        """A SHA not found in the ordered list returns None (safe default)."""
        from backfill_commits import classify_pre006

        ordered_shas = [self._FIRST_SHA, self._CUTOFF_SHA, "after001"]
        result = classify_pre006("unknown_sha", cutoff_sha=self._CUTOFF_SHA, ordered_shas=ordered_shas)
        assert result is None

    def test_empty_ordered_shas_returns_none(self):
        """Empty SHA list returns None without error."""
        from backfill_commits import classify_pre006

        result = classify_pre006("any_sha", cutoff_sha=self._CUTOFF_SHA, ordered_shas=[])
        assert result is None

    def test_default_cutoff_sha(self):
        """When cutoff_sha is not provided, defaults to d6befe0."""
        from backfill_commits import classify_pre006

        # Use simple mode: just sha and cutoff comparison
        # The function should have d6befe0 as default
        result = classify_pre006(self._CUTOFF_SHA)
        assert result == "001-inicio-de-tudo"

    def test_partial_sha_match(self):
        """classify_pre006 should handle partial SHA prefixes (7+ chars).

        Git SHAs can be abbreviated.  The function should match when the
        provided SHA starts with (or is a prefix of) the cutoff.
        """
        from backfill_commits import classify_pre006

        # Full 40-char SHA that starts with the cutoff prefix
        full_cutoff = "d6befe0abc123def456789012345678901234567"
        ordered_shas = [
            self._FIRST_SHA,
            full_cutoff,
            "eee0001",
        ]
        result = classify_pre006(full_cutoff, cutoff_sha=self._CUTOFF_SHA, ordered_shas=ordered_shas)
        assert result == "001-inicio-de-tudo"

    def test_returns_correct_epic_string(self):
        """The returned epic slug is exactly '001-inicio-de-tudo' (no variations)."""
        from backfill_commits import classify_pre006

        result = classify_pre006(self._CUTOFF_SHA)
        assert result == "001-inicio-de-tudo"
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# T034 — Backfill idempotency
# ---------------------------------------------------------------------------


def _create_commits_table(conn: sqlite3.Connection) -> None:
    """Create the commits table matching the latest migrations (014 + 018 + 019)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha TEXT NOT NULL UNIQUE,
            message TEXT NOT NULL,
            author TEXT NOT NULL,
            platform_id TEXT NOT NULL,
            epic_id TEXT,
            source TEXT NOT NULL DEFAULT 'hook'
                CHECK (source IN ('hook', 'backfill', 'manual', 'reseed', 'external-fetch')),
            committed_at TEXT NOT NULL,
            files_json TEXT DEFAULT '[]',
            reconciled_at TEXT,
            host_repo TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_commits_platform ON commits(platform_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_commits_epic ON commits(epic_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_commits_host_repo ON commits(host_repo)")
    conn.commit()


def _count_commits(conn: sqlite3.Connection) -> int:
    """Return total row count in commits table."""
    row = conn.execute("SELECT COUNT(*) FROM commits").fetchone()
    return row[0]


# Fake git outputs reused across idempotency tests
_MERGE_LOG_OUTPUT = (
    "aaa111\n"
    "Merge branch 'epic/madruga-ai/012-pipeline-dag' into main\n"
    "ppp111 ppp222\n"
    "bbb222\n"
    "Merge branch 'epic/madruga-ai/015-daemon' into main\n"
    "ppp333 ppp444"
)

_EPIC_COMMITS_OUTPUT = (
    "ccc333\nfeat: add parser\nDev A\n2026-03-01T10:00:00Z\nddd444\nfix: typo\nDev B\n2026-03-02T11:00:00Z"
)

_DIRECT_MAIN_OUTPUT = "eee555\nchore: update deps\nDev C\n2026-02-15T09:00:00Z"


class TestBackfillIdempotency:
    """Running backfill twice must not create duplicate rows (FR-009, SC-005).

    The backfill script uses INSERT OR IGNORE on the SHA UNIQUE constraint.
    Re-running should produce the exact same row count.
    """

    @pytest.fixture()
    def backfill_db(self, tmp_path):
        """Create a temporary SQLite DB with commits table."""
        db_path = tmp_path / "test_backfill.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        _create_commits_table(conn)
        return conn, db_path

    def _mock_subprocess_calls(self, mock_sub):
        """Configure subprocess.run mock for all git commands backfill calls.

        Returns different outputs based on the command arguments.
        """

        def side_effect(cmd, *args, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            result = MagicMock(returncode=0)
            if "--merges" in cmd_str:
                result.stdout = _MERGE_LOG_OUTPUT
            elif "diff-tree" in cmd_str:
                result.stdout = "platforms/madruga-ai/some-file.py"
            elif "--no-merges" in cmd_str and "--first-parent" in cmd_str:
                result.stdout = _DIRECT_MAIN_OUTPUT
            elif "log" in cmd_str:
                # Fallback for epic commit range queries
                result.stdout = _EPIC_COMMITS_OUTPUT
            else:
                result.stdout = ""
            return result

        mock_sub.run.side_effect = side_effect

    def test_second_run_produces_zero_new_rows(self, backfill_db):
        """Run backfill twice: row count after second run equals first run."""
        from backfill_commits import run_backfill

        conn, db_path = backfill_db

        with patch("backfill_commits.subprocess") as mock_sub:
            self._mock_subprocess_calls(mock_sub)

            # First run — inserts commits
            run_backfill(conn)
            count_after_first = _count_commits(conn)

            # Second run — should insert nothing new (INSERT OR IGNORE)
            run_backfill(conn)
            count_after_second = _count_commits(conn)

        assert count_after_first > 0, "First run should insert at least one commit"
        assert count_after_second == count_after_first, (
            f"Second run changed row count: {count_after_first} → {count_after_second}"
        )

    def test_third_run_still_idempotent(self, backfill_db):
        """Even a third consecutive run adds zero new rows."""
        from backfill_commits import run_backfill

        conn, db_path = backfill_db

        with patch("backfill_commits.subprocess") as mock_sub:
            self._mock_subprocess_calls(mock_sub)

            run_backfill(conn)
            run_backfill(conn)
            run_backfill(conn)
            count = _count_commits(conn)

        # Should equal first-run count (same git history mocked)
        with patch("backfill_commits.subprocess") as mock_sub2:
            self._mock_subprocess_calls(mock_sub2)
            conn2 = sqlite3.connect(":memory:")
            _create_commits_table(conn2)
            run_backfill(conn2)
            expected = _count_commits(conn2)
            conn2.close()

        assert count == expected

    def test_no_duplicate_shas_after_double_run(self, backfill_db):
        """After two runs, every SHA in the DB is unique (no duplicates)."""
        from backfill_commits import run_backfill

        conn, db_path = backfill_db

        with patch("backfill_commits.subprocess") as mock_sub:
            self._mock_subprocess_calls(mock_sub)
            run_backfill(conn)
            run_backfill(conn)

        # Check for duplicate SHAs
        rows = conn.execute("SELECT sha, COUNT(*) as cnt FROM commits GROUP BY sha HAVING cnt > 1").fetchall()
        assert rows == [], f"Duplicate SHAs found: {rows}"

    def test_idempotency_with_mixed_epic_and_adhoc(self, backfill_db):
        """Both epic-linked and ad-hoc commits maintain idempotency."""
        from backfill_commits import run_backfill

        conn, db_path = backfill_db

        with patch("backfill_commits.subprocess") as mock_sub:
            self._mock_subprocess_calls(mock_sub)
            run_backfill(conn)

        epic_count_1 = conn.execute("SELECT COUNT(*) FROM commits WHERE epic_id IS NOT NULL").fetchone()[0]
        adhoc_count_1 = conn.execute("SELECT COUNT(*) FROM commits WHERE epic_id IS NULL").fetchone()[0]

        with patch("backfill_commits.subprocess") as mock_sub:
            self._mock_subprocess_calls(mock_sub)
            run_backfill(conn)

        epic_count_2 = conn.execute("SELECT COUNT(*) FROM commits WHERE epic_id IS NOT NULL").fetchone()[0]
        adhoc_count_2 = conn.execute("SELECT COUNT(*) FROM commits WHERE epic_id IS NULL").fetchone()[0]

        assert epic_count_1 == epic_count_2, "Epic commit count changed on re-run"
        assert adhoc_count_1 == adhoc_count_2, "Ad-hoc commit count changed on re-run"

    def test_backfill_uses_source_backfill(self, backfill_db):
        """All commits inserted by backfill have source='backfill'."""
        from backfill_commits import run_backfill

        conn, db_path = backfill_db

        with patch("backfill_commits.subprocess") as mock_sub:
            self._mock_subprocess_calls(mock_sub)
            run_backfill(conn)

        non_backfill = conn.execute("SELECT COUNT(*) FROM commits WHERE source != 'backfill'").fetchone()[0]
        assert non_backfill == 0, "Some commits have source != 'backfill'"
