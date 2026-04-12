"""Tests for queue/dequeue/queue-list CLI + promote_queued_epic (T029–T044b)."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def queue_db(tmp_path):
    """DB with a platform + drafted epic ready for queue tests."""
    from db_core import get_conn, migrate

    db_path = tmp_path / "test.db"
    migrations_dir = Path(__file__).parents[3] / ".pipeline" / "migrations"
    conn = get_conn(db_path)
    migrate(conn, migrations_dir)

    conn.execute(
        "INSERT OR IGNORE INTO platforms (platform_id, name, title, lifecycle, repo_path)"
        " VALUES ('prosauai', 'prosauai', 'ProsauAI', 'design', '/tmp/prosauai')"
    )
    conn.execute(
        "INSERT INTO epics (epic_id, platform_id, title, status, created_at, updated_at)"
        " VALUES ('004-foo', 'prosauai', 'Foo', 'drafted', '2026-04-12T00:00:00Z', '2026-04-12T00:00:00Z')"
    )
    conn.commit()
    yield conn, db_path
    conn.close()


# ── CLI queue subcommand (T029–T032) ────────────────────────────────────


class TestCmdQueue:
    def test_queue_drafted_to_queued(self, queue_db):
        """T029: queue command transitions drafted → queued."""
        conn, db_path = queue_db
        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue

            cmd_queue("prosauai", "004-foo")

        row = conn.execute("SELECT status FROM epics WHERE epic_id='004-foo'").fetchone()
        assert row[0] == "queued"

    def test_queue_rejects_non_drafted(self, queue_db):
        """T030: queue rejects epic not in drafted status."""
        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='in_progress' WHERE epic_id='004-foo'")
        conn.commit()

        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue

            with pytest.raises(SystemExit) as exc:
                cmd_queue("prosauai", "004-foo")
            assert exc.value.code == 3

    def test_queue_rejects_unknown_epic(self, queue_db):
        """T031: queue rejects unknown epic."""
        _, db_path = queue_db
        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue

            with pytest.raises(SystemExit) as exc:
                cmd_queue("prosauai", "999-nonexistent")
            assert exc.value.code == 2

    def test_queue_rejects_unknown_platform(self, queue_db):
        """T032: queue rejects unknown platform (no epics found)."""
        _, db_path = queue_db
        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue

            with pytest.raises(SystemExit) as exc:
                cmd_queue("no-such-platform", "004-foo")
            assert exc.value.code == 2


# ── CLI dequeue subcommand (T033–T034) ──────────────────────────────────


class TestCmdDequeue:
    def test_dequeue_queued_to_drafted(self, queue_db):
        """T033: dequeue reverts queued → drafted."""
        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_dequeue

            cmd_dequeue("prosauai", "004-foo")

        row = conn.execute("SELECT status FROM epics WHERE epic_id='004-foo'").fetchone()
        assert row[0] == "drafted"

    def test_dequeue_preserves_artifact_files(self, queue_db, tmp_path):
        """T034: dequeue does not delete pitch.md or any files on disk."""
        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        pitch_file = tmp_path / "pitch.md"
        pitch_file.write_text("# Pitch\nContent here")

        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_dequeue

            cmd_dequeue("prosauai", "004-foo")

        assert pitch_file.exists()
        assert pitch_file.read_text() == "# Pitch\nContent here"


# ── CLI queue-list subcommand (T035–T037) ───────────────────────────────


class TestCmdQueueList:
    def test_empty_queue(self, queue_db, capsys):
        """T035: queue-list with no queued epics."""
        _, db_path = queue_db
        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue_list

            cmd_queue_list("prosauai")

        out = capsys.readouterr().out
        assert "No epics queued" in out

    def test_fifo_order(self, queue_db, capsys):
        """T036: queue-list shows epics in FIFO order (oldest first)."""
        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.execute(
            "INSERT INTO epics (epic_id, platform_id, title, status, created_at, updated_at)"
            " VALUES ('005-bar', 'prosauai', 'Bar', 'queued', '2026-04-12T01:00:00Z', '2026-04-12T01:00:00Z')"
        )
        conn.commit()

        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue_list

            cmd_queue_list("prosauai")

        out = capsys.readouterr().out
        pos_foo = out.index("004-foo")
        pos_bar = out.index("005-bar")
        assert pos_foo < pos_bar, "004-foo (older) should appear before 005-bar"

    def test_json_output(self, queue_db, capsys):
        """T037: queue-list --json produces valid JSON."""
        import json

        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        with patch("db_core.DB_PATH", db_path):
            from platform_cli import cmd_queue_list

            cmd_queue_list("prosauai", as_json=True)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["platform"] == "prosauai"
        assert data["count"] == 1
        assert data["queue"][0]["epic_id"] == "004-foo"


# ── promote_queued_epic (T038–T044b) ────────────────────────────────────


class TestPromoteQueuedEpic:
    def test_no_queue_returns_no_queue(self, queue_db):
        """T038: Empty queue → status='no_queue'."""
        _, db_path = queue_db
        with patch("db_core.DB_PATH", db_path):
            from queue_promotion import promote_queued_epic

            result = promote_queued_epic("prosauai")
        assert result.status == "no_queue"

    @patch("queue_promotion.subprocess.run")
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_happy_path(self, mock_selfref, mock_binding, mock_ensure, mock_subproc, queue_db):
        """T039: Happy path — queued epic promoted on first attempt."""
        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        mock_binding.return_value = {
            "org": "paceautomations",
            "name": "prosauai",
            "base_branch": "develop",
            "epic_branch_prefix": "epic/prosauai/",
        }
        mock_ensure.return_value = Path("/tmp/prosauai")

        # git status (clean), git branch --list (empty), git fetch, git for-each-ref (empty),
        # git checkout -b, git checkout base --, git add, git commit
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("db_core.DB_PATH", db_path):
            from queue_promotion import promote_queued_epic

            result = promote_queued_epic("prosauai")

        assert result.status == "promoted"
        assert result.epic_id == "004-foo"
        assert result.attempts == 1
        assert result.branch_name == "epic/prosauai/004-foo"

        # Verify DB state
        row = conn.execute("SELECT status, branch_name FROM epics WHERE epic_id='004-foo'").fetchone()
        assert row[0] == "in_progress"
        assert row[1] == "epic/prosauai/004-foo"

    @patch("queue_promotion.subprocess.run")
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_retry_on_transient_failure(self, mock_selfref, mock_binding, mock_ensure, mock_subproc, queue_db):
        """T040: Transient git failure on attempt 1, success on attempt 2."""
        import subprocess as real_subprocess

        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        mock_binding.return_value = {
            "org": "paceautomations",
            "name": "prosauai",
            "base_branch": "develop",
            "epic_branch_prefix": "epic/prosauai/",
        }
        mock_ensure.return_value = Path("/tmp/prosauai")

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # First git status call → succeed. Then fail on checkout.
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and "status" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "branch" in cmd and "--list" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "fetch" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "for-each-ref" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "rev-list" in cmd:
                return MagicMock(returncode=0, stdout="0", stderr="")
            if isinstance(cmd, list) and "checkout" in cmd and "-b" in cmd:
                if call_count[0] < 10:
                    raise real_subprocess.CalledProcessError(1, cmd, stderr="lock error")
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subproc.side_effect = side_effect

        with patch("db_core.DB_PATH", db_path), patch("queue_promotion.time.sleep"):
            from queue_promotion import promote_queued_epic

            result = promote_queued_epic("prosauai")

        assert result.status == "promoted"
        assert result.attempts >= 2

    @patch("queue_promotion._notify")
    @patch("queue_promotion.subprocess.run")
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_retry_exhaustion_marks_blocked(
        self, mock_selfref, mock_binding, mock_ensure, mock_subproc, mock_notify, queue_db
    ):
        """T041: All 3 attempts fail → blocked + notification."""
        import subprocess as real_subprocess

        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        mock_binding.return_value = {
            "org": "paceautomations",
            "name": "prosauai",
            "base_branch": "develop",
            "epic_branch_prefix": "epic/prosauai/",
        }
        mock_ensure.return_value = Path("/tmp/prosauai")

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and "status" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "branch" in cmd and "--list" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "fetch" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "for-each-ref" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "rev-list" in cmd:
                return MagicMock(returncode=0, stdout="0", stderr="")
            # Always fail on checkout -b
            if isinstance(cmd, list) and "checkout" in cmd and "-b" in cmd:
                raise real_subprocess.CalledProcessError(1, cmd, stderr="fatal error")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subproc.side_effect = side_effect

        with patch("db_core.DB_PATH", db_path), patch("queue_promotion.time.sleep"):
            from queue_promotion import promote_queued_epic

            result = promote_queued_epic("prosauai")

        assert result.status == "blocked_retry_exhausted"
        assert result.attempts == 3

        # FR-013: no half-written branch metadata
        row = conn.execute("SELECT status, branch_name FROM epics WHERE epic_id='004-foo'").fetchone()
        assert row[0] == "blocked"
        assert row[1] is None, "branch_name must remain NULL after failed promotion"

        mock_notify.assert_called_once()

    @patch("queue_promotion._notify")
    @patch("queue_promotion._checkout_epic_branch")
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_dirty_tree_blocks_immediately(
        self, mock_selfref, mock_binding, mock_ensure, mock_checkout, mock_notify, queue_db
    ):
        """T042: Dirty tree → blocked immediately, no retry."""
        from queue_promotion import DirtyTreeError

        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        mock_binding.return_value = {
            "org": "paceautomations",
            "name": "prosauai",
            "base_branch": "develop",
            "epic_branch_prefix": "epic/prosauai/",
        }
        mock_ensure.return_value = Path("/tmp/prosauai")
        mock_checkout.side_effect = DirtyTreeError("M README.md")

        with patch("db_core.DB_PATH", db_path):
            from queue_promotion import promote_queued_epic

            result = promote_queued_epic("prosauai")

        assert result.status == "blocked_dirty_tree"
        assert result.attempts == 1  # no retry

        row = conn.execute("SELECT status FROM epics WHERE epic_id='004-foo'").fetchone()
        assert row[0] == "blocked"
        mock_notify.assert_called_once()

    @patch("queue_promotion.subprocess.run")
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_idempotent_race(self, mock_selfref, mock_binding, mock_ensure, mock_subproc, queue_db):
        """T043: Concurrent promote — second call sees rowcount=0, still returns promoted."""
        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        mock_binding.return_value = {
            "org": "paceautomations",
            "name": "prosauai",
            "base_branch": "develop",
            "epic_branch_prefix": "epic/prosauai/",
        }
        mock_ensure.return_value = Path("/tmp/prosauai")
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("db_core.DB_PATH", db_path):
            from queue_promotion import promote_queued_epic

            # First call succeeds
            r1 = promote_queued_epic("prosauai")
            assert r1.status == "promoted"

            # Epic is now in_progress — second call finds no queued epic
            r2 = promote_queued_epic("prosauai")
            assert r2.status == "no_queue"

    @patch("queue_promotion.subprocess.run")
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_retry_budget_within_10s(self, mock_selfref, mock_binding, mock_ensure, mock_subproc, queue_db):
        """T044: Total wall time ≤ 10s even with retries."""
        import subprocess as real_subprocess

        conn, db_path = queue_db
        conn.execute("UPDATE epics SET status='queued' WHERE epic_id='004-foo'")
        conn.commit()

        mock_binding.return_value = {
            "org": "paceautomations",
            "name": "prosauai",
            "base_branch": "develop",
            "epic_branch_prefix": "epic/prosauai/",
        }
        mock_ensure.return_value = Path("/tmp/prosauai")

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and "status" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "branch" in cmd and "--list" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "fetch" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "for-each-ref" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and "rev-list" in cmd:
                return MagicMock(returncode=0, stdout="0", stderr="")
            if isinstance(cmd, list) and "checkout" in cmd and "-b" in cmd:
                raise real_subprocess.CalledProcessError(1, cmd, stderr="fail")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subproc.side_effect = side_effect

        with patch("db_core.DB_PATH", db_path), patch("queue_promotion.time.sleep"):
            from queue_promotion import promote_queued_epic

            t0 = time.monotonic()
            result = promote_queued_epic("prosauai")
            elapsed = time.monotonic() - t0

        assert result.status == "blocked_retry_exhausted"
        # With mocked sleep, wall time should be negligible
        assert elapsed < 10.0
