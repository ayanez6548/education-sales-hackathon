"""Logging helpers that avoid dumping secrets or full personal data."""

from __future__ import annotations

import logging
import re

from app.config import get_settings

SECRET_PATTERN = re.compile(r"(token|secret|password|authorization|api[_-]?key)=([^&\s]+)", re.I)
NOISY_HTTP_LOGGERS = ("httpx", "httpcore", "httpcore.connection", "httpcore.http11")


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for name in NOISY_HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def redact(value: str) -> str:
    return SECRET_PATTERN.sub(r"\1=[redacted]", value)
