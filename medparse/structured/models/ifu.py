"""Schema for Instructions for Use (IFU) payloads."""
from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class IFUWarning(BaseModel):
    """Tagged warning/caution extracted from an IFU."""

    id: str
    doc_id: str
    severity: str
    section: Optional[str] = None
    text: str
    page: Optional[int] = None
    span: Optional[Tuple[int, int]] = None


class IFUStep(BaseModel):
    """Procedure or setup step extracted from an IFU."""

    number: Optional[str] = None
    text: str
    page: Optional[int] = None


class IFUExtract(BaseModel):
    """Container for IFU-specific structured fields."""

    doc_id: str
    device_name: Optional[str] = None
    model: Optional[str] = None
    software_versions: List[str] = Field(default_factory=list)
    part_numbers: List[str] = Field(default_factory=list)
    intended_use: List[str] = Field(default_factory=list)
    indications_for_use: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    warnings: List[IFUWarning] = Field(default_factory=list)
    cautions: List[IFUWarning] = Field(default_factory=list)
    notes: List[IFUWarning] = Field(default_factory=list)
    setup_steps: List[IFUStep] = Field(default_factory=list)
    procedure_steps: List[IFUStep] = Field(default_factory=list)
    compatible_accessories: List[str] = Field(default_factory=list)
    schema_version: str = "1.0"


__all__ = [
    "IFUWarning",
    "IFUStep",
    "IFUExtract",
]
