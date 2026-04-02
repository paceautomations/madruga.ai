"""sd_notify.py — systemd notification via NOTIFY_SOCKET (stdlib only)."""

from __future__ import annotations

import os
import socket


def sd_notify(state: str) -> bool:
    """Send notification to systemd. Returns True if sent, False on any failure."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr.startswith("@"):
        addr = "\0" + addr[1:]  # abstract socket
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(addr)
            sock.sendall(state.encode())
            return True
        finally:
            sock.close()
    except OSError:
        return False
