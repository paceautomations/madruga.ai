"""Tests for ntfy.py — ntfy.sh alert function."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_ntfy_alert_success():
    """ntfy_alert returns True when HTTP POST succeeds."""
    from ntfy import ntfy_alert

    with patch("ntfy.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = MagicMock()
        result = ntfy_alert("test-topic", "hello")
    assert result is True
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "https://ntfy.sh/test-topic"
    assert req.data == b"hello"
    assert req.get_header("Title") == "Madruga AI"


def test_ntfy_alert_failure_silent():
    """ntfy_alert returns False on network error (no exception raised)."""
    from ntfy import ntfy_alert

    with patch("ntfy.urllib.request.urlopen", side_effect=OSError("connection refused")):
        result = ntfy_alert("test-topic", "hello")
    assert result is False


def test_ntfy_alert_timeout():
    """ntfy_alert passes timeout to urlopen."""
    from ntfy import ntfy_alert

    with patch("ntfy.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = MagicMock()
        ntfy_alert("t", "m", timeout=10)
    assert mock_urlopen.call_args[1]["timeout"] == 10
