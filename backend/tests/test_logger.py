import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import logging
import pytest
from unittest.mock import patch


def test_json_formatter_produces_valid_json():
    from logger import JsonFormatter
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["logger"] == "test.module"
    assert data["msg"] == "hello world"
    assert "ts" in data


def test_setup_logging_adds_stream_handler(tmp_path):
    from logger import setup_logging
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    try:
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG", "LOG_FILE": str(tmp_path / "app.json")}):
            setup_logging()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "StreamHandler" in handler_types
    finally:
        for h in root.handlers[:]:
            if h not in original_handlers:
                root.removeHandler(h)


def test_setup_logging_creates_json_file(tmp_path):
    from logger import setup_logging
    log_path = tmp_path / "app.json"
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    try:
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG", "LOG_FILE": str(log_path)}):
            setup_logging()
        logging.getLogger("test").info("test message")
        assert log_path.exists()
        line = log_path.read_text().strip().splitlines()[0]
        data = json.loads(line)
        assert data["msg"] == "test message"
    finally:
        for h in root.handlers[:]:
            if h not in original_handlers:
                root.removeHandler(h)


def test_setup_logging_no_file_when_log_file_empty(tmp_path):
    from logger import setup_logging
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    try:
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO", "LOG_FILE": ""}):
            setup_logging()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "RotatingFileHandler" not in handler_types
    finally:
        for h in root.handlers[:]:
            if h not in original_handlers:
                root.removeHandler(h)
