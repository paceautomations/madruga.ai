"""ntfy.py — Fire-and-forget alerts via ntfy.sh (stdlib only)."""

from __future__ import annotations

import urllib.request


def ntfy_alert(topic: str, message: str, title: str = "Madruga AI", timeout: int = 5) -> bool:
    """Send alert via ntfy.sh. Returns True if sent, False on any failure."""
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=message.encode(),
            headers={"Title": title},
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False
