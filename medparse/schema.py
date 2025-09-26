"""Canonical data models for Medparse document artifacts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, Field


class Concept(BaseModel):
    """Normalized UMLS (or equivalent) concept mention."""

    cui: str
    tui: Optional[str] = None
    pref_label: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    offsets: List[Tuple[int, int]] = Field(default_factory=list)
    source: Optional[str] = None
    score: Optional[float] = None


class StatResult(BaseModel):
    """Structured statistical result extracted from text or tables."""

    type: str
    value: Optional[Union[float, str]] = None
    ci_low: Optional[float] = Field(default=None, alias="ciLow")
    ci_high: Optional[float] = Field(default=None, alias="ciHigh")
    p: Optional[Union[float, str]] = None
    n: Optional[int] = None
    group_labels: List[str] = Field(default_factory=list)
    text_span: Optional[str] = None
    table_ref: Optional[str] = None
    figure_ref: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class Figure(BaseModel):
    """Representation of a figure detected in the source document."""

    id: str
    caption: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[Sequence[float]] = None
    ocr_text: Optional[str] = None
    image_path: Optional[str] = None


class Table(BaseModel):
    """Representation of a table with preserved structure and exports."""

    id: str
    caption: Optional[str] = None
    page: Optional[int] = None
    structure_json: Optional[List[List[Union[str, float, int, None]]]] = None
    csv_path: Optional[str] = None


class Reference(BaseModel):
    """Bibliographic reference optionally enriched from PubMed."""

    raw: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    title: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[int] = None
    abstract: Optional[str] = None


class CrossRef(BaseModel):
    """In-document cross reference linking text spans to artifacts."""

    source_type: str
    source_id: Optional[str] = None
    target_type: str
    target_id: Optional[str] = None
    anchor_text: Optional[str] = None
    page: Optional[int] = None


class Quality(BaseModel):
    """Quality summary for the extracted document artifact."""

    completeness_score: Optional[float] = None
    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class DocumentArtifact(BaseModel):
    """Top-level payload produced by the Medparse extraction pipeline."""

    meta: Dict[str, Any] = Field(default_factory=dict)
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    concepts: List[Concept] = Field(default_factory=list)
    statistics: List[StatResult] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    crossrefs: List[CrossRef] = Field(default_factory=list)
    quality: Optional[Quality] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "Concept",
    "StatResult",
    "Figure",
    "Table",
    "Reference",
    "CrossRef",
    "Quality",
    "DocumentArtifact",
]
