"""Centralised configuration for the Medparse pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _custom_parse_env_var(field_name: str, raw_value: str) -> str:
    """Return raw environment values so validators can process custom formats."""

    return raw_value


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables or .env files."""

    umls_api_key: Optional[str] = Field(default=None, alias="UMLS_API_KEY")
    quickumls_path: Optional[Path] = Field(default=None, alias="QUICKUMLS_PATH")
    scispacy_model: Optional[str] = Field(default=None, alias="SCISPACY_MODEL")
    tui_whitelist_raw: Optional[str] = Field(default=None, alias="TUI_WHITELIST")
    enable_ocr: bool = Field(default=False, alias="ENABLE_OCR")
    grobid_url: Optional[str] = Field(default=None, alias="GROBID_URL")
    pubmed_email: Optional[str] = Field(default=None, alias="PUBMED_EMAIL")
    pubmed_tool: Optional[str] = Field(default=None, alias="PUBMED_TOOL")
    neo4j_uri: Optional[str] = Field(default=None, alias="NEO4J_URI")
    neo4j_user: Optional[str] = Field(default=None, alias="NEO4J_USER")
    neo4j_password: Optional[str] = Field(default=None, alias="NEO4J_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        parse_env_var=_custom_parse_env_var,
    )

    @classmethod
    def model_construct_from_env(cls, env_file: Optional[Path] = None) -> "AppConfig":
        """Helper for tests to load configuration from a given ``.env`` file."""

        kwargs = {}
        if env_file is not None:
            kwargs["_env_file"] = env_file
        return cls(**kwargs)

    @field_validator("enable_ocr", mode="before")
    @classmethod
    def _validate_enable_ocr(cls, value: Optional[object]) -> bool:
        if isinstance(value, bool):
            return value
        if value in (None, "", "0", 0):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @property
    def tui_whitelist(self) -> Set[str]:
        if not self.tui_whitelist_raw:
            return set()
        return {item.strip() for item in self.tui_whitelist_raw.split(",") if item.strip()}


__all__ = ["AppConfig"]
