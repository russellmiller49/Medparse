"""Schema for peer-reviewed article extraction."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PopulationStats(BaseModel):
    """Study population summary."""

    n_patients: Optional[int] = None
    n_lesions: Optional[int] = None
    lesion_size_bins: Dict[str, int] = Field(default_factory=dict)
    bronchus_sign_rate: Optional[float] = None
    tools_used: List[str] = Field(default_factory=list)


class ArticleDiagnosticOutcome(BaseModel):
    """Diagnostic outcome metrics for an article."""

    doc_id: str
    yield_overall: Optional[float] = None
    yield_definition: Optional[str] = None
    numerator_definition: Optional[str] = None
    denominator_definition: Optional[str] = None
    followup_window_months: Optional[int] = None
    handles_nonspecific_pathology: Optional[bool] = None
    nonspecific_handling_notes: Optional[str] = None
    tool_yield: Dict[str, float] = Field(default_factory=dict)
    exclusive_by_tool: Dict[str, float] = Field(default_factory=dict)
    ngs_adequacy_by_tool: Dict[str, float] = Field(default_factory=dict)
    complications: Dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None


class ArticleExtract(BaseModel):
    """Container for article-level structured data."""

    doc_id: str
    population: PopulationStats = Field(default_factory=PopulationStats)
    diagnostic_outcome: ArticleDiagnosticOutcome
    schema_version: str = "1.0"


__all__ = [
    "PopulationStats",
    "ArticleDiagnosticOutcome",
    "ArticleExtract",
]
