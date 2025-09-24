"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .config import settings
from .logging import setup_logging
from .routers import extract, health, link

logger = setup_logging()

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    default_response_class=ORJSONResponse,
)

allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(extract.router)
app.include_router(link.router)


@logger.catch
@app.on_event("startup")
async def _startup() -> None:
    logger.info("Starting %s v%s", settings.API_TITLE, settings.API_VERSION)


__all__ = ["app"]
