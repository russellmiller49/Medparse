"""Centralized log configuration for the Medparse API."""
from __future__ import annotations

import sys
from loguru import logger


def setup_logging() -> "loguru.Logger":
    """Configure loguru to emit structured logs to stdout."""
    logger.remove()
    logger.add(sys.stdout, level="INFO", backtrace=False, diagnose=False)
    return logger


__all__ = ["setup_logging", "logger"]
