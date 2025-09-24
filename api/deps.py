"""Reusable FastAPI dependencies."""
from __future__ import annotations

from fastapi import Header, HTTPException

from .config import settings
from .logging import logger


def api_key_required(x_api_key: str | None = Header(default=None)) -> bool:
    """Optional API-key guard. Accept all traffic when no key configured."""
    required_key = settings.API_KEY
    if required_key:
        if x_api_key != required_key:
            logger.warning("Rejected request with invalid API key header")
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True


__all__ = ["api_key_required"]
