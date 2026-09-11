"""Structured (JSON) logging setup, no external dependency."""

from __future__ import annotations

import json
import logging
import sys

_EXTRA_FIELDS = ("request_id", "site", "path", "method", "status_code", "latency_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Quiet down noisy third-party loggers at INFO; keep our own verbose.
    logging.getLogger("sqlalchemy.engine").setLevel(max(logging.WARNING, root.level))
