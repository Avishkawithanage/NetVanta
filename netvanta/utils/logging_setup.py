"""Local rotating log file. Nothing is ever uploaded."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import log_file

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("netvanta")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        try:
            handler = RotatingFileHandler(log_file(), maxBytes=512_000, backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter(_FORMAT))
            logger.addHandler(handler)
        except OSError:
            logger.addHandler(logging.NullHandler())
    return logger


def set_level(level: str) -> None:
    logging.getLogger("netvanta").setLevel(getattr(logging, level.upper(), logging.INFO))
