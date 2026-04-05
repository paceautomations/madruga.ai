"""log_utils.py — Shared NDJSON logging for madruga.ai scripts."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class NDJSONFormatter(logging.Formatter):
    """Emit one JSON object per line for CI consumption."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
            }
        )


def setup_logging(json_mode: bool, verbose: bool = False) -> None:
    """Configure root logger for human or NDJSON output."""
    handler = logging.StreamHandler()
    if json_mode:
        handler.setFormatter(NDJSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.DEBUG if verbose else logging.INFO)
