"""Typed models exposed by the Medparse API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UmlsLink(BaseModel):
    cui: str
    text: str
    tui: List[str] = Field(default_factory=list)
    score: float = Field(default=0.0)
    offsets: Optional[List[int]] = None
    sentence: Optional[str] = None
    preferred_name: Optional[str] = None
    source: Optional[str] = None


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
    caption: str
    image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    local_id: Optional[str] = None


class ExtractionResult(BaseModel):
    doc_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    references_enriched: List[Dict[str, Any]] = Field(default_factory=list)
    umls_links: List[UmlsLink] = Field(default_factory=list)
    umls_links_local: List[UmlsLink] = Field(default_factory=list)
    statistics: List[StatObs] = Field(default_factory=list)
    figures: List[VisualAsset] = Field(default_factory=list)
    tables: List[VisualAsset] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)


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
    "ExtractionResult",
    "LinkRequest",
    "LinkResponse",
]
