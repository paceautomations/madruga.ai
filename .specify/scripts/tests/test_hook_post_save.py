"""Tests for hook_post_save.py — PostToolUse hook wrapper."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent))

import hook_post_save


class TestMain:
    """Tests for hook_post_save.main()."""

    def test_valid_json_with_file_path_calls_subprocess(self):
        payload = {"tool_input": {"file_path": "platforms/test-platform/business/vision.md"}}
        stdin = io.StringIO(json.dumps(payload))

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--detect-from-path" in args
        assert "--register-only" in args
        assert "platforms/test-platform/business/vision.md" in args

    def test_empty_file_path_returns_early(self):
        payload = {"tool_input": {"file_path": ""}}
        stdin = io.StringIO(json.dumps(payload))

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        mock_run.assert_not_called()

    def test_invalid_json_returns_early(self):
        stdin = io.StringIO("not json at all")

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        mock_run.assert_not_called()

    def test_missing_tool_input_returns_early(self):
        payload = {"other_key": "value"}
        stdin = io.StringIO(json.dumps(payload))

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        mock_run.assert_not_called()

    def test_non_platforms_path_returns_early(self):
        payload = {"tool_input": {"file_path": "/tmp/some-other-file.md"}}
        stdin = io.StringIO(json.dumps(payload))

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        mock_run.assert_not_called()

    def test_missing_file_path_in_tool_input_returns_early(self):
        payload = {"tool_input": {"other_key": "value"}}
        stdin = io.StringIO(json.dumps(payload))

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        mock_run.assert_not_called()

    def test_subprocess_uses_correct_script_path(self):
        payload = {"tool_input": {"file_path": "platforms/test-platform/business/vision.md"}}
        stdin = io.StringIO(json.dumps(payload))

        with patch.object(sys, "stdin", stdin), patch("hook_post_save.subprocess.run") as mock_run:
            hook_post_save.main()

        args = mock_run.call_args[0][0]
        # Should use post_save.py from the same directory
        assert "post_save.py" in args[1]
        assert mock_run.call_args[1].get("capture_output") is True
