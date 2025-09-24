"""
Pydantic schemas for IFU (Instructions For Use) documents.

These schemas capture:
- Regulatory requirements (FDA 21 CFR Part 801, EU MDR)
- Common IFU sections for interventional pulmonary devices
- Full provenance tracking
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date


class Provenance(BaseModel):
    """Document provenance and source tracking."""
    doc_id: str
    source_path: str
    url: Optional[str] = None
    sha256: str
    pages: List[int] = Field(default_factory=list)


class MRISafety(BaseModel):
    """MRI safety information per ASTM F2503."""
    status: Optional[str] = Field(
        None, 
        description="MR Safe / MR Conditional / MR Unsafe per ASTM F2503"
    )
    conditions: Optional[str] = Field(
        None,
        description="Conditions for safe use (e.g., '3.0T max, SAR < 2 W/kg')"
    )
    prov: Optional[Provenance] = None


class Reprocessing(BaseModel):
    """Reprocessing and cleaning instructions."""
    single_use: Optional[bool] = None
    cleaning: Optional[str] = None
    disinfection: Optional[str] = None
    sterilization: Optional[str] = None
    drying_storage: Optional[str] = None
    accessories_required: Optional[List[str]] = None
    prov: Optional[Provenance] = None


class Compatibility(BaseModel):
    """Device compatibility information."""
    bronch_channel_mm_min: Optional[float] = None
    compatible_scopes: Optional[List[str]] = None
    accessories: Optional[List[str]] = None
    other: Optional[str] = None
    prov: Optional[Provenance] = None


class Dimensions(BaseModel):
    """Physical dimensions of the device."""
    od_mm: Optional[float] = None
    length_mm: Optional[float] = None
    other_dims: Dict[str, str] = Field(default_factory=dict)
    prov: Optional[Provenance] = None


class RegIdentifiers(BaseModel):
    """Regulatory identifiers and classifications."""
    udi_di: Optional[List[str]] = Field(None, description="UDI Device Identifier(s)")
    basic_udi_di: Optional[str] = Field(None, description="EU Basic UDI-DI")
    catalog_numbers: Optional[List[str]] = None
    model_numbers: Optional[List[str]] = None
    product_codes: Optional[List[str]] = Field(None, description="FDA product code(s)")
    gmdn_terms: Optional[List[str]] = Field(None, description="GMDN terms")
    pma_numbers: Optional[List[str]] = None
    k510_numbers: Optional[List[str]] = None
    mr_safety_status: Optional[str] = Field(None, description="MR safety status from regulatory database")
    prov: Optional[Provenance] = None


class IFUSection(BaseModel):
    """Generic IFU section with title and text."""
    title: str
    text: str
    prov: Optional[Provenance] = None


class IFUMetadata(BaseModel):
    """Core IFU metadata and document information."""
    manufacturer: Optional[str] = None
    device_family: Optional[str] = None
    trade_name: Optional[str] = None
    intended_user: Optional[str] = Field(default="HCP", description="Healthcare Professional")
    language: Optional[str] = Field(default="en")
    country_scope: Optional[List[str]] = None
    revision_id: Optional[str] = None
    revision_date: Optional[date] = None
    effective_date: Optional[date] = None
    copyright_notice: Optional[str] = None
    contact: Optional[str] = None
    website: Optional[str] = None


class IFURecord(BaseModel):
    """Complete IFU record with all sections and metadata."""
    ifu_metadata: IFUMetadata
    regulatory: RegIdentifiers
    indications: Optional[IFUSection] = None
    contraindications: Optional[IFUSection] = None
    warnings: Optional[IFUSection] = None
    precautions: Optional[IFUSection] = None
    adverse_events: Optional[IFUSection] = None
    directions_for_use: Optional[IFUSection] = None
    troubleshooting: Optional[IFUSection] = None
    maintenance: Optional[IFUSection] = None
    disposal: Optional[IFUSection] = None
    reprocessing: Optional[Reprocessing] = None
    mri_safety: Optional[MRISafety] = None
    compatibility: Optional[Compatibility] = None
    dimensions: Optional[Dimensions] = None
    tables_csv: List[str] = Field(default_factory=list, description="Paths to exported CSV tables")
    figures: List[str] = Field(default_factory=list, description="Paths to extracted figure images")
    fulltext_md_path: Optional[str] = Field(None, description="Path to Markdown export for fallback")
    extracted_at: date