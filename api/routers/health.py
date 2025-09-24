"""Liveness and version endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["meta"])


@router.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.get("/version")
def version() -> dict[str, str]:
    return {"title": settings.API_TITLE, "version": settings.API_VERSION}
