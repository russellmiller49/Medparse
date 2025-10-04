"""Schema for textbook chapter structured fields."""
from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class ChapterSection(BaseModel):
    """Represents a targeted chapter subsection."""

    title: Optional[str] = None
    text: str
    page: Optional[int] = None
    span: Optional[Tuple[int, int]] = None


class ChapterExtract(BaseModel):
    """Container for clinically relevant chapter sections."""

    doc_id: str
    etiology: List[ChapterSection] = Field(default_factory=list)
    classification: List[ChapterSection] = Field(default_factory=list)
    signs_symptoms: List[ChapterSection] = Field(default_factory=list)
    diagnostic_workup: List[ChapterSection] = Field(default_factory=list)
    management_principles: List[ChapterSection] = Field(default_factory=list)
    complications: List[ChapterSection] = Field(default_factory=list)
    schema_version: str = "1.0"


__all__ = [
    "ChapterSection",
    "ChapterExtract",
]
