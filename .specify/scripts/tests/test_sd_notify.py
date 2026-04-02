"""Tests for sd_notify.py — systemd notification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_sd_notify_with_socket():
    """sd_notify sends state when NOTIFY_SOCKET is set."""
    from sd_notify import sd_notify

    mock_sock = MagicMock()
    with (
        patch.dict("os.environ", {"NOTIFY_SOCKET": "/run/systemd/notify"}),
        patch("sd_notify.socket.socket", return_value=mock_sock),
    ):
        result = sd_notify("READY=1")

    assert result is True
    mock_sock.connect.assert_called_once_with("/run/systemd/notify")
    mock_sock.sendall.assert_called_once_with(b"READY=1")
    mock_sock.close.assert_called_once()


def test_sd_notify_no_socket_returns_false():
    """sd_notify returns False when NOTIFY_SOCKET is not set."""
    from sd_notify import sd_notify

    with patch.dict("os.environ", {}, clear=True):
        result = sd_notify("READY=1")
    assert result is False


def test_sd_notify_abstract_socket():
    """sd_notify handles abstract socket addresses (prefixed with @)."""
    from sd_notify import sd_notify

    mock_sock = MagicMock()
    with (
        patch.dict("os.environ", {"NOTIFY_SOCKET": "@/run/systemd/notify"}),
        patch("sd_notify.socket.socket", return_value=mock_sock),
    ):
        result = sd_notify("WATCHDOG=1")

    assert result is True
    mock_sock.connect.assert_called_once_with("\0/run/systemd/notify")
