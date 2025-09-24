from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration sourced from environment variables."""

    API_TITLE: str = Field(default="Medparse API")
    API_VERSION: str = Field(default="0.1.0")
    GROBID_URL: str = Field(default="http://localhost:8070")
    UMLS_API_KEY: str = Field(default="")
    NCBI_API_KEY: str = Field(default="")
    NCBI_EMAIL: str = Field(default="")
    QUICKUMLS_PATH: str | None = Field(default=None)
    ALLOWED_ORIGINS: str = Field(default="http://localhost:7860")
    MAX_UPLOAD_MB: int = Field(default=40)
    ENABLE_PIPELINE: bool = Field(default=True)
    API_KEY: str = Field(default="")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
