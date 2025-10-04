"""Typed models exposed by the Medparse API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class UmlsLink(BaseModel):
    cui: str
    text: str
    start: Optional[int] = None
    end: Optional[int] = None
    tui: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    score: float = Field(default=0.0)
    preferred_term: Optional[str] = None
    preferred_name: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    offsets: Optional[List[int]] = None
    sentence: Optional[str] = None

    @model_validator(mode="after")
    def _sync_fields(self) -> "UmlsLink":
        if self.confidence and not self.score:
            self.score = self.confidence
        if self.score and not self.confidence:
            self.confidence = self.score
        preferred = self.preferred_term or self.preferred_name
        if preferred:
            self.preferred_term = preferred
            self.preferred_name = preferred
        if self.start is None and self.offsets and len(self.offsets) == 2:
            self.start, self.end = self.offsets
        if self.start is not None and self.end is not None and not self.offsets:
            self.offsets = [self.start, self.end]
        return self


class StatObs(BaseModel):
    kind: str
    value: float
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    p_value: Optional[float] = None
    group_a: Optional[str] = None
    group_b: Optional[str] = None
    sentence: Optional[str] = None


class VisualAsset(BaseModel):
    kind: str
    caption: Optional[str] = None
    image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    local_id: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[List[Any]] = None
    bbox_pixels: Optional[List[Any]] = None
    rows: Optional[List[List[Dict[str, Any]]]] = None
    footnotes: List[str] = Field(default_factory=list)
    csv_path: Optional[str] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None


class Recommendation(BaseModel):
    id: str
    number: int
    text: str
    grade: Optional[str] = None
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_sections: List[Dict[str, Any]] = Field(default_factory=list)
    supplementary_text: Optional[List[str]] = None


class ExtractionResult(BaseModel):
    doc_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Recommendation] = Field(default_factory=list)
    references_enriched: List[Dict[str, Any]] = Field(default_factory=list)
    umls_links: List[UmlsLink] = Field(default_factory=list)
    umls_links_local: List[UmlsLink] = Field(default_factory=list)
    statistics: List[StatObs] = Field(default_factory=list)
    figures: List[VisualAsset] = Field(default_factory=list)
    tables: List[VisualAsset] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)
    page_map: List[Dict[str, Any]] = Field(default_factory=list)
    doc_specific: Dict[str, Any] = Field(default_factory=dict)


class LinkRequest(BaseModel):
    text: str
    top_k: int = Field(default=20, ge=1, le=100)


class LinkResponse(BaseModel):
    doc_id: Optional[str] = None
    umls_links: List[UmlsLink] = Field(default_factory=list)


__all__ = [
    "UmlsLink",
    "StatObs",
    "VisualAsset",
    "Recommendation",
    "ExtractionResult",
    "LinkRequest",
    "LinkResponse",
]
