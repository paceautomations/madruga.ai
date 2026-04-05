"""Tests for log_utils.py — shared NDJSON logging."""

import json
import logging


def test_ndjson_formatter_produces_valid_json():
    from log_utils import NDJSONFormatter

    formatter = NDJSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "hello world"
    assert data["logger"] == "test_logger"
    assert "timestamp" in data


def test_setup_logging_json_mode():
    from log_utils import setup_logging

    # Just verify it doesn't raise
    setup_logging(json_mode=True, verbose=True)
    # Cleanup: remove handlers added by setup_logging
    logging.root.handlers = [h for h in logging.root.handlers if h.__class__.__name__ != "StreamHandler"]
