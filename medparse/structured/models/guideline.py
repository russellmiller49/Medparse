"""Schema definitions for guideline-specific extraction payloads."""
from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class GuidelineRecommendation(BaseModel):
    """Structured representation of a single guideline recommendation."""

    id: str
    doc_id: str
    number: Optional[int] = None
    text: str
    grade: Optional[str] = None
    evidence_level: Optional[str] = None
    context: Optional[str] = None
    stations: List[str] = Field(default_factory=list)
    figures: List[str] = Field(default_factory=list)
    page: Optional[int] = None
    span: Optional[Tuple[int, int]] = None
    section: Optional[str] = None


class StationCoverageEntry(BaseModel):
    """Mapping of mediastinal stations to modality access."""

    doc_id: str
    station: str
    ebus: bool = False
    eus: bool = False
    notes: Optional[str] = None
    page: Optional[int] = None


class GuidelineExtract(BaseModel):
    """Container for guideline-specific artifacts."""

    doc_id: str
    recommendations: List[GuidelineRecommendation] = Field(default_factory=list)
    coverage_map: List[StationCoverageEntry] = Field(default_factory=list)
    schema_version: str = "1.0"


__all__ = [
    "GuidelineRecommendation",
    "StationCoverageEntry",
    "GuidelineExtract",
]
